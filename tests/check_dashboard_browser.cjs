// Real Chromium verification of the existing dashboard, using SQL references.
const fs = require('fs');
const path = require('path');
const assert = require('assert');
const {pathToFileURL} = require('url');
const {chromium} = require('playwright');
const root = path.resolve(__dirname, '..');

(async () => {
  const options = {headless: true};
  if (process.env.CREDIT_RISK_CHROMIUM) {
    options.executablePath = process.env.CREDIT_RISK_CHROMIUM;
    options.args = ['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu'];
  }
  if (process.env.CREDIT_RISK_BROWSER_CHANNEL) {
    options.channel = process.env.CREDIT_RISK_BROWSER_CHANNEL;
  }
  const browser = await chromium.launch(options);
  const errors = [];
  const page = await browser.newPage({viewport: {width: 1440, height: 1050}});
  page.setDefaultTimeout(10000);
  page.on('pageerror', e => errors.push(e.message));
  const network = [];
  page.on('request', r => {if (/^https?:/.test(r.url())) network.push(r.url());});
  try {
    await page.goto(pathToFileURL(path.join(root, 'dashboard', 'index.html')).href);
    const cases = JSON.parse(fs.readFileSync(path.join(root, 'outputs', 'dashboard_reference.json')));
    const all = {date: '2026-09-30', product: 'all', stage: 'all', scenario: 'weighted'};
    async function choose(c, fast = false) {
      if (fast) {
        return page.evaluate(c => {
          for (const id of ['date', 'product', 'stage', 'scenario']) {
            document.getElementById(id).value = c[id];
          }
          document.getElementById('scenario').dispatchEvent(new Event('change', {bubbles: true}));
        }, c);
      }
      for (const id of ['date', 'product', 'stage', 'scenario']) {
        await page.selectOption('#' + id, c[id]);
      }
    }
    await choose(all);
    fs.mkdirSync(path.join(root, 'screenshots'), {recursive: true});
    await page.screenshot({path: path.join(root, 'screenshots', 'dashboard-overview.png'), fullPage: true});
    for (const c of cases) {
      await choose(c, true);
      const got = await page.evaluate(() => ({
        count: document.getElementById('k-loans').textContent,
        ead: document.getElementById('k-ead').textContent,
        ecl: document.getElementById('k-ecl').textContent,
        top: [...document.querySelectorAll('#top-body tr')].map(r => r.cells[0].textContent),
        svg: document.getElementById('trend').innerHTML
      }));
      assert.strictEqual(got.count, new Intl.NumberFormat('en-GB', {maximumFractionDigits: 0}).format(c.count));
      assert.strictEqual(got.ead, (c.ead / 1e6).toFixed(2) + 'm PLN');
      assert.strictEqual(got.ecl, (c.ecl / 1e6).toFixed(2) + 'm PLN');
      assert.deepStrictEqual(got.top, c.top);
      assert(!got.svg.includes('NaN'));
    }
    await choose({...all, product: 'credit_card', stage: '2', scenario: 'adverse'});
    await page.screenshot({path: path.join(root, 'screenshots', 'dashboard-filtered.png'), fullPage: true});
    const downloadPromise = page.waitForEvent('download');
    await page.click('#export');
    const download = await downloadPromise;
    assert.strictEqual(download.suggestedFilename(), 'credit_risk_top10.csv');
    const csv = fs.readFileSync(await download.path(), 'utf8');
    assert.strictEqual(csv.split('\r\n').length, 11);
    assert(csv.split('\r\n')[0].endsWith('ecl_adverse'));
    await choose(all);
    await page.setViewportSize({width: 390, height: 844});
    await page.screenshot({path: path.join(root, 'screenshots', 'dashboard-mobile.png'), fullPage: true});
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
           'Unexpected horizontal overflow on mobile');
    assert.deepStrictEqual(errors, []);
    assert.deepStrictEqual(network, []);
    const result = {
      browser: await browser.version(),
      loading: 'file:// with no server',
      independent_sql_filter_cases: cases.length,
      kpi_totals: 'pass',
      top10_rankings: 'pass',
      csv_download: 'pass',
      javascript_errors: errors.length,
      external_network_requests: network.length,
      desktop_viewport: '1440x1050',
      mobile_viewport: '390x844',
      horizontal_overflow: false
    };
    fs.writeFileSync(path.join(root, 'outputs', 'browser_checks.json'), JSON.stringify(result, null, 2));
    console.log(JSON.stringify(result));
  } finally {
    await browser.close();
  }
})().catch(e => {console.error(e); process.exitCode = 1;});
