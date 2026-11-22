"""Prix à terme indicatifs du SPX par la parité call-put."""
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq


def _facteurs_actualisation(taux: pd.Series) -> dict[int, float]:
    """Construit les facteurs d'actualisation à partir des T-bills d'une date.

    Le taux d'escompte bancaire d (en % annuel, base 360) donne le prix aujourd'hui d'un
    dollar payé dans T jours calendaires :

                     d       T
        D(T) = 1 − ───── · ─────          D(0) = 1
                    100     360

    Notations
    ---------
    T           durée jusqu'à l'échéance du bon, en jours calendaires
    d           taux d'escompte bancaire du T-bill, en % annuel (convention 360 jours)
    D(T)        facteur d'actualisation : valeur aujourd'hui de 1 $ payé dans T jours

    La date de valeur est approchée par la date d'observation.
    """
    noeuds = {0: 1.}
    for semaines in (4, 8, 13, 26, 52):
        duree = (pd.to_datetime(taux[f"tbill_{semaines}w_maturity"]) - taux.name).days
        d = taux[f"tbill_{semaines}w_discount_pct"]
        if pd.notna(d) and duree > 0:
            noeuds[duree] = 1 - d / 100 * duree / 360
    return noeuds


def estimer_termes(chaines: Path, taux: pd.DataFrame) -> pd.DataFrame:
    """Estime le prix à terme du SPX par la parité call-put, par séance et échéance.

    Pour un call C et un put P européens de même échéance T et de même prix d'exercice K,
    la parité C − P = D(T) · (F − K) donne :

                 C − P                   C_bid − P_ask                   C_ask − P_bid
        F = K + ───────     F_bas = K + ───────────────     F_haut = K + ───────────────
                  D(T)                       D(T)                            D(T)

    Le facteur D(T) est interpolé linéairement en logarithme entre deux échéances de T-bills,
    ln D(T) = (1 − λ) · ln D(T₁) + λ · ln D(T₂). Par échéance, le prix à terme retenu est la
    médiane des milieux (F_bas + F_haut) / 2 sur au moins trois paires. On retient les options
    SPXW européennes PM de 15 à 95 jours, à 98-102 % du spot, avec bid > 0 et ask ≥ bid.

    Notations
    ---------
    C, P            prix d'un call et d'un put de même échéance et même strike, en points
    C_bid, C_ask    prix auxquels le marché achète (bid) et vend (ask) le call ; idem pour P
    K               prix d'exercice commun, en points d'indice
    T               jours calendaires jusqu'à l'échéance des options
    D(T)            facteur d'actualisation à T jours, tiré des T-bills
    T₁, T₂, λ       échéances de T-bills encadrant T et poids d'interpolation
    F               prix à terme du SPX pour l'échéance T, en points d'indice
    F_bas, F_haut   bornes de F compatibles avec les fourchettes bid/ask

    Paramètres
    ----------
    chaines : Parquet produit par ``extraire_chaines``.
    taux : taux des T-bills (``pretraitement.charger_taux_tresor`` ou son CSV).

    Retourne
    --------
    Une ligne par séance et échéance : prix à terme indicatif, dispersion (quartiles) et
    largeur médiane de fourchette, en points d'indice.
    """
    fichier = pq.ParquetFile(chaines)
    resultat = []
    for i in range(fichier.num_row_groups):  # un groupe de lignes = une séance
        contrats = fichier.read_row_group(i, columns=["contract", "quote_date", "expiration", "settlement_time",
                                                      "strike", "bid", "ask", "underlying_close", "type",
                                                      "dte", "style"]).to_pandas()
        jour = pd.Timestamp(contrats.quote_date.iloc[0])
        dernier_taux = taux.loc[:jour].iloc[-1]  # dernier taux connu à la date de la séance
        noeuds = _facteurs_actualisation(dernier_taux)
        durees = np.array(sorted(noeuds))
        masque = (contrats.contract.str.match(r"^SPXW\d") & contrats.settlement_time.eq("PM") &
                  contrats["style"].eq("E") & contrats.dte.between(15, 95) & contrats.bid.gt(0) &
                  contrats.ask.ge(contrats.bid) & (contrats.strike / contrats.underlying_close).between(.98, 1.02))
        filtres = contrats.loc[masque]
        calls, puts = filtres.loc[filtres.type.eq("call")], filtres.loc[filtres.type.eq("put")]
        paires = calls.merge(puts, on=["expiration", "strike", "dte"], suffixes=("_c", "_p"), validate="one_to_one")
        for (echeance, horizon), groupe in paires.groupby(["expiration", "dte"]):
            if len(groupe) < 3 or horizon > durees[-1]:
                continue
            # Interpolation linéaire des logarithmes des facteurs entre deux échéances de T-bills.
            actualisation = np.exp(np.interp(horizon, durees, np.log([noeuds[t] for t in durees])))
            bas = groupe.strike + (groupe.bid_c - groupe.ask_p) / actualisation
            haut = groupe.strike + (groupe.ask_c - groupe.bid_p) / actualisation
            milieu = (bas + haut) / 2
            resultat.append(dict(date=jour.date(), expiration=echeance, dte=horizon,
                                 date_taux=dernier_taux.name.date(), facteur_tbill_approx=actualisation,
                                 paires=len(groupe), forward_indicatif=milieu.median(),
                                 q25=milieu.quantile(.25), q75=milieu.quantile(.75),
                                 largeur_fourchette_mediane_points=(haut - bas).median()))
    return pd.DataFrame(resultat)
