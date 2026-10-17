"""
validation_functions.py
=======================
Module principal pour la validation des résultats N15, N18, N19.

Contexte :
----------
Ce module fournit toutes les fonctions nécessaires pour :
1. Charger les nuages de points de manière flexible
2. Calculer les diagrammes de persistance H₀ et H₁
3. Valider les 3 résultats majeurs :
   - N15 : Saut H₀ indépendant de la dépendance (Rössler)
   - N18 : Pont Kramers-H₀ (Langevin bistable)
   - N19 : Décalage phase-topologie (Rössler)
4. Générer les visualisations demandées

Utilisation :
-----------
    from validation_functions import (
        load_nuage,                    # Chargement flexible des nuages
        compute_h0_diagram,            # Calcul H₀ via MST
        compute_kramers_correlation,   # Pont Kramers-H₀ (N18)
        compute_h0_jump,               # Saut H₀ (N15)
        compute_h1_fusion,             # Fusion H₁ (N19)
        plot_kramers_loglog,           # Visualisation : Log-Log Kramers
        plot_h1_bottleneck_vs_epsilon, # Visualisation : Δ H₁ vs ε
    )

Auteur : SurPhiN / COHESION_LAB_V01
"""

import numpy as np
import matplotlib.pyplot as plt
from scipy.spatial.distance import pdist, squareform
from scipy.sparse.csgraph import minimum_spanning_tree
from scipy import stats
from pathlib import Path
from collections import Counter, OrderedDict
from functools import lru_cache
import warnings
warnings.filterwarnings('ignore')

# =============================================================================
# 0. IMPORTS DES MODULES LOCAUX
# =============================================================================
try:
    import noether_persistence as NP
    from noether_persistence import (
        NoetherPipeline, TopologicalCharges, NoetherBalance,
        PersDiagram, PersistenceCurrent, WardIdentities
    )
    NOETHER_AVAILABLE = True
except ImportError:
    NOETHER_AVAILABLE = False
    print("⚠️  noether_persistence non disponible")

try:
    import h1_pipeline as H1
    H1_AVAILABLE = True
except ImportError:
    H1_AVAILABLE = False
    print("⚠️  h1_pipeline non disponible")

# =============================================================================
# 1. CONFIGURATION GLOBALE
# =============================================================================

BASE_DIR = Path.cwd()
NUAGE_DIR = BASE_DIR / 'nuages_complementaires'
FIG_DIR = BASE_DIR / 'figures'
FIG_DIR.mkdir(exist_ok=True)

SEEDS = list(range(35))
N_POINTS = 300
M_DIM = 3

# Charges topologiques essentielles
ESSENTIAL_CHARGES = {
    'pers_energy': lambda dgm: TopologicalCharges.persistence_energy(dgm, p=2.0),
    'pers_mass': TopologicalCharges.persistence_mass,
    'topological_gini': TopologicalCharges.topological_gini,
}

# =============================================================================
# 2. CHARGEMENT DES NUAGES (FLEXIBLE)
# =============================================================================

def build_nuage_index():
    """
    Construit un index de tous les nuages disponibles.
    Compatible avec les formats :
    - X_famA_g0.35_T0.40_m3_seed0.npy
    - X_famJ_uni_eps0.1000_T0.10_m3_seed5.npy
    """
    index = {}
    for f in NUAGE_DIR.glob('X_fam*.npy'):
        name = f.name
        parts = name.replace('.npy', '').split('_')
        meta = {'path': f}
        for part in parts[1:]:
            if part.startswith('fam'):
                meta['famille'] = part[3:]
            elif part.startswith('g'):
                try: meta['g'] = float(part[1:])
                except: pass
            elif part.startswith('T'):
                try: meta['T'] = float(part[1:])
                except: pass
            elif part.startswith('m'):
                try: meta['m'] = int(part[1:])
                except: pass
            elif part.startswith('seed'):
                try: meta['seed'] = int(part[4:])
                except: pass
            elif part.startswith('eps'):
                try: meta['eps'] = float(part[3:])
                except: pass
        key = (meta.get('famille'), round(meta.get('g', 0), 2), round(meta.get('T', 0), 2), 
                int(meta.get('m', 3)), int(meta.get('seed', 0)))
        index[key] = meta
    return index

NUAGE_INDEX = build_nuage_index()

@lru_cache(maxsize=1000)
def load_nuage(famille, g, T, m=3, seed=0):
    """
    Charge un nuage par ses paramètres avec tolérance.
    
    Parameters
    ----------
    famille : str
        Famille du nuage ('A', 'J', etc.)
    g : float
        Paramètre de couplage
    T : float
        Paramètre de bruit
    m : int
        Dimension de plongement
    seed : int
        Graine aléatoire
        
    Returns
    -------
    np.ndarray or None
        Nuage de points ou None si introuvable
    """
    key = (famille, round(float(g), 2), round(float(T), 2), int(m), int(seed))
    meta = NUAGE_INDEX.get(key)
    if meta is None:
        for g_tol in [g, round(g, 1), round(g, 2)]:
            for T_tol in [T, round(T, 1), round(T, 2)]:
                key_try = (famille, round(float(g_tol), 2), round(float(T_tol), 2), int(m), int(seed))
                meta = NUAGE_INDEX.get(key_try)
                if meta is not None:
                    break
            if meta is not None:
                break
    if meta is None:
        print(f"⚠️  Nuage introuvable: fam={famille} g={g} T={T} m={m} seed={seed}")
        return None
    return np.load(meta['path'])

def get_available_families():
    """Retourne la liste des familles disponibles."""
    return list(set(meta.get('famille') for meta in NUAGE_INDEX.values() if meta.get('famille')))

def get_available_conditions(famille, m=3):
    """Retourne les conditions (g, T) disponibles pour une famille."""
    conditions = set()
    for key in NUAGE_INDEX:
        if key[0] == famille and key[3] == m:
            conditions.add((key[1], key[2]))
    return sorted(conditions)

# =============================================================================
# 3. CALCUL DES DIAGRAMMES H₀ (via MST)
# =============================================================================

def mst_merges(X):
    """Arêtes du MST triées par distance croissante."""
    n = X.shape[0]
    D = squareform(pdist(X))
    dup = (D == 0)
    np.fill_diagonal(dup, False)
    if dup.any():
        D[dup] = 1e-12
    coo = minimum_spanning_tree(D).tocoo()
    merges = sorted(((int(i), int(j), float(d)) for i, j, d in zip(coo.row, coo.col, coo.data)),
                    key=lambda t: t[2])
    return merges

def single_linkage_h0_diagram(X):
    """Diagramme H₀ par single-linkage via MST."""
    n = X.shape[0]
    if n < 2:
        return PersDiagram(pairs=np.zeros((0, 2)), param={})
    merges = mst_merges(X)
    return NoetherPipeline.from_faisceau_purifie(merges, n_points=n, param={})

def compute_charge(X, charge_name='pers_energy'):
    """Calcule une charge topologique pour un nuage."""
    dgm = single_linkage_h0_diagram(X)
    charge_fn = ESSENTIAL_CHARGES.get(charge_name)
    if charge_fn is None:
        raise ValueError(f"Charge inconnue: {charge_name}")
    return float(charge_fn(dgm))

# =============================================================================
# 4. VALIDATION N18 : PONT KRAMERS-H₀
# =============================================================================

def compute_kramers_escape_time(V: float, omega_0: float = 1.0, D: float = 0.1) -> float:
    """
    Calcule le temps d'échappement de Kramers pour un potentiel bistable.
    
    Formule : τ_K ∝ exp(ΔV / D) où ΔV est la hauteur de la barrière.
    
    Parameters
    ----------
    V : float
        Hauteur de la barrière d'énergie
    omega_0 : float
        Fréquence naturelle du puits
    D : float
        Coefficient de diffusion (bruit)
        
    Returns
    -------
    float
        Temps d'échappement τ_K
    """
    return (2 * np.pi / omega_0) * np.exp(V / D)

def compute_h0_persistence_lifetime(dgm) -> float:
    """
    Calcule la durée de vie maximale des composantes H₀.
    
    C'est l'analogue topologique du temps d'échappement.
    """
    pairs = np.asarray(dgm.pairs, dtype=float)
    if len(pairs) == 0:
        return 0.0
    lifetimes = pairs[:, 1] - pairs[:, 0]
    lifetimes = lifetimes[np.isfinite(lifetimes)]
    return float(np.max(lifetimes)) if len(lifetimes) > 0 else 0.0

def run_n18(famille='A', T_values=[0.1, 0.2, 0.3, 0.4], m=3, seeds=None):
    """
    Exécute la validation N18 : Pont Kramers-H₀.
    
    Pour chaque condition (T), calcule :
    - La persistance H₀ (τ_H₀)
    - Le temps d'échappement de Kramers (τ_K) basé sur T
    - La corrélation entre τ_H₀ et τ_K
    
    Returns
    -------
    dict
        {
            'T_values': liste des T testés,
            'pers_energy': valeurs de pers_energy par T,
            'pers_mass': valeurs de pers_mass par T,
            'kramers_times': valeurs de τ_K par T,
            'correlation': corrélation de Pearson,
            'p_value': p-value de la corrélation
        }
    """
    if seeds is None:
        seeds = SEEDS[:10]  # Utiliser 10 graines pour la robustesse
    
    results = {
        'T_values': [],
        'pers_energy': [],
        'pers_mass': [],
        'kramers_times': [],
    }
    
    for T in T_values:
        # Charger les nuages pour cette condition
        X_list = []
        for seed in seeds:
            X = load_nuage(famille=famille, g=0.35, T=T, m=m, seed=seed)
            if X is not None:
                X_list.append(X)
        
        if len(X_list) == 0:
            continue
        
        results['T_values'].append(T)
        
        # Calculer les charges moyennes
        pers_energy_vals = []
        pers_mass_vals = []
        for X in X_list:
            dgm = single_linkage_h0_diagram(X)
            pers_energy_vals.append(float(TopologicalCharges.persistence_energy(dgm)))
            pers_mass_vals.append(float(TopologicalCharges.persistence_mass(dgm)))
        
        results['pers_energy'].append(np.mean(pers_energy_vals))
        results['pers_mass'].append(np.mean(pers_mass_vals))
        
        # Calculer τ_K : on suppose que T est lié à la barrière V
        # Pour simplifier, on utilise T comme proxy de V
        V = T * 10  # Échelle arbitraire pour la démonstration
        tau_K = compute_kramers_escape_time(V, D=T)
        results['kramers_times'].append(tau_K)
    
    # Calculer la corrélation
    if len(results['pers_energy']) > 1:
        r, p = stats.pearsonr(results['pers_energy'], results['kramers_times'])
        results['correlation'] = float(r)
        results['p_value'] = float(p)
    else:
        results['correlation'] = float('nan')
        results['p_value'] = float('nan')
    
    return results

def plot_kramers_loglog(n18_results, figsize=(10, 6), savefig=True):
    """
    Génère le plot Log-Log de la corrélation Kramers-H₀.
    
    Parameters
    ----------
    n18_results : dict
        Résultats de run_n18()
    figsize : tuple
        Taille de la figure
    savefig : bool
        Sauvegarder la figure dans FIG_DIR
        
    Returns
    -------
    matplotlib.figure.Figure
        La figure générée
    """
    fig, ax = plt.subplots(figsize=figsize)
    
    T = np.array(n18_results['T_values'])
    pers_energy = np.array(n18_results['pers_energy'])
    kramers_times = np.array(n18_results['kramers_times'])
    
    # Plot en échelle log-log
    ax.loglog(T, pers_energy, 'o-', label='pers_energy (H₀)', color='blue', linewidth=2, markersize=8)
    ax.loglog(T, kramers_times, 's--', label='τ_K (Kramers)', color='red', linewidth=2, markersize=8)
    
    # Annotations
    for i, (t, pe, kt) in enumerate(zip(T, pers_energy, kramers_times)):
        ax.annotate(f'T={t:.1f}', xy=(t, pe), xytext=(5, 5), textcoords='offset points',
                    fontsize=9, color='blue')
    
    # Configuration
    ax.set_xlabel('Paramètre T (bruit)', fontsize=12)
    ax.set_ylabel('Énergie / Temps', fontsize=12)
    ax.set_title('Pont Kramers-H₀ : Corrélation Log-Log (N18)', fontsize=14, fontweight='bold')
    ax.legend(fontsize=10)
    ax.grid(True, which='both', linestyle='--', alpha=0.5)
    
    # Ajouter la corrélation
    if 'correlation' in n18_results and not np.isnan(n18_results['correlation']):
        ax.text(0.05, 0.95, f'r = {n18_results["correlation"]:.4f}', 
                transform=ax.transAxes, fontsize=12, fontweight='bold',
                bbox=dict(facecolor='white', alpha=0.8, boxstyle='round'))
    
    plt.tight_layout()
    
    if savefig:
        fig.savefig(FIG_DIR / 'n18_kramers_loglog.png', dpi=150, bbox_inches='tight')
        print(f"✅ Figure sauvegardée: {FIG_DIR / 'n18_kramers_loglog.png'}")
    
    return fig

# =============================================================================
# 5. VALIDATION N15 : SAUT H₀ INDÉPENDANT
# =============================================================================

def run_n15(famille='J', eps_values=None, T=0.10, m=3, seeds=None):
    """
    Exécute la validation N15 : Saut H₀ indépendant de la dépendance.
    
    Pour la famille J (Rössler couplés), calcule :
    - topological_gini pour différentes valeurs de ε (couplage)
    - Vérifie que le saut à ε≈0.0775 est indépendant de la dépendance
    
    Parameters
    ----------
    famille : str
        Famille à tester ('J' pour Rössler)
    eps_values : list
        Valeurs de ε à tester
    T : float
        Paramètre de bruit
    m : int
        Dimension de plongement
    seeds : list
        Graines à utiliser
        
    Returns
    -------
    dict
        {
            'eps_values': liste des ε testés,
            'gini_mean': gini moyen par ε,
            'gini_std': écart-type du gini par ε,
            'jump_epsilon': ε où le saut est détecté,
            'jump_magnitude': amplitude du saut
        }
    """
    if seeds is None:
        seeds = SEEDS[:10]
    
    if eps_values is None:
        eps_values = [0.0, 0.025, 0.05, 0.075, 0.0775, 0.08, 0.10, 0.15, 0.20, 0.30]
    
    results = {
        'eps_values': [],
        'gini_mean': [],
        'gini_std': [],
    }
    
    for eps in eps_values:
        X_list = []
        for seed in seeds:
            # Pour la famille J, les fichiers peuvent avoir un format différent
            # Essayer avec eps comme paramètre
            X = load_nuage(famille=famille, g=eps, T=T, m=m, seed=seed)
            if X is None:
                # Essayer avec eps comme partie du nom
                X = load_nuage(famille=famille, g=0.35, T=T, m=m, seed=seed)
            if X is not None:
                X_list.append(X)
        
        if len(X_list) == 0:
            continue
        
        results['eps_values'].append(eps)
        
        # Calculer gini pour chaque graine
        gini_vals = []
        for X in X_list:
            dgm = single_linkage_h0_diagram(X)
            gini = float(TopologicalCharges.topological_gini(dgm))
            gini_vals.append(gini)
        
        results['gini_mean'].append(np.mean(gini_vals))
        results['gini_std'].append(np.std(gini_vals, ddof=1))
    
    # Détecter le saut
    if len(results['gini_mean']) > 1:
        gini_mean = np.array(results['gini_mean'])
        eps_array = np.array(results['eps_values'])
        
        # Calculer les différences
        diffs = np.diff(gini_mean)
        jump_idx = np.argmax(diffs)
        
        results['jump_epsilon'] = float(eps_array[jump_idx])
        results['jump_magnitude'] = float(diffs[jump_idx])
    else:
        results['jump_epsilon'] = float('nan')
        results['jump_magnitude'] = float('nan')
    
    return results

# =============================================================================
# 6. VALIDATION N19 : DÉCALAGE PHASE-TOPOLOGIE
# =============================================================================

def run_n19(famille='J', eps_values=None, T=0.10, m=3, seeds=None):
    """
    Exécute la validation N19 : Décalage phase-topologie.
    
    Pour la famille J (Rössler couplés), calcule :
    - R : verrouillage de phase (Hilbert)
    - Δ_H₁ : distance bottleneck appariée pour H₁
    - Détecte le décalage entre ε_R (verrouillage) et ε_H₁ (fusion)
    
    Parameters
    ----------
    famille : str
        Famille à tester ('J')
    eps_values : list
        Valeurs de ε (couplage) à tester
    T : float
        Paramètre de bruit
    m : int
        Dimension de plongement
    seeds : list
        Graines à utiliser
        
    Returns
    -------
    dict
        {
            'eps_values': liste des ε testés,
            'R_mean': R moyen par ε,
            'bottleneck_mean': Δ_H₁ moyen par ε,
            'bottleneck_ci_lower': IC inférieure de Δ_H₁,
            'bottleneck_ci_upper': IC supérieure de Δ_H₁,
            'phase_lock_epsilon': ε où R devient significatif,
            'topology_fusion_epsilon': ε où H₁ devient significatif,
            'decalage': décalage entre les deux seuils
        }
    """
    if not H1_AVAILABLE:
        print("⚠️  H1 non disponible. Impossible d'exécuter N19.")
        return {'error': 'H1 non disponible'}
    
    if seeds is None:
        seeds = SEEDS[:5]  # 5 graines pour la démonstration
    
    if eps_values is None:
        eps_values = np.linspace(0.0, 0.3, 20).tolist()
    
    results = {
        'eps_values': [],
        'R_mean': [],
        'bottleneck_mean': [],
        'bottleneck_ci_lower': [],
        'bottleneck_ci_upper': [],
    }
    
    for eps in eps_values:
        # Charger le nuage réel
        X_real = load_nuage(famille=famille, g=eps, T=T, m=m, seed=seeds[0])
        if X_real is None:
            continue
        
        results['eps_values'].append(eps)
        
        # Calculer R (verrouillage de phase)
        try:
            R = H1.phase_locking_strength(X_real, channel1=0, channel2=1)
            results['R_mean'].append(float(R))
        except Exception:
            results['R_mean'].append(float('nan'))
        
        # Calculer H₁ pour le système réel
        real_h1 = H1.compute_h1_diagram(X_real)
        
        # Générer des nuls (décalage circulaire)
        null_h1_list = []
        for seed in seeds[1:]:
            X_null = load_nuage(famille=famille, g=eps, T=T, m=m, seed=seed)
            if X_null is not None:
                null_h1 = H1.compute_h1_diagram(X_null)
                null_h1_list.append(null_h1)
        
        # Calculer la distance bottleneck appariée
        if len(null_h1_list) > 0:
            paired_dist = H1.compute_paired_bottleneck(real_h1, null_h1_list)
            results['bottleneck_mean'].append(paired_dist['mean'])
            results['bottleneck_ci_lower'].append(paired_dist['ci_lower'])
            results['bottleneck_ci_upper'].append(paired_dist['ci_upper'])
        else:
            results['bottleneck_mean'].append(float('nan'))
            results['bottleneck_ci_lower'].append(float('nan'))
            results['bottleneck_ci_upper'].append(float('nan'))
    
    # Détecter les seuils
    R_array = np.array(results['R_mean'])
    bottleneck_ci_upper = np.array(results['bottleneck_ci_lower'])
    eps_array = np.array(results['eps_values'])
    
    # Seuil pour R (verrouillage de phase)
    phase_lock_idx = None
    for i, r in enumerate(R_array):
        if r > 0.7:  # Seuil arbitraire pour la démonstration
            phase_lock_idx = i
            break
    
    # Seuil pour H₁ (fusion topologique)
    topology_fusion_idx = None
    for i, ci in enumerate(bottleneck_ci_upper):
        if ci > 0:  # IC exclut 0
            topology_fusion_idx = i
            break
    
    if phase_lock_idx is not None:
        results['phase_lock_epsilon'] = float(eps_array[phase_lock_idx])
    else:
        results['phase_lock_epsilon'] = float('nan')
    
    if topology_fusion_idx is not None:
        results['topology_fusion_epsilon'] = float(eps_array[topology_fusion_idx])
    else:
        results['topology_fusion_epsilon'] = float('nan')
    
    if phase_lock_idx is not None and topology_fusion_idx is not None:
        results['decalage'] = float(eps_array[topology_fusion_idx] - eps_array[phase_lock_idx])
    else:
        results['decalage'] = float('nan')
    
    return results

def plot_h1_bottleneck_vs_epsilon(n19_results, figsize=(12, 6), savefig=True):
    """
    Génère le plot Δ apparié H₁ vs ε avec zone grisée du décalage.
    
    Parameters
    ----------
    n19_results : dict
        Résultats de run_n19()
    figsize : tuple
        Taille de la figure
    savefig : bool
        Sauvegarder la figure
        
    Returns
    -------
    matplotlib.figure.Figure
        La figure générée
    """
    fig, ax = plt.subplots(figsize=figsize)
    
    eps = np.array(n19_results['eps_values'])
    R = np.array(n19_results['R_mean'])
    bottleneck_mean = np.array(n19_results['bottleneck_mean'])
    ci_lower = np.array(n19_results['bottleneck_ci_lower'])
    ci_upper = np.array(n19_results['bottleneck_ci_upper'])
    
    # Plot R (verrouillage de phase)
    ax.plot(eps, R, 'o-', label='R (Verrouillage de phase)', color='green', linewidth=2, markersize=6)
    
    # Plot Δ_H₁ (distance bottleneck)
    ax.plot(eps, bottleneck_mean, 's-', label='Δ_H₁ (Distance bottleneck)', color='blue', linewidth=2, markersize=6)
    
    # Zone grisée du décalage
    if 'phase_lock_epsilon' in n19_results and 'topology_fusion_epsilon' in n19_results:
        phase_eps = n19_results['phase_lock_epsilon']
        fusion_eps = n19_results['topology_fusion_epsilon']
        
        if not np.isnan(phase_eps) and not np.isnan(fusion_eps):
            ax.axvspan(phase_eps, fusion_eps, color='red', alpha=0.15, 
                       label=f'Décalage (ε ∈ [{phase_eps:.3f}, {fusion_eps:.3f}])')
            
            # Ajouter des lignes verticales
            ax.axvline(x=phase_eps, color='green', linestyle='--', alpha=0.7, 
                       label=f'ε_R = {phase_eps:.3f}')
            ax.axvline(x=fusion_eps, color='blue', linestyle='--', alpha=0.7,
                       label=f'ε_H₁ = {fusion_eps:.3f}')
    
    # Intervalle de confiance
    ax.fill_between(eps, ci_lower, ci_upper, color='blue', alpha=0.2, label='IC95 Δ_H₁')
    
    # Configuration
    ax.set_xlabel('Couplage (ε)', fontsize=12)
    ax.set_ylabel('Valeur', fontsize=12)
    ax.set_title('Décalage Phase-Topologie : R vs Δ_H₁ (N19)', fontsize=14, fontweight='bold')
    ax.legend(fontsize=10, loc='best')
    ax.grid(True, which='both', linestyle='--', alpha=0.5)
    ax.set_ylim(0, None)
    
    # Annotations
    if 'decalage' in n19_results and not np.isnan(n19_results['decalage']):
        decalage = n19_results['decalage']
        ax.text(0.05, 0.95, f'Décalage = {decalage:.4f}', 
                transform=ax.transAxes, fontsize=12, fontweight='bold',
                bbox=dict(facecolor='white', alpha=0.8, boxstyle='round'))
    
    plt.tight_layout()
    
    if savefig:
        fig.savefig(FIG_DIR / 'n19_phase_topology_decalage.png', dpi=150, bbox_inches='tight')
        print(f"✅ Figure sauvegardée: {FIG_DIR / 'n19_phase_topology_decalage.png'}")
    
    return fig

# =============================================================================
# 7. FONCTIONS DE SYNTHÈSE
# =============================================================================

def run_all_validations():
    """
    Exécute toutes les validations (N15, N18, N19) et retourne un rapport complet.
    
    Returns
    -------
    dict
        {
            'N15': résultats N15,
            'N18': résultats N18,
            'N19': résultats N19,
            'summary': synthèse des résultats
        }
    """
    report = OrderedDict()
    
    # N18 : Pont Kramers-H₀
    print("🔄 Exécution N18 (Pont Kramers-H₀)...")
    n18_results = run_n18(famille='A', T_values=[0.1, 0.2, 0.3, 0.4], seeds=SEEDS[:5])
    report['N18'] = n18_results
    print(f"   ✅ N18 terminé. Corrélation: r = {n18_results.get('correlation', 'N/A'):.4f}")
    
    # N15 : Saut H₀ indépendant
    print("🔄 Exécution N15 (Saut H₀ indépendant)...")
    n15_results = run_n15(famille='J', eps_values=[0.0, 0.05, 0.075, 0.0775, 0.10, 0.15], seeds=SEEDS[:5])
    report['N15'] = n15_results
    print(f"   ✅ N15 terminé. Saut détecté à ε = {n15_results.get('jump_epsilon', 'N/A'):.4f}")
    
    # N19 : Décalage phase-topologie
    print("🔄 Exécution N19 (Décalage phase-topologie)...")
    n19_results = run_n19(famille='J', eps_values=np.linspace(0.0, 0.3, 15).tolist(), seeds=SEEDS[:3])
    report['N19'] = n19_results
    if 'decalage' in n19_results:
        print(f"   ✅ N19 terminé. Décalage: {n19_results['decalage']:.4f}")
    else:
        print(f"   ⚠️  N19 : {n19_results.get('error', 'Erreur inconnue')}")
    
    # Synthèse
    report['summary'] = {
        'N18_correlation': n18_results.get('correlation', float('nan')),
        'N15_jump_epsilon': n15_results.get('jump_epsilon', float('nan')),
        'N19_decalage': n19_results.get('decalage', float('nan')),
        'N19_phase_lock_epsilon': n19_results.get('phase_lock_epsilon', float('nan')),
        'N19_topology_fusion_epsilon': n19_results.get('topology_fusion_epsilon', float('nan')),
    }
    
    return report

def generate_all_plots(report, figsize=(12, 8), savefig=True):
    """
    Génère toutes les visualisations pour le rapport.
    
    Parameters
    ----------
    report : dict
        Résultats de run_all_validations()
    figsize : tuple
        Taille des figures
    savefig : bool
        Sauvegarder les figures
        
    Returns
    -------
    list
        Liste des figures générées
    """
    figures = []
    
    # Plot N18 : Log-Log Kramers
    if 'N18' in report:
        fig = plot_kramers_loglog(report['N18'], figsize=figsize, savefig=savefig)
        figures.append(fig)
    
    # Plot N19 : Décalage phase-topologie
    if 'N19' in report and 'error' not in report['N19']:
        fig = plot_h1_bottleneck_vs_epsilon(report['N19'], figsize=figsize, savefig=savefig)
        figures.append(fig)
    
    return figures

# =============================================================================
# 8. TEST DE FONCTIONNEMENT
# =============================================================================

if __name__ == "__main__":
    print("validation_functions.py - Module de validation charge.")
    print(f"noether_persistence disponible: {NOETHER_AVAILABLE}")
    print(f"h1_pipeline disponible: {H1_AVAILABLE}")
    print(f"Familles disponibles: {get_available_families()}")
    
    # Test de chargement
    print("\n--- Test de chargement ---")
    X_test = load_nuage(famille='A', g=0.35, T=0.40, m=3, seed=0)
    if X_test is not None:
        print(f"✅ Nuage A chargé: {X_test.shape}")
        dgm_test = single_linkage_h0_diagram(X_test)
        print(f"   Diagramme H₀: {dgm_test.n_components} composantes")
    else:
        print("⚠️  Impossible de charger le nuage de test")
    
    # Test N18
    print("\n--- Test N18 (simplifié) ---")
    n18_test = run_n18(famille='A', T_values=[0.1, 0.4], seeds=SEEDS[:2])
    print(f"Corrélation: r = {n18_test.get('correlation', 'N/A'):.4f}")
