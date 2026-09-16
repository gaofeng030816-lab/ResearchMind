const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const {chromium} = require(process.argv[2] || "playwright");

const origin = process.argv[3] || "http://127.0.0.1:8514";
const vaultPath = path.resolve(process.argv[4]);
const outputPath = path.resolve(process.argv[5]);

function markdownFiles() {
  if (!fs.existsSync(vaultPath)) return [];
  return fs.readdirSync(vaultPath, {recursive: true})
    .filter(name => name.endsWith(".md"))
    .map(name => path.join(vaultPath, name));
}

async function openManagedPaper(page) {
  await page.getByRole("radio", {name: "本地资料库"}).click({force: true});
  await page.getByRole("heading", {name: "本地研究资料库"}).waitFor();
  await page.getByRole("button", {name: "打开论文"}).click();
  await page.getByRole("heading", {name: "1. 阅读论文"}).waitFor();
}

async function main() {
  const browser = await chromium.launch({channel: "msedge", headless: true});
  const context = await browser.newContext({viewport: {width: 1440, height: 1200}});
  const report = {
    browser: browser.version(),
    checks: [],
    errors: [],
    externalRequests: [],
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
    await openManagedPaper(page);

    await page.getByRole("textbox", {name: "选中文本"}).fill(
      "ResearchMind manual acceptance sentence"
    );
    await page.getByRole("button", {name: "确认选择"}).click();
    await page.getByText(/已定位/).waitFor();
    assert.equal(markdownFiles().length, 0);
    report.checks.push("selection alone does not create a Vault file");

    await page.getByRole("button", {name: "加入原文到证据篮"}).click();
    await page.getByText("原文已加入证据篮。").waitFor();
    await page.getByText(/来源修订仍为当前版本/).waitFor();
    assert.equal(markdownFiles().length, 0);
    report.checks.push("explicit evidence capture remains local-only");

    const title = page.getByRole("textbox", {name: "草稿标题"});
    const body = page.getByRole("textbox", {name: "可编辑 Markdown 正文"});
    await title.fill("G4 browser acceptance note");
    await body.fill("## 我的理解\n\n浏览器旅程中的显式正文。");
    await body.press("Tab");
    await page.getByText(/当前编辑尚未保存/).waitFor();
    await page.getByText(/旧预览已暂停使用/).waitFor();
    assert.equal(
      await page.getByRole("button", {name: "保存当前预览到 Obsidian Vault"}).count(),
      0
    );
    report.checks.push("unsaved editing cannot export an older preview");

    await page.getByRole("button", {name: "保存草稿到本地资料库"}).click();
    await page.getByRole("textbox", {name: "草稿标题"}).waitFor();
    assert.equal(markdownFiles().length, 0);
    report.checks.push("local draft save does not write the Vault");

    await page.getByRole("button", {name: "生成已保存版本预览"}).click();
    await page.getByText(/渲染预览（不会创建文件）/).waitFor();
    await page.getByRole("heading", {name: "我的理解", level: 2}).last().waitFor();
    await page.getByText(/current（仍匹配当前资料库修订）/).first().waitFor();
    assert.equal(markdownFiles().length, 0);
    report.checks.push("preview renders saved body and current provenance without output");

    await page.locator("label").filter({
      hasText: "我确认把上方这一版预览写入 Obsidian",
    }).click();
    await page.getByRole("button", {name: "保存当前预览到 Obsidian Vault"}).click();
    await page.getByText(/已保存：/).waitFor();
    const files = markdownFiles();
    assert.equal(files.length, 1);
    const markdown = fs.readFileSync(files[0], "utf8");
    assert.match(markdown, /# G4 browser acceptance note/);
    assert.match(markdown, /浏览器旅程中的显式正文/);
    assert.match(markdown, /ResearchMind manual acceptance sentence/);
    assert.match(markdown, /来源文件 SHA-256/);
    report.checks.push("confirmed export creates one traceable non-overwriting Markdown file");

    const secondContext = await browser.newContext({viewport: {width: 1440, height: 1200}});
    await secondContext.route("**/*", route => {
      const url = new URL(route.request().url());
      if (url.origin !== origin && !["blob:", "data:"].includes(url.protocol)) {
        report.externalRequests.push(url.origin);
        return route.abort();
      }
      return route.continue();
    });
    const restarted = await secondContext.newPage();
    restarted.setDefaultTimeout(30000);
    restarted.on("pageerror", error => report.errors.push(error.message));
    await restarted.goto(origin);
    await openManagedPaper(restarted);
    await restarted.getByRole("button", {name: "打开所选草稿"}).click();
    await restarted.getByRole("textbox", {name: "草稿标题"}).waitFor();
    assert.equal(
      await restarted.getByRole("textbox", {name: "草稿标题"}).inputValue(),
      "G4 browser acceptance note"
    );
    assert.match(
      await restarted.getByRole("textbox", {name: "可编辑 Markdown 正文"}).inputValue(),
      /浏览器旅程中的显式正文/
    );
    report.checks.push("a new browser session reopens the durable draft");
    await secondContext.close();

    assert.deepEqual(report.externalRequests, []);
    assert.deepEqual(report.errors, []);
    report.checks.push("journey produced no external request or page error");
  } finally {
    fs.writeFileSync(outputPath, JSON.stringify(report, null, 2));
    await context.close();
    await browser.close();
  }
}

main().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
