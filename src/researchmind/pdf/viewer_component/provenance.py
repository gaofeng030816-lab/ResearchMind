"""Trusted PyMuPDF reconciliation for untrusted PDF.js selection events."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import math
import re

import pymupdf

MAX_PDF_BYTES = 10 * 1024 * 1024
MAX_SELECTION_CHARS = 8000
MAX_SELECTION_RANGES = 128
MAX_SAFE_SEQUENCE = 2**53 - 1
GEOMETRY_TOLERANCE = 0.006
MIN_GEOMETRY_COVERAGE = 0.70
MIN_GEOMETRY_PRECISION = 0.50
MIN_UNIQUE_SCORE_MARGIN = 0.10
UNIQUE_ANCHOR_TOLERANCE = 0.012
MIN_UNIQUE_ANCHOR_COVERAGE = 0.15

Box = tuple[float, float, float, float]


@dataclass(frozen=True)
class TrustedGlyph:
    """One server-extracted character and its page-relative provenance."""

    text: str
    bbox: Box
    normalized_bbox: Box
    block_index: int
    line_index: int
    span_index: int


@dataclass(frozen=True)
class TrustedPageSnapshot:
    """Immutable current-page evidence derived again from the uploaded bytes."""

    revision: str
    instance: str
    page: int
    page_count: int
    width: float
    height: float
    glyphs: tuple[TrustedGlyph, ...]


@dataclass(frozen=True)
class VerifiedSelection:
    """A candidate whose text and location both match trusted page evidence."""

    revision: str
    page: int
    sequence: int
    text: str
    client_ranges: tuple[tuple[int, int, int], ...]
    trusted_bboxes: tuple[Box, ...]
    origin: str
    engine: str
    locator_status: str
    geometry_coverage: float
    geometry_precision: float


def build_page_snapshot(
    pdf_bytes: bytes,
    *,
    page: int,
    instance: str,
) -> TrustedPageSnapshot:
    """Extract bounded character evidence without retaining a vendor handle."""

    if not isinstance(pdf_bytes, bytes) or not pdf_bytes.startswith(b"%PDF-"):
        raise ValueError("A digital PDF byte stream is required")
    if not 0 < len(pdf_bytes) <= MAX_PDF_BYTES:
        raise ValueError("Browser text-layer PDF exceeds the 10 MiB limit")
    if type(page) is not int or page < 1:
        raise ValueError("Page must be a positive integer")
    if not isinstance(instance, str) or not 0 < len(instance) <= 128:
        raise ValueError("Component instance is required")

    try:
        with pymupdf.open(stream=pdf_bytes, filetype="pdf") as document:
            if document.needs_pass:
                raise ValueError("Encrypted PDFs are not supported by the browser viewer")
            if not 1 <= page <= document.page_count:
                raise ValueError("Page exceeds the trusted document bounds")
            source_page = document.load_page(page - 1)
            rect = source_page.rect
            if rect.width <= 0 or rect.height <= 0:
                raise ValueError("Trusted page geometry is invalid")
            # PDF.js selection follows the document's text-content stream. Keep the
            # independent PyMuPDF snapshot in that source order for reconciliation;
            # the formal V2 reading-order parser remains a separate concern.
            raw = source_page.get_text("rawdict", sort=False)
            glyphs = _extract_glyphs(raw, rect)
            page_count = document.page_count
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("PyMuPDF could not build a trusted page snapshot") from exc

    return TrustedPageSnapshot(
        revision="sha256:" + sha256(pdf_bytes).hexdigest(),
        instance=instance,
        page=page,
        page_count=page_count,
        width=float(rect.width),
        height=float(rect.height),
        glyphs=tuple(glyphs),
    )


def verify_selection(
    event: object,
    snapshot: TrustedPageSnapshot,
    *,
    last_sequence: int = 0,
) -> VerifiedSelection:
    """Require current identity, exact normalized text, and unique geometry."""

    keys = {
        "version", "revision", "instance", "page", "sequence", "ranges",
        "text", "bboxes", "viewport", "engine",
    }
    if not isinstance(event, dict) or set(event) != keys:
        raise ValueError("Invalid selection envelope")
    if type(event["version"]) is not int or event["version"] != 1:
        raise ValueError("Unsupported selection version")
    if event["revision"] != snapshot.revision or event["instance"] != snapshot.instance:
        raise ValueError("Stale document or component instance")
    if type(event["page"]) is not int or event["page"] != snapshot.page:
        raise ValueError("Wrong page")
    sequence = event["sequence"]
    if (
        type(last_sequence) is not int
        or last_sequence < 0
        or type(sequence) is not int
        or not last_sequence < sequence <= MAX_SAFE_SEQUENCE
    ):
        raise ValueError("Stale or invalid selection sequence")

    text = event["text"]
    if not isinstance(text, str) or not 0 < len(text) <= MAX_SELECTION_CHARS:
        raise ValueError("Invalid selection text budget")
    normalized_text = _normalize_whitespace(text)
    if not normalized_text:
        raise ValueError("Selection contains only whitespace")
    ranges = _validate_ranges(event["ranges"])
    client_boxes = _validate_boxes(event["bboxes"])
    _validate_viewport(event["viewport"])
    engine = event["engine"]
    if not isinstance(engine, str) or re.fullmatch(r"pdf\.js/\d+\.\d+\.\d+", engine) is None:
        raise ValueError("Unsupported viewer engine")

    page_text, page_mapping = _normalized_page_text(snapshot.glyphs)
    candidates = _find_candidates(page_text, normalized_text)
    if not candidates:
        raise ValueError("Selection text does not match the trusted page")
    qualified: list[tuple[float, float, float, tuple[int, ...], str]] = []
    measured: list[tuple[tuple[float, float, int, int, int, int], tuple[int, ...]]] = []
    for start in candidates:
        mapping = page_mapping[start:start + len(normalized_text)]
        glyph_indices = tuple(dict.fromkeys(index for index in mapping if index is not None))
        if not glyph_indices:
            continue
        score = _geometry_scores(snapshot.glyphs, glyph_indices, client_boxes)
        coverage, precision = score[:2]
        measured.append((score, glyph_indices))
        if coverage >= MIN_GEOMETRY_COVERAGE and precision >= MIN_GEOMETRY_PRECISION:
            qualified.append(
                ((coverage + precision) / 2, coverage, precision, glyph_indices, "verified_text_geometry")
            )
        elif len(candidates) == 1 and _unique_anchor_matches(
            client_boxes,
            tuple(snapshot.glyphs[index].normalized_bbox for index in glyph_indices),
            coverage=coverage,
            precision=precision,
        ):
            qualified.append(
                ((coverage + precision) / 2, coverage, precision, glyph_indices, "verified_unique_text_anchor")
            )
    if not qualified:
        best, best_indices = max(
            measured,
            key=lambda item: item[0][0] + item[0][1],
            default=((0.0, 0.0, 0, 0, 0, 0), ()),
        )
        client_envelope = _envelope(client_boxes)
        trusted_envelope = _envelope(tuple(snapshot.glyphs[index].normalized_bbox for index in best_indices))
        raise ValueError(
            "Selection geometry does not match the trusted page text "
            f"(candidates={len(measured)}, best_coverage={best[0]:.2f}, "
            f"best_precision={best[1]:.2f}, selected_inside={best[2]}/{best[3]}, "
            f"page_inside={best[4]}, unique_centers={best[5]}, "
            f"client_box={_format_box(client_envelope)}, trusted_box={_format_box(trusted_envelope)})"
        )
    qualified.sort(key=lambda item: item[0], reverse=True)
    if len(qualified) > 1 and qualified[0][0] - qualified[1][0] < MIN_UNIQUE_SCORE_MARGIN:
        raise ValueError("Selection location is ambiguous on the trusted page")

    _, coverage, precision, glyph_indices, locator_status = qualified[0]
    trusted_boxes = _line_boxes(snapshot.glyphs, glyph_indices)
    return VerifiedSelection(
        revision=snapshot.revision,
        page=snapshot.page,
        sequence=sequence,
        text=normalized_text,
        client_ranges=ranges,
        trusted_bboxes=trusted_boxes,
        origin="pdfjs_text_layer_reconciled_with_pymupdf",
        engine=engine,
        locator_status=locator_status,
        geometry_coverage=round(coverage, 4),
        geometry_precision=round(precision, 4),
    )


def _extract_glyphs(raw: dict[str, object], page_rect: pymupdf.Rect) -> list[TrustedGlyph]:
    glyphs: list[TrustedGlyph] = []
    for block_index, block in enumerate(raw.get("blocks", [])):
        if not isinstance(block, dict) or int(block.get("type", -1)) != 0:
            continue
        for line_index, line in enumerate(block.get("lines", [])):
            if not isinstance(line, dict):
                continue
            for span_index, span in enumerate(line.get("spans", [])):
                if not isinstance(span, dict):
                    continue
                for character in span.get("chars", []):
                    if not isinstance(character, dict):
                        continue
                    value = character.get("c")
                    raw_bbox = character.get("bbox")
                    if not isinstance(value, str) or not value or not _is_box(raw_bbox):
                        continue
                    bbox = tuple(float(number) for number in raw_bbox)
                    normalized = _normalize_box(bbox, page_rect)
                    if normalized is None:
                        continue
                    for code_point in value:
                        glyphs.append(TrustedGlyph(
                            text=code_point,
                            bbox=bbox,
                            normalized_bbox=normalized,
                            block_index=block_index,
                            line_index=line_index,
                            span_index=span_index,
                        ))
    return glyphs


def _is_box(value: object) -> bool:
    return (
        isinstance(value, (list, tuple))
        and len(value) == 4
        and all(type(number) in (int, float) and math.isfinite(float(number)) for number in value)
    )


def _normalize_box(box: Box, page_rect: pymupdf.Rect) -> Box | None:
    x0 = max(0.0, min(1.0, (box[0] - page_rect.x0) / page_rect.width))
    y0 = max(0.0, min(1.0, (box[1] - page_rect.y0) / page_rect.height))
    x1 = max(0.0, min(1.0, (box[2] - page_rect.x0) / page_rect.width))
    y1 = max(0.0, min(1.0, (box[3] - page_rect.y0) / page_rect.height))
    if x1 <= x0 or y1 <= y0:
        return None
    return (x0, y0, x1, y1)


def _validate_ranges(value: object) -> tuple[tuple[int, int, int], ...]:
    if not isinstance(value, list) or not 0 < len(value) <= MAX_SELECTION_RANGES:
        raise ValueError("Invalid selection range budget")
    checked: list[tuple[int, int, int]] = []
    previous_item, previous_end = -1, 0
    for item in value:
        if not isinstance(item, list) or len(item) != 3 or any(type(number) is not int for number in item):
            raise ValueError("Invalid client range")
        item_index, start, end = item
        if not 0 <= item_index <= 100_000 or not 0 <= start < end <= MAX_SELECTION_CHARS:
            raise ValueError("Invalid client range")
        if item_index < previous_item or (item_index == previous_item and start < previous_end):
            raise ValueError("Unordered or overlapping client ranges")
        checked.append((item_index, start, end))
        previous_item, previous_end = item_index, end
    return tuple(checked)


def _validate_boxes(value: object) -> tuple[Box, ...]:
    if not isinstance(value, list) or not 0 < len(value) <= MAX_SELECTION_RANGES:
        raise ValueError("Invalid selection geometry budget")
    boxes: list[Box] = []
    for item in value:
        if not _is_box(item):
            raise ValueError("Invalid selection box")
        box = tuple(float(number) for number in item)
        if not 0 <= box[0] < box[2] <= 1 or not 0 <= box[1] < box[3] <= 1:
            raise ValueError("Selection box is outside the page")
        boxes.append(box)
    return tuple(boxes)


def _validate_viewport(value: object) -> None:
    if (
        not isinstance(value, list)
        or len(value) != 2
        or any(type(number) not in (int, float) for number in value)
        or any(not math.isfinite(float(number)) or not 1 <= float(number) <= 20_000 for number in value)
    ):
        raise ValueError("Invalid selection viewport")


def _normalize_whitespace(text: str) -> str:
    return " ".join(text.split())


def _normalized_page_text(
    glyphs: tuple[TrustedGlyph, ...],
) -> tuple[str, tuple[int | None, ...]]:
    characters: list[str] = []
    mapping: list[int | None] = []
    previous_line: tuple[int, int] | None = None
    whitespace_pending = False
    for index, glyph in enumerate(glyphs):
        line = (glyph.block_index, glyph.line_index)
        if previous_line is not None and line != previous_line:
            whitespace_pending = True
        previous_line = line
        for code_point in glyph.text:
            if code_point.isspace():
                whitespace_pending = bool(characters)
                continue
            if whitespace_pending and characters:
                characters.append(" ")
                mapping.append(None)
            whitespace_pending = False
            characters.append(code_point)
            mapping.append(index)
    return "".join(characters), tuple(mapping)


def _find_candidates(page_text: str, needle: str) -> tuple[int, ...]:
    positions: list[int] = []
    start = 0
    while len(positions) <= 64:
        found = page_text.find(needle, start)
        if found < 0:
            break
        positions.append(found)
        start = found + 1
    if len(positions) > 64:
        raise ValueError("Selection text is too repetitive to locate safely")
    return tuple(positions)


def _contains(box: Box, point: tuple[float, float]) -> bool:
    return (
        box[0] - GEOMETRY_TOLERANCE <= point[0] <= box[2] + GEOMETRY_TOLERANCE
        and box[1] - GEOMETRY_TOLERANCE <= point[1] <= box[3] + GEOMETRY_TOLERANCE
    )


def _center(box: Box) -> tuple[float, float]:
    return ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)


def _envelope(boxes: tuple[Box, ...]) -> Box:
    if not boxes:
        return (0.0, 0.0, 0.0, 0.0)
    return (
        min(box[0] for box in boxes),
        min(box[1] for box in boxes),
        max(box[2] for box in boxes),
        max(box[3] for box in boxes),
    )


def _format_box(box: Box) -> str:
    return "[" + ",".join(f"{value:.3f}" for value in box) + "]"


def _unique_anchor_matches(
    client_boxes: tuple[Box, ...],
    trusted_boxes: tuple[Box, ...],
    *,
    coverage: float,
    precision: float,
) -> bool:
    client = _envelope(client_boxes)
    trusted = _envelope(trusted_boxes)
    return (
        coverage >= MIN_UNIQUE_ANCHOR_COVERAGE
        and precision >= MIN_GEOMETRY_PRECISION
        and _intersection_area(client, trusted) > 0
        and abs(client[0] - trusted[0]) <= UNIQUE_ANCHOR_TOLERANCE
        and abs(client[1] - trusted[1]) <= UNIQUE_ANCHOR_TOLERANCE
    )


def _geometry_scores(
    glyphs: tuple[TrustedGlyph, ...],
    selected: tuple[int, ...],
    client_boxes: tuple[Box, ...],
) -> tuple[float, float, int, int, int, int]:
    selected_set = set(selected)
    selected_inside = {
        index for index in selected_set
        if any(_contains(box, _center(glyphs[index].normalized_bbox)) for box in client_boxes)
    }
    page_inside = {
        index for index, glyph in enumerate(glyphs)
        if not glyph.text.isspace()
        and any(_contains(box, _center(glyph.normalized_bbox)) for box in client_boxes)
    }
    trusted_boxes = _normalized_line_boxes(glyphs, selected)
    trusted_area = sum(_area(box) for box in trusted_boxes)
    client_area = sum(_area(box) for box in client_boxes)
    covered_area = sum(
        max((_intersection_area(box, client) for client in client_boxes), default=0.0)
        for box in trusted_boxes
    )
    precise_area = sum(
        max((_intersection_area(box, trusted) for trusted in trusted_boxes), default=0.0)
        for box in client_boxes
    )
    coverage = covered_area / trusted_area if trusted_area else 0.0
    precision = precise_area / client_area if client_area else 0.0
    unique_centers = {
        (round(_center(glyphs[index].normalized_bbox)[0], 4),
         round(_center(glyphs[index].normalized_bbox)[1], 4))
        for index in page_inside
    }
    return (
        coverage,
        precision,
        len(selected_inside),
        len(selected_set),
        len(page_inside),
        len(unique_centers),
    )


def _normalized_line_boxes(
    glyphs: tuple[TrustedGlyph, ...],
    selected: tuple[int, ...],
) -> tuple[Box, ...]:
    grouped: dict[tuple[int, int], list[Box]] = {}
    for index in selected:
        glyph = glyphs[index]
        grouped.setdefault((glyph.block_index, glyph.line_index), []).append(glyph.normalized_bbox)
    return tuple(_envelope(tuple(boxes)) for boxes in grouped.values())


def _area(box: Box) -> float:
    return max(0.0, box[2] - box[0]) * max(0.0, box[3] - box[1])


def _intersection_area(first: Box, second: Box) -> float:
    return max(0.0, min(first[2], second[2]) - max(first[0], second[0])) * max(
        0.0,
        min(first[3], second[3]) - max(first[1], second[1]),
    )


def _line_boxes(
    glyphs: tuple[TrustedGlyph, ...],
    selected: tuple[int, ...],
) -> tuple[Box, ...]:
    grouped: dict[tuple[int, int], list[Box]] = {}
    for index in selected:
        glyph = glyphs[index]
        grouped.setdefault((glyph.block_index, glyph.line_index), []).append(glyph.bbox)
    return tuple(
        (
            min(box[0] for box in boxes),
            min(box[1] for box in boxes),
            max(box[2] for box in boxes),
            max(box[3] for box in boxes),
        )
        for boxes in grouped.values()
    )
