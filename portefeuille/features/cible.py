"""Cible de prévision : risque réalisé du panier sur les 21 séances suivant l'exécution."""
import numpy as np
import pandas as pd

from ..config import HORIZON, POIDS_IEF, POIDS_SPY, SEANCES_PAR_AN


def cible_future(prix: pd.DataFrame) -> pd.DataFrame:
    """Calcule, pour chaque séance de signal ``s``, le risque réalisé des 21 séances suivantes.

    Le panier est acheté à la clôture s+1 (valeur 1, poids 60/40), puis les poids évoluent
    librement avec les prix ajustés P :

                         P_SPY(u)              P_IEF(u)
        B(s,u) = 0,6 · ──────────── + 0,4 · ────────────          b(s,u) = B(s,u) / B(s,u−1) − 1
                        P_SPY(s+1)            P_IEF(s+1)

                252
        y(s) = ───── · Σ_{j=2…22} b(s, s+j)²          σ(s) = √y(s)
                 21

    Notations
    ---------
    s           séance du signal (date de la ligne) ; s+1 est la séance suivante, etc.
    u           séance quelconque de la période de détention, de s+1 à s+22
    j           décalage en séances depuis le signal (j = 2 pour le premier rendement)
    P_SPY(u)    clôture ajustée de SPY à la séance u (distributions réinvesties), en $
    P_IEF(u)    clôture ajustée d'IEF à la séance u, en $
    0,6 ; 0,4   poids initiaux de SPY et d'IEF dans le panier (``POIDS_SPY``, ``POIDS_IEF``)
    B(s,u)      valeur en u d'un panier valant 1 $ à l'achat en s+1 (B(s,s+1) = 1)
    b(s,u)      rendement quotidien de ce panier entre u−1 et u, en décimal
    252         nombre conventionnel de séances par an (``SEANCES_PAR_AN``)
    21          nombre de rendements dans la cible (``HORIZON``)
    y(s)        cible de variance annualisée, en décimal (0,01 = variance de 1 %)
    σ(s)        cible de volatilité annualisée, en décimal (0,10 = 10 %)

    y(s) est un second moment non centré : il approche la variance car le rendement moyen
    quotidien est presque nul. Les 22 dernières séances de l'historique restent vides.

    Paramètres
    ----------
    prix : sortie de ``pretraitement.charger_prix`` (colonnes ``spy_adj``, ``ief_adj``).

    Retourne
    --------
    ``execution`` (séance s+1), ``fin_cible`` (séance s+22, utile pour purger les
    observations aux frontières des échantillons), ``variance_21j_ann`` = y(s) et
    ``vol_21j_ann`` = σ(s).
    """
    calendrier = pd.Series(prix.index, index=prix.index)
    cible = pd.DataFrame(dict(execution=calendrier.shift(-1), fin_cible=calendrier.shift(-(HORIZON + 1))))
    base_spy, base_ief = prix.spy_adj.shift(-1), prix.ief_adj.shift(-1)
    precedent = 1.
    somme_carres = pd.Series(0., index=prix.index)
    for j in range(2, HORIZON + 2):
        # B(s, s+j) : chaque poche vaut sa mise initiale fois la variation de son prix depuis s+1.
        valeur = POIDS_SPY * prix.spy_adj.shift(-j) / base_spy + POIDS_IEF * prix.ief_adj.shift(-j) / base_ief
        somme_carres += (valeur / precedent - 1) ** 2  # b(s, s+j)²
        precedent = valeur
    cible["variance_21j_ann"] = somme_carres * SEANCES_PAR_AN / HORIZON  # y(s) = 252/21 · Σ b²
    cible["vol_21j_ann"] = np.sqrt(cible.variance_21j_ann)
    return cible
