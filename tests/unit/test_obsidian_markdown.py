"""Tests for traceable KnowledgeNote Markdown rendering."""

from datetime import UTC, datetime

import pytest

from researchmind.integration.obsidian import MarkdownRenderError, render_markdown
from researchmind.models import KnowledgeNote


def test_render_markdown_contains_traceability_and_all_optional_sections() -> None:
    note = KnowledgeNote(
        title="Inertial parameter",
        source="Optimization Paper",
        authors=["Ada Researcher", "Grace Scientist"],
        page_number=7,
        selected_text="First source line\nSecond source line",
        translation="惯性参数",
        question="Why is it introduced?",
        ai_explanation="It stabilizes the update.",
        user_notes="Compare this with momentum.",
        tags=["optimization", "algorithm"],
        created_at=datetime(2026, 8, 27, 9, 30, tzinfo=UTC),
    )

    markdown = render_markdown(note)

    assert markdown.startswith("# Inertial parameter\n")
    assert "- 文档：Optimization Paper" in markdown
    assert "- 作者：Ada Researcher, Grace Scientist" in markdown
    assert "- 页码：7" in markdown
    assert "- 创建时间：2026-08-27T09:30:00+00:00" in markdown
    assert "> First source line\n> Second source line" in markdown
    assert "## 翻译\n\n惯性参数" in markdown
    assert "### 问题\n\nWhy is it introduced?" in markdown
    assert "### AI 解释\n\nIt stabilizes the update." in markdown
    assert "## 我的理解\n\nCompare this with momentum." in markdown
    assert "- optimization" in markdown
    assert markdown.endswith("\n")
    assert "\x00" not in markdown


def test_render_markdown_omits_empty_optional_sections() -> None:
    markdown = render_markdown(
        KnowledgeNote(title="Document note", source="Paper", authors=[])
    )

    assert "- 作者：未提供" in markdown
    assert "- 页码：未定位" in markdown
    assert "## 原文" not in markdown
    assert "## 翻译" not in markdown
    assert "## 问答" not in markdown
    assert "## 我的理解" not in markdown
    assert "## 标签" not in markdown


@pytest.mark.parametrize(
    ("title", "source", "message"),
    ((" ", "Paper", "title"), ("Title", " ", "source")),
)
def test_render_markdown_requires_title_and_source(
    title: str,
    source: str,
    message: str,
) -> None:
    with pytest.raises(MarkdownRenderError, match=message):
        render_markdown(KnowledgeNote(title=title, source=source))
