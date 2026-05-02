import { defineConfig, devices } from '@playwright/test';

/**
 * MANSA — Playwright e2e config.
 *
 * Run locally:
 *   npm run test:install   # one-time browser download
 *   npm run test:e2e
 *
 * The webServer block boots the Flask backend on :5000 and serves the static
 * frontend on :8080 via Python's http.server. Set MANSA_E2E_BASE_URL to point
 * tests at an already-running stack instead.
 */
export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: false,        // keep DB-heavy tests serial
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: 1,
  timeout: 30_000,
  expect: { timeout: 5_000 },
  reporter: process.env.CI
    ? [['list'], ['junit', { outputFile: 'test-results/junit.xml' }]]
    : 'list',
  use: {
    baseURL: process.env.MANSA_E2E_BASE_URL ?? 'http://127.0.0.1:8080',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    actionTimeout: 10_000,
    navigationTimeout: 15_000,
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  // Spin up the stack only when running locally without an explicit URL.
  webServer: process.env.MANSA_E2E_BASE_URL
    ? undefined
    : [
        {
          command: 'python -m http.server 8080 --directory frontend',
          url: 'http://127.0.0.1:8080/app.html',
          reuseExistingServer: !process.env.CI,
          timeout: 30_000,
        },
        {
          command: 'python -m flask --app server.api_server run --port 5000',
          url: 'http://127.0.0.1:5000/api/health',
          reuseExistingServer: !process.env.CI,
          timeout: 30_000,
          env: {
            FLASK_ENV: 'development',
            MANSA_ALLOWED_ORIGINS: 'http://127.0.0.1:8080,http://localhost:8080',
          },
        },
      ],
});
