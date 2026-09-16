const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const {chromium} = require(process.argv[2] || "playwright");

const origin = process.argv[3] || "http://127.0.0.1:8515";
const pdfPath = path.resolve(process.argv[4]);
const outputPath = path.resolve(process.argv[5]);
const runFullFakeFlow = process.argv[6] === "--full-fake";

async function main() {
  const browser = await chromium.launch({channel: "msedge", headless: true});
  const context = await browser.newContext({viewport: {width: 1440, height: 1200}});
  const report = {
    browser: browser.version(),
    checks: [],
    errors: [],
    externalRequests: [],
    cropSha256: null,
    fullFakeFlow: runFullFakeFlow,
    failure: null,
  };
  await context.route("**/*", route => {
    const url = new URL(route.request().url());
    if (url.origin !== origin && !["blob:", "data:"].includes(url.protocol)) {
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
    await page.getByRole("heading", {name: "ResearchMind", exact: true}).waitFor();
    await page.getByRole("textbox", {name: "本地 PDF 路径"}).fill(pdfPath);
    await page.getByRole("button", {name: "打开 PDF"}).click();
    await page.getByText(/20 页/).first().waitFor();
    report.checks.push("the synthetic 20-page PDF opens in the paper workspace");

    const pageNumber = page.getByRole("spinbutton", {name: "页码（加减后立即跳转）"});
    await pageNumber.fill("5");
    await pageNumber.press("Tab");
    await page.waitForFunction(() => {
      const input = document.querySelector('input[aria-label="页码（加减后立即跳转）"]');
      return input && input.value === "5";
    });
    await page.getByRole("heading", {name: "1. 阅读论文"}).waitFor();
    await page.waitForTimeout(1000);
    report.checks.push("page navigation reaches the finite-sum page");

    const formulaCard = page.getByText("公式识别（单公式）", {exact: true});
    if (!(await formulaCard.isVisible().catch(() => false))) {
      const aiToggle = page.locator("button").filter({hasText: "AI 面板"}).first();
      if (await aiToggle.count() === 0) {
        const labels = await page.locator("button").allInnerTexts();
        throw new Error(`AI panel toggle is missing; buttons: ${labels.join(" | ")}`);
      }
      await aiToggle.click();
    }
    await formulaCard.waitFor();
    await page.getByRole("button", {name: "扫描当前页公式"}).click();
    await page.getByText(/当前页发现 1 个候选区域/).waitFor();
    report.checks.push("local detector finds one bounded formula region");

    await page.getByRole("button", {name: "生成并检查公式裁剪"}).click();
    const transferPreview = page.getByText(/本次固定裁剪 SHA-256：[0-9a-f]{64}/);
    await transferPreview.waitFor();
    const previewText = await transferPreview.textContent();
    const hashMatch = previewText.match(/SHA-256：([0-9a-f]{64})/);
    assert.ok(hashMatch, "the transfer preview must expose an exact crop hash");
    report.cropSha256 = hashMatch[1];
    await page.getByText(/不会发送 PDF 路径、整篇 PDF、正文、对话或笔记/).waitFor();
    report.checks.push("crop preview exposes exact hash and bounded transfer scope");

    const recognizeButton = page.getByRole("button", {name: "识别这一个公式"});
    assert.equal(await recognizeButton.isDisabled(), true);
    assert.equal(
      await page.getByRole("textbox", {name: /检查并编辑 LaTeX/}).count(),
      0,
    );
    report.checks.push("recognition and candidate editing stay unavailable before consent");

    const consent = page.getByRole("checkbox", {
      name: "我确认仅将上方这张公式裁剪发送到外部识别服务",
    });
    await consent.focus();
    await consent.press("Space");
    await page.waitForFunction(() => {
      const checkbox = document.querySelector(
        'input[aria-label="我确认仅将上方这张公式裁剪发送到外部识别服务"]',
      );
      return checkbox && checkbox.checked;
    });
    await page.waitForTimeout(750);
    assert.equal(await recognizeButton.isEnabled(), true);
    report.checks.push("exact-crop consent enables only the explicit recognition button");

    if (runFullFakeFlow) {
      await recognizeButton.click();
      const editor = page.getByRole("textbox", {name: /检查并编辑 LaTeX/});
      await editor.waitFor();
      assert.equal(
        await editor.inputValue(),
        "\\sum_{i=1}^{n} i = \\frac{n(n+1)}{2}",
      );
      assert.equal(
        await page.getByRole("button", {name: "加入公式到证据篮"}).count(),
        0,
      );
      report.checks.push("recognizer output remains editable and unsaved before acceptance");

      await page.getByRole("button", {name: "接受当前 LaTeX"}).click();
      await page.getByText("LaTeX 已通过安全校验并由你接受。").waitFor();
      const addEvidence = page.getByRole("button", {name: "加入公式到证据篮"});
      await addEvidence.waitFor();
      assert.equal(await addEvidence.isEnabled(), true);
      report.checks.push("explicit acceptance unlocks rendering and evidence capture");

      await addEvidence.click();
      await page.getByText("已接受的公式 LaTeX 已加入证据篮。").waitFor();
      await page.getByText(/\d+\. LaTeX/, {exact: true}).last().waitFor();
      report.checks.push("only accepted LaTeX enters the persistent evidence basket");
    }

    assert.deepEqual(report.externalRequests, []);
    assert.deepEqual(report.errors, []);
    report.checks.push("the pre-recognition journey produces no external request or page error");
  } catch (error) {
    report.failure = {
      name: error && error.name ? error.name : "Error",
      message: error && error.message ? error.message : String(error),
    };
    throw error;
  } finally {
    fs.writeFileSync(outputPath, JSON.stringify(report, null, 2) + "\n");
    await context.close();
    await browser.close();
  }
}

main().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
