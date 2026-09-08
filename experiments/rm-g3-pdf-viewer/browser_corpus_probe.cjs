const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");
const {chromium} = require(process.argv[2] || "playwright");

const origin = "http://127.0.0.1:8504";
const manifestPath = path.resolve(process.argv[3]);
const outputPath = path.resolve(process.argv[4]);
const DIGITAL_ATTEMPTS = 3;
const SAMPLE_FRACTIONS = [0.2, 0.5, 0.8];

function parseSamples(values) {
  const samples = new Map();
  for (const value of values) {
    const separator = value.indexOf("=");
    if (separator < 1) throw new Error("Each sample must use ID=PATH");
    const id = value.slice(0, separator);
    if (samples.has(id)) throw new Error(`Duplicate sample id: ${id}`);
    samples.set(id, path.resolve(value.slice(separator + 1)));
  }
  return samples;
}

function fileHash(filename) {
  return crypto.createHash("sha256").update(fs.readFileSync(filename)).digest("hex").toUpperCase();
}

async function selectVisibleSpan(page, fraction) {
  const spans = page.locator(".textLayer span");
  const indices = await spans.evaluateAll(elements => elements.flatMap((element, index) => {
    const text = element.textContent || "";
    const match = /\S{6}/u.exec(text);
    let eligible = element.firstChild?.nodeType === Node.TEXT_NODE && Boolean(match);
    if (eligible) {
      const range = element.ownerDocument.createRange();
      range.setStart(element.firstChild, match.index);
      range.setEnd(element.firstChild, match.index + match[0].length);
      const box = range.getBoundingClientRect();
      const root = element.getRootNode();
      const hit = typeof root.elementFromPoint === "function"
        ? root.elementFromPoint(box.left + box.width / 2, box.top + box.height / 2)
        : element;
      eligible = box.width > 1 && box.height > 1 && (hit === element || element.contains(hit));
    }
    return eligible ? [index] : [];
  }));
  if (!indices.length) return false;
  const sampledIndex = indices[Math.floor((indices.length - 1) * fraction)];
  const target = spans.nth(sampledIndex);
  await target.scrollIntoViewIfNeeded();
  const points = await target.evaluate(element => {
    const node = element.firstChild;
    const text = node.data;
    const match = /\S{6}/u.exec(text);
    if (!match) throw new Error("Candidate text changed before selection");
    const start = match.index;
    const end = start + match[0].length;
    const codePoints = Array.from(match[0]);
    const firstEnd = start + codePoints[0].length;
    const lastStart = end - codePoints[codePoints.length - 1].length;
    return [[start, firstEnd, 0.25], [lastStart, end, 0.75]].map(([from, to, ratio]) => {
      const range = document.createRange();
      range.setStart(node, from);
      range.setEnd(node, to);
      const box = range.getBoundingClientRect();
      return {x: box.left + box.width * ratio, y: box.top + box.height / 2};
    });
  });
  await page.mouse.move(points[0].x, points[0].y);
  await page.mouse.down();
  await page.mouse.move(points[1].x, points[1].y, {steps: 12});
  await page.mouse.up();
  await page.locator(".selection-submit:enabled").waitFor();
  return true;
}

async function openDocumentPage(context, spec, filename, result) {
  const page = await context.newPage();
  page.setDefaultTimeout(30000);
  page.on("pageerror", () => { result.page_error_count += 1; });
  await page.goto(origin);
  await page.locator('input[type="file"]').setInputFiles(filename);
  await page.locator(".viewer-status").filter({hasText: "Page 1/"}).waitFor();
  if (spec.sample_page !== 1) {
    const input = page.getByRole("spinbutton", {name: "页码", exact: true});
    await input.fill(String(spec.sample_page));
    await input.press("Enter");
  }
  await page.locator(".viewer-status").filter({hasText: `Page ${spec.sample_page}/`}).waitFor();
  return page;
}

async function probeDocument(context, spec, filename) {
  assert.equal(fileHash(filename), spec.sha256, `SHA-256 mismatch for ${spec.id}`);
  const result = {
    id: spec.id,
    sample_page: spec.sample_page,
    expected_text_layer: spec.expected_text_layer,
    page_error_count: 0,
  };
  if (!spec.expected_text_layer) {
    const page = await openDocumentPage(context, spec, filename, result);
    try {
      result.text_items = await page.locator(".textLayer span").count();
      result.degraded_without_selection = result.text_items === 0
        && await page.locator(".selection-submit:disabled").count() === 1;
      result.passed = result.degraded_without_selection && result.page_error_count === 0;
      return result;
    } finally {
      await page.close();
    }
  }

  result.required_attempts = DIGITAL_ATTEMPTS;
  result.selection_attempts = 0;
  result.clipboard_matches = 0;
  result.reconciled_attempts = 0;
  result.locator_status_counts = {};
  result.failures = [];
  for (let ordinal = 0; ordinal < DIGITAL_ATTEMPTS; ordinal += 1) {
    let stage = "open";
    let page;
    try {
      stage = "upload_navigate";
      page = await openDocumentPage(context, spec, filename, result);
      const textItems = await page.locator(".textLayer span").count();
      if (result.text_items === undefined) result.text_items = textItems;
      stage = "select";
      if (!await selectVisibleSpan(page, SAMPLE_FRACTIONS[ordinal])) {
        result.failures.push({attempt: ordinal + 1, stage, type: "NoCandidate"});
        continue;
      }
      result.selection_attempts += 1;
      const preview = await page.locator(".selection-preview").innerText();
      await page.keyboard.press("Control+C");
      const copied = await page.evaluate(() => navigator.clipboard.readText());
      if (copied === preview && Array.from(preview).length === 6) result.clipboard_matches += 1;
      stage = "reconcile";
      await page.locator(".selection-submit").click();
      const accepted = page.getByText("已通过 PyMuPDF 文字与几何对账的实验选择", {exact: true});
      const rejected = page.getByText(/PDF 选择未通过服务器对账/);
      await Promise.race([accepted.waitFor(), rejected.waitFor()]);
      if (await accepted.count() === 1) {
        result.reconciled_attempts += 1;
        const statusLine = await page.getByText(/实验 locator_status：/).innerText();
        const status = statusLine.replace("实验 locator_status：", "");
        result.locator_status_counts[status] = (result.locator_status_counts[status] || 0) + 1;
      } else {
        const reason = (await rejected.innerText()).replace("PDF 选择未通过服务器对账：", "");
        result.failures.push({attempt: ordinal + 1, stage, type: "Rejected", reason});
      }
    } catch (error) {
      result.failures.push({attempt: ordinal + 1, stage, type: error?.name || "Error"});
    } finally {
      if (page) await page.close();
    }
  }
  result.passed = result.text_items > 0
    && result.selection_attempts === DIGITAL_ATTEMPTS
    && result.clipboard_matches === DIGITAL_ATTEMPTS
    && result.reconciled_attempts === DIGITAL_ATTEMPTS
    && result.page_error_count === 0;
  return result;
}

async function main() {
  const manifest = JSON.parse(fs.readFileSync(manifestPath, "utf8"));
  const samples = parseSamples(process.argv.slice(5));
  const required = new Set(manifest.documents.map(item => item.id));
  assert.deepEqual(new Set(samples.keys()), required, "Sample ids must match the manifest exactly");

  const browser = await chromium.launch({channel: "msedge", headless: true});
  const context = await browser.newContext({viewport: {width: 1280, height: 1050}});
  await context.grantPermissions(["clipboard-read", "clipboard-write"], {origin});
  const externalRequests = [];
  await context.route("**/*", route => {
    const url = new URL(route.request().url());
    if (url.origin !== origin) {
      externalRequests.push(url.origin);
      return route.abort();
    }
    return route.continue();
  });
  const report = {
    schema_version: 1,
    status: "isolated_spike_evidence",
    engine: "pdf.js/6.3.289 + PyMuPDF/1.28.2",
    browser: browser.version(),
    external_request_count: 0,
    documents: [],
    limitations: [
      "Visible text spans are sampled at 20%, 50%, and 80% of the page, not exhaustively labeled.",
      "Automated wheel events are not physical-trackpad evidence.",
      "Mathematical text-layer selection is not formula recognition or LaTeX reconstruction.",
    ],
  };
  try {
    for (const spec of manifest.documents) {
      try {
        report.documents.push(await probeDocument(context, spec, samples.get(spec.id)));
      } catch (error) {
        report.documents.push({id: spec.id, passed: false, failure_stage: "prepare", failure_type: error?.name || "Error"});
      }
    }
    report.external_request_count = externalRequests.length;
    report.aggregate = {
      documents_passed: report.documents.filter(item => item.passed).length,
      digital_selection_attempts: report.documents.reduce(
        (total, item) => total + (item.selection_attempts || 0), 0),
      native_copy_matches: report.documents.reduce(
        (total, item) => total + (item.clipboard_matches || 0), 0),
      server_reconciliations: report.documents.reduce(
        (total, item) => total + (item.reconciled_attempts || 0), 0),
      verified_text_geometry: report.documents.reduce(
        (total, item) => total + (item.locator_status_counts?.verified_text_geometry || 0), 0),
      verified_unique_text_anchor: report.documents.reduce(
        (total, item) => total + (item.locator_status_counts?.verified_unique_text_anchor || 0), 0),
      external_requests: report.external_request_count,
    };
    report.passed = report.documents.every(item => item.passed) && externalRequests.length === 0;
  } finally {
    fs.mkdirSync(path.dirname(outputPath), {recursive: true});
    fs.writeFileSync(outputPath, JSON.stringify(report, null, 2));
    console.log(JSON.stringify(report));
    await browser.close();
  }
  if (!report.passed) process.exitCode = 1;
}

main().catch(error => { console.error(String(error)); process.exitCode = 1; });
