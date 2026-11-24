"""Tests de la volatilité locale de Dupire (ensemble C).

Les cinq premiers tests utilisent des surfaces fictives dont on connaît la réponse exacte.
Les deux derniers relisent les vrais classeurs Bloomberg : ils sont sautés si les fichiers privés sont absents.

Usage, depuis la racine du projet ::

    .venv\\Scripts\\python.exe -m unittest discover -s tests -v
"""
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from portefeuille import controle_surface, features, pretraitement  # noqa: E402
from portefeuille.config import BLOOMBERG, BLOOMBERG_COMPLEMENTS, BLOOMBERG_OPTIONS, DATE_CHAINE_BLOOMBERG, PREPARE  # noqa: E402
from portefeuille.features import locale  # noqa: E402

NIVEAUX = np.array([.90, .95, 1., 1.05, 1.10])


def vol(iv_pct, echeances, r, q, niveau, j):
    """Lisse la surface puis renvoie la volatilité locale en un point."""
    coefs, _ = locale.lisser_sourires(NIVEAUX, echeances, iv_pct, r, q)
    return locale.volatilite_locale(coefs, echeances, r, q, niveau, j)


class TestVolatiliteLocale(unittest.TestCase):
    """Cas dont la réponse est connue à l'avance."""

    def test_surface_plate_redonne_la_volatilite_implicite(self):
        """Sans sourire ni structure par terme, σ_loc = σ, quels que soient les taux."""
        echeances, r = np.array([30., 60., 91.]), np.array([.05, .05, .05])
        iv = np.full((5, 3), 20.)
        for niveau in (.95, 1., 1.05):
            for j in (0, 1):
                self.assertAlmostEqual(vol(iv, echeances, r, .02, niveau, j), 20., places=6)

    def test_structure_par_terme_donne_la_volatilite_a_terme(self):
        """Sans sourire, σ_loc² est la variance à terme entre 30 et 60 jours."""
        echeances, r = np.array([30., 60.]), np.zeros(2)
        iv = np.tile([20., 25.], (5, 1))
        attendu = 100 * np.sqrt((.25 ** 2 * 60 - .20 ** 2 * 30) / 30)   # 29,15 %
        self.assertAlmostEqual(vol(iv, echeances, r, 0., 1., 0), attendu, places=6)

    def test_arbitrage_calendaire_donne_un_resultat_manquant(self):
        """Si le risque cumulé baisse avec l'échéance, la volatilité locale n'existe pas."""
        echeances, r = np.array([30., 60.]), np.zeros(2)
        iv = np.tile([30., 20.], (5, 1))                                # w(60) < w(30)
        self.assertTrue(np.isnan(vol(iv, echeances, r, 0., 1., 0)))

    def test_sourire_trop_creuse_donne_un_resultat_manquant(self):
        """Un sourire très concave (dénominateur négatif, arbitrage papillon) n'a pas de volatilité locale."""
        echeances, r = np.array([30., 60.]), np.zeros(2)
        coefs = np.array([[-5., 0., .004], [-5., 0., .008]])           # w(y) = −5·y² + c : courbure négative
        self.assertTrue(np.isnan(locale.volatilite_locale(coefs, echeances, r, 0., .90, 0)))

    def test_taux_continu_par_echeance(self):
        """Interpolation selon la durée, valeur constante aux bords, conversion ln(1 + y·T) / T."""
        taux = locale.taux_par_echeance(np.array([28., 59.5, 400.]), np.array([2., 3., np.nan, 4.]))
        self.assertAlmostEqual(taux[0], np.log1p(.02 * 28 / 365) / (28 / 365))
        self.assertAlmostEqual(taux[1], np.log1p(.025 * 59.5 / 365) / (59.5 / 365))   # milieu de 28 et 91 jours
        self.assertAlmostEqual(taux[2], np.log1p(.04 * 400 / 365) / (400 / 365))     # au-delà de 52 semaines
        self.assertTrue(np.isnan(locale.taux_par_echeance(np.array([30.]), np.full(4, np.nan))).all())

    def test_regle_du_double_pour_le_skew(self):
        """Près du cours, la pente de la volatilité locale vaut environ deux fois celle de l'IV."""
        echeances, r = np.array([30., 60., 91.]), np.zeros(3)
        iv = np.array([[100 * (.20 - .5 * np.log(m))] * 3 for m in NIVEAUX])
        pente_iv = iv[1, 0] - iv[2, 0]
        pente_vl = vol(iv, echeances, r, 0., .95, 0) - vol(iv, echeances, r, 0., 1., 0)
        self.assertGreater(pente_vl / pente_iv, 1.8)
        self.assertLess(pente_vl / pente_iv, 2.3)

    def test_chaque_jour_traite_seul(self):
        """Modifier la surface d'un jour ne change rien aux autres ; un jour arbitrable est vidé."""
        dates = pd.bdate_range("2022-01-03", periods=2)
        echeances = np.array([30., 60., 91., 182., 365.])
        cube = np.full((5, 5, 2), 20.)
        taux = pd.DataFrame({b[1]: 2. for b in locale.BONS}, index=dates)
        dividende = pd.Series(1.5, index=dates)
        avant, _ = locale.variables_locales(NIVEAUX, echeances, dates, cube, dividende, taux)
        cube[:, 0, 1] = 40.                                             # 30 jours très au-dessus de 60 jours
        apres, diag = locale.variables_locales(NIVEAUX, echeances, dates, cube, dividende, taux)
        pd.testing.assert_series_equal(avant.iloc[0], apres.iloc[0])
        self.assertAlmostEqual(apres.iloc[0].vl_30j_100spot_pct, 20., places=6)
        self.assertEqual(diag.rejetee.tolist(), [False, True])
        self.assertTrue(apres.iloc[1].isna().all())


@unittest.skipUnless(BLOOMBERG.exists(), "classeur Bloomberg privé absent")
class TestDonneesBloomberg(unittest.TestCase):
    """Relecture du vrai classeur : structure et exemple du 1er juillet 2022."""

    def test_structure_et_exemple_du_1er_juillet_2022(self):
        niveaux, echeances, dates, cube, dividende = pretraitement.charger_surface_bloomberg()
        self.assertEqual(cube.shape, (5, 5, 3627))
        self.assertEqual((dates[0], dates[-1]), (pd.Timestamp("2011-08-01"), pd.Timestamp("2025-12-31")))
        taux = pd.read_csv(PREPARE / "taux_bons_tresor.csv", index_col="date", parse_dates=["date"])
        jour = dates.get_loc(pd.Timestamp("2022-07-01"))
        variables, _ = locale.variables_locales(niveaux, echeances, dates[jour:jour + 1],
                                                cube[:, :, jour:jour + 1], dividende, taux)
        # B Bloomberg : la fonction de B appliquée à la grille Bloomberg lit exactement les nœuds.
        b, _ = features.indicateurs_surface(niveaux, echeances, dates[jour:jour + 1], cube[:, :, jour:jour + 1])
        self.assertAlmostEqual(b.iv_30j_100spot_pct.iloc[0], 24.5228, places=4)
        self.assertAlmostEqual(b.skew_30j_points.iloc[0], 27.3266 - 24.5228, places=4)
        self.assertAlmostEqual(variables.vl_30j_100spot_pct.iloc[0], 25.05, delta=.01)
        self.assertAlmostEqual(variables.vl_30j_95spot_pct.iloc[0], 30.58, delta=.01)


@unittest.skipUnless(BLOOMBERG_COMPLEMENTS.exists(), "second classeur Bloomberg privé absent")
class TestLissageSurChaine(unittest.TestCase):
    """La parabole sur 5 points reste proche d'une chaîne complète d'options."""

    def test_parabole_juste_au_cours_et_biais_limite_a_95(self):
        sourires = controle_surface.sourires_chaine(pretraitement.charger_chaine_bloomberg(), DATE_CHAINE_BLOOMBERG)
        test = controle_surface.comparer_lissage(sourires).set_index(["echeance_jours", "niveau_K_sur_F"])
        self.assertTrue((test.xs(1., level=1).ecart_parabole_points.abs() < .5).all())
        self.assertTrue(test.xs(.95, level=1).ecart_parabole_points.between(-2, 0).all())



@unittest.skipUnless(BLOOMBERG.exists() and BLOOMBERG_OPTIONS.exists(), "classeurs Bloomberg privés absents")
class TestContratsExpires(unittest.TestCase):
    """La surface Bloomberg redonne l'IV de vraies options expirées, à moins d'un demi-point près."""

    def test_ecart_median_faible_sur_un_mois(self):
        niveaux, echeances, dates, cube, dividende = pretraitement.charger_surface_bloomberg()
        options = controle_surface.charger_options_expirees()
        options = options[options.echeance == pd.Timestamp("2022-07-15")]     # un seul mois, pour la rapidité
        taux = pd.read_csv(PREPARE / "taux_bons_tresor.csv", index_col="date", parse_dates=["date"])
        spx = pd.read_csv(PREPARE / "prix_etf_et_spx.csv", index_col="date", parse_dates=["date"]).spx_close
        table = controle_surface.comparer_contrats_surface(options, spx, taux, niveaux, echeances, dates, cube, dividende)
        hors = table[table.hors_monnaie].ecart_points
        self.assertGreater(len(hors), 50)
        self.assertLess(hors.abs().median(), .5)


if __name__ == "__main__":
    unittest.main()
