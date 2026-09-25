"""Mode texte (jarvis_texte.py) : boucle vocale remplacee par le clavier.

Verifie la logique du REPL sans materiel audio, sans LLM, sans serveur :
le demarrage (registre, memoire, parleur console) et les trois detours du
main loop — quit, confirmation oui/toujours d'une action N2/N3 en attente,
et le passage au pipeline ecrit (traiter_ecrit). jarvis14 est mocke entierement
pour ne rien charger (openWakeWord, Whisper, Ollama...)."""

import io
import unittest
from unittest import mock


class JarvizTexteTests(unittest.TestCase):
    def setUp(self):
        import sys
        # jarvis14 importe sounddevice/numpy/openwakeword : on ne l'importe
        # JAMAIS reellement dans les tests, tout passe par des mocks. Chaque
        # test repart d'un jarvis_texte vierge, sinon le module deja importe
        # garderait la reference au mock du test precedent.
        self.jarvis = mock.MagicMock()
        self.jarvis.SENTINEL_CONFIRM = "sentinel"
        sys.modules["jarvis14"] = self.jarvis
        sys.modules["core.llm"] = mock.MagicMock()
        sys.modules.pop("jarvis_texte", None)

    def tearDown(self):
        import sys
        sys.modules.pop("jarvis14", None)
        sys.modules.pop("core.llm", None)
        sys.modules.pop("jarvis_texte", None)

    def _lancer(self, lignes):
        """Lance main() avec les lignes tapees ; renvoie la sortie console."""
        import jarvis_texte
        with mock.patch("builtins.input", side_effect=lignes):
            sortie = io.StringIO()
            with mock.patch("sys.stdout", sortie):
                try:
                    jarvis_texte.main()
                except StopIteration:
                    pass                      # input() epuise : fin de session
            return sortie.getvalue()

    def test_quit_arrete_proprement(self):
        self.jarvis.memoire.charger.return_value = {}
        with mock.patch("core.llm.llm") as llm:
            llm.return_value.disponible.return_value = True
            llm.return_value.nom = "Test"
            sortie = self._lancer(["quit"])
        self.assertIn("Au revoir", sortie)
        self.jarvis.demarrer_drain_ecrit.assert_called_once()

    def test_ligne_vide_ignored(self):
        self.jarvis.memoire.charger.return_value = {}
        with mock.patch("core.llm.llm") as llm:
            llm.return_value.disponible.return_value = True
            sortie = self._lancer(["", "  ", "exit"])
        self.assertIn("Au revoir", sortie)
        self.jarvis.traiter_ecrit.assert_not_called()

    def test_phrase_passee_au_pipeline_ecrit(self):
        self.jarvis.memoire.charger.return_value = {"facts": ["quelque chose"]}
        self.jarvis.traiter_ecrit.return_value = ("Voila.", "")
        with mock.patch("core.llm.llm") as llm:
            llm.return_value.disponible.return_value = True
            self._lancer(["quelle heure est-il", "quit"])
        self.jarvis.traiter_ecrit.assert_called_once()
        args = self.jarvis.traiter_ecrit.call_args[0]
        self.assertEqual(args[0], "quelle heure est-il")

    def test_reponse_vide_devient_c_est_fait(self):
        self.jarvis.memoire.charger.return_value = {}
        self.jarvis.traiter_ecrit.return_value = ("", "")
        with mock.patch("core.llm.llm") as llm:
            llm.return_value.disponible.return_value = True
            sortie = self._lancer(["fais quelque chose", "quit"])
        self.assertIn("C'est fait.", sortie)

    def test_oui_confirme_une_action_en_attente(self):
        from core import registre
        self.jarvis.memoire.charger.return_value = {}
        self.jarvis.traiter_ecrit.return_value = ("", "")
        with mock.patch("core.llm.llm") as llm, \
             mock.patch.object(registre, "file_en_attente",
                                return_value=True), \
             mock.patch.object(registre, "executer_confirme",
                               return_value="Fait.") as confirme:
            llm.return_value.disponible.return_value = True
            sortie = self._lancer(["oui", "quit"])
        confirme.assert_called_once_with(memoriser=False)
        self.assertIn("Fait.", sortie)
        self.jarvis.traiter_ecrit.assert_not_called()

    def test_oui_toujours_memorise_l_autorisation(self):
        from core import registre
        self.jarvis.memoire.charger.return_value = {}
        with mock.patch("core.llm.llm") as llm, \
             mock.patch.object(registre, "file_en_attente",
                                return_value=True), \
             mock.patch.object(registre, "executer_confirme",
                               return_value="Fait.") as confirme:
            llm.return_value.disponible.return_value = True
            self._lancer(["oui, toujours", "quit"])
        confirme.assert_called_once_with(memoriser=True)

    def test_oui_sans_action_en_attente_passe_au_pipeline(self):
        from core import registre
        self.jarvis.memoire.charger.return_value = {}
        self.jarvis.traiter_ecrit.return_value = ("D'accord.", "")
        with mock.patch("core.llm.llm") as llm, \
             mock.patch.object(registre, "file_en_attente",
                                return_value=False):
            llm.return_value.disponible.return_value = True
            self._lancer(["oui", "quit"])
        self.jarvis.traiter_ecrit.assert_called_once()

    def test_llm_indisponible_affiche_l_avertissement(self):
        self.jarvis.memoire.charger.return_value = {}
        with mock.patch("core.llm.llm") as llm:
            llm.return_value.disponible.return_value = False
            llm.return_value.nom = "Ollama"
            sortie = self._lancer(["quit"])
        self.assertIn("ATTENTION", sortie)
        self.assertIn("Ollama", sortie)


if __name__ == "__main__":
    unittest.main()
