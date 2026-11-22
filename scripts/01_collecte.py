"""Étape 1 : télécharge les 29 sources brutes dans ``data/brut/``.

Usage, depuis la racine du projet ::

    .venv\\Scripts\\python.exe scripts/01_collecte.py

Un fichier déjà présent et conforme à sa fiche (même adresse, même empreinte) n'est pas
téléchargé de nouveau. L'inventaire complet est écrit dans ``data/sources.json``.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # rend le paquet importable

from portefeuille.collecte import collecter_tout  # noqa: E402

if __name__ == "__main__":
    fiches = collecter_tout()
    print(f"{len(fiches)} sources disponibles dans data/brut/.")
