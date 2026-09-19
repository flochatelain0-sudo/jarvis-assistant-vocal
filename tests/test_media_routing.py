"""Tests hors réseau du routage média direct, sans Astra."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from core import registre
from tools import media, spotify


class MediaRoutingTests(unittest.TestCase):
    def test_commandes_transport_utilisent_les_touches_media(self):
        cas = {
            "Hey Jarvis, change de musique": "suivant",
            "musique précédente": "precedent",
            "mets en pause": "pause",
            "reprends la musique": "pause",
        }
        for phrase, action in cas.items():
            with self.subTest(phrase=phrase):
                self.assertEqual(
                    media.router_commande_media(phrase),
                    ("controler_media", {"action": action}),
                )

    def test_playlist_et_titre_spotify_sont_routes_sans_astra(self):
        self.assertEqual(
            media.router_commande_media("Lance ma playlist Chill sur Spotify"),
            ("lire_spotify", {"recherche": "chill", "type_media": "playlist"}),
        )
        self.assertEqual(
            media.router_commande_media("Joue Blinding Lights sur Spotify"),
            ("lire_spotify", {
                "recherche": "blinding lights", "type_media": "titre"}),
        )

    def test_serie_netflix_est_routee_sans_astra(self):
        self.assertEqual(
            media.router_commande_media("Lance la série Arcane sur Netflix"),
            ("lire_netflix", {"titre": "arcane"}),
        )

    def test_alexa_et_les_phrases_discursives_ne_sont_pas_detournees(self):
        for phrase in (
                "Mets la musique sur Alexa",
                "Est-ce que tu connais ma playlist Chill ?",
                "J'aimerais parler de la série Arcane sur Netflix"):
            with self.subTest(phrase=phrase):
                self.assertIsNone(media.router_commande_media(phrase))

    def test_outils_media_ne_demandent_pas_confirmation(self):
        for nom in ("controler_media", "lire_spotify", "lire_netflix"):
            with self.subTest(nom=nom):
                outil = registre.get(nom)
                self.assertIsNotNone(outil)
                self.assertFalse(outil.confirmation)
                self.assertEqual(registre.niveau(nom), "N1")

    def test_spotify_connect_lance_le_resultat_exact(self):
        with patch("tools.spotify._configure", return_value=True), \
                patch("tools.spotify._chercher_media", return_value={
                    "uri": "spotify:track:abc", "name": "Blinding Lights"}), \
                patch("tools.spotify._demarrer_lecture",
                      return_value=SimpleNamespace(status_code=204)), \
                patch.object(spotify.os, "startfile") as startfile:
            resultat = spotify.lire_spotify("Blinding Lights")

        self.assertEqual(resultat, "Je lance « Blinding Lights » sur Spotify.")
        startfile.assert_not_called()

    def test_spotify_sans_oauth_ouvre_une_recherche_locale(self):
        with patch("tools.spotify._configure", return_value=False), \
                patch.object(spotify.os, "startfile") as startfile:
            resultat = spotify.lire_spotify("Daft Punk")

        self.assertIn("recherche Spotify", resultat)
        startfile.assert_called_once_with("spotify:search:Daft%20Punk")

    @patch("tools.media.time.sleep")
    @patch("tools.navigateur.browser_interact", return_value="C'est clique.")
    @patch("tools.navigateur.browser_open", return_value="Netflix ouvert.")
    def test_netflix_ouvre_et_tente_une_action_bornee(
            self, ouvrir, interagir, _sleep):
        resultat = media.lire_netflix("Arcane")

        self.assertEqual(resultat, "Je lance « Arcane » sur Netflix.")
        ouvrir.assert_called_once_with(
            url="https://www.netflix.com/search?q=Arcane")
        self.assertIn("Netflix uniquement", interagir.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
