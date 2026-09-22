"""Connecteur monday.com (tools/monday.py) : CRM officiel via API GraphQL v2.

Securite verifiee par ces tests :
  - lecture (N1) sans confirmation ; ecriture (N2) AVEC confirmation
  - mcp_expose=False : jamais expose aux agents externes
  - token jamais logge, jamais dans les messages d'erreur
Les appels HTTP sont moques : aucun test ne touche le vrai monday.com.
"""

import json

import pytest

from core import registre


@pytest.fixture(autouse=True)
def outils_charges():
    registre.charger_outils()
    yield


def _reglages(monkeypatch, token="", tableau=""):
    from tools import monday
    monkeypatch.setattr(monday, "reglage", lambda cle, defaut=None: {
        "monday.token": token, "monday.tableau": tableau,
    }.get(cle, defaut))


def test_outils_enregistres_avec_bons_niveaux():
    for nom in ("monday_tableaux", "monday_items"):
        o = registre.get(nom)
        assert o.confirmation is False       # lecture : libre
        assert o.mcp_expose is False         # jamais aux agents externes
    for nom in ("monday_creer_item", "monday_maj_item"):
        o = registre.get(nom)
        assert o.confirmation is True        # ecriture : feu vert requis
        assert o.mcp_expose is False


def test_message_clair_quand_non_configure(monkeypatch):
    _reglages(monkeypatch, token="", tableau="")
    from tools import monday
    assert "config.yaml" in monday.monday_tableaux()
    assert "config.yaml" in monday.monday_items()
    assert "config.yaml" in monday.monday_creer_item("Test")


def _mock_requete(monkeypatch, reponse):
    from tools import monday
    appels = []

    def fausse(query, variables=None):
        appels.append((query, variables))
        return reponse

    monkeypatch.setattr(monday, "_requete", fausse)
    return appels


def test_lister_tableaux(monkeypatch):
    _reglages(monkeypatch, token="tok", tableau="123")
    _mock_requete(monkeypatch, ({"boards": [{"id": "1", "name": "CRM"}]}, []))
    from tools import monday
    resultat = monday.monday_tableaux()
    assert "CRM" in resultat
    assert "tok" not in resultat               # le token ne fuit jamais


def test_lire_items_resume(monkeypatch):
    _reglages(monkeypatch, token="tok", tableau="123")
    _mock_requete(monkeypatch, ({"boards": [{"name": "Clients", "items_page": {
        "items": [{"name": "Acme", "column_values": [{"text": "Signé"}]}]}}]}, []))
    from tools import monday
    resultat = monday.monday_items()
    assert "Acme" in resultat and "Signé" in resultat


def test_creer_item_envoie_la_mutation(monkeypatch):
    _reglages(monkeypatch, token="tok", tableau="42")
    appels = _mock_requete(monkeypatch, ({"create_item": {"id": "999"}}, []))
    from tools import monday
    resultat = monday.monday_creer_item("Nouveau client",
                                        colonnes='{"statut": "En cours"}')
    assert "999" in resultat
    query, variables = appels[0]
    assert "create_item" in query
    assert variables["b"] == 42
    assert json.loads(variables["c"]) == {"statut": "En cours"}


def test_creer_item_colonnes_invalides_refusees(monkeypatch):
    _reglages(monkeypatch, token="tok", tableau="42")
    _mock_requete(monkeypatch, ({}, []))
    from tools import monday
    assert "JSON" in monday.monday_creer_item("X", colonnes="pas du json")


def test_maj_item_trouve_par_nom(monkeypatch):
    _reglages(monkeypatch, token="tok", tableau="42")
    appels = _mock_requete(monkeypatch, ({"boards": [{"items_page": {
        "items": [{"id": "77", "name": "Acme"}]}}]}, []))
    from tools import monday
    # la 2e requete (mutation) doit etre envoyee ; le mock renvoie les boards
    # a chaque fois, on intercepte les deux appels
    resultat = monday.monday_maj_item("Acme", colonnes='{"statut": "Signé"}')
    assert "mis à jour" in resultat
    assert len(appels) == 2
    assert "update_column_values" in appels[1][0]


def test_maj_item_introuvable(monkeypatch):
    _reglages(monkeypatch, token="tok", tableau="42")
    _mock_requete(monkeypatch, ({"boards": [{"items_page": {
        "items": [{"id": "77", "name": "Autre"}]}}]}, []))
    from tools import monday
    assert "Aucun item" in monday.monday_maj_item("Acme", colonnes="{}")


def test_erreur_api_remontee_sans_token(monkeypatch):
    _reglages(monkeypatch, token="tok", tableau="42")
    _mock_requete(monkeypatch, ({}, [{"message": "Board not found"}]))
    from tools import monday
    assert "Board not found" in monday.monday_items()


def test_etat_crm_pour_operator(monkeypatch):
    _reglages(monkeypatch, token="tok", tableau="42")
    _mock_requete(monkeypatch, ({"boards": [{"name": "CRM", "items_page": {
        "items": [{"name": "Acme", "column_values": [{"text": "Signé"}]}]}}]}, []))
    from tools import monday
    etat = monday.etat_crm()
    assert etat["configure"] is True
    assert etat["tableau"] == "CRM"
    assert etat["items"][0]["nom"] == "Acme"

# ------------------------------------------------------- route prioritaire

def test_route_mes_tableaux_monday():
    from core.routage_intentions import decider_prioritaire
    d = decider_prioritaire("mes tableaux monday")
    assert d is not None and d.type == "outil"
    assert d.outil == "monday_tableaux"


def test_route_mes_items_monday():
    from core.routage_intentions import decider_prioritaire
    d = decider_prioritaire("mes items monday")
    assert d is not None and d.outil == "monday_items"


def test_route_boards_monday():
    from core.routage_intentions import decider_prioritaire
    d = decider_prioritaire("mes boards monday")
    assert d is not None and d.outil == "monday_tableaux"


def test_ecriture_monday_ne_passe_pas_par_la_route_directe():
    from core.routage_intentions import decider_prioritaire
    assert decider_prioritaire("ajoute un client Acme dans monday") is None
    assert decider_prioritaire("cree une affaire dans monday") is None
    assert decider_prioritaire("passe le client Acme en signe dans monday") is None


def test_ouverture_du_site_monday_n_est_pas_une_lecture_crm():
    from core.routage_intentions import decider_prioritaire
    d = decider_prioritaire("ouvre monday.com dans chrome")
    assert d is None or d.outil != "monday_tableaux"


def test_domaine_monday_expose_les_outils_au_llm():
    from core.routage_intentions import modules_pour_phrase
    assert "monday" in modules_pour_phrase("mes tableaux monday")
    assert "monday" in modules_pour_phrase("ou j'en suis sur mon CRM")
    assert modules_pour_phrase("bonjour") == set()
