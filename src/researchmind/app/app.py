"""ResearchMind Streamlit application composition."""

from functools import partial

import streamlit as st

from researchmind.app import state, use_cases
from researchmind.app.views import (
    render_actions,
    render_code_workspace,
    render_configuration_diagnostics,
    render_conversation,
    render_evidence_basket,
    render_knowledge,
    render_library,
    render_read_only_assistant,
    render_reader,
)

_WORKSPACE_LABELS = {
    "paper": "论文阅读与笔记",
    "code": "代码学习与复现",
    "assistant": "只读研究助手",
    "library": "本地资料库",
}


def main() -> None:
    st.set_page_config(page_title="ResearchMind", page_icon="📚", layout="wide")
    state.initialize_state()
    state.apply_requested_workspace()

    st.title("ResearchMind")
    st.caption("论文理解、代码学习与科研复现，最终沉淀为可追溯知识。")
    render_configuration_diagnostics()
    workspace = st.radio(
        "选择工作区",
        options=list(_WORKSPACE_LABELS),
        format_func=lambda value: _WORKSPACE_LABELS[value],
        horizontal=True,
        key="workspace_navigation",
        label_visibility="collapsed",
    )
    st.divider()

    if workspace == "paper":
        _render_ai_shortcut()
        if (
            state.get_opened_document() is not None
            and state.get_opened_code_project() is not None
        ):
            paper_column, code_column = st.columns(
                [3, 2],
                gap="medium",
                wrap=True,
            )
            with paper_column:
                render_reader()
            with code_column:
                render_code_workspace()
        else:
            render_reader()
        st.divider()
        st.button(
            "关闭 AI 面板" if state.is_ai_panel_open() else "打开 AI 面板",
            key="toggle_ai_panel_button",
            icon=":material/smart_toy:",
            on_click=state.toggle_ai_panel,
        )
        if state.is_ai_panel_open():
            st.subheader("AI 研究面板")
            st.caption(
                "Ctrl+Shift+A 可打开或关闭；在输入框、编辑器和按钮中操作时不会触发。"
            )
            render_actions()
            st.divider()
            render_evidence_basket()
            st.divider()
            render_conversation()
            st.divider()
            render_knowledge()
        else:
            st.caption("AI 面板已收起；按 Ctrl+Shift+A 或点击按钮重新打开。")
    elif workspace == "code":
        render_code_workspace()
    elif workspace == "assistant":
        render_read_only_assistant()
    else:
        render_library()


def _render_ai_shortcut() -> None:
    pending = state.take_pdf_viewer_event(
        state.AI_SHORTCUT_INSTANCE,
        "shortcut",
    )
    if pending is not None:
        try:
            sequence = use_cases.validate_ai_panel_shortcut(
                pending,
                last_sequence=state.get_pdf_viewer_sequence(
                    state.AI_SHORTCUT_INSTANCE,
                    "shortcut",
                ),
            )
            state.accept_ai_panel_shortcut(sequence)
        except use_cases.USER_FACING_ERRORS as exc:
            st.error(f"AI 快捷键事件已拒绝：{exc}")

    try:
        use_cases.mount_ai_panel_shortcut(
            key=state.AI_SHORTCUT_COMPONENT_KEY,
            last_sequence=state.get_pdf_viewer_sequence(
                state.AI_SHORTCUT_INSTANCE,
                "shortcut",
            ),
            on_toggle=partial(
                state.capture_pdf_viewer_event,
                state.AI_SHORTCUT_COMPONENT_KEY,
                instance=state.AI_SHORTCUT_INSTANCE,
                event_kind="shortcut",
            ),
        )
    except use_cases.USER_FACING_ERRORS as exc:
        st.warning(f"AI 快捷键不可用：{exc}")


if __name__ == "__main__":
    main()
