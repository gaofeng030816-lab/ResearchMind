"""Shared Streamlit renderer for read-only LLM context evidence."""

import streamlit as st

from researchmind.app.use_cases import ContextEvidencePreview


def render_context_evidence(
    preview: ContextEvidencePreview,
    *,
    action_label: str,
) -> None:
    """Show what one ResearchContext-backed call will send."""

    with st.expander(f"{action_label}上下文证据（发送前预览）"):
        st.caption(
            "打开预览不会发起网络请求；只有点击操作按钮后，以下数据才会发送到"
            "配置的 LLM 服务。"
        )
        st.text(f"文档：{preview.document_title or '（未提供）'}")
        st.text(f"作者：{preview.author or '（未提供）'}")
        page_label = (
            str(preview.page_number)
            if preview.page_number is not None
            else "未定位"
        )
        st.text(f"页码：{page_label}")
        st.text(f"章节：{preview.section_heading or '（未识别）'}")
        st.text(f"图表说明：{preview.related_caption or '（未识别）'}")
        st.text(f"预算内历史消息：{preview.history_message_count} 条")
        st.caption(
            f"请求估算：约 {preview.request_character_count:,} 字符 / "
            f"{preview.approximate_request_tokens:,} tokens。"
            "采用 4 字符/token 的确定性近似，实际计费以服务商为准。"
        )

        st.markdown("**当前问题**")
        st.code(preview.user_question or "（未提供）", language=None)
        st.markdown("**选中文本**")
        st.code(preview.selected_text, language=None)
        st.markdown("**周边文本**")
        st.code(preview.surrounding_text or "（无可用周边文本）", language=None)
