"""Ensembles B et C à partir de la surface Bloomberg du SPX (2011-2025).

Usage, depuis la racine du projet, après ``02_preparation.py`` et une fois les classeurs
privés placés dans ``data/brut/bloomberg/`` ::

    .venv\\Scripts\\python.exe scripts/04_surface_bloomberg.py

Fichiers produits (dérivés de Bloomberg, donc exclus du dépôt public) :

- ``data/prepare/variables_B.csv``                      les 8 indicateurs implicites B, 2012-2025 ;
- ``data/prepare/variables_C.csv``                      les 8 variables de volatilité locale C ;
- ``data/controles/controle_qualite_surface_bloomberg.csv`` contrôle de B (mêmes règles que la
  surface universitaire) et écart avec celle-ci sur 2017-2023 ;
- ``data/controles/controle_volatilite_locale.csv``     lissage, arbitrages, taux, dividende ;
- ``data/controles/controle_lissage_chaine.csv``        si le second classeur est présent :
  volatilité locale tirée de 5 points contre celle d'une chaîne complète d'options ;
- ``data/controles/controle_contrats_bloomberg.csv``    si le classeur des options expirées est
  présent : IV de vraies options SPX (2015-2025) contre la surface Bloomberg.

Une journée rejetée par l'un des deux contrôles (B ou C) est vidée dans les deux fichiers :
B et C viennent de la même surface.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # rend le paquet importable

from portefeuille import controle_surface, controles, features, pretraitement  # noqa: E402
from portefeuille.config import (BLOOMBERG_COMPLEMENTS, BLOOMBERG_OPTIONS, CONTROLES,  # noqa: E402
                                 DATE_CHAINE_BLOOMBERG, ETUDE, PREPARE)
from portefeuille.utilitaires import ecrire_csv  # noqa: E402


def main() -> None:
    """Calcule B et C sur la grille Bloomberg, applique les contrôles et écrit les fichiers."""
    niveaux, echeances, dates, cube, dividende = pretraitement.charger_surface_bloomberg()
    quotidien = pd.read_csv(PREPARE / "donnees_quotidiennes.csv", index_col="date", parse_dates=["date"])
    taux = pd.read_csv(PREPARE / "taux_bons_tresor.csv", index_col="date", parse_dates=["date"])

    # B : mêmes fonctions et mêmes règles de rejet que pour la surface universitaire.
    b_brut, diagnostics_b = features.indicateurs_surface(niveaux, echeances, dates, cube)
    _, controle_b = controles.controle_qualite_surface(b_brut, diagnostics_b, quotidien.vix)
    # C : volatilité locale de Dupire, avec son propre rejet (arbitrage).
    c_brut, diagnostics_c = features.variables_locales(niveaux, echeances, dates, cube, dividende, taux)

    # Une journée douteuse pour l'un est douteuse pour l'autre : même surface.
    rejet = controle_b.rejetee | diagnostics_c.rejetee
    variables_b, variables_c = b_brut.copy(), c_brut.copy()
    variables_b.loc[rejet] = np.nan
    variables_c.loc[rejet] = np.nan
    controle_b["rejetee_par_c"] = diagnostics_c.rejetee
    controle_b["rejetee_finale"] = rejet
    diagnostics_c["rejetee_finale"] = rejet
    # Recoupement avec la surface universitaire (2017-2023) : même point, deux sources.
    controle_b["ecart_iv30_100_vs_universitaire_points"] = (b_brut.iv_30j_100spot_pct
                                                           - quotidien.iv_30j_100spot_pct.reindex(dates))

    ecrire_csv(variables_b.reindex(ETUDE), PREPARE / "variables_B.csv")
    ecrire_csv(variables_c.reindex(ETUDE), PREPARE / "variables_C.csv")
    ecrire_csv(controle_b.reindex(ETUDE), CONTROLES / "controle_qualite_surface_bloomberg.csv")
    ecrire_csv(diagnostics_c.reindex(ETUDE), CONTROLES / "controle_volatilite_locale.csv")

    etude = rejet.reindex(ETUDE)
    print(f"Séances : {len(etude)} ; rejetées : {list(etude.index[etude].date)}")
    print(f"Écart médian absolu avec la surface universitaire (IV 30 j au cours) : "
          f"{controle_b.ecart_iv30_100_vs_universitaire_points.abs().median():.2f} point")
    print(f"Écart de lissage maximal (C) : {diagnostics_c.ecart_lissage_max_points.reindex(ETUDE).max():.2f} point (2012-2025)")
    print(variables_b.reindex(ETUDE).describe().round(2).T[["count", "50%", "min", "max"]].to_string())
    print(variables_c.reindex(ETUDE).describe().round(2).T[["count", "50%", "min", "max"]].to_string())

    # Test du lissage sur la chaîne complète d'une séance (second classeur, facultatif).
    if BLOOMBERG_COMPLEMENTS.exists():
        sourires = controle_surface.sourires_chaine(pretraitement.charger_chaine_bloomberg(), DATE_CHAINE_BLOOMBERG)
        test = controle_surface.comparer_lissage(sourires)
        ecrire_csv(test, CONTROLES / "controle_lissage_chaine.csv", index_label=None)
        print("Volatilité locale : 5 points lissés contre chaîne complète (points de volatilité)")
        print(test.round(2).to_string(index=False))

    # Contrôle de la surface par de vraies options expirées (quatrième classeur, facultatif).
    if BLOOMBERG_OPTIONS.exists():
        spx = pd.read_csv(PREPARE / "prix_etf_et_spx.csv", index_col="date", parse_dates=["date"]).spx_close
        contrats = controle_surface.comparer_contrats_surface(controle_surface.charger_options_expirees(), spx, taux,
                                                             niveaux, echeances, dates, cube, dividende)
        ecrire_csv(contrats, CONTROLES / "controle_contrats_bloomberg.csv", index_label=None)
        hors = contrats[contrats.hors_monnaie].ecart_points
        print(f"Options expirées : {len(contrats)} cotations comparées, dont {len(hors)} hors de la monnaie ; "
              f"écart médian {hors.median():+.2f}, absolu médian {hors.abs().median():.2f}, "
              f"95e centile absolu {hors.abs().quantile(.95):.2f} point")


if __name__ == "__main__":
    main()
