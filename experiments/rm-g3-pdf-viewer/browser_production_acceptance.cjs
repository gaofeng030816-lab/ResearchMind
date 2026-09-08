const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const {chromium} = require(process.argv[2] || "playwright");

const pdfPath = path.resolve(process.argv[3]);
const codePath = path.resolve(process.argv[4]);
const output = path.resolve(process.argv[5] || ".release-tmp/g3-production-browser");
const origin = process.argv[6] || "http://127.0.0.1:8505";

async function currentPage(page) {
  const input = page.getByRole("spinbutton", {name: "页码（加减后立即跳转）"});
  return Number(await input.inputValue());
}

async function wheelAt(page, locator, deltaY) {
  const box = await locator.boundingBox();
  if (!box) throw new Error("PDF scroller is not visible");
  await page.mouse.move(box.x + Math.min(box.width / 2, 260), box.y + Math.min(box.height / 2, 220));
  await page.mouse.wheel(0, deltaY);
}

async function main() {
  fs.mkdirSync(output, {recursive: true});
  const browser = await chromium.launch({channel: "msedge", headless: true});
  const context = await browser.newContext({viewport: {width: 1440, height: 1100}});
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
  page.setDefaultTimeout(30000);
  page.on("pageerror", error => report.errors.push(error.message));
  try {
    await page.goto(origin);
    await page.getByRole("textbox", {name: "本地 PDF 路径"}).fill(pdfPath);
    await page.getByRole("button", {name: "打开 PDF"}).click();
    await page.locator(".viewer-status").filter({hasText: "Page 1/2"}).waitFor();

    let scroller = page.locator(".viewer-scroll");
    const mainWidth = await page.getByTestId("stMainBlockContainer").evaluate(element => element.clientWidth);
    const paperWidth = await scroller.evaluate(element => element.clientWidth);
    assert.ok(paperWidth > mainWidth * 0.65);
    report.checks.push("formal paper-only workspace gives the PDF the main content width");

    const target = page.locator(".textLayer span").filter({hasText: "Select this exact sentence"}).first();
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
    await page.locator(".selection-preview").filter({hasText: "Select"}).waitFor();
    await page.locator(".selection-submit:enabled").waitFor();
    assert.equal(await page.locator(".selection-preview").innerText(), "Select");
    await page.locator(".selection-submit").click();
    await page.getByText(/已验证第 1 页的 PDF 文字层选择/).waitFor();
    assert.equal(await page.getByRole("textbox", {name: "选中文本"}).inputValue(), "Select");
    assert.match(await page.locator("body").innerText(), /PDF\.js 文字层 \/ PyMuPDF 服务端对账/);
    report.checks.push("formal real-mouse selection reaches ReadingSelection only after server reconciliation");

    scroller = page.locator(".viewer-scroll");
    await scroller.click({position: {x: 40, y: 40}});
    await scroller.evaluate(element => { element.scrollTop = Math.min(8, element.scrollHeight); });
    await wheelAt(page, scroller, 30);
    await page.waitForTimeout(250);
    assert.equal(await currentPage(page), 1);
    report.checks.push("formal mid-page wheel remains ordinary scrolling");

    scroller = page.locator(".viewer-scroll");
    await scroller.evaluate(element => { element.scrollTop = element.scrollHeight; });
    await wheelAt(page, scroller, 30);
    await wheelAt(page, scroller, 30);
    await wheelAt(page, scroller, 30);
    await page.locator(".viewer-status").filter({hasText: "Page 2/2"}).waitFor();
    assert.equal(await currentPage(page), 2);
    report.checks.push("formal edge bursts produce one adjacent debounced page turn");

    scroller = page.locator(".viewer-scroll");
    await scroller.click({position: {x: 40, y: 40}});
    await scroller.evaluate(element => { element.scrollTop = element.scrollHeight; });
    await wheelAt(page, scroller, 120);
    await page.waitForTimeout(250);
    assert.equal(await currentPage(page), 2);
    report.checks.push("formal last-page wheel is released at document bounds");

    await page.getByRole("heading", {name: "ResearchMind"}).click();
    await page.keyboard.press("Control+Shift+A");
    await page.getByRole("heading", {name: "AI 研究面板"}).waitFor({state: "detached"});
    const pathInput = page.getByRole("textbox", {name: "本地 PDF 路径"});
    await pathInput.press("Control+Shift+A");
    await page.waitForTimeout(200);
    assert.equal(await page.getByRole("heading", {name: "AI 研究面板"}).count(), 0);
    await page.getByRole("heading", {name: "ResearchMind"}).click();
    await page.keyboard.press("Control+Shift+A");
    await page.getByRole("heading", {name: "AI 研究面板"}).waitFor();
    report.checks.push("formal Ctrl+Shift+A toggles AI and is suppressed while typing");

    await page.getByText("代码学习与复现", {exact: true}).click();
    await page.getByRole("textbox", {name: "本地代码文件夹"}).fill(codePath);
    await page.getByRole("button", {name: "打开代码文件夹"}).click();
    await page.getByText(/已只读索引：/).waitFor();
    await page.getByText("论文阅读与笔记", {exact: true}).click();
    await page.getByRole("heading", {name: "代码学习与科研复现"}).waitFor();
    const paperColumn = page.getByRole("heading", {name: "1. 阅读论文"})
      .locator('xpath=ancestor::*[@data-testid="stColumn"][1]');
    const codeColumn = page.getByRole("heading", {name: "代码学习与科研复现"})
      .locator('xpath=ancestor::*[@data-testid="stColumn"][1]');
    const desktopPaper = await paperColumn.boundingBox();
    const desktopCode = await codeColumn.boundingBox();
    assert.ok(desktopPaper && desktopCode && desktopCode.x > desktopPaper.x);
    assert.ok(Math.abs(desktopCode.y - desktopPaper.y) < 10);
    report.checks.push("formal paper-plus-code workspace forms desktop columns");

    await page.setViewportSize({width: 600, height: 900});
    await page.waitForTimeout(350);
    const narrowPaper = await paperColumn.boundingBox();
    const narrowCode = await codeColumn.boundingBox();
    assert.ok(narrowPaper && narrowCode && narrowCode.y > narrowPaper.y + 100);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    assert.ok(overflow <= 1, `narrow layout overflows by ${overflow}px`);
    report.checks.push("formal 600px workspace stacks without horizontal overflow");

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
