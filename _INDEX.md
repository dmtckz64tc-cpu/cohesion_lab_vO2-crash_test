# cohesion_lab_vO2 — INDEX & ÉTAT D'ÉDITION

> Ce document est le reflet instantané du dépôt. Il bouge avec lui. Pas de version "finale" — juste des états, des passages, des fragments qui apprennent.

---

## Vue d'ensemble

**Quoi :** Un laboratoire de cohésion transformant du matériau dispersé en fragments autonomes contextualisés.

**Pourquoi public :** Pour que la méthode elle-même soit observée, critiquée, reprise — et que la racine se mélange à d'autres possibles.

**Licence :** CC BY-SA 4.0 — Communs créatifs, mention de l'auteur, partage à l'identique.

**Repo :** `dmtckz64tc-cpu/cohesion_lab_vO2-crash_test` (public, 17.5 KB, créé 2026-10-04)

---

## Structure du dépôt

```
.
├── _INDEX.md                              ← Vous êtes ici
├── README.md                              Manifeste court (2.2 KB)
├── index-html-la-chimère-page-d-accueil-du-dépôt.html
│                                           Portail visuel (7.7 KB)
├── License                                CC BY-SA 4.0 (20 KB)
├── cohesion_lab_vO2-crash_test.code-workspace
│                                           Config VS Code
│
├── tirage-py-le-cardeur-du-tas-tirage-aléatoire-d-extraits.py
│                                           Extracteur aléatoire (5.4 KB)
├── tirage_du_jour.md                      Résultat du dernier tirage (4.3 KB)
├── deepseek_html_20261004_846db5.html     Export DeepSeek (23 KB)
│
├── exemples/                              Fragments contextualisés (12 fichiers)
│   ├── **Mathématiques & Diagnostic**
│   │   ├── surphin_takens_diagnostic.py
│   │   │   Diagnostic topologico-computationnel du plongement de Takens
│   │   │   Tests : alpha_obs, alpha_monde, kappa, rho, estimation RAM
│   │   │   (10.3 KB)
│   │   │
│   │   └── Atlas_CLD-tests_attention_H0_30092026-encours.py
│   │       Tests d'attention pour couplage H0 (shuffle, unfolding, tau physique)
│   │       État : EN COURS (dépend de fichiers non publiés)
│   │       (19.4 KB)
│   │
│   ├── **Visualisations 3D Interactives**
│   │   ├── Surphinphy.html
│   │   │   Jeu interactif : repère co-tournant (bille, centre, œil)
│   │   │   Entrée : "de l'univers se regarder"
│   │   │   (16.5 KB, aucune dépendance)
│   │   │
│   │   ├── Surphinphy_CLD002.html
│   │   │   Version CLD002 : cohérence & rémanence
│   │   │   Lignée itérative, différence intentionnellement visible
│   │   │   (17.9 KB)
│   │   │
│   │   ├── IEEE754_Mi-explore_paysage-3d-des-allocations-flottantes_Mi-003.html
│   │   │   Paysage 3D des bits flottants
│   │   │   Où vit la précision, comment la mantisse distribue
│   │   │   Exploration "Mi" (16.5 KB)
│   │   │
│   │   └── SakanaJAPAN_surphin_white-spaced_PHI_DOCTYPE html.html
│   │       Visualisation SakanaJAPAN / surPhiN'Phi
│   │       (44.9 KB)
│   │
│   ├── **Orchestration & Agents LLM**
│   │   └── orchestrator_v008.py
│   │       FastAPI qui bascule entre 3 backends :
│   │       - Jan local (portable, Q4_K_M)
│   │       - Ollama-home (RTX fixe, qwen2.5-coder:32b)
│   │       - Mistral cloud (API)
│   │       Logging Supabase avec clé publishable publique
│   │       (8 KB)
│   │
│   ├── **Références Structurées**
│   │   └── kinship_references_structured.md
│   │       Arbre : généalogie & ontologie géométrique
│   │       (Thalès → Euclide, IEEE 754, Einstein, Simondon)
│   │       Chaque référence porte son lien avec l'ensemble
│   │       (9.1 KB)
│   │
│   └── **Fichiers de Soutien (bruts, non indexés)**
│       ├── SimondonInMurielCollombes-3chap_1.doc (259 KB, binaire)
│       ├── Sur la place des concepts dans les architectures d'apprentissage.pdf (459 KB, binaire)
│       ├── surffinPhi_game_RULESv00.odt (30 KB, binaire)
│       ├── Une chose survit au changement lors.txt (598 B)
│       └── prompt orchestratorLe fichier `orchestrator_v005.py` e.txt (1.1 KB)
│
└── sources/                               [ABSENT — ignoré par git, local]
                                            Matériau brut, triage en cours
```

---

## Quatre entrées du projet

Le projet est organisé en **quatre vecteurs**, chacun étant une façon d'entrer dans le matériau :

| Entrée | Description | Fichiers clés | État |
|--------|-------------|---------------|------|
| **math** | Tête mathématique — au repos en diagnostic topologico-computationnel | `surphin_takens_diagnostic.py`<br/>`Atlas_CLD-tests_attention_H0.py` | ✓ Diagnostic stable<br/>⚠ Tests en cours |
| **rag** | Colonne RAGlagChain — agent_local ↔ cloud | `orchestrator_v008.py` | ✓ POC fonctionnel<br/>(backend switchable) |
| **surphin** | Corps SurphiN'Phi — jeu du changement d'échelle visible | `Surphinphy.html`<br/>`Surphinphy_CLD002.html` | ✓ Public<br/>⚠ Lignée continue |
| **philo / méso** | Ailes — univers se regarder, références structurées | `kinship_references_structured.md`<br/>`IEEE754_Mi-explore_paysage-3d...html` | ✓ Arbre documenté<br/>✓ Mi-003 stable |

---

## Flux de circulation

```
sources/ (local, privé)
    ↓ [script tirage.py — extraction aléatoire quotidienne]
    ↓
tirage_du_jour.md (222 fenêtres possibles)
    ↓ [étiquetage manuel : entrée / état / où dans l'ensemble]
    ↓
exemples/ (fragments contextualisés)
    ↓ [git push]
    ↓
Dépôt public (CC BY-SA 4.0)
    ↓ [se mélange ailleurs]
```

**Clé :** Aucun fichier binaire ou brut ne quitte `sources/`. Seuls les fragments qui ont reçu un **bloc de contexte** — où ils se situent, ce qu'ils font, pourquoi — montent en public.

---

## Fichiers à parcourir en priorité

### Pour comprendre la philosophie
1. **`README.md`** — 2 min — La déclaration d'intention
2. **`index-html-la-chimère-page-d-accueil-du-dépôt.html`** — 5 min — Portail visuel avec chaque brique contextée
3. **Ce document (`_INDEX.md`)** — 10 min — Cartographie complète

### Pour voir le flux en action
4. **`tirage_du_jour.md`** — 5 extraits aléatoires du 2026-10-04, étiquettes à remplir
5. **`tirage-py-le-cardeur-du-tas...py`** — 131 lignes, bien commentées, aucune dépendance
6. **`exemples/kinship_references_structured.md`** — Exemple du geste : fragment autonome qui porte son contexte

### Pour voir les quatre entrées
7. **`exemples/surphin_takens_diagnostic.py`** — *math* : le diagnostic
8. **`exemples/orchestrator_v008.py`** — *rag* : l'agent orchestrateur
9. **`exemples/Surphinphy.html`** — *surphin* : le jeu (ouvrir dans navigateur)
10. **`exemples/IEEE754_Mi-explore_paysage-3d...html`** — *philo/méso* : paysage 3D (ouvrir dans navigateur)

---

## État d'édition actuel

### ✓ Stable
- Portail HTML (index visuel)
- Diagnostic Takens
- Visualisations 3D (Surphinphy v1, CLD002, IEEE754 Mi-003)
- Orchestrateur FastAPI (v008)
- Arbre de références (kinship)
- Script de tirage (`tirage.py`)

### ⚠ En cours
- **`Atlas_CLD-tests_attention_H0...py`** : 4 tests d'attention pour couplage H0
  - Dépend de `surphin_couplage_viz_vO3c.py` (non publié, encore chaud)
  - Dépend de `langevin_bridge.py` (non publié)
  - Commande test : `python tests_attention_H0.py --test all`

### ◼ Prévu, pas ici
- **méthode/** : Scripts de captage, contextualisation, indexation (pas encore publié)
- **Contenu binaire** : PDF, .doc, .odt restent en `exemples/` sans indexation fine
- **Sources** : Le dossier `sources/` local reste ignoré par git (matériau brut)

### ⚡ Tensions actives
1. **Quoi publier, quoi garder au chaud ?**  
   Tests d'attention → pas de dépendances externes disponibles → reste "en cours"

2. **Format du contexte**  
   Bloc de contexte : "où, quoi, pourquoi" — à affiner avec usage

3. **Lien math ↔ Surphinphy**  
   Diagnostic → Takens → Couplage → Changement d'échelle visible dans le jeu  
   Chemin à clarifier dans un document de liaison

---

## Commandes rapides

### Lancer le tirage du jour
```bash
python tirage-py-le-cardeur-du-tas-tirage-aléatoire-d-extraits.py
# Lit sources/, sort tirage_du_jour.md
```

### Lancer l'orchestrateur LLM
```bash
cd exemples
python orchestrator_v008.py
# Démarre http://127.0.0.1:8000
# Basculer backend dans le fichier (local/home/cloud)
```

### Ouvrir les visualisations
```bash
# Directement dans le navigateur (aucune dépendance)
exemples/Surphinphy.html
exemples/IEEE754_Mi-explore_paysage-3d-des-allocations-flottantes_Mi-003.html
```

### Quel fichier pour quoi ?
- **Tests mathématiques** : `surphin_takens_diagnostic.py`
- **Avis sur la construction** : Ce document (`_INDEX.md`) + `README.md` + `index-html-la-chimère...html`
- **Flux du projet** : `tirage.py` → `tirage_du_jour.md` → `exemples/`
- **Backend LLM** : `orchestrator_v008.py` (FastAPI, 3 backends, Supabase logging)

---

## Pour les agents LLM (prompt context)

**Tu dois savoir que :**
1. C'est un **nid, pas une œuvre finale** — tout est mouvant, révisable, incomplet par design
2. Les **quatre entrées** (math, rag, surphin, philo) sont volontairement orthogonales
3. Le **flux de tirage** crée une sérendipité quotidienne — mêmes extraits si même graine
4. **Supabase est publique** (clé publishable) — logging transparent
5. **CC BY-SA 4.0** — ce qui sort d'ici repart transformé

**Quand tu analyses ce repo, cherche :**
- Les **tensions** (fichiers "en cours", dépendances non publiées)
- Les **liens cachés** (comment Takens → Surphinphy → IEEE754 forment une écologie)
- Les **vides** (sources/ ignoré, methode/ absent — c'est intentionnel)
- La **forme du geste** (bloc de contexte = unité de publication)

---

## Licence & Remerciements

**Contenu :** CC BY-SA 4.0 — Creative Commons Attribution – Share Alike  
Vous pouvez réutiliser et transformer, à condition de créditer l'auteur et de rediffuser sous la même licence.

**Esprit :** Communs créatifs. L'œuvre n'est jamais prête. Le nid s'agrandit brique par brique.

---

*Index généré 2026-10-04. Mise à jour manuelle : à chaque changement d'état significatif.*

**Prochains états :**
- [ ] Publier `methode/` (scripts de captage, contextualisation, indexation)
- [ ] Clarifier lien math → Surphinphy dans document dédié
- [ ] Compléter `Atlas_CLD-tests_attention_H0.py` (dépend dépendances non publiques)
- [ ] Ajouter prompt d'autodescription pour agents LLM
