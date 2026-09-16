"""Streamlit selection, translation, and explanation actions."""

import streamlit as st

from researchmind.app import state, use_cases
from researchmind.app.views.context_evidence import render_context_evidence
from researchmind.models import (
    FormulaRecognitionCandidate,
    FormulaRegion,
    Message,
    NoteDraft,
    ReadingSelection,
)
from researchmind.pdf import OpenedDocument


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

    _render_formula_card(document)

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

    _render_translation_card(selection, document)

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
    latex_column, explanation_column = st.columns(2)
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


def _render_formula_card(document: OpenedDocument) -> None:
    """Render the explicit, one-crop G5 formula workflow."""

    page_number = state.get_current_page_number()
    with st.container(border=True):
        st.markdown("**公式识别（单公式）**")
        st.caption(
            "扫描和裁剪始终在本机完成。只有在预览具体裁剪并勾选本次同意后，"
            "该单张 PNG 才会发送给已配置的识别服务。"
        )
        if st.button(
            "扫描当前页公式",
            key=f"detect_formula_regions_{document.document.id}_{page_number}",
            icon=":material/function:",
        ):
            try:
                regions = use_cases.detect_formula_regions(document, page_number)
                state.set_formula_regions(regions)
                if regions:
                    st.success(f"当前页发现 {len(regions)} 个候选区域。")
                else:
                    st.info("当前页未发现可靠的公式区域；不会虚构候选。")
            except use_cases.USER_FACING_ERRORS as exc:
                st.error(str(exc))

        regions = state.get_formula_regions()
        if not regions:
            return
        selected_region = st.selectbox(
            "公式区域",
            options=regions,
            format_func=_formula_region_label,
            key=f"formula_region_select_{document.document.id}_{page_number}",
        )
        if not isinstance(selected_region, FormulaRegion):
            st.error("公式区域选择无效，请重新扫描当前页。")
            return
        current_region = state.get_current_formula_region()
        if current_region is None or current_region.id != selected_region.id:
            try:
                state.set_current_formula_region(selected_region)
            except use_cases.USER_FACING_ERRORS as exc:
                st.error(str(exc))
                return

        if selected_region.source_text:
            st.caption(
                "本地文字层线索（可能不完整，不会随识别请求发送）："
                f"{selected_region.source_text[:180]}"
            )
        if st.button(
            "生成并检查公式裁剪",
            key=f"prepare_formula_crop_{selected_region.id}",
            icon=":material/crop:",
        ):
            try:
                state.set_current_formula_crop(
                    use_cases.prepare_formula_crop(document, selected_region)
                )
            except use_cases.USER_FACING_ERRORS as exc:
                st.error(str(exc))

        crop = state.get_current_formula_crop()
        if crop is None or crop.region.id != selected_region.id:
            return
        st.image(
            crop.png_bytes,
            caption=(
                f"第 {selected_region.page_number} 页 · "
                f"{crop.width_px}×{crop.height_px} px · {len(crop.png_bytes)} bytes"
            ),
            width="content",
            output_format="PNG",
        )
        try:
            preview = use_cases.preview_formula_recognition(crop)
        except use_cases.USER_FACING_ERRORS as exc:
            st.warning(f"识别器尚不可用：{exc}")
            return
        st.caption(
            f"本次固定裁剪 SHA-256：{preview.crop_sha256}。"
            f"识别器：{preview.recognizer} / {preview.model_revision}。"
            "不会发送 PDF 路径、整篇 PDF、正文、对话或笔记。"
        )
        consent_key = f"formula_transfer_consent_{preview.crop_sha256}"
        confirmed = st.checkbox(
            "我确认仅将上方这张公式裁剪发送到外部识别服务",
            key=consent_key,
        )
        if st.button(
            "识别这一个公式",
            key=f"recognize_formula_{preview.crop_sha256}",
            type="primary",
            icon=":material/document_scanner:",
            disabled=preview.will_leave_device and not confirmed,
        ):
            try:
                state.set_current_formula_candidate(
                    use_cases.recognize_formula_crop(
                        crop,
                        confirm_external_transfer=confirmed,
                    )
                )
            except use_cases.USER_FACING_ERRORS as exc:
                st.error(str(exc))

        candidate = state.get_current_formula_candidate()
        if candidate is None or candidate.crop_sha256 != crop.sha256:
            return
        _render_formula_candidate(candidate, document)


def _render_formula_candidate(
    candidate: FormulaRecognitionCandidate,
    document: OpenedDocument,
) -> None:
    if candidate.status == "unreadable" or candidate.latex_candidate is None:
        st.warning("识别器认为该裁剪不可可靠读取；不会生成或保存 LaTeX。")
        return
    edited_latex = st.text_area(
        "检查并编辑 LaTeX（接受前不会渲染或保存）",
        value=candidate.accepted_latex or candidate.latex_candidate,
        key=f"formula_latex_editor_{candidate.id}",
        height=120,
        disabled=candidate.accepted_latex is not None,
    )
    if candidate.accepted_latex is None:
        if st.button(
            "接受当前 LaTeX",
            key=f"accept_formula_latex_{candidate.id}",
            icon=":material/check_circle:",
        ):
            try:
                candidate = use_cases.accept_formula_candidate(
                    candidate,
                    edited_latex,
                    document,
                )
                state.set_current_formula_candidate(candidate)
                st.success("LaTeX 已通过安全校验并由你接受。")
            except use_cases.USER_FACING_ERRORS as exc:
                st.error(str(exc))
    if candidate.accepted_latex is None:
        return

    st.latex(candidate.accepted_latex)
    library_ready = use_cases.is_library_configured()
    if not library_ready:
        st.caption("配置 RESEARCHMIND_DATA_DIR 后可将已接受公式加入持久化证据篮。")
    if st.button(
        "加入公式到证据篮",
        key=f"add_formula_evidence_{candidate.id}",
        icon=":material/note_add:",
        disabled=not library_ready,
    ):
        _add_formula_evidence(candidate, document)


def _formula_region_label(region: FormulaRegion) -> str:
    x0, y0, x1, y1 = region.bbox
    source = "文字层" if region.source_kind == "digital_text" else "嵌入图像"
    return (
        f"第 {region.page_number} 页 · {source} · "
        f"bbox {x0:.1f}, {y0:.1f}, {x1:.1f}, {y1:.1f} · "
        f"置信度 {region.detector_confidence:.2f}"
    )


def _render_translation_card(
    selection: ReadingSelection,
    document: OpenedDocument,
) -> None:
    """Render exact transfer scope and explicit evidence-capture actions."""

    try:
        preview = use_cases.preview_selection_translation(selection)
    except use_cases.USER_FACING_ERRORS as exc:
        st.error(str(exc))
        return

    with st.container(border=True):
        st.markdown("**划词翻译**")
        st.text_area(
            "本次将发送的所选原文",
            value=preview.source_text,
            key=f"translation_transfer_text_{preview.selection_id}",
            height=110,
            disabled=True,
        )
        st.caption(
            f"目标语言：{preview.target_language}。"
            "只有上方原文与目标语言会在你点击后发送；"
            "打开卡片、选择文字或加入证据篮都不会调用翻译服务。"
        )
        if st.button(
            "翻译所选文本",
            key="translate_selection_button",
            type="primary",
        ):
            try:
                message = use_cases.translate_selection(selection)
                state.append_message(
                    use_cases.bind_translation_to_selection(message, selection)
                )
                st.success("翻译已加入当前对话；是否加入笔记仍由你决定。")
            except use_cases.USER_FACING_ERRORS as exc:
                st.error(str(exc))

        translation = _latest_translation(preview.selection_id)
        library_ready = use_cases.is_library_configured()
        if not library_ready:
            st.caption(
                "配置 RESEARCHMIND_DATA_DIR 后，才可把明确选择的内容加入持久化证据篮。"
            )
        with st.container(horizontal=True):
            if st.button(
                "加入原文到证据篮",
                key="add_selection_evidence_button",
                disabled=not library_ready,
            ):
                _add_selection_evidence(selection, document)
            if st.button(
                "加入译文到证据篮",
                key="add_translation_evidence_button",
                disabled=not library_ready or translation is None,
            ):
                assert translation is not None
                _add_translation_evidence(
                    selection,
                    translation,
                    document,
                )


def _latest_translation(selection_id: str) -> Message | None:
    return next(
        (
            message
            for message in reversed(state.get_messages())
            if message.role == "assistant"
            and message.task == "translate"
            and message.selection_id == selection_id
        ),
        None,
    )


def _ensure_note_draft(document: OpenedDocument) -> NoteDraft:
    draft = state.get_current_note_draft()
    if draft is None:
        existing = use_cases.list_paper_note_drafts(
            document,
            library_entry=state.get_opened_paper_library_entry(),
        )
        if len(existing) > 1:
            raise ValueError(
                "这篇论文已有多个草稿。请先在下方 Markdown 草稿区选择一个。"
            )
        draft = (
            existing[0]
            if existing
            else use_cases.create_paper_note_draft(
                document,
                library_entry=state.get_opened_paper_library_entry(),
            )
        )
        state.set_current_note_draft(draft)
    return draft


def _add_selection_evidence(
    selection: ReadingSelection,
    document: OpenedDocument,
) -> None:
    try:
        draft, _snapshot = use_cases.capture_reading_selection_evidence(
            _ensure_note_draft(document),
            selection,
            document,
            library_entry=state.get_opened_paper_library_entry(),
        )
        state.set_current_note_draft(draft)
        st.success("原文已加入证据篮。")
    except use_cases.USER_FACING_ERRORS as exc:
        st.error(str(exc))


def _add_translation_evidence(
    selection: ReadingSelection,
    translation: Message,
    document: OpenedDocument,
) -> None:
    try:
        draft, _snapshot = use_cases.capture_translation_evidence(
            _ensure_note_draft(document),
            selection,
            translation,
            document,
            library_entry=state.get_opened_paper_library_entry(),
        )
        state.set_current_note_draft(draft)
        st.success("译文已加入证据篮。")
    except use_cases.USER_FACING_ERRORS as exc:
        st.error(str(exc))


def _add_formula_evidence(
    candidate: FormulaRecognitionCandidate,
    document: OpenedDocument,
) -> None:
    try:
        draft, _snapshot = use_cases.capture_formula_evidence(
            _ensure_note_draft(document),
            candidate,
            document,
            library_entry=state.get_opened_paper_library_entry(),
        )
        state.set_current_note_draft(draft)
        st.success("已接受的公式 LaTeX 已加入证据篮。")
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
