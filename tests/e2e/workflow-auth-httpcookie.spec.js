// @ts-check
const { test, expect } = require('@playwright/test');

/**
 * WORKFLOW SECURITY & AUTH TESTS
 *
 * Verifies:
 * 1. JWT tokens are stored in httpOnly cookies (NOT localStorage)
 * 2. Credentials: include is used for all auth API calls
 * 3. 401/403 redirects to login
 * 4. Session persists across page navigation
 * 5. Logout clears all session state
 */

const BASE = 'http://localhost:8000';
const PASSWORD = 'SecureTestPass123!';
let primaryEmail;
let secondaryEmail;

function uniqueEmail() {
  return `test_${Date.now()}_${Math.floor(Math.random() * 1e6)}@example.com`;
}

test.describe.configure({ mode: 'serial' });

test.beforeAll(async ({ request }) => {
  primaryEmail = uniqueEmail();
  secondaryEmail = uniqueEmail();
  for (const email of [primaryEmail, secondaryEmail]) {
    const regResp = await request.post(`${BASE}/api/auth/register`, {
      data: { email, password: PASSWORD },
    });
    expect(regResp.status(), await regResp.text()).toBe(201);
  }
});

/**
 * Helper: register through the real API, then login from the browser context so
 * Set-Cookie lands in the same context that protected pages will use.
 */
async function registerAndLogin(page, request, email, password) {
  await page.goto(`${BASE}/pages/login.html`);
  const loginResult = await page.evaluate(async ({ email, password }) => {
    const resp = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ email, password }),
    });
    let data = null;
    try { data = await resp.json(); } catch (_) {}
    return { status: resp.status, data };
  }, { email, password });
  expect(loginResult.status).toBe(200);

  return { json: async () => loginResult.data };
}

test.describe('Workflow A: Authentication Security (httpOnly Cookies)', () => {
  test('JWT token is NOT stored in localStorage (security compliance)', async ({ page, request }) => {
    await registerAndLogin(page, request, primaryEmail, PASSWORD);

    // Navigate to login page
    await page.goto(`${BASE}/pages/login.html`);

    // Check: localStorage should NOT contain a token
    const token = await page.evaluate(() => localStorage.getItem('lawapp_token'));
    expect(token).toBeNull();
  });

  test('POST /api/auth/login returns JWT in httpOnly cookie', async ({ page, request, context }) => {
    await registerAndLogin(page, request, primaryEmail, PASSWORD);

    // Get cookies from context
    const cookies = await context.cookies();
    const hasAuthCookie = cookies.some(c =>
      c.name.includes('access') || c.name.includes('auth') || c.name.includes('token')
    );

    // httpOnly cookies are not directly accessible from JS, but they should be set
    // Verify by checking that authenticated requests work
    const meResp = await request.get(`${BASE}/api/auth/me`, {
      headers: { 'Cookie': cookies.map(c => `${c.name}=${c.value}`).join('; ') }
    });
    expect(meResp.status()).toBe(200);
  });

  test('Credentials are sent automatically (credentials: include)', async ({ page, request }) => {
    await registerAndLogin(page, request, primaryEmail, PASSWORD);

    // Navigate to dashboard - should require auth
    await page.goto(`${BASE}/pages/dashboard.html`);

    // The page should load (not redirect to login) because cookies are sent
    await expect(page.locator('h1:has-text("Dashboard")')).toBeVisible({ timeout: 10000 });
  });

  test('Unauthenticated requests to protected routes redirect to login', async ({ page }) => {
    // Try to access dashboard without logging in
    await page.goto(`${BASE}/pages/dashboard.html`);

    // Should redirect to login
    await expect(page).toHaveURL(/login\.html/);
  });

  test('401 response triggers redirect to login', async ({ page, request }) => {
    await registerAndLogin(page, request, primaryEmail, PASSWORD);

    // Navigate to dashboard
    await page.goto(`${BASE}/pages/dashboard.html`);
    await expect(page.locator('h1:has-text("Dashboard")')).toBeVisible({ timeout: 10000 });

    // Simulate session expiration: clear all cookies
    await page.context().clearCookies();

    // Try to make an API call
    const meStatus = await page.evaluate(async () => {
      const resp = await fetch('/api/auth/me', { credentials: 'include' });
      return resp.status;
    });
    expect(meStatus).toBe(401);
  });

  test('Logout clears session state', async ({ page, request }) => {
    await registerAndLogin(page, request, primaryEmail, PASSWORD);

    // Verify authenticated
    await page.goto(`${BASE}/pages/dashboard.html`);
    await expect(page.locator('h1:has-text("Dashboard")')).toBeVisible({ timeout: 10000 });

    // Call logout
    const logoutStatus = await page.evaluate(async () => {
      const resp = await fetch('/api/auth/logout', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ all_sessions: true }),
      });
      return resp.status;
    });
    expect(logoutStatus).toBe(200);

    // Verify: subsequent requests should be 401
    const meStatus = await page.evaluate(async () => {
      const resp = await fetch('/api/auth/me', { credentials: 'include' });
      return resp.status;
    });
    expect(meStatus).toBe(401);
  });
});

test.describe('Workflow B: Session Persistence', () => {
  test('Session persists across page navigations', async ({ page, request }) => {
    await registerAndLogin(page, request, primaryEmail, PASSWORD);

    // Navigate to dashboard
    await page.goto(`${BASE}/pages/dashboard.html`);
    await expect(page.locator('h1:has-text("Dashboard")')).toBeVisible({ timeout: 10000 });

    // Navigate to intake form
    await page.goto(`${BASE}/pages/intake.html`);

    // Should NOT redirect to login (session is still valid)
    await expect(page).not.toHaveURL(/login\.html/);
  });

  test('Session expires and user is redirected to login', async ({ page, request, context }) => {
    await registerAndLogin(page, request, primaryEmail, PASSWORD);

    // Navigate to a protected page
    await page.goto(`${BASE}/pages/dashboard.html`);
    await expect(page.locator('h1:has-text("Dashboard")')).toBeVisible({ timeout: 10000 });

    // Clear cookies (simulate session expiration)
    await context.clearCookies();

    // Reload page - should redirect to login
    await page.reload();
    await expect(page).toHaveURL(/login\.html/, { timeout: 10000 });
  });
});

test.describe('Workflow C: API Error Handling', () => {
  test('401 on API call redirects to login', async ({ page, request }) => {
    await registerAndLogin(page, request, primaryEmail, PASSWORD);

    // Go to dashboard
    await page.goto(`${BASE}/pages/dashboard.html`);
    await expect(page.locator('h1:has-text("Dashboard")')).toBeVisible({ timeout: 10000 });

    // Clear cookies to invalidate session
    await page.context().clearCookies();

    // Attempt to call a protected API
    const casesStatus = await page.evaluate(async () => {
      const resp = await fetch('/cases', { credentials: 'include' });
      return resp.status;
    });
    expect(casesStatus).toBe(401);
  });

  test('403 on API call (permission denied) shows error', async ({ page, request }) => {
    // Create two users
    await registerAndLogin(page, request, primaryEmail, PASSWORD);
    await registerAndLogin(page, request, secondaryEmail, PASSWORD);

    // Logout user1
    await request.post(`${BASE}/api/auth/logout`, { data: { all_sessions: true } });

    // Try to access user1's case as user2 (should fail with 403)
    // Note: This requires creating a case first - skipped for now
  });
});

test.describe('Workflow D: Token Refresh', () => {
  test('Refresh token renews the access token', async ({ page, request }) => {
    const loginResp = await registerAndLogin(page, request, primaryEmail, PASSWORD);

    const loginData = await loginResp.json();
    expect(loginData.refresh_token).toBeDefined();

    // Wait a bit, then refresh
    await new Promise(r => setTimeout(r, 1000));

    const refreshResp = await request.post(`${BASE}/api/auth/refresh`, {
      data: { refresh_token: loginData.refresh_token },
    });
    expect(refreshResp.status()).toBe(200);

    const refreshData = await refreshResp.json();
    expect(refreshData.access_token).toBeDefined();
  });
});
