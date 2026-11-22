"""Téléchargement contrôlé et traçabilité des sources brutes.

Chaque fichier est enregistré dans ``data/brut/`` tel que publié, avec une fiche voisine
``<fichier>.source.json`` : adresse, taille, date de téléchargement (UTC) et empreinte
SHA-256. Une relance réutilise un fichier local dont l'empreinte correspond à sa fiche,
ce qui rend la collecte reproductible et vérifiable.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
import json
import tempfile

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from ..config import BRUT, DONNEES
from ..utilitaires import ecrire_json, empreinte_sha256
from .sources import sources


def fiche_valide(chemin: Path, fiche: Path, nom: str, url: str) -> dict | None:
    """Retourne la fiche d'un fichier déjà téléchargé si elle correspond exactement au fichier.

    Un fichier est réutilisé seulement si sa fiche est lisible, désigne la même adresse,
    et si sa taille et son empreinte correspondent. Sinon la fonction retourne ``None``.
    """
    try:
        info = json.loads(fiche.read_text(encoding="utf8"))
        if not isinstance(info, dict) or info.get("file") != nom or info.get("url") != url:
            return None
        recupere = datetime.fromisoformat(info["retrieved_utc"])
        if recupere.utcoffset() != timezone.utc.utcoffset(None) or info["bytes"] != chemin.stat().st_size:
            return None
        if info["sha256"] == empreinte_sha256(chemin):
            return info
    except (FileNotFoundError, KeyError, TypeError, ValueError):
        # Fiche absente, illisible ou incomplète : le fichier sera téléchargé de nouveau.
        return None
    return None


def telecharger(source: tuple[str, str]) -> dict:
    """Télécharge une source si nécessaire et retourne sa fiche de traçabilité.

    Le contenu est écrit dans un fichier temporaire, contrôlé (archive ZIP valide, pas de
    page d'erreur HTML), puis seulement alors installé comme copie de référence.

    Paramètres
    ----------
    source : couple ``(chemin relatif dans data/brut, adresse)`` produit par ``sources()``.
    """
    nom, url = source
    chemin = BRUT / nom
    fiche = chemin.with_suffix(chemin.suffix + ".source.json")
    chemin.parent.mkdir(parents=True, exist_ok=True)
    info = fiche_valide(chemin, fiche, nom, url)
    if info is not None:
        return info
    with requests.Session() as session:
        # Nouvelles tentatives en cas de serveur indisponible ou de trop nombreuses requêtes.
        session.mount("https://", HTTPAdapter(max_retries=Retry(
            total=2, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])))
        session.headers["User-Agent"] = "Mozilla/5.0 (Paris 1 academic portfolio data collection)"
        with session.get(url, stream=True, timeout=(12, 90)) as reponse:
            reponse.raise_for_status()
            with tempfile.NamedTemporaryFile(dir=chemin.parent, delete=False) as f:
                temporaire = Path(f.name)
            try:
                with temporaire.open("wb") as f:
                    # Écriture par blocs de 512 Kio : l'archive d'options n'est jamais chargée en mémoire.
                    for bloc in reponse.iter_content(512 * 1024):
                        f.write(bloc)
                with temporaire.open("rb") as f:
                    debut = f.read(100).lstrip()
                # Un site peut renvoyer une page d'erreur HTML avec un code de succès.
                if chemin.suffix == ".zip" and not debut.startswith(b"PK"):
                    raise ValueError(f"Archive invalide : {nom}")
                if not debut or debut.lower().startswith((b"<html", b"<!doctype html")):
                    raise ValueError(f"Contenu inattendu : {nom}")
                info = dict(file=nom, url=url, bytes=temporaire.stat().st_size,
                            sha256=empreinte_sha256(temporaire),
                            retrieved_utc=datetime.now(timezone.utc).isoformat())
                temporaire.replace(chemin)
                ecrire_json(fiche, info)
            finally:
                temporaire.unlink(missing_ok=True)
    print(f"{nom} : {info['bytes']:,} octets", flush=True)
    return info


def collecter_tout(paralleles: int = 5) -> list[dict]:
    """Télécharge toutes les sources et écrit l'inventaire global ``data/sources.json``.

    Paramètres
    ----------
    paralleles : nombre de téléchargements simultanés.
    """
    with ThreadPoolExecutor(max_workers=paralleles) as pool:
        fiches = list(pool.map(telecharger, sources()))
    ecrire_json(DONNEES / "sources.json", fiches)
    return fiches
