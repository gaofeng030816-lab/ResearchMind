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

    if note.source_type == "code" or note.code_selection is not None:
        lines = _code_note_lines(note, title=title, source=source)
    else:
        lines = _paper_note_lines(note, title=title, source=source)
        _append_section(lines, "原文", note.selected_text, quote=True)
        _append_section(lines, "翻译", note.translation)
        _append_latex_section(lines, note.latex)

    question = _optional_text(note.question)
    explanation = _optional_text(note.ai_explanation)
    if question is not None or explanation is not None:
        lines.extend(["", "## 问答"])
        if question is not None:
            lines.extend(["", "### 问题", "", question])
        if explanation is not None:
            lines.extend(["", "### AI 解释", "", explanation])

    _append_section(lines, "我的理解", note.user_notes)
    _append_evidence_links(lines, note)

    tags = [tag for tag in (_single_line(item) for item in note.tags) if tag]
    if tags:
        lines.extend(["", "## 标签", ""])
        lines.extend(f"- {tag}" for tag in tags)

    return "\n".join(lines).rstrip() + "\n"


def _paper_note_lines(
    note: KnowledgeNote,
    *,
    title: str,
    source: str,
) -> list[str]:
    authors = ", ".join(
        author for author in (_single_line(item) for item in note.authors) if author
    )
    page = "未定位" if note.page_number is None else str(note.page_number)
    block = "未定位" if note.block_index is None else str(note.block_index)
    bbox = (
        "未定位"
        if note.bbox is None
        else ", ".join(f"{coordinate:.2f}" for coordinate in note.bbox)
    )
    return [
        f"# {title}",
        "",
        "## 来源",
        "",
        f"- 文档：{source}",
        f"- 作者：{authors or '未提供'}",
        f"- 来源类型：{_single_line(note.source_type) or '未提供'}",
        f"- 页码：{page}",
        f"- 文本块：{block}",
        f"- 边界框：{bbox}",
        f"- 创建时间：{note.created_at.isoformat()}",
    ]


def _code_note_lines(
    note: KnowledgeNote,
    *,
    title: str,
    source: str,
) -> list[str]:
    selection = note.code_selection
    if note.source_type != "code" or selection is None:
        raise MarkdownRenderError(
            "Code knowledge note requires a code selection and code source type."
        )
    project_name = _single_line(selection.project_name)
    relative_path = selection.relative_path.replace("\\", "/").strip()
    if (
        not project_name
        or project_name != source
        or not relative_path
        or relative_path.startswith("/")
        or ":" in relative_path.split("/", maxsplit=1)[0]
        or any(part in {"", ".", ".."} for part in relative_path.split("/"))
    ):
        raise MarkdownRenderError("Code selection must use safe relative provenance.")
    if selection.start_line < 1 or selection.end_line < selection.start_line:
        raise MarkdownRenderError("Code selection must use a valid line range.")
    if _optional_text(note.selected_text) != _optional_text(selection.text):
        raise MarkdownRenderError("Code note text must match its code selection.")

    symbol = "显式行范围"
    if selection.symbol_name is not None:
        symbol_labels = {
            "class": "类",
            "function": "函数",
            "method": "方法",
            "import": "导入",
        }
        kind = symbol_labels.get(selection.symbol_kind or "", "符号")
        symbol = f"{kind} {_single_line(selection.symbol_name)}"
    extraction = {
        "ast": "AST 静态提取",
        "text": "显式文本范围",
    }.get(selection.extraction_method)
    if extraction is None:
        raise MarkdownRenderError("Code selection extraction method is unsupported.")

    lines = [
        f"# {title}",
        "",
        "## 来源",
        "",
        f"- 代码项目：{project_name}",
        f"- 相对路径：{relative_path}",
        f"- 行号：{selection.start_line}-{selection.end_line}",
        f"- 代码符号：{symbol}",
        f"- 提取方式：{extraction}",
        "- 来源类型：code",
        f"- 创建时间：{note.created_at.isoformat()}",
    ]
    code = _optional_text(note.selected_text)
    if code is not None:
        lines.extend(["", "## 代码", "", _indented_code_block(code)])
    return lines


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


def _append_latex_section(lines: list[str], value: str | None) -> None:
    latex = _optional_text(value)
    if latex is None:
        return
    expressions = [
        expression.strip()
        for expression in latex.split("\n\n")
        if expression.strip()
    ]
    lines.extend(["", "## LaTeX 公式"])
    for expression in expressions:
        lines.extend(["", "$$", expression, "$$"])


def _append_evidence_links(
    lines: list[str],
    note: KnowledgeNote,
) -> None:
    if not note.evidence_links:
        return
    relation_labels = {
        "implements": "实现",
        "explains": "解释",
        "supports": "支持",
        "contradicts": "矛盾",
        "related": "相关",
    }
    generation_labels = {
        "user_confirmed": "用户确认",
        "deterministic": "确定性提取",
        "model_inference": "模型推断",
    }
    evidence_kind_labels = {
        "paper": "论文内容",
        "mathematics": "数学公式",
        "algorithm": "算法",
    }
    symbol_kind_labels = {
        "class": "类",
        "function": "函数",
        "method": "方法",
        "import": "导入",
    }
    extraction_labels = {
        "ast": "AST 静态提取",
        "text": "显式文本范围",
    }
    lines.extend(["", "## 证据链接"])
    for index, link in enumerate(note.evidence_links, start=1):
        relation = relation_labels[link.relation]
        generation = generation_labels[link.generation_method]
        block = (
            "未定位"
            if link.paper.block_index is None
            else str(link.paper.block_index)
        )
        bbox = (
            "未定位"
            if link.paper.bbox is None
            else ", ".join(
                f"{coordinate:.2f}" for coordinate in link.paper.bbox
            )
        )
        symbol = "未指定"
        if link.code.symbol_name is not None:
            kind = symbol_kind_labels.get(
                link.code.symbol_kind or "",
                link.code.symbol_kind or "符号",
            )
            symbol = f"{kind} {_single_line(link.code.symbol_name)}"
        lines.extend(
            [
                "",
                f"### {index}. {relation} · {generation}",
                "",
                f"- 生成方式：{generation}",
                f"- 置信度：{link.confidence:.2f}",
                "- 论文证据类型："
                f"{evidence_kind_labels[link.paper.evidence_kind]}",
                f"- 论文：{_single_line(link.paper.document_title)}",
                f"- 论文位置：第 {link.paper.page_number} 页 · "
                f"文本块 {block}",
                f"- 论文边界框：{bbox}",
                f"- 代码项目：{_single_line(link.code.project_name)}",
                f"- 代码位置：{_single_line(link.code.relative_path)}:"
                f"{link.code.start_line}-{link.code.end_line}",
                f"- 代码符号：{symbol}",
                "- 代码提取："
                f"{extraction_labels[link.code.extraction_method]}",
                f"- 建立时间：{link.created_at.isoformat()}",
            ]
        )
        if link.rationale:
            lines.append(f"- 说明：{_single_line(link.rationale)}")
        lines.extend(
            [
                "",
                "#### 论文片段",
                "",
                _quote_block(link.paper.excerpt),
                "",
                "#### 代码片段",
                "",
                _indented_code_block(link.code.excerpt),
            ]
        )


def _indented_code_block(text: str) -> str:
    return "\n".join(
        f"    {line}" if line else "    "
        for line in text.splitlines()
    )


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _single_line(value: str) -> str:
    return " ".join(value.split())
