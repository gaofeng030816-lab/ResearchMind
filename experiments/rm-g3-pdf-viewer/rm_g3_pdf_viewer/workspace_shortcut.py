"""Isolated CCv2 keyboard listener for the G3 workspace experiment."""

from collections.abc import Callable

import streamlit as st

_HTML = """
<span class="shortcut-root" role="status">
  实验快捷键：Ctrl+Shift+A 打开或关闭 AI 占位面板
</span>
"""

_CSS = """
.shortcut-root {
  display: block;
  color: color-mix(in srgb, var(--st-text-color), transparent 30%);
  font-size: .8rem;
  margin-bottom: .25rem;
}
"""

_JS = r"""
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
  if (!root) throw new Error("G3 shortcut DOM is incomplete");
  const doc = root.ownerDocument;
  let sequence = data.last_sequence;

  const onKeyDown = event => {
    if (event.isComposing || event.repeat || isEditableTarget(event)) return;
    if (!event.ctrlKey || !event.shiftKey || event.altKey || event.metaKey) return;
    if (event.key.toLowerCase() !== "a") return;
    event.preventDefault();
    sequence += 1;
    setTriggerValue("toggle", {
      version: 1,
      sequence,
      shortcut: "Ctrl+Shift+A",
      source: "keyboard",
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
"""

_SHORTCUT = st.components.v2.component(
    "rm_g3_workspace_shortcut",
    html=_HTML,
    css=_CSS,
    js=_JS,
)


def workspace_shortcut(
    *,
    key: str,
    last_sequence: int,
    on_toggle: Callable[[], None],
):
    """Mount the fixed shortcut without intercepting keystrokes in editors."""

    if type(last_sequence) is not int or last_sequence < 0:
        raise ValueError("Shortcut sequence must be a non-negative integer")
    return _SHORTCUT(
        key=key,
        data={"last_sequence": last_sequence},
        on_toggle_change=on_toggle,
        height="content",
    )
