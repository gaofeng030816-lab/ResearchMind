"""Streamlit view for the V3 library and optional Zotero source links."""

from __future__ import annotations

from hashlib import sha256

import streamlit as st

from researchmind.app import state, use_cases
from researchmind.models import (
    LibraryEntry,
    LibraryItemKind,
    UploadedFileData,
    ZoteroBrowseResult,
    ZoteroItemDetails,
)


_KIND_LABELS = {
    "all": "全部",
    "paper": "论文",
    "code": "代码",
}


def render_library() -> None:
    """Render explicit imports and managed local-library actions."""

    st.subheader("本地研究资料库")
    st.caption(
        "点击选择或拖放文件后，ResearchMind 会验证并复制到显式配置的私有数据目录。"
        "数据库只保存元数据、哈希、修订和相对路径。"
    )
    if not use_cases.is_library_configured():
        st.info(
            "先在 .env 中填写 RESEARCHMIND_DATA_DIR，再重新启动 ResearchMind。"
            "该目录必须与 Obsidian Vault 分开。"
        )
        return

    _render_imports()
    st.divider()
    _render_zotero_connection()
    st.divider()
    _render_entries()


def _render_imports() -> None:
    st.markdown("**点击导入**")
    paper_upload = st.file_uploader(
        "选择或拖放一篇 PDF",
        type=["pdf"],
        accept_multiple_files=False,
        key="library_pdf_upload",
    )
    if st.button(
        "导入 PDF 到资料库",
        key="library_import_pdf_button",
        type="primary",
        disabled=paper_upload is None,
    ):
        try:
            result = use_cases.import_pdf_to_library(
                UploadedFileData(
                    name=paper_upload.name,
                    content=paper_upload.getvalue(),
                )
            )
            if result.duplicate:
                st.info(
                    f"已存在完全相同的论文：{result.entry.record.title}"
                )
            else:
                st.success(
                    f"已导入论文：{result.entry.record.title}"
                )
        except use_cases.USER_FACING_ERRORS as exc:
            st.error(str(exc))

    code_uploads = st.file_uploader(
        "选择或拖放一个 Python 代码目录",
        type=["py"],
        accept_multiple_files="directory",
        key="library_code_directory_upload",
        help=(
            "V3-G1 延续 V2 的 Python 静态阅读边界；C、Java、Julia、R "
            "将在 V3-G6 通过解析器门禁后加入。"
        ),
    )
    project_name = st.text_input(
        "代码项目名称（可选）",
        key="library_code_project_name",
        placeholder="留空时使用上传目录名称",
    )
    if st.button(
        "导入代码目录到资料库",
        key="library_import_code_button",
        disabled=not code_uploads,
    ):
        try:
            result = use_cases.import_code_directory_to_library(
                [
                    UploadedFileData(
                        name=upload.name,
                        content=upload.getvalue(),
                    )
                    for upload in code_uploads
                ],
                project_name=project_name,
            )
            if result.duplicate:
                st.info(
                    f"已存在完全相同的代码目录：{result.entry.record.title}"
                )
            else:
                st.success(
                    f"已导入代码目录：{result.entry.record.title}"
                )
        except use_cases.USER_FACING_ERRORS as exc:
            st.error(str(exc))


def _render_entries() -> None:
    st.markdown("**资料库内容**")
    filter_kind = st.radio(
        "资料类型",
        options=list(_KIND_LABELS),
        format_func=lambda value: _KIND_LABELS[value],
        horizontal=True,
        key="library_kind_filter",
        label_visibility="collapsed",
    )
    include_removed = st.checkbox(
        "显示已从资料库移除的记录",
        key="library_include_removed",
    )
    kind: LibraryItemKind | None = (
        None if filter_kind == "all" else filter_kind
    )
    try:
        entries = use_cases.list_library_entries(
            kind=kind,
            include_removed=include_removed,
        )
    except use_cases.USER_FACING_ERRORS as exc:
        st.error(str(exc))
        return
    if not entries:
        st.info("当前筛选下还没有资料。")
        return

    selected_id = st.selectbox(
        "选择资料",
        options=[entry.record.id for entry in entries],
        format_func=lambda record_id: _entry_label(
            _entry_by_id(entries, record_id)
        ),
        key="library_entry_select",
    )
    entry = _entry_by_id(entries, selected_id)
    st.caption(
        f"类型：{_KIND_LABELS[entry.record.kind]} · "
        f"修订：{entry.asset.revision} · "
        f"托管大小：{entry.asset.size_bytes:,} bytes"
    )

    if entry.record.removed_at is None:
        _render_active_entry_actions(entry)
    else:
        _render_removed_entry_actions(entry)


def _render_active_entry_actions(entry: LibraryEntry) -> None:
    with st.container(horizontal=True):
        if st.button(
            "打开论文" if entry.record.kind == "paper" else "打开代码",
            key=f"library_open_{entry.record.id}",
            type="primary",
        ):
            try:
                if entry.record.kind == "paper":
                    state.set_opened_document(
                        use_cases.open_library_paper(entry.record.id)
                    )
                    state.request_workspace("paper")
                else:
                    state.set_opened_code_project(
                        use_cases.open_library_code_project(entry.record.id)
                    )
                    state.request_workspace("code")
                st.rerun()
            except use_cases.USER_FACING_ERRORS as exc:
                st.error(str(exc))

    if entry.record.kind == "paper":
        _render_entry_zotero_link(entry)

    _render_revision_import(entry)
    remove_confirmed = st.checkbox(
        "我确认只把该记录从资料库列表移除；此操作不会删除托管副本。",
        key=f"library_remove_confirm_{entry.record.id}",
    )
    if st.button(
        "从资料库移除",
        key=f"library_remove_{entry.record.id}",
        disabled=not remove_confirmed,
    ):
        try:
            use_cases.remove_library_record(
                entry.record.id,
                confirmed=remove_confirmed,
            )
            st.rerun()
        except use_cases.USER_FACING_ERRORS as exc:
            st.error(str(exc))


def _render_revision_import(entry: LibraryEntry) -> None:
    with st.expander("导入该资料的新修订", expanded=False):
        st.caption(
            "新内容会建立独立 AssetReference，不覆盖旧修订；"
            "导入后重新打开该资料即可使用最新修订。"
        )
        if entry.record.kind == "paper":
            upload = st.file_uploader(
                "选择新 PDF 修订",
                type=["pdf"],
                key=f"library_pdf_revision_{entry.record.id}",
            )
            if st.button(
                "导入 PDF 新修订",
                key=f"library_import_pdf_revision_{entry.record.id}",
                disabled=upload is None,
            ):
                try:
                    result = use_cases.import_pdf_to_library(
                        UploadedFileData(
                            name=upload.name,
                            content=upload.getvalue(),
                        ),
                        record_id=entry.record.id,
                    )
                    if result.duplicate:
                        st.info("该内容已存在，没有创建重复修订。")
                    else:
                        st.success(
                            f"已建立修订 {result.entry.asset.revision}。"
                        )
                except use_cases.USER_FACING_ERRORS as exc:
                    st.error(str(exc))
            return

        uploads = st.file_uploader(
            "选择新的 Python 目录修订",
            type=["py"],
            accept_multiple_files="directory",
            key=f"library_code_revision_{entry.record.id}",
        )
        if st.button(
            "导入代码目录新修订",
            key=f"library_import_code_revision_{entry.record.id}",
            disabled=not uploads,
        ):
            try:
                result = use_cases.import_code_directory_to_library(
                    [
                        UploadedFileData(
                            name=upload.name,
                            content=upload.getvalue(),
                        )
                        for upload in uploads
                    ],
                    record_id=entry.record.id,
                )
                if result.duplicate:
                    st.info("该内容已存在，没有创建重复修订。")
                else:
                    st.success(
                        f"已建立修订 {result.entry.asset.revision}。"
                    )
            except use_cases.USER_FACING_ERRORS as exc:
                st.error(str(exc))


def _render_removed_entry_actions(entry: LibraryEntry) -> None:
    st.warning(
        "该记录已从资料库移除，但 ResearchMind 托管副本仍然存在。"
    )
    if entry.record.kind == "paper":
        _render_entry_zotero_link(entry)
    with st.container(horizontal=True):
        if st.button(
            "恢复到资料库",
            key=f"library_restore_{entry.record.id}",
        ):
            try:
                use_cases.restore_library_record(entry.record.id)
                st.rerun()
            except use_cases.USER_FACING_ERRORS as exc:
                st.error(str(exc))

    delete_confirmed = st.checkbox(
        "我确认永久删除 ResearchMind 管理的所有修订副本；"
        "外部原文件和 Obsidian 笔记不会被删除。",
        key=f"library_delete_confirm_{entry.record.id}",
    )
    if st.button(
        "删除托管副本",
        key=f"library_delete_{entry.record.id}",
        disabled=not delete_confirmed,
    ):
        try:
            count = use_cases.delete_library_managed_copies(
                entry.record.id,
                confirmed=delete_confirmed,
            )
            st.success(f"已删除 {count} 个 ResearchMind 托管修订副本。")
            st.rerun()
        except use_cases.USER_FACING_ERRORS as exc:
            st.error(str(exc))


def _render_zotero_connection() -> None:
    st.markdown("**Zotero 只读连接（可选）**")
    if not use_cases.is_zotero_local_api_enabled():
        st.info(
            "当前未连接 Zotero。需要时在 .env 中设置 "
            "ZOTERO_LOCAL_API_ENABLED=true 并重启；"
            "默认关闭不会影响本地资料库。"
        )
        return

    st.caption(
        "仅在你点击按钮后读取本机 Zotero 的个人资料库。"
        "ResearchMind 不写入 Zotero，也不会在后台同步或缓存整个资料库。"
    )
    query = st.text_input(
        "搜索 Zotero 最近条目（可留空）",
        key="zotero_query",
        placeholder="标题、作者或关键词",
    )
    if st.button("读取 Zotero 条目", key="zotero_browse_button"):
        try:
            state.set_zotero_browse_result(
                use_cases.browse_zotero_items(query=query)
            )
        except use_cases.USER_FACING_ERRORS as exc:
            state.clear_zotero_browse_result()
            st.error(str(exc))

    browse_result = state.get_zotero_browse_result()
    if browse_result is None:
        return
    if not browse_result.items:
        st.info("本次读取没有找到可链接的文献条目。")
        return

    item_key = st.selectbox(
        "选择一个 Zotero 文献条目",
        options=[item.item_key for item in browse_result.items],
        format_func=lambda key: _zotero_item_label(
            browse_result,
            key,
        ),
        key="zotero_item_select",
    )
    if st.button(
        "读取该条目的 PDF 附件",
        key="zotero_fetch_attachments_button",
    ):
        try:
            state.set_zotero_item_details(
                use_cases.get_zotero_item_details(
                    browse_result,
                    item_key,
                )
            )
        except use_cases.USER_FACING_ERRORS as exc:
            state.clear_zotero_item_details()
            st.error(str(exc))

    details = state.get_zotero_item_details()
    if details is None or details.item.item_key != item_key:
        return

    creators = "、".join(details.item.creators) or "未提供作者"
    st.text(
        f"{details.item.title} · {creators} · "
        f"Zotero 版本 {details.item.item_version}"
    )
    attachment_key: str | None = None
    if details.attachments:
        attachment_key = st.selectbox(
            "选择 PDF 附件",
            options=[item.item_key for item in details.attachments],
            format_func=lambda key: _zotero_attachment_label(
                details,
                key,
            ),
            key="zotero_attachment_select",
        )
    else:
        st.warning(
            "该条目没有可由 Zotero Local API 提供的 PDF 附件；"
            "仍可把元数据来源链接到已导入论文。"
        )

    _render_zotero_link_existing(details, attachment_key)
    if attachment_key is not None:
        _render_zotero_import(details, attachment_key)


def _render_zotero_link_existing(
    details: ZoteroItemDetails,
    attachment_key: str | None,
) -> None:
    try:
        papers = use_cases.list_library_entries(kind="paper")
    except use_cases.USER_FACING_ERRORS as exc:
        st.error(str(exc))
        return
    if not papers:
        st.info("资料库中还没有可链接的论文；请先用上方 PDF 上传框导入文件。")
        return
    record_id = st.selectbox(
        "链接到已有论文",
        options=[paper.record.id for paper in papers],
        format_func=lambda value: _entry_label(
            _entry_by_id(papers, value)
        ),
        key="zotero_existing_paper_select",
    )
    include_attachment = False
    if attachment_key is not None:
        include_attachment = st.checkbox(
            "同时记录所选 PDF 附件的来源身份",
            value=True,
            key="zotero_link_include_attachment",
        )
    confirmed = st.checkbox(
        "我确认建立只读来源链接；不会修改 Zotero 或论文文件。",
        key=(
            f"zotero_link_confirm_{record_id}_"
            + _zotero_confirmation_scope(
                details, attachment_key if include_attachment else None,
            )
        ),
    )
    if st.button(
        "链接已有论文",
        key="zotero_link_existing_button",
        disabled=not confirmed,
    ):
        try:
            use_cases.link_zotero_item_to_paper(
                record_id,
                details,
                attachment_key=(
                    attachment_key if include_attachment else None
                ),
                confirmed=confirmed,
            )
            st.success("已保存 Zotero 来源链接；没有复制或修改文件。")
        except use_cases.USER_FACING_ERRORS as exc:
            st.error(str(exc))


def _render_zotero_import(details: ZoteroItemDetails, attachment_key: str) -> None:
    root_scope = use_cases.zotero_attachment_approval_scope()
    if root_scope is None:
        st.info(
            "直接复制需要 Windows，并在 .env 中设置 ZOTERO_ATTACHMENT_ROOT "
            "为你批准的 Zotero 附件目录。不要填写网络盘或整个磁盘。"
            "未配置时仍可手动上传 PDF 后链接来源。"
        )
    st.caption("只读复制所选的一个 PDF 到 ResearchMind；不修改 Zotero 原文件，不外发内容。")
    confirmed = st.checkbox(
        "我批准只读复制当前选中的 PDF，且仅允许读取已配置的附件目录。",
        key=(
            "zotero_import_confirm_" + _zotero_confirmation_scope(details, attachment_key)
            + "_" + str(root_scope) + "_" + str(state.get_zotero_action_generation())
        ),
        disabled=root_scope is None,
    )
    if st.button(
        "复制所选 Zotero PDF 到资料库",
        key="zotero_import_pdf_button",
        disabled=root_scope is None or not confirmed,
    ):
        try:
            result = use_cases.import_zotero_pdf_attachment(
                details, attachment_key, confirmed=confirmed, approved_root_scope=root_scope,
            )
            state.clear_zotero_item_details()
            st.success(
                "已复用相同 PDF 并链接来源。" if result.duplicate
                else "已复制 PDF 并链接来源；Zotero 原件未改动。"
            )
        except use_cases.USER_FACING_ERRORS as exc:
            state.clear_zotero_item_details()
            st.error(str(exc))


def _render_entry_zotero_link(entry: LibraryEntry) -> None:
    try:
        link = use_cases.get_zotero_source_link(entry.record.id)
    except use_cases.USER_FACING_ERRORS as exc:
        st.error(str(exc))
        return
    if link is None:
        return
    with st.expander("Zotero 来源", expanded=False):
        st.text(link.title or "未命名 Zotero 条目")
        st.text(
            f"条目 {link.item_key} · Zotero 版本 {link.item_version}"
            + (
                ""
                if link.attachment_filename is None
                else f" · 附件 {link.attachment_filename}"
            )
        )
        confirmed = st.checkbox(
            "我确认只解除 ResearchMind 中的链接；"
            "不会删除 Zotero 条目、附件或托管论文。",
            key=f"zotero_unlink_confirm_{entry.record.id}",
        )
        if st.button(
            "解除 Zotero 链接",
            key=f"zotero_unlink_{entry.record.id}",
            disabled=not confirmed,
        ):
            try:
                use_cases.unlink_zotero_item_from_paper(
                    entry.record.id,
                    confirmed=confirmed,
                )
                st.success("已解除 ResearchMind 来源链接。")
            except use_cases.USER_FACING_ERRORS as exc:
                st.error(str(exc))


def _zotero_confirmation_scope(
    details: ZoteroItemDetails,
    attachment_key: str | None,
) -> str:
    """Invalidate confirmation when its source, revision, or attachment changes."""

    identity = (
        details.connection.server_id,
        details.item.library_type,
        details.item.library_id,
        details.item.item_key,
        details.item.item_version,
        tuple(
            (item.item_key, item.item_version)
            for item in details.attachments
            if item.item_key == attachment_key
        ),
    )
    return sha256(repr(identity).encode("utf-8")).hexdigest()[:24]


def _zotero_item_label(
    browse_result: ZoteroBrowseResult,
    item_key: str,
) -> str:
    item = next(
        item for item in browse_result.items if item.item_key == item_key
    )
    creators = "、".join(item.creators[:2]) or "未知作者"
    return f"{item.title or '未命名条目'} · {creators}"


def _zotero_attachment_label(
    details: ZoteroItemDetails,
    item_key: str,
) -> str:
    attachment = next(
        item for item in details.attachments if item.item_key == item_key
    )
    return f"{attachment.filename} · v{attachment.item_version}"


def _entry_by_id(
    entries: list[LibraryEntry],
    record_id: str,
) -> LibraryEntry:
    return next(entry for entry in entries if entry.record.id == record_id)


def _entry_label(entry: LibraryEntry) -> str:
    removed = " · 已移除" if entry.record.removed_at is not None else ""
    return (
        f"{_KIND_LABELS[entry.record.kind]} · {entry.record.title}"
        f" · r{entry.asset.revision}{removed}"
    )
