"""Tests for traceable KnowledgeNote Markdown rendering."""

from datetime import UTC, datetime

import pytest

from researchmind.integration.obsidian import MarkdownRenderError, render_markdown
from researchmind.models import (
    CodeEvidenceReference,
    CodeSelection,
    EvidenceLink,
    KnowledgeNote,
    PaperEvidenceReference,
)


def test_render_markdown_contains_traceability_and_all_optional_sections() -> None:
    note = KnowledgeNote(
        title="Inertial parameter",
        source="Optimization Paper",
        authors=["Ada Researcher", "Grace Scientist"],
        page_number=7,
        source_type="pdf",
        block_index=12,
        bbox=(10.0, 20.0, 30.0, 40.0),
        selected_text="First source line\nSecond source line",
        translation="惯性参数",
        latex=r"x_{k+1}=x_k+\alpha d_k",
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
    assert "- 来源类型：pdf" in markdown
    assert "- 文本块：12" in markdown
    assert "- 边界框：10.00, 20.00, 30.00, 40.00" in markdown
    assert "- 创建时间：2026-08-27T09:30:00+00:00" in markdown
    assert "> First source line\n> Second source line" in markdown
    assert "## 翻译\n\n惯性参数" in markdown
    assert "## LaTeX 公式\n\n$$\nx_{k+1}=x_k+\\alpha d_k\n$$" in markdown
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
    assert "- 文本块：未定位" in markdown
    assert "- 边界框：未定位" in markdown
    assert "## 原文" not in markdown
    assert "## 翻译" not in markdown
    assert "## LaTeX 公式" not in markdown
    assert "## 问答" not in markdown
    assert "## 我的理解" not in markdown
    assert "## 标签" not in markdown


def test_render_markdown_uses_separate_blocks_for_multiple_latex_results() -> None:
    markdown = render_markdown(
        KnowledgeNote(
            title="Formula note",
            source="Paper",
            latex="x = y\n\ny = z",
        )
    )

    assert "## LaTeX 公式\n\n$$\nx = y\n$$\n\n$$\ny = z\n$$" in markdown


def test_render_markdown_exports_traceable_evidence_links() -> None:
    link = EvidenceLink(
        paper=PaperEvidenceReference(
            document_id="paper-1",
            document_title="Optimization Paper",
            evidence_kind="mathematics",
            page_number=4,
            block_index=7,
            bbox=(10.0, 20.0, 200.0, 45.0),
            excerpt="The update follows Equation 3.",
        ),
        code=CodeEvidenceReference(
            project_id="project-1",
            project_name="optimizer",
            relative_path="solver.py",
            start_line=10,
            end_line=12,
            excerpt="def step(x):\n    return x + 1",
            extraction_method="ast",
            symbol_kind="function",
            symbol_name="step",
        ),
        relation="implements",
        confidence=0.85,
        generation_method="user_confirmed",
        rationale="The variable names and update order match.",
        created_at=datetime(2026, 8, 29, 8, 0, tzinfo=UTC),
    )

    markdown = render_markdown(
        KnowledgeNote(
            title="Equation implementation",
            source="Optimization Paper",
            evidence_links=[link],
        )
    )

    assert "## 证据链接" in markdown
    assert "### 1. 实现 · 用户确认" in markdown
    assert "- 置信度：0.85" in markdown
    assert "- 论文证据类型：数学公式" in markdown
    assert "- 论文：Optimization Paper" in markdown
    assert "- 论文位置：第 4 页 · 文本块 7" in markdown
    assert "- 代码项目：optimizer" in markdown
    assert "- 代码位置：solver.py:10-12" in markdown
    assert "- 代码符号：函数 step" in markdown
    assert "- 代码提取：AST 静态提取" in markdown
    assert "- 说明：The variable names and update order match." in markdown
    assert "> The update follows Equation 3." in markdown
    assert "    def step(x):\n        return x + 1" in markdown


def test_render_code_note_uses_relative_locator_and_indented_python() -> None:
    selection = CodeSelection(
        project_id="project-1",
        project_name="optimizer",
        relative_path="src/solver.py",
        start_line=10,
        end_line=11,
        text="def step(x):\n    return x + 1",
        extraction_method="ast",
        symbol_kind="function",
        symbol_name="step",
    )
    note = KnowledgeNote(
        title="Solver step",
        source="optimizer",
        source_type="code",
        selected_text=selection.text,
        question="What does this do?",
        ai_explanation="It performs one update.",
        user_notes="Use this in the training loop.",
        code_selection=selection,
        created_at=datetime(2026, 8, 31, 9, 30, tzinfo=UTC),
    )

    markdown = render_markdown(note)

    assert "- 代码项目：optimizer" in markdown
    assert "- 相对路径：src/solver.py" in markdown
    assert "- 行号：10-11" in markdown
    assert "- 代码符号：函数 step" in markdown
    assert "- 提取方式：AST 静态提取" in markdown
    assert "## 代码\n\n    def step(x):\n        return x + 1" in markdown
    assert "## 原文" not in markdown
    assert "- 文档：" not in markdown
    assert "- 页码：" not in markdown
    assert "D:\\" not in markdown


def test_render_code_note_requires_code_selection() -> None:
    with pytest.raises(MarkdownRenderError, match="code selection"):
        render_markdown(
            KnowledgeNote(
                title="Invalid code note",
                source="project",
                source_type="code",
            )
        )


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
