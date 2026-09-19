"""Streamlit code workspace with read-only analysis and narrow T5-B1 writes."""

from pathlib import Path

import streamlit as st

from researchmind.app import state, use_cases
from researchmind.models import (
    CodeFile,
    CodeProject,
    CodeProjectSummary,
    CodeSelection,
    Message,
)


_SOURCE_PREVIEW_CHARACTER_LIMIT = 40_000
_CODE_QUESTIONS = {
    "beginner": (
        "请把这段代码当作我第一次学习编程来解释：先用一句话说明用途，"
        "再按执行顺序解释变量、函数和关键语法，最后给出一个简单输入示例。"
        "遇到专业术语时先用通俗语言定义，不要假设我已经知道。"
    ),
    "reproduction": (
        "请从科研代码复现角度解释这段代码：说明输入、输出、关键参数、"
        "配置或依赖假设、随机性/设备/路径风险，以及它可能位于实验流程的哪一步。"
        "只根据当前代码证据回答，并明确尚不能确认的信息。"
    ),
}
_GOAL_LABELS = {
    "beginner": "零基础学习",
    "reproduction": "科研复现",
}
_SYMBOL_KIND_LABELS = {
    "class": "类",
    "function": "函数",
    "type": "类型",
    "method": "方法",
    "import": "导入",
}
_LANGUAGE_LABELS = {
    "python": "Python",
    "c": "C",
    "java": "Java",
    "julia": "Julia",
    "r": "R",
}
_EVIDENCE_KIND_LABELS = {
    "paper": "论文内容",
    "mathematics": "数学公式",
    "algorithm": "算法",
}
_RELATION_LABELS = {
    "implements": "代码实现论文内容",
    "explains": "代码解释论文内容",
    "supports": "代码支持论文证据",
    "contradicts": "代码与论文证据矛盾",
    "related": "代码与论文内容相关",
}
_GENERATION_METHOD_LABELS = {
    "user_confirmed": "用户确认",
    "deterministic": "确定性提取",
    "model_inference": "模型推断",
}


def render_code_workspace() -> None:
    """Render one bounded, non-executing static-code workflow."""

    st.subheader("代码学习与科研复现")
    st.caption(
        "这是独立代码工作区，不需要先打开 PDF。可只读分析 Python、C、Java、"
        "Julia 与 R；应用不会 import、执行、测试、安装依赖、调用编译器或 Shell。"
        "T5-B1 原地修改权限仍严格限于外部 Python 项目。"
    )
    goal = st.radio(
        "本次目标",
        options=list(_GOAL_LABELS),
        format_func=lambda value: _GOAL_LABELS[value],
        horizontal=True,
        key="code_workspace_goal",
    )
    _render_goal_intro(goal)
    path_text = st.text_input(
        "本地代码文件夹",
        key="code_project_path_input",
        placeholder="D:/projects/example",
    )
    if st.button(
        "打开代码文件夹",
        key="open_code_project_button",
        type="primary",
    ):
        try:
            project = use_cases.open_code_project(Path(path_text.strip()))
            state.set_opened_code_project(project)
            st.success(
                f"已只读索引：{project.name} · "
                f"{len(project.files)} 个源码文件"
            )
        except use_cases.USER_FACING_ERRORS as exc:
            st.error(str(exc))

    project = state.get_opened_code_project()
    if project is None:
        st.info("输入本地文件夹路径后，可选择源码文件、静态符号或行范围。")
        return

    st.markdown(
        f"**{project.name}** · {len(project.files):,} 个候选文件 · "
        f"{project.total_source_bytes:,} bytes"
    )
    if project.managed_by_researchmind:
        st.info(
            "当前打开的是 ResearchMind 托管修订副本：可静态阅读、解释和写笔记，"
            "但不能用 T5-B1 原地修改。修改后的目录请作为新修订重新导入。"
        )
    _render_project_summary(
        use_cases.get_code_project_summary(project),
        goal=goal,
    )
    available_files = [
        code_file
        for code_file in project.files
        if code_file.status != "unreadable" and code_file.line_count > 0
    ]
    unreadable_files = [
        code_file
        for code_file in project.files
        if code_file.status == "unreadable"
    ]
    empty_files = [
        code_file
        for code_file in project.files
        if code_file.status != "unreadable" and code_file.line_count == 0
    ]
    if unreadable_files:
        st.warning(
            f"{len(unreadable_files)} 个文件不是有效 UTF-8，未读取其源码。"
        )
    if empty_files:
        st.caption(f"{len(empty_files)} 个空源码文件没有可选择内容。")
    if not available_files:
        st.warning("当前文件夹没有可选择的 UTF-8 支持源码。")
        return

    relative_path = st.selectbox(
        "源码文件",
        options=[item.relative_path for item in available_files],
        key=f"code_file_select_{project.id}",
    )
    code_file = use_cases.get_code_file(project, relative_path)
    _render_file_status(code_file)
    _render_source_preview(code_file)
    _render_code_change_receipt(project)

    selection_mode = _selection_mode(code_file, project.id)
    symbol_index = 0
    start_line = 1
    end_line = max(1, code_file.line_count)
    if selection_mode == "symbol":
        symbol_index = st.selectbox(
            "代码符号",
            options=list(range(len(code_file.symbols))),
            format_func=lambda index: _symbol_label(
                code_file,
                index,
            ),
            key=f"code_symbol_select_{project.id}_{relative_path}",
        )
    else:
        start_column, end_column = st.columns(2)
        with start_column:
            start_line = int(
                st.number_input(
                    "起始行",
                    min_value=1,
                    max_value=max(1, code_file.line_count),
                    value=1,
                    step=1,
                    key=f"code_start_line_{project.id}_{relative_path}",
                )
            )
        with end_column:
            end_line = int(
                st.number_input(
                    "结束行",
                    min_value=1,
                    max_value=max(1, code_file.line_count),
                    value=max(1, code_file.line_count),
                    step=1,
                    key=f"code_end_line_{project.id}_{relative_path}",
                )
            )

    if st.button("选择代码", key="select_code_button"):
        try:
            if selection_mode == "symbol":
                selection = use_cases.create_code_symbol_selection(
                    project,
                    relative_path,
                    symbol_index=symbol_index,
                )
            else:
                selection = use_cases.create_code_line_selection(
                    project,
                    relative_path,
                    start_line=start_line,
                    end_line=end_line,
                )
            state.set_current_code_selection(selection)
            st.success(
                f"已选择 {selection.relative_path}:"
                f"{selection.start_line}-{selection.end_line}"
            )
        except use_cases.USER_FACING_ERRORS as exc:
            st.error(str(exc))

    selection = state.get_current_code_selection()
    if (
        selection is None
        or selection.project_id != project.id
        or selection.relative_path != relative_path
    ):
        _render_evidence_links()
        return

    st.markdown("**当前代码选择**")
    st.caption(
        f"{selection.relative_path}:{selection.start_line}-"
        f"{selection.end_line} · {_LANGUAGE_LABELS[selection.language]} · "
        f"{selection.extraction_method}"
    )
    st.code(selection.text, language=selection.language, line_numbers=True)
    with st.expander("可选：连接论文证据", expanded=False):
        _render_evidence_link_creator(project, selection)
    _render_evidence_links()
    question = st.text_area(
        "代码解释问题",
        value=_CODE_QUESTIONS[goal],
        key=f"code_question_input_{selection.id}_{goal}",
        height=150,
    )

    try:
        preview = use_cases.preview_code_context(
            project,
            selection,
            question=question,
        )
        _render_code_evidence(preview)
    except use_cases.USER_FACING_ERRORS as exc:
        st.error(str(exc))

    st.caption(
        "只有点击下方按钮时，选中代码、最小邻近代码、相对路径、行号和问题"
        "才会发送到配置的 LLM；绝对项目路径和整个仓库不会发送。"
    )
    if st.button("AI 解释代码", key="explain_code_button"):
        try:
            response = use_cases.explain_code_selection(
                project,
                selection,
                question=question,
            )
            state.set_current_code_response(response, question=question)
            st.success("代码解释已返回；应用没有执行或修改源码。")
        except use_cases.USER_FACING_ERRORS as exc:
            st.error(str(exc))

    response = state.get_current_code_response()
    response_question = state.get_current_code_response_question()
    if (
        response is not None
        and response.selection_id in {None, selection.id}
        and response_question == question.strip()
    ):
        st.markdown("**AI 代码解释**")
        st.markdown(response.content)
    _render_code_note_controls(
        project,
        selection,
        question=question,
        response=response,
        response_question=response_question,
    )
    _render_code_change_controls(project, selection)


def _render_code_note_controls(
    project: CodeProject,
    selection: CodeSelection,
    *,
    question: str,
    response: Message | None,
    response_question: str | None,
) -> None:
    with st.expander("可选：保存为 Obsidian 代码笔记", expanded=False):
        st.caption(
            "笔记只包含当前选择、相对路径、行号、符号、当前问题、"
            "可用的 AI 解释和你的理解；不会包含绝对项目路径，也不会修改源码。"
        )
        symbol_or_location = selection.symbol_name or (
            f"{selection.relative_path}:"
            f"{selection.start_line}-{selection.end_line}"
        )
        title = st.text_input(
            "代码笔记标题",
            value=f"{project.name} · {symbol_or_location}",
            key=f"code_note_title_{selection.id}",
        )
        user_notes = st.text_area(
            "我的理解（可选）",
            key=f"code_note_user_notes_{selection.id}",
            height=120,
            placeholder="例如：这个函数在实验流程中负责准备模型输入。",
        )
        tags_text = st.text_input(
            "代码笔记标签（逗号分隔，可选）",
            key=f"code_note_tags_{selection.id}",
            placeholder="reproduction, preprocessing",
        )
        current_response = (
            response
            if response is not None
            and response.selection_id == selection.id
            and response_question == question.strip()
            else None
        )
        if response is not None and current_response is None:
            st.warning("当前 AI 解释没有绑定到这次代码选择，因此不会写入笔记。")
        if st.button("生成代码笔记预览", key="preview_code_note_button"):
            try:
                note = use_cases.capture_code_knowledge(
                    project,
                    selection,
                    current_response,
                    question=question,
                    response_question=response_question,
                    user_notes=user_notes,
                    tags=tags_text.split(","),
                    title=title,
                )
                state.set_current_code_note(note)
            except use_cases.USER_FACING_ERRORS as exc:
                st.error(str(exc))

        note = state.get_current_code_note()
        if (
            note is None
            or note.code_selection is None
            or note.code_selection.id != selection.id
        ):
            return
        try:
            markdown = use_cases.preview_note_markdown(note)
        except use_cases.USER_FACING_ERRORS as exc:
            st.error(str(exc))
            return
        st.code(markdown, language="markdown", line_numbers=False)
        if st.button("保存代码笔记到 Obsidian Vault", key="save_code_note_button"):
            try:
                saved_path = use_cases.save_note_to_vault(note)
                state.set_last_code_note_saved_path(saved_path)
                st.success("代码笔记已保存到配置的 Obsidian Vault。")
            except use_cases.USER_FACING_ERRORS as exc:
                st.error(str(exc))
        saved_path = state.get_last_code_note_saved_path()
        if saved_path is not None:
            st.caption(f"最近保存位置：{saved_path}")


def _render_goal_intro(goal: str) -> None:
    if goal == "beginner":
        st.markdown("**从这里开始**")
        st.markdown(
            "1. 选择一个代码文件夹；2. 先看项目概览；3. 选择函数、类或少量行；"
            "4. 检查发送内容；5. 再请求 AI 用通俗语言解释。"
        )
        st.caption(
            "不认识“函数、类、导入”等词也没关系，符号列表会标出类型和行号。"
        )
        return
    st.markdown("**静态复现检查（尚未运行代码）**")
    st.markdown(
        "先确认入口候选、依赖候选和问题文件，再选择训练、评估或数据处理代码。"
        "这里提供复现线索，不代表项目已经成功运行。"
    )


def _render_project_summary(
    summary: CodeProjectSummary,
    *,
    goal: str,
) -> None:
    st.markdown("**静态项目概览**")
    columns = st.columns(4)
    columns[0].metric("源码文件", summary.total_files)
    columns[1].metric("可解析文件", summary.parsed_files)
    columns[2].metric("定义数量", summary.definition_count)
    columns[3].metric("导入数量", summary.import_count)
    st.caption(
        f"共 {summary.total_lines:,} 行 · 语法错误 "
        f"{summary.syntax_error_files} · 不可读 {summary.unreadable_files}"
    )
    st.text(f"语言：{'、'.join(_LANGUAGE_LABELS[item] for item in summary.languages)}")
    if goal == "beginner":
        entry_points = "、".join(summary.entry_point_candidates) or "尚未识别"
        st.text(f"建议先看的入口文件：{entry_points}")
        return

    entry_points = "、".join(summary.entry_point_candidates) or "未识别"
    imports = "、".join(summary.imported_modules) or "未识别"
    external = (
        "、".join(summary.external_dependency_candidates)
        or "未识别到明显第三方候选"
    )
    problems = "、".join(summary.problem_files) or "无"
    st.text(f"入口候选：{entry_points}")
    st.text(f"全部导入模块：{imports}")
    st.text(f"第三方依赖候选：{external}")
    st.text(f"需要人工处理的文件：{problems}")
    st.caption(
        "依赖候选来自静态 import 名称，不等同于 requirements，也未检查版本、"
        "数据集、模型权重、GPU、随机种子或运行命令。"
    )


def _render_evidence_link_creator(
    project: CodeProject,
    code_selection: CodeSelection,
) -> None:
    document = state.get_opened_document()
    reading_selection = state.get_current_selection()
    st.markdown("**建立论文 ↔ 代码证据链接**")
    st.caption(
        "链接只记录来源与用户判断，不会合并 ResearchContext 和 "
        "CodeContext，也不会触发模型调用。"
    )
    if document is None or reading_selection is None:
        st.info("先打开 PDF 并选择一段已定位的论文文本，再建立链接。")
        return
    locator = reading_selection.locator
    page_number = None if locator is None else locator.get("page_number")
    if (
        not isinstance(page_number, int)
        or isinstance(page_number, bool)
        or page_number < 1
    ):
        st.warning("当前论文选择没有可靠页码定位，不能建立事实链接。")
        return

    st.caption(
        f"论文：{document.document.title} · 第 "
        f"{page_number} 页 → 代码："
        f"{code_selection.relative_path}:"
        f"{code_selection.start_line}-"
        f"{code_selection.end_line}"
    )
    evidence_kind = st.selectbox(
        "论文证据类型",
        options=list(_EVIDENCE_KIND_LABELS),
        format_func=lambda value: _EVIDENCE_KIND_LABELS[value],
        key="evidence_link_kind",
    )
    relation = st.selectbox(
        "代码与论文的关系",
        options=list(_RELATION_LABELS),
        format_func=lambda value: _RELATION_LABELS[value],
        key="evidence_link_relation",
    )
    confidence = float(
        st.slider(
            "我的置信度",
            min_value=0.0,
            max_value=1.0,
            value=0.8,
            step=0.05,
            key="evidence_link_confidence",
        )
    )
    rationale = st.text_area(
        "判断依据（可选）",
        key="evidence_link_rationale",
        height=80,
        placeholder="例如：变量定义和更新顺序与公式一致。",
    )
    if st.button("确认建立证据链接", key="create_evidence_link_button"):
        try:
            link = use_cases.create_evidence_link(
                document,
                reading_selection,
                project,
                code_selection,
                evidence_kind=evidence_kind,
                relation=relation,
                confidence=confidence,
                rationale=rationale,
            )
            links = use_cases.add_evidence_link(
                state.get_evidence_links(),
                link,
            )
            state.set_evidence_links(links)
            st.success("证据链接已由用户确认，并保存在当前会话中。")
        except use_cases.USER_FACING_ERRORS as exc:
            st.error(str(exc))


def _render_evidence_links() -> None:
    links = state.get_evidence_links()
    if not links:
        return
    st.markdown("**当前会话证据链接**")
    st.caption(
        "来源标签会区分用户确认、确定性提取和模型推断；"
        "本阶段只创建用户确认链接。"
    )
    for index, link in enumerate(links, start=1):
        generation = _GENERATION_METHOD_LABELS[link.generation_method]
        relation = _RELATION_LABELS[link.relation]
        st.markdown(f"**{index}. {relation} · {generation}**")
        st.caption(
            f"论文第 {link.paper.page_number} 页 → "
            f"{link.code.relative_path}:"
            f"{link.code.start_line}-{link.code.end_line} · "
            f"置信度 {link.confidence:.2f}"
        )
        if link.rationale:
            st.text(link.rationale)


def _selection_mode(code_file: CodeFile, project_id: str) -> str:
    if not code_file.symbols:
        st.caption("当前文件没有可用 AST 符号，请按行范围选择。")
        return "lines"
    return st.radio(
        "选择方式",
        options=["symbol", "lines"],
        format_func=lambda value: "AST 符号" if value == "symbol" else "行范围",
        horizontal=True,
        key=f"code_selection_mode_{project_id}_{code_file.relative_path}",
    )


def _symbol_label(code_file: CodeFile, index: int) -> str:
    symbol = code_file.symbols[index]
    kind = _SYMBOL_KIND_LABELS.get(symbol.kind, symbol.kind)
    return (
        f"{kind} · {symbol.qualified_name} · "
        f"{symbol.start_line}-{symbol.end_line} 行"
    )


def _render_file_status(code_file: CodeFile) -> None:
    st.caption(
        f"{code_file.line_count:,} 行 · {code_file.size_bytes:,} bytes · "
        f"{code_file.status}"
    )
    if code_file.error:
        st.warning(code_file.error)


def _render_source_preview(code_file: CodeFile) -> None:
    source = code_file.source[:_SOURCE_PREVIEW_CHARACTER_LIMIT]
    with st.expander("源码预览", expanded=False):
        st.code(source, language="python", line_numbers=True)
        if len(code_file.source) > len(source):
            st.caption(
                "界面预览仅显示前 "
                f"{_SOURCE_PREVIEW_CHARACTER_LIMIT:,} 个字符；"
                "选择与上下文仍按明确行范围处理。"
            )


def _render_code_evidence(
    preview: use_cases.CodeContextEvidencePreview,
) -> None:
    with st.expander("代码上下文证据（发送前预览）"):
        st.caption(
            "打开预览不会发起网络请求；以下源码均作为不可信数据处理。"
        )
        st.text(f"项目：{preview.project_name}")
        st.text(f"来源类型：{preview.source_type}")
        st.text(
            f"位置：{preview.relative_path}:"
            f"{preview.start_line}-{preview.end_line}"
        )
        symbol = preview.symbol_name or "（显式行范围）"
        kind = preview.symbol_kind or "未指定"
        st.text(f"符号：{symbol} · {kind}")
        st.text(
            "语言 / 提取方式："
            f"{_LANGUAGE_LABELS[preview.language]} / {preview.extraction_method}"
        )
        st.caption(
            f"请求估算：约 {preview.request_character_count:,} 字符 / "
            f"{preview.approximate_request_tokens:,} tokens。"
        )
        st.markdown("**当前问题**")
        st.code(preview.user_question, language=None)
        st.markdown("**选中代码**")
        st.code(preview.selected_code, language=preview.language, line_numbers=True)
        st.markdown("**预算内邻近代码**")
        st.code(
            preview.surrounding_code or "（无邻近代码）",
            language=preview.language,
            line_numbers=False,
        )


def _render_code_change_controls(
    project: CodeProject,
    selection: CodeSelection,
) -> None:
    if project.managed_by_researchmind:
        st.caption(
            "托管资料库代码保持只读，以保护已登记的哈希和修订。"
        )
        return
    if selection.language != "python":
        st.caption(
            "当前语言仅支持只读静态理解；T5-B1 原地修改权限仅适用于 Python。"
        )
        return
    with st.expander("受控单文件修改（T5-B1）", expanded=False):
        st.warning(
            "模型只会提出当前相对路径与行范围的替换文本。生成建议不会写盘；"
            "应用前请逐行检查 diff，并单独确认。"
        )
        st.caption(
            "不提供 Shell、PowerShell、测试、安装、Git、多文件或任意路径权限。"
            "生成建议时会把当前选择、预算内邻近代码、相对路径和修改要求发送给"
            "已配置的 LLM。"
        )
        instruction = st.text_area(
            "希望怎样修改当前选择",
            key=f"code_change_instruction_{selection.id}",
            height=100,
            placeholder="例如：保留函数签名，为除数为零增加清晰的参数校验。",
        )
        if st.button(
            "生成修改建议（不写盘）",
            key="propose_code_change_button",
        ):
            try:
                proposal = use_cases.propose_code_change(
                    project,
                    selection,
                    instruction=instruction,
                )
                state.set_code_change_proposal(proposal)
                _record_code_change_audit(
                    action="propose",
                    status="success",
                    selection=selection,
                    before_sha256=proposal.original_sha256,
                    after_sha256=proposal.candidate_sha256,
                )
                st.success("建议已生成并通过 UTF-8、行数与 Python 语法校验。")
            except use_cases.USER_FACING_ERRORS as exc:
                _record_code_change_audit(
                    action="propose",
                    status="failed",
                    selection=selection,
                    error=exc,
                )
                st.error(str(exc))

        proposal = state.get_code_change_proposal()
        if (
            proposal is None
            or proposal.project_id != project.id
            or proposal.selection_id != selection.id
        ):
            _render_code_change_audit()
            return

        st.markdown("**待确认修改**")
        st.caption(
            f"{proposal.relative_path}:{proposal.start_line}-"
            f"{proposal.end_line} · 替换 {proposal.replacement_character_count:,} "
            f"字符 · 改变 {proposal.changed_line_count} 行 · Python 语法有效"
        )
        st.code(proposal.unified_diff, language="diff", line_numbers=False)
        confirmed = st.checkbox(
            "我已检查 diff，并确认只修改上述现有 Python 文件的选中行范围。",
            key=f"confirm_code_change_apply_{proposal.id}",
        )
        apply_column, cancel_column = st.columns(2)
        with apply_column:
            if st.button(
                "确认应用并创建恢复副本",
                key="apply_code_change_button",
                type="primary",
                disabled=not confirmed,
            ):
                try:
                    application = use_cases.apply_code_change_proposal(
                        project,
                        proposal,
                        confirmed=confirmed,
                    )
                    state.set_code_change_applied(
                        application.project,
                        application.receipt,
                    )
                    _record_code_change_audit(
                        action="apply",
                        status="success",
                        selection=selection,
                        before_sha256=application.receipt.original_sha256,
                        after_sha256=application.receipt.applied_sha256,
                        recovery_relative_path=(
                            application.receipt.recovery_relative_path
                        ),
                    )
                    st.success(
                        "修改已应用；当前选择与旧证据链接已失效。"
                        f"恢复副本：{application.receipt.recovery_relative_path}"
                    )
                    st.rerun()
                except use_cases.USER_FACING_ERRORS as exc:
                    _record_code_change_audit(
                        action="apply",
                        status="failed",
                        selection=selection,
                        before_sha256=proposal.original_sha256,
                        after_sha256=proposal.candidate_sha256,
                        error=exc,
                    )
                    st.error(str(exc))
        with cancel_column:
            if st.button("取消此建议", key="cancel_code_change_button"):
                state.clear_code_change_proposal()
                _record_code_change_audit(
                    action="cancel",
                    status="canceled",
                    selection=selection,
                    before_sha256=proposal.original_sha256,
                    after_sha256=proposal.candidate_sha256,
                )
                st.info("修改建议已取消；磁盘没有变化。")
        _render_code_change_audit()


def _render_code_change_receipt(project: CodeProject) -> None:
    receipt = state.get_code_change_receipt()
    rollback = state.get_code_change_rollback_receipt()
    if rollback is not None and rollback.project_id == project.id:
        st.success(
            "最近一次受控修改已安全回滚："
            f"{rollback.relative_path} · 恢复副本仍保留。"
        )
    if receipt is None or receipt.project_id != project.id:
        return
    with st.expander("最近一次已应用修改与安全回滚", expanded=True):
        st.caption(
            f"{receipt.relative_path}:{receipt.start_line}-{receipt.end_line} · "
            f"应用时间 {receipt.applied_at}"
        )
        st.code(receipt.recovery_relative_path, language=None)
        st.warning(
            "若文件已被编辑，SHA-256 保护会拒绝回滚，避免覆盖外部修改。"
        )
        confirmed = st.checkbox(
            "我确认回滚最近一次修改，并恢复到写入前内容。",
            key=f"confirm_code_change_rollback_{receipt.proposal_id}",
        )
        if st.button(
            "确认安全回滚",
            key="rollback_code_change_button",
            disabled=not confirmed,
        ):
            try:
                application = use_cases.rollback_applied_code_change(
                    project,
                    receipt,
                    confirmed=confirmed,
                )
                state.set_code_change_rolled_back(
                    application.project,
                    application.receipt,
                )
                state.append_code_change_audit(
                    use_cases.create_code_change_audit_event(
                        action="rollback",
                        status="success",
                        relative_path=receipt.relative_path,
                        start_line=receipt.start_line,
                        end_line=receipt.end_line,
                        before_sha256=receipt.applied_sha256,
                        after_sha256=application.receipt.restored_sha256,
                        recovery_relative_path=receipt.recovery_relative_path,
                    )
                )
                st.success("回滚完成；恢复副本仍保留且未被覆盖。")
                st.rerun()
            except use_cases.USER_FACING_ERRORS as exc:
                state.append_code_change_audit(
                    use_cases.create_code_change_audit_event(
                        action="rollback",
                        status="failed",
                        relative_path=receipt.relative_path,
                        start_line=receipt.start_line,
                        end_line=receipt.end_line,
                        before_sha256=receipt.applied_sha256,
                        after_sha256=receipt.original_sha256,
                        recovery_relative_path=receipt.recovery_relative_path,
                        error=exc,
                    )
                )
                st.error(str(exc))


def _record_code_change_audit(
    *,
    action: str,
    status: str,
    selection: CodeSelection,
    before_sha256: str | None = None,
    after_sha256: str | None = None,
    recovery_relative_path: str | None = None,
    error: Exception | None = None,
) -> None:
    state.append_code_change_audit(
        use_cases.create_code_change_audit_event(
            action=action,
            status=status,
            relative_path=selection.relative_path,
            start_line=selection.start_line,
            end_line=selection.end_line,
            before_sha256=before_sha256,
            after_sha256=after_sha256,
            recovery_relative_path=recovery_relative_path,
            error=error,
        )
    )


def _render_code_change_audit() -> None:
    events = state.get_code_change_audit()
    if not events:
        return
    with st.expander("T5-B1 会话审计（仅元数据）", expanded=False):
        st.caption("不记录源码、修改要求、模型请求、API Key 或绝对项目路径。")
        for event in events[-10:]:
            hashes = ""
            if event.before_sha256 and event.after_sha256:
                hashes = (
                    f" · {event.before_sha256[:12]} → "
                    f"{event.after_sha256[:12]}"
                )
            error = f" · {event.error_type}" if event.error_type else ""
            st.text(
                f"{event.occurred_at} · {event.action}/{event.status} · "
                f"{event.relative_path}:{event.start_line}-{event.end_line}"
                f"{hashes}{error}"
            )
