const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const {chromium} = require(process.argv[2] || "playwright");
const origin = "http://127.0.0.1:8504";
const pdfPath = path.resolve(process.argv[3]);
const output = path.resolve(process.argv[4] || ".release-tmp/g3-pdf-browser");
async function canvasSignature(page) {
  return page.locator(".pdf-canvas").evaluate(canvas => {
    const context = canvas.getContext("2d", {willReadFrequently: true});
    if (!context) throw new Error("Canvas 2D is unavailable");
    const pixels = context.getImageData(0, 0, canvas.width, canvas.height).data;
    let hash = 2166136261;
    for (let index = 0; index < pixels.length; index += 1) {
      hash ^= pixels[index]; hash = Math.imul(hash, 16777619);
    }
    return {width: canvas.width, height: canvas.height, hash: hash >>> 0};
  });
}
async function main() {
  fs.mkdirSync(output, {recursive: true});
  const browser = await chromium.launch({channel: "msedge", headless: true});
  const context = await browser.newContext({viewport: {width: 1280, height: 1050}});
  const report = {browser: browser.version(), checks: [], errors: [], externalRequests: []};
  await context.route("**/*", route => {
    const url = new URL(route.request().url());
    if (url.origin !== origin) { report.externalRequests.push(url.origin); return route.abort(); }
    return route.continue();
  });
  const page = await context.newPage();
  page.setDefaultTimeout(20000);
  page.on("pageerror", error => report.errors.push(error.message));
  try {
    await page.goto(origin);
    await page.locator('input[type="file"]').setInputFiles(pdfPath);
    await page.locator(".viewer-status").filter({hasText: "Page 1/2"}).waitFor();
    const pageOneCanvas = await canvasSignature(page);
    await page.locator(".pdf-canvas").screenshot({path: path.join(output, "page1-canvas.png")});
    const target = page.locator(".textLayer span").filter({hasText: "Select this exact sentence"}).first();
    await target.waitFor();
    const points = await target.evaluate(element => {
      const node = element.firstChild;
      return [0, 6].map(offset => {
        const range = document.createRange();
        range.setStart(node, offset); range.setEnd(node, offset);
        const box = range.getBoundingClientRect();
        return {x: box.x + 0.1, y: box.y + box.height / 2};
      });
    });
    await page.mouse.move(points[0].x, points[0].y);
    await page.mouse.down();
    await page.mouse.move(points[1].x, points[1].y, {steps: 12});
    await page.mouse.up();
    await page.locator(".selection-submit:enabled").waitFor();
    assert.equal(await page.locator(".selection-preview").innerText(), "Select");
    await page.locator(".selection-submit").click();
    await page.getByText("已通过 PyMuPDF 文字与几何对账的实验选择", {exact: true}).waitFor();
    await page.getByTestId("stCode").filter({hasText: "Select"}).waitFor();
    assert.deepEqual(await canvasSignature(page), pageOneCanvas);
    const ui = await page.locator("body").innerText();
    assert.match(ui, /Select/);
    assert.match(ui, /pdf\.js\/6\.3\.289/);
    assert.match(ui, /verified_text_geometry/);
    report.checks.push("PDF canvas and text layer rendered from local upload");
    report.checks.push("real mouse selection emitted page/revision/item/bbox event");
    report.checks.push("canvas bitmap survives the trigger rerun unchanged");
    await page.locator(".viewer-root").screenshot({path: path.join(output, "page1-selection.png")});
    const pageInput = page.getByRole("spinbutton", {name: "页码", exact: true});
    await pageInput.fill("2");
    await pageInput.press("Enter");
    await page.locator(".viewer-status").filter({hasText: "Page 2/2"}).waitFor();
    assert.doesNotMatch(await page.locator("body").innerText(), /已通过 PyMuPDF 文字与几何对账的实验选择/);
    await page.locator(".textLayer span").filter({hasText: "Right column first line"}).waitFor();
    report.checks.push("page change re-renders and invalidates prior selection");
    report.checks.push("page 2 exposes both-column PDF.js text items");
    await page.locator(".pdf-canvas").screenshot({path: path.join(output, "page2-canvas.png")});
    await page.locator(".viewer-root").screenshot({path: path.join(output, "page2-columns.png")});
    assert.deepEqual(report.errors, []);
    assert.deepEqual(report.externalRequests, []);
    report.passed = true;
  } catch (error) {
    report.passed = false; report.failure = String(error);
    report.uiText = await page.locator("body").innerText().catch(() => "");
    report.viewerDiagnostics = await page.locator(".viewer-root").evaluateAll(roots => roots.map(root => {
      const status = root.querySelector(".viewer-status");
      const canvas = root.querySelector("canvas");
      const layer = root.querySelector(".textLayer");
      const context = canvas?.getContext("2d", {willReadFrequently: true});
      const sample = context && canvas.width && canvas.height
        ? Array.from(context.getImageData(0, 0, Math.min(canvas.width, 32), Math.min(canvas.height, 32)).data)
            .reduce((sum, value) => sum + value, 0) : null;
      return {status: status?.textContent || null, canvas: canvas ? [canvas.width, canvas.height] : null,
        layerItems: layer?.childElementCount || 0, topLeftPixelSum: sample};
    })).catch(() => []);
    await page.screenshot({path: path.join(output, "failure.png"), fullPage: true});
    process.exitCode = 1;
  } finally {
    fs.writeFileSync(path.join(output, "report.json"), JSON.stringify(report, null, 2));
    console.log(JSON.stringify(report)); await browser.close();
  }
}
main().catch(error => {console.error(error); process.exitCode = 1;});
