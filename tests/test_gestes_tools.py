"""Tests des commandes vocales de gestes, sans ouvrir la webcam."""
import unittest
from unittest.mock import patch

from tools.gestes import demande_calibration_gestes, lancer_calibration_gestes


class GestesToolsTests(unittest.TestCase):
    def test_ordre_explicite_est_reconnu(self):
        self.assertTrue(demande_calibration_gestes(
            "Lance l'appli calibration geste"))
        self.assertTrue(demande_calibration_gestes(
            "Peux-tu ouvrir la calibration des gestes ?"))
        self.assertTrue(demande_calibration_gestes(
            "Teste la reconnaissance de mes mains"))

    def test_question_ou_discussion_n_ouvre_pas_la_camera(self):
        self.assertFalse(demande_calibration_gestes(
            "Est-ce que la calibration des gestes existe ?"))
        self.assertFalse(demande_calibration_gestes(
            "Je parle de la reconnaissance des mains dans ma vidéo"))

    def test_commande_vocale_ouvre_la_calibration_locale(self):
        with patch("core.gestes.lancer_calibration",
                   return_value="Calibration ouverte.") as lancer:
            self.assertEqual(lancer_calibration_gestes(), "Calibration ouverte.")
        lancer.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
