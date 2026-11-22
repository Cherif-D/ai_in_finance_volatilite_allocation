"""Contrôle de la surface d'options par de vrais contrats (échantillon du second semestre 2022).

Usage, depuis la racine du projet, après ``02_preparation.py`` ::

    .venv\\Scripts\\python.exe scripts/03_controle_surface.py

Fichiers produits :

- ``data/prepare/chaines_spx_2022S2.parquet``        contrats SPX/SPXW, une ligne par contrat et séance ;
- ``data/controles/controle_chaines_et_surfaces.csv`` IV à 30 jours : contrats contre surface ;
- ``data/prepare/termes_indicatifs_2022S2.csv``       prix à terme par parité call-put.
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # rend le paquet importable

from portefeuille import controle_surface, controles, features, pretraitement  # noqa: E402
from portefeuille.config import CONTROLES, ETUDE, PREPARE  # noqa: E402
from portefeuille.utilitaires import ecrire_csv  # noqa: E402


def main() -> None:
    """Compare l'IV recalculée depuis les contrats à la surface, puis estime les prix à terme."""
    surface, diagnostics = features.indicateurs_surface(*pretraitement.charger_grille_surface())
    surface, _ = controles.controle_qualite_surface(surface, diagnostics, pretraitement.charger_indices_cboe().vix)
    surface = surface.loc[surface.index.intersection(ETUDE)]

    chaines = PREPARE / "chaines_spx_2022S2.parquet"
    comparaison = controle_surface.extraire_chaines(chaines).join(surface.iv_30j_100spot_pct)
    # Écart en points de volatilité : IV recalculée depuis les contrats moins IV de la surface.
    comparaison["ecart_points"] = comparaison.iv30_pm_spot_pct - comparaison.iv_30j_100spot_pct
    ecrire_csv(comparaison, CONTROLES / "controle_chaines_et_surfaces.csv")

    taux = pd.read_csv(PREPARE / "taux_bons_tresor.csv", index_col="date", parse_dates=["date"])
    ecrire_csv(controle_surface.estimer_termes(chaines, taux), PREPARE / "termes_indicatifs_2022S2.csv",
               index_label=None)

    print(f"Chaînes SPX/SPXW : {comparaison.contracts.sum():,} lignes, {comparaison.quality_ok.sum():,} valides.")
    print("Écart absolu d'IV à 30 jours entre contrats et surface (points) :")
    print(comparaison.ecart_points.abs().describe().to_string())


if __name__ == "__main__":
    main()
