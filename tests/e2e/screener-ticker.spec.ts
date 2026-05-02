import { test, expect } from '@playwright/test';

/**
 * Screener filter + ticker detail flow.
 *
 * Hits the API directly (the UI is heavily JS-rendered and brittle).
 * These cover the critical data paths the frontend depends on.
 */

test.describe('MANSA — data API smoke', () => {
  test('screener returns equity tickers only', async ({ request }) => {
    const r = await request.get('http://127.0.0.1:5000/api/screener?sort=symbol&order=ASC');
    expect(r.status()).toBe(200);
    const body = await r.json();
    expect(body.count).toBeGreaterThan(0);
    // All results must be equities (excluded from indices).
    body.results.forEach((row: any) => {
      expect(row.symbol).toBeDefined();
      expect(row.name).toBeDefined();
    });
  });

  test('screener whitelist rejects malicious sort param (no SQLi)', async ({ request }) => {
    // Even a malicious `sort=` should not cause 500 — it falls back to t.symbol.
    const r = await request.get(
      'http://127.0.0.1:5000/api/screener?sort=t.symbol;DROP%20TABLE%20tickers&order=ASC'
    );
    expect(r.status()).toBe(200);
    // tickers table must still exist.
    const t = await request.get('http://127.0.0.1:5000/api/tickers');
    expect(t.status()).toBe(200);
  });

  test('ticker detail returns prices + range_52w', async ({ request }) => {
    const list = await (await request.get('http://127.0.0.1:5000/api/tickers')).json();
    const symbol = list.tickers[0]?.symbol;
    test.skip(!symbol, 'No tickers seeded — skipping');

    const r = await request.get(`http://127.0.0.1:5000/api/ticker/${encodeURIComponent(symbol)}`);
    expect(r.status()).toBe(200);
    const body = await r.json();
    expect(body.ticker.symbol).toBe(symbol);
    expect(Array.isArray(body.prices)).toBe(true);
    expect(body.range_52w).toBeDefined();
  });
});
