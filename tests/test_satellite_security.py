"""Tests de la frontière réseau du WebSocket satellite."""
import unittest
from types import SimpleNamespace

from core.satellite import _origine_locale_ou_lan, _phrase_progression


def _ws(hote, **entetes):
    return SimpleNamespace(client=SimpleNamespace(host=hote), headers=entetes)


class SatelliteSecurityTests(unittest.TestCase):
    def test_loopback_et_lan_prive_sont_acceptes(self):
        self.assertTrue(_origine_locale_ou_lan(_ws("127.0.0.1")))
        self.assertTrue(_origine_locale_ou_lan(_ws("192.168.1.42")))
        self.assertTrue(_origine_locale_ou_lan(_ws("10.0.0.8")))

    def test_adresse_publique_est_refusee(self):
        self.assertFalse(_origine_locale_ou_lan(_ws("8.8.8.8")))

    def test_reverse_proxy_est_refuse_meme_en_loopback(self):
        self.assertFalse(_origine_locale_ou_lan(
            _ws("127.0.0.1", **{"x-forwarded-for": "203.0.113.9"})))

    def test_client_sans_adresse_est_refuse(self):
        self.assertFalse(_origine_locale_ou_lan(_ws("")))

    def test_progression_est_liee_a_l_intention(self):
        self.assertEqual(_phrase_progression("Cherche les dernières nouvelles"),
                         "Je lance la recherche.")
        self.assertEqual(_phrase_progression("Quelle heure est-il ?"),
                         "Je vérifie l'heure.")
        self.assertEqual(_phrase_progression("Allume la lumière"),
                         "Je m'en occupe.")
        self.assertEqual(_phrase_progression("Explique-moi cette idée"),
                         "Mmh, je réfléchis.")


if __name__ == "__main__":
    unittest.main()
