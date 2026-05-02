import { test, expect } from '@playwright/test';

/**
 * Community post → poll round-trip with XSS payload.
 *
 * Verifies that:
 *  - An authenticated user can POST a message with a `<script>` payload.
 *  - Polling returns the sanitized version (no `<script>` tag).
 *  - The raw `content` field is NEVER exposed via the API.
 */

const EMAIL = `e2e-comm+${Date.now()}@example.com`;

test.describe('MANSA — community sanitization round-trip', () => {
  test('post with XSS payload → poll returns sanitized', async ({ request }) => {
    const reg = await request.post('http://127.0.0.1:5000/api/auth/register', {
      data: { email: EMAIL, password: 'strongpass123', prenom: 'Comm' },
    });
    expect(reg.status()).toBe(201);

    const evil = '<p>Hello</p><script>window.evil=true</script>';
    const post = await request.post('http://127.0.0.1:5000/api/community/post', {
      data: { room: 'general', content: evil },
    });
    expect(post.status()).toBe(201);
    const body = await post.json();
    expect(body.sanitized_content.toLowerCase()).not.toContain('<script');

    const poll = await request.get(
      'http://127.0.0.1:5000/api/community/poll?room=general&since=1970-01-01T00:00:00'
    );
    expect(poll.status()).toBe(200);
    const messages = (await poll.json()).messages as Array<Record<string, unknown>>;
    const ours = messages.find(m => m.id === body.id);
    expect(ours).toBeDefined();
    expect(ours).not.toHaveProperty('content');     // raw must NEVER leak
    expect(String(ours!.sanitized_content).toLowerCase()).not.toContain('<script');
  });
});
