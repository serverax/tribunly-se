// @ts-check
const { test, expect } = require('@playwright/test');

/**
 * lawapp End-to-End Journey Tests
 *
 * Full user journey: register → login → intake → assessment → save → dashboard
 *   → case detail → document generation → download → logout → user isolation
 *
 * Requires:
 *   - Docker Compose running (backend on :8000)
 *   - LAWAPP_AUTH_MODE=mock or jwt
 *   - PAYMENT_MODE=test_simulator or mock
 */

const BASE = 'http://localhost:8000';

// Unique emails for each test run
const TS = Date.now();
const USER_A_EMAIL = `usera_${TS}@lawapp-e2e.local`;
const USER_B_EMAIL = `userb_${TS}@lawapp-e2e.local`;
const PASSWORD = 'E2eTestPass123!';

let tokenA = '';
let tokenB = '';
let caseIdA = '';

// ── API helpers ──────────────────────────────────────────────────────────────

async function apiRegister(request, email, password) {
  const r = await request.post(`${BASE}/auth/register`, {
    data: { email, password },
  });
  return r;
}

async function apiLogin(request, email, password) {
  const r = await request.post(`${BASE}/auth/token`, {
    data: { email, password },
  });
  const body = await r.json();
  return body.access_token || null;
}

// ── Test: Health check ───────────────────────────────────────────────────────

test('backend health check', async ({ request }) => {
  const r = await request.get(`${BASE}/health`);
  expect(r.status()).toBe(200);
  const body = await r.json();
  expect(body.status).toBe('ok');
  expect(body.db).toBe('connected');
});

// ── Test: Rules endpoint ─────────────────────────────────────────────────────

test('rules endpoint returns unfair dismissal rules', async ({ request }) => {
  const r = await request.get(`${BASE}/rules/unfair_dismissal`);
  expect(r.status()).toBe(200);
  const body = await r.json();
  expect(body.rules.length).toBeGreaterThan(0);
  const keys = body.rules.map(r => r.rule_key);
  expect(keys).toContain('unfair_dismissal.time_limit_months');
  expect(keys).toContain('unfair_dismissal.qualifying_period');
});

// ── Test: Register User A ────────────────────────────────────────────────────

test('register user A', async ({ request }) => {
  const r = await apiRegister(request, USER_A_EMAIL, PASSWORD);
  expect(r.status()).toBe(201);
  const body = await r.json();
  expect(body.user_id).toBeTruthy();
  expect(body.message).toContain('registered');
});

// ── Test: Register User B ────────────────────────────────────────────────────

test('register user B', async ({ request }) => {
  const r = await apiRegister(request, USER_B_EMAIL, PASSWORD);
  expect(r.status()).toBe(201);
});

// ── Test: Login User A ───────────────────────────────────────────────────────

test('login user A and receive token', async ({ request }) => {
  tokenA = await apiLogin(request, USER_A_EMAIL, PASSWORD);
  expect(tokenA).toBeTruthy();
  expect(tokenA.length).toBeGreaterThan(20);
});

// ── Test: Login User B ───────────────────────────────────────────────────────

test('login user B and receive token', async ({ request }) => {
  tokenB = await apiLogin(request, USER_B_EMAIL, PASSWORD);
  expect(tokenB).toBeTruthy();
});

// ── Test: Assessment API (short service → definitive answer) ─────────────────

test('assessment returns definitive answer for short service (QP fails)', async ({ request }) => {
  const r = await request.post(`${BASE}/assess`, {
    data: {
      query: 'I was dismissed after 10 months',
      facts: {
        edt: '2026-03-01',
        service_start_date: '2025-05-01',
        reason_for_dismissal: 'conduct',
        was_procedure_followed: false,
        weekly_pay: 500,
        jurisdiction: 'EW',
      },
      jurisdiction: 'EW',
    },
  });
  expect(r.status()).toBe(200);
  const body = await r.json();
  expect(body.status).toBe('ok');
  expect(body.has_viable_claim).toBe('no');
  expect(body.key_weaknesses.length).toBeGreaterThan(0);
  expect(body.citations.length).toBeGreaterThan(0);
  expect(body.deadline).not.toBeNull();
  expect(body.deadline.limitation_date).toBeTruthy();
});

// ── Test: Save case as User A ────────────────────────────────────────────────

test('save case as user A', async ({ request }) => {
  if (!tokenA) { test.skip(); return; }
  const r = await request.post(`${BASE}/cases`, {
    data: {
      claim_type: 'unfair_dismissal',
      jurisdiction: 'EW',
      assessment: { status: 'ok', has_viable_claim: 'no' },
      key_dates: { edt: '2026-03-01' },
    },
    headers: { 'Authorization': `Bearer ${tokenA}` },
  });
  expect(r.status()).toBe(201);
  const body = await r.json();
  caseIdA = body.case_id;
  expect(caseIdA).toBeTruthy();
});

// ── Test: User A can read own case ───────────────────────────────────────────

test('user A can read own case', async ({ request }) => {
  if (!tokenA || !caseIdA) { test.skip(); return; }
  const r = await request.get(`${BASE}/cases/${caseIdA}`, {
    headers: { 'Authorization': `Bearer ${tokenA}` },
  });
  expect(r.status()).toBe(200);
  const body = await r.json();
  expect(body.case_id).toBe(caseIdA);
});

// ── Test: User isolation  -  B cannot read A's case ────────────────────────────

test('user B CANNOT read user A case (HTTP 403)', async ({ request }) => {
  if (!tokenB || !caseIdA) { test.skip(); return; }
  const r = await request.get(`${BASE}/cases/${caseIdA}`, {
    headers: { 'Authorization': `Bearer ${tokenB}` },
  });
  // In jwt/mock mode: 403. In none mode: 200 (isolation bypassed  -  staging blocker)
  const status = r.status();
  // Accept 403 (proper isolation) or note if 200 (auth mode=none  -  staging blocker)
  if (status === 200) {
    console.warn('USER ISOLATION BYPASSED: LAWAPP_AUTH_MODE may be "none"  -  set to "mock" or "jwt"');
  }
  // In mock mode this SHOULD be 403
  expect(status).toBe(403);
});

// ── Test: 19-step brain trace ────────────────────────────────────────────────

test('brain trace runs all 19 steps', async ({ request }) => {
  const r = await request.post(`${BASE}/api/brain/trace`, {
    data: {
      message: 'I was dismissed after 4 years without warning',
      facts: {
        edt: '2026-03-01',
        service_start_date: '2022-01-01',
        jurisdiction: 'EW',
        weekly_pay: 750,
      },
    },
  });
  expect(r.status()).toBe(200);
  const body = await r.json();
  const steps = body.trace.steps.map(s => s.step);
  const required = [
    'authenticate', 'load_context', 'detect_jurisdiction', 'detect_legal_area',
    'detect_claim_type', 'detect_urgency', 'detect_missing_facts', 'select_agents',
    'select_rag_source', 'run_rules_engine', 'retrieve_legal_evidence', 'verify_citations',
    'compress_context', 'generate_draft', 'evaluate_draft', 'apply_safety_policy',
    'save_case_memory', 'store_audit_log', 'return_answer',
  ];
  required.forEach(step => expect(steps).toContain(step));
  expect(body.trace.rag_sources).toContain('hybrid');
  expect(body.safety.passed).toBe(true);
});

// ── Test: Document generation (test_simulator payment) ───────────────────────

test('document generation with test payment token', async ({ request }) => {
  if (!tokenA) { test.skip(); return; }
  // First get a test token
  const sessionR = await request.post(`${BASE}/api/payment/create-session`, {
    data: { document_type: 'particulars_of_claim' },
    headers: { 'Authorization': `Bearer ${tokenA}` },
  });
  expect(sessionR.status()).toBe(200);
  const session = await sessionR.json();
  const token = session.payment_token;
  expect(token).toBeTruthy();

  // Now generate the document
  const docR = await request.post(`${BASE}/documents/generate`, {
    data: {
      document_type: 'particulars_of_claim',
      assessment: { has_viable_claim: 'uncertain' },
      facts: { edt: '2026-03-01', service_start_date: '2022-01-01' },
      payment_token: token,
    },
    headers: { 'Authorization': `Bearer ${tokenA}` },
  });
  expect(docR.status()).toBe(200);
  const doc = await docR.json();
  expect(doc.payment_required).toBe(false);
  expect(doc.content.length).toBeGreaterThan(200);
  expect(doc.disclaimer_included).toBe(true);
});

// ── Test: No paid doc without token ──────────────────────────────────────────

test('document preview only without payment token', async ({ request }) => {
  const r = await request.post(`${BASE}/documents/generate`, {
    data: {
      document_type: 'schedule_of_loss',
      assessment: { has_viable_claim: 'uncertain' },
      facts: { edt: '2026-03-01', service_start_date: '2022-01-01' },
    },
  });
  expect(r.status()).toBe(200);
  const body = await r.json();
  expect(body.payment_required).toBe(true);
});

// ── Test: Landing page loads ─────────────────────────────────────────────────

test('landing page loads with legal notice', async ({ page }) => {
  await page.goto(`${BASE}/`);
  await expect(page.locator('.legal-notice')).toBeVisible();
  await expect(page.locator('.legal-notice')).toContainText('Not a law firm');
  // Start diagnosis button exists
  const startBtn = page.locator('text=Start free diagnosis').first();
  await expect(startBtn).toBeVisible();
});

// ── Test: Intake page loads ───────────────────────────────────────────────────

test('intake page loads with ACAS fields', async ({ page }) => {
  await page.goto(`${BASE}/pages/intake.html`);
  // Claim type radio
  await expect(page.locator('input[name="claim_type"][value="unfair_dismissal"]')).toBeVisible();
  // Go to step 2
  await page.click('button:has-text("Continue")');
  // EDT field
  await expect(page.locator('#edt')).toBeVisible();
  // ACAS Day A field
  await expect(page.locator('#ec_day_a')).toBeVisible();
  // ACAS Day B field
  await expect(page.locator('#ec_day_b')).toBeVisible();
  // ACAS not started checkbox
  await expect(page.locator('#acas_not_started')).toBeVisible();
});

// ── Test: Live deadline preview ───────────────────────────────────────────────

test('intake deadline preview: rules API returns correct values for WASM/JS', async ({ request }) => {
  // Pure API test  -  verifies the data that drives the deadline preview
  const r = await request.get(`${BASE}/rules/unfair_dismissal`);
  expect(r.status()).toBe(200);
  const body = await r.json();
  const rules = body.rules;
  expect(rules.length).toBeGreaterThan(0);

  const tl = rules.find(r => r.rule_key === 'unfair_dismissal.time_limit_months');
  expect(tl).toBeTruthy();
  expect(Number(tl.value_numeric)).toBe(3);  // 3 months (current rule)
  expect(tl.authority_ref).toContain('ERA 1996');

  const qp = rules.find(r => r.rule_key === 'unfair_dismissal.qualifying_period');
  expect(qp).toBeTruthy();
  expect(Number(qp.value_numeric)).toBe(2);  // 2 years qualifying period

  const cap = rules.find(r => r.rule_key === 'unfair_dismissal.compensatory_cap_amount');
  expect(cap).toBeTruthy();
  expect(Number(cap.value_numeric)).toBe(123543);  // current cap

  // Intake page has ACAS fields (browser check)
  // Already proven in 'intake page loads with ACAS fields' test
});

// ── Test: Register → intake → assessment journey (browser) ──────────────────

test('full browser journey: landing, register, login, intake, assessment', async ({ page, request }) => {
  test.setTimeout(90000);
  const ts = Date.now();
  const email = `e2e_journey_${ts}@lawapp-test.local`;

  // 1. Landing page
  await page.goto(`${BASE}/`);
  await expect(page.locator('.legal-notice')).toBeVisible();

  // 2. Register via API (faster than browser form)
  const regR = await request.post(`${BASE}/auth/register`, {
    data: { email, password: PASSWORD }
  });
  expect(regR.status()).toBe(201);

  // 3. Login via API
  const loginR = await request.post(`${BASE}/auth/token`, {
    data: { email, password: PASSWORD }
  });
  const token = (await loginR.json()).access_token;
  expect(token).toBeTruthy();

  // 4. Go to intake page
  await page.goto(`${BASE}/pages/intake.html`);
  await expect(page.locator('#intakeForm')).toBeVisible({ timeout: 5000 });

  // 5. Step 1 → Step 2 (click the visible Continue button)
  await page.locator('.wizard-panel.active button:has-text("Continue")').click();
  await expect(page.locator('#edt')).toBeVisible({ timeout: 5000 });

  // 6. Fill dates
  await page.fill('#edt', '2025-10-01');
  await page.fill('#service_start', '2022-01-01');
  await page.selectOption('#reason', 'conduct');
  await page.check('#acas_not_started');

  // 7. Step 2 → Step 3 (click Continue in active panel)
  await page.locator('.wizard-panel.active button:has-text("Continue")').click();
  await expect(page.locator('input[name="procedure"]').first()).toBeVisible({ timeout: 5000 });

  // 8. Procedure
  await page.check('input[name="procedure"][value="false"]');
  await page.check('input[name="hearing"][value="false"]');

  // 9. Step 3 → Step 4
  await page.locator('.wizard-panel.active button:has-text("Continue")').click();
  await expect(page.locator('#weekly_pay')).toBeVisible({ timeout: 5000 });

  // 10. Pay + Submit
  await page.fill('#weekly_pay', '650');
  const assessResp = page.waitForResponse(
    r => r.url().includes('/assess'), { timeout: 30000 }
  );
  await page.locator('button[type="submit"]').click();
  await assessResp;

  // 11. Should be on assessment page
  await page.waitForURL(/assessment/, { timeout: 15000 });
  await expect(page).toHaveURL(/assessment/);

  // 12. Save case via API (proves end-to-end data flow)
  const caseR = await request.post(`${BASE}/cases`, {
    data: {
      claim_type: 'unfair_dismissal', jurisdiction: 'EW',
      assessment: { status: 'ok' }, key_dates: { edt: '2025-10-01' }
    },
    headers: { 'Authorization': `Bearer ${token}` }
  });
  expect(caseR.status()).toBe(201);
  const caseId = (await caseR.json()).case_id;
  expect(caseId).toBeTruthy();

  // 13. User isolation: new user cannot see saved case
  const email2 = `e2e_userb_${ts}@lawapp-test.local`;
  await request.post(`${BASE}/auth/register`, { data: { email: email2, password: PASSWORD } });
  const loginB = await request.post(`${BASE}/auth/token`, { data: { email: email2, password: PASSWORD } });
  const tokenB = (await loginB.json()).access_token;
  const isoR = await request.get(`${BASE}/cases/${caseId}`, {
    headers: { 'Authorization': `Bearer ${tokenB}` }
  });
  expect(isoR.status()).toBe(403);
});
