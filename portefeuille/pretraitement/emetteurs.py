"""Données officielles des émetteurs des ETF (State Street pour SPY, iShares pour IEF)."""
import re
from xml.etree import ElementTree

import pandas as pd
from openpyxl import load_workbook

from ..config import BRUT


def charger_emetteurs() -> dict:
    """Lit les données officielles des émetteurs, utilisées uniquement comme contrôle.

    Retourne
    --------
    Dictionnaire avec ``spy_nav`` (tableau des valeurs liquidatives de SPY, State Street),
    ``ief_nav`` (valeurs liquidatives d'IEF, iShares) et ``ief_distributions`` (montants
    distribués par part, rattachés à la date de détachement).
    """
    classeur = load_workbook(BRUT / "emetteurs/SPY_nav.xlsx", read_only=True, data_only=True)
    lignes_nav = list(classeur.active.values)[4:]
    classeur.close()
    spy = pd.DataFrame([(ligne[0], ligne[1]) for ligne in lignes_nav], columns=["date", "spy_nav"])
    spy["date"] = pd.to_datetime(spy.date, format="%d-%b-%Y", errors="coerce")
    # Le fichier iShares est un XML de tableur ; ses liens contiennent des « & » non échappés.
    contenu = (BRUT / "emetteurs/IEF_fonds.xml").read_bytes()
    xml = re.sub(rb"&(?!#\d+;|#x[\dA-Fa-f]+;|amp;|lt;|gt;|quot;|apos;)", b"&amp;", contenu)
    feuilles = {next(iter(f.attrib.values())): f for f in ElementTree.fromstring(xml).findall("{*}Worksheet")}

    def lire_feuille(nom: str) -> pd.DataFrame:
        """Retourne une feuille ; la première ligne donne les colonnes, on garde les lignes complètes."""
        lignes = [[c.text for c in ligne.findall(".//{*}Data")] for ligne in feuilles[nom].findall(".//{*}Row")]
        return pd.DataFrame([r for r in lignes[1:] if len(r) == len(lignes[0])], columns=lignes[0])

    nav = lire_feuille("Historical")
    nav.index = pd.to_datetime(nav["As Of"], format="%b %d, %Y", errors="coerce")
    distributions = lire_feuille("Distributions")
    distributions.index = pd.to_datetime(distributions["Ex-Date"], format="%b %d, %Y", errors="coerce")
    return dict(
        spy_nav=spy.dropna().set_index("date"),
        ief_nav=pd.to_numeric(nav["NAV per Share"], errors="coerce").dropna(),
        ief_distributions=pd.to_numeric(distributions["Total Distribution"], errors="coerce")
        .dropna().groupby(level=0).sum(),
    )
