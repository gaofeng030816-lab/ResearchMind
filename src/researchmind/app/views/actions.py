"""Streamlit selection, translation, and explanation actions."""

import streamlit as st

from researchmind.app import state, use_cases
from researchmind.app.views.context_evidence import render_context_evidence


_MODE_LABELS: dict[use_cases.ExplainMode, str] = {
    "concept": "概念解释",
    "math": "数学解释",
    "algorithm": "算法解释",
    "contextual": "上下文解释",
}


def render_actions() -> None:
    """Render selection creation and independent AI-backed actions."""

    st.subheader("2. 选择、翻译与解释")
    document = state.get_opened_document()
    if document is None:
        st.info("打开 PDF 后可选择文本并调用翻译或 AI 解释。")
        return

    selected_text = st.text_area(
        "选中文本",
        key=state.selection_text_widget_key(document.document.id),
        placeholder="从上方文本面板复制，或直接输入需要理解的内容。",
        height=130,
    )
    if st.button("确认选择", key="create_selection_button"):
        try:
            selection = use_cases.create_selection(
                document,
                selected_text,
                state.get_current_page_number(),
            )
            state.set_current_selection(selection)
            if selection.locator is None:
                st.warning("未定位到原文；仍可翻译或解释该文本。")
            else:
                st.success(f"已定位：{_selection_location_label(selection.locator)}")
        except use_cases.USER_FACING_ERRORS as exc:
            st.error(str(exc))

    selection = state.get_current_selection()
    if selection is None:
        return

    if selection.locator is None:
        st.caption("当前选择：未定位的手动文本")
    else:
        st.caption(f"当前选择：{_selection_location_label(selection.locator)}")

    mode = st.selectbox(
        "解释模式",
        options=list(_MODE_LABELS),
        format_func=lambda value: _MODE_LABELS[value],
        key="explanation_mode_select",
    )
    question = st.text_input(
        "解释问题（可选）",
        key="explanation_question_input",
        placeholder="例如：作者为什么在这里引入这个参数？",
    )
    st.caption("翻译仅发送选中文本和目标语言，不使用 ResearchContext。")
    try:
        preview = use_cases.preview_explanation_context(
            selection,
            mode,
            document=document,
            conversation=state.get_current_conversation(),
            question=question.strip() or None,
        )
        render_context_evidence(preview, action_label="AI 解释")
        latex_preview = use_cases.preview_latex_context(
            selection,
            document=document,
            conversation=state.get_current_conversation(),
        )
        render_context_evidence(latex_preview, action_label="LaTeX 转换")
    except use_cases.USER_FACING_ERRORS as exc:
        st.error(str(exc))

    st.caption(
        "LaTeX 转换会发送当前选择和最小 ResearchContext；"
        "仅处理文字层，不读取图片公式。"
    )
    translation_column, latex_column, explanation_column = st.columns(3)
    with translation_column:
        if st.button(
            "翻译",
            key="translate_selection_button",
            width="stretch",
        ):
            try:
                message = use_cases.translate_selection(selection)
                state.append_message(message)
                st.success("翻译已加入对话。")
            except use_cases.USER_FACING_ERRORS as exc:
                st.error(str(exc))
    with latex_column:
        if st.button(
            "转换为 LaTeX",
            key="convert_latex_button",
            width="stretch",
        ):
            try:
                message = use_cases.convert_selection_to_latex(
                    selection,
                    document=document,
                    conversation=state.get_current_conversation(),
                )
                state.append_exchange(
                    "将当前选择转换为 LaTeX",
                    "convert:latex",
                    message,
                )
                st.success("LaTeX 已加入对话，可复制或预览。")
            except use_cases.USER_FACING_ERRORS as exc:
                st.error(str(exc))
    with explanation_column:
        if st.button(
            "AI 解释",
            key="explain_selection_button",
            width="stretch",
        ):
            try:
                message = use_cases.explain_selection(
                    selection,
                    mode,
                    document=document,
                    conversation=state.get_current_conversation(),
                    question=question.strip() or None,
                )
                user_content = question.strip() or f"请求{_MODE_LABELS[mode]}"
                state.append_exchange(
                    user_content,
                    f"explain:{mode}",
                    message,
                )
                st.success("解释已加入对话。")
            except use_cases.USER_FACING_ERRORS as exc:
                st.error(str(exc))


def _selection_location_label(locator: dict[str, object]) -> str:
    page = locator.get("page_number", "未知")
    block = locator.get("block_index", "未知")
    bbox = locator.get("bbox")
    if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
        bbox_label = ", ".join(f"{float(value):.1f}" for value in bbox)
    else:
        bbox_label = "未提供"
    origin = locator.get("origin")
    if origin == "pdfjs_text_layer_reconciled_with_pymupdf":
        status = locator.get("locator_status", "已核对")
        return (
            f"第 {page} 页 · PDF.js 文字层 / PyMuPDF 服务端对账（{status}）"
            f" · 文本块 {block} · bbox {bbox_label}"
        )
    return f"第 {page} 页 · 文本块 {block} · bbox {bbox_label}"
