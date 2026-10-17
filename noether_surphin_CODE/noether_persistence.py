"""
noether_persistence.py
======================
Module SurPhiN : Lois de bilan topologiques et termes-sources (copeaux)
sous l'angle d'un "theoreme de Noether pour la persistance H0".

Contexte SurPhiN
----------------
- Le plongement de Takens transforme le temps physique (trajectoire x(t))
  en geometrie statique (attracteur dans R^m).
- La filtration single-linkage sur ce nuage produit un faisceau purifie
  de composantes connexes H0(epsilon), site = poset des echelles epsilon.
- Ce module formalise ce que nous appelons le "copeau" comme un terme-source
  dans une loi de bilan : la variation d'une quantite topologique conservee
  sous l'action d'un parametre externe lambda (graine, g, T, dimension m...).

Loi de bilan fondamentale (analogue Noether-SurPhiN)
----------------------------------------------------
    dQ_topo / dlambda  =  sigma_lambda

ou Q_topo est une "charge" topologique (ex: energie de persistance,
moment topologique, nombre de composantes adiabatiques) et sigma_lambda est
le copeau median (terme-source) associe a la variation du parametre lambda.

References internes
-------------------
- faisceau_purifie.py   : site = epsilon, fibre = H0(epsilon), restriction = inclusion exacte.
- faisceau_couplage.py  : couplage multi-signaux, bottleneck H0 exact.
- surphin_couplage_viz_vO3b.py : grille g x T, stabilite multi-graines.
- Tests 02, 03, 04      : donnees empiriques sur robustesse et invariants.

Auteur : SurPhiN / COHESION_LAB_V01
"""

from __future__ import annotations

import numpy as np
from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Callable, Optional
from collections import defaultdict
import warnings

# =============================================================================
# 0. TYPES ET STRUCTURES DE DONNEES
# =============================================================================

@dataclass
class PersDiagram:
    """
    Diagramme de persistance H0 : liste de paires (naissance, mort).
    Naissance = distance a laquelle la composante apparait.
    Mort      = distance a laquelle elle fusionne dans une autre.
    """
    pairs: np.ndarray  # shape (n, 2), births <= deaths
    param: Dict = field(default_factory=dict)  # metadonnees (graine, g, T, m, etc.)

    def __post_init__(self):
        self.pairs = np.asarray(self.pairs)
        if self.pairs.ndim == 1 and len(self.pairs) == 2:
            self.pairs = self.pairs.reshape(1, 2)
        if self.pairs.size == 0:
            self.pairs = np.zeros((0, 2))

    @property
    def lifetimes(self) -> np.ndarray:
        """Durees de vie d_i = death_i - birth_i."""
        return self.pairs[:, 1] - self.pairs[:, 0]

    @property
    def n_components(self) -> int:
        return len(self.pairs)


@dataclass
class BalanceLaw:
    """
    Resultat d'une loi de bilan : variation d'une charge topologique.

    charge_name   : nom de la quantite Q (ex: "pers_energy", "adiabatic_ncomp")
    param_name    : nom du parametre lambda (ex: "seed", "g", "T", "dim")
    dQ_dlambda    : derivee (discrete ou symbolique) de Q par rapport a lambda
    source_term   : sigma_lambda, le terme-source / copeau
    is_conserved  : True si |source_term| < tol (symetrie respectee)
    metadata      : contexte (condition g x T, etc.)
    """
    charge_name: str
    param_name: str
    dQ_dlambda: float
    source_term: float
    is_conserved: bool
    metadata: Dict = field(default_factory=dict)


@dataclass
class TopologicalCurrent:
    """
    Courant de persistance : flux de naissance/mort a travers l'echelle epsilon.

    En mecanique continue : partial_mu j^mu = sigma.
    En persistance H0     : d/depsilon N(epsilon) = J_birth(epsilon) - J_death(epsilon) = sigma(epsilon).

    C'est l'analogue du courant de Noether transporte le long de l'echelle.
    """
    epsilon_grid: np.ndarray
    ncomp: np.ndarray          # N(epsilon) = nombre de composantes
    flux: np.ndarray           # dN/depsilon (discrete)
    births: np.ndarray         # naissances a chaque epsilon
    deaths: np.ndarray         # morts a chaque epsilon
    source: np.ndarray         # sigma(epsilon) = births - deaths (ou flux)


# =============================================================================
# 1. CHARGES TOPOLOGIQUES (quantites Q a conserver)
# =============================================================================

class TopologicalCharges:
    """
    Calcul des "charges" topologiques analogues aux grandeurs Noetheriennes.
    """

    @staticmethod
    def persistence_energy(dgm: PersDiagram, p: float = 2.0) -> float:
        """
        Energie topologique : E_p = sum (death - birth)^p.

        Analogie : en mecanique, E = 1/2 m v^2 + V(x).
        Ici, chaque composante H0 contribue selon sa duree de vie.
        p=2 donne une "energie cinetique" des composantes.
        """
        lifetimes = dgm.lifetimes
        if len(lifetimes) == 0:
            return 0.0
        return float(np.sum(lifetimes ** p))

    @staticmethod
    def persistence_mass(dgm: PersDiagram) -> float:
        """
        Masse totale du diagramme : M = sum (death - birth).
        C'est le cas p=1 de l'energie topologique.
        """
        return TopologicalCharges.persistence_energy(dgm, p=1.0)

    ## adding charges by-Oll
    @staticmethod
    def pers_median(dgm):
        """Median persistence (death - birth)."""
        # Filter out infinite deaths if necessary, as per your notebook's logic
        # persistence = dgm.deaths - dgm.births
        persistence = dgm.pairs[:, 1] - dgm.pairs[:, 0]
        return np.median(persistence[np.isfinite(persistence)])

    @staticmethod
    def pers_entropy_OLDlegacy(dgm):
        """Shannon entropy of the persistence distribution."""
        # persistence = dgm.deaths - dgm.births
        persistence = dgm.pairs[:, 1] - dgm.pairs[:, 0]
        # Only consider finite persistence
        p = persistence[np.isfinite(persistence)]
        if len(p) == 0:
            return 0.0
        
        # Normalize to create a probability distribution
        # We use a small epsilon to avoid division by zero if needed, 
        # but here we treat the values themselves as the 'events'
        # A common way is to bin the persistence values
        counts, bin_edges = np.histogram(p, bins='auto', density=True)
        probs = counts / np.sum(counts)
        probs = probs[probs > 0] # Remove zero probabilities for log
        return -np.sum(probs * np.log(probs))


    @staticmethod
    def pers_entropy(dgm):
        """Shannon entropy of the normalised bar lengths (standard definition)."""
        l = np.asarray(dgm.pairs[:, 1] - dgm.pairs[:, 0], dtype=float)
        l = l[np.isfinite(l)]
        if l.size == 0 or l.sum() <= 0:
            return 0.0

        p = l / l.sum()
        p = p[p > 0]
        return float(-(p * np.log(p)).sum())

    @staticmethod
    def pers_iqr(dgm):
        """Interquartile range of persistence."""
        persistence = dgm.pairs[:, 1] - dgm.pairs[:, 0]
        # persistence = dgm.deaths - dgm.births
        p = persistence[np.isfinite(persistence)]
        if len(p) == 0:
            return 0.0
        return np.percentile(p, 75) - np.percentile(p, 25)
    ## Oll-add-ends


    @staticmethod
    def adiabatic_ncomp(dgm: PersDiagram, epsilon_frac: float = 0.5) -> int:
        """
        Nombre de composantes a une fraction de hmax (invariant adiabatique).

        Dans un potentiel perturbe V = V0 + epsilon V1, certaines quantites
        sont "adiabatiques" : elles changent lentement sous la perturbation.
        Ici, n_comp a 0.5 * hmax est quasi-determine par hmax (Test 04, r ~ -0.95).
        C'est un invariant approche du systeme couple.
        """
        if dgm.n_components == 0:
            return 0
        hmax = float(np.max(dgm.lifetimes)) if len(dgm.lifetimes) > 0 else 1.0
        thresh = epsilon_frac * hmax
        alive = int(np.sum(dgm.pairs[:, 1] > thresh))
        return alive

    @staticmethod
    def depth_fraction(dgm: PersDiagram, epsilon_frac: float = 0.5) -> float:
        """
        Fraction de la profondeur exploree : n_alive(epsilon) / n_total.
        Repond nettement a T (rho ~ +0.78, Test 04).
        """
        n_total = dgm.n_components
        if n_total == 0:
            return 0.0
        n_adiabatic = TopologicalCharges.adiabatic_ncomp(dgm, epsilon_frac)
        return n_adiabatic / n_total

    @staticmethod
    def topological_momentum(dgm: PersDiagram) -> float:
        """
        "Quantite de mouvement" topologique : moment d'ordre 1 des durees de vie.

        Analogie : p = m v. Ici, c'est la position moyenne ponderee
        des durees de vie dans l'espace des echelles.
        """
        lifetimes = dgm.lifetimes
        if len(lifetimes) == 0:
            return 0.0
        return float(np.mean(lifetimes))

    @staticmethod
    def topological_gini(dgm: PersDiagram) -> float:
        """
        Coefficient de Gini des durees de vie : mesure l'heterogeneite
        de la distribution des composantes. Reste plat en T (Test 04).
        """
        lifetimes = dgm.lifetimes
        n = len(lifetimes)
        if n == 0:
            return 0.0
        sorted_lt = np.sort(lifetimes)
        cumsum = np.cumsum(sorted_lt)
        if cumsum[-1] == 0:
            return 0.0
        return float((n + 1 - 2 * np.sum(cumsum) / cumsum[-1]) / n)


# =============================================================================
# 2. TERMES-SOURCES (COPEAUX) ET LOIS DE BILAN
# =============================================================================

class NoetherBalance:
    """
    Calcul des lois de bilan : dQ/dlambda = sigma_lambda.

    Le parametre lambda peut etre :
    - graine (translation dans l'espace des conditions initiales)
    - g (couplage entre signaux)
    - T (seuil de filtration)
    - m (dimension d'embedding Takens)
    """

    @staticmethod
    def compute_balance(
        diagrams: List[PersDiagram],
        param_values: np.ndarray,
        param_name: str,
        charge_fn: Callable[[PersDiagram], float],
        charge_name: str,
        tol: float = 1e-6,
    ) -> List[BalanceLaw]:
        """
        Calcule la loi de bilan pour une charge Q sous variation de lambda.

        Parameters
        ----------
        diagrams     : liste de diagrammes a differentes valeurs de lambda
        param_values : valeurs correspondantes de lambda (doivent etre triees)
        param_name   : nom du parametre (ex: "seed", "g", "T")
        charge_fn    : fonction Q(diagramme) -> float
        charge_name  : nom de la charge (ex: "pers_energy")
        tol          : seuil de conservation (|sigma| < tol => conservee)

        Returns
        -------
        Liste de BalanceLaw, une par intervalle [lambda_i, lambda_{i+1}].
        
        # NoetherBalance.compute_balance(param_name=&quot;seed&quot;) has d_lambda = 1,
        #   so source_term IS the raw charge difference between consecutive seeds.
        #   Rename to dQ_seed, or drop it and keep the inter-seed SD.

        """
        if len(diagrams) != len(param_values):
            raise ValueError("diagrams et param_values doivent avoir la meme taille")
        if len(diagrams) < 2:
            raise ValueError("Au moins 2 diagrammes sont necessaires pour un bilan")

        idx = np.argsort(param_values)
        sorted_diagrams = [diagrams[i] for i in idx]
        sorted_params = param_values[idx]

        balances = []
        Q_vals = np.array([charge_fn(d) for d in sorted_diagrams])

        for i in range(len(sorted_diagrams) - 1):
            d_lambda = sorted_params[i + 1] - sorted_params[i]
            if abs(d_lambda) < 1e-12:
                continue
            dQ = Q_vals[i + 1] - Q_vals[i]
            sigma = dQ / d_lambda

            balances.append(BalanceLaw(
                charge_name=charge_name,
                param_name=param_name,
                dQ_dlambda=float(dQ / d_lambda),
                source_term=float(sigma),
                is_conserved=abs(sigma) < tol,
                metadata={
                    "lambda_left": float(sorted_params[i]),
                    "lambda_right": float(sorted_params[i + 1]),
                    "Q_left": float(Q_vals[i]),
                    "Q_right": float(Q_vals[i + 1]),
                }
            ))

        return balances

    @staticmethod
    def copeau_mediane(
        balances: List[BalanceLaw],
        metric: str = "source_term",
    ) -> float:
        """
        Copeau mediane : valeur centrale du terme-source sur un ensemble
        de conditions (ex: multi-graines). C'est la mesure de robustesse
        du Test 02 formalisee comme loi de bilan.

        Parameters
        ----------
        balances : liste de BalanceLaw (typiquement pour differentes graines)
        metric   : "source_term" | "dQ_dlambda"
        """
        vals = np.array([getattr(b, metric) for b in balances])
        if len(vals) == 0:
            return 0.0
        return float(np.median(np.abs(vals)))

    @staticmethod
    def robustesse_noetherienne(
        balances: List[BalanceLaw],
        metric: str = "source_term",
    ) -> Dict[str, float]:
        """
        Evalue la robustesse d'une charge sous variation de lambda au sens Noether.

        Renvoie un dictionnaire avec :
        - copeau_mediane : mediane des |sigma|
        - copeau_spread  : ecart-type des |sigma|
        - regime         : "conservatif" | "adiabatique" | "turbulent"
        
        # robustesse_noetherienne thresholds are hard-coded constants:
        #   conservative: median &lt; 0.05 and spread &lt; 0.05
        #   adiabatic   : median &lt; 0.15 and spread &lt; 0.10
        #   iid null at N=300 gives |dQ| median 0.0081, sd 0.0073
        #   -&gt; the &quot;conservative&quot; cut sits ~6x the null median. Document it.
        
        """
        vals = np.array([getattr(b, metric) for b in balances])
        abs_vals = np.abs(vals)
        median_val = float(np.median(abs_vals))
        spread_val = float(np.std(abs_vals))

        if median_val < 0.05 and spread_val < 0.05:
            regime = "conservatif"
        elif median_val < 0.15 and spread_val < 0.10:
            regime = "adiabatique"
        else:
            regime = "turbulent"

        return {
            "copeau_mediane": median_val,
            "copeau_spread": spread_val,
            "regime": regime,
            "n_samples": len(balances),
        }


# =============================================================================
# 3. COURANT DE PERSISTANCE (flux le long de epsilon)
# =============================================================================

class PersistenceCurrent:
    """
    Courant de persistance : analogie avec partial_mu j^mu = sigma.

    Le long de l'echelle epsilon, les composantes naissent et meurent.
    Le flux net est le terme-source local sigma(epsilon).
    
    # PersistenceCurrent.integrated_source is ALWAYS n_points - 1.
    #   verified: 299, 119, 299 on three clouds of different sizes and natures
    #   it counts MST edges. Rename to n_merges / edge_count.
   
    """

    @staticmethod
    def from_mst(
        merges: List[Tuple[int, int, float]],
        n_points: int,
        epsilon_grid: Optional[np.ndarray] = None,
        n_bins: int = 100,
    ) -> TopologicalCurrent:
        """
        Construit le courant de persistance depuis un arbre de fusion (MST).

        Parameters
        ----------
        merges : liste de (i, j, distance) triee par distance croissante
                 Chaque merge = mort d'une composante a distance d.
        n_points : nombre total de points dans le nuage
        epsilon_grid : grille d'echelles (None = auto)
        n_bins : nombre de bins si grille auto

        Returns
        -------
        TopologicalCurrent
        """
        if len(merges) == 0:
            if epsilon_grid is None:
                epsilon_grid = np.linspace(0, 1, n_bins)
            return TopologicalCurrent(
                epsilon_grid=epsilon_grid,
                ncomp=np.full_like(epsilon_grid, n_points, dtype=int),
                flux=np.zeros_like(epsilon_grid),
                births=np.zeros_like(epsilon_grid),
                deaths=np.zeros_like(epsilon_grid),
                source=np.zeros_like(epsilon_grid),
            )

        distances = np.array([m[2] for m in merges])
        d_min, d_max = distances[0], distances[-1]

        if epsilon_grid is None:
            epsilon_grid = np.linspace(d_min * 0.9, d_max * 1.1, n_bins)

        ncomp = np.zeros(len(epsilon_grid), dtype=int)
        births = np.zeros(len(epsilon_grid))
        deaths = np.zeros(len(epsilon_grid))

        for idx, eps in enumerate(epsilon_grid):
            n_alive = n_points - int(np.sum(distances <= eps))
            ncomp[idx] = max(n_alive, 1)

            if idx == 0:
                delta = epsilon_grid[1] - epsilon_grid[0] if len(epsilon_grid) > 1 else 1.0
                d_low = epsilon_grid[0] - delta
            else:
                delta = eps - epsilon_grid[idx - 1]
                d_low = epsilon_grid[idx - 1]

            n_deaths = int(np.sum((distances > d_low) & (distances <= eps)))
            deaths[idx] = n_deaths / delta if delta > 0 else 0

        flux = -np.gradient(ncomp.astype(float), epsilon_grid)
        source = flux

        return TopologicalCurrent(
            epsilon_grid=epsilon_grid,
            ncomp=ncomp,
            flux=flux,
            births=births,
            deaths=deaths,
            source=source,
        )

    @staticmethod
    def integrated_source(current: TopologicalCurrent) -> float:
        """
        Source integree : integral sigma(epsilon) depsilon.
        Dans un systeme conservatif (recollement exact), cette integrale
        doit etre egale a la variation totale du nombre de composantes.
        """
        return float(np.trapezoid(current.source, current.epsilon_grid))


# =============================================================================
# 4. IDENTITES DE WARD TOPOLOGIQUES
# =============================================================================
def bottleneck_H0(deaths_a: Sequence[float], deaths_b: Sequence[float]) -> float:
    """Distance bottleneck H0 par programmation dynamique, diagonale incluse."""
    a = np.sort(np.asarray(deaths_a, dtype=float))
    b = np.sort(np.asarray(deaths_b, dtype=float))
    if a.ndim != 1 or b.ndim != 1:
        raise ValueError("Les diagrammes H0 doivent être des tableaux 1D.")
    if not np.all(np.isfinite(a)) or not np.all(np.isfinite(b)):
        raise ValueError("Les diagrammes H0 doivent contenir des valeurs finies.")
    na, nb = len(a), len(b)
    dp = np.full((na + 1, nb + 1), np.inf)
    dp[0, 0] = 0.0
    for i in range(1, na + 1):
        dp[i, 0] = max(dp[i - 1, 0], a[i - 1] / 2.0)
    for j in range(1, nb + 1):
        dp[0, j] = max(dp[0, j - 1], b[j - 1] / 2.0)
    for i in range(1, na + 1):
        for j in range(1, nb + 1):
            paired = max(dp[i - 1, j - 1], abs(a[i - 1] - b[j - 1]))
            drop_a = max(dp[i - 1, j], a[i - 1] / 2.0)
            drop_b = max(dp[i, j - 1], b[j - 1] / 2.0)
            dp[i, j] = min(paired, drop_a, drop_b)
    return float(dp[na, nb])

class WardIdentities:
    """
    Identites de Ward topologiques : [partial_lambda, H^0] = Copeau(lambda).

    Mesure la non-commutation entre "varier un parametre externe" et
    "calculer la cohomologie H0". Le copeau est le commutateur.
    """

    @staticmethod
    def commutator_copeau(
        dgm_left: PersDiagram,
        dgm_right: PersDiagram,
        lambda_left: float,
        lambda_right: float,
        bottleneck_distance_fn: Optional[Callable] = None,
    ) -> float:
        """
        Copeau comme norme du commutateur [partial_lambda, H^0].

        Approximation : on utilise la distance bottleneck entre diagrammes
        comme proxy de la norme du commutateur.

        Si vous avez deja une fonction bottleneck exacte (faisceau_couplage.py),
        passez-la en argument. Sinon, on utilise une approximation L2.

        voir, dans topology_engine.py OU surphin_couplage_viz_vO3c_PATCHED.py :
        bottleneck_H0

        """
        if bottleneck_distance_fn is not None:
            d_bottleneck = bottleneck_distance_fn(dgm_left, dgm_right)
            # print("_approx_bottleneck used")#"debug d'apprenti as gemma agreed"
        else:
            d_bottleneck = bottleneck_H0(dgm_left, dgm_right)
            # d_bottleneck = WardIdentities._approx_bottleneck(dgm_left, dgm_right)

        d_lambda = lambda_right - lambda_left
        if abs(d_lambda) < 1e-12:
            return 0.0

        return d_bottleneck / abs(d_lambda)

    @staticmethod
    def _approx_bottleneck(dgm1: PersDiagram, dgm2: PersDiagram) -> float:
        """
        Approximation rapide de la distance entre diagrammes par difference
        des energies topologiques (proxy quand le bottleneck exact n'est pas dispo).
        """
        e1 = TopologicalCharges.persistence_energy(dgm1, p=2.0)
        e2 = TopologicalCharges.persistence_energy(dgm2, p=2.0)
        return abs(e1 - e2)


# =============================================================================
# 5. INVARIANTS ADIABATIQUES ET "VERITES ACCEPTALES"
# =============================================================================

class AdiabaticInvariants:
    """
    Invariants adiabatiques : quantites qui changent lentement sous
    perturbation. La "verite acceptale" est une charge dont la derivee
    est bornee par un terme-source faible.
    """

    @staticmethod
    def is_acceptable(
        balances: List[BalanceLaw],
        epsilon_tol: float = 0.1,
    ) -> bool:
        """
        Une charge est "acceptable" (verite acceptale) si son terme-source
        est faible (|sigma| < epsilon_tol) sur l'ensemble des conditions testees.

        C'est la formalisation mathematique de la "verite acceptale" de SurPhiN :
        pas une verite exacte, mais une quantite dont la derivee est controlee.
        """
        if len(balances) == 0:
            return False
        max_sigma = max(abs(b.source_term) for b in balances)
        return max_sigma < epsilon_tol

    @staticmethod
    def adiabatic_order(
        diagrams: List[PersDiagram],
        param_values: np.ndarray,
        charge_fn: Callable[[PersDiagram], float],
    ) -> float:
        """
        Ordre adiabatique : mesure a quel point la charge est adiabatique.

        Renvoie le rapport |dQ/dlambda| / |Delta Q| ou Delta Q est la variation totale.
        Proche de 0 => adiabatique (derive lente).
        Proche de 1 => non adiabatique (variation brutale).
        """
        Q_vals = np.array([charge_fn(d) for d in diagrams])
        idx = np.argsort(param_values)
        Q_sorted = Q_vals[idx]
        params_sorted = param_values[idx]

        if len(Q_sorted) < 2:
            return 1.0

        dQ = np.diff(Q_sorted)
        dlambda = np.diff(params_sorted)
        derivatives = dQ / (dlambda + 1e-12)

        delta_Q_total = abs(Q_sorted[-1] - Q_sorted[0])
        if delta_Q_total < 1e-12:
            return 0.0

        mean_derivative = np.mean(np.abs(derivatives))
        return float(mean_derivative / delta_Q_total)


# =============================================================================
# 6. INTEGRATION AVEC LE PIPELINE EXISTANT
# =============================================================================

class NoetherPipeline:
    """
    Interface entre noether_persistence.py et le pipeline SurPhiN existant.
    """

    @staticmethod
    def from_faisceau_purifie_OLDlegacy(
        merges: List[Tuple[int, int, float]],
        n_points: int,
        param: Dict,
    ) -> PersDiagram:
        """
        Convertit la sortie de faisceau_purifie.py (arbre de fusion MST)
        en un PersDiagram utilisable par ce module.

        Parameters
        ----------
        merges : sortie de scipy.sparse.csgraph.minimum_spanning_tree
                 ou de l'algorithme single-linkage interne.
                 Format : [(i, j, distance), ...] trie par distance.
        n_points : nombre de points dans le nuage
        param : metadonnees {graine, g, T, dim, ...}
        """
        n_merges = len(merges)
        pairs = []
        for k, (i, j, d) in enumerate(merges):
            pairs.append([0.0, d])
        if n_merges > 0:
            max_d = merges[-1][2]
            pairs.append([0.0, max_d * 2])

        return PersDiagram(pairs=np.array(pairs), param=param)

    @staticmethod
    def from_faisceau_purifie(
        merges: List[Tuple[int, int, float]],
        n_points: int,
        param: Dict,
    ) -> PersDiagram:
        """H0 d'un nuage de points : une barre finie par fusion MST.

        Le diagramme ne contient pas de classe essentielle artificielle.
        """
        pairs = np.array([[0.0, float(d)] for (_, _, d) in merges])
        return PersDiagram(pairs=pairs, param=param)

    @staticmethod
    def analyze_grille_couplage(
        diagram_grid: Dict[Tuple[float, float], PersDiagram],
        g_values: List[float],
        T_values: List[float],
    ) -> Dict:
        """
        Analyse Noetherienne complete de la grille de couplage g x T.

        Reproduit et formalise les Tests 02, 03, 04 comme lois de bilan.

        Returns
        -------
        Dict avec les resultats par charge et par parametre.
        """
        results = {
            "by_charge": {},
            "robustesse": {},
            "regimes": {},
        }

        charges = {
            "pers_energy": TopologicalCharges.persistence_energy,
            "pers_mass": TopologicalCharges.persistence_mass,
            "adiabatic_ncomp": TopologicalCharges.adiabatic_ncomp,
            "depth_fraction": TopologicalCharges.depth_fraction,
            "topological_momentum": TopologicalCharges.topological_momentum,
            "topological_gini": TopologicalCharges.topological_gini,
        }

        for T in T_values:
            dgms_T = [diagram_grid[(g, T)] for g in g_values if (g, T) in diagram_grid]
            if len(dgms_T) < 2:
                continue
            for charge_name, charge_fn in charges.items():
                balances = NoetherBalance.compute_balance(
                    dgms_T, np.array(g_values), "g", charge_fn, charge_name, tol=0.05
                )
                key = f"{charge_name}_vs_g_T{T}"
                results["by_charge"][key] = balances
                results["robustesse"][key] = NoetherBalance.robustesse_noetherienne(balances)

        for g in g_values:
            dgms_g = [diagram_grid[(g, T)] for T in T_values if (g, T) in diagram_grid]
            if len(dgms_g) < 2:
                continue
            for charge_name, charge_fn in charges.items():
                balances = NoetherBalance.compute_balance(
                    dgms_g, np.array(T_values), "T", charge_fn, charge_name, tol=0.05
                )
                key = f"{charge_name}_vs_T_g{g}"
                results["by_charge"][key] = balances
                results["robustesse"][key] = NoetherBalance.robustesse_noetherienne(balances)

        return results


# =============================================================================
# 7. UTILITAIRES ET FORMATAGE
# =============================================================================

def format_balance(b: BalanceLaw) -> str:
    """Format lisible d'une loi de bilan."""
    conserved = "CONSERVEE" if b.is_conserved else "NON CONSERVEE"
    return (
        f"[{b.charge_name}] vs {b.param_name} : "
        f"dQ/dlambda = {b.dQ_dlambda:.6f}, sigma = {b.source_term:.6f} [{conserved}]"
    )


def summary_report(results: Dict) -> str:
    """Rapport textuel synthetique des resultats Noetheriens."""
    lines = ["=" * 60, "RAPPORT NOETHER-SURPHIN", "=" * 60, ""]

    for key, robust in results.get("robustesse", {}).items():
        lines.append(f"\n{key}")
        lines.append(f"  Copeau mediane : {robust['copeau_mediane']:.4f}")
        lines.append(f"  Copeau spread  : {robust['copeau_spread']:.4f}")
        lines.append(f"  Regime         : {robust['regime'].upper()}")
        lines.append(f"  N echantillons : {robust['n_samples']}")

    lines.append("\n" + "=" * 60)
    return "\n".join(lines)


# =============================================================================
# 8. DEMO MINIMALE
# =============================================================================

if __name__ == "__main__":
    print("noether_persistence.py - Module SurPhiN charge.")
    print("Lois de bilan topologiques et termes-sources (copeaux).")
    print()

    # Demo : trois diagrammes a differents g (T fixe)
    dgm_015 = PersDiagram(pairs=np.array([[0, 0.3], [0, 0.5], [0, 0.8]]), param={"g": 0.15})
    dgm_035 = PersDiagram(pairs=np.array([[0, 0.35], [0, 0.55], [0, 0.85]]), param={"g": 0.35})
    dgm_070 = PersDiagram(pairs=np.array([[0, 0.1], [0, 0.2], [0, 0.4], [0, 0.9]]), param={"g": 0.70})

    balances = NoetherBalance.compute_balance(
        [dgm_015, dgm_035, dgm_070],
        np.array([0.15, 0.35, 0.70]),
        "g",
        TopologicalCharges.persistence_energy,
        "pers_energy",
        tol=0.5,
    )

    print("--- Lois de bilan pers_energy vs g ---")
    for b in balances:
        print(format_balance(b))

    robust = NoetherBalance.robustesse_noetherienne(balances)
    print(f"\nRobustesse : regime = {robust['regime']}")
    print(f"Copeau mediane = {robust['copeau_mediane']:.4f}")
