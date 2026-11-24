"""Variables C : volatilité locale de Dupire tirée de la surface Bloomberg.

La volatilité implicite σ(K, T) donne un risque **moyen** jusqu'à l'échéance T. La
volatilité locale σ_loc(K, T) donne le risque **instantané** que le marché attend à la date
T si l'indice vaut alors K. Dupire (1994) montre qu'elle se déduit de toute la surface.
On utilise sa réécriture en variance totale (Gatheral, *The Volatility Surface*, 2006,
éq. 1.10), qui évite de passer par les prix des options.

Méthode, jour par jour (aucune information d'une autre séance) :

1. prix à terme F(T) = S · exp((r(T) − q) · T), avec r(T) le taux des T-bills et q le
   rendement de dividende estimé par Bloomberg ;
2. pour chaque échéance, on lisse le sourire en variance totale par une parabole en
   y = ln(K / F) ;
3. on applique la formule de Dupire-Gatheral aux points demandés.
"""
import numpy as np
import pandas as pd

from ..config import DEGRE_LISSAGE, ECHEANCES_LOCALE, NIVEAUX_LOCALE

# T-bills utilisés pour le taux sans risque : durée en jours et colonne du taux équivalent.
BONS = ((28, "tbill_4w_investment_pct"), (91, "tbill_13w_investment_pct"),
        (182, "tbill_26w_investment_pct"), (364, "tbill_52w_investment_pct"))


def taux_par_echeance(echeances: np.ndarray, taux_bons_pct: np.ndarray) -> np.ndarray:
    """Taux sans risque continu pour chaque échéance, à partir des T-bills du jour.

    Le taux équivalent y des T-bills (en %, base 365) est interpolé linéairement selon la
    durée, constant au-delà des bornes, puis converti en taux continu :

                  ln(1 + y · T)
        r(T) = ─────────────────         T en années (jours / 365), y en décimal
                       T

    Paramètres
    ----------
    echeances : échéances en jours calendaires.
    taux_bons_pct : taux des T-bills de 4, 13, 26 et 52 semaines du jour, en % (NaN accepté).
    """
    duree = np.array([b[0] for b in BONS], dtype=float)
    connu = ~np.isnan(taux_bons_pct)
    if not connu.any():
        return np.full(len(echeances), np.nan)
    y = np.interp(echeances, duree[connu], taux_bons_pct[connu]) / 100
    t = echeances / 365
    return np.log1p(y * t) / t


def lisser_sourires(niveaux: np.ndarray, echeances: np.ndarray, iv_pct: np.ndarray,
                    r: np.ndarray, q: float, degre: int = DEGRE_LISSAGE) -> tuple[np.ndarray, float]:
    """Lisse le sourire de chaque échéance par un polynôme en variance totale (parabole par défaut).

    Pour l'échéance T et le prix d'exercice relatif m = K / S :

        y = ln(m) − (r(T) − q) · T          w = σ² · T          w(y) ≈ a · y² + b · y + c

    Notations
    ---------
    y           log-moneyness par rapport au prix à terme, ln(K / F)
    σ           volatilité implicite, en décimal
    w           variance totale (risque cumulé jusqu'à l'échéance)
    a, b, c     coefficients ajustés par moindres carrés sur les 5 points du sourire
    degre       degré du polynôme (``DEGRE_LISSAGE`` = 2, la parabole)

    Une parabole a 3 paramètres pour 5 points : elle lisse le bruit tout en gardant la
    pente et la courbure du sourire, dont Dupire a besoin. Test du 24/11/2026 sur une chaîne
    complète de ~400 options par échéance : la parabole est juste au cours (0,3 point) mais
    sous-estime la volatilité locale à 95 % d'environ 1,5 point. Le degré 4 (courbe passant
    exactement par les 5 points) corrige ce biais, mais rend le skew local deux fois plus
    bruité d'un jour à l'autre (2012-2025). On garde la parabole, plus stable.

    Retourne les coefficients (une ligne par échéance) et l'écart maximal entre l'IV lissée
    et l'IV Bloomberg, en points de volatilité.
    """
    t = echeances / 365
    coefs, ecart = [], 0.
    for j, tj in enumerate(t):
        y = np.log(niveaux) - (r[j] - q) * tj
        w = (iv_pct[:, j] / 100) ** 2 * tj
        c = np.polyfit(y, w, degre)
        coefs.append(c)
        ajuste = 100 * np.sqrt(np.clip(np.polyval(c, y), 0, None) / tj)
        ecart = max(ecart, float(np.abs(ajuste - iv_pct[:, j]).max()))
    return np.array(coefs), ecart


def volatilite_locale(coefs: np.ndarray, echeances: np.ndarray, r: np.ndarray, q: float,
                      niveau: float, j: int) -> float:
    """Volatilité locale de Dupire au prix d'exercice m = K / S et à l'échéance d'indice j.

    Formule de Dupire écrite en variance totale (Gatheral, éq. 1.10) :

                                          ∂w/∂T
        σ²_loc = ───────────────────────────────────────────────────────────────
                  1 − (y/w)·∂w/∂y + ¼·(−¼ − 1/w + y²/w²)·(∂w/∂y)² + ½·∂²w/∂y²

    Notations
    ---------
    y           ln(K / F(T)), avec K = m · S
    w(y, T)     variance totale σ²·T lue sur le polynôme lissé de l'échéance T
    ∂w/∂y       pente du sourire ; ∂²w/∂y² sa courbure (dérivées exactes du polynôme)
    ∂w/∂T       croissance du risque cumulé avec l'échéance, à y fixé : différence finie avec
                l'échéance suivante (avant), la précédente (dernière) ou les deux voisines (centrée)
    σ_loc       volatilité locale, renvoyée en % annuel

    Sans sourire ni structure par terme (σ constante), la formule redonne σ_loc = σ.
    Si ∂w/∂T ≤ 0 (arbitrage calendaire) ou si le dénominateur est ≤ 0 (arbitrage papillon),
    la volatilité locale n'existe pas : le résultat est manquant, jamais remplacé.
    """
    t = echeances / 365
    y = np.log(niveau) - (r[j] - q) * t[j]
    w = np.polyval(coefs[j], y)
    w1 = np.polyval(np.polyder(coefs[j]), y)
    w2 = np.polyval(np.polyder(coefs[j], 2), y)
    avant, apres = max(j - 1, 0), min(j + 1, len(t) - 1)
    dw_dt = (np.polyval(coefs[apres], y) - np.polyval(coefs[avant], y)) / (t[apres] - t[avant])
    denominateur = 1 - y / w * w1 + .25 * (-.25 - 1 / w + y * y / (w * w)) * w1 * w1 + .5 * w2
    if not (w > 0 and dw_dt > 0 and denominateur > 0):
        return np.nan
    return 100 * float(np.sqrt(dw_dt / denominateur))


def variables_locales(niveaux: np.ndarray, echeances: np.ndarray, dates: pd.DatetimeIndex,
                      cube: np.ndarray, dividende_pct: pd.Series,
                      taux: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Construit les variables C, date par date.

    Les IV Bloomberg aux mêmes points (ensemble B) se calculent à part, avec
    ``features.indicateurs_surface`` appliquée à la même grille.

    Paramètres
    ----------
    niveaux, echeances, dates, cube, dividende_pct : sortie de ``charger_surface_bloomberg``.
    taux : taux des T-bills (``taux_bons_tresor.csv``). Un jour sans publication du Trésor
        reprend le dernier taux publié (information passée uniquement).

    Retourne
    --------
    variables :
        ``vl_{30,60}j_{95,100,105}spot_pct`` volatilité locale, en % ;
        ``skew_vl_30j_points`` = σ_loc(0,95 ; 30) − σ_loc(1 ; 30), en points ;
        ``pente_vl_60j_30j_points`` = σ_loc(1 ; 60) − σ_loc(1 ; 30), en points.
    diagnostics :
        ``ecart_lissage_max_points`` (IV lissée − IV Bloomberg, maximum en valeur absolue),
        ``arbitrages_calendaires`` (cellules où w décroît avec T sur la grille brute),
        ``points_vl_manquants`` (sur les 6 points demandés), ``taux_30j_pct``, ``dividende_pct``,
        ``rejetee`` (journée vidée car la volatilité locale manque en au moins un point).
        Le script 04 ajoute à ce rejet celui du contrôle de qualité de B (même surface).
    """
    bons = taux[[b[1] for b in BONS]].reindex(dates, method="ffill").to_numpy()
    q = dividende_pct.reindex(dates).to_numpy() / 100
    colonne = {T: int(np.argmin(np.abs(echeances - T))) for T in ECHEANCES_LOCALE}

    lignes, diag = [], []
    for i in range(len(dates)):
        r = taux_par_echeance(echeances, bons[i])
        coefs, ecart = lisser_sourires(niveaux, echeances, cube[:, :, i], r, q[i])
        ligne = {}
        for T in ECHEANCES_LOCALE:
            for m in NIVEAUX_LOCALE:
                ligne[f"vl_{T}j_{round(100 * m)}spot_pct"] = volatilite_locale(coefs, echeances, r, q[i], m, colonne[T])
        lignes.append(ligne)
        w = (cube[:, :, i] / 100) ** 2 * echeances
        diag.append({"ecart_lissage_max_points": ecart,
                     "arbitrages_calendaires": int((np.diff(w, axis=1) < 0).sum()),
                     "points_vl_manquants": sum(np.isnan(v) for k, v in ligne.items() if k.startswith("vl_")),
                     "taux_30j_pct": 100 * r[0], "dividende_pct": 100 * q[i]})

    variables = pd.DataFrame(lignes, index=dates)
    diagnostics = pd.DataFrame(diag, index=dates)
    # Règle de rejet : si la volatilité locale n'existe pas en l'un des 6 points (arbitrage),
    # toute la journée est jugée douteuse et vidée ; elle n'est jamais remplie.
    # Cas observé : le 20/09/2022, Bloomberg donne 47,3 % à 30 jours contre 25,1 % à 60 jours.
    diagnostics["rejetee"] = diagnostics.points_vl_manquants > 0
    variables.loc[diagnostics.rejetee] = np.nan
    variables["skew_vl_30j_points"] = variables.vl_30j_95spot_pct - variables.vl_30j_100spot_pct
    variables["pente_vl_60j_30j_points"] = variables.vl_60j_100spot_pct - variables.vl_30j_100spot_pct
    return variables, diagnostics
