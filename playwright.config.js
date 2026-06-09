// @ts-check
const { defineConfig, devices } = require('@playwright/test');

module.exports = defineConfig({
  testDir:  './tests/e2e',
  timeout:  30_000,
  retries:  1,
  reporter: [['html', { open: 'never', outputFolder: 'reports/playwright-report' }], ['list']],
  use: {
    baseURL:     'http://localhost:8000',
    trace:       'on-first-retry',
    screenshot:  'only-on-failure',
    video:       'off',
    headless:    true,
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
  ],
  // Global setup: ensure backend is running before tests
  webServer: {
    command:   'docker compose up -d 2>&1 || true',
    url:       'http://localhost:8000/health',
    reuseExistingServer: true,
    timeout:   30_000,
  },
});
