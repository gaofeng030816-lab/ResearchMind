"""Safe PDF opening, text extraction, and page rendering with PyMuPDF."""

from __future__ import annotations

from dataclasses import dataclass, field
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
from researchmind.pdf.layout import normalize_block_text, order_text_blocks


DEFAULT_PDF_MAX_SIZE_BYTES = DEFAULT_PDF_MAX_SIZE_MB * 1024 * 1024
PDF_MAGIC = b"%PDF-"
MAX_RENDER_ZOOM = 5.0
MIN_FIGURE_DIMENSION = 24.0


@dataclass(frozen=True)
class OpenedDocument:
    """An opened document represented only by ResearchMind-owned data.

    PyMuPDF handles are deliberately not retained or exposed. Streamlit can
    cache this value so metadata and text extraction happen once per file.
    """

    document: Document
    pages: tuple[Page, ...]
    max_size_bytes: int = field(repr=False)


def open_pdf(
    path: Path,
    *,
    max_size_bytes: int = DEFAULT_PDF_MAX_SIZE_BYTES,
) -> OpenedDocument:
    """Validate and extract a local PDF into in-memory project models."""

    validated_path = _validate_pdf_file(path, max_size_bytes=max_size_bytes)

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

    return OpenedDocument(
        document=document,
        pages=pages,
        max_size_bytes=max_size_bytes,
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
                matrix=pymupdf.Matrix(normalized_zoom, normalized_zoom),
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
    try:
        with pymupdf.open(source_path) as source:
            source_page = source.load_page(page_number - 1)
            return tuple(
                source_page.get_pixmap(
                    matrix=pymupdf.Matrix(normalized_zoom, normalized_zoom),
                    clip=pymupdf.Rect(figure.bbox),
                    alpha=False,
                ).tobytes("png")
                for figure in page_model.figures
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

        block_text = normalize_block_text(str(raw_block[4]))
        if not block_text:
            continue

        blocks.append(
            TextBlock(
                block_index=int(raw_block[5]),
                text=block_text,
                bbox=bbox,
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
