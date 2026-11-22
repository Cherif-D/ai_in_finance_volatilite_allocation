"""Collecte des sources brutes : catalogue des fournisseurs et téléchargements traçables.

- ``sources``        : liste des 29 fichiers à télécharger et leurs adresses ;
- ``telechargement`` : téléchargement contrôlé, fiche de traçabilité et inventaire global.
"""
from .sources import sources
from .telechargement import collecter_tout, fiche_valide, telecharger

__all__ = ["sources", "collecter_tout", "fiche_valide", "telecharger"]
