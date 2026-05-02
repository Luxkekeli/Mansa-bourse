import { test, expect } from '@playwright/test';

/**
 * Full auth round-trip: register → me → logout → me (should fail).
 *
 * Uses a unique email per run so reruns don't collide on the UNIQUE constraint.
 */

const UNIQUE_EMAIL = `e2e+${Date.now()}@example.com`;
const PASSWORD = 'e2e-pass-123';

test.describe('MANSA — auth round-trip', () => {
  test('register → me → logout → me 401', async ({ request }) => {
    // Register.
    const r1 = await request.post('http://127.0.0.1:5000/api/auth/register', {
      data: { email: UNIQUE_EMAIL, password: PASSWORD, prenom: 'E2E' },
    });
    expect(r1.status(), 'register should be 201').toBe(201);
    const reg = await r1.json();
    expect(reg.user.email).toBe(UNIQUE_EMAIL);

    // me — should return the freshly registered user.
    const r2 = await request.get('http://127.0.0.1:5000/api/auth/me');
    expect(r2.status()).toBe(200);
    const me = await r2.json();
    expect(me.user.email).toBe(UNIQUE_EMAIL);

    // logout.
    const r3 = await request.post('http://127.0.0.1:5000/api/auth/logout');
    expect(r3.status()).toBe(200);

    // me — now anonymous.
    const r4 = await request.get('http://127.0.0.1:5000/api/auth/me');
    expect(r4.status()).toBe(401);
  });
});
