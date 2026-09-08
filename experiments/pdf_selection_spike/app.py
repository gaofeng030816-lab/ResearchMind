"""Run separately with streamlit; never imported by the ResearchMind application."""

import streamlit as st

from component import mount
from fixtures import CASES
from spike_state import COMPONENT_KEY, configure, receive_selection

st.set_page_config(page_title="ResearchMind G3 selection experiment", layout="wide")
st.title("G3 划词事件实验")
st.warning("仅合成文字 / 非 PDF 阅读器。无 AI、Zotero、资料库或笔记写入。")
case = st.selectbox("合成样本", tuple(CASES), key="g3_case")
page = st.selectbox("实验页码", (1, 2), key="g3_page")
generation = st.number_input("重挂载代数（改动可使旧事件失效）", min_value=0, max_value=1000, step=1)
st.button("仅重新运行（保留已验证选择）")
state = configure(case, page, generation)
st.caption("鼠标选择下方文字 → 查看预览 → 点击提交。Ctrl+C 使用浏览器原生复制。")
mount(state, key=COMPONENT_KEY, on_submit=receive_selection)
st.subheader("服务端校验结果")
if state.error:
    st.error(state.error)
elif state.selection:
    st.success(f"已验证选择，序号 {state.last_sequence}，页码 {state.selection.page}")
    st.code(state.selection.text, language=None)
    st.json({"revision": state.selection.revision, "ranges": state.selection.ranges,
             "span_boxes": state.selection.span_boxes})
else:
    st.info("尚无已验证选择。切换样本、页码或重挂载代数会清空旧选择。")
