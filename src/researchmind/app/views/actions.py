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
        key=f"selection_text_{document.document.id}",
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
                st.success(f"已定位到第 {selection.locator['page_number']} 页。")
        except use_cases.USER_FACING_ERRORS as exc:
            st.error(str(exc))

    selection = state.get_current_selection()
    if selection is None:
        return

    if selection.locator is None:
        st.caption("当前选择：未定位的手动文本")
    else:
        st.caption(f"当前选择：第 {selection.locator['page_number']} 页")

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
    except use_cases.USER_FACING_ERRORS as exc:
        st.error(str(exc))

    translation_column, explanation_column = st.columns(2)
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
