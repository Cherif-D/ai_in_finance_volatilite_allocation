"""Prépare les données du graphique du document de passation.

Usage, depuis la racine du projet, après ``scripts/02_preparation.py`` ::

    .venv\\Scripts\\python.exe docs/latex/generer_figures.py

Produit ``docs/latex/figures/series_mensuelles.tex`` : les moyennes mensuelles de la cible
σ(s) (volatilité réalisée future du panier 60/40) et du VIX, en %, sous forme de coordonnées
TikZ. Si le classeur Bloomberg privé est présent, produit aussi ``figures/sourire_local.tex`` :
le sourire implicite et le sourire local à 30 jours du 1er juillet 2022 (figure de l'ensemble C). Le mois est repéré par le nombre d'années écoulées depuis janvier 2012 (0 = janvier 2012,
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


def sourire_local() -> None:
    """Écrit le sourire implicite (lissé) et le sourire local à 30 jours du 1er juillet 2022."""
    import sys
    import numpy as np
    sys.path.insert(0, str(RACINE))
    from portefeuille import pretraitement
    from portefeuille.config import BLOOMBERG
    from portefeuille.features import locale
    if not BLOOMBERG.exists():
        print("Classeur Bloomberg absent : figure du sourire local non régénérée")
        return
    niveaux, echeances, dates, cube, dividende = pretraitement.charger_surface_bloomberg()
    taux = pd.read_csv(RACINE / "data/prepare/taux_bons_tresor.csv", index_col="date", parse_dates=["date"])
    i = dates.get_loc(pd.Timestamp("2022-07-01"))
    bons = taux[[b[1] for b in locale.BONS]].reindex(dates, method="ffill").to_numpy()[i]
    r, q = locale.taux_par_echeance(echeances, bons), dividende.iloc[i] / 100
    coefs, _ = locale.lisser_sourires(niveaux, echeances, cube[:, :, i], r, q)
    grille = np.round(np.arange(.92, 1.0801, .005), 3)
    y = np.log(grille) - (r[0] - q) * echeances[0] / 365
    iv = 100 * np.sqrt(np.polyval(coefs[0], y) / (echeances[0] / 365))
    vl = [locale.volatilite_locale(coefs, echeances, r, q, m, 0) for m in grille]
    def points(xs, ys, separateur=" "):
        """Coordonnées TikZ (prix d'exercice en % du cours, volatilité en %)."""
        return separateur.join(f"({100 * x:.1f},{v:.2f})" for x, v in zip(xs, ys))

    # Chaque macro prend le style du trait en argument, comme pour la figure 1.
    lignes = [
        "% Fichier généré par generer_figures.py : ne pas modifier à la main.",
        r"\newcommand{\sourireiv}[1]{\draw[#1] plot coordinates {" + points(grille, iv) + "};}",
        r"\newcommand{\sourirevl}[1]{\draw[#1] plot coordinates {" + points(grille, vl) + "};}",
        r"\newcommand{\pointsbloomberg}[1]{\foreach \p in {" + points(niveaux, cube[:, 0, i], ",")
        + r"} {\fill[#1] \p circle (1.6pt);}}",
    ]
    sortie = SORTIE.parent / "sourire_local.tex"
    sortie.write_text("\n".join(lignes) + "\n", encoding="utf8")
    print(f"{sortie.name} : sourire local de {min(vl):.1f} à {max(vl):.1f} %")


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
    sourire_local()
