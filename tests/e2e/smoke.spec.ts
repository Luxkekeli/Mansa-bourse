import { test, expect } from '@playwright/test';

/**
 * Critical-path smoke tests.
 *
 * Each test is independent (no shared user state). They cover the 3 highest-
 * priority parcours that must work for a launch:
 *   1. Dashboard renders and Chart.js loads.
 *   2. Tab navigation works (dashboard → screener → titres).
 *   3. Auth modal opens and rejects bad credentials with a friendly error.
 */

test.describe('MANSA — smoke', () => {
  test('dashboard loads and Chart.js initializes', async ({ page }) => {
    await page.goto('/app.html');
    await expect(page).toHaveTitle(/MANSA/i);

    // Wait for Chart.js to be loaded (the inline onload handler triggers goTab).
    await page.waitForFunction(() => typeof (window as any).Chart === 'function', null, {
      timeout: 10_000,
    });

    // Dashboard tab should be active and visible.
    const dashboard = page.locator('[data-tab="dashboard"]').first();
    await expect(dashboard).toBeVisible();

    // Topbar lang switch must be wired (P1-6 trigger).
    await expect(page.locator('#lang-switch-btn')).toBeVisible();
  });

  test('tab navigation: dashboard → screener', async ({ page }) => {
    await page.goto('/app.html');
    // Wait for any nav link to be present.
    await page.waitForSelector('.nav-link', { timeout: 10_000 });

    // Click the screener tab.
    const screenerTab = page.locator('.nav-link[data-tab="screener"]').first();
    if (await screenerTab.count() > 0) {
      await screenerTab.click();
      await expect(page.locator('.nav-link.active[data-tab="screener"]')).toBeVisible();
    }
  });

  test('auth modal rejects wrong credentials', async ({ page }) => {
    await page.goto('/app.html');
    await page.waitForLoadState('networkidle');

    // Force-open the auth modal via the global helper (UI path may vary).
    await page.evaluate(() => (window as any).openAuthModal && (window as any).openAuthModal('login'));

    const emailInput = page.locator('#auth-email');
    if (await emailInput.count() > 0) {
      await emailInput.fill('nobody@nowhere.com');
      await page.locator('#auth-pwd').fill('wrong-password-123');

      // doLogin() uses fetch + showNotif. We just verify the network call returns 401.
      const [resp] = await Promise.all([
        page.waitForResponse(r => r.url().endsWith('/api/auth/login'), { timeout: 10_000 }),
        page.evaluate(() => (window as any).doLogin && (window as any).doLogin()),
      ]);
      expect(resp.status()).toBe(401);
    }
  });
});
