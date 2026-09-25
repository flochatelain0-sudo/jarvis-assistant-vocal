"""Tests pipeline leads : stockage reel, ICP, etats, relances dues, N3 envoi."""

import json

import pytest

from tools import leads


@pytest.fixture()
def bac(tmp_path, monkeypatch):
    monkeypatch.setattr(leads, "_FICHIER", tmp_path / "leads.json")
    return tmp_path


def test_enregistres():
    from core import registre
    registre.charger_outils()
    assert registre.niveau("ajouter_lead") == "N1"
    assert registre.niveau("rediger_message_lead") == "N1"
    assert registre.niveau("envoyer_message_linkedin") == "N3"


def test_ajout_et_doublon(bac):
    reponse = leads.ajouter_lead("Marie Dupont", "Acme", "CEO", "rencontre au salon")
    assert "ajoute" in reponse.lower() or "ajouté" in reponse.lower()
    doublon = leads.ajouter_lead("marie dupont", "Acme")
    assert "deja" in doublon.lower() or "déjà" in doublon.lower()


def test_nom_vide(bac):
    assert "nom" in leads.ajouter_lead("").lower()


def test_persistence_reelle(bac):
    leads.ajouter_lead("Paul", "Beta Corp", "CTO")
    # relecture directe du fichier : la persistance est verifiee pour de vrai
    brut = json.loads((bac / "leads.json").read_text(encoding="utf-8"))
    assert brut[0]["nom"] == "Paul"
    assert brut[0]["etat"] == "nouveau"


def test_icp_positif(bac, monkeypatch):
    monkeypatch.setattr(leads, "reglage", lambda cle, defaut=None: (
        {"entreprises": ["acme"], "roles": ["ceo"]} if cle == "leads.icp" else defaut
    ))
    leads.ajouter_lead("Marie", "ACME Industries", "CEO")
    brut = json.loads((bac / "leads.json").read_text(encoding="utf-8"))
    assert brut[0]["icp"] is True


def test_icp_negatif(bac, monkeypatch):
    monkeypatch.setattr(leads, "reglage", lambda cle, defaut=None: (
        {"entreprises": ["acme"]} if cle == "leads.icp" else defaut
    ))
    leads.ajouter_lead("Paul", "AutreBoite", "Stagiaire")
    brut = json.loads((bac / "leads.json").read_text(encoding="utf-8"))
    assert brut[0]["icp"] is False


def test_etats(bac):
    leads.ajouter_lead("Paul", "Beta", "CTO")
    r = leads.changer_etat_lead("Paul", "repondu")
    assert "repondu" in r
    brut = json.loads((bac / "leads.json").read_text(encoding="utf-8"))
    assert brut[0]["etat"] == "repondu"
    # etat inconnu -> nouveau
    leads.changer_etat_lead("Paul", "nimporte")
    brut = json.loads((bac / "leads.json").read_text(encoding="utf-8"))
    assert brut[0]["etat"] == "nouveau"


def test_relances_dues(bac, monkeypatch):
    leads.ajouter_lead("Vieux", "X", "Y")
    brut = json.loads((bac / "leads.json").read_text(encoding="utf-8"))
    brut[0]["cree"] = "2020-01-01"
    (bac / "leads.json").write_text(json.dumps(brut), encoding="utf-8")
    rapport = leads.leads_a_relancer()
    assert "Vieux" in rapport
    # un lead frais n'est pas du
    leads.ajouter_lead("Neuf", "X", "Y")
    rapport2 = leads.leads_a_relancer()
    assert "Neuf" not in rapport2


def test_pipeline_resume(bac):
    leads.ajouter_lead("A", "X", "Y")
    leads.ajouter_lead("B", "X", "Y")
    leads.changer_etat_lead("B", "gagne")
    resume = leads.pipeline_leads()
    assert "2 leads" in resume and "gagne : 1" in resume


def test_envoi_n3_sans_brouillon(bac, monkeypatch):
    leads.ajouter_lead("Paul", "Beta", "CTO")
    monkeypatch.setattr("tools.navigateur._connexion", lambda auto=True: None)
    reponse = leads.envoyer_message_linkedin("Paul")
    assert "brouillon" in reponse.lower()


def test_marquer_relance(bac):
    leads.ajouter_lead("Paul", "Beta", "CTO")
    reponse = leads.marquer_relance("paul")
    assert "relance" in reponse.lower()
