"""Isolated G3 packaged CCv2/pdf.js experiment; not a production adapter."""

from collections.abc import Callable

import streamlit as st

from .boundary import MAX_EXPERIMENT_PDF_BYTES, make_payload

_VIEWER = st.components.v2.component(
    "rm-g3-pdf-viewer.rm_g3_pdf_viewer",
    js="index.js",
    css="index.css",
    html="""
      <section class="viewer-root" aria-label="G3 PDF text layer experiment">
        <p class="viewer-status" role="status">Waiting for a PDF.</p>
        <div class="viewer-scroll" tabindex="0" aria-label="Scrollable PDF page">
          <div class="page-shell">
            <canvas class="pdf-canvas"></canvas><div class="textLayer"></div>
          </div>
        </div>
        <p>Browser selection preview (not submitted):</p>
        <pre class="selection-preview"></pre>
        <button class="selection-submit" type="button" disabled>Submit current selection</button>
      </section>
    """,
)


def pdf_viewer(
    pdf_bytes: bytes,
    *,
    page: int,
    page_count: int,
    scale: float,
    key: str,
    on_selection: Callable[[], None],
    on_page_turn: Callable[[], None],
):
    """Mount one bounded in-memory PDF revision in the experimental viewer."""
    component_state = st.session_state.get(key, {})
    if isinstance(component_state, dict):
        loaded_revision = component_state.get("loaded_revision", "")
    else:
        loaded_revision = getattr(component_state, "loaded_revision", "")
    return _VIEWER(
        key=key,
        data=make_payload(
            pdf_bytes,
            page=page,
            page_count=page_count,
            scale=scale,
            instance=key,
            loaded_revision=loaded_revision,
        ),
        default={"loaded_revision": ""},
        on_loaded_revision_change=lambda: None,
        on_submitted_change=on_selection,
        on_page_turn_change=on_page_turn,
        width="stretch",
        height="content",
    )
