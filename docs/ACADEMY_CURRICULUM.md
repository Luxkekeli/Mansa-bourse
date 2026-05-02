# MANSA Academy — Curriculum complet (24 modules)

**Format** : 4 parcours × 6 modules · ~6h de contenu · 1 415 XP au total · 11 quizzes + 3 projets pratiques + 1 certification finale

---

## Parcours 1 — 🌱 Novice BRVM (115 XP · 5-8 min/module)

| ID | Titre | Format | Compétence |
|----|-------|--------|------------|
| m1 | Qu'est-ce que la BRVM ? | Cours + quiz 1 question | Comprendre l'écosystème UEMOA, 8 pays, 48 sociétés |
| m2 | Comment fonctionne une action ? | Cours + tableau de gain SNTS + quiz | Distinguer plus-value vs dividende, ratio risque/rendement |
| m3 | Lire une cotation BRVM | Cours + tableau lecture + quiz | Décrypter ticker, PER, rendement, limite ±7,5% |
| m4 | Les secteurs de la BRVM | Cours sectoriel + tableau cycles + quiz | Connaître les 7 secteurs, comportement par cycle |
| m5 | Ouvrir un compte SGI | Cours pratique + barème frais + quiz | Choisir une SGI, comprendre les frais (0,7-1,2%) |
| m6 | Quiz Novice : Es-tu prêt ? | Récap + quiz validation | Synthèse Novice |

---

## Parcours 2 — 📈 Analyste Junior (250 XP · 7-15 min/module)

| ID | Titre | Format | Compétence |
|----|-------|--------|------------|
| m7 | Le PER démystifié | Cours + tableau interprétation + cas + quiz | Calculer et interpréter le PER en contexte BRVM |
| m8 | ROE, ROA, Marge nette | Cours triade qualité + tableau comparatif SNTS/SGBC + quiz | Mesurer la qualité d'une entreprise |
| m9 | Analyse des dividendes | Cours payout + grille 5 questions + liste aristocrates BRVM + quiz | Sélectionner les vrais leaders de dividende |
| m10 | Lire un bilan simplifié | Cours bilan + 3 ratios clés + drapeaux rouges/verts + quiz | Repérer une société surendettée vs saine |
| m11 | Construire un screener | Cours 3 stratégies (Value/Dividende/Croissance) + erreurs + quiz | Filtrer 48 actions BRVM selon critères |
| m12 | Projet : Analyse ta première action | Cahier des charges complet + grille + thèse 5 phrases | Produire une analyse complète publiable |

---

## Parcours 3 — 🎯 Expert BRVM (270 XP · 8-20 min/module)

| ID | Titre | Format | Compétence |
|----|-------|--------|------------|
| m13 | Analyse technique : les bases | Cours indicateurs (SMA/RSI/Bollinger/MACD) + étude de cas ETIT 2024-25 + quiz | Combiner 3 indicateurs minimum sur blue chips |
| m14 | Gestion de portefeuille | 5 piliers + tableau allocation 3 profils + cas portefeuille 5 M F + quiz | Construire portefeuille équilibré, calculer beta |
| m15 | Obligations UEMOA | Cours TPS/corporate/sukuk + 3 rendements + cas TPS Sénégal 6,55% + quiz | Choisir entre obligations et actions selon BCEAO |
| m16 | OPCVM et fonds collectifs | 4 catégories + frais + 6 critères de sélection + cas comparaison Fonds A/B + quiz | Comparer OPCVM via Sharpe + frais |
| m17 | Stratégies avancées | Value Graham/Buffett, Momentum, Quality, All-Weather UEMOA + backtest 2018-24 + quiz | Choisir UNE stratégie cohérente |
| m18 | Projet : Construis ton portefeuille modèle | Cahier des charges 10 M F + 5 étapes + scenarios bull/base/bear | Publier portefeuille modèle complet justifié |

---

## Parcours 4 — 👑 Mansa (485 XP · 10-30 min/module)

| ID | Titre | Format | Compétence |
|----|-------|--------|------------|
| m19 | Macroéconomie UEMOA | 5 indicateurs clés + parité FCFA-EUR + chocs externes + cas covid 2020 + quiz | Anticiper l'impact macro sur la BRVM |
| m20 | Valorisation intrinsèque | DCF + DDM Gordon + Graham Number + EV/EBITDA + marge sécurité + cas ETIT triangulé + quiz | Trianguler 3-4 méthodes pour fixer un prix cible |
| m21 | Psychologie de l'investisseur | 7 biais cognitifs + 5 disciplines + 6 phases émotionnelles + cas BRVM 2009 + quiz | Résister aux biais via plan écrit |
| m22 | Fiscalité BRVM par pays | 8 régimes UEMOA détaillés + résidents hors UEMOA + 5 stratégies optim. + cas 20 ans CI vs Niger + quiz | Optimiser la fiscalité (+46% patrimoine final) |
| m23 | Mentor : partager tes analyses | Template thèse Buffett-style + exemple SNTS complet + déontologie + métriques | Publier thèse de qualité Mansa |
| m24 | Certification Mansa 👑 | 30 questions/8 sections · 30 min · niveaux Standard/Honors/Excellence | Obtenir la certification |

---

## Architecture technique

### Stockage des leçons
```js
window.ACADEMY_LESSONS = {
  m1: {
    emoji: '🌱', title: '...', duration: '5 min',
    content: '<p>...</p>',  // HTML structuré (tableaux, exemples chiffrés)
    quiz: { question: '...', options: [...], correct: 1 }  // optionnel
  },
  // ... 24 modules total
};
```

### Flow utilisateur
1. User clique "Commencer" sur un module → `toggleModule(mid, xp)`
2. Si contenu présent → `openLessonModal(mid, xp)` ouvre le modal avec le contenu HTML
3. Soit le user lit puis valide (modules sans quiz : m12, m18, m23, m24)
4. Soit il répond au quiz (modules m1-m11, m13-m17, m19-m22) → `_checkLessonAnswer`
5. Bonne réponse → `_markLessonComplete` ajoute XP + sauvegarde dans `localStorage.bf_academy_progress`
6. Mauvaise réponse → toast "Pas tout à fait — relis et réessaie"

### Persistence
- `localStorage.bf_academy_progress` : array des `mid` complétés
- `localStorage.bf_xp` : XP cumulés
- Niveau auto-calculé : Novice (<300) → Analyste (300-799) → Expert (800-1499) → Mansa (1500+)

---

## Études de cas concrètes incluses

| Module | Cas réel BRVM |
|--------|---------------|
| m1 | Création BRVM 1996, démarrage 1998, 8 pays |
| m2 | SNTS achat 100 actions à 18 000 F → +31% en 1 an avec dividendes |
| m3 | SNTS lecture cotation complète |
| m4 | Poids sectoriels réels BRVM (Banque 40%, Télécom 25%) |
| m5 | Frais SGI réels (CGF Bourse, BICI Bourse, etc.) |
| m7 | SGBC PER 8.8x, SNTS PER 11x, BOA décote |
| m8 | Triade SNTS (ROE 37%, ROA 14%, Marge 22%) vs SGBC |
| m9 | Aristocrates BRVM : SNTS, PALC, SGBC, BICC, BOA, TTLC |
| m10 | Drapeaux rouges/verts pour bilan banques BRVM |
| m11 | 3 stratégies screener avec critères chiffrés |
| m13 | **Étude ETIT 2024-25** : RSI 22 → achat 11 500 F · cible 18 200 F → +58% |
| m14 | Portefeuille équilibré 5 M F détaillé (SNTS/SGBC/BOAS/ETIT/OPCVM) |
| m15 | TPS Sénégal 6,55% 2025-2030 : calcul concret 1 M F → 1,33 M F |
| m16 | Comparaison Fonds A vs B (Sharpe 0,42 vs 0,68) |
| m17 | Backtest Value (+9,8%) vs Momentum (+12,2%) vs BRVM-C (+5,1%) sur 2018-24 |
| m19 | **Crise covid 2020 BRVM** : -5,5% vs -33% S&P500, télécoms +8% |
| m20 | Triangulation ETIT : DCF 14 800 F · DDM 13 500 F · Graham 11 200 F → ~13 000 F |
| m21 | **Crise BRVM 2009** : "panique" -45% vs "value" +95% sur 5 ans |
| m22 | Cas 20 ans CI optimisé (PEA + >2 ans) : +46% vs Niger non-optimisé |
| m23 | Thèse SNTS v1.0 complète format Buffett-memo |

---

## Checklist d'apprentissage

Pour chaque parcours, l'apprenant doit avoir :
- [x] **Novice** : compris la structure BRVM, ouvert un compte SGI virtuellement
- [x] **Analyste Junior** : analysé 1 action BRVM avec PER/ROE/payout, publié sa thèse
- [x] **Expert BRVM** : construit 1 portefeuille modèle 10 M F avec 8 lignes justifiées
- [x] **Mansa** : produit 1+ thèse complète (template Buffett), passé certification 24/30+

---

## Évolution future (post-launch)

- [ ] Certification finale m24 : implémenter les 30 questions interactives en v2.3
- [ ] Vidéos courtes (3-5 min) en complément du texte
- [ ] Cas pratiques mis à jour annuellement (dernier rapport BCEAO, conjoncture)
- [ ] Traduction EN du curriculum complet (post P1-1 Vite migration)
- [ ] Badges visuels avec progression visible dans la communauté
