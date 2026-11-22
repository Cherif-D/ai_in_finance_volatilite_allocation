"""Prix des ETF et de l'indice (Yahoo Finance) et indices de volatilité de Cboe."""
import json

import pandas as pd

from ..config import BRUT, DEBUT_AMORCAGE, FIN_ETUDE, SEANCES


def dates_new_york(horodatages) -> pd.DatetimeIndex:
    """Convertit des horodatages Unix en dates de séance à New York (sans heure)."""
    return pd.to_datetime(horodatages, unit="s", utc=True).tz_convert(
        "America/New_York").tz_localize(None).normalize()


def charger_prix() -> pd.DataFrame:
    """Lit les historiques Yahoo de SPY, IEF et SPX, alignés sur les séances NYSE.

    Avec P_adj la clôture ajustée, P la clôture cotée et D(u) la distribution détachée en u :

                P_adj(u)                                ⎛ P(u) + D(u)            ⎞
        r(u) = ─────────── − 1          e(u) = 10 000 · ⎜ ─────────── − 1 − r(u) ⎟
               P_adj(u−1)                               ⎝   P(u−1)               ⎠

    Notations
    ---------
    u           séance de Bourse ; u−1 est la séance précédente
    P(u)        clôture cotée en u : prix réellement négocié, en $ par part
    P_adj(u)    clôture ajustée en u par Yahoo : prix corrigé pour réinvestir les distributions
    D(u)        distribution (dividende ou coupon) détachée en u, en $ par part ; 0 sinon
    r(u)        rendement total quotidien, en décimal (0,01 = +1 %)
    e(u)        écart de contrôle, en points de base (1 pb = 0,01 %)

    e(u) mesure l'écart entre le rendement ajusté de Yahoo et un rendement total recalculé
    à la main ; il doit rester proche de zéro.

    Yahoo ajuste les prix de façon multiplicative (méthode CRSP) : chaque distribution D(u)
    multiplie tous les prix antérieurs par f(u) = 1 − D(u) / P(u−1). Son rendement vaut donc
    exactement r(u) = P(u) / (P(u−1) − D(u)) − 1, ce qui diffère de (P(u) + D(u)) / P(u−1) − 1
    d'un terme du second ordre, ≈ D(u) / P(u−1) × r(u). C'est pourquoi e(u) n'est pas nul les
    jours de distribution (au plus 2,5 pb pour SPY) ; vérifié : avec la formule multiplicative,
    l'écart résiduel reste sous 0,02 pb sur toutes les séances.

    Retourne
    --------
    Une ligne par séance depuis août 2011 et, pour chaque titre préfixé (``spy_``, ``ief_``,
    ``spx_``) :

    - ``close`` : clôture cotée P (dollars par part, points d'indice pour le SPX) ;
    - ``adj`` : clôture ajustée P_adj, distributions réinvesties (ETF seulement) ;
    - ``distribution`` : D(u), en dollars par part ;
    - ``return`` : r(u), en décimal ;
    - ``ecart_controle_bp`` : e(u), en points de base.
    """
    series = []
    for titre in ("SPY", "IEF", "SPX"):
        doc = json.loads((BRUT / "yahoo" / f"{titre}.json").read_bytes())["chart"]["result"][0]
        dates = dates_new_york(doc["timestamp"])
        if not dates.equals(SEANCES) or doc["meta"]["currency"] != "USD":
            raise ValueError(f"Calendrier ou devise à examiner pour {titre}")
        tableau = pd.DataFrame(index=dates)
        tableau["close"] = doc["indicators"]["quote"][0]["close"]
        if titre != "SPX":
            tableau["adj"] = doc["indicators"]["adjclose"][0]["adjclose"]
            # Distributions rattachées à leur date de détachement.
            tableau["distribution"] = 0.
            for evenement in doc.get("events", {}).get("dividends", {}).values():
                jour = dates_new_york([evenement["date"]])[0]
                if jour not in dates:
                    raise ValueError(f"Distribution hors séance : {jour}")
                tableau.loc[jour, "distribution"] += evenement["amount"]
            if doc.get("events", {}).get("splits"):
                raise ValueError("Division de parts : vérifier la convention d'ajustement")
            tableau["return"] = tableau.adj.pct_change(fill_method=None)
            # Contrôle : (clôture + distribution) / clôture de la veille - 1 doit égaler le rendement ajusté.
            tableau["ecart_controle_bp"] = 10000 * (
                (tableau.close + tableau.distribution) / tableau.close.shift(1) - 1 - tableau["return"])
        prix = tableau[["close", "adj"] if titre != "SPX" else ["close"]]
        if prix.isna().any().any() or (prix <= 0).any().any():
            raise ValueError(f"Prix manquants ou non positifs : {titre}")
        series.append(tableau.add_prefix(titre.lower() + "_"))
    return pd.concat(series, axis=1)


def charger_indices_cboe() -> pd.DataFrame:
    """Lit les clôtures des indices Cboe ``vix9d``, ``vix``, ``vix3m``, ``vix6m`` et ``skew``.

    Les quatre VIX sont des volatilités implicites annualisées du SPX à 9 jours, 30 jours,
    3 mois et 6 mois, en pourcentage. SKEW est un indice d'asymétrie sur sa propre échelle.
    Les dates publiées hors séance sont conservées ici et écartées lors de la jointure.
    """
    champs = []
    for symbole in ("VIX9D", "VIX", "VIX3M", "VIX6M", "SKEW"):
        df = pd.read_csv(BRUT / "cboe" / f"{symbole}.csv")
        df.index = pd.to_datetime(df.DATE, format="%m/%d/%Y")
        serie = df[symbole if symbole == "SKEW" else "CLOSE"].rename(symbole.lower())
        if serie.index.has_duplicates:
            raise ValueError(f"Date répétée : {symbole}")
        champs.append(serie)
    return pd.concat(champs, axis=1, sort=True).loc[DEBUT_AMORCAGE:FIN_ETUDE]
