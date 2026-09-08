"""Streamlit reader view for local PDF navigation and search."""

from functools import partial
from pathlib import Path

import streamlit as st

from researchmind.app import state, use_cases


@st.cache_resource(show_spinner=False)
def _cached_open_pdf(path_text: str) -> use_cases.OpenedDocument:
    return use_cases.open_pdf(Path(path_text))


@st.cache_data(show_spinner=False, max_entries=4)
def _cached_pdf_viewer_source(
    path_text: str,
    expected_sha256: str,
    max_size_bytes: int,
) -> use_cases.PdfViewerSource:
    return use_cases.load_pdf_text_layer_source(
        Path(path_text),
        expected_sha256=expected_sha256,
        max_size_bytes=max_size_bytes,
    )


def render_reader() -> None:
    """Render PDF opening, page navigation, zoom, text, and search controls."""

    st.subheader("1. 阅读论文")
    path_text = st.text_input(
        "本地 PDF 路径",
        key="pdf_path_input",
        placeholder="D:/papers/example.pdf",
    )
    if st.button("打开 PDF", key="open_pdf_button", type="primary"):
        try:
            opened = _cached_open_pdf(path_text.strip())
            state.set_opened_document(opened)
            st.success(f"已打开：{opened.document.title}")
        except use_cases.USER_FACING_ERRORS as exc:
            st.error(str(exc))

    document = state.get_opened_document()
    if document is None:
        st.info("输入本地 PDF 路径后开始阅读。")
        return

    st.markdown(
        f"**{document.document.title}**  ·  "
        f"{document.document.num_pages} 页  ·  "
        f"作者：{', '.join(document.document.authors) or '未提供'}"
    )
    viewer_key = state.pdf_viewer_key(
        document.document.id,
        document.content_sha256,
    )
    viewer_source: use_cases.PdfViewerSource | None = None
    viewer_error: str | None = None
    try:
        viewer_source = _cached_pdf_viewer_source(
            str(document.document.path),
            document.content_sha256,
            document.max_size_bytes,
        )
        _process_pending_viewer_events(
            document,
            viewer_source,
            viewer_key=viewer_key,
        )
    except use_cases.USER_FACING_ERRORS as exc:
        viewer_error = str(exc)

    text_coverage = use_cases.get_document_text_coverage(document)
    if text_coverage.is_limited:
        if text_coverage.pages_with_text == 0:
            coverage_message = "整篇文档未提取到可用文本"
        else:
            coverage_message = (
                f"仅 {text_coverage.pages_with_text}/"
                f"{text_coverage.total_pages} 页提取到文本"
            )
        st.warning(
            f"PDF 文本可提取性较低：{coverage_message}。"
            "这通常意味着文档是扫描版或以图像为主；V1 不包含 OCR。"
            "你仍可查看页面图像，或手动输入文字进行翻译和解释。"
        )

    previous_column, next_column = st.columns(2)
    current_page = state.get_current_page_number()
    with previous_column:
        st.button(
            "上一页",
            key="previous_page_button",
            disabled=current_page <= 1,
            width="stretch",
            on_click=state.set_current_page_number,
            args=(current_page - 1,),
        )
    with next_column:
        st.button(
            "下一页",
            key="next_page_button",
            disabled=current_page >= document.document.num_pages,
            width="stretch",
            on_click=state.set_current_page_number,
            args=(current_page + 1,),
        )

    jump_column, zoom_column = st.columns(2)
    with jump_column:
        page_widget_key = state.page_number_widget_key(document.document.id)
        st.number_input(
            "页码（加减后立即跳转）",
            min_value=1,
            max_value=document.document.num_pages,
            value=state.get_current_page_number(),
            step=1,
            key=page_widget_key,
            on_change=state.set_current_page_number_from_widget,
            args=(page_widget_key,),
        )
    with zoom_column:
        zoom = st.slider(
            "页面缩放",
            min_value=0.5,
            max_value=3.0,
            value=1.0,
            step=0.25,
            key=f"page_zoom_{document.document.id}",
        )

    try:
        page_view = use_cases.get_page_view(
            document,
            state.get_current_page_number(),
            zoom=zoom,
        )
    except use_cases.USER_FACING_ERRORS as exc:
        st.error(str(exc))
        return

    viewer_mounted = False
    if viewer_source is not None and zoom <= 2.5:
        st.caption(
            "PDF.js 文字层在本机浏览器渲染。拖选后先在组件内预览，"
            "点击“确认使用当前选择”才会由 PyMuPDF 重新核对文字与位置。"
        )
        try:
            use_cases.mount_pdf_text_layer(
                viewer_source,
                page=page_view.page.page_number,
                page_count=document.document.num_pages,
                scale=float(zoom),
                key=viewer_key,
                on_selection=partial(
                    state.capture_pdf_viewer_event,
                    viewer_key,
                    instance=viewer_key,
                    event_kind="selection",
                ),
                on_page_turn=partial(
                    state.capture_pdf_viewer_event,
                    viewer_key,
                    instance=viewer_key,
                    event_kind="page_turn",
                ),
            )
            viewer_mounted = True
        except use_cases.USER_FACING_ERRORS as exc:
            viewer_error = str(exc)
    elif viewer_source is not None:
        viewer_error = (
            "PDF.js 文字层的已验收缩放范围为 0.5–2.5；"
            "当前使用 PyMuPDF 兼容页面图像。"
        )

    if viewer_mounted:
        with st.expander("兼容页面图像（PDF.js 不可用时使用）"):
            st.image(
                page_view.image_png,
                caption=f"第 {page_view.page.page_number} 页",
                width="stretch",
            )
    else:
        if viewer_error:
            st.warning(f"浏览器文字层不可用：{viewer_error}")
        st.image(
            page_view.image_png,
            caption=f"第 {page_view.page.page_number} 页 · 兼容模式",
            width="stretch",
        )
    if page_view.figure_images:
        with st.expander(
            f"检测到 {len(page_view.figure_images)} 个嵌入图表/图片区域"
        ):
            for figure_index, figure_png in enumerate(
                page_view.figure_images,
                start=1,
            ):
                st.image(
                    figure_png,
                    caption=f"第 {page_view.page.page_number} 页 · 图表 {figure_index}",
                    width="stretch",
                )
                st.download_button(
                    f"下载图表 {figure_index}",
                    data=figure_png,
                    file_name=(
                        f"{document.document.id}-page-"
                        f"{page_view.page.page_number}-figure-{figure_index}.png"
                    ),
                    mime="image/png",
                    key=(
                        f"download_figure_{document.document.id}_"
                        f"{page_view.page.page_number}_{figure_index}"
                    ),
                )

    st.markdown("**当前页提取文本** · 每个文本块右上角都可一键复制")
    if page_view.page.blocks:
        formula_count = sum(
            block.role == "formula"
            for block in page_view.page.blocks
        )
        if formula_count:
            st.caption(
                f"检测到 {formula_count} 个疑似数学公式文字块。"
                "已保留可用换行；可复制后选择“数学”模式解释。"
                "复杂排版可能仍需对照页面图像。"
            )
        with st.expander("按阅读顺序逐块复制", expanded=True):
            for display_index, block in enumerate(page_view.page.blocks, start=1):
                block_label = (
                    f"数学公式候选 · 阅读序号 {display_index} · "
                    f"源块 {block.block_index}"
                    if block.role == "formula"
                    else (
                        f"文本块 · 阅读序号 {display_index} · "
                        f"源块 {block.block_index}"
                    )
                )
                st.caption(block_label)
                st.code(
                    block.text,
                    language=None,
                    wrap_lines=block.role != "formula",
                    height="content",
                )
                if st.button(
                    "选择此公式" if block.role == "formula" else "选择此文本块",
                    key=(
                        f"select_block_{document.document.id}_"
                        f"{page_view.page.page_number}_{block.block_index}"
                    ),
                ):
                    try:
                        selection = use_cases.create_block_selection(
                            document,
                            page_view.page.page_number,
                            block.block_index,
                        )
                        state.set_current_selection_from_reader(
                            selection,
                            document_id=document.document.id,
                        )
                        st.success(
                            f"已选择第 {page_view.page.page_number} 页"
                            f"文本块 {block.block_index}，可直接翻译或解释。"
                        )
                    except use_cases.USER_FACING_ERRORS as exc:
                        st.error(str(exc))
    else:
        st.caption("本页未提取到可复制文本。")

    with st.expander("复制整页文本"):
        st.code(
            page_view.page.text or "（本页未提取到文本）",
            language=None,
            wrap_lines=True,
            height=280,
        )

    query = st.text_input(
        "文档内搜索",
        key=f"pdf_search_query_{document.document.id}",
    )
    if st.button("搜索", key="pdf_search_button"):
        try:
            state.set_search_results(use_cases.search_text(document, query))
        except use_cases.USER_FACING_ERRORS as exc:
            st.error(str(exc))

    matches = state.get_search_results()
    if query.strip() and not matches:
        st.caption("未找到匹配文本。")
    for index, match in enumerate(matches):
        result_column, jump_result_column = st.columns([5, 1])
        with result_column:
            st.caption(
                f"第 {match.page_number} 页 · 块 {match.block_index}："
                f"{match.excerpt}"
            )
        with jump_result_column:
            st.button(
                "前往",
                key=f"search_match_{document.document.id}_{index}",
                on_click=state.set_current_page_number,
                args=(match.page_number,),
            )


def _process_pending_viewer_events(
    document: use_cases.OpenedDocument,
    source: use_cases.PdfViewerSource,
    *,
    viewer_key: str,
) -> None:
    page_turn_event = state.take_pdf_viewer_event(viewer_key, "page_turn")
    if page_turn_event is not None:
        try:
            target_page, sequence = use_cases.validate_pdf_text_layer_page_turn(
                source,
                page_turn_event,
                instance=viewer_key,
                current_page=state.get_current_page_number(),
                page_count=document.document.num_pages,
                last_sequence=state.get_pdf_viewer_sequence(
                    viewer_key,
                    "page_turn",
                ),
            )
            state.accept_pdf_viewer_page_turn(
                viewer_key,
                sequence,
                target_page,
            )
            st.success(f"触控板/滚轮已翻到第 {target_page} 页。")
        except use_cases.USER_FACING_ERRORS as exc:
            st.error(f"滚轮翻页事件已拒绝：{exc}")

    selection_event = state.take_pdf_viewer_event(viewer_key, "selection")
    if selection_event is None:
        return
    try:
        selection, sequence = use_cases.create_pdf_text_layer_selection(
            source,
            document,
            selection_event,
            instance=viewer_key,
            last_sequence=state.get_pdf_viewer_sequence(
                viewer_key,
                "selection",
            ),
        )
        state.accept_pdf_viewer_selection(
            viewer_key,
            sequence,
            selection,
            document_id=document.document.id,
        )
        st.success(
            f"已验证第 {selection.locator['page_number']} 页的 PDF 文字层选择；"
            "可继续使用现有翻译、LaTeX 或解释功能。"
        )
    except use_cases.USER_FACING_ERRORS as exc:
        st.error(f"PDF 选择未通过服务端对账：{exc}")
