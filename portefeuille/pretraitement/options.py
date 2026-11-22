"""Données d'options déjà agrégées : surface de volatilité implicite et variables de Hamidieh."""
import numpy as np
import pandas as pd

from ..config import BRUT


def charger_grille_surface() -> tuple[np.ndarray, np.ndarray, pd.DatetimeIndex, np.ndarray]:
    """Lit et valide la grille universitaire de volatilité implicite du SPX.

    La grille est publiée par les auteurs du dépôt ``ivs-generative-benchmark`` à partir de
    cotations OptionsDX, déjà lissées et complétées à l'intérieur de chaque journée.

    Retourne
    --------
    niveaux : prix d'exercice rapportés au SPX du jour (32 valeurs croissantes, 0,80 à 1,20) ;
    echeances : maturités en jours calendaires (16 valeurs croissantes, 7 à 365) ;
    dates : dates d'observation ;
    cube : IV en pourcentage, de dimensions niveau x échéance x date.
    """
    with np.load(BRUT / "surfaces/spx_long.npz", allow_pickle=False) as z:
        niveaux, echeances, jours, cube = (z[k] for k in ("m_grid", "tenor_days", "asof_dates", "cube"))
    dates = pd.DatetimeIndex(jours)
    if (dates.has_duplicates or not dates.is_monotonic_increasing
            or cube.shape != (len(niveaux), len(echeances), len(dates))
            or not (np.all(np.diff(niveaux) > 0) and np.all(np.diff(echeances) > 0))
            or not np.isfinite(cube).all() or (cube <= 0).any()):
        raise ValueError("Grille de surface incohérente")
    return niveaux, echeances, dates, cube


def charger_hamidieh() -> pd.DataFrame:
    """Lit les variables d'options publiées par Kam Hamidieh (2017-2025).

    Leur définition (skew moyen, prix moyen d'un straddle normalisé) est celle de l'auteur
    et diffère de nos propres indicateurs ; leur heure de disponibilité n'est pas documentée.
    """
    tableau = pd.read_csv(BRUT / "hamidieh/spx.csv", parse_dates=["date"]).set_index("date")
    if tableau.index.has_duplicates:
        raise ValueError("Date répétée dans les variables de Hamidieh")
    return tableau
