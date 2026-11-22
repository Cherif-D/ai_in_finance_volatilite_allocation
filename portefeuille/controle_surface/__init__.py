"""Contrôle de la surface d'options par de vrais contrats (échantillon 2022 de HistoricalData.net).

L'échantillon contient les cotations de fin de journée des options SPX, contrat par contrat
(bid, ask, IV du fournisseur), sur 127 séances du second semestre 2022. Trop court pour
servir de variable, il sert de banc d'essai à deux vérifications :

1. ``chaines`` : extraire les contrats SPX/SPXW et recalculer l'IV à 30 jours au spot,
   pour la comparer à la surface universitaire ;
2. ``termes`` : estimer des prix à terme du SPX par la parité call-put.

Limite majeure : l'archive ne donne aucune heure de cotation.
"""
from .chaines import extraire_chaines
from .termes import estimer_termes

__all__ = ["extraire_chaines", "estimer_termes"]
