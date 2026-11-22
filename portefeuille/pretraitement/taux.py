"""Taux courts du Trésor américain et rémunération des liquidités."""
import re
import zipfile
from xml.etree import ElementTree

import numpy as np
import pandas as pd

from ..config import BRUT, DEBUT_AMORCAGE, FIN_ETUDE


def charger_taux_tresor() -> pd.DataFrame:
    """Lit les taux quotidiens des T-bills américains à 4, 8, 13, 26 et 52 semaines.

    Pour chaque durée : taux d'escompte (``discount_pct``, base 360), taux de rendement
    équivalent (``investment_pct``, base 365), tous deux en pourcentage annuel, et date
    d'échéance du bon.
    """
    lignes = []
    for chemin in sorted((BRUT / "treasury").glob("*.xml")):
        for noeud in ElementTree.parse(chemin).findall(".//{*}properties"):
            valeurs = {champ.tag.split("}")[-1]: champ.text for champ in noeud}
            ligne = {"date": pd.Timestamp(valeurs["INDEX_DATE"])}
            for semaines in [4, 8, 13, 26, 52]:
                prefixe = f"tbill_{semaines}w"
                for cle, champ in [("discount_pct", f"CS_{semaines}WK_CLOSE_AVG"),
                                   ("investment_pct", f"CS_{semaines}WK_YIELD_AVG")]:
                    ligne[f"{prefixe}_{cle}"] = float(valeurs[champ]) if valeurs.get(champ) else np.nan
                echeance = valeurs.get(f"MATURITY_DATE_{semaines}WK")
                if echeance:
                    ligne[f"{prefixe}_maturity"] = echeance[:10]
            lignes.append(ligne)
    tableau = pd.DataFrame(lignes).set_index("date").sort_index().loc[DEBUT_AMORCAGE:FIN_ETUDE]
    if tableau.index.has_duplicates or tableau.tbill_4w_investment_pct.notna().sum() < 3400:
        raise ValueError("Couverture des taux du Trésor inattendue")
    return tableau


def charger_cash_french() -> pd.Series:
    """Lit le rendement quotidien des liquidités en dollars (RF) de Kenneth French, en décimal.

    Attention : la source est arrondie à 0,01 % par jour. Cette série est conservée pour
    comparaison ; le portefeuille utilise ``rendement_cash_tbill``.
    """
    with zipfile.ZipFile(BRUT / "french/daily.zip") as z:
        lignes = z.read(z.namelist()[0]).decode("latin1").splitlines()
    valeurs = [ligne.split(",") for ligne in lignes if re.match(r"^\d{8},", ligne)]
    df = pd.DataFrame(valeurs, columns=["date", "market", "smb", "hml", "rf"])
    df.index = pd.to_datetime(df.date, format="%Y%m%d")
    # La source est en pourcentage : division par 100 pour obtenir un rendement en décimal.
    return (pd.to_numeric(df.rf) / 100).rename("rf_usd_rendement_jour").loc[DEBUT_AMORCAGE:FIN_ETUDE]


def rendement_cash_tbill(taux: pd.DataFrame, seances: pd.DatetimeIndex) -> pd.Series:
    """Rendement quotidien des liquidités tiré du T-bill à 4 semaines, en décimal.

    Le RF quotidien de Kenneth French est publié arrondi à 0,01 % par jour : il ne prend que
    trois valeurs (0 ; 2,52 % ; 5,04 % par an) et reste par exemple à 0 % jusqu'en juillet 2022.
    Cette série le remplace pour rémunérer le cash du portefeuille.

    Pour la séance t précédée de la séance t⁻, avec y(t⁻) le taux de rendement équivalent
    (``investment_pct``, en %, base 365) publié en t⁻ :

                        y(t⁻)      t − t⁻
        r_cash(t)  =  ─────── × ────────
                         100        365

    Notations
    ---------
    t           séance rémunérée
    t⁻          séance de Bourse précédente
    t − t⁻      jours calendaires écoulés (1 en semaine, 3 du vendredi au lundi)
    y(t⁻)       taux de rendement du T-bill 4 semaines publié en t⁻, en % annuel, base 365
    r_cash(t)   rendement du cash entre t⁻ et t, en décimal

    Le taux est connu avant la période qu'il rémunère. Un jour sans publication du Trésor
    reprend le dernier taux publié (information passée uniquement).
    """
    taux_connu = taux.tbill_4w_investment_pct.reindex(seances, method="ffill").shift(1)
    jours = seances.to_series().diff().dt.days
    return (taux_connu / 100 * jours / 365).rename("cash_tbill_rendement_jour")
