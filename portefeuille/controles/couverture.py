"""Couverture de chaque source par rapport au calendrier des séances."""
import pandas as pd


def couverture_calendrier(series: list[tuple[str, pd.Series]],
                          seances: pd.DatetimeIndex) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Mesure la couverture de chaque source par rapport aux séances de l'étude.

    Les trous ne sont comptés qu'entre la première et la dernière observation de la source,
    pour ne pas compter comme manquantes les dates antérieures à son lancement.

    Paramètres
    ----------
    series : couples (nom de la source, série datée).
    seances : séances de l'étude.

    Retourne
    --------
    couverture : une ligne par source (début, fin, séances couvertes, trous, dates hors séance) ;
    ecarts : une ligne par date manquante (``absent``) ou hors séance (``hors_seance``).
    """
    couverture, ecarts = [], []
    for nom, serie in series:
        s = serie.loc["2012":].dropna()
        actives = seances[(seances >= s.index.min()) & (seances <= s.index.max())]
        manquantes = actives.difference(s.index)
        hors_seance = s.index.difference(seances)
        couverture.append(dict(source=nom, start=s.index.min().date(), end=s.index.max().date(),
                               trading_dates=len(s.index.intersection(seances)),
                               missing_inside=len(manquantes), outside_calendar=len(hors_seance)))
        for motif, jours in [("absent", manquantes), ("hors_seance", hors_seance)]:
            ecarts.extend(dict(source=nom, date=jour.date(), reason=motif) for jour in jours)
    return pd.DataFrame(couverture), pd.DataFrame(ecarts)
