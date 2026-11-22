"""Rejet des surfaces d'options incohérentes."""
import numpy as np
import pandas as pd

from ..config import SEUIL_ECART_VIX, SEUIL_PENTE_SOURIRE


def controle_qualite_surface(indicateurs: pd.DataFrame, diagnostics: pd.DataFrame,
                             vix: pd.Series) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Rejette les surfaces d'options incohérentes, sans les remplacer.

    Deux critères indépendants, calculés avec les données de la même clôture (aucune
    information future), signalent une surface fausse à la date t :

        IV au-dessus du VIX :   σ_t(1 ; 30) − VIX_t > 5 points
        sourire plat        :   σ_t(0,90 ; 30) − σ_t(1 ; 30) < 2 points

    Notations
    ---------
    t               date de la surface
    σ_t(m ; T)      IV de la surface au niveau m = K / S et à T jours calendaires, en %
    VIX_t           clôture du VIX le même jour, en % (volatilité implicite à 30 jours de Cboe)
    5 ; 2           seuils ``SEUIL_ECART_VIX`` et ``SEUIL_PENTE_SOURIRE``, en points de volatilité

    La surface est rejetée si l'un des deux critères est vrai. Le VIX intègre les ailes du
    sourire et dépasse donc normalement l'IV à la monnaie ; sur un marché actions, la pente
    du sourire est nettement positive.

    Sur 2017-2023, ces deux critères isolent exactement les mêmes six séances de mai 2019.

    Paramètres
    ----------
    indicateurs, diagnostics : sorties de ``features.indicateurs_surface``.
    vix : clôtures du VIX.

    Retourne
    --------
    indicateurs_propres : indicateurs où les dates rejetées sont vides (ni copie de la veille,
    ni interpolation) ;
    controle : critères et décision, date par date.
    """
    controle = pd.DataFrame(index=indicateurs.index)
    controle["iv_30j_100spot_pct"] = indicateurs.iv_30j_100spot_pct
    controle["vix"] = vix.reindex(indicateurs.index)
    controle["ecart_iv_vix_points"] = controle.iv_30j_100spot_pct - controle.vix
    controle["pente_sourire_90_points"] = diagnostics.pente_sourire_90_points
    controle["cellules_sous_1pct"] = diagnostics.cellules_sous_1pct
    controle["iv_au_dessus_vix"] = controle.ecart_iv_vix_points > SEUIL_ECART_VIX
    controle["sourire_plat"] = controle.pente_sourire_90_points < SEUIL_PENTE_SOURIRE
    controle["rejetee"] = controle.iv_au_dessus_vix | controle.sourire_plat
    indicateurs_propres = indicateurs.copy()
    indicateurs_propres.loc[controle.rejetee] = np.nan
    return indicateurs_propres, controle
