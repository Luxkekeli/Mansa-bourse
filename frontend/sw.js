/* MANSA Service Worker — v2.2 (P1-5)
 *
 * Strategies (Workbox-style, hand-rolled to avoid the runtime cost):
 *   1. Cache-first for the app shell + static assets   (fastest UX, offline-OK)
 *   2. Network-first w/ 5-min cache fallback for /api/* GETs (fresh data)
 *   3. Network-only (no caching) for /api/auth/* and /api/payment/* (security)
 *
 * Versioning: bump CACHE_VERSION on every deploy. The activate handler purges
 * older caches automatically.
 */

const CACHE_VERSION = 'v2.2.0';
const SHELL_CACHE   = 'mansa-shell-' + CACHE_VERSION;
const API_CACHE     = 'mansa-api-'   + CACHE_VERSION;
const API_TTL_MS    = 5 * 60 * 1000;  // 5 minutes

const SHELL_URLS = [
  './app.html',
  './manifest.json',
];

const NEVER_CACHE_PATTERNS = [
  /\/api\/auth\//,
  /\/api\/payment\//,
  /\/api\/admin\//,
  /\/api\/community\/post/,   // POST anyway, but defense-in-depth
];

const CACHE_FIRST_PATTERNS = [
  /\/app\.html$/,
  /\/manifest\.json$/,
  /\.(?:css|woff2?|ttf|otf|eot|svg|png|jpg|jpeg|gif|ico)$/,
];

// ── Install: precache the app shell ──────────────────────────────────────
self.addEventListener('install', function (e) {
  e.waitUntil(
    caches.open(SHELL_CACHE)
      .then(function (c) { return c.addAll(SHELL_URLS); })
      .then(function () { return self.skipWaiting(); })
  );
});

// ── Activate: drop old caches, claim clients ─────────────────────────────
self.addEventListener('activate', function (e) {
  e.waitUntil(
    caches.keys().then(function (names) {
      return Promise.all(
        names
          .filter(function (n) {
            return n.startsWith('mansa-') && n !== SHELL_CACHE && n !== API_CACHE;
          })
          .map(function (n) { return caches.delete(n); })
      );
    }).then(function () { return self.clients.claim(); })
  );
});

// ── Helpers ──────────────────────────────────────────────────────────────
function isNavigation(req) {
  return req.mode === 'navigate' || (req.method === 'GET' && req.headers.get('accept')?.includes('text/html'));
}
function shouldCacheFirst(url) {
  return CACHE_FIRST_PATTERNS.some(function (p) { return p.test(url.pathname); });
}
function shouldNeverCache(url) {
  return NEVER_CACHE_PATTERNS.some(function (p) { return p.test(url.pathname); });
}

// Stamp metadata onto responses we cache so we can expire them.
function stampResponse(resp) {
  const headers = new Headers(resp.headers);
  headers.set('x-mansa-cached-at', String(Date.now()));
  return resp.blob().then(function (body) {
    return new Response(body, { status: resp.status, statusText: resp.statusText, headers: headers });
  });
}
function isFresh(resp) {
  const stamp = parseInt(resp.headers.get('x-mansa-cached-at') || '0', 10);
  return stamp && (Date.now() - stamp < API_TTL_MS);
}

// ── Fetch dispatcher ─────────────────────────────────────────────────────
self.addEventListener('fetch', function (e) {
  const req = e.request;
  if (req.method !== 'GET') return;  // mutations bypass SW

  const url = new URL(req.url);

  // Never cache auth/payment/admin endpoints — go straight to network.
  if (shouldNeverCache(url)) {
    return;  // browser default = network-only
  }

  // Strategy 1: cache-first for shell + static assets.
  if (shouldCacheFirst(url)) {
    e.respondWith(
      caches.match(req).then(function (cached) {
        if (cached) return cached;
        return fetch(req).then(function (resp) {
          if (resp.ok) {
            const clone = resp.clone();
            caches.open(SHELL_CACHE).then(function (c) { c.put(req, clone); });
          }
          return resp;
        }).catch(function () {
          // Navigation fallback — serve the shell or a tiny offline page.
          if (isNavigation(req)) return caches.match('./app.html');
          return new Response('', { status: 504, statusText: 'Gateway Timeout' });
        });
      })
    );
    return;
  }

  // Strategy 2: network-first w/ 5-min cache fallback for /api/* GETs.
  if (url.pathname.startsWith('/api/')) {
    e.respondWith(
      fetch(req).then(function (resp) {
        if (resp.ok) {
          const clone = resp.clone();
          stampResponse(clone).then(function (stamped) {
            caches.open(API_CACHE).then(function (c) { c.put(req, stamped); });
          });
        }
        return resp;
      }).catch(function () {
        return caches.match(req).then(function (cached) {
          if (cached && isFresh(cached)) return cached;
          if (cached) {
            // Stale but better than nothing — annotate for the UI.
            const headers = new Headers(cached.headers);
            headers.set('x-mansa-stale', '1');
            return cached.blob().then(function (body) {
              return new Response(body, { status: cached.status, headers: headers });
            });
          }
          return new Response(JSON.stringify({ error: 'offline', code: 503 }),
            { status: 503, headers: { 'Content-Type': 'application/json' } });
        });
      })
    );
    return;
  }

  // Default: network with offline fallback for navigations.
  e.respondWith(
    fetch(req).catch(function () {
      if (isNavigation(req)) {
        return caches.match('./app.html').then(function (cached) {
          if (cached) return cached;
          return new Response(
            '<!DOCTYPE html><html><body style="background:#0A0A0F;color:#F0EDE6;font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;text-align:center"><div><h1 style="color:#C9A84C;font-size:32px">MANSA</h1><p style="margin-top:12px;color:#9A9488">Vous êtes hors-ligne.</p><button onclick="location.reload()" style="margin-top:20px;padding:10px 24px;background:#C9A84C;color:#0A0A0F;border:none;border-radius:6px;font-weight:700;cursor:pointer">Réessayer</button></div></body></html>',
            { headers: { 'Content-Type': 'text/html' } }
          );
        });
      }
      return new Response('', { status: 504 });
    })
  );
});

// ── Update notification: tell clients when a new SW takes over ───────────
self.addEventListener('message', function (e) {
  if (e.data === 'SKIP_WAITING') self.skipWaiting();
});
