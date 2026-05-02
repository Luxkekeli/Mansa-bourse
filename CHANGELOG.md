# MANSA — Changelog

Toutes les modifications notables de la plateforme depuis la première session de
hardening v2.1 → v2.2.

Format : [Keep a Changelog](https://keepachangelog.com/fr/1.0.0/),
versioning : [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [2.2.0-session5] — 2026-04-28 — ENTERPRISE-READY

### Sécurité (P1)
- **P1-3** : Talisman activé. CSP stricte (default-src 'self', whitelist Chart.js
  CDN, frame-ancestors 'none', object-src 'none'), HSTS prod
  (`max-age=31536000; includeSubDomains`), X-Frame-Options DENY,
  Permissions-Policy bloquant geo/mic/cam/payment/usb/topics, Referrer-Policy
  strict-origin-when-cross-origin.
- **P1-2** : DOMPurify chargé avec SRI. Helpers globaux `safeSetHTML`,
  `safeInsertHTML`, `escapeText`. `renderCommMsg` et `bbot.addMsg` refactorés.
- **P1-4** : SRI ajouté sur Chart.js + DOMPurify CDN.
- **P1-10** : Cloudflare Turnstile intégré (`server/captcha.py` + frontend
  loader conditionnel). Endpoints register/forgot/community/post gates derrière
  un token vérifié serveur. Mode bypass pour CI/dev.

### Performance (P1)
- **P1-9** : `/api/tickers` et `/api/indices` réécrits en CTE + window function.
  Plan EXPLAIN passe de 96 SCANS à 1 SCAN + 1 SORT.
- **P1-5** : Service Worker v2.2 versionné. 3 stratégies : cache-first (assets),
  network-first w/ TTL 5 min (API), network-only (auth/payment/admin).

### Internationalisation (P1)
- **P1-6** : i18n FR/EN étendue de 74 → ~165 clés/langue. Nouveaux namespaces :
  auth, community, screener, portfolio, error, time, unit, action, status,
  onboarding.

### Tests (P1)
- **P1-8** : 10 tests Playwright e2e (smoke, auth round-trip, community XSS,
  screener anti-SQLi, ticker detail, i18n switch).
- 101 tests pytest (unit + integration), 0 ruff, 0 bandit.

### Architecture (P1)
- **P1-1** : Vite scaffold posé (`vite.config.ts`, `tsconfig.json`,
  `frontend/src/{main,api,auth,i18n,router,data,styles}.ts`,
  `frontend/src/tabs/dashboard.ts`, `frontend/src/i18n/{fr,en}.json`).
  Migration tab-par-tab documentée dans `docs/VITE_MIGRATION.md`. App.html
  reste le monolithe servi en prod tant que les tabs ne sont pas migrés.

### Observabilité (P2)
- Sentry hook conditionnel (env `MANSA_SENTRY_DSN`).
- Plausible analytics (privacy-first, cookieless, conditionnel via
  `MANSA_PLAUSIBLE_DOMAIN`).
- Footer dynamique « Données: BRVM.org · MAJ il y a X min » alimenté par
  `/api/health`, refresh chaque minute.
- Helper `scripts/dump_tickers_to_data_ts.py` pour générer le snapshot
  `frontend/src/data.ts` depuis la DB.

### Endpoints API
- `GET /api/config` — Configuration publique (turnstile site_key, payments
  enabled, plausible_domain, version). Ne renvoie JAMAIS de secret.

---

## [2.2.0-session4] — 2026-04-26

### Sécurité
- DOMPurify pour défense en profondeur XSS.
- Talisman/CSP/HSTS.
- SRI sur Chart.js.
- Couverture Playwright initiale : 4 e2e tests.
- `docs/RELEASE_CHECKLIST.md` (47 items pré-launch).

---

## [2.2.0-session3] — 2026-04-26

### Backend
- **P0-3** : Premium désactivé par défaut (Option A). Endpoints
  `/api/payment/*` retournent 503 sauf si `MANSA_PAYMENTS_ENABLED=1`.
- **P0-8** : Migration progressive du tableau `S` → DB via
  `scripts/seed_from_app_html.py` (parser tolérant pour la JS shorthand).
- **P1-7** : Dockerfile multi-stage, `docker-compose.yml`, nginx config,
  `render.yaml`, GitHub Actions CI workflow.
- `docs/DEPLOY_RENDER.md` (12 sections, guide complet).

---

## [2.2.0-session2] — 2026-04-26

### Sécurité critique
- **P0-1** : Frontend appelle Flask uniquement (9 URLs `.php` retirées).
  Nouveaux endpoints `/api/chat`, `/api/quiz/email`, `/api/community/post`,
  `/api/community/poll`.
- **P0-2** : Auth réelle. Argon2id (OWASP 2024 params), table `users`,
  sessions Flask Secure/HttpOnly/SameSite=Lax. Endpoints `/api/auth/{register,
  login, logout, me, verify, forgot, reset}`. Frontend `localStorage.bfin_users`
  (annuaire en clair) **supprimé**.
- Sanitization community via bleach. Champ raw `content` jamais exposé.

### Tests
- 64 tests pytest (28 → 64).

---

## [2.2.0-phase0] — 2026-04-25

### Préparation production
- **P0-4** : `debug=True` désactivé par défaut, refusé en prod.
- **P0-5** : CORS via `MANSA_ALLOWED_ORIGINS` (plus de wildcard `*`).
- **P0-6** : `MANSA_SECRET` ≥ 32 chars requis. Token admin séparé
  (`MANSA_ADMIN_TOKEN`), header `X-Admin-Token` (constant-time compare).
- **P0-7** : OHLCV non fabriqué — `open=high=low=close` retiré du pipeline.
  NULL préservé dans la DB quand la source ne fournit pas l'OHLC.

### Structure projet
- Restructure en `mansa/{frontend,server,scripts,tests,docs,docker,.github,
  data,archive}`.
- `pyproject.toml` (ruff, pytest, coverage, bandit centralisé).
- 28 tests pytest initiaux.

---

## [2.1.0] — Baseline (avant audit)

État originel avec :
- ❌ `debug=True` en prod
- ❌ CORS `*`
- ❌ `MANSA_SECRET` default
- ❌ Auth localStorage `btoa()` (Base64 = pas de hashing)
- ❌ Frontend appelait des routes PHP fantômes
- ❌ Pipeline corrompait les OHLC

8 problèmes P0 + 10 P1 + 6 P2 identifiés lors de l'audit technique.

---

## Migration upgrade path

```bash
# Depuis n'importe quelle version v2.2.x antérieure :
git pull
pip install -r server/requirements.txt   # nouvelles deps : argon2-cffi, bleach, flask-talisman
python server/db_init.py                 # idempotent, ajoute les nouvelles tables
python -m pytest tests/                  # vérifier qu'on est vert
gunicorn -w 4 -b 127.0.0.1:5000 server.api_server:app
```
