import { FrontendRenderer, FrontendRendererArgs } from "@streamlit/component-v2-lib";
import { getDocument, GlobalWorkerOptions, TextLayer, version } from "pdfjs-dist";
import workerUrl from "pdfjs-dist/build/pdf.worker.mjs?url";
import "./viewer.css";

GlobalWorkerOptions.workerSrc = workerUrl;

type SelectionEvent = {version: 1; revision: string; instance: string;
  page: number; sequence: number;
  text: string; ranges: [number, number, number][]; bboxes: [number, number, number, number][];
  viewport: [number, number]; engine: string};
type PageTurnEvent = {version: 1; revision: string; instance: string;
  page: number; sequence: number;
  delta: -1 | 1; source: "wheel"};
type FrontendState = {submitted: SelectionEvent; page_turn: PageTurnEvent;
  loaded_revision: string};
type ComponentData = {pdf_base64: string; revision: string; page: number; scale: number;
  page_count: number; instance: string; max_selection_chars: number;
  loaded_revision: string};
type Instance = {selectionSequence: number; pageTurnSequence: number;
  disposed: boolean; cleanup: () => void};
const instances = new WeakMap<FrontendRendererArgs["parentElement"], Instance>();
type PdfResource = {revision: string; loadingTask: ReturnType<typeof getDocument>;
  reuseCount: number; disposeTimer?: number};
const resources = new Map<string, PdfResource>();
const WHEEL_THRESHOLD_PX = 80;
const WHEEL_RESET_MS = 180;
const WHEEL_DEBOUNCE_MS = 650;
const WHEEL_QUIET_MS = 250;
const WHEEL_EVENT_CLAMP_PX = 120;
const SCROLL_EDGE_EPSILON_PX = 2;
const NORMALIZED_BOX_EDGE_EPSILON = 0.01;
const RESOURCE_DISPOSE_DELAY_MS = 1500;

function acquireResource(
  data: ComponentData,
): PdfResource | undefined {
  const existing = resources.get(data.instance);
  if (existing?.revision === data.revision) {
    if (existing.disposeTimer !== undefined) window.clearTimeout(existing.disposeTimer);
    existing.disposeTimer = undefined;
    existing.reuseCount += 1;
    return existing;
  }
  if (existing) {
    if (existing.disposeTimer !== undefined) window.clearTimeout(existing.disposeTimer);
    void existing.loadingTask.destroy();
    resources.delete(data.instance);
  }
  if (!data.pdf_base64) return undefined;
  const resource = {
    revision: data.revision,
    loadingTask: getDocument({data: decodeBase64(data.pdf_base64)}),
    reuseCount: 0,
  };
  resources.set(data.instance, resource);
  return resource;
}

function scheduleResourceDisposal(
  instance: string,
  resource: PdfResource,
) {
  if (resource.disposeTimer !== undefined) window.clearTimeout(resource.disposeTimer);
  resource.disposeTimer = window.setTimeout(() => {
    if (resources.get(instance) !== resource) return;
    resources.delete(instance);
    void resource.loadingTask.destroy();
  }, RESOURCE_DISPOSE_DELAY_MS);
}

function decodeBase64(value: string): Uint8Array {
  const binary = atob(value);
  const output = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) output[index] = binary.charCodeAt(index);
  return output;
}

function codePointOffset(text: string, utf16Offset: number): number {
  if (!Number.isInteger(utf16Offset) || utf16Offset < 0 || utf16Offset > text.length)
    throw new Error("Invalid UTF-16 selection offset");
  if (utf16Offset > 0 && utf16Offset < text.length &&
      /[\uD800-\uDBFF]/.test(text[utf16Offset - 1]) && /[\uDC00-\uDFFF]/.test(text[utf16Offset]))
    throw new Error("Selection splits a Unicode surrogate pair");
  return Array.from(text.slice(0, utf16Offset)).length;
}

function offsetWithin(element: HTMLElement, node: Node, offset: number): number {
  const range = element.ownerDocument.createRange();
  range.selectNodeContents(element);
  range.setEnd(node, offset);
  return range.toString().length;
}

const Viewer: FrontendRenderer<FrontendState, ComponentData> = args => {
  const {parentElement, data, setStateValue, setTriggerValue} = args;
  instances.get(parentElement)?.cleanup();
  const root = parentElement.querySelector<HTMLElement>(".viewer-root");
  const scroller = root?.querySelector<HTMLElement>(".viewer-scroll");
  const shell = root?.querySelector<HTMLElement>(".page-shell");
  const canvas = root?.querySelector<HTMLCanvasElement>(".pdf-canvas");
  const layer = root?.querySelector<HTMLElement>(".textLayer");
  const status = root?.querySelector<HTMLElement>(".viewer-status");
  const preview = root?.querySelector<HTMLElement>(".selection-preview");
  const submit = root?.querySelector<HTMLButtonElement>(".selection-submit");
  if (!root || !scroller || !shell || !canvas || !layer || !status || !preview || !submit)
    throw new Error("G3 viewer DOM is incomplete");
  const storedSelectionSequence = Number(root.dataset.selectionSequence || "0");
  const storedPageTurnSequence = Number(root.dataset.pageTurnSequence || "0");
  const previousPage = Number(root.dataset.page || "0");
  const state: Instance = {
    selectionSequence: Number.isSafeInteger(storedSelectionSequence) ? storedSelectionSequence : 0,
    pageTurnSequence: Number.isSafeInteger(storedPageTurnSequence) ? storedPageTurnSequence : 0,
    disposed: false,
    cleanup: () => undefined,
  };
  let renderTask: {cancel: () => void; promise: Promise<unknown>} | undefined;
  let textLayer: TextLayer | undefined;
  let pageHandle: {cleanup: () => boolean} | undefined;
  let resource: PdfResource | undefined;
  let pending: SelectionEvent | undefined;
  let textDivs: HTMLElement[] = [];
  let wheelAccumulator = 0;
  let lastWheelAt = 0;
  let lockedUntil = 0;

  const clearPending = () => { pending = undefined; preview.textContent = ""; submit.disabled = true; };
  const capture = () => {
    clearPending();
    const selected = root.ownerDocument.getSelection();
    if (!selected) return;
    const shadow = root.getRootNode() as ShadowRoot;
    const composed = typeof selected.getComposedRanges === "function"
      ? selected.getComposedRanges({shadowRoots: [shadow]}) : [];
    const shadowSelection = (shadow as ShadowRoot & {getSelection?: () => Selection | null}).getSelection;
    const local = typeof shadowSelection === "function" ? shadowSelection.call(shadow) : undefined;
    const source = composed.length === 1 ? composed[0]
      : local && local.rangeCount === 1 ? local.getRangeAt(0) : undefined;
    if (!source || !layer.contains(source.startContainer) || !layer.contains(source.endContainer)) return;
    const range = root.ownerDocument.createRange();
    range.setStart(source.startContainer, source.startOffset);
    range.setEnd(source.endContainer, source.endOffset);
    if (range.collapsed) return;
    const browserText = selected.toString();
    if (!browserText || Array.from(browserText).length > data.max_selection_chars) return;
    const startElement = source.startContainer.nodeType === Node.TEXT_NODE
      ? source.startContainer.parentElement : source.startContainer as HTMLElement;
    const endElement = source.endContainer.nodeType === Node.TEXT_NODE
      ? source.endContainer.parentElement : source.endContainer as HTMLElement;
    const start = textDivs.findIndex(item => item === startElement || item.contains(startElement));
    const end = textDivs.findIndex(item => item === endElement || item.contains(endElement));
    if (start < 0 || end < start) return;
    const ranges: [number, number, number][] = [];
    const chunks: {element: HTMLElement; text: string}[] = [];
    try {
      for (let index = start; index <= end; index += 1) {
        const element = textDivs[index];
        const itemText = element.textContent || "";
        const startUtf16 = index === start ? offsetWithin(element, source.startContainer, source.startOffset) : 0;
        const endUtf16 = index === end ? offsetWithin(element, source.endContainer, source.endOffset) : itemText.length;
        const rangeStart = codePointOffset(itemText, startUtf16);
        const rangeEnd = codePointOffset(itemText, endUtf16);
        if (rangeEnd > rangeStart) {
          ranges.push([index, rangeStart, rangeEnd]);
          chunks.push({element, text: Array.from(itemText).slice(rangeStart, rangeEnd).join("")});
        }
      }
    } catch {
      return;
    }
    if (!ranges.length || ranges.length > 128) return;
    const text = chunks.map((chunk, index) => {
      if (index === 0) return chunk.text;
      const previousBox = chunks[index - 1].element.getBoundingClientRect();
      const currentBox = chunk.element.getBoundingClientRect();
      const changedLine = Math.abs(currentBox.top - previousBox.top) > 1;
      return (changedLine ? "\n" : "") + chunk.text;
    }).join("");
    if (!text || Array.from(text).length > data.max_selection_chars) return;
    const pageBox = shell.getBoundingClientRect();
    const rawBboxes = Array.from(range.getClientRects()).slice(0, 128).map(box => [
      (box.left - pageBox.left) / pageBox.width, (box.top - pageBox.top) / pageBox.height,
      (box.right - pageBox.left) / pageBox.width, (box.bottom - pageBox.top) / pageBox.height,
    ] as [number, number, number, number]);
    if (!rawBboxes.length || rawBboxes.some(box => box.some(value =>
      !Number.isFinite(value)
      || value < -NORMALIZED_BOX_EDGE_EPSILON
      || value > 1 + NORMALIZED_BOX_EDGE_EPSILON))) return;
    const bboxes = rawBboxes.map(box => box.map(value =>
      Math.max(0, Math.min(1, value))) as [number, number, number, number])
      .filter(box => box[2] > box[0] && box[3] > box[1]);
    if (!bboxes.length) return;
    pending = {version: 1, revision: data.revision, instance: data.instance,
      page: data.page,
      sequence: state.selectionSequence + 1, text, ranges, bboxes,
      viewport: [pageBox.width, pageBox.height], engine: `pdf.js/${version}`};
    preview.textContent = text;
    submit.disabled = false;
    status.textContent = `Selection captured locally; ${ranges.length} ranges; `
      + `${(text.match(/\n/g) || []).length} line breaks; confirm for local PyMuPDF reconciliation.`;
  };
  const emit = () => {
    if (!pending) return;
    state.selectionSequence = pending.sequence;
    root.dataset.selectionSequence = String(state.selectionSequence);
    setTriggerValue("submitted", pending);
    clearPending();
  };
  const wheelPixels = (event: WheelEvent) => {
    if (event.deltaMode === WheelEvent.DOM_DELTA_LINE) return event.deltaY * 16;
    if (event.deltaMode === WheelEvent.DOM_DELTA_PAGE) return event.deltaY * scroller.clientHeight;
    return event.deltaY;
  };
  const onWheel = (event: WheelEvent) => {
    const shadow = root.getRootNode() as ShadowRoot;
    const active = shadow.activeElement || root.ownerDocument.activeElement;
    if (active !== scroller && !scroller.contains(active)) return;
    if (event.ctrlKey || event.metaKey || event.altKey || event.shiftKey || pending) return;
    if (!Number.isFinite(event.deltaY) || Math.abs(event.deltaY) <= Math.abs(event.deltaX)) return;
    const rawPixels = wheelPixels(event);
    const pixels = Math.max(-WHEEL_EVENT_CLAMP_PX, Math.min(WHEEL_EVENT_CLAMP_PX, rawPixels));
    const delta: -1 | 1 = pixels < 0 ? -1 : 1;
    const atEdge = delta < 0
      ? scroller.scrollTop <= SCROLL_EDGE_EPSILON_PX
      : scroller.scrollTop + scroller.clientHeight >= scroller.scrollHeight - SCROLL_EDGE_EPSILON_PX;
    const target = data.page + delta;
    if (!atEdge || target < 1 || target > data.page_count) {
      wheelAccumulator = 0;
      return;
    }
    // Once the PDF scroller reaches an eligible page edge, it owns the gesture.
    // Small bursts are absorbed until the deliberate-turn threshold is crossed.
    event.preventDefault();
    const now = performance.now();
    const quietBeforeEvent = now - lastWheelAt;
    if (now < lockedUntil || (lockedUntil > 0 && quietBeforeEvent < WHEEL_QUIET_MS)) {
      lastWheelAt = now;
      return;
    }
    lockedUntil = 0;
    if (now - lastWheelAt > WHEEL_RESET_MS || Math.sign(wheelAccumulator) !== delta) {
      wheelAccumulator = 0;
    }
    lastWheelAt = now;
    wheelAccumulator += pixels;
    if (Math.abs(wheelAccumulator) < WHEEL_THRESHOLD_PX) return;
    wheelAccumulator = 0;
    lockedUntil = now + WHEEL_DEBOUNCE_MS;
    state.pageTurnSequence += 1;
    root.dataset.pageTurnSequence = String(state.pageTurnSequence);
    status.textContent = `Wheel requested page ${target}; waiting for server validation.`;
    setTriggerValue("page_turn", {version: 1, revision: data.revision,
      instance: data.instance, page: data.page,
      sequence: state.pageTurnSequence, delta, source: "wheel"});
  };
  const focusScroller = () => scroller.focus({preventScroll: true});
  const keep = (event: Event) => event.preventDefault();
  layer.addEventListener("pointerup", capture);
  layer.addEventListener("keyup", capture);
  submit.addEventListener("mousedown", keep);
  submit.addEventListener("click", emit);
  scroller.addEventListener("pointerdown", focusScroller);
  scroller.addEventListener("wheel", onWheel, {passive: false});

  const render = async () => {
    try {
      status.textContent = `Loading page ${data.page} locally with PDF.js ${version}...`;
      resource = acquireResource(data);
      if (!resource) {
        status.textContent = "Browser PDF cache is unavailable; requesting the validated bytes again.";
        if (data.loaded_revision) setStateValue("loaded_revision", "");
        return;
      }
      const document = await resource.loadingTask.promise;
      if (state.disposed) return;
      if (document.numPages !== data.page_count) throw new Error("Trusted page count changed");
      if (data.page > document.numPages) throw new Error(`Page exceeds document (${document.numPages})`);
      const page = await document.getPage(data.page);
      pageHandle = page;
      const viewport = page.getViewport({scale: data.scale});
      const ratio = window.devicePixelRatio || 1;
      layer.replaceChildren();
      canvas.width = Math.floor(viewport.width * ratio);
      canvas.height = Math.floor(viewport.height * ratio);
      canvas.style.width = `${viewport.width}px`; canvas.style.height = `${viewport.height}px`;
      shell.style.width = `${viewport.width}px`; shell.style.height = `${viewport.height}px`;
      const context = canvas.getContext("2d");
      if (!context) throw new Error("Canvas 2D is unavailable");
      renderTask = page.render({canvas, canvasContext: context, viewport,
        transform: ratio === 1 ? undefined : [ratio, 0, 0, ratio, 0, 0]});
      const content = await page.getTextContent();
      await renderTask.promise;
      if (state.disposed) return;
      textLayer = new TextLayer({textContentSource: content, container: layer, viewport});
      await textLayer.render();
      textDivs = textLayer.textDivs;
      textDivs.forEach((element, index) => { element.dataset.itemIndex = String(index); });
      if (previousPage > data.page) scroller.scrollTop = scroller.scrollHeight;
      else if (previousPage !== data.page) scroller.scrollTop = 0;
      root.dataset.page = String(data.page);
      const resourceState = resource.reuseCount > 0 ? "reused" : "opened";
      root.dataset.pdfPayload = data.pdf_base64 ? "received" : "omitted";
      if (data.loaded_revision !== data.revision) {
        setStateValue("loaded_revision", data.revision);
      }
      status.textContent = `Page ${data.page}/${document.numPages}; ${textDivs.length} text items; `
        + `resource ${resourceState}; no network upload.`;
    } catch (error) {
      if (!state.disposed) status.textContent = `Cannot render this PDF page: ${String(error)}`;
    }
  };
  // Canvas bitmap state is not durable across Streamlit DOM reconciliation.
  // Repaint on every renderer invocation even when the PDF inputs are unchanged.
  void render();
  const cleanup = () => {
    state.disposed = true;
    layer.removeEventListener("pointerup", capture); layer.removeEventListener("keyup", capture);
    submit.removeEventListener("mousedown", keep); submit.removeEventListener("click", emit);
    scroller.removeEventListener("pointerdown", focusScroller);
    scroller.removeEventListener("wheel", onWheel);
    renderTask?.cancel(); textLayer?.cancel(); pageHandle?.cleanup();
    if (resource) scheduleResourceDisposal(data.instance, resource);
    if (instances.get(parentElement) === state) instances.delete(parentElement);
  };
  state.cleanup = cleanup; instances.set(parentElement, state);
  return cleanup;
};
export default Viewer;
