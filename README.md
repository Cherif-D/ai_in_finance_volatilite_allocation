# Prévoir le risque d'un portefeuille 60/40 grâce aux options, pour piloter son allocation

---

# 1. Informations sur le projet

- **Titre du projet :** Prévision de la volatilité d'un panier 60 % SPY / 40 % IEF et allocation pilotée par le risque
- **Nom du groupe :** [à compléter]
- **Membres du groupe :**
  - Mamadou Cherif DIALLO
  - [à compléter]
  - [à compléter]
- **Cours :** AI In Finance
- **Enseignants :** Nicolas De Roux et Mohamed EL FAKIR
- **Date de rendu :** 6 décembre 2026

---

# 2. Description du projet

Un investisseur détient un panier composé à 60 % d'actions américaines (l'ETF **SPY**, qui suit le S&P 500) et à 40 % d'obligations du Trésor américain à 7–10 ans (l'ETF **IEF**). Il veut que son portefeuille garde un risque à peu près constant, autour de **8 % de volatilité par an** : quand il s'attend à un marché agité, il investit moins et place le reste en liquidités (*cash*, rémunéré au taux des bons du Trésor).

Toute la difficulté est de **prévoir le risque du mois qui vient**. Le passé récent en dit beaucoup, mais les **prix des options** sur le S&P 500 contiennent aussi ce que le marché anticipe (la *volatilité implicite*, dont le VIX est la mesure la plus connue). On peut aussi en tirer une lecture plus fine, la *volatilité locale* de Dupire, qui découpe ce risque attendu selon la date et le niveau de l'indice. Les deux sont calculées à partir d'une surface de volatilité implicite du S&P 500 extraite de Bloomberg (2012–2025).

**Question de recherche :** les informations tirées des options améliorent-elles la prévision du risque à 21 séances du panier, et la performance nette de l'allocation qui s'en sert, par rapport aux seules données historiques ?

Ce problème intéresse les gérants de fonds diversifiés, de fonds à volatilité cible et tout investisseur qui veut limiter ses pertes en crise (2020, 2022).

---

# 3. Objectif du projet

- **Ce que le modèle prévoit :** pour chaque séance *s*, la volatilité réalisée du panier sur les 21 séances suivantes, notée σ̂ₛ.
- **Ce qu'on en fait :** la part investie dans le panier vaut *a* = min(1, 8 % / σ̂ₛ). Le reste va au cash. Il n'y a jamais d'emprunt.
  - Exemple : si le modèle prévoit 16 %, on investit 8/16 = 50 % (30 % en SPY, 20 % en IEF, 50 % en cash).
- **Ce qui compte comme une réussite :**
  1. les modèles qui reçoivent les informations des options (ensemble B) prévoient mieux, hors échantillon, que ceux qui ne voient que le passé (ensemble A) ;
  2. la volatilité locale (ensemble C) apporte encore une information en plus de B ;
  3. la stratégie garde un risque proche de 8 % et perd moins en crise qu'un panier 60/40 toujours investi à 100 %.

On compare trois ensembles de variables, avec **la même cible, les mêmes dates et les mêmes modèles** : seule l'information donnée au modèle change.

| Ensemble | Ce que le modèle reçoit | État |
|---|---|---|
| **A** | le passé seul : 13 variables de risque, de rendement et de corrélation | construit |
| **B** | A + les options : 8 indicateurs tirés de la surface Bloomberg du SPX (2012–2025), ou les indices Cboe (VIX9D, VIX, VIX3M, VIX6M, SKEW) ; la surface universitaire (2017–2023) sert de contrôle | construit (fichier privé, voir plus bas) |
| **C** | B + la volatilité locale de Dupire, tirée de la même surface Bloomberg | construit (fichier privé, voir plus bas) |

---

# 4. Définition de la tâche

- **Type de tâche :** régression sur série temporelle (prévision à 21 séances).
- **Variables d'entrée :** les 13 variables historiques A, puis A + les indices Cboe, puis A + B (surface Bloomberg), puis A + B + C (section 5).
- **Variable cible :** la volatilité réalisée annualisée du panier sur les séances *s*+2 à *s*+22 (colonne `vol_21j_ann`). Les modèles apprennent son carré en logarithme, log(`variance_21j_ann`).
- **Métriques d'évaluation :**
  - prévision : MAE, RMSE, QLIKE et R² sur la période de test ;
  - allocation : volatilité réalisée de la stratégie (proche de 8 % ?), ratio de Sharpe, perte maximale (*maximum drawdown*), après 5 points de base de frais par changement de position.

---

# 5. Description des données

Les données viennent de **29 sources publiques** et de **4 classeurs Bloomberg privés**. Les sources publiques ont été téléchargées le 19 novembre 2026 et alignées sur le calendrier de la Bourse de New York. Le fichier [`data/sources.json`](data/sources.json) donne, pour chacune, l'URL, la date et une empreinte SHA-256. Le détail complet est dans [`DONNEES.md`](DONNEES.md) et dans le [document de passation](docs/pdf/Passation_donnees_et_variables.pdf) (28 pages).

## Vue d'ensemble

- **Nombre d'observations :** 3 520 séances, du 3 janvier 2012 au 31 décembre 2025 (une ligne par séance).
- **Nombre de variables :** 13 variables historiques (A), 5 indices Cboe, 8 indicateurs implicites (B) et 8 variables de volatilité locale (C).
- **Variable cible :** `vol_21j_ann`, connue pour 3 498 séances (les 22 dernières n'ont pas encore de mois futur complet).
- **Sources :** prix de Yahoo Finance (SPY, IEF, S&P 500), indices de Cboe, taux du Trésor américain, bibliothèque de Kenneth French, surface de volatilité implicite publiée par les auteurs de [ivs-generative-benchmark](https://github.com/DusBaja/ivs-generative-benchmark), surface Bloomberg du SPX et compléments (privés, quatre classeurs).

## Description des variables

Fichiers à utiliser, dans [`data/prepare/`](data/prepare/) :

| Fichier | Contenu |
|---|---|
| `variables_A.csv` | les 13 variables A, **connues** à la date de la ligne |
| `donnees_quotidiennes.csv` | 29 colonnes : prix, indices Cboe, indicateurs de la surface universitaire (contrôle de B), rendement du cash |
| `cibles_futures.csv` | la cible, **inconnue** à la date de la ligne (calculée après coup) |
| `variables_B.csv`, `variables_C.csv` | **hors dépôt** : B (8 indicateurs, mêmes noms de colonnes que la surface universitaire) et C (volatilité locale), recréés par `scripts/04_surface_bloomberg.py` à partir des classeurs Bloomberg privés |

| Variable | Description | Type |
|---|---|---|
| `var_panier_5`, `var_panier_21`, `var_panier_63` | variance annualisée du panier sur 5, 21 ou 63 séances | numérique |
| `var_spy_21`, `var_spy_63`, `var_ief_21`, `var_ief_63` | variance annualisée de SPY et d'IEF | numérique |
| `rend_panier_21`, `rend_panier_63` | rendement cumulé du panier | numérique |
| `semivar_baisse_21`, `semivar_baisse_63` | semi-variance des jours de baisse | numérique |
| `corr_spy_ief_21`, `corr_spy_ief_63` | corrélation entre SPY et IEF | numérique, entre −1 et 1 |
| `vix9d`, `vix`, `vix3m`, `vix6m`, `skew` | indices de volatilité implicite de Cboe | numérique |
| `iv_30j_{95,100,105}spot_pct`, `iv_60j_{95,100,105}spot_pct` | volatilité implicite à 30 et 60 jours, prix d'exercice à 95 %, 100 % et 105 % du cours | numérique, en % |
| `skew_30j_points` | IV à 95 % moins IV à 100 %, à 30 jours | numérique, en points |
| `pente_60j_30j_points` | IV à 60 jours moins IV à 30 jours, au cours | numérique, en points |
| `vl_{30,60}j_{95,100,105}spot_pct` | volatilité locale de Dupire aux mêmes points (C, `variables_C.csv`) | numérique, en % |
| `skew_vl_30j_points`, `pente_vl_60j_30j_points` | skew et pente de la volatilité locale (C) | numérique, en points |

## Variable cible

`vol_21j_ann` est la volatilité **réellement subie** par le panier sur les 21 séances qui suivent l'achat (fait à la clôture de *s*+1), annualisée, en décimal (0,0713 = 7,13 %). Elle sert uniquement à entraîner et à noter les modèles, jamais comme entrée. `fin_cible` donne la date à partir de laquelle elle est connue.

## Types de données

Toutes les variables sont numériques et forment une **série temporelle quotidienne**. Il n'y a ni texte ni variable catégorielle. La seule colonne booléenne, `vix9d_vix6m_diffuses`, indique si VIX9D et VIX6M étaient publiés en temps réel ce jour-là.

## Distribution des données

- **Cible asymétrique :** 7,1 % en médiane, 8,4 % en moyenne, 47,8 % au maximum (signal du 5 mars 2020, krach du Covid). D'où le passage au logarithme.
- **Variables A très corrélées entre elles :** les variances sur différentes fenêtres bougent ensemble.
- **Changement de régime :** la corrélation SPY–IEF sur 63 séances vaut −0,36 en moyenne jusqu'en 2021, puis +0,06 depuis 2022, quand actions et obligations ont baissé ensemble.
- **Premier indice :** sur tout l'échantillon, la cible est plus corrélée aux options (VIX 0,61 ; IV Bloomberg à 30 jours au cours 0,62 ; volatilité locale au cours 0,58) qu'à la volatilité passée sur 21 séances (0,53). Ce ne sont pas encore des prévisions.

## Qualité des données

- **Surface d'options :** Bloomberg couvre 2012–2025 ; 2 journées douteuses de 2022 sont écartées (3 518 séances restent). Sur 777 vraies options expirées (2015–2025), l'IV des contrats s'écarte de la surface de 0,32 point en médiane. La surface universitaire ne couvre que 2017–2023 (1 734 séances après rejet de 6 surfaces corrompues de mai 2019) ; elle s'accorde avec Bloomberg à 0,28 point près au cours.
- **Valeurs manquantes :** VIX9D et VIX6M ne sont publiés en temps réel qu'à partir du 27 novembre 2013 (avant cette date, les valeurs ont été reconstruites après coup). Les 22 dernières cibles sont vides, ainsi que B et C les 20 septembre et 27 octobre 2022 (journées rejetées). Aucun trou n'est comblé artificiellement.
- **Contrôles :** 17 tests unitaires (dont 3 sautés sans les classeurs Bloomberg privés) et un audit indépendant de 48 contrôles. Un recoupement avec de vrais contrats de 2022 trouve un écart médian de 0,55 point de volatilité avec la surface universitaire.

---

# 6. Prétraitement des données

| Étape | Pourquoi |
|---|---|
| Alignement de toutes les sources sur le calendrier NYSE, sans remplissage des trous | comparer des séances identiques sans inventer de données |
| Rendements calculés sur les cours ajustés (dividendes réinvestis) | mesurer le vrai gain de l'investisseur |
| Contrôle de qualité des deux surfaces (IV au cours au-dessus du VIX, sourire plat, arbitrage), avec rejet des journées aberrantes | éviter d'apprendre sur des données corrompues |
| B : IV lues directement sur la grille Bloomberg (30 et 60 jours ; 95, 100 et 105 %) ; sur la surface universitaire, interpolation en variance puis en variance totale | obtenir les mêmes 8 indicateurs sur les deux sources, un jour à la fois |
| C : prix à terme tiré des taux et du dividende, lissage de chaque sourire par une parabole, puis formule de Dupire (forme de Gatheral) | calculer la volatilité locale sans dériver des données bruitées |
| Construction des variables A sur des fenêtres qui se terminent le jour du signal | aucune fuite du futur |
| *À faire :* découpage chronologique avec **purge** (une cible d'apprentissage doit être terminée avant le début du test) | les cibles se chevauchent sur 21 séances : un découpage au hasard mélangerait passé et futur |
| *À faire :* mise à l'échelle calculée sur la période d'apprentissage seulement | même raison |

---

# 7. Approche de modélisation

## Modèles choisis

*Étapes 5 à 7 en cours.*

- **Références simples :** persistance (volatilité des 21 dernières séances), EWMA (RiskMetrics), GARCH(1,1).
- **Modèles d'apprentissage :** régression Ridge, forêt aléatoire, XGBoost, entraînés sur le logarithme de la variance.

## Stratégie de modélisation

- **Références d'abord :** un modèle d'apprentissage n'a d'intérêt que s'il bat la persistance et l'EWMA, qui sont déjà de bonnes prévisions.
- **Même modèle, plusieurs ensembles de variables (A, A + Cboe, A + B, A + B + C) :** c'est une expérience contrôlée qui isole l'apport des options, puis celui de la volatilité locale.
- **Découpage dans le temps :** apprentissage jusqu'à fin 2019 (avec purge), test à partir de 2020, pour tous les ensembles. En contrôle, A + B universitaire sur 2017–2023 (par exemple apprentissage 2017–2020, test 2021–2023).
- **Réglages :** choisis par validation glissante sur 2015–2019, jamais sur la période de test.

## Métriques d'évaluation

- **MAE et RMSE** sur la volatilité : l'erreur moyenne, en points de volatilité. La RMSE punit davantage les grosses erreurs.
- **QLIKE** sur la variance : la métrique de référence pour comparer des prévisions de volatilité. Elle reste fiable quand la cible est mesurée avec du bruit et punit davantage une sous-estimation du risque.
- **R²** : la part de la variation de la cible que le modèle explique.
- **Backtest :** volatilité réalisée de la stratégie, ratio de Sharpe et perte maximale, comparés au panier 60/40 toujours investi.

---

# 8. Structure du dépôt

```
├── README.md                   ce fichier
├── DONNEES.md                  sources, conventions et commandes de reproduction
├── PROJECT_GUIDELINES.md       consignes du cours
├── requirements.txt            versions exactes des bibliothèques Python
├── data/
│   ├── sources.json            manifeste des 29 téléchargements
│   ├── prepare/                données prêtes pour la modélisation (CSV)
│   └── controles/              résultats des contrôles de qualité
├── docs/
│   ├── pdf/                    document de passation (28 pages) et propositions du projet
│   └── latex/                  source du document et script de ses figures
├── notebooks/                  exploration des données (étape 2)
├── selected_approach/          modèle retenu, évaluation et backtest
├── src/                        (réservé au code de modélisation réutilisable)
├── portefeuille/               ajouté : paquet Python de collecte, prétraitement et variables
├── scripts/                    ajouté : 01_collecte, 02_preparation, 03_controle_surface, 04_surface_bloomberg
└── tests/                      ajouté : tests unitaires et audit des données
```

**Dossiers ajoutés au modèle du cours :**
- `portefeuille/` contient tout le code de préparation : collecte, prétraitement, cible, variables A, B et C, contrôles ;
- `scripts/` enchaîne ces fonctions dans l'ordre ;
- `tests/` vérifie les calculs.

Ce code est importable depuis la racine du dépôt (`from portefeuille.features import cible`).

**Fichiers absents du dépôt :**
- les données brutes (247 Mo) ;
- les deux fichiers tirés de l'échantillon d'options 2022 (`termes_indicatifs_2022S2.csv` et `controle_chaines_et_surfaces.csv`), dont le fournisseur encadre la redistribution ;
- les quatre classeurs Bloomberg (`data/brut/bloomberg/`) et ce qui en dérive (`variables_B.csv`, `variables_C.csv` et quatre fichiers de contrôle) : Bloomberg interdit leur diffusion. Ils se demandent au groupe (Cherif, ou Maxime qui les a extraits), et ne doivent jamais être committés.

Les scripts recréent les données publiques manquantes ; `scripts/04_surface_bloomberg.py` recrée B et C une fois les classeurs Bloomberg en place (voir section 9).

---

# 9. Installation

Sous Windows, avec Python 3.12 :

```powershell
git clone https://github.com/Cherif-D/ai_in_finance_volatilite_allocation.git
cd ai_in_finance_volatilite_allocation
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Les données publiques de `data/prepare/` suffisent pour explorer et modéliser A et A + indices Cboe ; B et C demandent les classeurs Bloomberg privés. Pour tout reconstruire depuis les sources (environ 250 Mo téléchargés) :

```powershell
.\.venv\Scripts\python.exe scripts/01_collecte.py
.\.venv\Scripts\python.exe scripts/02_preparation.py
.\.venv\Scripts\python.exe scripts/03_controle_surface.py
.\.venv\Scripts\python.exe tests/audit_donnees.py
# ensembles B et C : placer d'abord les classeurs Bloomberg dans data/brut/bloomberg/
.\.venv\Scripts\python.exe scripts/04_surface_bloomberg.py
```

Pour charger les données dans un notebook :

```python
import pandas as pd

def lire(nom):
    return pd.read_csv(f"data/prepare/{nom}", index_col="date", parse_dates=True)

quotidien, A, cible = lire("donnees_quotidiennes.csv"), lire("variables_A.csv"), lire("cibles_futures.csv")
B, C = lire("variables_B.csv"), lire("variables_C.csv")   # fichiers privés, à placer dans data/prepare/
```

Pour comparer les ensembles (A, A + Cboe, A + B, A + B + C), gardez les dates communes à tous : les jours disponibles diffèrent un peu. L'exemple complet, avec le découpage et la purge, est dans la section 12 du document de passation.
