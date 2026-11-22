"""Tests reproductibles sur des données fictives, sans accès réseau.

Usage, depuis la racine du projet ::

    .venv\\Scripts\\python.exe -m unittest discover -s tests -v
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from portefeuille import controles, features, pretraitement, utilitaires  # noqa: E402
from portefeuille.collecte import telechargement  # noqa: E402


class TestCollecte(unittest.TestCase):
    """Traçabilité des téléchargements."""

    def test_fiche_tronquee_puis_reutilisation_sans_reseau(self):
        """Une fiche illisible provoque un téléchargement ; la relance réutilise le fichier."""
        with tempfile.TemporaryDirectory() as dossier:
            racine = Path(dossier)
            chemin, fiche = racine / "test.csv", racine / "test.csv.source.json"
            chemin.write_bytes(b"ancien")
            fiche.write_bytes(b'{"file":')
            source = (chemin.name, "https://example.invalid/test.csv")
            with patch.object(telechargement, "BRUT", racine), patch.object(telechargement.requests, "Session") as reseau:
                reponse = reseau.return_value.__enter__.return_value.get.return_value.__enter__.return_value
                reponse.iter_content.return_value = [b"date,prix\n2022-01-03,100\n"]
                premiere = telechargement.telecharger(source)
                self.assertEqual(telechargement.telecharger(source), premiere)
                self.assertEqual(reseau.call_count, 1)
            self.assertEqual(premiere, json.loads(fiche.read_text(encoding="utf8")))
            self.assertEqual(premiere["sha256"], utilitaires.empreinte_sha256(chemin))
            self.assertEqual(premiere["bytes"], chemin.stat().st_size)

    def test_interruption_pendant_ecriture_du_manifeste(self):
        """Une écriture qui échoue laisse intacte la version précédente."""
        with tempfile.TemporaryDirectory() as dossier:
            chemin = Path(dossier) / "sources.json"
            utilitaires.ecrire_json(chemin, ["version précédente"])
            avant = chemin.read_bytes()
            with self.assertRaises(TypeError):
                utilitaires.ecrire_json(chemin, object())
            self.assertEqual(chemin.read_bytes(), avant)
            self.assertEqual(list(chemin.parent.iterdir()), [chemin])


class TestVariablesEtCible(unittest.TestCase):
    """Calendrier de la cible et absence d'information future."""

    def setUp(self):
        self.dates = pd.bdate_range("2022-01-03", periods=30)
        # Le prix double avant l'achat, puis les deux ETF gagnent 1 % par séance.
        prix = pd.Series([50.] + [100 * 1.01 ** i for i in range(29)], index=self.dates)
        self.prix = pd.DataFrame(dict(spy_adj=prix, ief_adj=prix,
                                      spy_return=prix.pct_change(), ief_return=prix.pct_change()))

    def test_execution_et_21_rendements_futurs(self):
        """Achat en s+1, fin en s+22 ; le saut de prix avant l'achat est exclu de la cible."""
        cible = features.cible_future(self.prix)
        self.assertEqual(cible.execution.iloc[0], self.dates[1])
        self.assertEqual(cible.fin_cible.iloc[0], self.dates[22])
        self.assertAlmostEqual(cible.variance_21j_ann.iloc[0], 252 * 0.01 ** 2)
        self.assertAlmostEqual(cible.vol_21j_ann.iloc[0], (252 * 0.01 ** 2) ** 0.5)
        self.assertTrue(cible.variance_21j_ann.iloc[:-22].notna().all())
        self.assertTrue(cible.variance_21j_ann.iloc[-22:].isna().all())

    def test_variables_sans_information_future(self):
        """Modifier les rendements après une date ne change pas les variables de cette date."""
        avant = features.variables_historiques(self.prix)
        modifie = self.prix.copy()
        modifie.iloc[25:, modifie.columns.get_indexer(["spy_return", "ief_return"])] *= -3
        apres = features.variables_historiques(modifie)
        pd.testing.assert_frame_equal(avant.iloc[:25], apres.iloc[:25])
        # La variance centrée d'une série constante de rendements vaut zéro.
        self.assertAlmostEqual(avant.iloc[24].var_panier_5, 0.)


class TestCash(unittest.TestCase):
    """Rémunération des liquidités."""

    def test_taux_de_la_veille_et_jours_calendaires(self):
        """Le cash de t utilise le taux publié en t-1, sur les jours calendaires écoulés."""
        seances = pd.DatetimeIndex(["2022-01-03", "2022-01-04", "2022-01-07", "2022-01-10"])
        taux = pd.DataFrame(dict(tbill_4w_investment_pct=[3.65, 7.3, 99., 99.]), index=seances)
        cash = pretraitement.rendement_cash_tbill(taux, seances)
        self.assertTrue(np.isnan(cash.iloc[0]))                    # aucun taux connu avant la première séance
        self.assertAlmostEqual(cash.iloc[1], 0.0365 * 1 / 365)    # taux du 03/01, un jour écoulé
        self.assertAlmostEqual(cash.iloc[2], 0.073 * 3 / 365)     # taux du 04/01, trois jours écoulés
        # Le taux exceptionnel publié le 07/01 ne rémunère que la période suivante.
        self.assertAlmostEqual(cash.iloc[3], 0.99 * 3 / 365)


class TestSurface(unittest.TestCase):
    """Interpolation de la surface et contrôle de qualité."""

    def test_interpolation_variance_totale_sans_extrapolation(self):
        """Une IV constante reste constante ; hors de la grille, le résultat est manquant."""
        jours, iv = np.array([20., 40.]), np.array([15., 15.])
        self.assertAlmostEqual(features.interpoler_echeance(jours, iv, 30), 15.)
        self.assertTrue(np.isnan(features.interpoler_echeance(jours, iv, 60)))

    def test_rejet_sans_remplissage(self):
        """Une surface incohérente est vidée ; un skew faible mais une forme normale est conservé."""
        dates = pd.bdate_range("2019-05-01", periods=4)
        indicateurs = pd.DataFrame(dict(iv_30j_100spot_pct=[11., 27.8, 12., 13.],
                                        skew_30j_points=[4., 0.1, 4., 1.]), index=dates)
        diagnostics = pd.DataFrame(dict(pente_sourire_90_points=[9., 0.5, 9., 6.],
                                        cellules_sous_1pct=0), index=dates)
        vix = pd.Series([14.8, 14.4, 15., 16.], index=dates)
        propres, controle = controles.controle_qualite_surface(indicateurs, diagnostics, vix)
        self.assertEqual(controle.rejetee.tolist(), [False, True, False, False])
        self.assertTrue(propres.iloc[1].isna().all())
        self.assertEqual(propres.iloc[3].iv_30j_100spot_pct, 13.)


if __name__ == "__main__":
    unittest.main()
