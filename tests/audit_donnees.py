"""Audit indépendant des données préparées : 48 contrôles de cohérence.

Ce programme **n'importe pas** le paquet ``portefeuille`` : il relit les fichiers bruts et
préparés et recalcule les grandeurs par d'autres chemins (produit par logarithmes, boucle
explicite, interpolation réécrite). Un accord entre les deux implémentations est une
preuve bien plus forte que de relire le même code.

Usage, depuis la racine du projet, après ``scripts/02_preparation.py`` et
``scripts/03_controle_surface.py`` ::

    .venv\\Scripts\\python.exe tests/audit_donnees.py

Le programme affiche chaque contrôle (OK ou ECHEC), un bilan, et se termine avec un code
d'erreur 1 si au moins un contrôle échoue.
"""
import hashlib
import json
import sys
from pathlib import Path

import exchange_calendars as xc
import numpy as np
import pandas as pd

RACINE = Path(__file__).resolve().parents[1]
BRUT, PREPARE, CONTROLES = RACINE / "data/brut", RACINE / "data/prepare", RACINE / "data/controles"
RESULTATS: list[bool] = []


def verifier(condition: bool, message: str) -> None:
    """Enregistre et affiche le résultat d'un contrôle."""
    RESULTATS.append(bool(condition))
    print(("OK     " if condition else "ECHEC  ") + "| " + message)


def information(message: str) -> None:
    """Affiche une information utile qui n'est pas un contrôle."""
    print("       | " + message)


def lire(chemin: Path) -> pd.DataFrame:
    """Lit un CSV indexé par date."""
    return pd.read_csv(chemin, index_col=0, parse_dates=True)


def prix_ajustes_bruts(titre: str) -> pd.Series:
    """Relit les clôtures ajustées Yahoo à pleine précision, directement depuis le JSON brut."""
    doc = json.loads((BRUT / "yahoo" / f"{titre}.json").read_bytes())["chart"]["result"][0]
    dates = pd.to_datetime(doc["timestamp"], unit="s", utc=True).tz_convert("America/New_York").tz_localize(None).normalize()
    return pd.Series(doc["indicators"]["adjclose"][0]["adjclose"], index=dates, dtype=float)


def main() -> int:
    """Exécute les 48 contrôles et retourne le code de sortie."""
    # ---- 1. Intégrité des sources (1 contrôle)
    fiches = json.loads((RACINE / "data/sources.json").read_text(encoding="utf8"))
    ecarts = [f["file"] for f in fiches
              if hashlib.sha256((BRUT / f["file"]).read_bytes()).hexdigest() != f["sha256"]]
    verifier(len(fiches) == 29 and not ecarts, f"29 sources, empreintes SHA-256 conformes ({len(ecarts)} écart)")

    # ---- 2. Calendrier (4 contrôles)
    seances = xc.get_calendar("XNYS", start="2011-08-01", end="2025-12-31").sessions
    etude = seances[seances.year >= 2012]
    quotidien, var_a = lire(PREPARE / "donnees_quotidiennes.csv"), lire(PREPARE / "variables_A.csv")
    cibles, prix = lire(PREPARE / "cibles_futures.csv"), lire(PREPARE / "prix_etf_et_spx.csv")
    for nom, tableau in [("donnees_quotidiennes", quotidien), ("variables_A", var_a), ("cibles_futures", cibles)]:
        verifier(tableau.index.equals(etude), f"{nom} : index = {len(etude)} séances NYSE 2012-2025, sans doublon")
    verifier(prix.index.equals(seances), f"prix : index = {len(seances)} séances NYSE depuis août 2011")

    # ---- 3. Prix (9 contrôles)
    for t in ("spy", "ief"):
        verifier((prix[f"{t}_close"] > 0).all() and (prix[f"{t}_adj"] > 0).all(), f"{t} : prix strictement positifs")
        verifier(np.allclose(prix[f"{t}_adj"].pct_change().dropna(), prix[f"{t}_return"].dropna()),
                 f"{t} : rendement = variation du prix ajusté")
        ratio = prix[f"{t}_adj"] / prix[f"{t}_close"]
        part = (ratio.diff().dropna() >= -1e-6).mean()
        verifier(part > .99, f"{t} : ratio ajusté/coté non décroissant (dividendes réinvestis) sur {100 * part:.2f} % des jours")
        sauts = ratio.pct_change().abs() > 1e-4
        verifier((~sauts | (prix[f"{t}_distribution"] > 0)).all(), f"{t} : le ratio ne saute qu'aux dates de distribution")
    rendement_spx = prix.spx_close.pct_change()
    correlation = rendement_spx.corr(prix.spy_return)
    verifier(correlation > .99, f"SPX et SPY cohérents : corrélation des rendements = {correlation:.4f}")
    information(f"SPY (rendement total) - SPX (prix), annualisé = {252 * (prix.spy_return - rendement_spx).loc['2012':].mean():.4f}")

    # ---- 4. Variables A recalculées autrement (3 contrôles)
    q = .6 * prix.spy_return + .4 * prix.ief_return
    reference = pd.DataFrame(index=prix.index)
    for h in (5, 21, 63):
        reference[f"var_panier_{h}"] = 252 * q.rolling(h).var()
    for h in (21, 63):
        reference[f"var_spy_{h}"] = 252 * prix.spy_return.rolling(h).var()
        reference[f"var_ief_{h}"] = 252 * prix.ief_return.rolling(h).var()
        reference[f"rend_panier_{h}"] = np.exp(np.log1p(q).rolling(h).sum()) - 1  # produit par les logarithmes
        reference[f"semivar_baisse_{h}"] = 252 * (np.minimum(q, 0) ** 2).rolling(h).mean()
        reference[f"corr_spy_ief_{h}"] = prix.spy_return.rolling(h).corr(prix.ief_return)
    ecart = (reference.reindex(etude)[var_a.columns] - var_a).abs().max().max()
    verifier(ecart < 1e-9, f"13 variables A recalculées autrement : écart absolu max = {ecart:.1e}")
    verifier(var_a.notna().all().all(), "variables A : aucune valeur manquante")
    verifier((var_a.filter(like="var") >= 0).all().all() and var_a.filter(like="corr").abs().le(1).all().all(),
             "variances positives, corrélations dans [-1, 1]")

    # ---- 5. Absence de fuite d'information future (1 contrôle)
    modifie = prix.copy()
    modifie.loc[modifie.index > "2020-03-02", ["spy_return", "ief_return"]] *= 3
    q_modifie = .6 * modifie.spy_return + .4 * modifie.ief_return
    verifier(np.isclose((252 * q_modifie.rolling(21).var())["2020-03-02"], var_a.loc["2020-03-02", "var_panier_21"]),
             "modifier les rendements après le 02/03/2020 ne change pas ses variables")

    # ---- 6. Cible recalculée par une boucle explicite, à pleine précision (6 contrôles)
    spy, ief = prix_ajustes_bruts("SPY").values, prix_ajustes_bruts("IEF").values
    position = {t: i for i, t in enumerate(seances)}
    valeurs = []
    for t in etude:
        i = position[t]
        if i + 22 >= len(seances):
            valeurs.append(np.nan)
            continue
        panier = .6 * spy[i + 1:i + 23] / spy[i + 1] + .4 * ief[i + 1:i + 23] / ief[i + 1]
        valeurs.append(252 * np.mean((panier[1:] / panier[:-1] - 1) ** 2))
    valeurs = pd.Series(valeurs, index=etude)
    ecart = np.nanmax(np.abs(valeurs - cibles.variance_21j_ann) / valeurs)
    verifier(ecart < 1e-9 and valeurs.isna().equals(cibles.variance_21j_ann.isna()),
             f"cible : {valeurs.notna().sum()} valeurs recalculées, écart relatif max = {ecart:.1e} "
             f"(limite d'un CSV à 10 chiffres : 5e-10), {valeurs.isna().sum()} vides en fin")
    verifier(np.allclose(cibles.vol_21j_ann ** 2, cibles.variance_21j_ann, equal_nan=True, rtol=1e-8), "vol = racine de la variance")
    execution, fin = pd.to_datetime(cibles.execution), pd.to_datetime(cibles.fin_cible)
    verifier(all(seances.get_loc(execution[t]) == seances.get_loc(t) + 1 for t in etude[:-1]), "exécution = séance suivant le signal")
    verifier(all(seances.get_loc(fin[t]) == seances.get_loc(t) + 22 for t in etude[:-22]), "fin de cible = signal + 22 séances")
    verifier(round(cibles.loc["2022-07-01", "vol_21j_ann"], 6) == 0.129332, "exemple documenté : 01/07/2022 = 12,9332 %")
    masque = cibles.variance_21j_ann.notna()
    persistance = np.corrcoef(np.log(var_a.var_panier_21[masque]), np.log(cibles.variance_21j_ann[masque]))[0, 1]
    verifier(.3 < persistance < .9, f"persistance : corr(log variance passée, log variance future) = {persistance:.3f}")

    # ---- 7. Indices Cboe (4 contrôles)
    verifier(quotidien[["vix9d", "vix", "vix3m", "vix6m"]].notna().all().all(), "VIX9D, VIX, VIX3M, VIX6M complets")
    verifier((quotidien.vix > 0).all() and (quotidien["skew"].dropna() > 100).all(), "bornes : VIX > 0, SKEW > 100")
    contango = (quotidien.vix3m >= quotidien.vix).mean()
    verifier(contango > .8, f"VIX3M >= VIX {100 * contango:.1f} % du temps (structure par terme habituelle)")
    verifier(quotidien.vix9d_vix6m_diffuses.eq(quotidien.index >= "2013-11-27").all(), "drapeau de diffusion VIX9D/VIX6M correct")

    # ---- 8. Surface (13 contrôles)
    surface = quotidien.dropna(subset=["iv_30j_100spot_pct"])
    verifier(len(surface) == 1734, f"surface : 1 740 séances - 6 rejetées = {len(surface)}")
    verifier((surface.iv_30j_95spot_pct > surface.iv_30j_105spot_pct).all(), "sourire : IV(95 %) > IV(105 %) chaque jour")
    verifier((surface.iv_30j_100spot_pct < surface.vix).all(), "IV à la monnaie sous le VIX chaque jour")
    verifier(np.allclose(surface.skew_30j_points, surface.iv_30j_95spot_pct - surface.iv_30j_100spot_pct, rtol=1e-6), "skew = IV95 - IV100")
    verifier(np.allclose(surface.pente_60j_30j_points, surface.iv_60j_100spot_pct - surface.iv_30j_100spot_pct, rtol=1e-6), "pente = IV60 - IV30")
    for annee in range(2017, 2024):
        x = surface.loc[str(annee)]
        c = x.iv_30j_100spot_pct.diff().corr(x.vix.diff())
        verifier(c > .9, f"surface {annee} : corrélation des variations IV à la monnaie / VIX = {c:.3f}")
    rejets = lire(CONTROLES / "controle_qualite_surface.csv")
    verifier(rejets.rejetee.sum() == 6 and (rejets.iv_au_dessus_vix == rejets.sourire_plat).all(), "6 rejets, les deux critères concordent")

    # ---- 9. IV recalculées depuis le cube brut, autre implémentation (3 contrôles)
    with np.load(BRUT / "surfaces/spx_long.npz") as z:
        niveaux, echeances, dates, cube = z["m_grid"], z["tenor_days"], pd.DatetimeIndex(z["asof_dates"]), z["cube"].astype(float)
    for jour, niveau, horizon, colonne in [("2020-03-16", 1., 30, "iv_30j_100spot_pct"),
                                           ("2020-03-16", .95, 60, "iv_60j_95spot_pct"),
                                           ("2018-02-05", 1.05, 30, "iv_30j_105spot_pct")]:
        k = dates.get_loc(pd.Timestamp(jour))
        variance_totale = [np.interp(niveau, niveaux, cube[:, j, k] ** 2) * echeances[j] for j in range(len(echeances))]
        iv = np.sqrt(np.interp(horizon, echeances, variance_totale) / horizon)
        verifier(abs(iv - quotidien.loc[jour, colonne]) < 1e-5,
                 f"IV recalculée depuis le cube brut, {jour}, {colonne} : {iv:.4f} contre {quotidien.loc[jour, colonne]:.4f}")

    # ---- 10. Cash (2 contrôles)
    rf = quotidien.rf_usd_rendement_jour
    verifier((rf >= 0).all() and rf.max() < .001, f"RF de French dans [0 ; 0,1 %] par jour, {rf.nunique()} valeurs distinctes (arrondi)")
    taux = lire(PREPARE / "taux_bons_tresor.csv")
    mensuel = pd.concat([quotidien.cash_tbill_rendement_jour.resample("ME").sum() * 12,
                         (taux.tbill_4w_investment_pct / 100).resample("ME").mean()], axis=1, sort=True).dropna()
    verifier(mensuel.corr().iloc[0, 1] > .99, f"cash T-bill cohérent avec le taux publié : corrélation mensuelle = {mensuel.corr().iloc[0, 1]:.4f}")

    # ---- 11. Contrôle de la surface par les contrats de 2022 (2 contrôles)
    comparaison = lire(CONTROLES / "controle_chaines_et_surfaces.csv")
    verifier(abs(comparaison.ecart_points.abs().median() - .545) < .01,
             f"contrôle de la surface : écart médian contrats / surface = {comparaison.ecart_points.abs().median():.3f} point")
    termes = pd.read_csv(PREPARE / "termes_indicatifs_2022S2.csv", parse_dates=["date"])
    base = termes.forward_indicatif.values / quotidien.spx_close.reindex(termes.date).values - 1
    verifier(np.abs(base).max() < .03, f"prix à terme cohérents avec le spot : écart max {np.abs(base).max():.4f}")

    reussis = sum(RESULTATS)
    print(f"\nBilan : {reussis} contrôles réussis sur {len(RESULTATS)}.")
    return 0 if reussis == len(RESULTATS) else 1


if __name__ == "__main__":
    sys.exit(main())
