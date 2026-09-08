const fs = require("node:fs");
const path = require("node:path");
const {chromium} = require(process.argv[2] || "playwright");

const origin = "http://127.0.0.1:8504";
const pdfPath = path.resolve(process.argv[3]);
const outputPath = path.resolve(process.argv[4]);

async function characterPoint(element, from, to, ratio) {
  return element.evaluate((nodeElement, values) => {
    const node = nodeElement.firstChild;
    const range = document.createRange();
    range.setStart(node, values.from);
    range.setEnd(node, values.to);
    const box = range.getBoundingClientRect();
    return {x: box.left + box.width * values.ratio, y: box.top + box.height / 2};
  }, {from, to, ratio});
}

async function main() {
  const browser = await chromium.launch({channel: "msedge", headless: true});
  const context = await browser.newContext({viewport: {width: 1280, height: 1050}});
  await context.grantPermissions(["clipboard-read", "clipboard-write"], {origin});
  const externalRequests = [];
  await context.route("**/*", route => {
    const url = new URL(route.request().url());
    if (url.origin !== origin) { externalRequests.push(url.origin); return route.abort(); }
    return route.continue();
  });
  const page = await context.newPage();
  page.setDefaultTimeout(30000);
  let pageErrorCount = 0;
  page.on("pageerror", () => { pageErrorCount += 1; });
  const report = {browser: browser.version()};
  let stage = "open";
  try {
    await page.goto(origin);
    stage = "upload";
    await page.locator('input[type="file"]').setInputFiles(pdfPath);
    await page.locator(".viewer-status").filter({hasText: "Page 1/2"}).waitFor();
    stage = "navigate";
    const pageInput = page.getByRole("spinbutton", {name: "页码", exact: true});
    await pageInput.fill("2");
    await pageInput.press("Enter");
    await page.locator(".viewer-status").filter({hasText: "Page 2/2"}).waitFor();
    const first = page.locator(".textLayer span").filter({hasText: "Left column first line."}).first();
    const second = page.locator(".textLayer span").filter({hasText: "Left column second line."}).first();
    await first.waitFor(); await second.waitFor();
    const structure = await Promise.all([first, second].map(locator => locator.evaluate(element => ({
      itemIndex: Number(element.dataset.itemIndex),
      top: element.getBoundingClientRect().top,
    }))));
    report.first_item_index = structure[0].itemIndex;
    report.second_item_index = structure[1].itemIndex;
    report.line_top_delta_px = Math.round(Math.abs(structure[1].top - structure[0].top) * 100) / 100;
    await first.evaluate(element => element.scrollIntoView({block: "center", inline: "center"}));
    stage = "select";
    const start = await characterPoint(first, 0, 1, 0.25);
    const end = await characterPoint(second, 10, 11, 0.75);
    await page.mouse.move(start.x, start.y);
    await page.mouse.down();
    await page.mouse.move(end.x, end.y, {steps: 24});
    await page.mouse.up();
    await page.locator(".selection-submit:enabled").waitFor();
    const preview = await page.locator(".selection-preview").innerText();
    report.selected_code_points = Array.from(preview).length;
    report.preview_line_breaks = (preview.match(/\n/g) || []).length;
    const captureStatus = await page.locator(".viewer-status").innerText();
    report.captured_ranges = Number(/(\d+) ranges/.exec(captureStatus)?.[1] || 0);
    await page.keyboard.press("Control+C");
    const copied = await page.evaluate(() => navigator.clipboard.readText());
    report.copied_code_points = Array.from(copied).length;
    report.native_copy_matches_preview = copied === preview;
    const normalize = value => value.trim().replace(/\s+/gu, " ");
    report.native_copy_normalized_matches_preview = normalize(copied) === normalize(preview);
    stage = "submit";
    await page.locator(".selection-submit").click();
    const accepted = page.getByText("已通过 PyMuPDF 文字与几何对账的实验选择", {exact: true});
    const rejected = page.getByText(/PDF 选择未通过服务器对账/);
    await Promise.race([accepted.waitFor(), rejected.waitFor()]);
    if (await rejected.count() === 1) {
      report.rejection_reason = (await rejected.innerText()).replace("PDF 选择未通过服务器对账：", "");
      throw Object.assign(new Error("Selection rejected"), {name: "ReconciledSelectionRejected"});
    }
    const statusLine = await page.getByText(/实验 locator_status：/).innerText();
    report.locator_status = statusLine.replace("实验 locator_status：", "");
    const provenanceLine = await page.getByText(/实验 provenance：/).innerText();
    const match = /ranges=(\d+), trusted_line_boxes=(\d+)/.exec(provenanceLine);
    report.client_ranges = Number(match?.[1] || 0);
    report.trusted_line_boxes = Number(match?.[2] || 0);
  } catch (error) {
    report.failure_stage = stage;
    report.failure_type = error?.name || "Error";
  } finally {
    report.page_error_count = pageErrorCount;
    report.external_request_count = externalRequests.length;
    report.passed = report.selected_code_points > 20
      && report.native_copy_normalized_matches_preview
      && report.client_ranges >= 2
      && report.trusted_line_boxes >= 2
      && pageErrorCount === 0
      && externalRequests.length === 0;
    fs.mkdirSync(path.dirname(outputPath), {recursive: true});
    fs.writeFileSync(outputPath, JSON.stringify(report, null, 2));
    console.log(JSON.stringify(report));
    await browser.close();
  }
  if (!report.passed) process.exitCode = 1;
}

main().catch(error => { console.error(error?.name || "Error"); process.exitCode = 1; });
