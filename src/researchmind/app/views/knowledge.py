"""Streamlit knowledge-note capture, preview, and save view."""

import streamlit as st

from researchmind.app import state, use_cases


def render_knowledge() -> None:
    """Render selected-message capture, Markdown preview, and Vault save."""

    st.subheader("4. 知识沉淀")
    if not state.is_knowledge_panel_open():
        st.info("在研究对话中点击“沉淀为知识”后整理笔记。")
        return

    document = state.get_opened_document()
    if document is None:
        st.error("请先打开 PDF。")
        return

    selection = state.get_current_selection()
    messages = state.get_messages()
    message_indices = list(range(len(messages)))
    selected_indices = st.multiselect(
        "选择要保存的对话内容",
        options=message_indices,
        default=message_indices,
        format_func=lambda index: _message_label(messages[index]),
        key=f"knowledge_message_indices_{document.document.id}",
    )
    default_title = (
        selection.text[:80] if selection is not None else document.document.title
    )
    title = st.text_input(
        "笔记标题",
        value=default_title,
        key=f"knowledge_title_{document.document.id}",
    )
    user_notes = st.text_area(
        "我的理解",
        key=f"knowledge_user_notes_{document.document.id}",
        height=140,
    )
    tags_text = st.text_input(
        "标签（逗号分隔）",
        key=f"knowledge_tags_{document.document.id}",
        placeholder="optimization, algorithm",
    )

    if st.button("生成 Markdown 预览", key="preview_knowledge_button"):
        try:
            note = use_cases.capture_knowledge(
                document,
                selection,
                [messages[index] for index in selected_indices],
                user_notes,
                tags_text.split(","),
                title=title,
            )
            state.set_current_note(note)
        except use_cases.USER_FACING_ERRORS as exc:
            st.error(str(exc))

    note = state.get_current_note()
    if note is None:
        return

    try:
        markdown = use_cases.preview_note_markdown(note)
    except use_cases.USER_FACING_ERRORS as exc:
        st.error(str(exc))
        return
    st.code(markdown, language="markdown")

    if st.button("保存到 Obsidian Vault", key="save_knowledge_button"):
        try:
            saved_path = use_cases.save_note_to_vault(note)
            state.set_last_saved_path(saved_path)
            st.success(f"已保存：{saved_path}")
        except use_cases.USER_FACING_ERRORS as exc:
            st.error(str(exc))

    saved_path = state.get_last_saved_path()
    if saved_path is not None:
        st.caption(f"最近保存位置：{saved_path}")


def _message_label(message: object) -> str:
    task = getattr(message, "task", "message")
    content = " ".join(str(getattr(message, "content", "")).split())
    excerpt = content if len(content) <= 60 else content[:57] + "..."
    return f"{task}: {excerpt}"
