# P1-1 — Vite migration plan

## État actuel (v2.2-session5)

- ✅ **Vite scaffold posé** : `vite.config.ts`, `tsconfig.json`, `frontend/src/{main,api,auth,i18n,router,data,styles}.ts`
- ✅ **Stub tab** : `frontend/src/tabs/dashboard.ts` (exemple)
- ✅ **Type-safe API client** : `frontend/src/api.ts` (couvre tous les endpoints prod)
- ❌ **Pas encore wiré** : `frontend/app.html` reste le monolithe servi en prod

Le scaffold compile et fournit la structure cible. La migration réelle (port des 11k lignes de `app.html` vers les modules `src/`) est un chantier étalé sur **3-4 sessions de travail** parce que chaque tab a sa propre logique.

## Pourquoi cette approche progressive ?

Le frontend marche aujourd'hui. Casser un seul des 42 onglets = utilisateur cassé. Plutôt que tout migrer d'un coup et risquer une régression, on migre **un tab à la fois** :

1. Porter le tab dans `src/tabs/<name>.ts`
2. Tester e2e
3. Retirer le block correspondant de `app.html`
4. Re-tester complètement
5. Commit

Tant que `app.html` n'est pas vidé, **les 2 codebases coexistent**. C'est intentionnel.

## Plan tab par tab

### Vague 1 — fondations (déjà posées)

| Module | État | Notes |
|--------|------|-------|
| `api.ts` | ✅ posé | 12 fonctions typées, ApiError class |
| `auth.ts` | ✅ posé | initAuth/login/logout/getUser |
| `i18n.ts` | ✅ posé | JSON dicts, switch/getLang |
| `router.ts` | ✅ posé | hash router, dynamic imports |
| `data.ts` | ✅ stub | Type `TickerMeta` défini, S vide (à générer) |
| `main.ts` | ✅ posé | bootstrap |

### Vague 2 — tabs prioritaires (estimation 1-2 sessions)

| Tab | Effort | Prérequis |
|-----|--------|-----------|
| Dashboard | 2-3 h | data.ts généré + Chart.js wrapper |
| Screener | 3-4 h | data.ts + filters logic |
| Ticker detail | 2-3 h | api.ticker(symbol) |
| Auth modal | 2 h | wrap auth.ts dans un composant |

### Vague 3 — tabs secondaires (1-2 sessions)

| Tab | Effort |
|-----|--------|
| Portfolio | 3 h |
| Watchlist | 2 h |
| Journal | 2 h |
| Alertes | 2 h |

### Vague 4 — tabs Pro / Education (1 session)

| Tab | Effort |
|-----|--------|
| 11 tabs « outils Pro » (fiscal, fraisSGI, etc.) | 4 h cumulés (templates similaires) |
| 6 tabs Education / Academy | 2 h |

### Vague 5 — finition (1 session)

- Service Worker via Workbox build (au lieu de notre handcrafted)
- Vider `app.html` jusqu'à ne garder que `<div id="app-root"></div>`
- Activer `'self'` strict sur la CSP (retirer `'unsafe-inline'`)
- Tests Lighthouse + perf budget

## Comment générer `data.ts` depuis la DB

```bash
python scripts/seed_from_app_html.py        # populate la DB depuis l'inline S
python scripts/dump_tickers_to_data_ts.py   # à écrire — dump DB → src/data.ts
```

Le 2nd script reste à créer (5 lignes : query `/api/tickers` puis écrire le `TickerMeta[]` dans `data.ts`).

## Pourquoi pas tout faire maintenant ?

| Risque | Sans migration progressive | Avec |
|--------|---------------------------|-----|
| Casser un tab silencieusement | 🔴 très élevé (42 tabs) | 🟢 contained, un tab à la fois |
| Régression UX | 🔴 100% chance d'oubli | 🟢 testable visuellement |
| Bloquer le launch | 🔴 oui (8-12h non-divisible) | 🟢 non (scaffold acquis, migration post-launch) |
| Time-to-market | 🔴 +2 semaines | 🟢 launch maintenant |

**Recommandation** : on lance avec `app.html` monolithe tel quel, on migre tab par tab post-launch.

## Activer le scaffold pour expérimenter

Pour tester le scaffold sans toucher à la prod :

```bash
npm install
npm run dev
# Ouvre http://localhost:5173/
```

Tu verras une page minimaliste rendue par `src/tabs/dashboard.ts`. C'est notre point de départ.

## Quand pourra-t-on retirer `'unsafe-inline'` de la CSP ?

Quand `app.html` ne contient plus de `<script>` ni de `style="..."` inline. Ça arrive à la **fin de la Vague 5**.

Tant qu'on n'y est pas, la CSP garde `'unsafe-inline'` (P1-3 documenté). Ce n'est pas idéal mais on a 3 autres couches de défense (DOMPurify, bleach, sessions).
