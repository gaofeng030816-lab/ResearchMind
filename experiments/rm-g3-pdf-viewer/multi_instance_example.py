"""Two-viewer G3 isolation harness; it never imports the formal app."""

from dataclasses import asdict
from functools import partial
from hashlib import sha256

import pymupdf
import streamlit as st

from rm_g3_pdf_viewer import MAX_EXPERIMENT_PDF_BYTES, pdf_viewer
from rm_g3_pdf_viewer.provenance import build_page_snapshot, verify_selection

VIEWER_KEYS = ("g3_viewer_a", "g3_viewer_b")


def _component_value(component_key: str, field: str):
    value = st.session_state.get(component_key)
    if isinstance(value, dict):
        return value.get(field)
    return getattr(value, field, None)


def _receive_selection(viewer_key: str) -> None:
    st.session_state[f"pending:{viewer_key}"] = _component_value(viewer_key, "submitted")


def _ignore_page_turn() -> None:
    """This harness validates instance isolation, not navigation."""


@st.cache_data(show_spinner=False)
def _inspect_pdf(pdf_bytes: bytes) -> int:
    if not pdf_bytes.startswith(b"%PDF-") or not 0 < len(pdf_bytes) <= MAX_EXPERIMENT_PDF_BYTES:
        raise ValueError("需要不超过 10 MiB 的数字 PDF。")
    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as document:
        if document.needs_pass or document.page_count < 1:
            raise ValueError("加密或空 PDF 不属于本实验。")
        return document.page_count


st.set_page_config(page_title="ResearchMind G3 multi-instance experiment", layout="wide")
st.title("G3 双 PDF 实例隔离实验")
st.warning("隔离实验：只验证两个 CCv2 挂载点，不调用 AI，不写正式资料库。")
upload = st.file_uploader("选择不敏感的测试 PDF", type=("pdf",), max_upload_size=MAX_EXPERIMENT_PDF_BYTES)
if upload is None:
    st.stop()

pdf_bytes = upload.getvalue()
try:
    page_count = _inspect_pdf(pdf_bytes)
except (ValueError, pymupdf.FileDataError) as exc:
    st.error(str(exc))
    st.stop()

revision = "sha256:" + sha256(pdf_bytes).hexdigest()
if st.session_state.get("multi_revision") != revision:
    st.session_state["multi_revision"] = revision
    for viewer_key in VIEWER_KEYS:
        st.session_state.pop(f"pending:{viewer_key}", None)
        st.session_state.pop(f"accepted:{viewer_key}", None)
        st.session_state[f"sequence:{viewer_key}"] = 0

for viewer_key in VIEWER_KEYS:
    pending = st.session_state.pop(f"pending:{viewer_key}", None)
    if pending is None:
        continue
    try:
        snapshot = build_page_snapshot(pdf_bytes, page=1, instance=viewer_key)
        verified = verify_selection(
            pending,
            snapshot,
            last_sequence=st.session_state.get(f"sequence:{viewer_key}", 0),
        )
        st.session_state[f"sequence:{viewer_key}"] = verified.sequence
        st.session_state[f"accepted:{viewer_key}"] = asdict(verified)
    except ValueError as exc:
        st.error(f"{viewer_key} rejected: {exc}")

columns = st.columns(2)
for column, viewer_key in zip(columns, VIEWER_KEYS, strict=True):
    with column:
        st.subheader(viewer_key)
        accepted = st.session_state.get(f"accepted:{viewer_key}")
        if accepted:
            st.success(f"{viewer_key} accepted: {accepted['locator_status']}")
        pdf_viewer(
            pdf_bytes,
            page=1,
            page_count=page_count,
            scale=1.0,
            key=viewer_key,
            on_selection=partial(_receive_selection, viewer_key),
            on_page_turn=_ignore_page_turn,
        )
