# Déploiement Render — guide pas à pas

Cible : déployer MANSA sur [Render.com](https://render.com) avec un service web Docker + un cron job pour le pipeline.

## 1. Pré-requis

| Item | Comment |
|------|---------|
| Compte Render (gratuit) | https://dashboard.render.com/register |
| Repo GitHub avec MANSA | Push le contenu du ZIP sur un repo privé |
| Domaine (optionnel) | `mansa.finance` ou autre |

## 2. Préparer les secrets

Sur ta machine locale :

```bash
python -c "import secrets;print('MANSA_SECRET=', secrets.token_urlsafe(48))"
python -c "import secrets;print('MANSA_ADMIN_TOKEN=', secrets.token_urlsafe(32))"
```

Garde ces valeurs précieusement (gestionnaire de mots de passe). Tu les colleras dans Render.

## 3. Créer le Blueprint

1. Sur Render → **New +** → **Blueprint**.
2. Connecte ton repo GitHub.
3. Render détecte automatiquement `render.yaml` à la racine.
4. **Avant le premier déploiement** :
   - Édite `render.yaml` ligne `repo:` pour pointer vers ton vrai repo.
   - Commit + push.

## 4. Renseigner les variables sensibles

Render va te lister les vars `sync: false` non remplies. Renseigne :

| Variable | Valeur |
|----------|--------|
| `MANSA_SECRET` | Sortie de `secrets.token_urlsafe(48)` |
| `MANSA_ADMIN_TOKEN` | Sortie de `secrets.token_urlsafe(32)` |
| `MANSA_ALLOWED_ORIGINS` | `https://mansa-web.onrender.com,https://mansa.finance` |

Pour le **cron pipeline**, renseigne les **mêmes valeurs** (les services partagent le disque).

## 5. Premier déploiement

Render va :

1. Cloner le repo.
2. Builder le `docker/Dockerfile` (10-15 min la 1re fois — argon2-cffi compile).
3. Lancer `entrypoint.sh` qui crée le schéma DB sur le disque persistant.
4. Démarrer gunicorn et tester `/api/health`.

**Vérification** :

```bash
curl -i https://mansa-web.onrender.com/api/health
# → 200 OK
# → Strict-Transport-Security: max-age=31536000; includeSubDomains
# → Content-Security-Policy: default-src 'self'; ...
```

## 6. Domaine custom (optionnel)

1. Render Dashboard → service `mansa-web` → **Settings** → **Custom Domains**.
2. Ajoute `mansa.finance` et `www.mansa.finance`.
3. Crée les 2 enregistrements DNS chez ton registrar :
   - `mansa.finance` → ALIAS/ANAME vers `mansa-web.onrender.com`
   - `www.mansa.finance` → CNAME vers `mansa-web.onrender.com`
4. Render génère un certificat Let's Encrypt automatiquement.
5. **Mets à jour `MANSA_ALLOWED_ORIGINS`** : `https://mansa.finance,https://www.mansa.finance`.

## 7. Vérifier le cron pipeline

Render Dashboard → service `mansa-pipeline` → **Logs**.

Le job tourne `*/15 10-15 * * 1-5` (toutes les 15 min, heures de marché GMT, lun–ven). Tu devrais voir des entrées dans les logs comme :

```
[Source 1] Fetching from BRVM.org...
[BRVM.org] Fetched 48 tickers
[DB] Stored 48 rows from BRVM.org
```

Si tu veux tester immédiatement : **Manual Run** dans la page du cron.

## 8. Activer le rate limit Redis (recommandé prod)

Le `flask-limiter` utilise actuellement `memory://` — non partagé entre les workers gunicorn. En multi-process tu perds en précision et ouvres une porte aux attaques par parallélisme.

1. Render Dashboard → **New +** → **Redis**.
2. Plan **starter** (gratuit, 25 MB) suffit.
3. Récupère l'URL `redis://...` interne.
4. Ajoute la var au service `mansa-web` :
   ```
   RATELIMIT_STORAGE_URI=redis://red-xxx:6379/0
   ```
5. Mets à jour `server/api_server.py` :
   ```python
   limiter = Limiter(get_remote_address, app=app,
                     default_limits=["200 per minute", "5000 per hour"],
                     storage_uri=os.environ.get("RATELIMIT_STORAGE_URI", "memory://"))
   ```
6. Redéploie.

## 9. Branchement SMTP réel

Le stub email log à stdout. Pour passer au réel :

1. Crée un compte Sendgrid / Mailgun / SES.
2. Génère un API key.
3. Modifie `server/auth.py::_send_email_stub` pour appeler le SDK provider.
4. Ajoute les vars d'env (`SENDGRID_API_KEY`, etc.) dans Render.

Voir `docs/SESSION2_REPORT.md` § "À surveiller en prod" pour les détails.

## 10. Surveillance & alertes

**Render natif** : healthcheck déjà configuré (`/api/health`). Si 3 checks consécutifs échouent, restart auto.

**À ajouter** :
- Sentry (erreurs JS + Python) — `pip install sentry-sdk[flask]` + DSN dans `.env`.
- Plausible / Umami (analytics non-trackant) — script JS dans `<head>`.
- UptimeRobot (gratuit) → ping toutes les 5 min sur `/api/health`.

## 11. Rollback

Si un déploiement plante :

1. Dashboard → service → **Deploys** → sélectionner un deploy précédent → **Rollback**.
2. Le disque persistant est conservé (les données de la DB ne sont pas perdues).

## 12. Coûts estimés

| Service | Plan | Coût mensuel |
|---------|------|--------------|
| `mansa-web` Starter | 0.5 CPU / 512 MB | ~7 $ |
| `mansa-pipeline` cron | 256 MB | gratuit (90 min/jour) |
| Disque 1 GB | persistant | 0.25 $ |
| Redis Starter | 25 MB | gratuit |
| **Total** | | **~7-8 $/mois** |

Pour passer en prod sérieux (2-5k users actifs) : plan **Standard** (2 CPU / 2 GB) à 25 $/mois.

---

**Voir aussi** :
- `docs/ROADMAP.md` — vue d'ensemble des tickets restants
- `docs/RELEASE_CHECKLIST.md` — checklist pré-launch officielle
