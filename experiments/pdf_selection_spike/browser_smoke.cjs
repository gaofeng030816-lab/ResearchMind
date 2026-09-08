// Explicit opt-in local browser checks; never run by the routine pytest suite.
// Usage: node browser_smoke.cjs <path-to-installed-playwright> [output-directory]
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require(process.argv[2] || 'playwright');
const output = path.resolve(process.argv[3] || '.release-tmp/g3-browser');
const origin = 'http://127.0.0.1:8503';

async function main() {
  fs.mkdirSync(output, {recursive: true});
  const browser = await chromium.launch({channel: 'msedge', headless: true});
  const context = await browser.newContext({viewport: {width: 1280, height: 1000}});
  const report = {browser: browser.version(), checks: [], errors: [], externalRequests: []};
  await context.route('**/*', route => {
    const url = new URL(route.request().url());
    if (url.origin !== origin) {
      report.externalRequests.push(url.origin);
      return route.abort();
    }
    return route.continue();
  });
  const page = await context.newPage();
  page.setDefaultTimeout(10000);
  page.on('pageerror', error => report.errors.push(error.message));
  try {
    await page.goto(origin);
    await page.locator('#page .span').first().waitFor({timeout: 20000});
    async function drag(index, start, end) {
      const span = page.locator('#page .span').nth(index);
      await span.scrollIntoViewIfNeeded();
      const points = await span.evaluate((element, offsets) => {
        const node = element.firstChild;
        return offsets.map(offset => {
          const range = document.createRange();
          range.setStart(node, offset); range.setEnd(node, offset);
          const box = range.getBoundingClientRect();
          return {x: box.x + 0.1, y: box.y + box.height / 2};
        });
      }, [start, end]);
      await page.mouse.move(points[0].x, points[0].y);
      await page.mouse.down();
      await page.mouse.move(points[1].x, points[1].y, {steps: 12});
      await page.mouse.up();
      await page.locator('#submit:enabled').waitFor();
    }
    async function submit(expected) {
      assert.equal(await page.locator('#preview').innerText(), expected);
      await page.locator('#submit').click();
      await page.getByTestId('stCode').filter({hasText: expected}).waitFor();
      assert.equal(await page.getByTestId('stCode').locator('code').innerText(), expected);
    }
    async function choose(label, value) {
      await page.getByRole('combobox', {name: label, exact: true}).click();
      await page.getByRole('option', {name: value, exact: true}).click();
    }
    await drag(0, 0, 6);
    await submit('Select');
    report.checks.push('real mouse selection and Python acknowledgement');
    await page.getByRole('button', {name: '仅重新运行（保留已验证选择）', exact: true}).click();
    await page.getByTestId('stCode').filter({hasText: 'Select'}).waitFor();
    report.checks.push('accepted text survives rerun');
    await choose('合成样本', 'unicode');
    await page.locator('#page .span').first().filter({hasText: 'A😀积分'}).waitFor();
    await page.getByTestId('stCode').waitFor({state: 'detached'});
    await drag(0, 1, 5);
    await submit('😀积分');
    report.checks.push('Unicode mouse offsets and source invalidation');
    await page.screenshot({path: path.join(output, 'unicode.png'), fullPage: true});
    await choose('实验页码', '2');
    await page.locator('#page .span').first().filter({hasText: 'Page two.'}).waitFor();
    await page.getByTestId('stCode').waitFor({state: 'detached'});
    report.checks.push('page switch clears accepted selection');
    await choose('实验页码', '1');
    await choose('合成样本', 'columns');
    await page.locator('#page.columns').waitFor();
    await drag(2, 0, 12);
    await submit('Right column');
    report.checks.push('right-column source mapping');
    await page.setViewportSize({width: 480, height: 900});
    await page.locator('#page').scrollIntoViewIfNeeded();
    await page.screenshot({path: path.join(output, 'narrow.png'), fullPage: true});
    const width = await page.evaluate(() => ({client:document.documentElement.clientWidth,
                                            scroll:document.documentElement.scrollWidth}));
    assert.ok(width.scroll <= width.client + 1, 'Unexpected horizontal overflow');
    report.checks.push('480px viewport without document horizontal overflow');
    await choose('合成样本', 'empty');
    await page.locator('#page').filter({hasText: '无文字层'}).waitFor();
    assert.ok(await page.locator('#submit').isDisabled());
    report.checks.push('empty page submission disabled');
    assert.deepEqual(report.errors, []);
    report.passed = true;
  } catch (error) {
    report.passed = false;
    report.failure = String(error);
    report.uiText = await page.locator('body').innerText();
    report.selectionDiagnostic = await page.locator('#page').evaluate(element => {
      const root = element.getRootNode();
      const selection = document.getSelection();
      const composed = selection.getComposedRanges({shadowRoots: [root]});
      const local = root.getSelection?.();
      return {globalCollapsed: selection.isCollapsed, globalText: selection.toString(),
        localCollapsed: local?.isCollapsed, localText: local?.toString(),
        root: root.nodeName, ranges: composed.map(r => ({
          start: r.startContainer.nodeName, end: r.endContainer.nodeName,
          startOffset: r.startOffset, endOffset: r.endOffset,
          startOwned: element.contains(r.startContainer), endOwned: element.contains(r.endContainer)
        }))};
    }).catch(() => null);
    await page.screenshot({path: path.join(output, 'failure.png'), fullPage: true});
    console.error(String(error));
    process.exitCode = 1;
  } finally {
    fs.writeFileSync(path.join(output, 'report.json'), JSON.stringify(report, null, 2));
    console.log(JSON.stringify(report));
    await browser.close();
  }
}
main().catch(error => { console.error(error); process.exitCode = 1; });
