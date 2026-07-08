const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const BASE_URL = process.env.LAWAPP_FRONTEND_BASE_URL || 'http://localhost:8000';
const PASSWORD = 'FrontendProofPass123!';
const WIDTHS = [360, 390, 768, 1024, 1440];

function ensureDir(dirPath) {
  fs.mkdirSync(dirPath, { recursive: true });
}

function writeJson(filePath, value) {
  ensureDir(path.dirname(filePath));
  fs.writeFileSync(filePath, JSON.stringify(value, null, 2) + '\n', 'utf8');
}

function uniqueEmail(prefix) {
  const stamp = Date.now();
  const rand = Math.floor(Math.random() * 1e6);
  return `${prefix}_${stamp}_${rand}@example.com`;
}

async function registerAndLogin(page, email) {
  await page.goto(`${BASE_URL}/pages/login.html`, { waitUntil: 'networkidle' });
  const result = await page.evaluate(async ({ email, password }) => {
    const registerResp = await fetch('/api/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ email, password }),
    });
    let registerBody = null;
    try { registerBody = await registerResp.json(); } catch (_) {}
    if (registerResp.status === 201) {
      return { status: registerResp.status, body: registerBody };
    }
    const loginResp = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ email, password }),
    });
    let loginBody = null;
    try { loginBody = await loginResp.json(); } catch (_) {}
    return { status: loginResp.status, body: loginBody };
  }, { email, password: PASSWORD });

  if (result.status !== 200 && result.status !== 201) {
    throw new Error(`Auth setup failed (${result.status})`);
  }
}

async function setupMockAuth(context, userId) {
  await context.addInitScript(
    ({ userId, baseUrl }) => {
      const targetBase = baseUrl.replace('http://127.0.0.1', 'http://localhost');
      const nativeFetch = window.fetch.bind(window);
      const normalizeUrl = (input) => {
        if (typeof input !== 'string') return input;
        if (input.startsWith('http://localhost:8000')) {
          return input.replace('http://localhost:8000', baseUrl);
        }
        if (input.startsWith('http://127.0.0.1:8000')) {
          return input.replace('http://127.0.0.1:8000', baseUrl);
        }
        return input;
      };
      window.fetch = function (input, init) {
        const options = Object.assign({}, init || {});
        const headers = Object.assign({}, options.headers || {});
        headers['X-User-ID'] = userId;
        options.headers = headers;
        options.credentials = options.credentials || 'include';
        return nativeFetch(normalizeUrl(input), options);
      };

      let authValue = null;
      Object.defineProperty(window, 'LAWAPP_AUTH', {
        configurable: true,
        get() {
          return authValue;
        },
        set(value) {
          value.isLoggedIn = async () => true;
          value.ensureLoggedIn = async () => true;
          value.getCurrentUser = async () => ({
            id: userId,
            email: `mock-${userId.slice(0, 8)}@example.com`,
          });
          value.fetchWithAuth = async (url, options) => {
            const opts = Object.assign({}, options || {});
            opts.headers = Object.assign({}, opts.headers || {}, { 'X-User-ID': userId });
            opts.credentials = opts.credentials || 'include';
            return window.fetch(normalizeUrl(url), opts);
          };
          value.updateNav = async () => {};
          value.logout = async () => {};
          authValue = value;
        },
      });
      window.__LAWAPP_MOCK_AUTH__ = { userId, baseUrl: targetBase };
    },
    { userId, baseUrl: BASE_URL }
  );
}

async function createCase(page, payload) {
  const result = await page.evaluate(async (casePayload) => {
    const resp = await fetch('/cases', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify(casePayload),
    });
    let body = null;
    try { body = await resp.json(); } catch (_) {}
    return { status: resp.status, body };
  }, payload);
  if (result.status !== 201 || !result.body || !result.body.case_id) {
    throw new Error(`Case create failed (${result.status}): ${JSON.stringify(result.body)}`);
  }
  return result.body;
}

async function createCaseWithAssessment(page, overrides) {
  const assessment = Object.assign({
    status: 'ok',
    claim_type: 'unfair_dismissal',
    has_viable_claim: 'yes',
    strength: 'medium',
    reasoning_summary: 'Dismissed after three years without a fair procedure.',
    key_weaknesses: ['Employer may dispute procedure facts.'],
    employer_arguments: ['Band of reasonable responses.'],
    deadline: {
      limitation_date: '2026-06-30',
      source: 'rules',
      authority: 'ERA 1996 s.111(2)',
      ec_applied: false,
    },
    deadline_info: {
      limitation_date: '2026-06-30',
      source: 'rules',
      authority: 'ERA 1996 s.111(2)',
      ec_applied: false,
    },
    citations: [
      { cite: 'ERA 1996 s.94', url: 'https://www.legislation.gov.uk/ukpga/1996/18/section/94' },
    ],
    grounding_score: 0.87,
    confidence_score: 0.79,
    insufficient_grounding: false,
    recommended_next_step: 'prepare_documents',
  }, (overrides && overrides.assessment) || {});

  const facts = Object.assign({
    edt: '2026-04-01',
    service_start_date: '2023-04-01',
    reason_for_dismissal: 'conduct',
    was_procedure_followed: false,
    weekly_pay: 600,
    jurisdiction: 'EW',
  }, (overrides && overrides.facts) || {});

  return createCase(page, {
    claim_type: 'unfair_dismissal',
    jurisdiction: 'EW',
    assessment,
    key_dates: {
      edt: facts.edt,
      deadline_date: assessment.deadline_info.limitation_date,
    },
    facts,
    recommended_next_step: assessment.recommended_next_step,
  });
}

async function captureViewportMatrix(page, name, url, waitSelector, setupFn) {
  const out = [];
  for (const width of WIDTHS) {
    await page.setViewportSize({ width, height: 1400 });
    if (setupFn) {
      await setupFn(width);
    }
    await page.goto(url, { waitUntil: 'networkidle' });
    await page.waitForSelector(waitSelector, { timeout: 15000 });
    const snapPath = path.join(process.cwd(), 'reports', 'frontend_snaps', `${name}-${width}.png`);
    ensureDir(path.dirname(snapPath));
    await page.screenshot({ path: snapPath, fullPage: true });
    const metrics = await page.evaluate(() => ({
      title: document.title,
      scrollWidth: document.documentElement.scrollWidth,
      clientWidth: document.documentElement.clientWidth,
      overflowX: document.documentElement.scrollWidth > document.documentElement.clientWidth,
      footerCount: document.querySelectorAll('footer').length,
      hasLegalNotice: !!document.querySelector('.legal-notice'),
    }));
    out.push({ screen: name, width, screenshot: snapPath, ...metrics });
  }
  return out;
}

async function launchBrowser() {
  return chromium.launch({ headless: true });
}

async function wireApiBase(context) {
  if (BASE_URL.endsWith(':8000')) return;
  await context.route('http://localhost:8000/**', async (route) => {
    const requestUrl = route.request().url();
    await route.continue({ url: requestUrl.replace('http://localhost:8000', BASE_URL) });
  });
}

module.exports = {
  BASE_URL,
  PASSWORD,
  WIDTHS,
  ensureDir,
  writeJson,
  uniqueEmail,
  registerAndLogin,
  setupMockAuth,
  createCase,
  createCaseWithAssessment,
  captureViewportMatrix,
  launchBrowser,
  wireApiBase,
};
