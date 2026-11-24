"""Étape 4 du cours : construction des variables explicatives et de la cible.

Trois familles :

- ``historiques`` : **A**, risque, rendement et corrélation passés du panier ;
- ``cible``       : volatilité réalisée du panier sur les 21 séances qui suivent l'exécution ;
- ``implicites``  : **B**, niveaux, asymétrie et pente de la surface d'options (Bloomberg, ou universitaire en contrôle) ;
- ``locale``      : **C**, volatilité locale de Dupire tirée de la surface Bloomberg.

Calendrier d'une observation (``s`` = séance du signal) ::

    s          signal calculé après la clôture, avec les seules données connues
    s + 1      achat du panier 60/40 à la clôture
    s + 2      premier rendement de la cible
    s + 22     dernier rendement de la cible (21 rendements au total)

Un exemple ``s`` ne peut servir à l'apprentissage qu'à partir de la séance ``s + 22``.
"""
from .cible import cible_future
from .historiques import variables_historiques
from .implicites import indicateurs_surface, interpoler_echeance
from .locale import variables_locales, volatilite_locale

__all__ = ["cible_future", "variables_historiques", "indicateurs_surface", "interpoler_echeance",
           "variables_locales", "volatilite_locale"]
