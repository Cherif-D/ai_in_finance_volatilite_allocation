"""Prépare les données du graphique du document de passation.

Usage, depuis la racine du projet, après ``scripts/02_preparation.py`` ::

    .venv\\Scripts\\python.exe docs/latex/generer_figures.py

Produit ``docs/latex/figures/series_mensuelles.tex`` : les moyennes mensuelles de la cible
σ(s) (volatilité réalisée future du panier 60/40) et du VIX, en %, sous forme de coordonnées
TikZ. Le mois est repéré par le nombre d'années écoulées depuis janvier 2012 (0 = janvier 2012,
1,5 = juillet 2013) : TeX ne sait pas tracer des abscisses de l'ordre de 2 000 cm.
"""
from pathlib import Path

import pandas as pd

RACINE = Path(__file__).resolve().parents[2]
SORTIE = Path(__file__).resolve().parent / "figures" / "series_mensuelles.tex"


def coordonnees(serie: pd.Series) -> str:
    """Formate une série mensuelle en points TikZ ``(années depuis janvier 2012, valeur)``."""
    points = [f"({d.year - 2012 + (d.month - 1) / 12:.4f},{v:.2f})" for d, v in serie.dropna().items()]
    return " ".join(points)


def main() -> None:
    """Calcule les moyennes mensuelles et écrit deux macros TikZ."""
    quotidien = pd.read_csv(RACINE / "data/prepare/donnees_quotidiennes.csv", index_col=0, parse_dates=True)
    cible = pd.read_csv(RACINE / "data/prepare/cibles_futures.csv", index_col=0, parse_dates=True)
    cible_mensuelle = (100 * cible.vol_21j_ann).resample("MS").mean()
    vix_mensuel = quotidien.vix.resample("MS").mean()
    SORTIE.parent.mkdir(exist_ok=True)
    # Chaque macro prend le style du trait en argument : \tracecible{teal, thick}.
    SORTIE.write_text(
        "% Fichier généré par generer_figures.py : ne pas modifier à la main.\n"
        f"\\newcommand{{\\tracecible}}[1]{{\\draw[#1] plot coordinates {{{coordonnees(cible_mensuelle)}}};}}\n"
        f"\\newcommand{{\\tracevix}}[1]{{\\draw[#1] plot coordinates {{{coordonnees(vix_mensuel)}}};}}\n",
        encoding="utf8")
    print(f"{SORTIE.name} : {cible_mensuelle.notna().sum()} mois (cible), {vix_mensuel.notna().sum()} mois (VIX)")
    print("maximum mensuel : cible", cible_mensuelle.max().round(1), "% ; VIX", vix_mensuel.max().round(1), "%")


if __name__ == "__main__":
    main()
