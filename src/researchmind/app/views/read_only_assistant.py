"""Streamlit view for the bounded, user-stepped T5-A assistant."""

import streamlit as st

from researchmind.app import state, use_cases
from researchmind.models import (
    AssistantToolName,
    ReadOnlyAssistantSession,
)


_TOOL_LABELS: dict[AssistantToolName, str] = {
    "inspect_paper_context": "查看当前论文上下文",
    "inspect_code_context": "查看当前代码上下文",
    "inspect_evidence_links": "查看当前论文 ↔ 代码证据链接",
}


def render_read_only_assistant() -> None:
    """Render the T5-A read-only assistant with one click per model step."""

    st.subheader("只读研究助手（T5-A）")
    st.caption(
        "这是当前会话内的受限助手：只可读取下方三个固定来源，"
        "不能访问 Shell、任意文件、网络搜索、代码执行、测试、依赖安装"
        "或 Obsidian 写入。每次模型调用都必须由你点击开始或继续。"
    )
    available_tools = use_cases.get_available_assistant_tools(
        document=state.get_opened_document(),
        reading_selection=state.get_current_selection(),
        code_project=state.get_opened_code_project(),
        code_selection=state.get_current_code_selection(),
        evidence_links=state.get_evidence_links(),
    )
    _render_tool_availability(available_tools)

    question = st.text_area(
        "研究问题",
        key="read_only_assistant_question",
        height=100,
        placeholder="例如：当前论文证据与代码实现之间有哪些可验证的对应关系？",
    )
    session = state.get_read_only_assistant_session()
    if session is None or session.status in {"completed", "stopped"}:
        label = "开始只读助手" if session is None else "开始新的只读助手"
        if st.button(
            label,
            key="start_read_only_assistant_button",
            type="primary",
        ):
            try:
                started = use_cases.start_read_only_assistant(
                    question,
                    document=state.get_opened_document(),
                    reading_selection=state.get_current_selection(),
                    conversation=state.get_current_conversation(),
                    code_project=state.get_opened_code_project(),
                    code_selection=state.get_current_code_selection(),
                    evidence_links=state.get_evidence_links(),
                )
                state.set_read_only_assistant_session(started)
                st.rerun()
            except use_cases.USER_FACING_ERRORS as exc:
                st.error(str(exc))

    session = state.get_read_only_assistant_session()
    if session is None:
        st.info("填写问题并点击开始后，模型才会进行第一次决策。")
        return

    _render_session_summary(session)
    _render_tool_results(session)
    _render_audit(session)

    if session.status == "awaiting_user":
        st.info(
            "模型已请求并读取一个本地来源。请检查“待发送工具结果”；"
            "只有点击继续后，这份结果才会发送给配置的 LLM。"
        )
        continue_column, stop_column = st.columns(2)
        with continue_column:
            if st.button(
                "确认并继续一步",
                key="continue_read_only_assistant_button",
                type="primary",
                width="stretch",
            ):
                try:
                    continued = use_cases.continue_read_only_assistant(
                        session,
                        document=state.get_opened_document(),
                        reading_selection=state.get_current_selection(),
                        conversation=state.get_current_conversation(),
                        code_project=state.get_opened_code_project(),
                        code_selection=state.get_current_code_selection(),
                        evidence_links=state.get_evidence_links(),
                    )
                    state.set_read_only_assistant_session(continued)
                    st.rerun()
                except use_cases.USER_FACING_ERRORS as exc:
                    st.error(str(exc))
        with stop_column:
            if st.button(
                "停止",
                key="stop_read_only_assistant_button",
                width="stretch",
            ):
                state.set_read_only_assistant_session(
                    use_cases.stop_read_only_assistant(session)
                )
                st.rerun()
    elif session.status == "completed":
        st.markdown("**只读助手结论**")
        st.markdown(session.final_answer or "")
        st.caption(
            "结论只显示在当前会话中，不会自动修改代码、运行命令或写入 Vault。"
        )
    elif session.status == "stopped":
        detail = session.last_error or "会话已按权限或预算规则停止。"
        st.warning(f"只读助手已停止：{detail}")


def _render_tool_availability(
    available_tools: tuple[AssistantToolName, ...],
) -> None:
    st.markdown("**固定只读工具**")
    for tool_name, label in _TOOL_LABELS.items():
        status = "可用" if tool_name in available_tools else "当前无来源"
        st.caption(f"- {label}：{status}")


def _render_session_summary(session: ReadOnlyAssistantSession) -> None:
    st.caption(
        f"状态：{session.status} · 工具调用 "
        f"{session.tool_call_count}/{use_cases.MAX_ASSISTANT_TOOL_CALLS} · "
        f"模型调用 {session.llm_call_count}/{use_cases.MAX_ASSISTANT_LLM_CALLS}"
    )


def _render_tool_results(session: ReadOnlyAssistantSession) -> None:
    for index, result in enumerate(session.tool_results, start=1):
        is_pending = (
            session.status == "awaiting_user"
            and index == len(session.tool_results)
        )
        delivery_status = "待发送" if is_pending else "已发送"
        with st.expander(
            f"{delivery_status}工具结果 {index} · {_TOOL_LABELS[result.tool_name]}",
            expanded=True,
        ):
            st.caption(
                f"状态：{result.status} · 来源：{result.source_summary} · "
                f"{result.character_count:,} 字符"
            )
            st.code(result.content, language=None)


def _render_audit(session: ReadOnlyAssistantSession) -> None:
    with st.expander("会话审计（仅元数据）", expanded=False):
        if not session.audit_log:
            st.caption("尚无步骤。")
            return
        for event in session.audit_log:
            executed = event.executed_tool or "无"
            stop_reason = event.stop_reason or "无"
            st.text(
                f"步骤 {event.step_number} · 请求 {event.requested_action} · "
                f"执行 {executed} · 状态 {event.status}"
            )
            st.caption(
                f"请求 {event.request_character_count:,} 字符 · "
                f"响应 {event.response_character_count:,} 字符 · "
                f"工具输出 {event.tool_output_character_count:,} 字符 · "
                f"停止原因 {stop_reason}"
            )
