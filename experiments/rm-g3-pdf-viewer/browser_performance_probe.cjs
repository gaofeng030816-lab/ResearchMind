const fs = require("node:fs");
const path = require("node:path");
const {chromium} = require(process.argv[2] || "playwright");

const origin = "http://127.0.0.1:8504";
const pdfPath = path.resolve(process.argv[3]);
const outputPath = path.resolve(process.argv[4]);

function elapsed(start) {
  return Math.round((performance.now() - start) * 100) / 100;
}

async function heapBytes(page) {
  return page.evaluate(() => Number(performance.memory?.usedJSHeapSize || 0));
}

async function settledHeapBytes(page, cdp) {
  await page.waitForTimeout(1500);
  await cdp.send("HeapProfiler.collectGarbage");
  await page.waitForTimeout(100);
  return heapBytes(page);
}

async function main() {
  const browser = await chromium.launch({channel: "msedge", headless: true});
  const context = await browser.newContext({viewport: {width: 1280, height: 1050}});
  const externalRequests = [];
  await context.route("**/*", route => {
    const url = new URL(route.request().url());
    if (url.origin !== origin) { externalRequests.push(url.origin); return route.abort(); }
    return route.continue();
  });
  const page = await context.newPage();
  const cdp = await context.newCDPSession(page);
  page.setDefaultTimeout(60000);
  let pageErrorCount = 0;
  page.on("pageerror", () => { pageErrorCount += 1; });
  const report = {
    schema_version: 1,
    browser: browser.version(),
    pdf_bytes: fs.statSync(pdfPath).size,
  };
  let stage = "open";
  try {
    await page.goto(origin);
    report.heap_before_upload_bytes = await settledHeapBytes(page, cdp);
    stage = "initial_render";
    let started = performance.now();
    await page.locator('input[type="file"]').setInputFiles(pdfPath);
    const initialStatus = page.locator(".viewer-status").filter({hasText: /Page 1\/\d+/});
    await initialStatus.waitFor();
    report.initial_render_ms = elapsed(started);
    const status = await initialStatus.innerText();
    report.page_count = Number(/Page 1\/(\d+)/.exec(status)?.[1] || 0);
    report.page_one_text_items = Number(/; (\d+) text items;/.exec(status)?.[1] || 0);
    report.page_one_resource = /resource (opened|reused)/.exec(status)?.[1] || "unknown";
    report.page_one_payload = await page.locator(".viewer-root").getAttribute("data-pdf-payload") || "unknown";
    report.heap_after_initial_bytes = await settledHeapBytes(page, cdp);

    const pageInput = page.getByRole("spinbutton", {name: "页码", exact: true});
    stage = "jump_page_20";
    started = performance.now();
    await pageInput.fill("20");
    await pageInput.press("Enter");
    const pageTwentyStatus = page.locator(".viewer-status").filter({hasText: `Page 20/${report.page_count}`});
    await pageTwentyStatus.waitFor();
    report.jump_page_20_ms = elapsed(started);
    report.page_twenty_text_items = Number(/; (\d+) text items;/.exec(await pageTwentyStatus.innerText())?.[1] || 0);
    report.page_twenty_resource = /resource (opened|reused)/.exec(await pageTwentyStatus.innerText())?.[1] || "unknown";
    report.page_twenty_payload = await page.locator(".viewer-root").getAttribute("data-pdf-payload") || "unknown";
    report.heap_after_page_20_bytes = await settledHeapBytes(page, cdp);

    stage = "next_page_21";
    started = performance.now();
    await pageInput.fill("21");
    await pageInput.press("Enter");
    const pageTwentyOneStatus = page.locator(".viewer-status").filter({hasText: `Page 21/${report.page_count}`});
    await pageTwentyOneStatus.waitFor();
    report.next_page_21_ms = elapsed(started);
    report.page_twenty_one_resource = /resource (opened|reused)/.exec(await pageTwentyOneStatus.innerText())?.[1] || "unknown";
    report.page_twenty_one_payload = await page.locator(".viewer-root").getAttribute("data-pdf-payload") || "unknown";
    report.heap_after_page_21_bytes = await settledHeapBytes(page, cdp);
  } catch (error) {
    report.failure_stage = stage;
    report.failure_type = error?.name || "Error";
  } finally {
    report.page_error_count = pageErrorCount;
    report.external_request_count = externalRequests.length;
    report.measurement_completed = report.page_count >= 21
      && Number.isFinite(report.initial_render_ms)
      && Number.isFinite(report.jump_page_20_ms)
      && Number.isFinite(report.next_page_21_ms)
      && pageErrorCount === 0
      && externalRequests.length === 0;
    fs.mkdirSync(path.dirname(outputPath), {recursive: true});
    fs.writeFileSync(outputPath, JSON.stringify(report, null, 2));
    console.log(JSON.stringify(report));
    await browser.close();
  }
  if (!report.measurement_completed) process.exitCode = 1;
}

main().catch(error => { console.error(error?.name || "Error"); process.exitCode = 1; });
