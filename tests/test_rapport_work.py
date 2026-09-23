"""Moteur de rapports type Mistral Work : groupes, repli deterministe, carte.

Un rapport Work ne plante JAMAIS : sans LLM, le repli local prend le relais
et la carte console reste injectee avec les donnees locales.
"""
from core import rapport_work


class _Bloc:
    def __init__(self, text):
        self.type = "text"
        self.text = text


class _Reponse:
    def __init__(self, text):
        self.blocs = [_Bloc(text)]


def test_normaliser_groupe():
    assert rapport_work.normaliser_groupe("A TRAITER") == "reponse"
    assert rapport_work.normaliser_groupe("A REPONDRE") == "reponse"
    assert rapport_work.normaliser_groupe("ATTENTION") == "attention"
    assert rapport_work.normaliser_groupe("INFO") == "info"
    assert rapport_work.normaliser_groupe("", "attention") == "attention"
    assert rapport_work.normaliser_groupe("n'importe quoi") == "info"


def test_analyser_parse_le_json_meme_avec_texte_autour(monkeypatch):
    class _LLM:
        def repondre(self, consigne, hist, msgs):
            return _Reponse(
                'Voici le rapport :\n'
                '[{"indice": 1, "groupe": "A TRAITER", "resume": "Devis a valider", '
                '"action": "Appeler le client", "brouillon": "Bonjour..."}]')
    monkeypatch.setattr("core.llm.llm", lambda: _LLM())
    resultats = rapport_work.groupes_analyses(
        "consigne", [{"titre": "a", "contenu": "x"}], replis={0: "info"})
    assert resultats[0]["groupe"] == "A TRAITER"
    assert resultats[0]["resume"] == "Devis a valider"
    assert resultats[0]["brouillon"] == "Bonjour..."
    assert resultats[0]["repli"] == ""


def test_analyser_repli_sans_llm(monkeypatch):
    def boom(consigne, hist, msgs):
        raise RuntimeError("pas de reseau")
    class _LLM:
        def repondre(self, *a):
            raise RuntimeError("pas de reseau")
    monkeypatch.setattr("core.llm.llm", lambda: _LLM())
    resultats = rapport_work.groupes_analyses(
        "consigne", [{"titre": "a", "contenu": "x"}], replis={0: "attention"})
    assert resultats[0]["groupe"] == ""
    assert resultats[0]["repli"] == "attention"
    assert resultats[0]["resume"] == ""


def test_carte_ne_plante_jamais(monkeypatch):
    def boom(donnees):
        raise RuntimeError("console fermee")
    monkeypatch.setattr("core.operator.carte_mails", boom)
    rapport_work.carte("Titre", (("reponse", "A faire", "X"),),
                        {"reponse": [{"expediteur": "a", "objet": "b",
                                      "resume": "c", "action": "",
                                      "brouillon": ""}]})
    monkeypatch.setattr("core.operator.carte_mails", lambda d: None)
    groupes = {"info": [{"titre": "e", "contenu": "f", "resume": "g"}]}
    rapport_work.carte("Titre", (("info", "Pour info", "Y"),), groupes)


def test_carte_mappe_titre_vers_expediteur(monkeypatch):
    cartes = []
    monkeypatch.setattr("core.operator.carte_mails",
                        lambda d: cartes.append(d))
    rapport_work.carte(
        "Rapport", (("attention", "A verifier", "S"),),
        {"attention": [{"titre": "Facture Acme", "contenu": "300 EUR",
                        "resume": "Impayee 300 EUR", "action": "Relancer"}]})
    assert cartes and cartes[0]["categories"][0]["mails"][0]["expediteur"] == "Facture Acme"
