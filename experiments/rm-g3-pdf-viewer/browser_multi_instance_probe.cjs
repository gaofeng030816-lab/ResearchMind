const fs = require("node:fs");
const path = require("node:path");
const {chromium} = require(process.argv[2] || "playwright");

const origin = "http://127.0.0.1:8505";
const pdfPath = path.resolve(process.argv[3]);
const outputPath = path.resolve(process.argv[4]);

async function selectSix(page, root) {
  const target = root.locator(".textLayer span").filter({hasText: "Select this exact sentence"}).first();
  await target.waitFor();
  await target.evaluate(element => element.scrollIntoView({block: "center", inline: "center"}));
  const points = await target.evaluate(element => {
    const node = element.firstChild;
    const match = /Select/u.exec(node.data);
    const codePoints = Array.from(match[0]);
    const start = match.index;
    const end = start + match[0].length;
    const parts = [[start, start + codePoints[0].length, 0.25],
      [end - codePoints[codePoints.length - 1].length, end, 0.75]];
    return parts.map(([from, to, ratio]) => {
      const range = document.createRange();
      range.setStart(node, from); range.setEnd(node, to);
      const box = range.getBoundingClientRect();
      return {x: box.left + box.width * ratio, y: box.top + box.height / 2};
    });
  });
  const hitState = await target.evaluate((element, points) => {
    const root = element.getRootNode();
    const hits = points.map(point => typeof root.elementFromPoint === "function"
      ? root.elementFromPoint(point.x, point.y) : element);
    return {
      hit: hits.every(hit => hit === element || element.contains(hit)),
      inViewport: points.every(point => point.x >= 0 && point.y >= 0
        && point.x <= window.innerWidth && point.y <= window.innerHeight),
      hitElements: hits.map(hit => ({
        tag: hit?.tagName || "NONE",
        className: typeof hit?.className === "string" ? hit.className.slice(0, 80) : "",
      })),
    };
  }, points);
  await page.mouse.move(points[0].x, points[0].y);
  await page.mouse.down();
  await page.mouse.move(points[1].x, points[1].y, {steps: 12});
  await page.mouse.up();
  try {
    await root.locator(".selection-submit:enabled").waitFor();
  } catch {
    const error = new Error("Selection capture did not enable submit");
    error.name = !hitState.inViewport ? "TargetOutsideViewport"
      : !hitState.hit ? "TargetOccluded" : "VisibleTargetSelectionTimeout";
    error.safeDetails = hitState;
    throw error;
  }
}

async function main() {
  const browser = await chromium.launch({channel: "msedge", headless: true});
  const context = await browser.newContext({viewport: {width: 1440, height: 1000}});
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
    await page.locator(".viewer-status").filter({hasText: "Page 1/2"}).nth(1).waitFor();
    let roots = page.locator(".viewer-root");
    report.viewer_count = await roots.count();
    stage = "first_select";
    await selectSix(page, roots.nth(0));
    report.second_preview_empty_before_first_submit = await roots.nth(1).locator(".selection-preview").innerText() === "";
    report.second_submit_disabled_before_first_submit = await roots.nth(1).locator(".selection-submit:disabled").count() === 1;
    stage = "first_submit";
    await roots.nth(0).locator(".selection-submit").click();
    await page.getByText(/g3_viewer_a accepted:/).waitFor();
    report.first_accepted = true;
    roots = page.locator(".viewer-root");
    stage = "second_select";
    await selectSix(page, roots.nth(1));
    report.first_preview_empty_before_second_submit = await roots.nth(0).locator(".selection-preview").innerText() === "";
    stage = "second_submit";
    await roots.nth(1).locator(".selection-submit").click();
    await page.getByText(/g3_viewer_b accepted:/).waitFor();
    report.second_accepted = true;
    report.first_acceptance_preserved = await page.getByText(/g3_viewer_a accepted:/).count() === 1;
  } catch (error) {
    report.failure_stage = stage;
    report.failure_type = error?.name || "Error";
    if (error?.safeDetails) report.failure_details = error.safeDetails;
    if (stage === "second_select") {
      const roots = page.locator(".viewer-root");
      report.first_preview_length = Array.from(await roots.nth(0).locator(".selection-preview").innerText()).length;
      report.second_preview_length = Array.from(await roots.nth(1).locator(".selection-preview").innerText()).length;
      report.second_submit_enabled = await roots.nth(1).locator(".selection-submit:enabled").count() === 1;
      report.document_selection_length = await page.evaluate(() => Array.from(document.getSelection()?.toString() || "").length);
    }
  } finally {
    report.page_error_count = pageErrorCount;
    report.external_request_count = externalRequests.length;
    report.passed = report.viewer_count === 2
      && report.second_preview_empty_before_first_submit
      && report.second_submit_disabled_before_first_submit
      && report.first_accepted
      && report.first_preview_empty_before_second_submit
      && report.second_accepted
      && report.first_acceptance_preserved
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
