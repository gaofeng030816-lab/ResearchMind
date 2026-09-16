"""Production boundary tests for the adopted CCv2/pdf.js viewer."""

from base64 import b64decode
from pathlib import Path

import pytest

from researchmind.app import use_cases
from researchmind.config import Settings
from researchmind.pdf import PdfViewerError, load_pdf_viewer_source, open_pdf
from researchmind.pdf.viewer_component import boundary
from researchmind.pdf.viewer_component.provenance import build_page_snapshot


def _client_box_for_text(snapshot, text: str) -> list[float]:
    glyphs = list(snapshot.glyphs)
    page_text = "".join(glyph.text for glyph in glyphs)
    start = page_text.index(text)
    selected = glyphs[start:start + len(text)]
    return [
        max(0.0, min(glyph.normalized_bbox[0] for glyph in selected) - 0.001),
        max(0.0, min(glyph.normalized_bbox[1] for glyph in selected) - 0.002),
        min(1.0, max(glyph.normalized_bbox[2] for glyph in selected) + 0.003),
        min(1.0, max(glyph.normalized_bbox[3] for glyph in selected) + 0.002),
    ]


def _selection_event(snapshot, text: str, box: list[float]) -> dict[str, object]:
    return {
        "version": 1,
        "revision": snapshot.revision,
        "instance": snapshot.instance,
        "page": snapshot.page,
        "sequence": 1,
        "ranges": [[0, 0, len(text)]],
        "text": text,
        "bboxes": [box],
        "viewport": [500, 375],
        "engine": "pdf.js/6.3.289",
    }


def test_payload_is_revision_bound_and_omits_repeated_pdf_bytes() -> None:
    content = b"%PDF-1.4\nformal-viewer"
    first = boundary.make_payload(
        content,
        page=1,
        page_count=2,
        scale=1.25,
        instance="viewer-a",
    )
    repeated = boundary.make_payload(
        content,
        page=2,
        page_count=2,
        scale=1.25,
        instance="viewer-a",
        loaded_revision=first["revision"],
    )

    assert b64decode(first["pdf_base64"]) == content
    assert repeated["pdf_base64"] == ""
    assert repeated["revision"] == first["revision"]


def test_viewer_source_revalidates_hash_and_size(single_page_pdf: Path) -> None:
    opened = open_pdf(single_page_pdf)
    source = load_pdf_viewer_source(
        single_page_pdf,
        expected_sha256=opened.content_sha256,
        max_size_bytes=opened.max_size_bytes,
    )

    assert source.content.startswith(b"%PDF-")
    assert source.revision == f"sha256:{opened.content_sha256}"

    with pytest.raises(PdfViewerError, match="revision is invalid"):
        load_pdf_viewer_source(
            single_page_pdf,
            expected_sha256="not-a-sha256",
            max_size_bytes=opened.max_size_bytes,
        )
    with pytest.raises(PdfViewerError, match="supports PDFs up to 0 MiB"):
        load_pdf_viewer_source(
            single_page_pdf,
            expected_sha256=opened.content_sha256,
            max_size_bytes=opened.max_size_bytes,
            viewer_max_size_bytes=4,
        )


def test_viewer_source_rejects_content_changed_after_open(
    single_page_pdf: Path,
) -> None:
    opened = open_pdf(single_page_pdf)
    single_page_pdf.write_bytes(single_page_pdf.read_bytes() + b"\nchanged")

    with pytest.raises(PdfViewerError, match="changed after it was opened"):
        load_pdf_viewer_source(
            single_page_pdf,
            expected_sha256=opened.content_sha256,
            max_size_bytes=opened.max_size_bytes,
        )


def test_selection_maps_only_server_reconciled_text_and_geometry(
    single_page_pdf: Path,
    tmp_path: Path,
) -> None:
    opened = open_pdf(single_page_pdf)
    source = load_pdf_viewer_source(
        single_page_pdf,
        expected_sha256=opened.content_sha256,
        max_size_bytes=opened.max_size_bytes,
    )
    snapshot = build_page_snapshot(source.content, page=1, instance="viewer-a")
    client_box = _client_box_for_text(snapshot, "ResearchMind")
    selection, sequence = use_cases.create_pdf_text_layer_selection(
        source,
        opened,
        _selection_event(snapshot, "ResearchMind", client_box),
        instance="viewer-a",
        last_sequence=0,
    )

    assert sequence == 1
    assert selection.text == "ResearchMind"
    assert selection.source_type == "pdf"
    assert selection.locator is not None
    assert selection.locator["page_number"] == 1
    assert selection.locator["origin"] == (
        "pdfjs_text_layer_reconciled_with_pymupdf"
    )
    assert selection.locator["viewer_engine"] == "pdf.js/6.3.289"
    assert selection.locator["locator_status"] == "verified_text_geometry"
    assert selection.locator["bbox"] != tuple(client_box)

    settings = Settings(researchmind_data_dir=tmp_path / "library")
    draft = use_cases.create_paper_note_draft(opened, settings=settings)
    _draft, evidence = use_cases.capture_reading_selection_evidence(
        draft,
        selection,
        opened,
        settings=settings,
    )
    assert evidence.origin == "browser_selection"
    assert evidence.locator["document_revision"] == source.revision
    assert evidence.locator["viewer_engine"] == "pdf.js/6.3.289"
    assert evidence.locator["bboxes"]
    assert evidence.locator["client_ranges"] == [[0, 0, len("ResearchMind")]]
    assert use_cases.note_evidence_source_state(
        evidence,
        settings=settings,
    ) == "detached"


@pytest.mark.parametrize(
    "change",
    [
        {"revision": "sha256:stale"},
        {"instance": "viewer-b"},
        {"page": 2},
        {"sequence": 0},
        {"text": "fabricated"},
        {"engine": "other/1.0"},
        {"extra": "field"},
    ],
)
def test_selection_rejects_stale_or_fabricated_component_events(
    single_page_pdf: Path,
    change: dict[str, object],
) -> None:
    opened = open_pdf(single_page_pdf)
    source = load_pdf_viewer_source(
        single_page_pdf,
        expected_sha256=opened.content_sha256,
        max_size_bytes=opened.max_size_bytes,
    )
    snapshot = build_page_snapshot(source.content, page=1, instance="viewer-a")
    event = _selection_event(
        snapshot,
        "ResearchMind",
        _client_box_for_text(snapshot, "ResearchMind"),
    )
    event.update(change)

    with pytest.raises(PdfViewerError):
        use_cases.create_pdf_text_layer_selection(
            source,
            opened,
            event,
            instance="viewer-a",
            last_sequence=0,
        )


def test_wheel_and_shortcut_events_are_bounded_and_sequence_checked() -> None:
    event = {
        "version": 1,
        "revision": "sha256:fixture",
        "instance": "viewer-a",
        "page": 1,
        "sequence": 2,
        "delta": 1,
        "source": "wheel",
    }
    turn = boundary.validate_page_turn(
        event,
        revision="sha256:fixture",
        instance="viewer-a",
        current_page=1,
        page_count=2,
        last_sequence=1,
    )
    assert turn.target_page == 2

    shortcut = {
        "version": 1,
        "sequence": 3,
        "shortcut": "Ctrl+Shift+A",
        "source": "keyboard",
    }
    assert use_cases.validate_ai_panel_shortcut(shortcut, last_sequence=2) == 3
    with pytest.raises(PdfViewerError):
        use_cases.validate_ai_panel_shortcut(shortcut, last_sequence=3)
