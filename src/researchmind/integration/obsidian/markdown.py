"""Render traceable KnowledgeNote values as readable Markdown."""

from __future__ import annotations

from researchmind.integration.obsidian.errors import MarkdownRenderError
from researchmind.models import KnowledgeNote


def render_markdown(note: KnowledgeNote) -> str:
    """Render one knowledge note without performing file-system I/O."""

    title = _single_line(note.title)
    source = _single_line(note.source)
    if not title:
        raise MarkdownRenderError("Knowledge note title must not be blank.")
    if not source:
        raise MarkdownRenderError("Knowledge note source must not be blank.")

    authors = ", ".join(
        author for author in (_single_line(item) for item in note.authors) if author
    )
    page = "未定位" if note.page_number is None else str(note.page_number)
    lines = [
        f"# {title}",
        "",
        "## 来源",
        "",
        f"- 文档：{source}",
        f"- 作者：{authors or '未提供'}",
        f"- 页码：{page}",
        f"- 创建时间：{note.created_at.isoformat()}",
    ]

    _append_section(lines, "原文", note.selected_text, quote=True)
    _append_section(lines, "翻译", note.translation)

    question = _optional_text(note.question)
    explanation = _optional_text(note.ai_explanation)
    if question is not None or explanation is not None:
        lines.extend(["", "## 问答"])
        if question is not None:
            lines.extend(["", "### 问题", "", question])
        if explanation is not None:
            lines.extend(["", "### AI 解释", "", explanation])

    _append_section(lines, "我的理解", note.user_notes)

    tags = [tag for tag in (_single_line(item) for item in note.tags) if tag]
    if tags:
        lines.extend(["", "## 标签", ""])
        lines.extend(f"- {tag}" for tag in tags)

    return "\n".join(lines).rstrip() + "\n"


def _append_section(
    lines: list[str],
    heading: str,
    value: str | None,
    *,
    quote: bool = False,
) -> None:
    content = _optional_text(value)
    if content is None:
        return
    if quote:
        content = _quote_block(content)
    lines.extend(["", f"## {heading}", "", content])


def _quote_block(text: str) -> str:
    return "\n".join(f"> {line}" if line else ">" for line in text.splitlines())


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _single_line(value: str) -> str:
    return " ".join(value.split())
