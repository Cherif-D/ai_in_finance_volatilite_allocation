"""Surface de volatilité implicite du SPX extraite de Bloomberg (ensemble C).

Le classeur ``data/brut/bloomberg/Bloomberg_SPX.xlsx`` a été extrait au terminal le
24/11/2026. Il est privé : les conditions de Bloomberg interdisent de le redistribuer, il
n'est donc pas dans le dépôt public. Conventions relevées sur le terminal (onglet
``NOTES_METADONNEES``) :

- champs ``{30DAY,60DAY,3MTH,6MTH,12MTH}_IMPVOL_{90,95,100,105,110}.0%MNY_DF`` ;
- prix d'exercice rapporté au **spot**, m = K / S ;
- échéances **constantes** en jours calendaires, interpolées par Bloomberg ;
- valeurs de **fin de journée**, moteur LIVE (Listed Implied Volatility Engine), calculé
  à partir des options cotées ;
- ``IDX_EST_DVD_YLD`` : rendement de dividende estimé du S&P 500 sur 12 mois, en %.
"""
import numpy as np
import pandas as pd
from openpyxl import load_workbook

from ..config import BLOOMBERG, BLOOMBERG_COMPLEMENTS, ECHEANCES_BLOOMBERG, NIVEAUX_BLOOMBERG, SEANCES

FEUILLES = {30: ("IV_30D", "30DAY"), 60: ("IV_60D", "60DAY"), 91: ("IV_90D", "3MTH"),
            182: ("IV_180D", "6MTH"), 365: ("IV_12M", "12MTH")}


def _nombre(valeur) -> float:
    """Convertit une cellule en nombre ; « #N/A N/A » et les cases vides deviennent manquantes."""
    return float(valeur) if isinstance(valeur, (int, float)) else np.nan


def charger_surface_bloomberg(chemin=BLOOMBERG):
    """Lit la grille Bloomberg et le rendement de dividende, puis vérifie leur structure.

    Retourne
    --------
    niveaux : tableau des prix d'exercice relatifs m = K / S (0,90 à 1,10).
    echeances : tableau des échéances en jours calendaires (30, 60, 91, 182, 365).
    dates : séances NYSE couvertes.
    cube : IV en %, de forme (niveau, échéance, date), comme ``charger_grille_surface``.
    dividende : rendement de dividende estimé en % annuel, une valeur par séance.

    Toute anomalie (champ inattendu, séance manquante ou en trop, IV hors de 1-200 %)
    arrête le programme : on ne construit pas C sur une grille douteuse.
    """
    classeur = load_workbook(chemin, read_only=True, data_only=True)
    tranches = []
    for jours in ECHEANCES_BLOOMBERG:
        feuille, prefixe = FEUILLES[jours]
        lignes = list(classeur[feuille].iter_rows(min_row=4, values_only=True))
        attendu = [f"{prefixe}_IMPVOL_{100 * m:.1f}%MNY_DF" for m in NIVEAUX_BLOOMBERG]
        if list(lignes[0][1:6]) != attendu:
            raise ValueError(f"{feuille} : champs inattendus {lignes[0][1:6]}")
        tableau = pd.DataFrame([[_nombre(v) for v in ligne[1:6]] for ligne in lignes[1:] if ligne[0] is not None],
                               index=pd.DatetimeIndex([ligne[0] for ligne in lignes[1:] if ligne[0] is not None]))
        tranches.append(tableau)

    dates = tranches[0].index
    seances = SEANCES[(SEANCES >= dates[0]) & (SEANCES <= dates[-1])]
    if any(not t.index.equals(dates) for t in tranches) or not dates.equals(seances):
        raise ValueError("Les dates Bloomberg ne correspondent pas aux séances NYSE")
    cube = np.stack([t.to_numpy().T for t in tranches], axis=1)  # (niveau, échéance, date)
    if np.isnan(cube).any() or cube.min() < 1 or cube.max() > 200:
        raise ValueError("Surface Bloomberg incomplète ou hors des bornes 1-200 %")

    lignes = list(classeur["DIV_&_FUTURES"].iter_rows(min_row=4, values_only=True))
    if lignes[0][:3] != ("Date", "PX_LAST", "IDX_EST_DVD_YLD"):
        raise ValueError("Onglet DIV_&_FUTURES inattendu")
    dividende = pd.Series({pd.Timestamp(ligne[0]): _nombre(ligne[2]) for ligne in lignes[1:] if ligne[0] is not None})
    # Le dividende est publié aussi certains jours fériés : on garde les séances, sans remplissage.
    dividende = dividende.reindex(dates).rename("dividende_estime_pct")
    if dividende.isna().any():
        raise ValueError("Rendement de dividende manquant sur une séance")
    classeur.close()  # libère le fichier (sinon il reste verrouillé sous Windows)
    return np.array(NIVEAUX_BLOOMBERG), np.array(ECHEANCES_BLOOMBERG, dtype=float), dates, cube, dividende


def charger_chaine_bloomberg(chemin=BLOOMBERG_COMPLEMENTS) -> pd.DataFrame:
    """Lit la chaîne complète des options SPX d'une seule séance (onglet ``OPT_CHAIN_JOUR``).

    Une ligne par option : racine (``SPX`` réglée le matin, ``SPXW`` le soir), prix
    d'exercice ``K``, échéance, ``type`` (Call ou Put), ``bid``, ``ask``, ``mid`` et l'IV
    calculée par Bloomberg (``iv``, en %, manquante pour certaines options très éloignées).
    Cette chaîne ne sert qu'à tester le lissage du sourire : elle ne couvre qu'un jour.
    """
    classeur = load_workbook(chemin, read_only=True, data_only=True)
    lignes = list(classeur["OPT_CHAIN_JOUR"].iter_rows(values_only=True))
    entete = next(i for i, ligne in enumerate(lignes) if ligne and ligne[0] == "Option Ticker (BDS)")
    if lignes[entete][1:8] != ("OPT_STRIKE_PX", "OPT_EXPIRE_DT", "OPT_PUT_CALL", "PX_BID", "PX_ASK", "PX_MID", "IVOL_MID"):
        raise ValueError("Onglet OPT_CHAIN_JOUR inattendu")
    chaine = pd.DataFrame(
        [(l[0].split()[0], _nombre(l[1]), pd.to_datetime(l[2], format="%d/%m/%Y"), l[3], _nombre(l[4]), _nombre(l[5]),
          _nombre(l[6]), _nombre(l[7])) for l in lignes[entete + 1:] if l[0]],
        columns=["racine", "K", "echeance", "type", "bid", "ask", "mid", "iv"])
    if not chaine.type.isin(["Call", "Put"]).all() or len(chaine) < 1000:
        raise ValueError("Chaîne d'options incomplète")
    classeur.close()
    return chaine
