"""Paramètres communs : chemins, calendrier boursier et conventions du protocole.

Chaque constante de ce module fixe une hypothèse du projet. Elles sont regroupées ici
pour être lues, discutées et modifiées en un seul endroit, puis réutilisées partout.

Conventions d'unités
--------------------
- rendements, variances et volatilités calculés : en décimal (0,01 = 1 %) ;
- volatilités implicites (VIX, surface) : en pourcentage, comme publiées (20 = 20 %) ;
- écarts entre volatilités implicites : en points de volatilité.

Annualisation : une variance quotidienne v devient 252 · v par an, et une volatilité
quotidienne σ devient √252 · σ.
"""
from pathlib import Path

import exchange_calendars as xc
import pandas as pd

# --------------------------------------------------------------------------------------
# Chemins
# --------------------------------------------------------------------------------------
RACINE = Path(__file__).resolve().parents[1]
DONNEES = RACINE / "data"
BRUT = DONNEES / "brut"            # fichiers tels que publiés par les fournisseurs
PREPARE = DONNEES / "prepare"      # tableaux calculés, prêts pour l'exploration et les modèles
CONTROLES = DONNEES / "controles"  # journaux de vérification

# --------------------------------------------------------------------------------------
# Période d'étude et calendrier
# --------------------------------------------------------------------------------------
# Les prix commencent en août 2011 : la première séance étudiée (3 janvier 2012) dispose
# ainsi de plus de 63 séances passées pour calculer les fenêtres historiques les plus longues.
DEBUT_AMORCAGE = "2011-08-01"
FIN_ETUDE = "2025-12-31"
FIN_TELECHARGEMENT = "2026-01-01"  # borne exclusive des requêtes de prix
ANNEE_DEBUT_ETUDE = 2012

# Calendrier officiel des séances de la Bourse de New York (NYSE). C'est la référence
# sur laquelle toutes les sources sont alignées ; aucune séance manquante n'est comblée.
SEANCES = xc.get_calendar("XNYS", start=DEBUT_AMORCAGE, end=FIN_ETUDE).sessions
ETUDE = SEANCES[SEANCES.year >= ANNEE_DEBUT_ETUDE]

# --------------------------------------------------------------------------------------
# Portefeuille et cible de prévision
# --------------------------------------------------------------------------------------
POIDS_SPY = .6           # poche actions du panier
POIDS_IEF = .4           # poche obligations du panier
HORIZON = 21             # nombre de rendements futurs dans la cible (environ un mois boursier)
SEANCES_PAR_AN = 252     # convention d'annualisation des variances
FENETRES_PANIER = (5, 21, 63)  # fenêtres historiques de la variance du panier
FENETRES = (21, 63)            # fenêtres des autres variables historiques

# --------------------------------------------------------------------------------------
# Options : indicateurs implicites et contrôles de qualité
# --------------------------------------------------------------------------------------
ECHEANCES_SURFACE = (30, 60)          # jours calendaires
NIVEAUX_SURFACE = (.95, 1., 1.05)     # prix d'exercice rapporté au niveau du SPX

# Première séance où le VIX9D (lancé le 1er octobre 2013) et le VIX6M (lancé le
# 27 novembre 2013) étaient tous deux publiés. Les valeurs antérieures sont rétropolées.
DIFFUSION_VIX9D_VIX6M = pd.Timestamp("2013-11-27")

# Seuils de rejet d'une surface, en points de volatilité. Hors des journées corrompues de
# mai 2019, l'IV à la monnaie reste toujours sous le VIX (écart maximal -0,85 point) et la
# pente du sourire IV(90 %) - IV(100 %) ne descend jamais sous 3,07 points.
SEUIL_ECART_VIX = 5.
SEUIL_PENTE_SOURIRE = 2.
