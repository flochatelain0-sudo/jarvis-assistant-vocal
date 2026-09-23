"""Tests AI Operator : synthese chiffree, carte console, file N3, doctrine."""

import pytest

from core import registre
from tools import operateur


@pytest.fixture()
def bac(tmp_path, monkeypatch):
    """Leads isoles + modules externes neutralises (mails/crm/factures off)."""
    from tools import leads
    monkeypatch.setattr(leads, "_FICHIER", tmp_path / "leads.json")
    monkeypatch.setattr(operateur, "_resume_mails",
                        lambda: {"dispo": False, "non_lus": 0})
    monkeypatch.setattr(operateur, "_resume_factures",
                        lambda: {"dispo": False})
    return tmp_path


def _sources_crm(relances=None, dispo=True):
    operateur._resume_crm = lambda: {"dispo": dispo,
                                     "relances": relances or []}


def test_enregistre():
    registre.charger_outils()
    assert registre.niveau("operateur_journee") == "N1"


def test_rien_a_signaler(bac):
    reponse = operateur.operateur_journee()
    assert "Rien a signaler" in reponse


def test_synthese_chiffree_et_carte(bac, monkeypatch):
    from tools import leads
    leads.ajouter_lead("Marie Dupont", "Acme", "CEO")
    leads.changer_etat_lead("Marie Dupont", "a_relancer")
    cartes = []
    monkeypatch.setattr("core.operator.carte_briefing", lambda d: cartes.append(d))
    _sources_crm(relances=[{"nom": "Acme SARL", "statut": "attente"}])
    reponse = operateur.operateur_journee()
    # etape 1 : points cles chiffres
    assert "1 sujet(s) en attente" in reponse or "2 sujet(s) en attente" in reponse
    assert "Marie Dupont" in reponse
    # carte recapitulative injectee dans la console
    assert cartes and cartes[0]["client"] == "Point du jour"
    titres = [c["titre"] for c in cartes[0]["champs"]]
    assert "CRM" in titres and "Leads" in titres


def test_envoi_n3_mis_en_file_jamais_executé(bac, monkeypatch):
    """Etape 3 : l'envoi LinkedIn est N3, range en file, PAS execute."""
    from tools import leads
    leads.ajouter_lead("Paul Martin", "Beta Corp", "CTO")
    leads.changer_etat_lead("Paul Martin", "a_relancer")
    # brouillon N1 simule (le LLM n'est pas joignable en test)
    monkeypatch.setattr("tools.leads.rediger_message_lead",
                        lambda nom, relance=False: f"BROUILLON pour {nom}")
    # l'envoi reel ne doit JAMAIS etre appelle ici
    appels = []
    monkeypatch.setattr("tools.leads.envoyer_message_linkedin",
                        lambda nom: appels.append(nom) or "ENVOYE")
    _sources_crm(relances=[])
    reponse = operateur.operateur_journee()
    assert "Paul Martin" in reponse
    assert appels == []                          # aucun envoi execute
    file = registre.file_en_attente()
    assert file, "l'envoi doit etre en file de confirmation"
    assert file[-1]["outil"] == "envoyer_message_linkedin"
    assert file[-1]["niveau"] == "N3"
    # nettoyage de la file pour les tests suivants
    while registre.file_en_attente():
        registre.annuler_confirme()


def test_doctrine_leads_etats_hors_relance_ignores(bac):
    """Seuls les etats a_relancer declenchent une action, pas les gagnes."""
    from tools import leads
    leads.ajouter_lead("Gagne Corp", "Win", "CEO")
    leads.changer_etat_lead("Gagne Corp", "gagne")
    _sources_crm(relances=[])
    reponse = operateur.operateur_journee()
    assert "Gagne Corp" not in reponse


def test_action_vue_dans_conversation():
    """Chaque action executee apparaît comme carte dans la conversation
    de la console (type action, categorie, statut)."""
    from core import operator
    avant = len(operator.conversation())
    operator.action_vue("mail", "Action exécutée : lire_mails",
                       "3 mails non lus", "ok")
    msgs = operator.conversation()
    assert len(msgs) == avant + 1
    m = msgs[-1]
    assert m["type"] == "action"
    assert m["categorie"] == "mail"
    assert m["resultat"] == "ok"
    assert "lire_mails" in m["texte"]


def test_action_vue_erreurs_bornées():
    """Les champs longs sont tronqués : la conversation reste légère."""
    from core import operator
    operator.action_vue("x" * 100, "t" * 300, "d" * 600, "ok")
    m = operator.conversation()[-1]
    assert len(m["categorie"]) <= 24
    assert len(m["texte"]) <= 160
    assert len(m["detail"]) <= 400
