"""Variables historiques A : ce que le passé du panier dit de son risque."""
import numpy as np
import pandas as pd

from ..config import FENETRES, FENETRES_PANIER, POIDS_IEF, POIDS_SPY, SEANCES_PAR_AN


def variables_historiques(prix: pd.DataFrame) -> pd.DataFrame:
    """Calcule les 13 variables historiques A, chaque fenêtre se terminant à la date de la ligne.

    Rendement approché du panier, remis à 60/40 chaque jour (simplification pour décrire le
    passé ; la cible, elle, laisse dériver les poids) :

        q(u) = 0,6 · r_SPY(u) + 0,4 · r_IEF(u)

    Pour une série z et une fenêtre de L séances se terminant à la date t :

        moyenne         z̄(t,L) = 1/L · Σ_{k=0…L−1} z(t−k)

        variance        v(t,L) = 252/(L−1) · Σ_{k=0…L−1} [ z(t−k) − z̄(t,L) ]²

        rendement       R(t,L) = Π_{k=0…L−1} [ 1 + z(t−k) ] − 1

        semi-variance   d(t,L) = 252/L · Σ_{k=0…L−1} z(t−k)² · 1[ z(t−k) < 0 ]

                                  Σ_k (s_k − s̄)(i_k − ī)
        corrélation     ρ(t,L) = ─────────────────────────────── ,  s = r_SPY, i = r_IEF
                                  √[ Σ_k (s_k − s̄)² · Σ_k (i_k − ī)² ]

    Notations
    ---------
    t           date de la ligne : séance de clôture à laquelle la variable est connue
    u           séance quelconque
    L           longueur de la fenêtre, en séances (5, 21 ou 63)
    k           position dans la fenêtre : t−k parcourt les L séances de t−L+1 à t
    r_SPY(u)    rendement quotidien de SPY en u (prix ajustés), en décimal
    r_IEF(u)    rendement quotidien d'IEF en u, en décimal
    q(u)        rendement quotidien du panier 60/40 remis à poids fixes, en décimal
    z           série étudiée (q, r_SPY ou r_IEF selon la variable)
    z̄(t,L)      moyenne de z sur la fenêtre
    252         nombre conventionnel de séances par an (annualisation des variances)
    1[ · ]      indicatrice : vaut 1 si la condition est vraie, 0 sinon
    s_k, i_k    rendements de SPY et d'IEF à la séance t−k ; s̄, ī leurs moyennes sur la fenêtre
    v, d        variance et semi-variance annualisées, en décimal (0,04 = variance de 4 %)
    R           rendement cumulé sur la fenêtre, en décimal
    ρ           corrélation de Pearson, entre −1 et +1

    Paramètres
    ----------
    prix : sortie de ``pretraitement.charger_prix`` (colonnes ``spy_return``, ``ief_return``).

    Retourne
    --------
    - ``var_panier_L``     = v(t,L) appliquée à q, pour L ∈ {5, 21, 63} ;
    - ``var_spy_L``        = v(t,L) appliquée à r_SPY, pour L ∈ {21, 63} ;
    - ``var_ief_L``        = v(t,L) appliquée à r_IEF, pour L ∈ {21, 63} ;
    - ``rend_panier_L``    = R(t,L) appliquée à q, pour L ∈ {21, 63} ;
    - ``semivar_baisse_L`` = d(t,L) appliquée à q, pour L ∈ {21, 63} ;
    - ``corr_spy_ief_L``   = ρ(t,L), pour L ∈ {21, 63}.
    """
    spy, ief = prix.spy_return, prix.ief_return
    panier = POIDS_SPY * spy + POIDS_IEF * ief
    a = pd.DataFrame(index=prix.index)
    for h in FENETRES_PANIER:
        a[f"var_panier_{h}"] = SEANCES_PAR_AN * panier.rolling(h).var()  # v(t,L) de q ; var() divise par L−1
    for h in FENETRES:
        a[f"var_spy_{h}"] = SEANCES_PAR_AN * spy.rolling(h).var()        # v(t,L) de r_SPY
        a[f"var_ief_{h}"] = SEANCES_PAR_AN * ief.rolling(h).var()        # v(t,L) de r_IEF
        # R(t,L) = Π (1 + q) − 1 : deux hausses de 1 % donnent 1,01 × 1,01 − 1 = +2,01 %.
        a[f"rend_panier_{h}"] = (1 + panier).rolling(h).apply(np.prod, raw=True) - 1
        # d(t,L) = 252/L · Σ q² · 1[q < 0] : baisses seules au numérateur, moyenne sur toute la fenêtre.
        a[f"semivar_baisse_{h}"] = SEANCES_PAR_AN * panier.clip(upper=0).pow(2).rolling(h).mean()
        a[f"corr_spy_ief_{h}"] = spy.rolling(h).corr(ief)                # ρ(t,L)
    return a
