"""Tests sans reseau de l'adaptateur OpenAI Responses API."""
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from core.llm import Bloc, OpenAIProvider


class _Responses:
    def __init__(self, reponse):
        self.reponse = reponse
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return self.reponse


class OpenAIProviderTests(unittest.TestCase):
    def _provider(self, reponse):
        p = OpenAIProvider.__new__(OpenAIProvider)
        p.modele = "gpt-6-astra"
        p.qualite = True
        p.client = SimpleNamespace(responses=_Responses(reponse))
        return p

    def test_appel_outil_est_adapte_pour_jarvis(self):
        sortie = SimpleNamespace(
            output_text="",
            output=[SimpleNamespace(
                type="function_call", call_id="call_42", name="allumer_lumiere",
                arguments=json.dumps({"piece": "bureau"}))],
            usage=None,
        )
        p = self._provider(sortie)
        with patch("core.cloud.enregistrer_usage"):
            rep = p.repondre(
                "Tu es Jarvis.", [{"role": "user", "content": "Allume le bureau"}],
                [{"name": "allumer_lumiere", "description": "Lumiere",
                  "input_schema": {"type": "object", "properties": {}}}],
            )
        self.assertEqual(rep.stop_reason, "tool_use")
        self.assertEqual(rep.content[0].name, "allumer_lumiere")
        self.assertEqual(rep.content[0].input, {"piece": "bureau"})
        self.assertTrue(p.client.responses.kwargs["parallel_tool_calls"])
        self.assertFalse(p.client.responses.kwargs["store"])

    def test_resultat_outil_et_capture_sont_reinjectes(self):
        p = self._provider(SimpleNamespace(output_text="Fait.", output=[], usage=None))
        historique = [
            {"role": "assistant", "content": [
                Bloc("tool_use", id="call_1", name="capture_screen", input={})]},
            {"role": "user", "content": [{
                "type": "tool_result", "tool_use_id": "call_1",
                "content": [{"type": "image", "source": {
                    "type": "base64", "media_type": "image/jpeg", "data": "YWJj"}}],
            }]},
        ]
        items = p._traduire(historique)
        self.assertEqual(items[0]["type"], "function_call")
        self.assertEqual(items[1]["type"], "function_call_output")
        self.assertTrue(items[2]["content"][0]["image_url"].startswith("data:image/jpeg;base64,"))


if __name__ == "__main__":
    unittest.main()
