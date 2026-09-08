"""ResearchMind-owned mapping from untrusted PDF.js events to project models."""

from __future__ import annotations

from researchmind.models import Page, ReadingSelection
from researchmind.pdf.errors import PdfViewerError
from researchmind.pdf.reader import OpenedDocument, PdfViewerSource

from .boundary import PageTurn, validate_page_turn
from .provenance import VerifiedSelection, build_page_snapshot, verify_selection


def reconcile_selection(
    source: PdfViewerSource,
    document: OpenedDocument,
    event: object,
    *,
    instance: str,
    last_sequence: int,
) -> tuple[ReadingSelection, int]:
    """Return a ReadingSelection only after current-page server reconciliation."""

    try:
        snapshot = build_page_snapshot(
            source.content,
            page=_event_page(event),
            instance=instance,
        )
        if snapshot.revision != source.revision:
            raise ValueError("Trusted PDF revision changed")
        if snapshot.page_count != document.document.num_pages:
            raise ValueError("Trusted PDF page count changed")
        verified = verify_selection(
            event,
            snapshot,
            last_sequence=last_sequence,
        )
        page = document.pages[verified.page - 1]
        return _to_reading_selection(verified, page), verified.sequence
    except (IndexError, ValueError) as exc:
        raise PdfViewerError(str(exc)) from exc


def reconcile_page_turn(
    source: PdfViewerSource,
    event: object,
    *,
    instance: str,
    current_page: int,
    page_count: int,
    last_sequence: int,
) -> PageTurn:
    """Validate a browser wheel request against the current trusted document."""

    try:
        return validate_page_turn(
            event,
            revision=source.revision,
            instance=instance,
            current_page=current_page,
            page_count=page_count,
            last_sequence=last_sequence,
        )
    except ValueError as exc:
        raise PdfViewerError(str(exc)) from exc


def _event_page(event: object) -> int:
    if not isinstance(event, dict):
        raise ValueError("Invalid selection envelope")
    page = event.get("page")
    if type(page) is not int or page < 1:
        raise ValueError("Wrong page")
    return page


def _to_reading_selection(
    verified: VerifiedSelection,
    page: Page,
) -> ReadingSelection:
    trusted_bboxes = tuple(verified.trusted_bboxes)
    locator: dict[str, object] = {
        "page_number": verified.page,
        "bbox": _envelope(trusted_bboxes),
        "bboxes": trusted_bboxes,
        "document_revision": verified.revision,
        "origin": verified.origin,
        "viewer_engine": verified.engine,
        "locator_status": verified.locator_status,
        "client_ranges": verified.client_ranges,
        "geometry_coverage": verified.geometry_coverage,
        "geometry_precision": verified.geometry_precision,
    }
    block_index = _matching_block_index(
        page,
        verified.text,
        selection_bbox=locator["bbox"],
    )
    if block_index is not None:
        locator["block_index"] = block_index
    return ReadingSelection(
        text=verified.text,
        source_type="pdf",
        locator=locator,
    )


def _matching_block_index(
    page: Page,
    text: str,
    *,
    selection_bbox: object,
) -> int | None:
    normalized = _normalized_text(text)
    candidates = [
        block
        for block in page.blocks
        if normalized and normalized in _normalized_text(block.text)
    ]
    if len(candidates) == 1:
        return candidates[0].block_index
    if not candidates or not _is_bbox(selection_bbox):
        return None
    scored = sorted(
        (
            (_intersection_area(selection_bbox, block.bbox), block)
            for block in candidates
            if block.bbox is not None
        ),
        key=lambda item: item[0],
        reverse=True,
    )
    if not scored or scored[0][0] <= 0:
        return None
    if len(scored) > 1 and scored[0][0] == scored[1][0]:
        return None
    return scored[0][1].block_index


def _normalized_text(value: str) -> str:
    return " ".join(value.split()).casefold()


def _is_bbox(value: object) -> bool:
    return isinstance(value, tuple) and len(value) == 4


def _intersection_area(
    first: object,
    second: tuple[float, float, float, float] | None,
) -> float:
    if not _is_bbox(first) or second is None:
        return 0.0
    return max(0.0, min(first[2], second[2]) - max(first[0], second[0])) * max(
        0.0,
        min(first[3], second[3]) - max(first[1], second[1]),
    )


def _envelope(
    boxes: tuple[tuple[float, float, float, float], ...],
) -> tuple[float, float, float, float]:
    if not boxes:
        raise ValueError("Verified selection has no trusted geometry")
    return (
        min(box[0] for box in boxes),
        min(box[1] for box in boxes),
        max(box[2] for box in boxes),
        max(box[3] for box in boxes),
    )
