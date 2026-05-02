# MANSA — Roadmap production

## Statut global

| Phase | Avancement | Date livraison |
|-------|------------|----------------|
| Phase 0 — Préparation | ✅ 100% | v2.2-phase0 |
| Phase 1 — P0 (8 bloquants) | 🟡 50% (4/8) | en cours |
| Phase 2 — P1 (10 majeurs) | ⏳ 0% | à venir |
| Phase 3 — P2 (6 mineurs) | ⏳ 0% | post-launch |

---

## Phase 0 — Préparation et nettoyage ✅

- [x] Structure projet `mansa/{frontend,server,scripts,tests,docs,docker,.github,data,archive}`
- [x] Déplacement scripts résiduels vers `archive/`
- [x] `.gitignore` complet (DB, logs, .env, node_modules, dist)
- [x] `README.md` avec installation, structure, env vars, démarrage prod
- [x] `pyproject.toml` (ruff, pytest, coverage, bandit)
- [x] `requirements-dev.txt` (pytest, ruff, mypy, bandit)
- [x] `docs/ROADMAP.md` (ce document)

---

## Phase 1 — Tickets P0 (bloquants production)

| Ticket | Description | État |
|--------|-------------|------|
| P0-1 | Aligner frontend et backend (URLs `.php` → `/api/...`) | ⏳ Session future |
| P0-2 | Auth réelle serveur (sessions Flask, argon2, rate limit) | ⏳ Session future |
| P0-3 | Premium désactivé (Option A par défaut) | ⏳ Session future |
| P0-4 | Désactiver `debug=True` Flask | ✅ Phase 0 |
| P0-5 | Restreindre CORS via `MANSA_ALLOWED_ORIGINS` | ✅ Phase 0 |
| P0-6 | `MANSA_SECRET` ≥ 32 chars + `MANSA_ADMIN_TOKEN` séparé | ✅ Phase 0 |
| P0-7 | Pipeline OHLCV corrigé + cron Docker | 🟡 Partie 1 ✅ / cron ⏳ |
| P0-8 | Migration tableau `S` → tables DB (mode progressif) | ⏳ Session future |

### Décisions prises (par défaut)

- **D1 — Paiement** : Option A (premium désactivé pour le lancement)
- **D2 — Auth** : Sessions Flask server-side avec cookies `Secure/HttpOnly/SameSite=Lax`
- **D3 — Hébergement** : Render (Dockerfile + render.yaml)
- **D4 — SMTP** : Stub console pour début, à brancher Sendgrid plus tard
- **D5 — Migration** : Progressive (API + fallback `S` pendant 1 release)
- **D6 — Scope session 1** : Phase 0 + P0-4/5/6/7-partiel (livré v2.2-phase0)

---

## Phase 2 — Tickets P1 (avant lancement officiel)

| Ticket | Description |
|--------|-------------|
| P1-1 | Découpage `app.html` en modules + Vite |
| P1-2 | DOMPurify sur 77 `innerHTML=` |
| P1-3 | `flask-talisman` (CSP, HSTS, frame-options) |
| P1-4 | SRI sur Chart.js (ou self-host) |
| P1-5 | Service Worker via Workbox (cache-first vs network-first) |
| P1-6 | i18n complète FR/EN (~1000 clés) |
| P1-7 | Dockerfile multistage + docker-compose + nginx + CI GitHub |
| P1-8 | Tests pytest 80% + Playwright e2e 5 parcours |
| P1-9 | Optimisation `/api/tickers` via CTE |
| P1-10 | Cloudflare Turnstile sur register/forgot/community |

---

## Phase 3 — Post-launch P2

- Logo professionnel (designer)
- Suppression `archive/`
- Footer "Données : BRVM.org · MAJ il y a 12 min"
- Sentry (erreurs JS+Python) + Plausible/Umami (analytics)
- OpenAPI/Swagger via `flask-smorest`
- Audits semestriels (`npm audit`, `pip-audit`, `bandit`)

---

## Critères d'acceptation finaux production

```bash
# Backend
pytest --cov=server --cov-fail-under=80    # vert
ruff check server/                          # 0 warning
bandit -r server/                           # 0 high/critical

# Frontend
npm run build                               # produit dist/ propre
npm audit --audit-level=high                # 0 high

# E2E
npx playwright test                         # 5 parcours verts

# Docker
docker compose up -d
curl -f http://localhost/api/health         # 200 OK
curl -f -I http://localhost/                # CSP/HSTS/X-Frame présents
```

Une fois tous verts → tag `v2.2.0` + PR `feat: production-ready v2.2`.
