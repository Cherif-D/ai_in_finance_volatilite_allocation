"""Rapprochement des cours Yahoo avec les données officielles des émetteurs."""
import pandas as pd


def controle_emetteurs(prix: pd.DataFrame, emetteurs: dict, seances: pd.DatetimeIndex) -> pd.DataFrame:
    """Rapproche les cours Yahoo des valeurs liquidatives et des distributions des émetteurs.

    La NAV (valeur des actifs du fonds par part) diffère légèrement de la clôture en Bourse ;
    un écart important signalerait une erreur de date ou d'unité.

    Paramètres
    ----------
    prix : sortie de ``pretraitement.charger_prix``.
    emetteurs : sortie de ``pretraitement.charger_emetteurs``.
    seances : séances de l'étude.
    """
    controle = prix[["spy_close", "ief_close", "ief_distribution"]].reindex(seances).copy()
    controle = controle.join(emetteurs["spy_nav"])
    controle["ief_nav"] = emetteurs["ief_nav"]
    controle["ief_distribution_emetteur"] = emetteurs["ief_distributions"].reindex(controle.index, fill_value=0.)
    return controle
