"""Indicateurs implicites B tirés de la surface de volatilité des options SPX."""
import numpy as np
import pandas as pd

from ..config import ECHEANCES_SURFACE, NIVEAUX_SURFACE


def interpoler_echeance(jours: np.ndarray, iv_pct: np.ndarray, horizon: float) -> float:
    """Interpole une IV à une échéance donnée, à prix d'exercice relatif fixé.

    On interpole linéairement la variance totale w(T) = σ(T)² · T entre les deux échéances
    voisines T₁ ≤ T* ≤ T₂, puis on revient à une volatilité :

                                T* − T₁
        w(T*) = w(T₁) + ─────────── · [ w(T₂) − w(T₁) ]          σ(T*) = √( w(T*) / T* )
                                T₂ − T₁

    Notations
    ---------
    T*          échéance recherchée, en jours calendaires (30 ou 60)
    T₁, T₂      échéances de la grille qui encadrent T* (T₁ ≤ T* ≤ T₂)
    σ(T)        volatilité implicite à l'échéance T, en % annuel
    w(T)        variance totale σ(T)² · T : elle croît avec T si la surface est cohérente

    Aucune extrapolation : si T* n'est pas encadré par les échéances disponibles, le
    résultat est manquant.

    Paramètres
    ----------
    jours : échéances disponibles, en jours calendaires, croissantes.
    iv_pct : IV correspondantes, en pourcentage.
    horizon : échéance cible en jours calendaires.
    """
    if len(jours) == 0 or not jours[0] <= horizon <= jours[-1]:
        return np.nan
    return np.sqrt(np.interp(horizon, jours, np.square(iv_pct) * jours) / horizon)


def _variance_au_niveau(niveaux: np.ndarray, cube: np.ndarray, niveau: float) -> np.ndarray:
    """Interpole linéairement σ² entre les deux niveaux de la grille qui encadrent ``niveau``.

    Avec m = K / S le prix d'exercice rapporté au spot, et m₁ ≤ m* < m₂ :

             m* − m₁
        λ = ─────────          σ²(m*, T) = (1 − λ) · σ²(m₁, T) + λ · σ²(m₂, T)
             m₂ − m₁

    Notations
    ---------
    K           prix d'exercice (strike) de l'option, en points d'indice
    S           niveau du SPX le jour de l'observation (spot), en points d'indice
    m*          niveau recherché (0,90 ; 0,95 ; 1 ou 1,05)
    m₁, m₂      niveaux de la grille qui encadrent m*
    λ           poids d'interpolation, entre 0 et 1
    σ²(m, T)    carré de l'IV au niveau m et à l'échéance T (IV en %)

    Retourne un tableau échéance × date de variances (IV en pourcentage, au carré).
    """
    haut = niveaux.searchsorted(niveau)
    poids = (niveau - niveaux[haut - 1]) / (niveaux[haut] - niveaux[haut - 1])
    return (1 - poids) * cube[haut - 1].astype(float) ** 2 + poids * cube[haut].astype(float) ** 2


def indicateurs_surface(niveaux: np.ndarray, echeances: np.ndarray, dates: pd.DatetimeIndex,
                        cube: np.ndarray) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Calcule les indicateurs implicites B à partir de la grille de surface, date par date.

    Chaque date est traitée isolément : aucune information d'une autre journée n'intervient.
    Le prix d'exercice est rapporté au **spot**, m = K / S (0,95 = 95 % du SPX du jour), et
    non au prix à terme, k = ln(K / F) ; à 30 et 60 jours la différence est faible, mais
    c'est une convention à citer. Avec σ(m ; T) l'IV au niveau m et à T jours :

        skew_30j        = σ(0,95 ; 30) − σ(1 ; 30)      en points de volatilité
        pente_60j_30j   = σ(1 ; 60)    − σ(1 ; 30)      en points de volatilité

    Notations
    ---------
    K, S        prix d'exercice et niveau du SPX du jour ; m = K / S
    F           prix à terme du SPX pour l'échéance considérée (non utilisé ici)
    σ(m ; T)    IV au niveau m et à l'échéance T (jours calendaires), en % annuel
    skew_30j    surcoût des puts 5 % sous le spot : prime de protection contre la baisse
    pente       structure par terme : positive en temps calme, négative en crise

    Paramètres
    ----------
    Sortie de ``pretraitement.charger_grille_surface``.

    Retourne
    --------
    indicateurs :
        ``iv_{30,60}j_{95,100,105}spot_pct`` (IV en %), ``skew_30j_points``
        (IV 95 % - IV 100 % à 30 jours) et ``pente_60j_30j_points`` (IV 60 j - IV 30 j à la
        monnaie), en points de volatilité.
    diagnostics :
        ``pente_sourire_90_points`` (IV 90 % - IV 100 % à 30 jours, contrôle de forme) et
        ``cellules_sous_1pct`` (nombre de cellules de la grille sous 1 %, aberrantes).
    """
    indicateurs = pd.DataFrame(index=dates)
    for horizon in ECHEANCES_SURFACE:
        for niveau in NIVEAUX_SURFACE:
            variance = _variance_au_niveau(niveaux, cube, niveau)
            indicateurs[f"iv_{horizon}j_{round(100 * niveau)}spot_pct"] = [
                interpoler_echeance(echeances, np.sqrt(v), horizon) for v in variance.T]
    indicateurs["skew_30j_points"] = indicateurs.iv_30j_95spot_pct - indicateurs.iv_30j_100spot_pct
    indicateurs["pente_60j_30j_points"] = indicateurs.iv_60j_100spot_pct - indicateurs.iv_30j_100spot_pct

    # Diagnostic de forme : σ(0,90 ; 30) − σ(1 ; 30). Sur un marché actions, les puts
    # éloignés sont plus chers : cette pente est nettement positive. Nulle, elle signale une surface fausse.
    iv90 = pd.Series([interpoler_echeance(echeances, np.sqrt(v), 30)
                      for v in _variance_au_niveau(niveaux, cube, .90).T], index=dates)
    diagnostics = pd.DataFrame(index=dates)
    diagnostics["pente_sourire_90_points"] = iv90 - indicateurs.iv_30j_100spot_pct
    diagnostics["cellules_sous_1pct"] = (cube < 1).sum(axis=(0, 1))
    return indicateurs, diagnostics
