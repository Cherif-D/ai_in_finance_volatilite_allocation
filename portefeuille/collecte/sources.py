"""Catalogue des 29 sources du projet.

Chaque source est décrite par son chemin dans ``data/brut/`` et l'adresse de son fournisseur.
Les dépôts GitHub sont figés sur un commit : le fichier téléchargé ne peut pas changer.
"""
from collections.abc import Iterator
from datetime import datetime, timezone

from ..config import DEBUT_AMORCAGE, FIN_TELECHARGEMENT

HAMIDIEH = ("https://raw.githubusercontent.com/khamidieh/spx-options-derived-features/"
            "fd7df5847120471f8e8a1807aabc09a7581ddf7f/")


def horodatage_unix(jour: str) -> int:
    """Convertit une date ISO en secondes depuis le 1er janvier 1970 à minuit UTC (format Yahoo)."""
    return int(datetime.fromisoformat(jour).replace(tzinfo=timezone.utc).timestamp())


def sources() -> Iterator[tuple[str, str]]:
    """Énumère les 29 sources du projet.

    Retourne
    --------
    Couples ``(chemin relatif dans data/brut, adresse du fournisseur)``.
    """
    # Émetteurs des ETF : valeurs liquidatives (NAV) et distributions officielles, pour contrôle.
    yield "emetteurs/SPY_nav.xlsx", "https://www.ssga.com/library-content/products/fund-data/etfs/us/navhist-us-en-spy.xlsx"
    yield "emetteurs/IEF_fonds.xml", ("https://www.blackrock.com/varnish-api/blk-one01-product-data/product-data/"
                                      "api/v1/get-fund-document?appType=PRODUCT_PAGE&appSubType=ISHARES&targetSite=us-ishares"
                                      "&locale=en_US&portfolioId=239456&component=fundDownload&userType=individual")
    # Yahoo Finance : clôtures brutes et ajustées, distributions et divisions de parts.
    # Le symbole ^GSPC (encodé %5EGSPC) correspond à l'indice S&P 500 (SPX).
    for symbole, nom in [("SPY", "SPY"), ("IEF", "IEF"), ("%5EGSPC", "SPX")]:
        url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{symbole}"
               f"?period1={horodatage_unix(DEBUT_AMORCAGE)}&period2={horodatage_unix(FIN_TELECHARGEMENT)}"
               "&interval=1d&events=div%2Csplits&includeAdjustedClose=true")
        yield f"yahoo/{nom}.json", url
    # Cboe : indices de volatilité implicite calculés à partir des options sur le SPX.
    for symbole in ("VIX9D", "VIX", "VIX3M", "VIX6M", "SKEW"):
        yield f"cboe/{symbole}.csv", f"https://cdn.cboe.com/api/global/us_indices/daily_prices/{symbole}_History.csv"
    # Trésor américain : taux des bons à court terme (T-bills), un fichier XML par année.
    for annee in range(2011, 2026):
        yield f"treasury/bills_{annee}.xml", ("https://home.treasury.gov/resource-center/data-chart-center/"
                                               f"interest-rates/pages/xml?data=daily_treasury_bill_rates&field_tdr_date_value={annee}")
    # Variables d'options publiées par Kam Hamidieh et rendement des liquidités de Kenneth French.
    yield "hamidieh/spx.csv", HAMIDIEH + "data/spx_options_features_data_public.csv"
    yield "french/daily.zip", "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_Factors_daily_CSV.zip"
    # Surface de volatilité implicite universitaire (grille strike relatif x maturité x date).
    yield "surfaces/spx_long.npz", ("https://raw.githubusercontent.com/DusBaja/ivs-generative-benchmark/"
                                    "0102e307d3d12692b7935ec44cf7bb21eeac8c4f/data/treated/vol_surface_spx_long.npz")
    # Cotations contrat par contrat du second semestre 2022 (échantillon gratuit).
    yield "historicaldata/options_sample_2022H2.zip", "https://historicaldata.net/file/options_sample_2022H2.zip"
