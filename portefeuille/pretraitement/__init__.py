"""Étape 3 du cours : lecture, validation et alignement de chaque source.

Chaque fonction lit un fichier brut de ``data/brut/``, vérifie sa structure et retourne un
tableau indexé par date. Règles communes :

- toutes les dates sont rapportées aux séances de la Bourse de New York ;
- une observation manquante reste manquante (aucune imputation, aucun remplissage) ;
- une anomalie de structure arrête le programme plutôt que de produire un résultat faux.

Modules : ``marches`` (ETF, SPX, indices Cboe), ``taux`` (T-bills et cash),
``options`` (surface et variables de Hamidieh), ``emetteurs`` (contrôles State Street et iShares).
"""
from .emetteurs import charger_emetteurs
from .marches import charger_indices_cboe, charger_prix, dates_new_york
from .options import charger_grille_surface, charger_hamidieh
from .taux import charger_cash_french, charger_taux_tresor, rendement_cash_tbill

__all__ = ["charger_emetteurs", "charger_indices_cboe", "charger_prix", "dates_new_york",
           "charger_grille_surface", "charger_hamidieh", "charger_cash_french",
           "charger_taux_tresor", "rendement_cash_tbill"]
