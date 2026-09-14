"""Tests du registre local du Command Center Hermes, sans appel a Hermes."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import deleguer_a_hermes as hermes


class HermesTaskRegistryTests(unittest.TestCase):
    def test_session_auto_unique_et_persistance(self):
        with tempfile.TemporaryDirectory() as dossier:
            fichier = Path(dossier) / "taches.json"
            with patch.object(hermes, "_FICHIER_TACHES", fichier), \
                    patch.object(hermes, "_TACHES", []), \
                    patch.object(hermes, "_pousser_hud"):
                tache = hermes._ajouter_tache("", "Analyse le budget du mois")
                self.assertTrue(tache["session"].startswith("jarvis-analyse-le-budget"))
                hermes._finir_tache(tache, "terminee", resume="Fait",
                                    tokens=1234, cout=0.0123,
                                    modele="modele-test")
                stock = json.loads(fichier.read_text(encoding="utf-8"))
                self.assertEqual(stock[0]["statut"], "terminee")
                self.assertEqual(stock[0]["cout"], 0.0123)
                self.assertEqual(stock[0]["tokens"], 1234)


if __name__ == "__main__":
    unittest.main()
