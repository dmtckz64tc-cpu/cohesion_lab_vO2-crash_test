#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Diagnostic topologico-computationnel du plongement de Takens.

Calcule les rapports de densité (alpha_obs, alpha_monde, kappa, rho) et estime
la RAM nécessaire pour une configuration (d, tau, n_max, n_max_full, downsample).

Usage:
    # Diagnostic d'une configuration planifiée
    python surphin_takens_diagnostic.py --signal-length 50000 --d 3 --tau 10 \\
        --downsample 5 --n-max 400 --n-max-full 2000

    # Recherche automatique du sweet spot sous une limite RAM
    python surphin_takens_diagnostic.py --signal-length 50000 --d 3 --tau 10 \\
        --find-sweet-spot --max-ram-gb 8

    # Balaie plusieurs dimensions
    python surphin_takens_diagnostic.py --signal-length 50000 \\
        --dimensions 2 3 4 --tau 10 --find-sweet-spot --max-ram-gb 16
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path
from typing import Sequence

import numpy as np


# ---------------------------------------------------------------------------
# Constantes physiques du nuage
# ---------------------------------------------------------------------------
BYTES_PER_FLOAT64 = 8
# pdist produit un vecteur de taille N*(N-1)/2 ; on estime la RAM
# comme ce vecteur + une marge pour la matrice carree interne (x2.5)
RAM_MARGIN_FACTOR = 2.5


def estimate_ram_gb(n_max_full: int) -> float:
    """Estime la RAM en Go pour pdist sur n_max_full points."""
    n_pairs = n_max_full * (n_max_full - 1) // 2
    bytes_total = n_pairs * BYTES_PER_FLOAT64 * RAM_MARGIN_FACTOR
    return bytes_total / (1024**3)


def compute_ratios(
    signal_length: int,
    d: int,
    tau: int,
    downsample: int,
    n_max: int,
    n_max_full: int | None,
) -> dict[str, float | int | bool | None]:
    """Calcule tous les rapports topologico-computationnels."""

    # Profondeurs temporelles
    P = (d - 1) * tau  # profondeur effective (en échantillons downsampled)
    P_brut = P * downsample  # profondeur brute (en échantillons originaux)

    # Densités
    alpha_obs = n_max / P if P > 0 else float("inf")  # densité observateur

    # Taille max théorique du nuage après downsample
    N_down = signal_length // downsample
    n_max_full_max = N_down - P

    if n_max_full is None:
        n_max_full = max(1000, min(n_max_full_max, 5000))

    alpha_monde = n_max_full / P_brut if P_brut > 0 else float("inf")

    # Taux de compression
    kappa = (n_max / n_max_full) * downsample if n_max_full > 0 else float("inf")

    # Densité topologique
    rho = n_max_full / P_brut if P_brut > 0 else float("inf")

    # RAM
    ram_gb = estimate_ram_gb(n_max_full)

    # Faisabilité
    feasible = n_max_full <= n_max_full_max and n_max_full >= n_max

    return {
        "d": d,
        "tau": tau,
        "downsample": downsample,
        "signal_length": signal_length,
        "N_down": N_down,
        "P": P,
        "P_brut": P_brut,
        "n_max": n_max,
        "n_max_full": n_max_full,
        "n_max_full_max": n_max_full_max,
        "alpha_obs": alpha_obs,
        "alpha_monde": alpha_monde,
        "kappa": kappa,
        "rho": rho,
        "ram_gb": ram_gb,
        "feasible": feasible,
    }


def format_diagnostic(r: dict) -> str:
    """Retourne un rapport lisible."""
    lines = [
        "=" * 60,
        "DIAGNOSTIC TAKENS — SurPhiN",
        "=" * 60,
        f"Configuration      : d={r['d']}, tau={r['tau']}, downsample={r['downsample']}",
        f"Signal brut        : {r['signal_length']:,} pts",
        f"Signal downsampled : {r['N_down']:,} pts",
        "",
        "--- Profondeurs temporelles ---",
        f"P (effective)      : {r['P']:,} échantillons",
        f"P_brut (originaux) : {r['P_brut']:,} échantillons",
        "",
        "--- Surfaces ---",
        f"n_max (observateur): {r['n_max']:,}",
        f"n_max_full (monde) : {r['n_max_full']:,} (max possible: {r['n_max_full_max']:,})",
        "",
        "--- Ratios topologiques ---",
        f"alpha_obs  (densité observateur) : {r['alpha_obs']:.3f}",
        f"alpha_monde(densité monde)       : {r['alpha_monde']:.3f}",
        f"kappa (taux compression)           : {r['kappa']:.3f}",
        f"rho   (densité topologique)      : {r['rho']:.3f}",
        "",
        "--- Coût computationnel ---",
        f"RAM estimée (pdist) : {r['ram_gb']:.2f} Go",
        f"Faisable            : {'OUI' if r['feasible'] else 'NON'}",
        "=" * 60,
    ]
    return "\n".join(lines)


def find_sweet_spot(
    signal_length: int,
    d: int,
    tau: int,
    max_ram_gb: float,
    n_max: int = 400,
    downsample_candidates: Sequence[int] | None = None,
) -> list[dict]:
    """Balaie les downsamples pour trouver la meilleure densité rho faisable."""
    if downsample_candidates is None:
        downsample_candidates = [1, 2, 5, 10, 20, 50]

    results = []
    for D in downsample_candidates:
        N_down = signal_length // D
        P = (d - 1) * tau
        n_max_full_max = N_down - P

        if n_max_full_max < n_max:
            continue  # Impossible : le nuage de référence serait plus petit que l'observateur

        # On cherche le plus grand n_max_full faisable sous la limite RAM
        # Par dichotomie grossière
        candidates = []
        for nmf in [500, 1000, 2000, 3000, 4000, 5000, 7500, 10000, 15000, 20000]:
            if nmf <= n_max_full_max and estimate_ram_gb(nmf) <= max_ram_gb:
                candidates.append(nmf)

        if not candidates:
            continue

        best_nmf = max(candidates)
        r = compute_ratios(signal_length, d, tau, D, n_max, best_nmf)
        results.append(r)

    # Trie par rho décroissant
    results.sort(key=lambda x: x["rho"], reverse=True)
    return results


def format_sweet_spot(results: list[dict], max_ram_gb: float) -> str:
    if not results:
        return f"Aucune configuration faisable sous {max_ram_gb} Go de RAM."

    lines = [
        "=" * 70,
        f"SWEET SPOT — Top {len(results)} configurations (RAM < {max_ram_gb} Go)",
        "=" * 70,
        f"{'D':>3} {'tau':>4} {'DS':>4} {'n_max':>7} {'n_full':>7} {'rho':>8} {'kappa':>7} {'RAM_GB':>7} {'feas':>5}",
        "-" * 70,
    ]
    for r in results:
        lines.append(
            f"{r['d']:>3} {r['tau']:>4} {r['downsample']:>4} "
            f"{r['n_max']:>7,} {r['n_max_full']:>7,} "
            f"{r['rho']:>8.2f} {r['kappa']:>7.3f} "
            f"{r['ram_gb']:>7.2f} {'OUI' if r['feasible'] else 'NON':>5}"
        )
    lines.append("=" * 70)
    lines.append("rho = densité topologique (plus haut = meilleure convergence)")
    lines.append("kappa = taux de compression (plus proche de 1 = observateur représentatif)")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--signal-length", type=int, required=True,
                        help="Longueur du signal brut (nombre d'échantillons).")
    parser.add_argument("--d", type=int, default=3, help="Dimension du plongement (défaut: 3).")
    parser.add_argument("--tau", type=int, default=20, help="Retard Takens (défaut: 20).")
    parser.add_argument("--downsample", type=int, default=1, help="Facteur de sous-échantillonnage.")
    parser.add_argument("--n-max", type=int, default=400, help="Taille du nuage observateur.")
    parser.add_argument("--n-max-full", type=int, default=None,
                        help="Taille du nuage de référence (défaut: auto).")
    parser.add_argument("--find-sweet-spot", action="store_true",
                        help="Balaie les downsamples pour trouver le meilleur compromis.")
    parser.add_argument("--max-ram-gb", type=float, default=8.0,
                        help="Limite RAM en Go pour le sweet spot (défaut: 8).")
    parser.add_argument("--dimensions", type=int, nargs="+", default=None,
                        help="Plusieurs dimensions à tester avec --find-sweet-spot.")
    parser.add_argument("--csv", type=Path, default=None,
                        help="Chemin CSV de sortie (optionnel).")
    args = parser.parse_args(argv)

    if args.find_sweet_spot:
        dimensions = args.dimensions or [args.d]
        all_results = []
        for d in dimensions:
            results = find_sweet_spot(
                signal_length=args.signal_length,
                d=d,
                tau=args.tau,
                max_ram_gb=args.max_ram_gb,
                n_max=args.n_max,
            )
            all_results.extend(results)
            print(f"\n--- Dimension d={d} ---")
            print(format_sweet_spot(results, args.max_ram_gb))

        if args.csv:
            import csv
            args.csv.parent.mkdir(parents=True, exist_ok=True)
            with open(args.csv, "w", newline="", encoding="utf-8") as f:
                if all_results:
                    writer = csv.DictWriter(f, fieldnames=[
                        "d", "tau", "downsample", "signal_length", "n_max",
                        "n_max_full", "rho", "kappa", "alpha_obs", "alpha_monde",
                        "ram_gb", "feasible"
                    ])
                    writer.writeheader()
                    for r in all_results:
                        writer.writerow({k: r[k] for k in writer.fieldnames})
            print(f"\nCSV écrit : {args.csv}")
    else:
        r = compute_ratios(
            signal_length=args.signal_length,
            d=args.d,
            tau=args.tau,
            downsample=args.downsample,
            n_max=args.n_max,
            n_max_full=args.n_max_full,
        )
        print(format_diagnostic(r))

        if args.csv:
            import csv
            args.csv.parent.mkdir(parents=True, exist_ok=True)
            with open(args.csv, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=[
                    "d", "tau", "downsample", "signal_length", "n_max",
                    "n_max_full", "rho", "kappa", "alpha_obs", "alpha_monde",
                    "ram_gb", "feasible"
                ])
                writer.writeheader()
                writer.writerow({k: r[k] for k in writer.fieldnames})
            print(f"CSV écrit : {args.csv}")


if __name__ == "__main__":
    main()
