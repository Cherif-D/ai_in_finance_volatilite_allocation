"""Écritures de fichiers sûres et empreintes de contenu.

Chaque écriture passe par un fichier temporaire, puis le remplace en une seule opération.
Une interruption (erreur, coupure) laisse donc toujours lisible la version précédente,
jamais un fichier à moitié écrit.
"""
import hashlib
import json
import tempfile
from pathlib import Path

import pandas as pd


def ecrire_csv(tableau: pd.DataFrame, chemin: Path, index_label: str | None = "date") -> None:
    """Enregistre un tableau en CSV, avec dix chiffres significatifs.

    Paramètres
    ----------
    tableau : DataFrame à enregistrer.
    chemin : fichier de destination (.csv).
    index_label : nom de la colonne d'index ; ``None`` pour ne pas écrire l'index.
    """
    temporaire = chemin.with_suffix(".part")
    if index_label is None:
        tableau.to_csv(temporaire, index=False, float_format="%.10g")
    else:
        tableau.to_csv(temporaire, index_label=index_label, float_format="%.10g")
    temporaire.replace(chemin)


def ecrire_json(chemin: Path, valeur) -> None:
    """Enregistre une valeur sérialisable en JSON indenté, sans risque de fichier tronqué."""
    with tempfile.NamedTemporaryFile(dir=chemin.parent, delete=False) as f:
        temporaire = Path(f.name)
    try:
        temporaire.write_text(json.dumps(valeur, indent=2), encoding="utf8")
        temporaire.replace(chemin)
    finally:
        temporaire.unlink(missing_ok=True)


def empreinte_sha256(chemin: Path) -> str:
    """Retourne l'empreinte SHA-256 d'un fichier.

    Si un seul octet du fichier change, l'empreinte change aussi : elle permet de
    vérifier qu'un fichier brut est exactement celui qui a été téléchargé.
    """
    with chemin.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()
