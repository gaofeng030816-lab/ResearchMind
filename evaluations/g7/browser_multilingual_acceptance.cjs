const fs = require("fs");
const path = require("path");

const playwrightRoot = process.argv[2];
const origin = process.argv[3];
const codeRoot = process.argv[4];
const reportPath = process.argv[5];

if (!playwrightRoot || !origin || !codeRoot || !reportPath) {
  throw new Error(
    "usage: node browser_multilingual_acceptance.cjs <playwright-root> <origin> <code-root> <report-path>",
  );
}

const { chromium } = require(path.join(playwrightRoot, "node_modules", "playwright-core"));

const UI = {
  codeWorkspace: "\u4ee3\u7801\u5b66\u4e60\u4e0e\u590d\u73b0",
  codeFolder: "\u672c\u5730\u4ee3\u7801\u6587\u4ef6\u5939",
  openFolder: "\u6253\u5f00\u4ee3\u7801\u6587\u4ef6\u5939",
  indexedFive: "5 \u4e2a\u6e90\u7801\u6587\u4ef6",
  sourceFile: "\u6e90\u7801\u6587\u4ef6",
  selectCode: "\u9009\u62e9\u4ee3\u7801",
  selected: "\u5df2\u9009\u62e9",
  t5b1: "\u53d7\u63a7\u5355\u6587\u4ef6\u4fee\u6539\uff08T5-B1\uff09",
  readOnly:
    "\u5f53\u524d\u8bed\u8a00\u4ec5\u652f\u6301\u53ea\u8bfb\u9759\u6001\u7406\u89e3\uff1bT5-B1 \u539f\u5730\u4fee\u6539\u6743\u9650\u4ec5\u9002\u7528\u4e8e Python\u3002",
  localLibrary: "\u672c\u5730\u8d44\u6599\u5e93",
  zoteroDisabled: "\u5f53\u524d\u672a\u8fde\u63a5 Zotero",
};

function ensure(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

async function chooseSelectbox(page, label, option) {
  const selectbox = page.getByRole("combobox", { name: label, exact: true });
  await selectbox.click();
  await page.waitForTimeout(200);
  const exposedOption = page.getByRole("option", { name: option, exact: true });
  if ((await exposedOption.count()) > 0) {
    await exposedOption.click();
    return;
  }
  await page.keyboard.type(option);
  await page.keyboard.press("Enter");
}

(async () => {
  const externalRequests = [];
  const pageErrors = [];
  const checks = [];
  const browser = await chromium.launch({ channel: "msedge", headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });

  page.on("pageerror", (error) => pageErrors.push(String(error)));
  page.on("request", (request) => {
    const requestUrl = new URL(request.url());
    const target = new URL(origin);
    if (requestUrl.hostname !== target.hostname || requestUrl.port !== target.port) {
      externalRequests.push(request.url());
    }
  });

  try {
    await page.route("**/*", async (route) => {
      const requestUrl = new URL(route.request().url());
      const target = new URL(origin);
      if (requestUrl.hostname === target.hostname && requestUrl.port === target.port) {
        await route.continue();
      } else {
        await route.abort();
      }
    });

    await page.goto(origin, { waitUntil: "networkidle" });
    await page.getByText(UI.codeWorkspace, { exact: true }).click();
    await page.getByRole("textbox", { name: UI.codeFolder, exact: true }).fill(codeRoot);
    await page.getByRole("button", { name: UI.openFolder, exact: true }).click();
    await page.getByText(UI.indexedFive, { exact: false }).waitFor();
    checks.push("five_file_index");

    const bodyAfterIndex = await page.locator("body").innerText();
    for (const language of ["Python", "C", "Java", "Julia", "R"]) {
      ensure(bodyAfterIndex.includes(language), `missing indexed language: ${language}`);
    }
    checks.push("language_summary");

    const cases = [
      ["main.py", "Python", "ast", true],
      ["main.c", "C", "tree_sitter", false],
      ["Main.java", "Java", "tree_sitter", false],
      ["main.jl", "Julia", "tree_sitter", false],
      ["main.R", "R", "lexical", false],
    ];

    for (const [fileName, language, method, pythonWritable] of cases) {
      await chooseSelectbox(page, UI.sourceFile, fileName);
      await page.getByRole("button", { name: UI.selectCode, exact: true }).click();
      await page.getByText(`${UI.selected} ${fileName}:`, { exact: false }).first().waitFor();
      const body = await page.locator("body").innerText();
      ensure(
        body.includes(`\u00b7 ${language} \u00b7 ${method}`),
        `missing provenance for ${fileName}`,
      );
      if (pythonWritable) {
        ensure(body.includes(UI.t5b1), "Python T5-B1 control missing");
      } else {
        ensure(body.includes(UI.readOnly), `read-only authority warning missing for ${fileName}`);
        ensure(!body.includes(UI.t5b1), `T5-B1 leaked to ${fileName}`);
      }
      checks.push(`${language.toLowerCase()}_selection_provenance`);
    }

    await page.getByText(UI.localLibrary, { exact: true }).click();
    await page.waitForTimeout(1000);
    const libraryBody = await page.locator("body").innerText();
    ensure(libraryBody.includes(UI.zoteroDisabled), "Zotero disabled state missing");
    checks.push("zotero_disabled_graceful");

    ensure(externalRequests.length === 0, `external requests observed: ${externalRequests.join(", ")}`);
    ensure(pageErrors.length === 0, `page errors observed: ${pageErrors.join(", ")}`);
    checks.push("no_external_requests_or_page_errors");

    const report = {
      passed: true,
      checkedAt: new Date().toISOString(),
      origin,
      edgeVersion: browser.version(),
      checks,
      externalRequests,
      pageErrors,
    };
    fs.mkdirSync(path.dirname(reportPath), { recursive: true });
    fs.writeFileSync(reportPath, `${JSON.stringify(report, null, 2)}\n`, "utf8");
    process.stdout.write(`${JSON.stringify(report, null, 2)}\n`);
  } finally {
    await browser.close();
  }
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
