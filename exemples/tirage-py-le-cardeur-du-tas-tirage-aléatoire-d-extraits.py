#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tirage du jour — cardeur du tas local.

Parcourt un dossier (par défaut ./sources), tire au hasard N extraits
de K lignes chacun, et les écrit dans un fichier « tirage_du_jour.md »
avec, pour chaque extrait, des étiquettes À REMPLIR à la main.

Le tirage est semé par la date : refaire tourner le même jour redonne
le même tirage (pour pouvoir en reparler tranquillement). Le lendemain,
le tas rend d'autres trésors.

Aucune dépendance : bibliothèque standard Python uniquement.
Le résultat est local. Rien ne part sur la toile tant qu'on ne le pousse pas.

Usage :
    python tirage.py                    # tire 5 extraits dans ./sources
    python tirage.py -n 8               # huit extraits
    python tirage.py -d ./mon_tas       # un autre dossier
    python tirage.py --seed 2026-10-04  # rejouer le tirage d'une date
"""

from __future__ import annotations

import argparse
import datetime
import random
import sys
from pathlib import Path

# Fichiers que l'on sait lire en texte. Les .doc/.pdf/images sont ignorés
# (binaires) — ils attendront un passage manuel ou un LLM local plus bavard.
EXTENSIONS_LUES = {".md", ".txt", ".py", ".dat", ".csv", ".json", ".html", ".css", ".js", ".tex"}

# Si un fichier dépasse cette taille (octets), on le saute : trop gros pour
# un extrait honnête.
TAILLE_MAX = 2_000_000


def lire_texte(chemin: Path) -> list[str] | None:
    """Tente de lire un fichier comme texte. Renvoie None si binaire/illisible."""
    try:
        octets = chemin.read_bytes()
    except OSError:
        return None
    if len(octets) > TAILLE_MAX:
        return None
    for encodage in ("utf-8", "latin-1"):
        try:
            texte = octets.decode(encodage)
        except UnicodeDecodeError:
            continue
        lignes = texte.splitlines()
        # Heuristique binaire : trop de caractères de contrôle => on saute.
        suspects = sum(1 for l in lignes[:200] if "\x00" in l)
        if suspects > 2:
            return None
        return lignes
    return None


def extraits_possibles(lignes: list[str], k: int) -> list[tuple[int, list[str]]]:
    """Toutes les fenêtres de k lignes non vides (index de départ, lignes)."""
    fenetres = []
    debut = 0
    while debut + k <= len(lignes):
        morceau = lignes[debut:debut + k]
        if any(ligne.strip() for ligne in morceau):  # au moins une ligne non vide
            fenetres.append((debut, morceau))
        debut += k
    return fenetres


def main() -> None:
    parseur = argparse.ArgumentParser(description="Cardeur : tirage aléatoire d'extraits dans le tas.")
    parseur.add_argument("-d", "--dossier", default="./sources", help="dossier du tas (défaut : ./sources)")
    parseur.add_argument("-n", "--nombre", type=int, default=5, help="nombre d'extraits à tirer")
    parseur.add_argument("-k", "--lignes", type=int, default=7, help="longueur de chaque extrait en lignes")
    parseur.add_argument("--seed", default=None, help="graine du tirage (défaut : la date du jour)")
    args = parseur.parse_args()

    racine = Path(args.dossier)
    if not racine.is_dir():
        print(f"Le dossier {racine} n'existe pas. Rien à carder.", file=sys.stderr)
        sys.exit(1)

    # 1. Ramasser tous les fichiers texte lisibles du tas.
    candidats = []  # (chemin, fenêtre_de_lignes)
    for chemin in sorted(racine.rglob("*")):
        if chemin.suffix.lower() not in EXTENSIONS_LUES or not chemin.is_file():
            continue
        lignes = lire_texte(chemin)
        if not lignes:
            continue
        for debut, morceau in extraits_possibles(lignes, args.lignes):
            candidats.append((chemin, debut, morceau))

    if not candidats:
        print("Aucun fichier texte trouvé. Le tas attend son cardeur.", file=sys.stderr)
        sys.exit(1)

    # 2. Tirer au sort, semé par la date du jour.
    graines = args.seed or datetime.date.today().isoformat()
    tirage = random.Random(graines)
    perdants = tirage.sample(candidats, min(args.nombre, len(candidats)))

    # 3. Écrire le carnet de tirage, étiquettes à remplir à la main.
    sortie = Path("tirage_du_jour.md")
    with sortie.open("w", encoding="utf-8") as f:
        f.write(f"# Tirage du jour — {graines}\n\n")
        f.write(f"{len(candidats)} fenêtres possibles dans {racine}. ")
        f.write(f"Graine : {graines}. Local, privé, rien de poussé.\n\n")
        for i, (chemin, debut, morceau) in enumerate(perdants, 1):
            f.write("---\n\n")
            f.write(f"## Extrait {i}\n\n")
            f.write(f"- **fichier** : {chemin}\n")
            f.write(f"- **lignes** : {debut + 1} à {debut + len(morceau)}\n")
            f.write("- **entrée** : (math / rag / surphin / philo / méso / ?)\n")
            f.write("- **état** : brut / taillé / contextualisé\n")
            f.write("- **où dans l'ensemble** : (une phrase à la main)\n")
            f.write("- **montrable ?** : oui / après taille / jamais\n\n")
            f.write("```text\n")
            f.write("\n".join(morceau).rstrip() + "\n")
            f.write("```\n\n")

    print(f"Tirage écrit : {sortie} — {len(perdants)} extraits, graine {graines}.")
    print("Remplis les étiquettes à la main, puis montre ce qui veut bien se laisser voir.")


if __name__ == "__main__":
    main()