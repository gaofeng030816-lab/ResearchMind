"""Inline CCv2 transport harness. No pdf.js, build step or external assets."""

from collections.abc import Callable
from dataclasses import asdict

import streamlit as st

from spike_state import HarnessState

HTML = """
<section id="harness" aria-label="Synthetic selection experiment">
  <div id="page" tabindex="0" aria-label="Selectable synthetic text"></div>
  <p id="status" role="status">Select text in the experiment.</p>
  <button id="submit" type="button" disabled>提交当前选择</button>
  <p>浏览器选择预览（未提交）：</p><pre id="preview"></pre>
</section>
"""

CSS = """
#page { max-height: 260px; overflow: auto; padding: 1rem;
  border: 1px solid var(--st-text-color); user-select: text; }
.span { display: block; white-space: pre-wrap; line-height: 2; }
#page.columns { display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; }
#preview { white-space: pre-wrap; max-height: 140px; overflow: auto; }
button { padding: .4rem .8rem; cursor: pointer; }
@media (max-width: 600px) { #page.columns { grid-template-columns: 1fr; } }
"""

JS = r"""
export function codePointOffset(text, offset) {
  if (!Number.isInteger(offset) || offset < 0 || offset > text.length)
    throw new Error("Invalid UTF-16 offset");
  if (offset > 0 && offset < text.length &&
      /[\uD800-\uDBFF]/.test(text[offset - 1]) && /[\uDC00-\uDFFF]/.test(text[offset]))
    throw new Error("Selection splits a surrogate pair");
  return Array.from(text.slice(0, offset)).length;
}

export function selectionEvent(data, ranges, sequence) {
  if (!ranges.length || ranges.length > 128 || !Number.isSafeInteger(sequence) || sequence < 1)
    throw new Error("Invalid selection budget");
  const text = ranges.map(([index, start, end]) => {
    const chars = Array.from(data.spans[index].text);
    if (!Number.isInteger(start) || !Number.isInteger(end) || start < 0 || end <= start || end > chars.length)
      throw new Error("Invalid character range");
    return chars.slice(start, end).join("");
  }).join("\n");
  if (Array.from(text).length > 8000) throw new Error("Selection too long");
  return {version: 1, revision: data.revision, instance: data.instance,
          page: data.page, sequence, ranges, text};
}

const activeMounts = new WeakMap();

export default function(component) {
  const {data, parentElement, setTriggerValue} = component;
  // CCv2 can call the renderer repeatedly without unmounting. Remove the previous
  // render's handlers now, not just when the entire component is removed.
  activeMounts.get(parentElement)?.();
  const root = parentElement.querySelector("#harness");
  const page = root.querySelector("#page");
  const submit = root.querySelector("#submit");
  const preview = root.querySelector("#preview");
  const status = root.querySelector("#status");
  const doc = root.ownerDocument;
  const shadow = root.getRootNode();
  const stamp = `${data.revision}:${data.page}:${data.instance}`;
  // Preserve DOM when only acknowledgements/reruns change; never insert text as HTML.
  if (page.dataset.stamp !== stamp) {
    page.replaceChildren();
    page.classList.toggle("columns", data.columns);
    const groups = data.columns ? [doc.createElement("div"), doc.createElement("div")] : [page];
    if (data.columns) groups.forEach(group => page.append(group));
    data.spans.forEach((span, index) => {
      const element = doc.createElement("span");
      element.className = "span";
      element.dataset.index = String(index);
      element.textContent = span.text;
      groups[data.columns && index >= Math.ceil(data.spans.length / 2) ? 1 : 0].append(element);
    });
    if (!data.spans.length) page.textContent = "无文字层：不可提交选择。";
    page.dataset.stamp = stamp;
  }
  let pending = null;
  let sequence = data.last_sequence;
  submit.disabled = true;
  preview.textContent = data.accepted_text || "";
  status.textContent = `服务端已接收序号：${data.last_sequence}；仅合成文字，非 PDF。`;

  function capture() {
    pending = null;
    submit.disabled = true;
    preview.textContent = "";
    const selected = doc.getSelection();
    // In Edge, the document selection may be collapsed at the shadow host even
    // while getComposedRanges exposes a non-empty selection inside this component.
    if (!selected) return;
    let selectedRange;
    if (typeof selected.getComposedRanges === "function") {
      const ranges = selected.getComposedRanges({shadowRoots: [shadow]});
      if (ranges.length !== 1) return;
      selectedRange = ranges[0];
    } else if (typeof shadow.getSelection === "function") {
      const local = shadow.getSelection();
      if (!local || local.rangeCount !== 1) return;
      selectedRange = local.getRangeAt(0);
    } else {
      status.textContent = "浏览器不支持可定位的 Shadow DOM 选择，请使用更新的浏览器。";
      return;
    }
    if (!page.contains(selectedRange.startContainer) || !page.contains(selectedRange.endContainer)) return;
    const range = doc.createRange();
    range.setStart(selectedRange.startContainer, selectedRange.startOffset);
    range.setEnd(selectedRange.endContainer, selectedRange.endOffset);
    if (range.collapsed) return;
    const ranges = [];
    try {
      for (const span of page.querySelectorAll(".span")) {
        const node = span.firstChild;
        if (!node || range.comparePoint(node, 0) > 0 || range.comparePoint(node, node.length) < 0) continue;
        const start = range.startContainer === node ? range.startOffset : 0;
        const end = range.endContainer === node ? range.endOffset : node.length;
        if (end > start) ranges.push([Number(span.dataset.index), codePointOffset(node.data, start), codePointOffset(node.data, end)]);
      }
      pending = selectionEvent(data, ranges, sequence + 1);
      preview.textContent = pending.text;
      submit.disabled = false;
      status.textContent = "选择已捕获；点击提交仅发送到本机实验，不调用 AI。";
    } catch {
      pending = null;
      status.textContent = "选择范围无效或过长，请重新选择。";
    }
  }
  const submitSelection = () => {
    if (!pending) return;
    sequence = pending.sequence;
    setTriggerValue("submitted", pending);
    pending = null;
    submit.disabled = true;
  };
  // Keep mouse-clicking Submit from collapsing the selection before its click event.
  const keepSelection = event => event.preventDefault();
  doc.addEventListener("selectionchange", capture);
  page.addEventListener("pointerup", capture);
  page.addEventListener("keyup", capture);
  submit.addEventListener("mousedown", keepSelection);
  submit.addEventListener("click", submitSelection);
  // No wheel/keydown interception: native scroll/copy remain untouched in G3-A.
  const cleanup = () => {
    doc.removeEventListener("selectionchange", capture);
    page.removeEventListener("pointerup", capture);
    page.removeEventListener("keyup", capture);
    submit.removeEventListener("mousedown", keepSelection);
    submit.removeEventListener("click", submitSelection);
    if (activeMounts.get(parentElement) === cleanup) activeMounts.delete(parentElement);
  };
  activeMounts.set(parentElement, cleanup);
  return cleanup;
}
"""

_COMPONENT = st.components.v2.component("g3_selection_contract_harness", html=HTML, css=CSS, js=JS)


def mount(state: HarnessState, *, key: str, on_submit: Callable[[], None]):
    payload = asdict(state.snapshot)
    payload.update(last_sequence=state.last_sequence,
                   accepted_text=state.selection.text if state.selection else "",
                   columns=state.identity[0] == "columns")
    return _COMPONENT(data=payload, key=key, on_submitted_change=on_submit, height="content")
