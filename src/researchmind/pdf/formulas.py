"""Revision-bound formula-region detection and crop rendering."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import math
import re
import unicodedata

import pymupdf

from researchmind.models import BoundingBox, FormulaCrop, FormulaRegion
from researchmind.pdf.errors import PdfFormulaError
from researchmind.pdf.reader import OpenedDocument, load_pdf_viewer_source


FORMULA_CROP_ZOOM = 3.0
FORMULA_CROP_PADDING_POINTS = 8.0
MAX_FORMULA_CROP_PIXELS = 4_000_000
MAX_FORMULA_CROP_BYTES = 2 * 1024 * 1024
MAX_FORMULA_SOURCE_CHARS = 500
MAX_FORMULA_TEXT_LINES = 4
MAX_FORMULA_CLUSTER_LINES = 16
MAX_FORMULA_CLUSTER_HEIGHT_POINTS = 96.0
MIN_EMBEDDED_FORMULA_ASPECT = 2.2
SHORT_FORMULA_BALANCE_LIMIT = 8

_MATH_FONT_MARKERS = (
    "cambria math",
    "cmex",
    "cmmi",
    "cmsy",
    "latinmodernmath",
    "math",
    "msam",
    "msbm",
    "stix",
    "symbol",
    "wasy",
)
_STRONG_MATH_SYMBOLS = frozenset(
    "∫∮∑∏√∂∇∞≤≥≈≠±∓∈∉⊂⊆⊃⊇∪∩→←⇒⇔∀∃ℝℤℕℚ⊗⊕⋅×÷"
)
_GREEK_PATTERN = re.compile("[Α-ωϑϕϖϱ]", re.UNICODE)
_RELATION_PATTERN = re.compile(r"(?:=|<|>|≤|≥|≈|≠|∝|∼|→|⇒)")
_MATH_PUNCTUATION_PATTERN = re.compile(r"[+\-*/^_=<>|(){}\[\],.:]")


@dataclass(frozen=True)
class _DetectedFragment:
    bbox: BoundingBox
    source_text: str
    score: float
    signals: tuple[str, ...]
    line_count: int


def detect_formula_regions(
    opened_document: OpenedDocument,
    page_number: int,
    *,
    include_inline: bool = False,
) -> tuple[FormulaRegion, ...]:
    """Detect bounded formula regions without OCR or network access."""

    source = _load_revision_bound_source(opened_document)
    try:
        with pymupdf.open(stream=source.content, filetype="pdf") as pdf:
            page = _load_page(pdf, page_number)
            text_fragments = _formula_text_fragments(page, include_inline=include_inline)
            clusters = tuple(
                cluster
                for cluster in _cluster_fragments(text_fragments)
                if max(item.score for item in cluster) >= 0.48
                and _cluster_is_bounded(cluster)
            )
            regions = [
                _text_region(opened_document, page_number, cluster)
                for cluster in clusters
            ]
            regions.extend(_image_regions(opened_document, page, page_number))
    except PdfFormulaError:
        raise
    except Exception as exc:
        raise PdfFormulaError(
            f"Could not detect formula regions on page {page_number}."
        ) from exc
    return tuple(sorted(regions, key=lambda item: (item.bbox[1], item.bbox[0])))


def render_formula_crop(
    opened_document: OpenedDocument,
    region: FormulaRegion,
    *,
    zoom: float = FORMULA_CROP_ZOOM,
    padding_points: float = FORMULA_CROP_PADDING_POINTS,
) -> FormulaCrop:
    """Render exactly one validated formula region to an in-memory PNG."""

    _validate_region_binding(opened_document, region)
    normalized_zoom = _positive_finite(zoom, label="Formula crop zoom")
    normalized_padding = _nonnegative_finite(
        padding_points,
        label="Formula crop padding",
    )
    if normalized_zoom > 6.0:
        raise PdfFormulaError("Formula crop zoom must not exceed 6.0.")
    if normalized_padding > 24.0:
        raise PdfFormulaError("Formula crop padding must not exceed 24 points.")

    source = _load_revision_bound_source(opened_document)
    try:
        with pymupdf.open(stream=source.content, filetype="pdf") as pdf:
            page = _load_page(pdf, region.page_number)
            page_rect = page.rect
            clip = pymupdf.Rect(region.bbox)
            if not _rect_is_inside(clip, page_rect):
                raise PdfFormulaError("Formula region is outside the current PDF page.")
            padded = pymupdf.Rect(
                max(page_rect.x0, clip.x0 - normalized_padding),
                max(page_rect.y0, clip.y0 - normalized_padding),
                min(page_rect.x1, clip.x1 + normalized_padding),
                min(page_rect.y1, clip.y1 + normalized_padding),
            )
            width_px = max(1, math.ceil(padded.width * normalized_zoom))
            height_px = max(1, math.ceil(padded.height * normalized_zoom))
            if width_px * height_px > MAX_FORMULA_CROP_PIXELS:
                raise PdfFormulaError("Formula crop exceeds the pixel limit.")
            pixmap = page.get_pixmap(
                matrix=pymupdf.Matrix(normalized_zoom, normalized_zoom),
                clip=padded,
                alpha=False,
            )
            png_bytes = pixmap.tobytes("png")
    except PdfFormulaError:
        raise
    except Exception as exc:
        raise PdfFormulaError("Could not render the selected formula region.") from exc

    if len(png_bytes) > MAX_FORMULA_CROP_BYTES:
        raise PdfFormulaError("Formula crop exceeds the byte limit.")
    crop_sha256 = sha256(png_bytes).hexdigest()
    return FormulaCrop(
        region=region,
        png_bytes=png_bytes,
        sha256=crop_sha256,
        width_px=pixmap.width,
        height_px=pixmap.height,
    )


def _load_revision_bound_source(opened_document: OpenedDocument):
    expected = opened_document.content_sha256
    if not _is_sha256(expected):
        raise PdfFormulaError("The opened PDF revision is invalid. Reopen the PDF.")
    try:
        return load_pdf_viewer_source(
            opened_document.document.path,
            expected_sha256=expected,
            max_size_bytes=opened_document.max_size_bytes,
            viewer_max_size_bytes=opened_document.max_size_bytes,
        )
    except Exception as exc:
        raise PdfFormulaError(
            "The PDF changed or is no longer readable. Reopen it before formula recognition."
        ) from exc


def _load_page(pdf: pymupdf.Document, page_number: int) -> pymupdf.Page:
    if isinstance(page_number, bool) or not isinstance(page_number, int):
        raise PdfFormulaError("Formula page number must be an integer.")
    if page_number < 1 or page_number > pdf.page_count:
        raise PdfFormulaError("Formula page number is outside the current PDF.")
    return pdf.load_page(page_number - 1)


def _formula_text_fragments(
    page: pymupdf.Page,
    *,
    include_inline: bool,
) -> list[_DetectedFragment]:
    raw = page.get_text("dict", sort=False)
    page_rect = page.rect
    fragments: list[_DetectedFragment] = []
    for block in raw.get("blocks", []):
        if block.get("type") != 0:
            continue
        lines = [
            line
            for line in block.get("lines", [])
            if any(
                str(span.get("text", "")).strip()
                for span in line.get("spans", [])
            )
        ]
        # Display formulas may be multiline (cases, aligned equations, matrices),
        # but larger math-heavy blocks are usually algorithms, tables, or proof
        # paragraphs. Keep the detector conservative so a recognizer never receives
        # an over-merged page block by default.
        if len(lines) > MAX_FORMULA_TEXT_LINES:
            continue
        spans = [
            span
            for line in lines
            for span in line.get("spans", [])
            if str(span.get("text", "")).strip()
        ]
        if not spans:
            continue
        text = _clean_source_text("".join(str(span.get("text", "")) for span in spans))
        if not text or len(text) > MAX_FORMULA_SOURCE_CHARS:
            continue
        bbox = _safe_bbox(block.get("bbox"), page_rect)
        if bbox is None:
            continue
        score, signals = _score_formula_fragment(spans, text)
        centered = abs(((bbox[0] + bbox[2]) / 2.0) - (page_rect.width / 2.0)) <= (
            page_rect.width * 0.38
        )
        short_enough = len(text) <= (220 if include_inline else 140)
        # Low-scoring script, numerator, denominator, radical, and matrix
        # fragments are retained here so spatial clustering can join them to a
        # stronger formula fragment. A complete cluster must still contain a
        # score of at least 0.48 before it becomes a public candidate.
        threshold = 0.22 if include_inline else 0.25
        if score < threshold or not short_enough or (not include_inline and not centered):
            continue
        fragments.append(
            _DetectedFragment(
                bbox=bbox,
                source_text=text,
                score=score,
                signals=signals,
                line_count=len(lines),
            )
        )
    return fragments


def _has_balanced_delimiters(text: str) -> bool:
    pairs = {")": "(", "]": "[", "}": "{"}
    stack: list[str] = []
    for character in text:
        if character in "([{":
            stack.append(character)
        elif character in pairs:
            if not stack or stack.pop() != pairs[character]:
                return False
    return not stack


def _score_formula_fragment(
    spans: list[dict[str, object]],
    text: str,
) -> tuple[float, tuple[str, ...]]:
    visible_chars = max(1, sum(not character.isspace() for character in text))
    math_font_chars = 0
    sizes: list[float] = []
    signals: set[str] = set()
    for span in spans:
        span_text = str(span.get("text", ""))
        font = str(span.get("font", "")).casefold()
        if any(marker in font for marker in _MATH_FONT_MARKERS):
            math_font_chars += sum(not character.isspace() for character in span_text)
            signals.add("math_font")
        try:
            size = float(span.get("size", 0.0))
        except (TypeError, ValueError):
            size = 0.0
        if math.isfinite(size) and size > 0:
            sizes.append(size)

    if any(character in _STRONG_MATH_SYMBOLS for character in text):
        signals.add("strong_symbol")
    if _GREEK_PATTERN.search(text):
        signals.add("greek")
    if _RELATION_PATTERN.search(text):
        signals.add("relation")
    punctuation_ratio = len(_MATH_PUNCTUATION_PATTERN.findall(text)) / visible_chars
    if punctuation_ratio >= 0.12:
        signals.add("operator_density")
    if sizes and max(sizes) - min(sizes) >= 2.0:
        signals.add("script_sizes")

    font_ratio = math_font_chars / visible_chars
    score = min(0.55, font_ratio * 0.62)
    score += 0.28 if "strong_symbol" in signals else 0.0
    score += 0.14 if "relation" in signals else 0.0
    score += 0.10 if "operator_density" in signals else 0.0
    score += 0.09 if "script_sizes" in signals else 0.0
    score += 0.06 if "greek" in signals else 0.0
    if len(text.split()) > 18:
        score -= 0.25
    if text.endswith((".", "?", "!")) and len(text.split()) >= 6:
        score -= 0.20
    return max(0.0, min(0.99, score)), tuple(sorted(signals))


def _cluster_fragments(
    fragments: list[_DetectedFragment],
) -> list[tuple[_DetectedFragment, ...]]:
    remaining = set(range(len(fragments)))
    clusters: list[tuple[_DetectedFragment, ...]] = []
    while remaining:
        seed = remaining.pop()
        members = {seed}
        changed = True
        while changed:
            changed = False
            for index in tuple(remaining):
                if any(
                    _fragments_are_near(fragments[index], fragments[member])
                    for member in members
                ):
                    remaining.remove(index)
                    members.add(index)
                    changed = True
        clusters.append(tuple(fragments[index] for index in sorted(members)))
    return clusters


def _cluster_is_bounded(cluster: tuple[_DetectedFragment, ...]) -> bool:
    bbox = _union_bbox(tuple(item.bbox for item in cluster))
    multiline_count = sum(item.line_count for item in cluster)
    visible_text = "".join(item.source_text for item in cluster)
    visible_text = "".join(visible_text.split())
    return (
        multiline_count <= MAX_FORMULA_CLUSTER_LINES
        and bbox[3] - bbox[1] <= MAX_FORMULA_CLUSTER_HEIGHT_POINTS
        and (
            len(visible_text) > SHORT_FORMULA_BALANCE_LIMIT
            or _has_balanced_delimiters(visible_text)
        )
    )


def _fragments_are_near(first: _DetectedFragment, second: _DetectedFragment) -> bool:
    horizontal_gap = max(
        0.0,
        max(first.bbox[0], second.bbox[0]) - min(first.bbox[2], second.bbox[2]),
    )
    vertical_gap = max(
        0.0,
        max(first.bbox[1], second.bbox[1]) - min(first.bbox[3], second.bbox[3]),
    )
    return horizontal_gap <= 30.0 and vertical_gap <= 36.0


def _text_region(
    opened_document: OpenedDocument,
    page_number: int,
    cluster: tuple[_DetectedFragment, ...],
) -> FormulaRegion:
    bbox = _union_bbox(tuple(item.bbox for item in cluster))
    source_text = " ".join(item.source_text for item in cluster).strip()
    confidence = min(
        0.99,
        max(item.score for item in cluster) + (0.04 if len(cluster) > 1 else 0.0),
    )
    signals = tuple(sorted({signal for item in cluster for signal in item.signals}))
    return _build_region(
        opened_document,
        page_number=page_number,
        bbox=bbox,
        source_kind="digital_text",
        detector_origin="pymupdf_text_geometry_v1",
        detector_confidence=confidence,
        signals=signals,
        source_text=source_text[:MAX_FORMULA_SOURCE_CHARS],
    )


def _image_regions(
    opened_document: OpenedDocument,
    page: pymupdf.Page,
    page_number: int,
) -> list[FormulaRegion]:
    page_area = max(1.0, page.rect.width * page.rect.height)
    regions: list[FormulaRegion] = []
    for image_info in page.get_image_info():
        bbox = _safe_bbox(image_info.get("bbox"), page.rect)
        if bbox is None:
            continue
        width = bbox[2] - bbox[0]
        height = bbox[3] - bbox[1]
        area_ratio = (width * height) / page_area
        aspect = width / max(height, 1.0)
        if (
            width < 24.0
            or height < 10.0
            or area_ratio > 0.35
            or aspect < MIN_EMBEDDED_FORMULA_ASPECT
        ):
            continue
        regions.append(
            _build_region(
                opened_document,
                page_number=page_number,
                bbox=bbox,
                source_kind="embedded_image",
                detector_origin="pymupdf_embedded_image_geometry_v1",
                detector_confidence=0.55,
                signals=("embedded_image", "formula_like_aspect"),
                source_text=None,
            )
        )
    return regions


def _build_region(
    opened_document: OpenedDocument,
    *,
    page_number: int,
    bbox: BoundingBox,
    source_kind: str,
    detector_origin: str,
    detector_confidence: float,
    signals: tuple[str, ...],
    source_text: str | None,
) -> FormulaRegion:
    revision = f"sha256:{opened_document.content_sha256}"
    payload = "|".join(
        (
            opened_document.document.id,
            revision,
            str(page_number),
            ",".join(f"{value:.3f}" for value in bbox),
            source_kind,
            detector_origin,
        )
    ).encode("utf-8")
    return FormulaRegion(
        id=f"formula-region-{sha256(payload).hexdigest()[:32]}",
        document_id=opened_document.document.id,
        document_revision=revision,
        page_number=page_number,
        bbox=bbox,
        kind="display",
        source_kind=source_kind,  # type: ignore[arg-type]
        detector_origin=detector_origin,
        detector_confidence=detector_confidence,
        signals=signals,
        source_text=source_text,
    )


def _validate_region_binding(
    opened_document: OpenedDocument,
    region: FormulaRegion,
) -> None:
    if region.document_id != opened_document.document.id:
        raise PdfFormulaError("Formula region belongs to another document.")
    expected_revision = f"sha256:{opened_document.content_sha256}"
    if region.document_revision != expected_revision:
        raise PdfFormulaError("Formula region is stale. Detect it again.")
    if region.page_number < 1 or region.page_number > opened_document.document.num_pages:
        raise PdfFormulaError("Formula region page is outside the current PDF.")
    if not _valid_bbox(region.bbox):
        raise PdfFormulaError("Formula region geometry is invalid.")


def _safe_bbox(value: object, page_rect: pymupdf.Rect) -> BoundingBox | None:
    if not isinstance(value, (tuple, list)) or len(value) != 4:
        return None
    try:
        bbox = tuple(float(item) for item in value)
    except (TypeError, ValueError):
        return None
    if not _valid_bbox(bbox):
        return None
    rect = pymupdf.Rect(bbox)
    if not _rect_is_inside(rect, page_rect):
        return None
    return bbox  # type: ignore[return-value]


def _valid_bbox(bbox: object) -> bool:
    return (
        isinstance(bbox, tuple)
        and len(bbox) == 4
        and all(
            type(value) in (int, float) and math.isfinite(float(value))
            for value in bbox
        )
        and bbox[0] >= 0
        and bbox[1] >= 0
        and bbox[2] > bbox[0]
        and bbox[3] > bbox[1]
    )


def _rect_is_inside(rect: pymupdf.Rect, page_rect: pymupdf.Rect) -> bool:
    return (
        rect.width > 0
        and rect.height > 0
        and rect.x0 >= page_rect.x0 - 0.01
        and rect.y0 >= page_rect.y0 - 0.01
        and rect.x1 <= page_rect.x1 + 0.01
        and rect.y1 <= page_rect.y1 + 0.01
    )


def _union_bbox(bboxes: tuple[BoundingBox, ...]) -> BoundingBox:
    return (
        min(item[0] for item in bboxes),
        min(item[1] for item in bboxes),
        max(item[2] for item in bboxes),
        max(item[3] for item in bboxes),
    )


def _clean_source_text(value: str) -> str:
    return "".join(
        "" if unicodedata.category(character).startswith("C") else character
        for character in value
    ).strip()


def _positive_finite(value: object, *, label: str) -> float:
    normalized = _nonnegative_finite(value, label=label)
    if normalized <= 0:
        raise PdfFormulaError(f"{label} must be positive.")
    return normalized


def _nonnegative_finite(value: object, *, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PdfFormulaError(f"{label} must be a number.")
    normalized = float(value)
    if not math.isfinite(normalized) or normalized < 0:
        raise PdfFormulaError(f"{label} must be finite and non-negative.")
    return normalized


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(
        character in "0123456789abcdef" for character in value
    )
