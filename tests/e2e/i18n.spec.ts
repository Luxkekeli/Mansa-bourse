import { test, expect } from '@playwright/test';

/**
 * P1-6 — i18n switch FR ↔ EN.
 *
 * Doesn't validate every key (would need ~200 assertions) — instead checks
 * that the switchLang() global flips a few visible strings. The full
 * "no French word remains in EN mode" audit is out of scope for smoke.
 */

test.describe('MANSA — i18n smoke', () => {
  test('switchLang flips translation table', async ({ page }) => {
    await page.goto('/app.html');
    await page.waitForLoadState('networkidle');

    // Force FR.
    await page.evaluate(() => {
      (window as any)._mansaLang = 'fr';
      try { localStorage.setItem('mansa_lang', 'fr'); } catch {}
    });
    const navDashboardFr = await page.evaluate(() => (window as any).t && (window as any).t('nav.dashboard'));
    expect(navDashboardFr).toBe('Dashboard');  // french "dashboard" is also "Dashboard" in our dict

    // Switch to EN and verify a key that differs.
    await page.evaluate(() => (window as any).switchLang && (window as any).switchLang());
    const dashboardEn = await page.evaluate(() => (window as any).t && (window as any).t('dash.market_summary'));
    expect(dashboardEn).toBe('Market Summary');

    // Switch back to FR.
    await page.evaluate(() => (window as any).switchLang && (window as any).switchLang());
    const dashboardFr = await page.evaluate(() => (window as any).t && (window as any).t('dash.market_summary'));
    expect(dashboardFr).toBe('Resume du marche');
  });

  test('all expanded keys present in both languages', async ({ page }) => {
    await page.goto('/app.html');
    await page.waitForLoadState('networkidle');

    // Sample keys from each new namespace added in P1-6.
    const sampleKeys = [
      'auth.welcome', 'community.send', 'screener.title',
      'portfolio.title', 'error.network', 'time.now',
      'unit.fcfa', 'action.view', 'status.active',
    ];

    const results = await page.evaluate((keys) => {
      const out: Record<string, { fr: string; en: string }> = {};
      const w = window as any;
      const orig = w._mansaLang;
      w._mansaLang = 'fr'; const fr = keys.map(k => w.t(k));
      w._mansaLang = 'en'; const en = keys.map(k => w.t(k));
      w._mansaLang = orig;
      keys.forEach((k, i) => { out[k] = { fr: fr[i], en: en[i] }; });
      return out;
    }, sampleKeys);

    for (const k of sampleKeys) {
      expect(results[k].fr, `FR missing for ${k}`).not.toBe(k);
      expect(results[k].en, `EN missing for ${k}`).not.toBe(k);
      expect(results[k].fr).not.toBe(results[k].en);
    }
  });
});
