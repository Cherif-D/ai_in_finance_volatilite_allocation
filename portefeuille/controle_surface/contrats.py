"""Contrôle de la surface Bloomberg par de vraies options SPX expirées (2015-2025).

Le classeur privé ``Bloomberg_SPX_Historique_Options_Rolls.xlsx`` donne, pour chaque mois,
6 options SPX mensuelles (puts à 90, 95 et 100 % du cours, calls à 100, 105 et 110 %) et
leur dernier prix négocié (``PX_LAST``) chaque jour pendant environ trois mois. On en tire la
volatilité implicite de chaque contrat, puis on la compare à la surface Bloomberg le même
jour, au même prix d'exercice relatif et à la même échéance.
"""
import numpy as np
import pandas as pd
from openpyxl import load_workbook
from scipy.optimize import brentq
from scipy.stats import norm

from ..config import BLOOMBERG_OPTIONS
from ..features.locale import taux_par_echeance, BONS


def charger_options_expirees(chemin=BLOOMBERG_OPTIONS) -> pd.DataFrame:
    """Lit les prix quotidiens des options expirées : une ligne par (contrat, jour).

    Colonnes : ``date``, ``echeance``, ``type`` (P ou C), ``K`` (prix d'exercice),
    ``prix`` (dernier prix négocié, en points d'indice) et ``panier`` (« 95% Put »…).
    Les contrats que Bloomberg ne fournit plus (« #N/A Invalid Security », avant 2015)
    sont ignorés.
    """
    classeur = load_workbook(chemin, read_only=True, data_only=True)
    lignes = []
    for feuille in classeur.sheetnames:
        if not feuille.startswith("OPT_"):
            continue
        rangs = list(classeur[feuille].iter_rows(values_only=True))
        h = next(i for i, r in enumerate(rangs) if r and isinstance(r[0], str) and r[0].startswith("SPX US"))
        noms, bornes, codes = rangs[h - 2], rangs[h - 1], rangs[h]
        for c in range(0, len(codes) - 1, 2):
            if not (isinstance(codes[c], str) and codes[c].startswith("SPX US")):
                continue
            code = codes[c].split()[3]                       # « P2875 » : type puis prix d'exercice
            for r in rangs[h + 1:]:
                if r[c] is not None and hasattr(r[c], "year") and isinstance(r[c + 1], (int, float)):
                    lignes.append((pd.Timestamp(r[c]), pd.Timestamp(bornes[c + 1]), code[0], float(code[1:]),
                                   float(r[c + 1]), str(noms[c + 1]).split(" (")[0]))
    classeur.close()
    return pd.DataFrame(lignes, columns=["date", "echeance", "type", "K", "prix", "panier"])


def _iv_black_scholes(prix: float, S: float, K: float, T: float, r: float, q: float, type_: str) -> float:
    """Volatilité implicite d'une option européenne, en décimal.

    Prix de Black-Scholes avec dividende continu, écrit avec le prix à terme :

        F = S · e^((r − q)·T)      D = e^(−r·T)      d₁ = [ln(F/K) + σ²T/2] / (σ√T)      d₂ = d₁ − σ√T
        call = D · [F·N(d₁) − K·N(d₂)]          put = D · [K·N(−d₂) − F·N(−d₁)]

    Notations
    ---------
    S, K        cours du SPX et prix d'exercice ; T durée en années
    r, q        taux sans risque continu et rendement de dividende, en décimal
    N           fonction de répartition de la loi normale centrée réduite
    σ           volatilité cherchée : celle qui redonne le prix observé (méthode de Brent)

    Manquant si le prix est sous la valeur intrinsèque actualisée (aucune σ ne convient).
    """
    F, D, racine = S * np.exp((r - q) * T), np.exp(-r * T), np.sqrt(T)

    def ecart(sigma):
        d1 = (np.log(F / K) + .5 * sigma * sigma * T) / (sigma * racine)
        d2 = d1 - sigma * racine
        modele = D * (F * norm.cdf(d1) - K * norm.cdf(d2)) if type_ == "C" else D * (K * norm.cdf(-d2) - F * norm.cdf(-d1))
        return modele - prix

    try:
        return brentq(ecart, 1e-4, 5.)
    except ValueError:
        return np.nan


def comparer_contrats_surface(options: pd.DataFrame, spx: pd.Series, taux: pd.DataFrame,
                              niveaux: np.ndarray, echeances: np.ndarray, dates: pd.DatetimeIndex,
                              cube: np.ndarray, dividende_pct: pd.Series) -> pd.DataFrame:
    """Compare l'IV de chaque cotation à la surface Bloomberg du même jour.

    On garde les cotations à 30-91 jours de l'échéance (à l'intérieur de la grille, sans
    extrapolation) et dont le prix d'exercice relatif m = K / S est entre 0,90 et 1,10.
    IV de la surface au point (m, T) : σ² interpolée linéairement selon m entre deux niveaux,
    puis variance totale σ²·T linéairement selon T entre deux échéances (comme pour B).

    Retourne une ligne par cotation : ``iv_contrat_pct``, ``iv_surface_pct``, ``ecart_points``
    (contrat − surface) et ``hors_monnaie`` (put avec K ≤ S ou call avec K ≥ S, la mesure la
    plus précise, voir la surface universitaire).
    """
    bons = taux[[b[1] for b in BONS]].reindex(dates, method="ffill")
    position = pd.Series(np.arange(len(dates)), index=dates)
    o = options.assign(S=options.date.map(spx), jours=(options.echeance - options.date).dt.days)
    o = o[o.S.notna() & o.date.isin(dates) & o.jours.between(30, 91)]
    o = o[(o.K / o.S).between(.90, 1.10)]
    lignes = []
    for x in o.itertuples():
        i = position[x.date]
        r = taux_par_echeance(np.array([float(x.jours)]), bons.iloc[i].to_numpy())[0]
        iv = _iv_black_scholes(x.prix, x.S, x.K, x.jours / 365, r, dividende_pct.iloc[i] / 100, x.type)
        m = x.K / x.S
        variance = np.array([np.interp(m, niveaux, cube[:, j, i] ** 2) for j in range(len(echeances))])
        iv_surface = np.sqrt(np.interp(x.jours, echeances, variance * echeances) / x.jours)
        lignes.append({"date": x.date, "echeance": x.echeance, "panier": x.panier, "type": x.type, "K": x.K,
                       "m": m, "jours": x.jours, "iv_contrat_pct": 100 * iv, "iv_surface_pct": iv_surface})
    table = pd.DataFrame(lignes).dropna(subset=["iv_contrat_pct"])
    table["ecart_points"] = table.iv_contrat_pct - table.iv_surface_pct
    table["hors_monnaie"] = (table.type.eq("P") & (table.m <= 1)) | (table.type.eq("C") & (table.m >= 1))
    return table
