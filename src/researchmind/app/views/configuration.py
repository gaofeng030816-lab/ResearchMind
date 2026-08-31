"""Streamlit entry point for explicit, non-network configuration checks."""

import streamlit as st

from researchmind.app import use_cases


def render_configuration_diagnostics() -> None:
    """Let the user explicitly inspect startup configuration without secrets."""

    with st.expander("启动与配置检查", expanded=False):
        st.caption(
            "本地检查 Python、LLM 配置格式和 Vault 目标；不会联网、"
            "不会显示 API Key，也不会创建目录。"
        )
        if not st.button(
            "运行本地配置检查",
            key="run_configuration_diagnostics",
        ):
            return
        report = use_cases.get_configuration_report()
        for check in report.checks:
            rendered = f"**{check.label}**：{check.message}"
            if check.status == "ok":
                st.success(rendered)
            elif check.status == "warning":
                st.warning(rendered)
            else:
                st.error(rendered)
