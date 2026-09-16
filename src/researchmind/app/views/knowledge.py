"""Streamlit durable draft composer and V2 compatibility export view."""

from __future__ import annotations

import streamlit as st

from researchmind.app import state, use_cases
from researchmind.models import NoteDraft
from researchmind.pdf import OpenedDocument


def render_knowledge() -> None:
    """Render explicit durable editing plus the retained V2 compatibility flow."""

    st.subheader("5. Markdown 草稿与输出")
    document = state.get_opened_document()
    if document is None:
        st.info("请先打开 PDF。")
        return

    if use_cases.is_library_configured():
        _render_durable_composer(document)
    else:
        st.info(
            "配置 RESEARCHMIND_DATA_DIR 后可使用跨重启草稿、证据预览和"
            "明确的 Obsidian 输出。"
        )

    if state.is_knowledge_panel_open():
        with st.expander("V2 兼容笔记导出", expanded=False):
            _render_legacy_knowledge(document)


def _render_durable_composer(document: OpenedDocument) -> None:
    try:
        drafts = use_cases.list_paper_note_drafts(
            document,
            library_entry=state.get_opened_paper_library_entry(),
        )
    except use_cases.USER_FACING_ERRORS as exc:
        st.error(str(exc))
        return

    current = state.get_current_note_draft()
    if drafts:
        draft_ids = [draft.id for draft in drafts]
        selected_index = (
            draft_ids.index(current.id)
            if current is not None and current.id in draft_ids
            else 0
        )
        selected_id = st.selectbox(
            "当前论文的本地草稿",
            options=draft_ids,
            index=selected_index,
            format_func=lambda draft_id: _draft_label(drafts, draft_id),
            key=f"note_draft_select_{document.document.id}",
        )
        if current is None or selected_id != current.id:
            if st.button(
                "打开所选草稿",
                key="open_selected_note_draft_button",
            ):
                selected = next(
                    draft for draft in drafts if draft.id == selected_id
                )
                state.set_current_note_draft(selected)
                st.rerun()

    with st.container(horizontal=True):
        if st.button("新建空白草稿", key="create_empty_note_draft_button"):
            try:
                draft = use_cases.create_paper_note_draft(
                    document,
                    library_entry=state.get_opened_paper_library_entry(),
                )
                state.set_current_note_draft(draft)
                st.rerun()
            except use_cases.USER_FACING_ERRORS as exc:
                st.error(str(exc))

    current = state.get_current_note_draft()
    if current is None:
        st.caption(
            "选择已有草稿、显式新建草稿，或在上方把原文/译文加入证据篮后开始。"
        )
        return

    _render_draft_editor(current)


def _render_draft_editor(draft: NoteDraft) -> None:
    st.caption(
        f"ResearchMind 本地草稿修订 {draft.revision}。"
        "编辑不会自动保存，也不会自动写入 Obsidian。"
    )
    title = st.text_input(
        "草稿标题",
        value=draft.title,
        key=f"note_draft_title_{draft.id}",
    )
    body_markdown = st.text_area(
        "可编辑 Markdown 正文",
        value=draft.body_markdown,
        key=f"note_draft_body_{draft.id}",
        height=280,
        placeholder="写下你的理解、结论和待验证问题……",
    )
    editor_matches_saved = (
        title.strip() == draft.title
        and body_markdown == draft.body_markdown
    )
    if not editor_matches_saved:
        st.warning("当前编辑尚未保存；先保存到本地资料库，才能生成同版预览。")

    with st.container(horizontal=True):
        if st.button(
            "保存草稿到本地资料库",
            key="save_note_draft_locally_button",
            disabled=editor_matches_saved,
        ):
            try:
                updated = use_cases.update_note_draft(
                    draft.id,
                    title=title,
                    body_markdown=body_markdown,
                    status=draft.status,
                    expected_revision=draft.revision,
                )
                state.set_current_note_draft(updated)
                st.rerun()
            except use_cases.USER_FACING_ERRORS as exc:
                st.error(str(exc))
        if st.button(
            "生成已保存版本预览",
            key="preview_note_draft_button",
            disabled=not editor_matches_saved,
        ):
            try:
                preview = use_cases.preview_note_draft_markdown(
                    draft.id,
                    expected_revision=draft.revision,
                )
                state.set_current_note_draft_preview(preview)
            except use_cases.USER_FACING_ERRORS as exc:
                st.error(str(exc))

    if not editor_matches_saved:
        st.caption("旧预览已暂停使用；保存当前编辑后再生成新预览。")
        return

    preview = state.get_current_note_draft_preview()
    if (
        preview is None
        or preview.draft_id != draft.id
        or preview.draft_revision != draft.revision
    ):
        st.caption("还没有与当前修订一致的 Markdown 预览。")
        return

    st.markdown("**渲染预览（不会创建文件）**")
    with st.container(border=True):
        st.markdown(preview.markdown)
    with st.expander("查看将写入 Vault 的准确 Markdown"):
        st.code(preview.markdown, language="markdown")
    st.caption(
        f"修订 {preview.draft_revision} · 纳入证据 "
        f"{preview.included_evidence_count} 条 · SHA-256 {preview.sha256[:12]}…"
    )

    confirmed = st.checkbox(
        "我确认把上方这一版预览写入 Obsidian（同名文件不会被覆盖）",
        key=f"confirm_note_draft_vault_{preview.sha256}",
    )
    if st.button(
        "保存当前预览到 Obsidian Vault",
        key="save_note_draft_to_vault_button",
        disabled=not confirmed,
        type="primary",
    ):
        try:
            saved_path = use_cases.save_note_draft_to_vault(preview)
            state.set_last_note_draft_saved_path(saved_path)
            st.success(f"已保存：{saved_path}")
        except use_cases.USER_FACING_ERRORS as exc:
            st.error(str(exc))

    saved_path = state.get_last_note_draft_saved_path()
    if saved_path is not None:
        st.caption(f"最近保存位置：{saved_path}")


def _render_legacy_knowledge(document: OpenedDocument) -> None:
    selection = state.get_current_selection()
    messages = state.get_messages()
    message_indices = list(range(len(messages)))
    selected_indices = st.multiselect(
        "选择要保存的对话内容",
        options=message_indices,
        default=[],
        format_func=lambda index: _message_label(messages[index]),
        key=f"knowledge_message_indices_{document.document.id}",
    )
    st.caption("只有你在上方明确勾选的会话内容才会进入这份兼容笔记。")
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
                evidence_links=state.get_evidence_links(),
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


def _draft_label(drafts: list[NoteDraft], draft_id: str) -> str:
    draft = next(item for item in drafts if item.id == draft_id)
    return f"{draft.title} · 修订 {draft.revision}"


def _message_label(message: object) -> str:
    task = getattr(message, "task", "message")
    content = " ".join(str(getattr(message, "content", "")).split())
    excerpt = content if len(content) <= 60 else content[:57] + "..."
    return f"{task}: {excerpt}"
