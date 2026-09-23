"""Prospection web type Work : extraction LLM, dedoublonnage CRM, doctrine.

L'outil ne JAMAIS ecrire dans monday sans confirmation : les creations
partent en file d'attente (95/5). Sans LLM ni reseau, il degrade en
pipeline local sans planter.
"""
import json

import pytest

from core import registre
from tools import leads


class _Bloc:
    def __init__(self, text):
        self.type = "text"
        self.text = text


class _Reponse:
    def __init__(self, text):
        self.blocs = [_Bloc(text)]


@pytest.fixture()
def bac(monkeypatch, tmp_path):
    monkeypatch.setattr(leads, "_FICHIER", tmp_path / "leads.json")
    return monkeypatch


def test_extraire_agences_parse_le_json(bac, monkeypatch):
    class _LLM:
        def repondre(self, consigne, hist, msgs):
            return _Reponse(
                '[{"nom": "AECC Global", "site": "https://aeccglobal.com", '
                '"pays": "Australie", "email": "info@aeccglobal.com", '
                '"type": "Study agent"}]')
    monkeypatch.setattr("core.llm.llm", lambda: _LLM())
    agences = leads._extraire_agences(
        [{"title": "AECC", "body": "study abroad", "href": "https://aeccglobal.com"}])
    assert agences == [{"nom": "AECC Global", "site": "https://aeccglobal.com",
                         "pays": "Australie", "email": "info@aeccglobal.com",
                         "type": "Study agent"}]


def test_extraire_agences_repli_sans_llm(bac, monkeypatch):
    class _LLM:
        def repondre(self, *a):
            raise RuntimeError("pas de reseau")
    monkeypatch.setattr("core.llm.llm", lambda: _LLM())
    agences = leads._extraire_agences(
        [{"title": "Edvoy", "body": "study abroad platform",
          "href": "https://edvoy.com"}])
    assert agences and agences[0]["nom"] == "Edvoy"
    assert agences[0]["site"] == "https://edvoy.com"


def test_doublons_crm_ecarte_les_existants(bac, monkeypatch):
    leads.ajouter_lead(nom="Canam Consultants", entreprise="Canam Consultants")
    monkeypatch.setattr("tools.monday._tableau", lambda: None)
    nouveaux, doublons = leads._doublons_crm([
        {"nom": "Canam Consultants", "site": "", "pays": "Inde",
         "email": "", "type": "Study agent"},
        {"nom": "TGM Education", "site": "", "pays": "Nigeria",
         "email": "", "type": "Study agent"},
    ])
    assert [d["nom"] for d in doublons] == ["Canam Consultants"]
    assert [n["nom"] for n in nouveaux] == ["TGM Education"]


def test_cle_doublon_normalise(bac):
    assert leads._cle_doublon("  Canam   Consultants! ") == "canam consultants"
    assert leads._cle_doublon("Canam Consultants") == leads._cle_doublon("canam consultants")


def test_prospection_sans_reseau_ne_plante_pas(bac, monkeypatch):
    monkeypatch.setattr(leads, "_chercher_web_brut", lambda r, m=6: [])
    assert "indisponible" in leads.prospection_leads()


def test_prospection_tout_doublon_n_ecrit_rien(bac, monkeypatch):
    leads.ajouter_lead(nom="AECC Global", entreprise="AECC Global")
    monkeypatch.setattr(
        leads, "_chercher_web_brut",
        lambda r, m=6: [{"title": "AECC Global", "body": "x",
                         "href": "https://aeccglobal.com"}])
    class _LLM:
        def repondre(self, *a):
            return _Reponse('[{"nom": "AECC Global", "site": "", "pays": "", '
                            '"email": "", "type": "Study agent"}]')
    monkeypatch.setattr("core.llm.llm", lambda: _LLM())
    monkeypatch.setattr("tools.monday._tableau", lambda: None)
    reponse = leads.prospection_leads()
    assert "deja" in reponse


def test_prospection_monday_en_file_jamais_direct(bac, monkeypatch):
    """Doctrine 95/5 : la creation monday est mise EN ATTENTE, jamais
    executee. Aucun item ne doit etre cree sans le feu vert."""
    monkeypatch.setattr(
        leads, "_chercher_web_brut",
        lambda r, m=6: [{"title": "TGM Education", "body": "agent",
                         "href": "https://tgmeducation.com"}])
    monkeypatch.setattr("tools.monday._tableau", lambda: 123456)
    monkeypatch.setattr("tools.monday._configue", lambda: True)
    crees = []

    def _requete_spy(query, variables=None):
        if "create_item" in str(query):
            crees.append(variables)
        return ({"boards": [{"items_page": {"items": []}}]}, [])

    monkeypatch.setattr("tools.monday._requete", _requete_spy)

    class _LLM:
        def repondre(self, *a):
            return _Reponse('[{"nom": "TGM Education", "site": "x", '
                            '"pays": "Nigeria", "email": "", "type": "Study agent"}]')
    monkeypatch.setattr("core.llm.llm", lambda: _LLM())
    reponse = leads.prospection_leads()
    assert crees == []                       # aucune ecriture monday directe
    assert "confirmes" in reponse
    # la creation est bien en file d'attente de confirmation
    assert registre.file_en_attente()


def test_route_prospection():
    from tools.leads import router_prospection_leads
    assert router_prospection_leads(
        "cherche-moi des nouveaux leads study abroad") == ("prospection_leads", {})
    assert router_prospection_leads(
        "trouve des agences et ajoute-les a mon crm") == ("prospection_leads", {})
    assert router_prospection_leads("lis mes mails") is None
