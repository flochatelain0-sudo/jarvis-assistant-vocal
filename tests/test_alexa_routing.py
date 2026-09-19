"""Tests du routage Alexa déterministe, sans connexion à Amazon."""
import unittest

from tools.alexa import _analyser_commande


class AlexaRoutingTests(unittest.TestCase):
    def test_lumieres_du_salon_passent_par_alexa(self):
        self.assertEqual(
            _analyser_commande("Allume les lumières du salon"),
            ("alexa_appareil", {"appareil": "lumieres salon", "action": "allumer"}),
        )

    def test_extinction_clim(self):
        self.assertEqual(
            _analyser_commande("Éteins la clim"),
            ("alexa_appareil", {"appareil": "clim", "action": "eteindre"}),
        )

    def test_piece_du_satellite_complete_une_lumiere_sans_piece(self):
        self.assertEqual(
            _analyser_commande("Allume la lumière", piece="cuisine"),
            ("alexa_appareil", {"appareil": "lumiere cuisine", "action": "allumer"}),
        )

    def test_piece_dite_gagne_sur_la_piece_du_satellite(self):
        self.assertEqual(
            _analyser_commande("Allume les lumières du salon", piece="cuisine"),
            ("alexa_appareil", {"appareil": "lumieres salon", "action": "allumer"}),
        )

    def test_routine_explicite(self):
        self.assertEqual(
            _analyser_commande("Lance la routine bonne nuit"),
            ("alexa_routine", {"nom": "bonne nuit"}),
        )

    def test_nom_de_routine_precharge(self):
        automations = [{"name": "Que la lumière soit", "triggers": []}]
        self.assertEqual(
            _analyser_commande("Que la lumière soit", automations=automations),
            ("alexa_routine", {"nom": "Que la lumière soit"}),
        )

    def test_commandes_non_domotiques_ne_sont_pas_detournees(self):
        self.assertIsNone(_analyser_commande("Ouvre Chrome"))
        self.assertIsNone(_analyser_commande("Arrête la musique"))
        self.assertIsNone(_analyser_commande("N'allume pas la lumière"))


if __name__ == "__main__":
    unittest.main()
