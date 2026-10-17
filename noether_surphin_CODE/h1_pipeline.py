"""
h1_pipeline.py
================
Module pour le calcul de l'homologie H₁ (cycles persistants) et la distance bottleneck.

Contexte :
----------
Ce module extrait et formalise le code de N19 du notebook original pour permettre :
1. Le calcul des diagrammes de persistance H₁ via ripser
2. Le calcul de la distance bottleneck entre diagrammes via persim
3. La détection du verrouillage de phase via la transformée de Hilbert

Utilisation :
-----------
    from h1_pipeline import (
        compute_h1_diagram,       # Calcul du diagramme H₁ d'un nuage
        bottleneck_distance,       # Distance bottleneck entre deux diagrammes H₁
        phase_locking_strength,    # Mesure R du verrouillage de phase (Hilbert)
        compute_paired_bottleneck, # Δ apparié H₁ entre système réel et nul
    )

Auteur : SurPhiN / COHESION_LAB_V01 (extrait de N19)
"""

import numpy as np
from scipy.signal import hilbert

# =============================================================================
# 0. DÉPENDANCES EXTERNES (à installer : pip install ripser persim)
# =============================================================================
try:
    from ripser import ripser
    RIPser_AVAILABLE = True
except ImportError:
    RIPser_AVAILABLE = False
    print("⚠️  ripser non disponible. H₁ ne peut pas être calculé.")

try:
    from persim import bottleneck as _bottleneck
    PERSIM_AVAILABLE = True
except ImportError:
    PERSIM_AVAILABLE = False
    print("⚠️  persim non disponible. La distance bottleneck ne peut pas être calculée.")


# =============================================================================
# 1. CALCUL DES DIAGRAMMES H₁
# =============================================================================

def compute_h1_diagram(X: np.ndarray, max_dim: int = 1) -> np.ndarray:
    """
    Calcule le diagramme de persistance H₁ d'un nuage de points.
    
    Parameters
    ----------
    X : np.ndarray
        Nuage de points de forme (n_points, n_features)
    max_dim : int
        Dimension maximale d'homologie à calculer (1 pour H₁ uniquement)
        
    Returns
    -------
    np.ndarray
        Diagramme de persistance H₁ de forme (n_bars, 2) où chaque ligne est [naissance, mort]
        Retourne un tableau vide si ripser n'est pas disponible.
    """
    if not RIPser_AVAILABLE:
        print("❌ ripser non disponible. Retourne un diagramme vide.")
        return np.zeros((0, 2))
    
    # ripser retourne une liste de diagrammes pour chaque dimension
    diagrams = ripser(X, maxdim=max_dim, distance_matrix=False)
    
    # diagrams[1] correspond à H₁ (les cycles)
    if len(diagrams) <= 1:
        return np.zeros((0, 2))
    
    h1_dgm = diagrams[1]
    return np.asarray(h1_dgm, dtype=float)


def compute_persistence_diagrams(X: np.ndarray, max_dim: int = 1) -> dict:
    """
    Calcule tous les diagrammes de persistance jusqu'à max_dim.
    
    Returns
    -------
    dict
        Dictionnaire {dimension: diagramme} où dimension est 0 (H₀), 1 (H₁), etc.
    """
    if not RIPser_AVAILABLE:
        return {}
    
    diagrams = ripser(X, maxdim=max_dim, distance_matrix=False)
    return {dim: np.asarray(dgm, dtype=float) for dim, dgm in enumerate(diagrams)}


# =============================================================================
# 2. DISTANCE BOTTLENECK POUR H₁
# =============================================================================

def bottleneck_distance(dgm1: np.ndarray, dgm2: np.ndarray) -> float:
    """
    Calcule la distance bottleneck entre deux diagrammes de persistance H₁.
    
    Parameters
    ----------
    dgm1, dgm2 : np.ndarray
        Diagrammes de persistance de forme (n_bars, 2) [naissance, mort]
        
    Returns
    -------
    float
        Distance bottleneck entre les deux diagrammes.
        Retourne np.inf si persim n'est pas disponible.
    """
    if not PERSIM_AVAILABLE:
        print("❌ persim non disponible. Retourne inf.")
        return float('inf')
    
    # persim.bottleneck attend des diagrammes au format (n_bars, 2)
    return float(_bottleneck(dgm1, dgm2))


def compute_paired_bottleneck(
    real_dgm: np.ndarray, 
    null_dgms: list, 
    n_bootstrap: int = 1000,
    seed: int = 42
) -> dict:
    """
    Calcule la distance bottleneck appariée entre le système réel et les nuls.
    
    Parameters
    ----------
    real_dgm : np.ndarray
        Diagramme H₁ du système réel
    null_dgms : list
        Liste de diagrammes H₁ des nuls (un par graine ou condition)
    n_bootstrap : int
        Nombre de rééchantillonnages pour l'intervalle de confiance
    seed : int
        Graine aléatoire pour la reproductibilité
        
    Returns
    -------
    dict
        {
            'mean': distance bottleneck moyenne,
            'std': écart-type,
            'ci_lower': borne inférieure IC95,
            'ci_upper': borne supérieure IC95,
            'n_samples': nombre d'échantillons
        }
    """
    if not PERSIM_AVAILABLE:
        return {'mean': float('nan'), 'std': float('nan'), 
                'ci_lower': float('nan'), 'ci_upper': float('nan'), 'n_samples': 0}
    
    # Calcul des distances pour chaque nul
    distances = []
    for null_dgm in null_dgms:
        if len(null_dgm) == 0 or len(real_dgm) == 0:
            distances.append(float('nan'))
            continue
        try:
            dist = float(_bottleneck(real_dgm, null_dgm))
            distances.append(dist)
        except Exception as e:
            print(f"⚠️  Erreur dans bottleneck: {e}")
            distances.append(float('nan'))
    
    # Filtrage des NaN
    distances = [d for d in distances if np.isfinite(d)]
    
    if len(distances) == 0:
        return {'mean': float('nan'), 'std': float('nan'), 
                'ci_lower': float('nan'), 'ci_upper': float('nan'), 'n_samples': 0}
    
    # Statistiques de base
    mean_dist = float(np.mean(distances))
    std_dist = float(np.std(distances, ddof=1))
    
    # Intervalle de confiance par bootstrap
    rng = np.random.default_rng(seed)
    bootstrap_means = []
    for _ in range(n_bootstrap):
        sample = rng.choice(distances, size=len(distances), replace=True)
        bootstrap_means.append(float(np.mean(sample)))
    
    ci_lower = float(np.percentile(bootstrap_means, 2.5))
    ci_upper = float(np.percentile(bootstrap_means, 97.5))
    
    return {
        'mean': mean_dist,
        'std': std_dist,
        'ci_lower': ci_lower,
        'ci_upper': ci_upper,
        'n_samples': len(distances)
    }


# =============================================================================
# 3. VERROUILLAGE DE PHASE (TRANSFORMÉE DE HILBERT)
# =============================================================================

def phase_locking_strength(X: np.ndarray, channel1: int = 0, channel2: int = 1) -> float:
    """
    Calcule la force de verrouillage de phase R entre deux canaux.
    
    Utilise la transformée de Hilbert pour extraire la phase instantanée.
    
    Parameters
    ----------
    X : np.ndarray
        Nuage de points de forme (n_timepoints, n_features)
        Doit contenir au moins 2 canaux (n_features >= 2)
    channel1, channel2 : int
        Indices des deux canaux à comparer (par défaut 0 et 1)
        
    Returns
    -------
    float
        Force de verrouillage de phase R ∈ [0, 1]
        R ≈ 0 : pas de verrouillage
        R ≈ 1 : verrouillage parfait
    """
    if X.shape[1] < 2:
        raise ValueError("X doit contenir au moins 2 canaux pour calculer R")
    
    # Extraire les deux canaux
    s1 = X[:, channel1]
    s2 = X[:, channel2]
    
    # Transformée de Hilbert pour obtenir la phase
    analytic1 = hilbert(s1)
    analytic2 = hilbert(s2)
    
    # Phase instantanée (argument du nombre complexe)
    phase1 = np.angle(analytic1)
    phase2 = np.angle(analytic2)
    
    # Différence de phase
    delta_phi = phase1 - phase2
    
    # Verrouillage de phase : |<e^(iΔφ)>|
    R = float(np.abs(np.mean(np.exp(1j * delta_phi))))
    
    return R


def compute_phase_locking(
    X_list: list,
    channel1: int = 0,
    channel2: int = 1
) -> np.ndarray:
    """
    Calcule R pour une liste de nuages (ex : différentes graines ou valeurs de ε).
    
    Returns
    -------
    np.ndarray
        Tableau des valeurs R pour chaque nuage
    """
    return np.array([phase_locking_strength(X, channel1, channel2) for X in X_list])


# =============================================================================
# 4. FONCTIONS UTILITAIRES POUR N19
# =============================================================================

def generate_circular_shift_null(X: np.ndarray, max_lag: int = 10) -> np.ndarray:
    """
    Génère un nul par décalage circulaire (détruit la dépendance temporelle).
    
    Parameters
    ----------
    X : np.ndarray
        Nuage de points de forme (n_timepoints, n_features)
    max_lag : int
        Lag maximum pour le décalage
        
    Returns
    -------
    np.ndarray
        Nuage avec décalage circulaire aléatoire
    """
    n = X.shape[0]
    if n == 0:
        return X
    
    # Décalage aléatoire pour chaque canal
    rng = np.random.default_rng()
    lags = rng.integers(0, max_lag, size=X.shape[1])
    
    X_null = np.zeros_like(X)
    for i, lag in enumerate(lags):
        X_null[:, i] = np.roll(X[:, i], lag)
    
    return X_null


def compute_h1_signature(
    X_real: np.ndarray,
    X_null_list: list,
    coupling_values: np.ndarray
) -> dict:
    """
    Calcule la signature H₁ complète pour N19 :
    - Diagrammes H₁ pour le système réel
    - Distances bottleneck appariées
    - Détection du seuil critique
    
    Parameters
    ----------
    X_real : np.ndarray
        Nuage du système réel (couplé)
    X_null_list : list
        Liste de nuages nuls (un par condition de couplage)
    coupling_values : np.ndarray
        Valeurs de ε correspondantes
        
    Returns
    -------
    dict
        {
            'real_h1': diagramme H₁ du système réel,
            'null_h1': liste des diagrammes H₁ des nuls,
            'bottleneck_distances': distances bottleneck,
            'phase_locking': valeurs R,
            'critical_epsilon': ε critique où H₁ devient significatif
        }
    """
    results = {}
    
    # Calcul H₁ pour le système réel
    if RIPser_AVAILABLE:
        results['real_h1'] = compute_h1_diagram(X_real)
    else:
        results['real_h1'] = np.zeros((0, 2))
    
    # Calcul H₁ pour les nuls
    results['null_h1'] = []
    if RIPser_AVAILABLE:
        for X_null in X_null_list:
            results['null_h1'].append(compute_h1_diagram(X_null))
    
    # Calcul des distances bottleneck
    if PERSIM_AVAILABLE and len(results['null_h1']) > 0:
        paired_dist = compute_paired_bottleneck(
            results['real_h1'], 
            results['null_h1']
        )
        results['bottleneck_distances'] = paired_dist
    else:
        results['bottleneck_distances'] = {
            'mean': float('nan'),
            'ci_lower': float('nan'),
            'ci_upper': float('nan')
        }
    
    # Calcul du verrouillage de phase
    try:
        results['phase_locking'] = phase_locking_strength(X_real)
    except Exception:
        results['phase_locking'] = float('nan')
    
    # Détection du seuil critique (simplifiée)
    # Ici, on cherche où la distance bottleneck devient > 0 de manière significative
    if 'bottleneck_distances' in results:
        if results['bottleneck_distances']['ci_lower'] > 0:
            # Le seuil est la première valeur de ε où CI exclut 0
            # (Cette logique doit être adaptée à tes données)
            results['critical_epsilon'] = float(coupling_values[0]) if len(coupling_values) > 0 else float('nan')
        else:
            results['critical_epsilon'] = float('nan')
    else:
        results['critical_epsilon'] = float('nan')
    
    return results


# =============================================================================
# 5. TEST DE FONCTIONNEMENT
# =============================================================================

if __name__ == "__main__":
    print("h1_pipeline.py - Module H₁ charge.")
    print(f"ripser disponible: {RIPser_AVAILABLE}")
    print(f"persim disponible: {PERSIM_AVAILABLE}")
    
    # Test avec des données aléatoires
    if RIPser_AVAILABLE and PERSIM_AVAILABLE:
        print("\n--- Test H₁ ---")
        rng = np.random.default_rng(42)
        X_test = rng.normal(size=(100, 3))  # 100 points, 3 dimensions
        
        # Calcul H₁
        h1_dgm = compute_h1_diagram(X_test)
        print(f"Diagramme H₁: {h1_dgm.shape[0]} barres")
        
        # Distance bottleneck
        dist = bottleneck_distance(h1_dgm, h1_dgm)
        print(f"Distance bottleneck (même diagramme): {dist:.6f}")
        
        # Verrouillage de phase (nécessite au moins 2 canaux)
        X_2ch = rng.normal(size=(100, 2))
        R = phase_locking_strength(X_2ch)
        print(f"Verrouillage de phase R: {R:.6f}")
    else:
        print("\n⚠️  Impossible de tester : ripser ou persim non disponible.")
