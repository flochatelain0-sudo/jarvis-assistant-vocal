"""Tests des commandes vocales de gestes, sans ouvrir la webcam."""
import unittest
from unittest.mock import patch

from tools.gestes import (demande_calibration_gestes, demande_demo_gestes,
                           demande_mode_visio,
                           lancer_calibration_gestes, lancer_demo_gestes)


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

    def test_ordre_demo_visible_est_reconnu(self):
        self.assertTrue(demande_demo_gestes("Ouvre la démo des gestes"))
        self.assertTrue(demande_demo_gestes(
            "Lance les gestes visibles pour ma vidéo"))
        self.assertFalse(demande_demo_gestes(
            "Je parle des gestes dans ma vidéo"))

    def test_mode_visio_est_une_commande_directe(self):
        self.assertIs(demande_mode_visio(
            "Hey Jarvis, passe en mode visio"), True)
        self.assertIs(demande_mode_visio("Active le mode visio"), True)
        self.assertIs(demande_mode_visio("Quitte le mode visio"), False)
        self.assertIs(demande_mode_visio("Je parle du mode visio"), None)

    def test_commande_vocale_ouvre_la_calibration_locale(self):
        with patch("core.gestes.lancer_calibration",
                   return_value="Calibration ouverte.") as lancer:
            self.assertEqual(lancer_calibration_gestes(), "Calibration ouverte.")
        lancer.assert_called_once_with()

    def test_commande_vocale_ouvre_la_demo_active(self):
        with patch("core.gestes.demarrer_demo",
                   return_value="Démo active.") as lancer:
            self.assertEqual(lancer_demo_gestes(), "Démo active.")
        lancer.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
