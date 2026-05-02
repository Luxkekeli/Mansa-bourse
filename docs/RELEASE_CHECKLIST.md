# MANSA — Checklist de mise en production

Cette checklist couvre tout ce qui doit être vert avant de lancer publiquement.

---

## 🟢 Bloquant (P0) — TOUS LIVRÉS

| # | Item | État | Vérif |
|---|------|------|-------|
| P0-1 | Frontend appelle Flask (plus de `.php`) | ✅ | `grep '\.php' frontend/app.html` → 3 commentaires uniquement |
| P0-2 | Auth réelle argon2 + sessions | ✅ | 19 tests `test_auth.py` |
| P0-3 | Premium désactivé (Option A) | ✅ | 503 sur `/api/payment/*` |
| P0-4 | Debug Flask off en prod | ✅ | `test_session_cookies_secure_in_prod` |
| P0-5 | CORS via `MANSA_ALLOWED_ORIGINS` | ✅ | Pas de `*` dans CSP/CORS |
| P0-6 | `MANSA_SECRET` ≥ 32 + token admin séparé | ✅ | RuntimeError si manquant en prod |
| P0-7 | Pipeline OHLCV propre | ✅ | NULL préservé dans la DB |
| P0-8 | Migration `S` → DB | ✅ | 48 tickers + 48 fundamentals + 48 div en DB |

---

## 🟡 Recommandé (P1)

| # | Item | État | Notes |
|---|------|------|-------|
| P1-2 | DOMPurify XSS defense-in-depth | ✅ session 4 | Sites user-data routés via `safeSetHTML` |
| P1-3 | Talisman CSP + HSTS + frame-options | ✅ session 4 | 8 tests `test_security_headers.py` |
| P1-4 | SRI sur Chart.js | ✅ session 4 | `integrity=` ajouté |
| P1-7 | Docker + nginx + CI + Render | ✅ session 3 | À valider sur staging |
| P1-8 | Tests pytest 80% + Playwright | 🟡 partiel | Backend ~75%, e2e scaffolded (3 tests) |
| P1-1 | Découpage Vite | ⏳ | Non bloquant |
| P1-5 | Workbox SW | ⏳ | Sw.js actuel fonctionne |
| P1-6 | i18n FR/EN complète | ⏳ | FR seulement OK pour launch |
| P1-9 | Optimisation `/api/tickers` CTE | ⏳ | OK avec 48 tickers |
| P1-10 | Cloudflare Turnstile | ⏳ | Rate-limit suffit pour launch |

---

## 📋 À faire AVANT de cliquer "publier"

### Configuration

- [ ] Générer `MANSA_SECRET` aléatoire (≥ 48 chars) et le mettre dans Render
- [ ] Générer `MANSA_ADMIN_TOKEN` aléatoire (≥ 32 chars) et le mettre dans Render
- [ ] Définir `MANSA_ALLOWED_ORIGINS` avec le ou les domaines réels
- [ ] Définir `FLASK_ENV=production`
- [ ] Confirmer que `MANSA_PAYMENTS_ENABLED` n'est PAS défini (= 0)

### Données

- [ ] Lancer `python scripts/seed_from_app_html.py` pour peupler tickers/dividends/fundamentals
- [ ] Lancer 1 fois manuellement le pipeline pour avoir des prix à jour
- [ ] Vérifier `/api/health` retourne `tickers >= 48` et `price_rows > 100k`

### Vérifications de sécurité

- [ ] Test : sans login, GET `/api/portfolio` → 401 (placeholder, ajout en P0-2 frontend)
- [ ] Test : POST `/api/community/post` sans auth → 401
- [ ] Test : GET `/api/payment/plans` → 503
- [ ] Test : GET `/api/admin/weekly-report` sans token → 401
- [ ] Test : GET `/api/admin/weekly-report` avec token wrong → 401
- [ ] Test : POST `/api/auth/login` 6 fois en 15 min → 6e bloquée (rate limit)
- [ ] Curl `-I https://mansa.finance/api/health` → headers `Strict-Transport-Security`, `Content-Security-Policy`, `X-Frame-Options: DENY`, `Permissions-Policy: geolocation=()...`
- [ ] Tester depuis https://securityheaders.com → note ≥ A
- [ ] Tester depuis https://observatory.mozilla.org → note ≥ B+

### Frontend

- [ ] Tester sur Chrome desktop, Firefox, Safari iOS
- [ ] Tester PWA install (Chrome Android)
- [ ] Vérifier que `/api/auth/me` est appelé au load (Network tab)
- [ ] Tester login → access ticker page → logout → tentative d'accès refusée
- [ ] Tester un message community avec `<script>alert('x')</script>` → injection bloquée

### Performance

- [ ] Lighthouse mobile : Performance ≥ 80, A11y ≥ 90, SEO ≥ 90
- [ ] First Contentful Paint < 2 s sur réseau 3G
- [ ] gunicorn workers = 4, threads = 2 (ajusté selon Render plan)

### Tests

- [ ] `pytest tests/` → 91/91 ✅
- [ ] `ruff check server/ tests/ scripts/` → 0 ✅
- [ ] `bandit -c pyproject.toml -r server/ scripts/ -ll` → 0 ✅
- [ ] `pip-audit -r server/requirements.txt --strict` → 0 high/critical ✅
- [ ] `npx playwright test` (si stack tournée) → 4/4 ✅

### Backup & rollback

- [ ] Dump DB initial : `sqlite3 mansa.db .dump > backup_$(date +%F).sql`
- [ ] Tester un rollback (Render → Deploys → sélectionner un deploy précédent)
- [ ] Documenter le contact d'urgence (toi)

### Communication

- [ ] Préparer le post LinkedIn / X annonce
- [ ] Mettre à jour `mansa.finance` page d'accueil avec un statut "BETA OUVERTE"
- [ ] Préparer un canal de feedback (typeform, email)

---

## 🚀 Jour J — séquence de lancement

```
H-2h  : Déploiement final sur Render
H-1h  : Vérifs santé + securityheaders.com
H-30m : Smoke test manuel (login + 5 fonctionnalités clés)
H     : Annonce publique + post LinkedIn
H+1h  : Surveiller logs Render + emails alertes
H+2h  : Premier feedback users — note les frictions
H+24h : Bilan rapide — count users / messages community / errors Sentry
```

---

## 📞 Contacts

- **Lead** : Kekele Donon (dononkekeli@gmail.com)
- **Render dashboard** : https://dashboard.render.com
- **Repo** : (à renseigner)
- **Status page** : `/api/health`

---

## 🔄 Plan post-launch (1ère semaine)

Jour 1-3 : monitoring intensif, hotfixes uniquement.
Jour 4-7 : début Session 5 (P1-1 Vite + P1-6 i18n complète).
Semaine 2 : activation premium (P0-3 réversible) si feedback positif.
