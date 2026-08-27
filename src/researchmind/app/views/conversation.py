"""Streamlit conversation view for messages and grounded follow-ups."""

import streamlit as st

from researchmind.app import state, use_cases


_TASK_LABELS = {
    "translate": "翻译",
    "explain:concept": "概念解释",
    "explain:math": "数学解释",
    "explain:algorithm": "算法解释",
    "explain:contextual": "上下文解释",
    "followup": "追问",
}


def render_conversation() -> None:
    """Render in-memory messages, follow-up input, and capture entry point."""

    st.subheader("3. 研究对话")
    document = state.get_opened_document()
    conversation = state.get_current_conversation()
    if document is None or conversation is None:
        st.info("打开 PDF 后开始围绕当前论文对话。")
        return

    messages = state.get_messages()
    if not messages:
        st.caption("翻译、解释和追问会显示在这里。")
    for message in messages:
        with st.chat_message(message.role):
            st.caption(_TASK_LABELS.get(message.task, message.task))
            st.markdown(message.content)

    selection = state.get_current_selection()
    if selection is not None:
        question = st.text_input(
            "继续追问",
            key=f"followup_question_{document.document.id}",
            placeholder="围绕当前选择和已有对话继续提问。",
        )
        st.caption(
            "隐私提示：追问会发送当前问题、最小论文上下文和预算内的最近对话。"
        )
        if st.button("发送追问", key="ask_followup_button"):
            try:
                response = use_cases.ask_followup(
                    question,
                    document=document,
                    selection=selection,
                    conversation=conversation,
                )
                state.append_exchange(question, "followup", response)
                st.rerun()
            except use_cases.USER_FACING_ERRORS as exc:
                st.error(str(exc))

    if messages and st.button(
        "沉淀为知识",
        key="open_knowledge_panel_button",
        type="primary",
    ):
        state.set_knowledge_panel_open(True)
