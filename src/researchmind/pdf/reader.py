"""Safe PDF opening, text extraction, and page rendering with PyMuPDF."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
import hashlib
import math
from pathlib import Path

import pymupdf

from researchmind.config import DEFAULT_PDF_MAX_SIZE_MB
from researchmind.models import Document, FigureRegion, Page, TextBlock
from researchmind.pdf.errors import (
    PdfError,
    PdfExtractionError,
    PdfPageError,
    PdfRenderError,
    PdfValidationError,
)
from researchmind.pdf.layout import (
    classify_block_role,
    normalize_block_text,
    normalize_formula_text,
    order_text_blocks,
)


DEFAULT_PDF_MAX_SIZE_BYTES = DEFAULT_PDF_MAX_SIZE_MB * 1024 * 1024
DEFAULT_PDF_VIEWER_MAX_SIZE_BYTES = 10 * 1024 * 1024
PDF_MAGIC = b"%PDF-"
MAX_RENDER_ZOOM = 5.0
MIN_FIGURE_DIMENSION = 24.0
RENDER_CACHE_SIZE = 32

PdfFileRevision = tuple[int, int, int, int]


@dataclass(frozen=True)
class OpenedDocument:
    """An opened document represented only by ResearchMind-owned data.

    PyMuPDF handles are deliberately not retained or exposed. Streamlit can
    cache this value so metadata and text extraction happen once per file.
    """

    document: Document
    pages: tuple[Page, ...]
    max_size_bytes: int = field(repr=False)
    content_sha256: str = field(default="", repr=False)


@dataclass(frozen=True)
class PdfViewerSource:
    """Validated immutable bytes passed only to the local browser PDF viewer."""

    content: bytes = field(repr=False)
    revision: str


def open_pdf(
    path: Path,
    *,
    max_size_bytes: int = DEFAULT_PDF_MAX_SIZE_BYTES,
) -> OpenedDocument:
    """Validate and extract a local PDF into in-memory project models."""

    validated_path = _validate_pdf_file(path, max_size_bytes=max_size_bytes)

    initial_revision = _file_revision(validated_path)
    content_sha256 = _content_sha256(validated_path)
    try:
        with pymupdf.open(validated_path) as source:
            if source.needs_pass:
                raise PdfExtractionError(
                    f"Password-protected PDF files are not supported: {validated_path.name}"
                )
            if source.page_count < 1:
                raise PdfExtractionError(
                    f"The PDF contains no readable pages: {validated_path.name}"
                )

            metadata = source.metadata or {}
            pages = tuple(
                _extract_loaded_page(source.load_page(index), index + 1)
                for index in range(source.page_count)
            )
            document = Document(
                id=_document_id(validated_path),
                title=_metadata_title(metadata, validated_path),
                authors=_metadata_authors(metadata),
                source_type="pdf",
                path=validated_path,
                num_pages=source.page_count,
            )
    except PdfError:
        raise
    except Exception as exc:
        raise PdfExtractionError(
            f"Could not read PDF file: {validated_path.name}"
        ) from exc
    if _file_revision(validated_path) != initial_revision:
        raise PdfExtractionError(
            f"PDF changed while it was being opened: {validated_path.name}"
        )

    return OpenedDocument(
        document=document,
        pages=pages,
        max_size_bytes=max_size_bytes,
        content_sha256=content_sha256,
    )


def extract_page(opened_document: OpenedDocument, page_number: int) -> Page:
    """Return one previously extracted, one-based page."""

    _validate_page_number(opened_document, page_number)
    return opened_document.pages[page_number - 1]


def render_page_image(
    opened_document: OpenedDocument,
    page_number: int,
    *,
    zoom: float = 1.0,
) -> bytes:
    """Render a one-based page to PNG bytes at the requested zoom."""

    _validate_page_number(opened_document, page_number)
    normalized_zoom = _validate_zoom(zoom)
    source_path = _validate_pdf_file(
        opened_document.document.path,
        max_size_bytes=opened_document.max_size_bytes,
    )
    return _render_page_image_cached(
        source_path,
        _file_revision(source_path),
        page_number,
        normalized_zoom,
    )


def load_pdf_viewer_source(
    path: Path,
    *,
    expected_sha256: str,
    max_size_bytes: int,
    viewer_max_size_bytes: int = DEFAULT_PDF_VIEWER_MAX_SIZE_BYTES,
) -> PdfViewerSource:
    """Read one unchanged local PDF for the bounded browser viewer."""

    from researchmind.pdf.errors import PdfViewerError

    if (
        not isinstance(expected_sha256, str)
        or len(expected_sha256) != 64
        or any(character not in "0123456789abcdef" for character in expected_sha256)
    ):
        raise PdfViewerError("The opened PDF revision is invalid. Reopen the PDF.")
    source_path = _validate_pdf_file(path, max_size_bytes=max_size_bytes)
    if (
        isinstance(viewer_max_size_bytes, bool)
        or not isinstance(viewer_max_size_bytes, int)
        or viewer_max_size_bytes <= 0
    ):
        raise PdfViewerError("PDF viewer size limit must be a positive integer.")
    try:
        size = source_path.stat().st_size
    except OSError as exc:
        raise PdfViewerError("PDF is no longer readable by the text-layer viewer.") from exc
    if size > viewer_max_size_bytes:
        limit_mib = viewer_max_size_bytes // (1024 * 1024)
        raise PdfViewerError(
            f"Browser text-layer viewing currently supports PDFs up to {limit_mib} MiB."
        )
    try:
        content = source_path.read_bytes()
    except OSError as exc:
        raise PdfViewerError("PDF is no longer readable by the text-layer viewer.") from exc
    actual_sha256 = hashlib.sha256(content).hexdigest()
    if actual_sha256 != expected_sha256:
        raise PdfViewerError(
            "PDF changed after it was opened. Reopen it before using browser selection."
        )
    return PdfViewerSource(
        content=content,
        revision=f"sha256:{actual_sha256}",
    )


@lru_cache(maxsize=RENDER_CACHE_SIZE)
def _render_page_image_cached(
    source_path: Path,
    _source_revision: PdfFileRevision,
    page_number: int,
    zoom: float,
) -> bytes:
    """Render once per file revision, page, and zoom within this process."""

    try:
        with pymupdf.open(source_path) as source:
            if source.needs_pass:
                raise PdfRenderError(
                    f"Password-protected PDF files are not supported: {source_path.name}"
                )
            if page_number > source.page_count:
                raise PdfPageError(
                    f"Page {page_number} is no longer available in {source_path.name}."
                )

            page = source.load_page(page_number - 1)
            pixmap = page.get_pixmap(
                matrix=pymupdf.Matrix(zoom, zoom),
                alpha=False,
            )
            return pixmap.tobytes("png")
    except PdfError:
        raise
    except Exception as exc:
        raise PdfRenderError(
            f"Could not render page {page_number} of {source_path.name}."
        ) from exc


def render_figure_images(
    opened_document: OpenedDocument,
    page_number: int,
    *,
    zoom: float = 2.0,
) -> tuple[bytes, ...]:
    """Render detected embedded figure regions as standalone PNG images."""

    page_model = extract_page(opened_document, page_number)
    if not page_model.figures:
        return ()

    normalized_zoom = _validate_zoom(zoom)
    source_path = _validate_pdf_file(
        opened_document.document.path,
        max_size_bytes=opened_document.max_size_bytes,
    )
    figure_bboxes = tuple(figure.bbox for figure in page_model.figures)
    return _render_figure_images_cached(
        source_path,
        _file_revision(source_path),
        page_number,
        normalized_zoom,
        figure_bboxes,
    )


@lru_cache(maxsize=RENDER_CACHE_SIZE)
def _render_figure_images_cached(
    source_path: Path,
    _source_revision: PdfFileRevision,
    page_number: int,
    zoom: float,
    figure_bboxes: tuple[tuple[float, float, float, float], ...],
) -> tuple[bytes, ...]:
    """Render figure crops once while keeping the cache revision-aware."""

    try:
        with pymupdf.open(source_path) as source:
            if source.needs_pass:
                raise PdfRenderError(
                    f"Password-protected PDF files are not supported: {source_path.name}"
                )
            if page_number > source.page_count:
                raise PdfPageError(
                    f"Page {page_number} is no longer available in {source_path.name}."
                )
            source_page = source.load_page(page_number - 1)
            return tuple(
                source_page.get_pixmap(
                    matrix=pymupdf.Matrix(zoom, zoom),
                    clip=pymupdf.Rect(bbox),
                    alpha=False,
                ).tobytes("png")
                for bbox in figure_bboxes
            )
    except PdfError:
        raise
    except Exception as exc:
        raise PdfRenderError(
            f"Could not render figure regions on page {page_number} of "
            f"{source_path.name}."
        ) from exc


def _validate_pdf_file(path: Path, *, max_size_bytes: int) -> Path:
    if max_size_bytes <= 0:
        raise PdfValidationError("PDF size limit must be greater than zero.")

    candidate = Path(path).expanduser()
    if candidate.suffix.lower() != ".pdf":
        raise PdfValidationError("Only files with a .pdf extension can be opened.")

    try:
        resolved_path = candidate.resolve(strict=True)
    except FileNotFoundError as exc:
        raise PdfValidationError(f"PDF file does not exist: {candidate.name}") from exc
    except OSError as exc:
        raise PdfValidationError(f"PDF path is not accessible: {candidate.name}") from exc

    if not resolved_path.is_file():
        raise PdfValidationError(f"PDF path is not a file: {resolved_path.name}")

    try:
        file_size = resolved_path.stat().st_size
        if file_size > max_size_bytes:
            raise PdfValidationError(
                f"PDF file exceeds the configured size limit: {resolved_path.name}"
            )
        with resolved_path.open("rb") as stream:
            magic = stream.read(len(PDF_MAGIC))
    except PdfValidationError:
        raise
    except OSError as exc:
        raise PdfValidationError(
            f"PDF file is not readable: {resolved_path.name}"
        ) from exc

    if magic != PDF_MAGIC:
        raise PdfValidationError(
            f"File does not have a valid PDF signature: {resolved_path.name}"
        )

    return resolved_path


def _file_revision(path: Path) -> PdfFileRevision:
    """Return a cheap cache key that changes when the source file changes."""

    try:
        status = path.stat()
    except OSError:
        raise PdfValidationError(
            f"PDF file is not readable: {path.name}"
        ) from None
    return (
        status.st_size,
        status.st_mtime_ns,
        status.st_ctime_ns,
        status.st_ino,
    )


def _extract_loaded_page(source_page: pymupdf.Page, page_number: int) -> Page:
    try:
        raw_blocks = source_page.get_text("blocks", sort=False)
        raw_images = source_page.get_image_info()
    except Exception as exc:
        raise PdfExtractionError(
            f"Could not extract text from page {page_number}."
        ) from exc

    blocks: list[TextBlock] = []
    for raw_block in raw_blocks:
        block_type = int(raw_block[6])
        bbox = tuple(float(value) for value in raw_block[:4])
        if block_type != 0:
            continue

        raw_text = str(raw_block[4])
        paragraph_text = normalize_block_text(raw_text)
        if not paragraph_text:
            continue
        role = classify_block_role(paragraph_text)
        block_text = (
            normalize_formula_text(raw_text)
            if role == "formula"
            else paragraph_text
        )

        blocks.append(
            TextBlock(
                block_index=int(raw_block[5]),
                text=block_text,
                bbox=bbox,
                role=role,
            )
        )

    ordered_blocks = order_text_blocks(blocks)
    page_text = "\n\n".join(block.text for block in ordered_blocks)
    figures = _extract_figure_regions(raw_images)
    return Page(
        page_number=page_number,
        text=page_text,
        blocks=ordered_blocks,
        figures=figures,
    )


def _is_meaningful_figure(bbox: tuple[float, float, float, float]) -> bool:
    width = bbox[2] - bbox[0]
    height = bbox[3] - bbox[1]
    return width >= MIN_FIGURE_DIMENSION and height >= MIN_FIGURE_DIMENSION


def _extract_figure_regions(
    raw_images: list[dict[str, object]],
) -> list[FigureRegion]:
    regions: list[FigureRegion] = []
    for image_info in raw_images:
        raw_bbox = image_info.get("bbox")
        if not isinstance(raw_bbox, (list, tuple)) or len(raw_bbox) != 4:
            continue
        try:
            bbox = tuple(float(value) for value in raw_bbox)
        except (TypeError, ValueError):
            continue
        if _is_meaningful_figure(bbox):
            regions.append(
                FigureRegion(figure_index=len(regions), bbox=bbox)
            )
    return regions


def _metadata_title(metadata: dict[str, object], path: Path) -> str:
    title = str(metadata.get("title") or "").strip()
    return title or path.stem


def _metadata_authors(metadata: dict[str, object]) -> list[str]:
    author_text = str(metadata.get("author") or "").strip()
    if not author_text:
        return []
    return [author.strip() for author in author_text.split(";") if author.strip()]


def _document_id(path: Path) -> str:
    normalized_path = str(path).casefold().encode("utf-8")
    return hashlib.sha256(normalized_path).hexdigest()[:16]


def _content_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise PdfValidationError(f"PDF file is not readable: {path.name}") from exc
    return digest.hexdigest()


def _validate_page_number(
    opened_document: OpenedDocument,
    page_number: int,
) -> None:
    if isinstance(page_number, bool) or not isinstance(page_number, int):
        raise PdfPageError("Page number must be an integer.")
    if page_number < 1 or page_number > opened_document.document.num_pages:
        raise PdfPageError(
            f"Page number must be between 1 and {opened_document.document.num_pages}."
        )


def _validate_zoom(zoom: float) -> float:
    if isinstance(zoom, bool) or not isinstance(zoom, (int, float)):
        raise PdfRenderError("Zoom must be a number.")

    normalized_zoom = float(zoom)
    if not math.isfinite(normalized_zoom) or not 0 < normalized_zoom <= MAX_RENDER_ZOOM:
        raise PdfRenderError(
            f"Zoom must be greater than zero and no more than {MAX_RENDER_ZOOM}."
        )
    return normalized_zoom
