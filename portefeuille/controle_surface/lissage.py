"""Test du lissage des sourires sur une chaîne complète d'options (une seule séance Bloomberg).

La surface Bloomberg ne donne que 5 points par échéance (90 à 110 % du cours). Pour savoir
ce que l'on perd, on prend un jour où l'on dispose de la chaîne complète (~400 options hors
de la monnaie par échéance) et l'on compare deux volatilités locales :

- **référence dense** : polynôme de degré 4 ajusté sur toutes les options entre 85 et 115 % ;
- **méthode du projet** : les 5 seuls points 90, 95, 100, 105 et 110 %, puis le lissage de
  ``features.locale`` (parabole, ou degré 4 pour comparaison).
"""
import numpy as np
import pandas as pd

from ..config import NIVEAUX_BLOOMBERG, NIVEAUX_LOCALE
from ..features.locale import lisser_sourires, volatilite_locale


def sourires_chaine(chaine: pd.DataFrame, jour: pd.Timestamp, racine: str = "SPX",
                    nombre: int = 3) -> list[dict]:
    """Extrait, pour les ``nombre`` premières échéances, le prix à terme et le sourire.

    Prix à terme par la parité call-put, ajustée sur les paires proches du cours :

        C − P = D · (F − K)       régression de C − P sur K : pente = −D, ordonnée = D · F

    Notations
    ---------
    C, P        prix milieux (mid) d'un call et d'un put de même prix d'exercice K
    D, F        facteur d'actualisation et prix à terme de l'échéance
    y, w        ln(K / F) et variance totale IV² · T des options hors de la monnaie
                (puts sous F, calls au-dessus), entre 80 et 120 % de F

    Retourne une liste de dictionnaires (``jours``, ``F``, ``D``, ``y``, ``w``), triée par échéance.
    """
    sourires = []
    for echeance, groupe in sorted(chaine[chaine.racine == racine].groupby("echeance"), key=lambda x: x[0])[:nombre]:
        calls = groupe[groupe.type == "Call"].set_index("K")
        puts = groupe[groupe.type == "Put"].set_index("K")
        communs = calls.index.intersection(puts.index)
        paires = pd.DataFrame({"c": calls.mid[communs], "p": puts.mid[communs],
                               "ok": (calls.bid[communs] > 0) & (puts.bid[communs] > 0)})
        paires = paires[paires.ok]
        proche = paires.index[(paires.c - paires.p).abs().argmin()]
        pres = paires[np.abs(paires.index / proche - 1) < .05]
        pente, origine = np.polyfit(pres.index, pres.c - pres.p, 1)
        D, jours = -pente, (echeance - jour).days
        F = origine / D
        hors = pd.concat([puts[puts.index < F], calls[calls.index >= F]])
        hors = hors[(hors.bid > 0) & hors.iv.notna()]
        y = np.log(hors.index.to_numpy() / F)
        w = (hors.iv.to_numpy() / 100) ** 2 * jours / 365
        garde = (y > np.log(.80)) & (y < np.log(1.20))
        sourires.append({"echeance": echeance, "jours": jours, "F": F, "D": D, "y": y[garde], "w": w[garde]})
    return sourires


def comparer_lissage(sourires: list[dict]) -> pd.DataFrame:
    """Compare la volatilité locale dense et celle tirée de 5 points, aux deux premières échéances.

    Les prix d'exercice sont repérés par rapport au prix à terme (K / F), d'où r = q = 0 dans
    les fonctions de ``features.locale``. Retourne une ligne par (échéance, niveau) avec la
    volatilité locale dense, celle de la parabole (degré 2) et celle du degré 4, en %.
    """
    jours = np.array([s["jours"] for s in sourires], dtype=float)
    zero = np.zeros(len(sourires))
    niveaux = np.array(NIVEAUX_BLOOMBERG)
    # Référence : degré 4 sur toutes les options entre 85 et 115 %.
    dense = []
    for s in sourires:
        garde = (s["y"] > np.log(.85)) & (s["y"] < np.log(1.15))
        dense.append(np.polyfit(s["y"][garde], s["w"][garde], 4))
    dense = np.array(dense)
    # Méthode du projet : IV lue aux 5 niveaux de la grille Bloomberg par interpolation des cotations.
    iv5 = np.column_stack([100 * np.sqrt(np.interp(np.log(niveaux), np.sort(s["y"]), s["w"][np.argsort(s["y"])])
                                         / (s["jours"] / 365)) for s in sourires])
    lignes = []
    for degre in (2, 4):
        coefs, _ = lisser_sourires(niveaux, jours, iv5, zero, 0., degre)
        for j in (0, 1):
            for m in NIVEAUX_LOCALE:
                lignes.append({"echeance_jours": int(jours[j]), "niveau_K_sur_F": m, "degre": degre,
                               "vl_dense_pct": volatilite_locale(dense, jours, zero, 0., m, j),
                               "vl_5_points_pct": volatilite_locale(coefs, jours, zero, 0., m, j)})
    table = pd.DataFrame(lignes).pivot_table(index=["echeance_jours", "niveau_K_sur_F", "vl_dense_pct"],
                                             columns="degre", values="vl_5_points_pct").reset_index()
    table.columns = ["echeance_jours", "niveau_K_sur_F", "vl_dense_pct", "vl_parabole_pct", "vl_degre4_pct"]
    table["ecart_parabole_points"] = table.vl_parabole_pct - table.vl_dense_pct
    table["ecart_degre4_points"] = table.vl_degre4_pct - table.vl_dense_pct
    return table
