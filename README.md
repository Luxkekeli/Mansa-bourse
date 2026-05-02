# MANSA — Plateforme d'investissement BRVM/UEMOA

Plateforme web d'analyse et d'investissement pour la Bourse Régionale des Valeurs Mobilières (BRVM) couvrant les 8 pays de l'UEMOA. Frontend en HTML/CSS/JS pur, backend Flask + SQLite.

> **État actuel : v2.2-phase0** — Préparation production en cours. Voir `docs/ROADMAP.md` pour l'avancement.

---

## Prérequis

| Outil | Version min |
|-------|-------------|
| Python | 3.10+ |
| Node.js | 18+ (pour build futur) |
| SQLite | 3.35+ (livré avec Python) |
| Git | 2.30+ |

---

## Installation rapide (dev)

```bash
# 1. Cloner et entrer dans le dossier
git clone <repo> mansa && cd mansa

# 2. Environnement Python
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux/macOS

# 3. Dépendances
pip install -r server/requirements.txt
pip install -r server/requirements-dev.txt

# 4. Configuration
copy server\.env.example server\.env
# Édite server/.env et définit MANSA_SECRET (>=32 chars)

# 5. Initialiser la base
python server/db_init.py

# 6. Lancer l'API
python -m flask --app server.api_server run --port 5000
```

Puis ouvre `frontend/app.html` dans le navigateur (ou via un serveur statique : `python -m http.server 8080 -d frontend`).

---

## Structure du projet

```
mansa/
├── frontend/               # SPA HTML/CSS/JS (sera découpée via Vite en P1)
│   ├── app.html            # Application complète (transitoire)
│   ├── sw.js               # Service Worker PWA
│   └── manifest.json       # Manifest PWA
├── server/                 # API Flask + SQLite
│   ├── api_server.py       # Routes REST
│   ├── db_init.py          # Initialisation schéma
│   ├── data_pipeline.py    # Pipeline ingestion BRVM
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   └── .env.example
├── scripts/                # Scrapers & utilitaires data
├── tests/                  # Pytest + Playwright
│   ├── unit/
│   ├── integration/
│   └── e2e/
├── docs/                   # Documentation, rapport, roadmap
├── docker/                 # Dockerfile, compose, nginx (P1-7)
├── .github/workflows/      # CI/CD (P1-7)
├── data/samples/           # Données d'exemple (CSV/JSON)
└── archive/                # Anciens scripts (à supprimer post-validation)
```

---

## Variables d'environnement

| Variable | Obligatoire | Description |
|----------|-------------|-------------|
| `MANSA_SECRET` | ✅ | Clé applicative, ≥ 32 caractères aléatoires |
| `MANSA_ADMIN_TOKEN` | ✅ | Token admin séparé pour l'API admin |
| `MANSA_ALLOWED_ORIGINS` | ✅ (prod) | CORS, séparés par virgule (ex: `https://mansa.finance,https://www.mansa.finance`) |
| `MANSA_DB` | non | Chemin DB SQLite (défaut : `../mansa.db`) |
| `FLASK_ENV` | non | `development` active debug ; sinon production |
| `MANSA_ALERT_EMAIL` | non | Destinataire alertes pipeline |
| `MANSA_SMTP_*` | non | Configuration SMTP |

Génère un secret valide :

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

---

## Tests

```bash
# Suite unitaire + intégration
pytest tests/ --cov=server --cov-report=term-missing

# Lint
ruff check server/ scripts/ tests/

# Audit sécurité
bandit -r server/

# E2E (après installation Playwright)
npx playwright test
```

Cible CI : **80% de coverage** backend, 0 warning ruff, 0 finding High/Critical bandit.

---

## Démarrage production

⚠️ **Ne jamais lancer `python api_server.py` directement en production.**

```bash
# Définir les variables d'environnement
export MANSA_SECRET="$(python -c 'import secrets;print(secrets.token_urlsafe(48))')"
export MANSA_ADMIN_TOKEN="$(python -c 'import secrets;print(secrets.token_urlsafe(32))')"
export MANSA_ALLOWED_ORIGINS="https://mansa.finance,https://www.mansa.finance"
export FLASK_ENV=production

# Lancer via gunicorn
gunicorn -w 4 -b 127.0.0.1:5000 server.api_server:app
```

Puis configurer nginx en reverse proxy (voir `docker/nginx.conf` une fois P1-7 livré).

---

## Roadmap

| Phase | État | Description |
|-------|------|-------------|
| **Phase 0** | ✅ Livrée | Restructure projet, gitignore, README, configs lint |
| **P0** (8 tickets) | 🟡 Partiel | Sécurité de base : debug, CORS, secret, OHLCV, auth, paiement |
| **P1** (10 tickets) | ⏳ À venir | Vite, DOMPurify, CSP, Workbox, i18n, Docker, tests |
| **P2** (6 tickets) | ⏳ À venir | Logo pro, monitoring, OpenAPI |

Voir `docs/ROADMAP.md` pour le détail.

---

## Licence

Propriétaire. Tous droits réservés. Contact : dononkekeli@gmail.com
