"""Extraction des contrats SPX/SPXW et recalcul de l'IV à 30 jours au niveau du spot."""
import hashlib
import io
import json
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from ..config import BRUT, SEANCES
from ..features.implicites import interpoler_echeance

COLONNES = ["contract", "underlying", "expiration", "type", "strike", "style", "quote_date",
            "bid", "ask", "quote_time", "volume", "open_interest", "underlying_close",
            "settlement_time", "iv_bid", "iv_ask", "iv", "iv_flag"]


def _iv_30j_spot(contrats: pd.DataFrame) -> float:
    """Recalcule l'IV à 30 jours au niveau du spot à partir des contrats d'une séance.

    On garde les options PM de 15 à 50 jours, valides selon ``quality_ok``, avec
    m = K / S ∈ [0,97 ; 1,03] : puts pour m ≤ 1, calls pour m > 1 (les options hors de la
    monnaie sont les plus liquides). Pour chaque échéance T, l'IV est interpolée
    linéairement en m = 1 si des prix d'exercice m₁ ≤ 1 ≤ m₂ encadrent le spot :

                                 1 − m₁
        σ(1, T) = σ(m₁, T) + ───────── · [ σ(m₂, T) − σ(m₁, T) ]
                                m₂ − m₁

    puis les échéances sont ramenées à 30 jours par interpolation de la variance totale
    (``features.interpoler_echeance``).

    Notations
    ---------
    K, S        prix d'exercice du contrat et clôture du SPX (``underlying_close``)
    m           K / S, prix d'exercice relatif ; m = 1 au niveau du spot
    m₁, m₂      niveaux des contrats qui encadrent le spot
    T           jours calendaires jusqu'à l'échéance (``dte``)
    σ(m, T)     IV du fournisseur (médiane s'il y a plusieurs contrats au même m), en %
    PM          options réglées sur la clôture du jour d'échéance (SPXW), par opposition à AM
    """
    f = contrats.loc[contrats.quality_ok & contrats.settlement_time.eq("PM") &
                     contrats.dte.between(15, 50)].copy()
    f["m"] = f.strike / f.underlying_close
    f = f[f.m.between(.97, 1.03) &
          ((f.m.le(1) & f.type.eq("put")) | (f.m.gt(1) & f.type.eq("call")))]
    par_echeance = {}
    for jours, sourire in f.groupby("dte"):
        ivs = sourire.groupby("m").iv.median().sort_index()
        if ivs.index.min() <= 1 <= ivs.index.max():
            par_echeance[jours] = np.interp(1., ivs.index, ivs.to_numpy()) * 100
    return interpoler_echeance(np.array(list(par_echeance)), np.array(list(par_echeance.values())), 30)


def extraire_chaines(destination: Path) -> pd.DataFrame:
    """Extrait les contrats SPX/SPXW de l'archive vers un Parquet, une séance à la fois.

    Chaque fichier journalier est vérifié (empreinte, date, unicité des contrats, nombre de
    lignes). Le drapeau ``quality_ok`` repère une cotation exploitable : IV positive et
    validée par le fournisseur (``iv_flag`` = 0), bid > 0, ask >= bid, échéance future,
    style européen, règlement AM ou PM.

    Paramètres
    ----------
    destination : chemin du Parquet à écrire.

    Retourne
    --------
    Une ligne par séance : nombre de contrats, de cotations valides, de prix d'exercice et
    d'échéances, et IV à 30 jours au spot recalculée (``iv30_pm_spot_pct``, en %).
    """
    resume = []
    temporaire = destination.with_suffix(".part")
    ecrivain = None
    try:
        with zipfile.ZipFile(BRUT / "historicaldata/options_sample_2022H2.zip") as z:
            manifeste = json.loads(z.read("day_by_date/manifest.json"))
            for fiche in manifeste["files"]:
                contenu = z.read("day_by_date/" + fiche["name"])
                if hashlib.sha256(contenu).hexdigest() != fiche["sha256"]:
                    raise ValueError(f"Empreinte invalide : {fiche['name']}")
                df = pd.read_csv(io.BytesIO(contenu), usecols=COLONNES, dtype={"quote_time": "string"})
                contrats = df.loc[df.underlying.isin(["SPX", "SPXW"])].copy()
                jour = pd.Timestamp(fiche["name"][:10])
                if (jour not in SEANCES or contrats.contract.duplicated().any() or
                        not contrats.quote_date.eq(str(jour.date())).all() or len(df) != fiche["rows"]):
                    raise ValueError(f"Anomalie de date, de clé ou de nombre de lignes le {jour.date()}")
                contrats["dte"] = (pd.to_datetime(contrats.expiration) - jour).dt.days  # jours calendaires
                contrats["quality_ok"] = (contrats.iv_flag.eq(0) & contrats.iv.gt(0) &
                                          contrats.bid.gt(0) & contrats.ask.ge(contrats.bid) & contrats.dte.gt(0) &
                                          contrats["style"].eq("E") & contrats.settlement_time.isin(["PM", "AM"]))
                table = pa.Table.from_pandas(contrats, preserve_index=False)
                if ecrivain is None:
                    ecrivain = pq.ParquetWriter(temporaire, table.schema, compression="zstd")
                ecrivain.write_table(table)
                resume.append(dict(date=jour, contracts=len(contrats), quality_ok=int(contrats.quality_ok.sum()),
                                   with_quote_time=int(contrats.quote_time.notna().sum()),
                                   distinct_strikes=contrats.strike.nunique(),
                                   expirations=contrats.expiration.nunique(),
                                   iv30_pm_spot_pct=_iv_30j_spot(contrats)))
    finally:
        if ecrivain is not None:
            ecrivain.close()
    temporaire.replace(destination)
    return pd.DataFrame(resume).set_index("date").sort_index()
