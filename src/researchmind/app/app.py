"""ResearchMind Streamlit application composition."""

import streamlit as st

from researchmind.app import state
from researchmind.app.views import (
    render_actions,
    render_conversation,
    render_knowledge,
    render_reader,
)


def main() -> None:
    st.set_page_config(page_title="ResearchMind", page_icon="📚", layout="wide")
    state.initialize_state()

    st.title("ResearchMind")
    st.caption("从本地论文阅读，到可追溯的 Obsidian 知识笔记。")

    render_reader()
    st.divider()
    render_actions()
    st.divider()
    render_conversation()
    st.divider()
    render_knowledge()


if __name__ == "__main__":
    main()
