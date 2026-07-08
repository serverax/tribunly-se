const path = require('path');
const helpers = require('./frontend_playwright_helpers');

async function createContext(browser, userId) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 1400 } });
  await helpers.wireApiBase(context);
  await helpers.setupMockAuth(context, userId);
  return context;
}

async function main() {
  const browser = await helpers.launchBrowser();
  const userId = '22222222-2222-2222-2222-222222222222';
  const noteTitle = 'Persistence proof note';
  const noteBody = 'State restored intact after a fresh browser context.';
  const storagePath = path.join(process.cwd(), 'reports', 'frontend_persistence_storage_state.json');
  const beforeShot = path.join(process.cwd(), 'reports', 'frontend_persistence_before.png');
  const restoredShot = path.join(process.cwd(), 'reports', 'frontend_persistence_restored.png');

  let firstContext = await createContext(browser, userId);
  try {
    const firstPage = await firstContext.newPage();
    await firstPage.goto(`${helpers.BASE_URL}/pages/login.html`, { waitUntil: 'networkidle' });
    const created = await helpers.createCaseWithAssessment(firstPage, {
      assessment: { reasoning_summary: 'Persistent workspace state proof case.' },
    });
    const caseId = created.case_id;

    await firstPage.goto(`${helpers.BASE_URL}/pages/workspace.html?case_id=${encodeURIComponent(caseId)}#notes`, {
      waitUntil: 'networkidle',
    });
    await firstPage.waitForSelector('#ws-workspace', { timeout: 20000 });
    await firstPage.fill('#ws-note-title', noteTitle);
    await firstPage.fill('#ws-note-body', noteBody);
    await firstPage.click('#ws-note-save');
    await firstPage.waitForFunction(
      ({ noteTitle, noteBody }) => {
        const text = document.querySelector('#ws-notes-list')?.innerText || '';
        return text.includes(noteTitle) && text.includes(noteBody);
      },
      { noteTitle, noteBody },
      { timeout: 20000 }
    );
    await firstPage.screenshot({ path: beforeShot, fullPage: true });

    const beforeState = await firstPage.evaluate(() => ({
      activeCaseId: localStorage.getItem('lawapp_active_case_id'),
      heading: document.getElementById('ws-claim-title')?.textContent || '',
      deadline: document.getElementById('ws-deadline')?.textContent || '',
      notesText: document.querySelector('#ws-notes-list')?.innerText || '',
    }));

    await firstContext.storageState({ path: storagePath });
    await firstContext.close();
    firstContext = null;

    const secondContext = await browser.newContext({
      viewport: { width: 1440, height: 1400 },
      storageState: storagePath,
    });
    await helpers.wireApiBase(secondContext);
    await helpers.setupMockAuth(secondContext, userId);
    const secondPage = await secondContext.newPage();
    await secondPage.goto(`${helpers.BASE_URL}/pages/workspace.html#notes`, { waitUntil: 'networkidle' });
    await secondPage.waitForSelector('#ws-workspace', { timeout: 20000 });
    await secondPage.waitForFunction(
      ({ noteTitle, noteBody }) => {
        const text = document.querySelector('#ws-notes-list')?.innerText || '';
        return text.includes(noteTitle) && text.includes(noteBody);
      },
      { noteTitle, noteBody },
      { timeout: 20000 }
    );
    await secondPage.screenshot({ path: restoredShot, fullPage: true });

    const restoredState = await secondPage.evaluate(() => ({
      activeCaseId: localStorage.getItem('lawapp_active_case_id'),
      heading: document.getElementById('ws-claim-title')?.textContent || '',
      deadline: document.getElementById('ws-deadline')?.textContent || '',
      notesText: document.querySelector('#ws-notes-list')?.innerText || '',
    }));

    helpers.writeJson(
      path.join(process.cwd(), 'reports', 'frontend_persistence_proof.json'),
      {
        generated_at: new Date().toISOString(),
        auth_mode: 'mock-header',
        user_id: userId,
        case_id: caseId,
        note_title: noteTitle,
        note_body: noteBody,
        screenshots: {
          before: beforeShot,
          restored: restoredShot,
        },
        storage_state_path: storagePath,
        before: beforeState,
        restored: restoredState,
      }
    );

    await secondContext.close();
  } finally {
    if (firstContext) {
      await firstContext.close();
    }
    await browser.close();
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
