const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const {chromium} = require(process.argv[2] || "playwright");

const origin = "http://127.0.0.1:8504";
const pdfPath = path.resolve(process.argv[3]);
const output = path.resolve(process.argv[4] || ".release-tmp/g3-workspace-browser");

async function currentPage(page) {
  return Number(await page.getByRole("spinbutton", {name: "页码", exact: true}).inputValue());
}

async function wheelAt(page, locator, deltaY) {
  const box = await locator.boundingBox();
  if (!box) throw new Error("PDF scroller is not visible");
  await page.mouse.move(box.x + Math.min(box.width / 2, 280), box.y + Math.min(box.height / 2, 240));
  await page.mouse.wheel(0, deltaY);
}

async function observeDefaultPrevented(locator, action) {
  await locator.evaluate(element => {
    window.__g3LastWheelPrevented = null;
    element.addEventListener("wheel", event => {
      window.__g3LastWheelPrevented = event.defaultPrevented;
    }, {once: true});
  });
  await action();
  return locator.evaluate(() => window.__g3LastWheelPrevented);
}

async function main() {
  fs.mkdirSync(output, {recursive: true});
  const browser = await chromium.launch({channel: "msedge", headless: true});
  const context = await browser.newContext({viewport: {width: 1280, height: 1050}});
  const report = {browser: browser.version(), checks: [], errors: [], externalRequests: []};
  await context.route("**/*", route => {
    const url = new URL(route.request().url());
    if (url.origin !== origin) {
      report.externalRequests.push(url.origin);
      return route.abort();
    }
    return route.continue();
  });
  const page = await context.newPage();
  page.setDefaultTimeout(20000);
  page.on("pageerror", error => report.errors.push(error.message));
  try {
    await page.goto(origin);
    await page.locator('input[type="file"]').setInputFiles(pdfPath);
    await page.locator(".viewer-status").filter({hasText: "Page 1/2"}).waitFor();
    let scroller = page.locator(".viewer-scroll");

    const mainWidth = await page.getByTestId("stMainBlockContainer").evaluate(element => element.clientWidth);
    const paperOnlyWidth = await scroller.evaluate(element => element.clientWidth);
    assert.ok(paperOnlyWidth > mainWidth * 0.65, `${paperOnlyWidth} is not a full-width paper workspace`);
    report.checks.push("paper-only mode gives the PDF workspace the main content width");

    await scroller.click({position: {x: 40, y: 40}});
    await scroller.evaluate(element => { element.scrollTop = 0; });
    const firstPagePrevented = await observeDefaultPrevented(scroller, () => wheelAt(page, scroller, -120));
    await page.waitForTimeout(150);
    assert.equal(await currentPage(page), 1);
    assert.equal(firstPagePrevented, false);
    report.checks.push("first-page upward wheel is released and cannot leave document bounds");

    await scroller.evaluate(element => { element.scrollTop = 120; });
    await wheelAt(page, scroller, 120);
    await page.waitForTimeout(250);
    assert.equal(await currentPage(page), 1);
    assert.ok(await scroller.evaluate(element => element.scrollTop > 120));
    report.checks.push("ordinary wheel input scrolls inside the focused PDF instead of turning mid-page");

    await scroller.evaluate(element => { element.scrollTop = element.scrollHeight; });
    await page.getByRole("heading", {name: "G3 PDF 工作区实验"}).click();
    const unfocusedPrevented = await observeDefaultPrevented(scroller, () => wheelAt(page, scroller, 120));
    await page.waitForTimeout(150);
    assert.equal(await currentPage(page), 1);
    assert.equal(unfocusedPrevented, false);
    report.checks.push("wheel over an unfocused viewer never requests a page turn");

    await scroller.click({position: {x: 40, y: 40}});
    await scroller.evaluate(element => { element.scrollTop = element.scrollHeight; });
    await page.keyboard.down("Control");
    const modifiedPrevented = await observeDefaultPrevented(scroller, () => wheelAt(page, scroller, 120));
    await page.keyboard.up("Control");
    await page.waitForTimeout(150);
    assert.equal(await currentPage(page), 1);
    assert.equal(modifiedPrevented, false);
    report.checks.push("Ctrl+wheel remains available for browser zoom semantics");

    const firstSmallPrevented = await observeDefaultPrevented(scroller, () => wheelAt(page, scroller, 30));
    await wheelAt(page, scroller, 30);
    await page.waitForTimeout(40);
    assert.equal(await currentPage(page), 1);
    await wheelAt(page, scroller, 30);
    await page.locator(".viewer-status").filter({hasText: "Page 2/2"}).waitFor();
    assert.equal(firstSmallPrevented, true);
    report.checks.push("three small edge bursts cross the 80px threshold and request one adjacent page");

    scroller = page.locator(".viewer-scroll");
    await scroller.evaluate(element => { element.scrollTop = element.scrollHeight; });
    const lastPagePrevented = await observeDefaultPrevented(scroller, () => wheelAt(page, scroller, 120));
    await page.waitForTimeout(250);
    assert.equal(await currentPage(page), 2);
    assert.equal(lastPagePrevented, false);
    report.checks.push("last-page downward wheel is not captured and cannot exceed document bounds");

    await page.waitForTimeout(950);
    scroller = page.locator(".viewer-scroll");
    await scroller.click({position: {x: 40, y: 40}});
    await scroller.evaluate(element => { element.scrollTop = 0; });
    await wheelAt(page, scroller, -90);
    await page.locator(".viewer-status").filter({hasText: "Page 1/2"}).waitFor();
    scroller = page.locator(".viewer-scroll");
    const reversePosition = await scroller.evaluate(element => ({
      top: element.scrollTop,
      bottom: element.scrollHeight - element.clientHeight,
    }));
    assert.ok(reversePosition.bottom <= 2 || reversePosition.top >= reversePosition.bottom - 2);
    report.checks.push("reverse edge gesture returns one page and restores the previous page bottom");

    await scroller.evaluate(element => { element.scrollTop = 0; });
    const target = page.locator(".textLayer span").filter({hasText: "Select this exact sentence"}).first();
    const points = await target.evaluate(element => {
      const node = element.firstChild;
      return [0, 6].map(offset => {
        const range = document.createRange();
        range.setStart(node, offset);
        range.setEnd(node, offset);
        const box = range.getBoundingClientRect();
        return {x: box.x + 0.1, y: box.y + box.height / 2};
      });
    });
    await page.mouse.move(points[0].x, points[0].y);
    await page.mouse.down();
    await page.mouse.move(points[1].x, points[1].y, {steps: 12});
    await page.mouse.up();
    await page.locator(".selection-submit:enabled").waitFor();
    await scroller.evaluate(element => { element.scrollTop = element.scrollHeight; });
    const pendingPrevented = await observeDefaultPrevented(scroller, () => wheelAt(page, scroller, 120));
    await page.waitForTimeout(250);
    assert.equal(await currentPage(page), 1);
    assert.equal(pendingPrevented, false);
    report.checks.push("a pending text selection suppresses page turns without trapping the wheel event");
    await page.locator(".selection-submit").click();
    await page.getByText("已通过 PyMuPDF 文字与几何对账的实验选择", {exact: true}).waitFor();

    await page.getByRole("heading", {name: "G3 PDF 工作区实验"}).click();
    await page.keyboard.press("Control+Shift+A");
    await page.getByRole("heading", {name: "AI 面板（无网络占位）"}).waitFor();
    const aiInput = page.getByRole("textbox", {name: "实验 AI 问题"});
    await aiInput.fill("typing owns this shortcut");
    await aiInput.press("Control+Shift+A");
    await page.waitForTimeout(250);
    assert.equal(await page.getByRole("heading", {name: "AI 面板（无网络占位）"}).count(), 1);
    assert.equal(await aiInput.inputValue(), "typing owns this shortcut");
    await page.getByRole("heading", {name: "G3 PDF 工作区实验"}).click();
    await page.keyboard.press("Control+Shift+A");
    await page.getByRole("heading", {name: "AI 面板（无网络占位）"}).waitFor({state: "detached"});
    await page.getByRole("heading", {name: "G3 PDF 工作区实验"}).dispatchEvent("keydown", {
      key: "A", ctrlKey: true, shiftKey: true, repeat: true, bubbles: true, composed: true,
    });
    await page.waitForTimeout(150);
    assert.equal(await page.getByRole("heading", {name: "AI 面板（无网络占位）"}).count(), 0);
    report.checks.push("Ctrl+Shift+A toggles the placeholder but is suppressed while an input owns focus");

    await page.getByText("论文 + 代码", {exact: true}).click();
    await page.getByRole("heading", {name: "代码阅读区（静态占位）"}).waitFor();
    const paperColumn = page.getByRole("heading", {name: "论文阅读区"})
      .locator('xpath=ancestor::*[@data-testid="stColumn"][1]');
    const codeColumn = page.getByRole("heading", {name: "代码阅读区（静态占位）"})
      .locator('xpath=ancestor::*[@data-testid="stColumn"][1]');
    const desktopPaper = await paperColumn.boundingBox();
    const desktopCode = await codeColumn.boundingBox();
    assert.ok(desktopPaper && desktopCode);
    assert.ok(desktopCode.x > desktopPaper.x + desktopPaper.width * 0.8);
    assert.ok(Math.abs(desktopCode.y - desktopPaper.y) < 10);
    report.checks.push("paper-plus-code mode forms distinct same-row columns on desktop");

    const codeNotes = page.getByRole("textbox", {name: "代码阅读备注"});
    await codeNotes.fill("editor focus remains local");
    await codeNotes.press("Control+Shift+A");
    await page.waitForTimeout(150);
    assert.equal(await page.getByRole("heading", {name: "AI 面板（无网络占位）"}).count(), 0);
    assert.equal(await codeNotes.inputValue(), "editor focus remains local");
    report.checks.push("the code-note editor also owns Ctrl+Shift+A while focused");

    await page.setViewportSize({width: 600, height: 900});
    await page.waitForTimeout(350);
    const narrowPaper = await paperColumn.boundingBox();
    const narrowCode = await codeColumn.boundingBox();
    assert.ok(narrowPaper && narrowCode);
    assert.ok(narrowCode.y > narrowPaper.y + 100);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    assert.ok(overflow <= 1, `narrow layout overflows by ${overflow}px`);
    report.checks.push("native columns stack on a 600px viewport without document overflow");

    await page.screenshot({path: path.join(output, "workspace-narrow.png"), fullPage: true});
    assert.deepEqual(report.errors, []);
    assert.deepEqual(report.externalRequests, []);
    report.passed = true;
  } catch (error) {
    report.passed = false;
    report.failure = String(error);
    report.uiText = await page.locator("body").innerText().catch(() => "");
    await page.screenshot({path: path.join(output, "failure.png"), fullPage: true});
    process.exitCode = 1;
  } finally {
    fs.writeFileSync(path.join(output, "report.json"), JSON.stringify(report, null, 2));
    console.log(JSON.stringify(report));
    await browser.close();
  }
}

main().catch(error => { console.error(error); process.exitCode = 1; });
