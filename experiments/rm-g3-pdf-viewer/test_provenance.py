"""Trusted PDF.js-to-PyMuPDF reconciliation tests for the isolated Spike."""

import importlib.util
import json
from pathlib import Path
import sys

import pymupdf
import pytest

MODULE_PATH = Path(__file__).parent / "rm_g3_pdf_viewer" / "provenance.py"
SPEC = importlib.util.spec_from_file_location("g3_pdf_provenance", MODULE_PATH)
assert SPEC and SPEC.loader
provenance = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = provenance
SPEC.loader.exec_module(provenance)


def _pdf_bytes(lines: list[tuple[float, float, str]]) -> bytes:
    document = pymupdf.open()
    try:
        page = document.new_page(width=400, height=300)
        for x, y, text in lines:
            page.insert_text((x, y), text, fontname="helv", fontsize=12)
        return document.tobytes()
    finally:
        document.close()


@pytest.fixture
def snapshot():
    content = _pdf_bytes([(40, 60, "Select this exact sentence."), (40, 100, "Second line.")])
    return provenance.build_page_snapshot(content, page=1, instance="viewer-a")


def _box_for_text(snapshot, text: str, *, occurrence: int = 0) -> list[float]:
    line_groups = {}
    for glyph in snapshot.glyphs:
        line_groups.setdefault((glyph.block_index, glyph.line_index), []).append(glyph)
    matches = []
    for glyphs in line_groups.values():
        line = "".join(glyph.text for glyph in glyphs)
        start = 0
        while True:
            found = line.find(text, start)
            if found < 0:
                break
            selected = glyphs[found:found + len(text)]
            matches.append(selected)
            start = found + 1
    selected = matches[occurrence]
    return [
        min(glyph.normalized_bbox[0] for glyph in selected),
        min(glyph.normalized_bbox[1] for glyph in selected),
        max(glyph.normalized_bbox[2] for glyph in selected),
        max(glyph.normalized_bbox[3] for glyph in selected),
    ]


def _event(snapshot, text: str, box: list[float]) -> dict[str, object]:
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


def test_real_pymupdf_snapshot_verifies_text_and_returns_only_trusted_boxes(snapshot):
    event = _event(snapshot, "Select", _box_for_text(snapshot, "Select"))
    result = provenance.verify_selection(event, snapshot)
    assert result.text == "Select"
    assert result.locator_status == "verified_text_geometry"
    assert result.origin == "pdfjs_text_layer_reconciled_with_pymupdf"
    assert result.trusted_bboxes
    assert result.geometry_coverage == 1.0
    assert result.geometry_precision == 1.0


def test_whitespace_is_normalized_only_after_trusted_text_match(snapshot):
    event = _event(snapshot, "Select   this", _box_for_text(snapshot, "Select this"))
    event["ranges"] = [[0, 0, 6], [1, 0, 4]]
    assert provenance.verify_selection(event, snapshot).text == "Select this"


def test_browser_line_height_inflation_keeps_a_tight_text_match(snapshot):
    trusted = _box_for_text(snapshot, "Select")
    browser_box = [
        max(0.0, trusted[0] - 0.002),
        max(0.0, trusted[1] - 0.004),
        min(1.0, trusted[2] + 0.015),
        min(1.0, trusted[3] + 0.004),
    ]
    result = provenance.verify_selection(_event(snapshot, "Select", browser_box), snapshot)
    assert result.geometry_coverage >= provenance.MIN_GEOMETRY_COVERAGE
    assert result.geometry_precision >= provenance.MIN_GEOMETRY_PRECISION


def test_unique_text_can_use_a_close_overlapping_anchor(snapshot):
    trusted = _box_for_text(snapshot, "Select")
    narrow = [
        trusted[0],
        trusted[1],
        trusted[0] + (trusted[2] - trusted[0]) * 0.35,
        trusted[1] + (trusted[3] - trusted[1]) * 0.75,
    ]
    result = provenance.verify_selection(_event(snapshot, "Select", narrow), snapshot)
    assert result.locator_status == "verified_unique_text_anchor"


def test_repeated_text_cannot_use_the_unique_anchor_fallback():
    content = _pdf_bytes([(40, 60, "repeat"), (260, 180, "repeat")])
    snapshot = provenance.build_page_snapshot(content, page=1, instance="viewer-a")
    trusted = _box_for_text(snapshot, "repeat")
    narrow = [
        trusted[0],
        trusted[1],
        trusted[0] + (trusted[2] - trusted[0]) * 0.35,
        trusted[1] + (trusted[3] - trusted[1]) * 0.75,
    ]
    with pytest.raises(ValueError):
        provenance.verify_selection(_event(snapshot, "repeat", narrow), snapshot)


def test_duplicate_text_is_disambiguated_by_geometry():
    content = _pdf_bytes([(40, 60, "repeat"), (260, 180, "repeat")])
    snapshot = provenance.build_page_snapshot(content, page=1, instance="viewer-a")
    event = _event(snapshot, "repeat", _box_for_text(snapshot, "repeat", occurrence=1))
    result = provenance.verify_selection(event, snapshot)
    assert result.trusted_bboxes[0][0] > 200


def test_multiline_selection_uses_source_order_in_a_two_column_layout():
    content = _pdf_bytes([
        (40, 60, "Left first line."),
        (40, 100, "Left second line."),
        (230, 60, "Right first line."),
    ])
    snapshot = provenance.build_page_snapshot(content, page=1, instance="viewer-a")
    first = _box_for_text(snapshot, "Left first line.")
    second = _box_for_text(snapshot, "Left second line.")
    event = _event(snapshot, "Left first line.\nLeft second", first)
    event["ranges"] = [[0, 0, 16], [1, 0, 11]]
    event["bboxes"] = [first, second]
    result = provenance.verify_selection(event, snapshot)
    assert len(result.client_ranges) == 2
    assert len(result.trusted_bboxes) == 2


@pytest.mark.parametrize("change", [
    {"revision": "sha256:old"},
    {"instance": "viewer-b"},
    {"page": 2},
    {"page": True},
    {"sequence": 0},
    {"sequence": True},
    {"text": "fabricated"},
    {"text": ""},
    {"ranges": []},
    {"ranges": [[0, 2, 1]]},
    {"ranges": [[0, 0, 3], [0, 2, 4]]},
    {"bboxes": []},
    {"bboxes": [[0, 0, 2, 1]]},
    {"bboxes": [[True, 0, 1, 1]]},
    {"viewport": [0, 100]},
    {"engine": "unknown/1.0"},
    {"extra": "field"},
])
def test_untrusted_or_stale_event_is_rejected(snapshot, change):
    event = _event(snapshot, "Select", _box_for_text(snapshot, "Select"))
    event.update(change)
    with pytest.raises(ValueError):
        provenance.verify_selection(event, snapshot)


def test_duplicate_sequence_and_wrong_geometry_are_rejected(snapshot):
    event = _event(snapshot, "Select", _box_for_text(snapshot, "Select"))
    with pytest.raises(ValueError):
        provenance.verify_selection(event, snapshot, last_sequence=1)
    event["bboxes"] = [[0.75, 0.75, 0.90, 0.90]]
    with pytest.raises(ValueError):
        provenance.verify_selection(event, snapshot)


def test_overbroad_geometry_cannot_relabel_one_word(snapshot):
    event = _event(snapshot, "Select", [[0.0, 0.0, 1.0, 1.0]])
    with pytest.raises(ValueError):
        provenance.verify_selection(event, snapshot)


def test_textless_page_cannot_produce_a_verified_selection():
    content = _pdf_bytes([])
    snapshot = provenance.build_page_snapshot(content, page=1, instance="viewer-a")
    event = _event(snapshot, "Select", [0.1, 0.1, 0.2, 0.2])
    with pytest.raises(ValueError):
        provenance.verify_selection(event, snapshot)


def test_corpus_manifest_is_path_free_and_covers_the_g3_matrix():
    manifest = json.loads((Path(__file__).parent / "corpus.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 1
    documents = manifest["documents"]
    assert len(documents) == 5
    categories = {category for item in documents for category in item["categories"]}
    assert {"digital_text", "double_column", "non_english", "formula", "table", "scanned"} <= categories
    assert {item["expected_text_layer"] for item in documents} == {True, False}
    for item in documents:
        assert set(item) == {
            "id", "filename", "sha256", "categories", "sample_page", "expected_text_layer",
        }
        assert len(item["sha256"]) == 64
        assert ":\\" not in item["filename"] and not item["filename"].startswith(("/", "\\"))


def test_recorded_corpus_result_is_path_free_and_distinguishes_locator_statuses():
    result_path = Path(__file__).parent / "current_corpus_results_2026-09-06.json"
    raw = result_path.read_text(encoding="utf-8")
    result = json.loads(raw)
    assert result["status"] == "isolated_spike_evidence"
    assert result["aggregate"]["documents_passed"] == 5
    assert result["aggregate"]["digital_selection_attempts"] == 12
    assert result["aggregate"]["native_copy_matches"] == 12
    assert result["aggregate"]["server_reconciliations"] == 12
    assert result["aggregate"]["verified_text_geometry"] == 10
    assert result["aggregate"]["verified_unique_text_anchor"] == 2
    assert result["aggregate"]["external_requests"] == 0
    assert "D:\\" not in raw and "课程资料" not in raw and '"filename"' not in raw


def test_recorded_performance_result_is_path_free_and_bounded_after_reruns():
    result_path = (
        Path(__file__).parent / "current_performance_results_2026-09-07.json"
    )
    raw = result_path.read_text(encoding="utf-8")
    result = json.loads(raw)
    assert result["status"] == "isolated_spike_evidence"
    assert result["sample"]["page_count"] == 209
    assert result["sample"]["private_path_recorded"] is False
    assert result["sample"]["document_text_recorded"] is False
    assert result["after"]["page_twenty_resource"] == "reused"
    assert result["after"]["page_twenty_payload"] == "omitted"
    assert result["after"]["page_twenty_one_payload"] == "omitted"
    assert result["after"]["page_errors"] == 0
    assert result["after"]["external_requests"] == 0
    assert result["derived"]["after_page_20_to_21_heap_growth_bytes"] < 1024 * 1024
    assert "D:\\" not in raw and "课程资料" not in raw
