"""Contrôles de qualité des données.

Ces fonctions ne modifient pas les données de marché, à une exception près et documentée :
``controle_qualite_surface`` vide les surfaces jugées incohérentes. Toutes les décisions
sont enregistrées dans ``data/controles/`` pour pouvoir être relues et contestées.

Modules : ``couverture`` (calendrier), ``emetteurs`` (Yahoo contre State Street et iShares),
``surface`` (rejet des surfaces d'options incohérentes).
"""
from .couverture import couverture_calendrier
from .emetteurs import controle_emetteurs
from .surface import controle_qualite_surface

__all__ = ["couverture_calendrier", "controle_emetteurs", "controle_qualite_surface"]
