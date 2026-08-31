"""ResearchMind Streamlit application composition."""

import streamlit as st

from researchmind.app import state
from researchmind.app.views import (
    render_actions,
    render_code_workspace,
    render_configuration_diagnostics,
    render_conversation,
    render_knowledge,
    render_read_only_assistant,
    render_reader,
)

_WORKSPACE_LABELS = {
    "paper": "论文阅读与笔记",
    "code": "代码学习与复现",
    "assistant": "只读研究助手",
}


def main() -> None:
    st.set_page_config(page_title="ResearchMind", page_icon="📚", layout="wide")
    state.initialize_state()

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
        render_reader()
        st.divider()
        render_actions()
        st.divider()
        render_conversation()
        st.divider()
        render_knowledge()
    elif workspace == "code":
        render_code_workspace()
    else:
        render_read_only_assistant()


if __name__ == "__main__":
    main()
