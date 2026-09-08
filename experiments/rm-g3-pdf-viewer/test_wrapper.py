"""Python boundary tests for the isolated packaged component."""

from base64 import b64decode
import importlib.util
from pathlib import Path

import pytest

BOUNDARY_PATH = Path(__file__).parent / "rm_g3_pdf_viewer" / "boundary.py"
SPEC = importlib.util.spec_from_file_location("g3_pdf_boundary", BOUNDARY_PATH)
assert SPEC and SPEC.loader
boundary = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(boundary)


@pytest.fixture
def pdf_bytes():
    return b"%PDF-1.4\nsynthetic-spike"


def test_boundary_builds_bounded_revision_without_path(pdf_bytes):
    payload = boundary.make_payload(
        pdf_bytes,
        page=2,
        page_count=3,
        scale=1.25,
        instance="viewer-a",
    )
    assert b64decode(payload["pdf_base64"]) == pdf_bytes
    assert payload["revision"].startswith("sha256:")
    assert set(payload) == {
        "pdf_base64", "revision", "loaded_revision", "page", "page_count",
        "scale", "instance", "max_selection_chars",
    }
    assert payload["loaded_revision"] == ""


def test_boundary_omits_pdf_after_same_revision_is_loaded(pdf_bytes):
    first = boundary.make_payload(
        pdf_bytes,
        page=1,
        page_count=3,
        scale=1.0,
        instance="viewer-a",
    )
    reused = boundary.make_payload(
        pdf_bytes,
        page=2,
        page_count=3,
        scale=1.0,
        instance="viewer-a",
        loaded_revision=first["revision"],
    )
    assert reused["pdf_base64"] == ""
    assert reused["loaded_revision"] == first["revision"]
    assert reused["revision"] == first["revision"]


@pytest.mark.parametrize("untrusted", [None, 7, object(), "x" * 97])
def test_boundary_falls_back_to_pdf_for_invalid_loaded_revision(
    pdf_bytes,
    untrusted,
):
    payload = boundary.make_payload(
        pdf_bytes,
        page=1,
        page_count=1,
        scale=1.0,
        instance="viewer-a",
        loaded_revision=untrusted,
    )
    assert b64decode(payload["pdf_base64"]) == pdf_bytes
    assert payload["loaded_revision"] == ""


@pytest.mark.parametrize(("content", "page", "page_count", "scale"), [
    (b"not-pdf", 1, 1, 1.0), (b"%PDF-", 0, 1, 1.0),
    (b"%PDF-", True, 1, 1.0), (b"%PDF-", 2, 1, 1.0),
    (b"%PDF-", 1, 0, 1.0), (b"%PDF-", 1, True, 1.0),
    (b"%PDF-", 1, 1, 0.49), (b"%PDF-", 1, 1, 2.51),
    (b"%PDF-", 1, 1, True),
])
def test_wrapper_rejects_invalid_inputs(content, page, page_count, scale):
    with pytest.raises(ValueError):
        boundary.make_payload(
            content,
            page=page,
            page_count=page_count,
            scale=scale,
            instance="viewer-a",
        )


def test_wrapper_rejects_oversize(monkeypatch):
    monkeypatch.setattr(boundary, "MAX_EXPERIMENT_PDF_BYTES", 4)
    with pytest.raises(ValueError):
        boundary.make_payload(
            b"%PDF-x",
            page=1,
            page_count=1,
            scale=1.0,
            instance="viewer-a",
        )


def test_page_turn_is_rechecked_against_trusted_state():
    event = {
        "version": 1,
        "revision": "sha256:fixture",
        "instance": "viewer-a",
        "page": 2,
        "sequence": 4,
        "delta": 1,
        "source": "wheel",
    }
    turn = boundary.validate_page_turn(
        event,
        revision="sha256:fixture",
        instance="viewer-a",
        current_page=2,
        page_count=3,
        last_sequence=3,
    )
    assert turn.target_page == 3
    assert turn.sequence == 4


@pytest.mark.parametrize("change", [
    {"revision": "old"}, {"instance": "viewer-b"}, {"page": 1},
    {"page": True}, {"sequence": 3},
    {"sequence": True}, {"delta": 2}, {"delta": True}, {"source": "key"},
    {"extra": "field"},
])
def test_page_turn_rejects_untrusted_changes(change):
    event = {
        "version": 1,
        "revision": "sha256:fixture",
        "instance": "viewer-a",
        "page": 2,
        "sequence": 4,
        "delta": 1,
        "source": "wheel",
    }
    event.update(change)
    with pytest.raises(ValueError):
        boundary.validate_page_turn(
            event,
            revision="sha256:fixture",
            instance="viewer-a",
            current_page=2,
            page_count=3,
            last_sequence=3,
        )


def test_page_turn_rejects_document_bounds():
    event = {
        "version": 1,
        "revision": "sha256:fixture",
        "instance": "viewer-a",
        "page": 3,
        "sequence": 1,
        "delta": 1,
        "source": "wheel",
    }
    with pytest.raises(ValueError):
        boundary.validate_page_turn(
            event,
            revision="sha256:fixture",
            instance="viewer-a",
            current_page=3,
            page_count=3,
            last_sequence=0,
        )


def test_shortcut_toggle_is_sequence_checked():
    event = {
        "version": 1,
        "sequence": 2,
        "shortcut": "Ctrl+Shift+A",
        "source": "keyboard",
    }
    assert boundary.validate_shortcut_toggle(event, last_sequence=1).sequence == 2
    with pytest.raises(ValueError):
        boundary.validate_shortcut_toggle(event, last_sequence=2)


def test_generated_fixture_is_not_committed_as_component_input():
    assert not (Path(__file__).parent / "rm_g3_pdf_viewer" / "fixture.pdf").exists()
