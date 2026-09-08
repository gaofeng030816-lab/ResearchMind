"""Manual G3 PDF workspace experiment; it never imports the formal app."""

from dataclasses import asdict
from hashlib import sha256

import pymupdf
import streamlit as st

from rm_g3_pdf_viewer import MAX_EXPERIMENT_PDF_BYTES, pdf_viewer
from rm_g3_pdf_viewer.boundary import (
    validate_page_turn,
    validate_shortcut_toggle,
)
from rm_g3_pdf_viewer.provenance import build_page_snapshot, verify_selection
from rm_g3_pdf_viewer.workspace_shortcut import workspace_shortcut

VIEWER_KEY = "g3_pdf_viewer"
SHORTCUT_KEY = "g3_workspace_shortcut"
PAGE_KEY = "g3_pdf_page"
SCALE_KEY = "g3_pdf_scale"
REVISION_KEY = "g3_pdf_revision"
LAST_TURN_SEQUENCE_KEY = "g3_last_page_turn_sequence"
LAST_SHORTCUT_SEQUENCE_KEY = "g3_last_shortcut_sequence"
PENDING_TURN_KEY = "g3_pending_page_turn"
PENDING_SHORTCUT_KEY = "g3_pending_shortcut"
LAST_SELECTION_KEY = "g3_last_pdf_selection"
LAST_SELECTION_SEQUENCE_KEY = "g3_last_pdf_selection_sequence"
PENDING_SELECTION_KEY = "g3_pending_pdf_selection"
SELECTION_IDENTITY_KEY = "g3_selection_identity"


def _component_value(component_key: str, field: str):
    value = st.session_state.get(component_key)
    if isinstance(value, dict):
        return value.get(field)
    return getattr(value, field, None)


def receive_selection() -> None:
    st.session_state[PENDING_SELECTION_KEY] = _component_value(VIEWER_KEY, "submitted")


def receive_page_turn() -> None:
    st.session_state[PENDING_TURN_KEY] = _component_value(VIEWER_KEY, "page_turn")


def receive_shortcut() -> None:
    st.session_state[PENDING_SHORTCUT_KEY] = _component_value(SHORTCUT_KEY, "toggle")


@st.cache_data(show_spinner=False)
def inspect_pdf(pdf_bytes: bytes) -> int:
    """Return a trusted page count without retaining an OS path or document handle."""

    if not pdf_bytes.startswith(b"%PDF-"):
        raise ValueError("文件头不是 PDF。")
    if not 0 < len(pdf_bytes) <= MAX_EXPERIMENT_PDF_BYTES:
        raise ValueError("实验 PDF 必须小于或等于 10 MiB。")
    try:
        with pymupdf.open(stream=pdf_bytes, filetype="pdf") as document:
            if document.needs_pass:
                raise ValueError("实验不读取加密 PDF。")
            if document.page_count < 1:
                raise ValueError("PDF 没有可读取页面。")
            return document.page_count
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("PyMuPDF 无法验证此 PDF。") from exc


st.set_page_config(page_title="ResearchMind G3 PDF workspace experiment", layout="wide")

shortcut_error = None
pending_shortcut = st.session_state.pop(PENDING_SHORTCUT_KEY, None)
if pending_shortcut is not None:
    try:
        toggle = validate_shortcut_toggle(
            pending_shortcut,
            last_sequence=st.session_state.get(LAST_SHORTCUT_SEQUENCE_KEY, 0),
        )
        st.session_state[LAST_SHORTCUT_SEQUENCE_KEY] = toggle.sequence
        st.session_state["g3_ai_open"] = not st.session_state.get("g3_ai_open", False)
    except ValueError as exc:
        shortcut_error = str(exc)

workspace_shortcut(
    key=SHORTCUT_KEY,
    last_sequence=st.session_state.get(LAST_SHORTCUT_SEQUENCE_KEY, 0),
    on_toggle=receive_shortcut,
)

st.title("G3 PDF 工作区实验")
st.warning("隔离实验：不调用 AI，不写资料库、Zotero 或 Obsidian，不代表正式组件已采用。")
if shortcut_error:
    st.error(f"快捷键事件被拒绝：{shortcut_error}")
if st.session_state.get("g3_ai_open", False):
    with st.container(border=True):
        st.subheader("AI 面板（无网络占位）")
        st.caption("Ctrl+Shift+A 可关闭。输入框获得焦点时快捷键不会触发。")
        st.text_input("实验 AI 问题", placeholder="这里只验证焦点归属，不会发送内容")

upload = st.file_uploader(
    "点击选择或拖入不敏感的测试 PDF",
    type=("pdf",),
    max_upload_size=MAX_EXPERIMENT_PDF_BYTES,
)
if upload is None:
    st.info("等待 PDF。文件仅通过本机 Streamlit 会话传给浏览器 PDF.js。")
    st.stop()

pdf_bytes = upload.getvalue()
try:
    page_count = inspect_pdf(pdf_bytes)
except ValueError as exc:
    st.error(str(exc))
    st.stop()

revision = "sha256:" + sha256(pdf_bytes).hexdigest()
if st.session_state.get(REVISION_KEY) != revision:
    st.session_state[REVISION_KEY] = revision
    st.session_state[PAGE_KEY] = 1
    st.session_state[LAST_TURN_SEQUENCE_KEY] = 0
    st.session_state[LAST_SELECTION_SEQUENCE_KEY] = 0
    st.session_state.pop(PENDING_TURN_KEY, None)
    st.session_state.pop(PENDING_SELECTION_KEY, None)
    st.session_state.pop(LAST_SELECTION_KEY, None)
    st.session_state.pop(SELECTION_IDENTITY_KEY, None)

turn_error = None
pending_turn = st.session_state.pop(PENDING_TURN_KEY, None)
if pending_turn is not None:
    try:
        turn = validate_page_turn(
            pending_turn,
            revision=revision,
            instance=VIEWER_KEY,
            current_page=st.session_state[PAGE_KEY],
            page_count=page_count,
            last_sequence=st.session_state.get(LAST_TURN_SEQUENCE_KEY, 0),
        )
        st.session_state[LAST_TURN_SEQUENCE_KEY] = turn.sequence
        st.session_state[PAGE_KEY] = turn.target_page
        st.session_state.pop(LAST_SELECTION_KEY, None)
    except ValueError as exc:
        turn_error = str(exc)

selection_error = None
pending_selection = st.session_state.pop(PENDING_SELECTION_KEY, None)
if pending_selection is not None:
    try:
        snapshot = build_page_snapshot(
            pdf_bytes,
            page=st.session_state[PAGE_KEY],
            instance=VIEWER_KEY,
        )
        verified = verify_selection(
            pending_selection,
            snapshot,
            last_sequence=st.session_state.get(LAST_SELECTION_SEQUENCE_KEY, 0),
        )
        st.session_state[LAST_SELECTION_SEQUENCE_KEY] = verified.sequence
        st.session_state[LAST_SELECTION_KEY] = asdict(verified)
    except ValueError as exc:
        st.session_state.pop(LAST_SELECTION_KEY, None)
        selection_error = str(exc)

control_left, control_right = st.columns(2)
with control_left:
    page = st.number_input(
        "页码",
        min_value=1,
        max_value=page_count,
        step=1,
        key=PAGE_KEY,
    )
with control_right:
    scale = st.slider(
        "缩放",
        min_value=0.5,
        max_value=2.5,
        value=1.25,
        step=0.25,
        key=SCALE_KEY,
    )
layout_mode = st.segmented_control(
    "工作区布局",
    options=("仅论文", "论文 + 代码"),
    default="仅论文",
    key="g3_workspace_layout",
)
if turn_error:
    st.error(f"滚轮翻页事件被拒绝：{turn_error}")
if selection_error:
    st.error(f"PDF 选择未通过服务器对账：{selection_error}")

selection_identity = (revision, int(page))
if st.session_state.get(SELECTION_IDENTITY_KEY) != selection_identity:
    st.session_state[SELECTION_IDENTITY_KEY] = selection_identity
    st.session_state.pop(LAST_SELECTION_KEY, None)


def mount_viewer() -> None:
    try:
        pdf_viewer(
            pdf_bytes,
            page=int(page),
            page_count=page_count,
            scale=float(scale),
            key=VIEWER_KEY,
            on_selection=receive_selection,
            on_page_turn=receive_page_turn,
        )
    except ValueError as exc:
        st.error(str(exc))


if layout_mode == "论文 + 代码":
    paper_column, code_column = st.columns([3, 2], gap="medium", wrap=True)
    with paper_column:
        st.subheader("论文阅读区")
        mount_viewer()
    with code_column:
        st.subheader("代码阅读区（静态占位）")
        st.caption("本实验不读取项目、不执行代码，只验证论文与代码并列布局。")
        st.code("def explain(value):\n    return value", language="python")
        st.text_area("代码阅读备注", placeholder="输入时 Ctrl+Shift+A 不应触发")
else:
    with st.container(border=True):
        st.subheader("全宽论文阅读区")
        mount_viewer()

selection = st.session_state.get(LAST_SELECTION_KEY)
if selection:
    st.subheader("已通过 PyMuPDF 文字与几何对账的实验选择")
    st.caption(f"实验 locator_status：{selection['locator_status']}")
    st.caption(
        "实验 provenance："
        f"ranges={len(selection['client_ranges'])}, "
        f"trusted_line_boxes={len(selection['trusted_bboxes'])}"
    )
    st.json(selection)
    st.code(repr(selection), language=None)
