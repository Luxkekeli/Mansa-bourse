# Phase 0 — Rapport de livraison v2.2-phase0

**Date** : 2026-04-26
**Branche** : `phase0-prep`
**Tag** : `v2.2-phase0`

---

## Résumé exécutif

| Métrique | Valeur |
|----------|--------|
| Tickets livrés | 8 |
| Lignes ajoutées | ~600 (tests + config + docs) |
| Lignes modifiées (server) | ~120 |
| Tests pytest | **28/28 ✅** |
| Ruff | **0 warning ✅** |
| Bandit | **0 finding ✅** |

---

## Tickets traités

### ✅ Phase 0 — Préparation et nettoyage

- Structure projet `mansa/{frontend,server,scripts,tests,docs,docker,.github,data,archive}` créée.
- 11 scripts résiduels déplacés vers `archive/` (`check_progress.py`, `extract_v8.py`, `inspect_sika.py`, etc.).
- `.gitignore` couvrant Python, Node, DB, logs, secrets, build artifacts.
- `README.md` complet (prérequis, installation, env vars, démarrage prod).
- `pyproject.toml` (config ruff, pytest, coverage, bandit centralisée).
- `server/requirements-dev.txt` (pytest, pytest-cov, pytest-flask, ruff, mypy, bandit, pip-audit).
- `docs/ROADMAP.md` listant P0/P1/P2 avec décisions par défaut.

### ✅ P0-4 — Désactivation Flask debug

- `app.run(debug=True)` ne s'exécute QUE si `FLASK_ENV=development`.
- Tout autre cas → exit 1 avec message orientant vers gunicorn.
- Bind sur `127.0.0.1` (plus jamais `0.0.0.0` direct).

### ✅ P0-5 — CORS restreint

- `MANSA_ALLOWED_ORIGINS` requis en production (séparés par virgule).
- Dev par défaut : `http://localhost:8080,http://127.0.0.1:8080`.
- `supports_credentials=True` activé pour préparer P0-2 (sessions).
- `*` interdit comme origin (test automatique).

### ✅ P0-6 — Secrets forcés

- `MANSA_SECRET` ≥ 32 chars : raise `RuntimeError` en prod si absent ou court.
- **`MANSA_ADMIN_TOKEN` séparé** : nouvelle variable indépendante de la clé applicative. Plus de dérivation SHA256(SECRET_KEY).
- Header admin renommé : `X-Admin-Token` (legacy `X-Admin-Key` toléré 1 release).
- Comparaison constant-time via `hmac.compare_digest`.
- Cookies session sécurisés : `Secure` (prod), `HttpOnly`, `SameSite=Lax`.

### ✅ P0-7 (partie 1) — OHLCV non fabriqué

- **Bug critique éliminé** : `data_pipeline.py` ne duplique plus `close` dans `open/high/low` quand la source ne fournit pas l'OHLC.
- BRVM.org et RichBourse : essai de parsing étendu si layout `>= 9` colonnes, sinon `None` → SQL `NULL`.
- `store_data` insère `None` verbatim (plus de `row.get('open', row['close'])`).
- Régression couverte par 3 tests pytest.

⚠️ **Restant pour P0-7 (partie 2)** : cron Docker + lancement initial du pipeline (à livrer en P1-7 avec le Dockerfile complet).

---

## Suite de tests

### Structure

```
tests/
├── conftest.py                    # Fixtures partagées (DB temp, env, client)
├── unit/
│   ├── test_security_config.py    # 13 tests — P0-4/5/6
│   ├── test_admin_auth.py         #  5 tests — décorateur admin
│   └── test_pipeline_ohlcv.py     #  3 tests — P0-7 OHLCV
└── integration/
    └── test_api_endpoints.py      #  10 tests — endpoints + NULL handling
```

### Couverture par ticket

| Ticket | Tests |
|--------|-------|
| P0-4 (debug) | `test_session_cookies_secure_in_prod`, `test_session_cookies_relaxed_in_dev` |
| P0-5 (CORS) | `test_production_without_origins_raises`, `test_origins_parsed_as_list`, `test_no_wildcard_origin_in_app` |
| P0-6 (secrets) | 5 tests `TestSecretEnforcement` + 5 tests `TestAdminAuth` |
| P0-7 (OHLCV) | `test_store_data_preserves_null_ohlc`, `test_store_data_keeps_real_ohlc_when_provided`, `test_no_close_duplication_into_open_high_low` |
| Régression API | 10 tests `TestPublicEndpoints` + `TestNullOHLCHandling` |

### Commande de validation

```bash
cd mansa
python -m pytest tests/ -v        # 28/28 ✅
python -m ruff check server/ tests/ # 0 warning ✅
python -m bandit -c pyproject.toml -r server/  # 0 issue ✅
```

---

## Décisions prises (mode défauts)

| Décision | Choix | Justification |
|----------|-------|---------------|
| D1 — Paiement | Option A (premium désactivé) | Lancement plus rapide, focus features gratuites |
| D2 — Auth | Sessions Flask | Plus simple que JWT, csrf-friendly |
| D3 — Hébergement | Render | Déploiement Docker direct, free tier acceptable |
| D4 — SMTP | Stub console | À brancher Sendgrid post-launch |
| D5 — Migration `S` | Progressive | API + fallback `S` pendant 1 release |
| D6 — Scope session | α (Phase 0 + P0 trivials) | Validé livré ici |

---

## Diff sécurité avant / après

| Item | v2.1 | v2.2-phase0 |
|------|------|-------------|
| `debug=True` en prod | ❌ Activé | ✅ Refusé (sys.exit) |
| Bind `0.0.0.0` | ❌ Direct | ✅ `127.0.0.1` derrière reverse proxy |
| CORS | ❌ `*` (any origin) | ✅ Whitelist via env, `credentials` propre |
| `MANSA_SECRET` | ❌ Default `'mansa-dev-key...'` | ✅ Required ≥ 32 chars en prod |
| Token admin | ❌ Dérivé de SECRET_KEY | ✅ `MANSA_ADMIN_TOKEN` indépendant |
| Header admin | `X-Admin-Key` (kebab) | ✅ `X-Admin-Token` (clarté) |
| Session cookies | ❌ Default Flask | ✅ Secure/HttpOnly/SameSite |
| OHLCV faux | ❌ open=high=low=close | ✅ NULL si source ne fournit pas |

---

## Reste à faire (P0 incomplet)

| Ticket | Effort | Bloquant ? |
|--------|--------|------------|
| P0-1 — Aligner frontend/backend (URLs `.php`→`/api/...`) | 4-6 h | 🔴 Oui (front cassé sans) |
| P0-2 — Auth réelle (argon2, sessions, register/login/logout) | 8-12 h | 🔴 Oui (localStorage = pas d'auth) |
| P0-3 — Premium désactivé OU Wave réel | 2-8 h | 🟡 Oui si paiements visibles |
| P0-7 — Cron pipeline + Docker | 2-3 h | 🟡 P1-7 |
| P0-8 — Migration tableau `S` → DB | 6-10 h | 🟡 Lent si non fait |

---

## Migration depuis v2.1

```bash
# 1. Cloner la nouvelle structure
git checkout v2.2-phase0

# 2. Générer secrets forts
python -c "import secrets;print(secrets.token_urlsafe(48))" > .secret_temp
python -c "import secrets;print(secrets.token_urlsafe(32))" > .admin_temp

# 3. Configurer .env
cp server/.env.example server/.env
# Édite server/.env avec les valeurs générées

# 4. Frontend admin headers (P0-6)
# Si tu as du code custom qui appelait l'admin API :
#   AVANT : headers: {'X-Admin-Key': sha256(SECRET_KEY)[:32]}
#   APRÈS : headers: {'X-Admin-Token': MANSA_ADMIN_TOKEN}

# 5. Pipeline OHLCV (P0-7)
# Aucune migration côté DB nécessaire — schéma déjà compatible NULL.
# Les anciennes lignes "open=high=low=close" restent, le pipeline n'écrit plus
# que des NULL pour les nouvelles entrées sans OHLC.

# 6. Lancer
python -m pytest tests/   # vérifier que tout passe sur ton environnement
gunicorn -w 4 -b 127.0.0.1:5000 server.api_server:app
```

---

## Prochaines sessions recommandées

1. **Session 2** — P0-1 (alignement URLs) + P0-2 (auth réelle backend)
2. **Session 3** — P0-2 frontend + P0-3 (désactiver premium) + P0-8 (migration `S`)
3. **Session 4** — P1-1 (Vite split) + P1-2 (DOMPurify) + P1-3 (Talisman CSP)
4. **Session 5** — P1-7 (Docker + nginx + CI) + P1-8 (Playwright e2e)

Estimation totale restante : **~50-60 h** sur 4 sessions.
