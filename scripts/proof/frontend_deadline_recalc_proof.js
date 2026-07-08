const path = require('path');
const helpers = require('./frontend_playwright_helpers');

async function main() {
  const browser = await helpers.launchBrowser();
  const context = await browser.newContext({ viewport: { width: 1440, height: 1400 } });
  await helpers.wireApiBase(context);
  await helpers.setupMockAuth(context, '33333333-3333-3333-3333-333333333333');
  const page = await context.newPage();

  let rulesPayload = null;
  page.on('response', async (response) => {
    if (response.url().includes('/rules/unfair_dismissal') && response.ok()) {
      try {
        rulesPayload = await response.json();
      } catch (_) {
        // ignore parse noise
      }
    }
  });

  try {
    await page.goto(`${helpers.BASE_URL}/pages/deadlines.html`, { waitUntil: 'networkidle' });
    await page.waitForFunction(
      () => {
        const content = document.getElementById('dl-content');
        return !!content && getComputedStyle(content).display !== 'none';
      },
      {},
      { timeout: 20000 }
    );
    await page.fill('#event_date', '2026-04-01');
    await page.waitForFunction(
      () => {
        const strong = document.querySelector('#deadline-widget strong')?.textContent || '';
        const note = document.getElementById('dl-note')?.textContent || '';
        return strong.length > 0 && note.includes('server rule set');
      },
      {},
      { timeout: 20000 }
    );

    const before = await page.evaluate(() => ({
      date: document.querySelector('#deadline-widget strong')?.textContent || '',
      note: document.getElementById('dl-note')?.textContent || '',
      summary: document.querySelector('#deadline-widget .cos-card')?.innerText || '',
    }));

    await page.fill('#event_date', '2026-05-15');
    await page.waitForFunction(
      (previous) => (document.querySelector('#deadline-widget strong')?.textContent || '') !== previous,
      before.date,
      { timeout: 20000 }
    );

    const after = await page.evaluate(() => ({
      date: document.querySelector('#deadline-widget strong')?.textContent || '',
      note: document.getElementById('dl-note')?.textContent || '',
      summary: document.querySelector('#deadline-widget .cos-card')?.innerText || '',
    }));

    const shotPath = path.join(process.cwd(), 'reports', 'frontend_deadline_recalc.png');
    await page.screenshot({ path: shotPath, fullPage: true });

    helpers.writeJson(
      path.join(process.cwd(), 'reports', 'frontend_deadline_recalc_proof.json'),
      {
        generated_at: new Date().toISOString(),
        auth_mode: 'mock-header',
        screenshot: shotPath,
        input_dates: {
          first: '2026-04-01',
          second: '2026-05-15',
        },
        before,
        after,
        rules_response: rulesPayload,
      }
    );
  } finally {
    await context.close();
    await browser.close();
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
