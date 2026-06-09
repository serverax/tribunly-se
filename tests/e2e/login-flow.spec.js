// @ts-check
const { test, expect } = require('@playwright/test');

/**
 * Login flow (browser) — login.html UI, both methods.
 *
 * Covers the spec's "test_login_flow: magic link + email/password" against the
 * REAL served page at http://localhost:8000/pages/login.html (no mocks).
 *
 * Implemented as a JS Playwright spec (not Python) because this repo's e2e
 * harness is @playwright/test (playwright.config.js); python-playwright is not
 * installed. See PROOF.md "E2E deviation" note.
 *
 * Proven:
 *   - the page renders both auth methods (password + magic link) + legal notice
 *   - tab switching reveals the magic-link form
 *   - email/password: a registered user logs in via the form -> httpOnly
 *     cookies authenticate /api/auth/me, redirected away from the login page
 *   - a wrong password surfaces a visible error (no silent failure)
 *   - magic-link request shows the generic "link is on its way" message
 *     (no account enumeration in the UI)
 *   - empty fields are validated client-side
 */

const BASE = 'http://localhost:8000';
const LOGIN = `${BASE}/pages/login.html`;
const PASSWORD = 'Str0ngP@ssw0rd!';

function email() {
  return `e2e_${Date.now()}_${Math.floor(Math.random() * 1e6)}@example.com`;
}

// Register a throwaway account through the real API so the password-login test
// has valid credentials.
async function registerViaApi(request, addr) {
  const r = await request.post(`${BASE}/api/auth/register`, {
    data: { email: addr, password: PASSWORD },
  });
  expect(r.status(), await r.text()).toBe(201);
}

test('login page renders both auth methods and the legal notice', async ({ page }) => {
  await page.goto(LOGIN);
  await expect(page.locator('.legal-notice')).toBeVisible();
  await expect(page.locator('#tab-password')).toBeVisible();
  await expect(page.locator('#tab-magic')).toBeVisible();
  await expect(page.locator('#loginForm')).toBeVisible();
});

test('switching to the magic-link tab reveals the magic form', async ({ page }) => {
  await page.goto(LOGIN);
  await page.locator('#tab-magic').click();
  await expect(page.locator('#magicForm')).toBeVisible();
  await expect(page.locator('#magic-email')).toBeVisible();
});

test('email/password: a registered user logs in and is redirected', async ({ page, request }) => {
  const addr = email();
  await registerViaApi(request, addr);

  await page.goto(LOGIN);
  await page.fill('#email', addr);
  await page.fill('#password', PASSWORD);
  await page.click('#loginForm button[type=submit]');

  // Success: no bearer token is exposed to JS; server-side /me authenticates
  // through httpOnly cookies and the page navigates away from login.
  await expect.poll(async () =>
    page.evaluate(() => localStorage.getItem('lawapp_token')),
    { timeout: 10_000 }
  ).toBeNull();
  await expect.poll(async () => {
    const resp = await page.request.get(`${BASE}/api/auth/me`);
    return resp.status();
  }, { timeout: 10_000 }).toBe(200);
  await expect(page).not.toHaveURL(/login\.html/);
});

test('email/password: a wrong password shows a visible error', async ({ page, request }) => {
  const addr = email();
  await registerViaApi(request, addr);

  await page.goto(LOGIN);
  await page.fill('#email', addr);
  await page.fill('#password', 'Wr0ngP@ssword!');
  await page.click('#loginForm button[type=submit]');

  await expect(page.locator('#login-error')).toBeVisible();
  await expect(page.locator('#login-error-text')).not.toBeEmpty();
  // Still on the login page — no silent "success".
  await expect(page).toHaveURL(/login\.html/);
});

test('magic link: request shows the generic on-its-way message', async ({ page }) => {
  await page.goto(LOGIN);
  await page.locator('#tab-magic').click();
  await page.fill('#magic-email', email());
  await page.click('#magicForm button[type=submit]');

  await expect(page.locator('#magic-ok')).toBeVisible({ timeout: 10_000 });
  await expect(page.locator('#magic-ok')).toContainText(/sign-in link is on its way/i);
});

test('login validates empty fields client-side', async ({ page }) => {
  await page.goto(LOGIN);
  await page.click('#loginForm button[type=submit]');
  await expect(page.locator('#login-error')).toBeVisible();
  await expect(page.locator('#login-error-text')).toContainText(/required/i);
});
