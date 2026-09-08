"""Packaged Streamlit CCv2/pdf.js viewer adopted for ResearchMind V3-G3."""

from __future__ import annotations

from collections.abc import Callable

import streamlit as st

from researchmind.pdf.errors import PdfViewerError
from researchmind.pdf.reader import PdfViewerSource

from .adapter import reconcile_page_turn, reconcile_selection
from .boundary import (
    MAX_VIEWER_PDF_BYTES,
    PageTurn,
    ShortcutToggle,
    make_payload,
    validate_shortcut_toggle,
)

_VIEWER = None
_VIEWER_HTML = """
      <section class="viewer-root" aria-label="ResearchMind PDF text-layer viewer">
        <p class="viewer-status" role="status">等待 PDF。</p>
        <div class="viewer-scroll" tabindex="0" aria-label="可滚动 PDF 页面">
          <div class="page-shell">
            <canvas class="pdf-canvas"></canvas><div class="textLayer"></div>
          </div>
        </div>
        <p>浏览器内选择预览（确认前不会进入 ResearchMind 上下文）：</p>
        <pre class="selection-preview"></pre>
        <button class="selection-submit" type="button" disabled>确认使用当前选择</button>
      </section>
    """

_SHORTCUT = st.components.v2.component(
    "researchmind_pdf_workspace_shortcut",
    html="""
      <span class="shortcut-root" role="status">
        快捷键：Ctrl+Shift+A 打开或关闭 AI 面板
      </span>
    """,
    css="""
      .shortcut-root {
        display: block;
        color: color-mix(in srgb, var(--st-text-color), transparent 30%);
        font-size: .8rem;
        margin-bottom: .25rem;
      }
    """,
    js=r"""
      const activeMounts = new WeakMap();
      function isEditableTarget(event) {
        return event.composedPath().some(candidate =>
          candidate instanceof HTMLElement &&
          (candidate.matches("input, textarea, select, button, [role='textbox'], [role='button'], .CodeMirror, .CodeMirror *, .monaco-editor, .monaco-editor *") ||
           candidate.isContentEditable));
      }
      export default function(component) {
        const {data, parentElement, setTriggerValue} = component;
        activeMounts.get(parentElement)?.();
        const root = parentElement.querySelector(".shortcut-root");
        if (!root) throw new Error("ResearchMind shortcut DOM is incomplete");
        const doc = root.ownerDocument;
        let sequence = data.last_sequence;
        const onKeyDown = event => {
          if (event.isComposing || event.repeat || isEditableTarget(event)) return;
          if (!event.ctrlKey || !event.shiftKey || event.altKey || event.metaKey) return;
          if (event.key.toLowerCase() !== "a") return;
          event.preventDefault();
          sequence += 1;
          setTriggerValue("toggle", {
            version: 1, sequence, shortcut: "Ctrl+Shift+A", source: "keyboard",
          });
        };
        doc.addEventListener("keydown", onKeyDown, true);
        const cleanup = () => {
          doc.removeEventListener("keydown", onKeyDown, true);
          if (activeMounts.get(parentElement) === cleanup) activeMounts.delete(parentElement);
        };
        activeMounts.set(parentElement, cleanup);
        return cleanup;
      }
    """,
)


def mount_pdf_viewer(
    source: PdfViewerSource,
    *,
    page: int,
    page_count: int,
    scale: float,
    key: str,
    on_selection: Callable[[], None],
    on_page_turn: Callable[[], None],
) -> None:
    """Mount the validated local PDF without returning component-owned objects."""

    global _VIEWER

    component_state = st.session_state.get(key, {})
    loaded_revision = (
        component_state.get("loaded_revision", "")
        if isinstance(component_state, dict)
        else getattr(component_state, "loaded_revision", "")
    )
    try:
        payload = make_payload(
            source.content,
            page=page,
            page_count=page_count,
            scale=scale,
            instance=key,
            loaded_revision=loaded_revision,
        )
    except ValueError as exc:
        raise PdfViewerError(str(exc)) from exc
    try:
        if _VIEWER is None:
            _VIEWER = st.components.v2.component(
                "researchmind.pdf_viewer",
                js="index.js",
                css="index.css",
                html=_VIEWER_HTML,
            )
        _VIEWER(
            key=key,
            data=payload,
            default={"loaded_revision": ""},
            on_loaded_revision_change=lambda: None,
            on_submitted_change=on_selection,
            on_page_turn_change=on_page_turn,
            width="stretch",
            height="content",
        )
    except Exception as exc:
        raise PdfViewerError(
            "The local browser PDF viewer could not be mounted."
        ) from exc


def mount_workspace_shortcut(
    *,
    key: str,
    last_sequence: int,
    on_toggle: Callable[[], None],
) -> None:
    """Mount the fixed input-safe AI-panel shortcut."""

    if type(last_sequence) is not int or last_sequence < 0:
        raise PdfViewerError("Shortcut sequence must be a non-negative integer.")
    try:
        _SHORTCUT(
            key=key,
            data={"last_sequence": last_sequence},
            on_toggle_change=on_toggle,
            height="content",
        )
    except Exception as exc:
        raise PdfViewerError(
            "The local AI-panel shortcut could not be mounted."
        ) from exc


def reconcile_shortcut(
    event: object,
    *,
    last_sequence: int,
) -> ShortcutToggle:
    try:
        return validate_shortcut_toggle(event, last_sequence=last_sequence)
    except ValueError as exc:
        raise PdfViewerError(str(exc)) from exc


__all__ = [
    "MAX_VIEWER_PDF_BYTES",
    "PageTurn",
    "PdfViewerSource",
    "ShortcutToggle",
    "mount_pdf_viewer",
    "mount_workspace_shortcut",
    "reconcile_page_turn",
    "reconcile_selection",
    "reconcile_shortcut",
]
