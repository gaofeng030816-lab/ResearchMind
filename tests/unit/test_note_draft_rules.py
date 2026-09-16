"""Pure G4-B validation tests for drafts and explicit evidence."""

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from researchmind.core import (
    MAX_DRAFT_MARKDOWN_CHARS,
    serialize_evidence_locator,
    validate_evidence_snapshot,
    validate_note_draft,
)
from researchmind.models import EvidenceSnapshot, NoteDraft


NOW = datetime(2026, 9, 8, 8, 0, tzinfo=UTC)


def _draft(**changes: object) -> NoteDraft:
    draft = NoteDraft(
        id="draft-1",
        title="梯度下降",
        body_markdown="## 我的理解\n",
        status="active",
        revision=1,
        created_at=NOW,
        updated_at=NOW,
        record_id="record-1",
        asset_id="asset-1",
    )
    return replace(draft, **changes)


def _evidence(**changes: object) -> EvidenceSnapshot:
    evidence = EvidenceSnapshot(
        id="evidence-1",
        draft_id="draft-1",
        kind="source_text",
        content="The gradient points uphill.",
        source_label="Paper · page 2",
        origin="browser_selection",
        included=True,
        sort_order=0,
        created_at=NOW,
        locator={
            "page_number": 2,
            "bbox": [10.0, 20.0, 30.0, 40.0],
            "relative_path": "src/main.py",
        },
        source_record_id="record-1",
        source_asset_id="asset-1",
        source_revision=1,
        source_sha256="a" * 64,
        selection_id="selection-1",
    )
    return replace(evidence, **changes)


def test_valid_draft_and_evidence_keep_unicode_and_relative_locator() -> None:
    draft = _draft()
    evidence = _evidence()

    validate_note_draft(draft)
    validate_evidence_snapshot(evidence)

    assert serialize_evidence_locator(evidence.locator) == (
        '{"bbox":[10.0,20.0,30.0,40.0],'
        '"page_number":2,"relative_path":"src/main.py"}'
    )


@pytest.mark.parametrize(
    "draft",
    [
        _draft(title="   "),
        _draft(body_markdown="x" * (MAX_DRAFT_MARKDOWN_CHARS + 1)),
        _draft(asset_id="asset-1", record_id=None),
        _draft(status="deleted"),
        _draft(created_at=datetime(2026, 9, 8, 8, 0)),
    ],
)
def test_invalid_drafts_are_rejected(draft: NoteDraft) -> None:
    with pytest.raises(ValueError):
        validate_note_draft(draft)


@pytest.mark.parametrize(
    "evidence",
    [
        _evidence(content="  "),
        _evidence(locator={"relative_path": "D:/private/paper.pdf"}),
        _evidence(locator={"relative_path": "../paper.pdf"}),
        _evidence(locator={"score": float("nan")}),
        _evidence(source_sha256="NOT-A-HASH"),
        _evidence(source_sha256=None),
        _evidence(source_label="C:/Users/private/paper.pdf"),
        _evidence(included=1),
        _evidence(source_asset_id="asset-1", source_record_id=None),
    ],
)
def test_invalid_evidence_is_rejected(evidence: EvidenceSnapshot) -> None:
    with pytest.raises(ValueError):
        validate_evidence_snapshot(evidence)
