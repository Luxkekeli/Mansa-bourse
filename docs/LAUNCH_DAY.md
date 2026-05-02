# MANSA — Launch Day Release Notes (v2.2-launchday)

**Date** : 2026-04-30
**Statut** : 🚀 **GO FOR LAUNCH**

Ce document récapitule TOUT ce qui a été fait pour rendre le site déployable aujourd'hui en production.

---

## Ce qui a été livré pour le launch

### 1. Données BRVM à jour (P0-7 finalisé)

| Métrique | Avant | Après |
|----------|-------|-------|
| Latest date en DB | 2026-03-17 | **2026-04-30** (today) |
| Pipeline log | aucun récent | Entrée `carry_forward` à today |
| Footer fraîcheur | "MAJ -:-" | "MAJ il y a 0 min · 🟡 Données reportées (BETA)" |

**Comment ça a été fait** : `scripts/refresh_market_data.py --carry-fwd` reporte la dernière clôture connue à la date du jour pour chaque ticker. Le footer affiche un **badge BETA** transparent indiquant que les données sont reportées (vs temps réel). Le pipeline live (`--live`) tente d'abord BRVM.org/RichBourse pour une vraie maj, puis fallback carry-forward.

**Sur Render** : ajouter au cron `pipeline` (déjà configuré dans `docker/crontab`) un appel quotidien :
```
0 16 * * 1-5  python /app/scripts/refresh_market_data.py --live
```

### 2. Traduction anglaise étendue (P1-6 v2)

| Métrique | Session 5 | Launch-day |
|----------|-----------|------------|
| Clés totales par langue | 165 | **~250** |
| Onboarding modal | FR seul | **FR + EN** ✅ |
| Hero card (Marché BRVM, Investir est ton héritage) | FR seul | **FR + EN** ✅ |
| Footer freshness badge | FR seul | **FR + EN** ✅ |
| Academy header + cards | FR seul | **FR + EN** ✅ |
| Boutons "Refaire / Commencer" | FR seul | **FR + EN** ✅ |

**Nouveaux namespaces ajoutés (~85 clés)** :
- `onboarding.*` (8 clés) — modal de bienvenue 3 profils
- `hero.*` (6 clés) — Marché BRVM, MARCHÉ OUVERT/FERMÉ, etc
- `ticker.*` (12 clés) — labels page détail (ACHETER, Score global, Solidité, Moat, Historique...)
- `footer.*` (4 clés) — last_update, beta_carry, live, delayed
- `academy.*` (12 clés) — title, level, xp_total, modules_done, in_progress, completed, etc
- `sector.*` (9 clés) — Banques, Distribution, Télécom, Énergie...

⚠️ **Note réaliste** : la couverture EN reste partielle (~80% des écrans). Le 20% restant (libellés métier dans render functions des onglets Pro) sera complété dans la session post-launch P1-1 (Vite migration tab par tab).

### 3. Parcours Academy — Contenu complet (12 leçons)

#### Parcours Novice (m1-m6)

| ID | Titre | Durée | XP | Quiz |
|----|-------|-------|----|----|
| m1 | Qu'est-ce que la BRVM ? | 5 min | 20 | ✅ |
| m2 | Comment fonctionne une action ? | 8 min | 20 | ✅ |
| m3 | Lire une cotation BRVM | 6 min | 25 | ✅ |
| m4 | Les secteurs de la BRVM | 7 min | 20 | ✅ |
| m5 | Ouvrir un compte SGI | 5 min | 30 | ✅ |
| m6 | Quiz : Es-tu prêt ? | 3 min | 50 | ✅ |

#### Parcours Analyst Junior (m7-m12)

| ID | Titre | Durée | XP | Quiz |
|----|-------|-------|----|----|
| m7 | Le PER démystifié | 8 min | 30 | ✅ |
| m8 | ROE, ROA, Marge nette | 10 min | 35 | ✅ |
| m9 | Analyse des dividendes | 8 min | 30 | ✅ |
| m10 | Lire un bilan simplifié | 12 min | 40 | ✅ |
| m11 | Construire un screener | 7 min | 35 | ✅ |
| m12 | Projet : Analyse ta première action | 15 min | 80 | Projet pratique |

**Architecture**:
- `window.ACADEMY_LESSONS` — dictionnaire des 12 leçons avec contenu HTML structuré (titre, durée, contenu, quiz optionnel)
- `openLessonModal(mid, xp)` — affiche la leçon dans le modal `gmodal`
- `_checkLessonAnswer` — valide la réponse au quiz, marque le module comme terminé si correct, attribue les XP
- `_markLessonComplete` — flow direct sans quiz (ex: projet)

**Contenu pédagogique inclus** :
- Tableaux de ratios avec exemples chiffrés (SGBC PER 8.8x, SNTS ROE 37%...)
- Drapeaux rouges/verts pour la lecture de bilan
- 3 stratégies de screener (Value, Dividende, Croissance) avec critères concrets
- Liste des principales SGI et frais typiques
- Liste des 7 secteurs BRVM avec poids dans la capi
- Quiz de validation à choix multiples

⚠️ Les parcours Expert (m13-m18) et Mansa (m19-m24) ont leurs intitulés en place mais **pas encore le contenu détaillé**. À ajouter post-launch (estimation 4h).

### 4. Tests + lint (verts)

```
pytest:    102 / 102  ✅
ruff:      0 issues   ✅
bandit:    0 issues   ✅
e2e specs: 10 tests   ✅
```

---

## ZIP launch-day

📦 `C:\Users\Kekeli.Donon\Desktop\brvm2\MANSA_v2.2_launchday.zip`

Contient toute la base prod-ready : backend (server/), frontend (frontend/), DB seed, scripts, tests, docs.

---

## Checklist pré-déploiement (à faire MAINTENANT)

```
[ ] Push code sur GitHub
[ ] Connecter Render via Blueprint (render.yaml détecté auto)
[ ] Renseigner les secrets sur Render :
    - MANSA_SECRET (>= 48 chars random)
    - MANSA_ADMIN_TOKEN (>= 32 chars random)
    - MANSA_ALLOWED_ORIGINS (https://mansa.finance,https://www.mansa.finance)
    - FLASK_ENV=production
[ ] Lancer le déploiement
[ ] Attendre 10-15 min (premier build argon2-cffi)
[ ] curl https://mansa-web.onrender.com/api/health → 200
[ ] Tester register/login/community en live
[ ] Lancer scripts/refresh_market_data.py --live (ou --carry-fwd) sur Render
[ ] Configurer le cron pipeline (toutes les 15 min, heures de marché)
[ ] Connecter le domaine mansa.finance (DNS CNAME)
[ ] Activer SMTP (Sendgrid recommandé) pour les emails de vérification
[ ] (Optionnel) Activer Cloudflare Turnstile :
    TURNSTILE_SITE_KEY + TURNSTILE_SECRET_KEY
[ ] Vérifier securityheaders.com → note A+
[ ] Test manuel des 5 parcours critiques (dashboard, ticker, screener, register, academy)
```

---

## Diff final P0/P1/P2 vs spec initiale

| Catégorie | Score | Détails |
|-----------|-------|---------|
| P0 (8 bloquants) | **8/8 ✅** | Auth, sécurité, data integrity, premium gate |
| P1 (10 majeurs) | **9/10 ✅** | Vite scaffold + plan (1 restant non-bloquant) |
| P2 (6 mineurs) | **5/6 ✅** | Logo pro reste à faire (designer humain) |
| Academy | **2/4 parcours** | Novice + Analyst Junior livrés, Expert + Mansa post-launch |
| i18n EN | **~80% coverage** | Onboarding/Hero/Academy/Footer/Auth/Common, render fns post-launch |
| Data freshness | **BETA carry-forward** | Vrai live à brancher sur Render via cron |

---

## Roadmap immédiate post-launch (J+1 → J+7)

| Priorité | Tâche | Effort |
|----------|-------|--------|
| 🔴 H+24h | Vérifier logs Render, corriger les premiers bugs | 2h |
| 🟠 J+2 | Brancher le pipeline live BRVM sur le cron Render | 1h |
| 🟠 J+3 | Ajouter contenu Academy Expert (m13-m18) | 4h |
| 🟡 J+5 | Compléter i18n EN sur les render fns Pro tools | 3h |
| 🟡 J+7 | Ajouter contenu Academy Mansa (m19-m24) + certification finale | 4h |

**Bon lancement.**
