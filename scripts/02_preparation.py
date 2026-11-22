"""Étapes 3 et 4 : prétraitement des sources et construction des variables.

Usage, depuis la racine du projet, après ``01_collecte.py`` ::

    .venv\\Scripts\\python.exe scripts/02_preparation.py

Fichiers produits dans ``data/prepare/`` :

- ``prix_etf_et_spx.csv``      prix, distributions et rendements de SPY, IEF et SPX ;
- ``taux_bons_tresor.csv``     taux des T-bills ;
- ``donnees_quotidiennes.csv`` toutes les sources jointes sur les séances 2012-2025 ;
- ``variables_A.csv``          13 variables historiques (connues à la date de la ligne) ;
- ``cibles_futures.csv``       cible de volatilité à 21 séances (inconnue à la date de la ligne).

Fichiers produits dans ``data/controles/`` : couverture des sources, écarts de calendrier,
contrôle des émetteurs et contrôle de qualité de la surface.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # rend le paquet importable

from portefeuille import controles, features, pretraitement  # noqa: E402
from portefeuille.config import CONTROLES, DIFFUSION_VIX9D_VIX6M, ETUDE, PREPARE  # noqa: E402
from portefeuille.utilitaires import ecrire_csv  # noqa: E402


def main() -> None:
    """Enchaîne lecture, contrôles, jointure et construction des variables."""
    for dossier in (PREPARE, CONTROLES):
        dossier.mkdir(parents=True, exist_ok=True)

    # ---- Étape 3 : lecture et validation de chaque source ----
    prix = pretraitement.charger_prix()
    indices = pretraitement.charger_indices_cboe()
    taux = pretraitement.charger_taux_tresor()
    cash = pretraitement.charger_cash_french()
    hamidieh = pretraitement.charger_hamidieh()
    surface_brute, diagnostics = features.indicateurs_surface(*pretraitement.charger_grille_surface())
    surface, controle_surface = controles.controle_qualite_surface(surface_brute, diagnostics, indices.vix)

    ecrire_csv(controle_surface, CONTROLES / "controle_qualite_surface.csv")
    ecrire_csv(prix, PREPARE / "prix_etf_et_spx.csv")
    ecrire_csv(taux, PREPARE / "taux_bons_tresor.csv")

    # Couverture : on décrit chaque source telle que livrée, avant nos propres rejets.
    couverture, ecarts = controles.couverture_calendrier(
        [("ETF", prix.spy_close), *indices.items(), ("surfaces", surface_brute.iloc[:, 0]),
         ("hamidieh", hamidieh.mean_skew), ("Treasury_4s", taux.tbill_4w_investment_pct),
         ("cash_RF", cash)], ETUDE)
    ecrire_csv(couverture, CONTROLES / "couverture.csv", index_label=None)
    ecrire_csv(ecarts, CONTROLES / "ecarts_calendrier.csv", index_label=None)

    # Jointure sur le calendrier des ETF : une source absente un jour laisse une case vide.
    surface = surface.loc[surface.index.intersection(ETUDE)]
    # Deux mesures du cash : RF de French (arrondi à 0,01 %/jour, conservé pour comparaison)
    # et le T-bill 4 semaines du Trésor (précis, à utiliser pour le portefeuille).
    cash_tbill = pretraitement.rendement_cash_tbill(taux, prix.index)
    quotidien = (prix.join(indices).join(surface).join(cash).join(cash_tbill)
                 .join(hamidieh[["mean_skew", "mean_normalized_straddle_price"]].add_prefix("hamidieh_")))
    # Avant le 27/11/2013, VIX9D et VIX6M sont rétropolés : ce drapeau permet de les exclure.
    quotidien["vix9d_vix6m_diffuses"] = quotidien.index >= DIFFUSION_VIX9D_VIX6M
    ecrire_csv(quotidien.reindex(ETUDE), PREPARE / "donnees_quotidiennes.csv")
    ecrire_csv(controles.controle_emetteurs(prix, pretraitement.charger_emetteurs(), ETUDE),
               CONTROLES / "controle_emetteurs.csv")

    # ---- Étape 4 : variables historiques A et cible ----
    ecrire_csv(features.variables_historiques(prix).reindex(ETUDE), PREPARE / "variables_A.csv")
    ecrire_csv(features.cible_future(prix).reindex(ETUDE), PREPARE / "cibles_futures.csv")

    print(couverture.to_string(index=False))
    print(f"Surfaces rejetées : {int(controle_surface.rejetee.sum())}")


if __name__ == "__main__":
    main()
