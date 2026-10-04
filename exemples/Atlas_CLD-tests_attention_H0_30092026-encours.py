#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests des points d'attention 1 à 4 de l'Atlas SurPhiN (couplage H0).

À placer dans le même dossier que :
    surphin_couplage_viz_vO3c.py   (ou surphin_couplage_viz_vO3c_PATCHED.py)
    langevin_bridge.py             (test 3 seulement)

Tests
    1  Shuffle       : H0 voit-il l'ordre temporel, ou seulement la loi marginale ?
                       (contrôle positif : AR(1) ; contrôle négatif : Poisson i.i.d.)
    2  Unfolding     : effet de la tendance de densité de zêta sur les distances.
    3  Tau physique  : sensibilité de H0 à tau*dt pour un signal de Langevin.
    4  Normalisation : mantisse par max / médiane / longueur totale, stabilité selon la graine.

Usage
    python tests_attention_H0.py --test all
    python tests_attention_H0.py --test 1 3 --n-max 400 --seeds 20
    python tests_attention_H0.py --test 4 --n-zeros 500

Les zéros de zêta (mpmath, lent) sont mis en cache dans zeta_zeros_cache.npy.
Sorties : ./tests_attention_out/ (figures .png + résumé .txt).
"""

from __future__ import annotations

import argparse
import importlib
import importlib.util
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))


# ---------------------------------------------------------------------------
# Import du script principal (avec ou sans suffixe _PATCHED)
# ---------------------------------------------------------------------------
def _import_main():
    try:
        return importlib.import_module("surphin_couplage_viz_vO3c")
    except ImportError:
        patched = SCRIPT_DIR / "surphin_couplage_viz_vO3c_PATCHED.py"
        if not patched.is_file():
            raise SystemExit(
                "Impossible d'importer surphin_couplage_viz_vO3c.py "
                "(ni la version _PATCHED) depuis " + str(SCRIPT_DIR)
            )
        spec = importlib.util.spec_from_file_location("surphin_couplage_viz_vO3c", patched)
        module = importlib.util.module_from_spec(spec)
        sys.modules["surphin_couplage_viz_vO3c"] = module
        spec.loader.exec_module(module)
        return module


sp = _import_main()

OUT_DIR = SCRIPT_DIR / "tests_attention_out"
SUMMARY: list[str] = []


def say(text: str = "") -> None:
    print(text, flush=True)
    SUMMARY.append(text)


# ---------------------------------------------------------------------------
# Signaux
# ---------------------------------------------------------------------------
def zeta_ordinates(n: int, cache: Path) -> np.ndarray:
    """n+1 premières ordonnées des zéros de zêta (cache .npy)."""
    if cache.is_file():
        data = np.load(cache)
        if len(data) >= n + 1:
            return data[: n + 1]
    import mpmath

    say(f"  calcul de {n + 1} zéros de zêta (mpmath, lent, une seule fois)...")
    ords = np.fromiter(
        (float(mpmath.zetazero(k).imag) for k in range(1, n + 2)), dtype=float, count=n + 1
    )
    np.save(cache, ords)
    return ords


def n_smooth(t: np.ndarray) -> np.ndarray:
    """Comptage lissé de Riemann–von Mangoldt : N(T) ≈ (T/2π) ln(T/2πe) + 7/8."""
    return (t / (2 * np.pi)) * np.log(t / (2 * np.pi * np.e)) + 7.0 / 8.0


def zeta_raw(ords: np.ndarray) -> np.ndarray:
    """Comme le pipeline : espacements bruts divisés par la moyenne globale."""
    return sp._unit_mean_spacings(np.diff(ords), "zeta-raw")


def zeta_unfolded(ords: np.ndarray) -> np.ndarray:
    """Espacements dépliés : différences de N_lisse, moyenne 1."""
    return sp._unit_mean_spacings(np.diff(n_smooth(ords)), "zeta-unfolded")


def ar1(n: int, phi: float, seed: int) -> np.ndarray:
    """Contrôle positif : AR(1). Avec phi=0.99 la corrélation au retard tau=20 vaut ~0.82."""
    rng = np.random.default_rng(seed)
    x = np.zeros(n)
    eps = rng.standard_normal(n)
    for i in range(1, n):
        x[i] = phi * x[i - 1] + eps[i]
    return x


# ---------------------------------------------------------------------------
# Outils H0
# ---------------------------------------------------------------------------
def deaths_of(x, tau: int, d: int, n_max: int, seed: int) -> np.ndarray:
    return sp.fusion_deaths(sp.phase_cloud(x, tau=tau, d=d, n_max=n_max, seed=seed))


def normalise(deaths: np.ndarray, how: str) -> np.ndarray:
    if how == "max":  # convention actuelle (mantisse)
        return deaths / np.max(deaths)
    if how == "median":
        return deaths / np.median(deaths)
    if how == "total":  # moyenne des morts ramenée à 1
        return deaths / np.mean(deaths)
    raise ValueError(how)


def bott(a: np.ndarray, b: np.ndarray) -> float:
    return sp.bottleneck_H0(a, b)


def shuffled(x: np.ndarray, j: int) -> np.ndarray:
    return np.random.default_rng(1000 + j).permutation(x)


def fmt_row(cells, widths) -> str:
    return "  ".join(str(c).rjust(w) for c, w in zip(cells, widths))



def order_sensitivity(x: np.ndarray, tau: int, d: int, n_max: int, seeds: list[int]) -> dict[str, float]:
    """Test de permutation : le signal se distingue-t-il de ses versions mélangées ?

    Pour chaque graine s : orig(s) = nuage du signal ; A(s) et B(s) = nuages de deux
    mélanges indépendants. On compare  d(orig, A)  (effet)  à  d(A, B)  (nul).
    Si l'ordre n'est pas vu, orig est échangeable avec un mélange : effet ≈ nul (ratio ≈ 1).
    Deux observables : forme (d_B des mantisses) et échelle (|ln| du rapport des exposants).
    """
    eff_m, nul_m, eff_e, nul_e = [], [], [], []
    for s in seeds:
        e_o = deaths_of(x, tau, d, n_max, s)
        e_a = deaths_of(shuffled(x, 2 * s), tau, d, n_max, s)
        e_b = deaths_of(shuffled(x, 2 * s + 1), tau, d, n_max, s)
        m_o, m_a, m_b = (normalise(v, "max") for v in (e_o, e_a, e_b))
        eff_m.append(bott(m_o, m_a))
        nul_m.append(bott(m_a, m_b))
        eff_e.append(abs(np.log(np.max(e_o) / np.max(e_a))))
        nul_e.append(abs(np.log(np.max(e_a) / np.max(e_b))))
    def ratio(a, b):
        return float(np.median(a) / np.median(b)) if np.median(b) > 0 else float("nan")
    return {
        "forme_effet": float(np.median(eff_m)), "forme_nul": float(np.median(nul_m)),
        "forme_ratio": ratio(eff_m, nul_m),
        "echelle_effet": float(np.median(eff_e)), "echelle_nul": float(np.median(nul_e)),
        "echelle_ratio": ratio(eff_e, nul_e),
    }

# ---------------------------------------------------------------------------
# TEST 1 — shuffle
# ---------------------------------------------------------------------------
def test1_shuffle(signals: dict[str, np.ndarray], tau: int, d: int, n_max: int, seeds: list[int]) -> None:
    say("=" * 72)
    say("TEST 1 — Permutation : H0 voit-il l'ordre temporel ?")
    say(f"  tau={tau}, d={d}, n_max={n_max}, {len(seeds)} graines")
    say("  effet = distance signal <-> mélange ; nul = distance mélange <-> autre mélange")
    say("  ratio = effet / nul   (≈1 : signal échangeable avec un mélange, l'ordre n'est pas vu ;")
    say("                         ≫1 : l'ordre est vu)   Deux observables : forme et échelle.")
    say()
    widths = (16, 9, 9, 8, 9, 9, 8)
    say(fmt_row(("signal", "forme:eff", "forme:nul", "ratio", "éch.:eff", "éch.:nul", "ratio"), widths))
    res = {}
    for name, x in signals.items():
        r = order_sensitivity(x, tau, d, n_max, seeds)
        res[name] = r
        say(fmt_row((name, f"{r['forme_effet']:.3f}", f"{r['forme_nul']:.3f}", f"{r['forme_ratio']:.2f}",
                     f"{r['echelle_effet']:.3f}", f"{r['echelle_nul']:.3f}", f"{r['echelle_ratio']:.2f}"), widths))
    say()
    say("Lecture : Poisson (i.i.d.) doit donner ≈ 1 partout (échangeabilité exacte) ; sinus et")
    say("AR(1) sont les contrôles positifs. Un observable dont le ratio reste ≈ 1 sur les contrôles")
    say("positifs n'a pas de puissance : on ne peut alors rien conclure pour zêta/GUE avec lui.")
    say("Avec peu de graines, des écarts de ±0.3 autour de 1 sont du bruit : utilisez --seeds 25.")

    fig, ax = plt.subplots(figsize=(8, 4))
    names = list(res)
    xs = np.arange(len(names))
    ax.bar(xs - 0.2, [res[n]["forme_ratio"] for n in names], 0.4, label="forme (d_B mantisses)")
    ax.bar(xs + 0.2, [res[n]["echelle_ratio"] for n in names], 0.4, label="échelle (exposant)")
    ax.axhline(1.0, color="k", lw=0.8, ls="--")
    ax.set_xticks(xs)
    ax.set_xticklabels(names, rotation=20, ha="right")
    ax.set_ylabel("effet / nul")
    ax.set_title(f"Test 1 — sensibilité de H0 à l'ordre (tau={tau}, d={d})")
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUT_DIR / "test1_shuffle.png", dpi=150)
    plt.close(fig)


# ---------------------------------------------------------------------------
# TEST 2 — unfolding de zêta
# ---------------------------------------------------------------------------
def pair_table(sigs: dict[str, np.ndarray], pairs, tau, d, n_max, seeds, how="max"):
    out = {p: [] for p in pairs}
    for s in seeds:
        m = {n: normalise(deaths_of(x, tau, d, n_max, s), how) for n, x in sigs.items()}
        for a, b in pairs:
            out[(a, b)].append(bott(m[a], m[b]))
    return {p: np.asarray(v) for p, v in out.items()}


def test2_unfolding(ords: np.ndarray, gue: np.ndarray, poisson: np.ndarray, tau, d, n_max, seeds) -> None:
    from scipy.stats import spearmanr

    say("=" * 72)
    say("TEST 2 — Zêta brut (moyenne globale) vs zêta déplié (N lissé)")
    raw, unf = zeta_raw(ords), zeta_unfolded(ords)
    k = max(len(raw) // 10, 10)
    say(f"  tendance zêta brut   : moyenne(10 premiers %)/moyenne(10 derniers %) = "
        f"{np.mean(raw[:k]) / np.mean(raw[-k:]):.2f} ; Spearman(indice, espacement) = "
        f"{spearmanr(np.arange(len(raw)), raw)[0]:+.3f}")
    say(f"  tendance zêta déplié : rapport = {np.mean(unf[:k]) / np.mean(unf[-k:]):.2f} ; "
        f"Spearman = {spearmanr(np.arange(len(unf)), unf)[0]:+.3f}")
    say()
    n = min(len(raw), len(gue), len(poisson))
    sigs = {"zeta_brut": raw[:n], "zeta_deplie": unf[:n], "gue": gue[:n], "poisson": poisson[:n]}
    pairs = [
        ("zeta_brut", "gue"), ("zeta_brut", "poisson"),
        ("zeta_deplie", "gue"), ("zeta_deplie", "poisson"),
        ("gue", "poisson"),
    ]
    res = pair_table(sigs, pairs, tau, d, n_max, seeds)
    widths = (26, 9, 9, 9)
    say(fmt_row(("paire (d_B, mantisses)", "médiane", "min", "max"), widths))
    for (a, b), v in res.items():
        say(fmt_row((f"{a} | {b}", f"{np.median(v):.4f}", f"{v.min():.4f}", f"{v.max():.4f}"), widths))
    say()
    say("Lecture : si zeta_deplie se rapproche de gue (ou s'éloigne de poisson) par rapport à")
    say("zeta_brut, la tendance de densité pesait sur le couplage ; sinon elle est négligeable.")

    fig, ax = plt.subplots(figsize=(8, 4.5))
    labels = [f"{a}\n{b}" for a, b in pairs]
    ax.boxplot([res[p] for p in pairs])
    ax.set_xticklabels(labels)
    ax.set_ylabel("distance bottleneck H0 (mantisses)")
    ax.set_title(f"Test 2 — effet de l'unfolding (tau={tau}, d={d}, n_max={n_max})")
    plt.setp(ax.get_xticklabels(), fontsize=7)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "test2_unfolding.png", dpi=150)
    plt.close(fig)


# ---------------------------------------------------------------------------
# TEST 3 — tau physique (Langevin)
# ---------------------------------------------------------------------------
def test3_tau_physique(d: int, n_max: int, seeds: list[int], gamma: float, temp: float,
                       t_final: float, dt: float) -> None:
    say("=" * 72)
    say("TEST 3 — Sensibilité de H0 à tau*dt pour un signal de Langevin")
    try:
        import langevin_bridge as lb
    except ImportError:
        say("  langevin_bridge.py introuvable : test 3 ignoré.")
        return
    omega0 = lb.freq_naturelle(lb.PUITS[0]["position"])
    period = 2 * np.pi / omega0
    say(f"  gamma={gamma}, T={temp}, dt={dt}, temps_final={t_final}, "
        f"omega0={omega0:.3f}, période propre={period:.2f}")
    _, theta, _ = lb.simuler_langevin(gamma=gamma, T=temp, dt=dt, temps_final=t_final, graine=7)
    say(f"  trajectoire : {len(theta)} points")
    tau_phys = [0.05, 0.1, 0.2, 0.5, 1.0, period / 4, period / 2, period]
    tau_phys = sorted(set(round(t, 3) for t in tau_phys))
    widths = (10, 8, 10, 8, 8)
    say()
    say(fmt_row(("tau*dt", "tau", "exposant", "forme", "échelle"), widths))
    say("  (forme / échelle = ratios effet/nul du test de permutation ; ≈1 : ordre non vu)")
    ratios_f, ratios_e = [], []
    for tp in tau_phys:
        tau = max(1, int(round(tp / dt)))
        e = float(np.median([np.max(deaths_of(theta, tau, d, n_max, s)) for s in seeds]))
        r = order_sensitivity(theta, tau, d, n_max, seeds)
        ratios_f.append(r["forme_ratio"])
        ratios_e.append(r["echelle_ratio"])
        say(fmt_row((f"{tp:.3f}", tau, f"{e:.4f}", f"{r['forme_ratio']:.2f}", f"{r['echelle_ratio']:.2f}"), widths))
    say()
    say("Lecture : les ratios indiquent pour quel tau*dt l'ordre temporel est visible pour H0")
    say("(forme = mantisse, échelle = exposant). Comparez avec période/4 et période/2.")

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(tau_phys, ratios_f, "o-", label="forme (mantisse)")
    ax.plot(tau_phys, ratios_e, "s-", label="échelle (exposant)")
    ax.axhline(1.0, color="k", lw=0.8, ls="--")
    ax.axvline(period / 4, color="tab:red", lw=0.8, ls=":", label="période/4")
    ax.axvline(period / 2, color="tab:green", lw=0.8, ls=":", label="période/2")
    ax.set_xscale("log")
    ax.set_xlabel("tau * dt (temps physique)")
    ax.set_ylabel("effet / nul (permutation)")
    ax.set_title(f"Test 3 — Langevin (γ={gamma}, T={temp}, d={d})")
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUT_DIR / "test3_tau_physique.png", dpi=150)
    plt.close(fig)


# ---------------------------------------------------------------------------
# TEST 4 — normalisation de la mantisse
# ---------------------------------------------------------------------------
def test4_normalisation(sigs: dict[str, np.ndarray], tau: int, d: int, n_max: int, seeds: list[int]) -> None:
    say("=" * 72)
    say("TEST 4 — Normalisation : max (actuel) vs médiane vs longueur totale")
    names = list(sigs)
    pairs = [(a, b) for i, a in enumerate(names) for b in names[i + 1:]]
    say(f"  signaux : {names} ; {len(seeds)} graines ; tau={tau}, d={d}, n_max={n_max}")
    say("  CV     = écart-type / moyenne de d_B sur les graines (par paire), moyenné sur les paires")
    say("  flips  = nombre de configurations distinctes de la paire la plus proche")
    say("  marge  = médiane de (2e plus petite - plus petite) / plus petite")
    say()
    raw = {s: {n: deaths_of(x, tau, d, n_max, s) for n, x in sigs.items()} for s in seeds}
    widths = (8, 8, 8, 8, 30)
    say(fmt_row(("norm", "CV", "flips", "marge", "fréquence de la paire la plus proche"), widths))
    fig, axes = plt.subplots(1, 3, figsize=(13, 4), sharey=False)
    for ax, how in zip(axes, ("max", "median", "total")):
        table = {p: [] for p in pairs}
        for s in seeds:
            m = {n: normalise(raw[s][n], how) for n in names}
            for a, b in pairs:
                table[(a, b)].append(bott(m[a], m[b]))
        arr = np.array([table[p] for p in pairs])  # (paires, graines)
        cv = float(np.mean(np.std(arr, axis=1) / np.mean(arr, axis=1)))
        closest = np.argmin(arr, axis=0)
        counts = np.bincount(closest, minlength=len(pairs))
        srt = np.sort(arr, axis=0)
        margin = float(np.median((srt[1] - srt[0]) / srt[0]))
        freq = ", ".join(f"{a[:4]}|{b[:4]}:{c}" for (a, b), c in zip(pairs, counts) if c)
        say(fmt_row((how, f"{cv:.3f}", int(np.count_nonzero(counts)), f"{margin:.3f}", freq), widths))
        ax.boxplot([table[p] for p in pairs])
        ax.set_xticklabels([f"{a[:5]}\n{b[:5]}" for a, b in pairs])
        ax.set_title(f"normalisation : {how}")
        ax.set_ylabel("d_B H0")
    fig.suptitle("Test 4 — dispersion des distances de paire selon la graine")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "test4_normalisation.png", dpi=150)
    plt.close(fig)
    say()
    say("Lecture : une normalisation plus stable a un CV plus faible, moins de flips et une")
    say("marge plus grande. Attention : les distances ne sont comparables qu'à l'intérieur")
    say("d'une même normalisation (échelles différentes) ; comparez CV, flips et marge.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    global OUT_DIR
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--test", nargs="+", default=["all"], help="1 2 3 4 ou all")
    p.add_argument("--n-signals", type=int, default=500, help="longueur des signaux d'espacements")
    p.add_argument("--n-zeros", type=int, default=None, help="zéros de zêta (défaut : n-signals)")
    p.add_argument("--n-max", type=int, default=300, help="taille des nuages sous-échantillonnés")
    p.add_argument("--seeds", type=int, default=12, help="nombre de graines")
    p.add_argument("--tau", type=int, default=20)
    p.add_argument("--dim", type=int, default=2)
    p.add_argument("--gamma", type=float, default=0.35)
    p.add_argument("--temp", type=float, default=0.25)
    p.add_argument("--t-final", type=float, default=300.0, help="durée Langevin (test 3)")
    p.add_argument("--dt", type=float, default=0.01)
    p.add_argument("--out-dir", type=Path, default=OUT_DIR)
    args = p.parse_args()

    OUT_DIR = args.out_dir
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    tests = {"1", "2", "3", "4"} if "all" in args.test else set(args.test)
    seeds = list(range(args.seeds))
    n = args.n_signals
    n_zeros = args.n_zeros or n

    need_zeta = tests & {"1", "2", "4"}
    ords = zeta_ordinates(n_zeros, SCRIPT_DIR / "zeta_zeros_cache.npy") if need_zeta else None
    gue = sp.generate_gue_spacings(n, seed=1)
    poisson = sp.generate_poisson_spacings(n, seed=2)

    if "1" in tests:
        s1 = {
            "zeta_brut": zeta_raw(ords)[:n],
            "zeta_deplie": zeta_unfolded(ords)[:n],
            "gue": gue,
            "poisson": poisson,
            "ar1(phi=0.99)": ar1(n, 0.99, seed=3),
            "sinus+bruit": np.sin(2 * np.pi * np.arange(n) / 37.0)
            + 0.1 * np.random.default_rng(5).standard_normal(n),
        }
        test1_shuffle(s1, args.tau, args.dim, args.n_max, seeds)
    if "2" in tests:
        test2_unfolding(ords, gue, poisson, args.tau, args.dim, args.n_max, seeds)
    if "3" in tests:
        test3_tau_physique(args.dim, args.n_max, seeds, args.gamma, args.temp, args.t_final, args.dt)
    if "4" in tests:
        m = min(len(ords) - 1, n)
        s4 = {"zeta": zeta_raw(ords)[:m], "gue": gue[:m], "poisson": poisson[:m]}
        test4_normalisation(s4, args.tau, args.dim, args.n_max, seeds)

    (OUT_DIR / "resume_tests.txt").write_text("\n".join(SUMMARY), encoding="utf-8")
    print(f"\nRésumé : {(OUT_DIR / 'resume_tests.txt').resolve()}")


if __name__ == "__main__":
    main()
