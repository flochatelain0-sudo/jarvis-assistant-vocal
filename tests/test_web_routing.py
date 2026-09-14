"""Tests du routage déterministe site web / application en mode local."""
import unittest
from unittest.mock import patch

from core import registre
from tools import navigateur, systeme


class WebRoutingTests(unittest.TestCase):
    def test_browser_open_reste_expose_au_modele_local(self):
        noms = {schema["name"] for schema in registre.schemas_api(local_seulement=True)}
        self.assertIn("browser_open", noms)
        self.assertNotIn("browser_interact", noms)

    def test_noms_et_domaines_connus_sont_normalises(self):
        self.assertEqual(navigateur._resoudre_cible("Netflix"),
                         "https://www.netflix.com")
        self.assertEqual(navigateur._resoudre_cible("netflix.com"),
                         "https://netflix.com")
        self.assertEqual(navigateur._resoudre_cible("ouvre YouTube"),
                         "https://www.youtube.com")

    def test_ouvrir_application_reroute_netflix(self):
        with patch("tools.navigateur.browser_open", return_value="Netflix ouvert.") as ouvrir, \
                patch.object(systeme.os, "startfile") as startfile:
            resultat = systeme.ouvrir_application("netflix")

        self.assertEqual(resultat, "Netflix ouvert.")
        ouvrir.assert_called_once_with(url="netflix")
        startfile.assert_not_called()

    def test_utilitaire_windows_reste_une_application(self):
        with patch.object(systeme.os, "startfile") as startfile:
            resultat = systeme.ouvrir_application("calculatrice")

        self.assertEqual(resultat, "calculatrice lance.")
        startfile.assert_called_once_with("calc")


if __name__ == "__main__":
    unittest.main()
