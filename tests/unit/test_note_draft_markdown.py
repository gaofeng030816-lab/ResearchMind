"""Deterministic G4-D Markdown composition tests."""

from datetime import UTC, datetime

import pytest

from researchmind.integration.obsidian import (
    MarkdownRenderError,
    render_note_draft_markdown,
)
from researchmind.models import EvidenceSnapshot, NoteDraft


def test_draft_markdown_keeps_editable_body_and_traceable_evidence_order() -> None:
    draft = _draft(body_markdown="## 我的结论\n\n需要复现实验。")
    later = _evidence(
        evidence_id="evidence-2",
        kind="translation",
        content="经过翻译的结论。",
        sort_order=1,
        source_label="Fixture Paper · page 2",
    )
    first = _evidence(
        evidence_id="evidence-1",
        kind="source_text",
        content="Claim from the selected paragraph.\nSecond line.",
        sort_order=0,
        source_label="Fixture Paper · page 1",
    )

    markdown = render_note_draft_markdown(
        draft,
        [later, first],
        {first.id: "current", later.id: "stale"},
    )

    assert markdown.startswith("# Durable note\n\n## 我的结论")
    assert markdown.index("### 1. 原文") < markdown.index("### 2. 译文")
    assert "> Claim from the selected paragraph." in markdown
    assert "current（仍匹配当前资料库修订）" in markdown
    assert "stale（来源已有新修订或已移除）" in markdown
    assert '    {"page_number":1}' in markdown
    assert "证据内容 SHA-256" in markdown


def test_draft_markdown_uses_only_explicitly_included_evidence() -> None:
    draft = _draft()
    excluded = _evidence(
        evidence_id="evidence-excluded",
        kind="answer",
        content="Do not export this answer.",
        sort_order=0,
        source_label="Conversation",
        included=False,
    )

    markdown = render_note_draft_markdown(draft, [excluded], {})

    assert "Do not export" not in markdown
    assert "本次预览未纳入证据" in markdown


def test_draft_markdown_rejects_cross_draft_or_missing_source_state() -> None:
    draft = _draft()
    evidence = _evidence(
        evidence_id="evidence-1",
        kind="code",
        content="print('safe')",
        sort_order=0,
        source_label="demo/main.py",
    )

    with pytest.raises(MarkdownRenderError, match="source state"):
        render_note_draft_markdown(draft, [evidence], {})

    other = EvidenceSnapshot(**{**evidence.__dict__, "draft_id": "draft-other"})
    with pytest.raises(MarkdownRenderError, match="different draft"):
        render_note_draft_markdown(draft, [other], {other.id: "detached"})


def _draft(*, body_markdown: str = "") -> NoteDraft:
    created = datetime(2026, 9, 8, 10, 0, tzinfo=UTC)
    return NoteDraft(
        id="draft-1",
        title="Durable note",
        body_markdown=body_markdown,
        status="active",
        revision=1,
        created_at=created,
        updated_at=created,
    )


def _evidence(
    *,
    evidence_id: str,
    kind: str,
    content: str,
    sort_order: int,
    source_label: str,
    included: bool = True,
) -> EvidenceSnapshot:
    return EvidenceSnapshot(
        id=evidence_id,
        draft_id="draft-1",
        kind=kind,  # type: ignore[arg-type]
        content=content,
        source_label=source_label,
        origin="user_entry",
        included=included,
        sort_order=sort_order,
        created_at=datetime(2026, 9, 8, 10, 1, tzinfo=UTC),
        locator={"page_number": 1},
    )
