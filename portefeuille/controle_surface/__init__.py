"""Contrôle de la surface d'options par de vrais contrats (échantillon 2022 de HistoricalData.net).

L'échantillon contient les cotations de fin de journée des options SPX, contrat par contrat
(bid, ask, IV du fournisseur), sur 127 séances du second semestre 2022. Trop court pour
servir de variable, il sert de banc d'essai à deux vérifications :

1. ``chaines`` : extraire les contrats SPX/SPXW et recalculer l'IV à 30 jours au spot,
   pour la comparer à la surface universitaire ;
2. ``termes`` : estimer des prix à terme du SPX par la parité call-put ;
3. ``lissage`` : sur la chaîne complète d'une séance Bloomberg, mesurer ce que coûte le lissage
   des 5 points de la surface avant Dupire ;
4. ``contrats`` : sur 777 vraies options expirées (2015-2025), vérifier la surface Bloomberg.

Limite majeure : l'archive ne donne aucune heure de cotation.
"""
from .chaines import extraire_chaines
from .contrats import charger_options_expirees, comparer_contrats_surface
from .lissage import comparer_lissage, sourires_chaine
from .termes import estimer_termes

__all__ = ["extraire_chaines", "estimer_termes", "comparer_lissage", "sourires_chaine",
           "charger_options_expirees", "comparer_contrats_surface"]
