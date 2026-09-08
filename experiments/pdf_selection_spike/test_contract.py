"""Synthetic contract tests only; no browser, PDF, provider or private files."""

import pytest

from contract import PageSnapshot, Span, validate_selection


@pytest.fixture
def snapshot():
    return PageSnapshot("sha256:fixture", "mount-a", 1, (
        Span("A😀积分", (0, 0, 100, 20)),
        Span("second column", (150, 0, 250, 20)),
    ))


@pytest.fixture
def event():
    return dict(version=1, revision="sha256:fixture", instance="mount-a", page=1,
                sequence=1, ranges=[[0, 1, 4]], text="😀积分")


def test_valid_unicode_uses_code_points_and_trusted_boxes(event, snapshot):
    result = validate_selection(event, snapshot)
    assert result.text == "😀积分"
    assert result.span_boxes == ((0, 0, 100, 20),)
    assert result.ranges == ((0, 1, 4),)


def test_multiple_spans_have_explicit_separator(event, snapshot):
    event.update(ranges=[[0, 1, 4], [1, 0, 6]], text="😀积分\nsecond")
    assert validate_selection(event, snapshot).text == event["text"]


@pytest.mark.parametrize("change", [
    {"revision": "old"}, {"instance": "mount-b"}, {"page": 2}, {"page": True},
    {"version": True}, {"version": 2}, {"sequence": True}, {"sequence": 0},
    {"sequence": 2**53}, {"text": "invented"}, {"text": ""}, {"text": "x" * 8001},
    {"ranges": []}, {"ranges": [[0, 0, 1]] * 129}, {"ranges": [[-1, 0, 1]]},
    {"ranges": [[2, 0, 1]]}, {"ranges": [[0, 1, 5]]}, {"ranges": [[0, 2, 1]]},
    {"ranges": [[0, True, 2]]}, {"ranges": [[0, 0]]}, {"ranges": "bad"},
    {"ranges": [[0, 0, 3], [0, 2, 4]]}, {"ranges": [[1, 0, 1], [0, 0, 1]]},
    {"bbox": [0, 0, 1, 1]},
])
def test_reject_untrusted_events(event, snapshot, change):
    event.update(change)
    with pytest.raises(ValueError):
        validate_selection(event, snapshot)


def test_duplicate_rejected_without_mutating_snapshot(event, snapshot):
    first = validate_selection(event, snapshot)
    with pytest.raises(ValueError):
        validate_selection(event, snapshot, last_sequence=first.sequence)
    event["sequence"] = 2
    assert validate_selection(event, snapshot, last_sequence=1).sequence == 2


@pytest.mark.parametrize("event", [None, [], "selection", {}])
def test_bad_envelope(event, snapshot):
    with pytest.raises(ValueError):
        validate_selection(event, snapshot)
