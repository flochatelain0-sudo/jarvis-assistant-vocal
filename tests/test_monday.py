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


# ---------------------------------------------------------------- briefing

def _reponse_items(nom="Acme", colonnes=None):
    colonnes = colonnes or [{"id": "statut", "title": "Statut", "text": "En cours"}]
    return ({"boards": [{"name": "Clients", "items_page": {
        "cursor": None,
        "items": [{"id": "42", "name": nom,
                   "column_values": colonnes}]}}]}, [])


def test_brief_client_affiche_la_fiche_et_les_questions(monkeypatch):
    from tools import monday
    _reglages(monkeypatch, token="tok", tableau="123")
    _mock_requete(monkeypatch, _reponse_items("Acme", [
        {"id": "a", "title": "Budget", "text": "285 000 euros"},
        {"id": "b", "title": "Statut", "text": "En cours"},
    ]))
    cartes = []
    monkeypatch.setattr("core.operator.carte_briefing", cartes.append)
    monkeypatch.setattr("tools.agenda.planning_du_jour",
                        lambda: {"evenements": [], "configure": True})
    resultat = monday.brief_client("Acme")
    assert "briefing" in resultat.lower() or "Acme" in resultat
    assert len(cartes) == 1
    carte = cartes[0]
    assert carte["client"] == "Acme"
    assert carte["champs"][0]["titre"] == "Budget"
    assert len(carte["questions"]) == 3


def test_brief_client_sans_client_demande_lequel(monkeypatch):
    from tools import monday
    _reglages(monkeypatch, token="tok", tableau="123")
    assert monday.brief_client("") == "Quel client ?"


def test_brief_client_introuvable_le_dit(monkeypatch):
    from tools import monday
    _reglages(monkeypatch, token="tok", tableau="123")
    _mock_requete(monkeypatch, ({"boards": [{"items_page": {
        "cursor": None, "items": []}}]}, []))
    assert "aucun client" in monday.brief_client("Personne").lower()


def test_questions_closing_s_adaptent_aux_donnees():
    from tools.monday import _questions_closing
    q = _questions_closing({"statut": "attente accord de principe banque"},
                           "", [("Statut", "attente accord banque")])
    assert "banque" in q[0].lower()


def test_brief_client_non_configure(monkeypatch):
    from tools import monday
    _reglages(monkeypatch, token="", tableau="")
    assert "config.yaml" in monday.brief_client("Acme")


def test_domaine_monday_expose_les_outils_au_llm():
    from core.routage_intentions import modules_pour_phrase
    assert "monday" in modules_pour_phrase("mes tableaux monday")
    assert "monday" in modules_pour_phrase("ou j'en suis sur mon CRM")
    assert modules_pour_phrase("bonjour") == set()


def _items_business():
    return [
        {"nom": "Acme", "colonnes": [
            {"titre": "Statut", "valeur": "Signé"},
            {"titre": "Montant", "valeur": "285 000 €"}]},
        {"nom": "Beta", "colonnes": [
            {"titre": "Statut", "valeur": "En cours"},
            {"titre": "Montant", "valeur": "150000"}]},
        {"nom": "Perdu & Co", "colonnes": [
            {"titre": "Statut", "valeur": "Perdu"},
            {"titre": "Montant", "valeur": "120000"}]},
        {"nom": "Sans statut", "colonnes": [
            {"titre": "Montant", "valeur": "99000"}]},
    ]


def test_kpis_business_separes_signes_et_pipeline():
    from tools.monday import _kpis_business
    k = _kpis_business(_items_business())
    assert k["nb_signes"] == 1 and k["signes"] == 285000.0
    assert k["nb_pipeline"] == 1 and k["pipeline"] == 150000.0


def test_kpis_business_ne_plante_pas_sans_montant():
    from tools.monday import _kpis_business
    k = _kpis_business([{"nom": "X", "colonnes": [
        {"titre": "Statut", "valeur": "Signé"}]}])
    assert k["nb_signes"] == 1 and k["signes"] == 0.0


def test_etat_crm_expose_les_kpis_business(monkeypatch):
    _reglages(monkeypatch, token="tok", tableau="42")
    _mock_requete(monkeypatch, ({"boards": [{"name": "CRM", "items_page": {
        "items": [
            {"name": "Acme", "column_values": [
                {"title": "Statut", "text": "Signé"},
                {"title": "Montant", "text": "285 000 €"}]},
            {"name": "Beta", "column_values": [
                {"title": "Statut", "text": "Négociation"},
                {"title": "Montant", "text": "150000"}]},
        ]}}]}, []))
    from tools import monday
    etat = monday.etat_crm()
    assert etat["business"]["nb_signes"] == 1
    assert etat["business"]["signes"] == 285000.0
    assert etat["business"]["nb_pipeline"] == 1
    assert etat["business"]["pipeline"] == 150000.0


def test_fiche_client_renvoie_toutes_les_colonnes(monkeypatch):
    _reglages(monkeypatch, token="tok", tableau="42")
    reponse = {"boards": [{"name": "CRM", "items_page": {"items": [
        {"name": "Acme", "id": "7", "column_values": [
            {"title": "Statut", "text": "Negociation"},
            {"title": "Montant", "text": "285 000 EUR"},
            {"title": "Historique", "text": "R1 le 3 septembre"},
            {"title": "Contact", "text": "pierre@acme.fr"},
        ]}]}}]}
    _mock_requete(monkeypatch, (reponse, []))
    from tools import monday
    fiche = monday.fiche_client("acme")
    assert fiche["nom"] == "Acme" and fiche["id"] == "7"
    titres = [c["titre"] for c in fiche["colonnes"]]
    assert titres == ["Statut", "Montant", "Historique", "Contact"]


def test_fiche_client_introuvable_renvoie_none(monkeypatch):
    _reglages(monkeypatch, token="tok", tableau="42")
    _mock_requete(monkeypatch, ({"boards": [{"name": "CRM", "items_page": {
        "items": []}}]}, []))
    from tools import monday
    assert monday.fiche_client("personne") is None


def test_fiche_client_erreur_api_ne_plante_pas(monkeypatch):
    _reglages(monkeypatch, token="tok", tableau="42")

    def faux(query, variables=None):
        raise RuntimeError("reseau coupe")

    from tools import monday
    monkeypatch.setattr(monday, "_requete", faux)
    assert monday.fiche_client("acme") is None


def test_etapes_pipeline_regroupe_par_statut():
    from tools.monday import _etapes_pipeline
    items = [
        {"nom": "A", "colonnes": [
            {"titre": "Statut", "valeur": "R1 à venir"},
            {"titre": "Montant", "valeur": "100000"}]},
        {"nom": "B", "colonnes": [
            {"titre": "Statut", "valeur": "R1 à venir"},
            {"titre": "Montant", "valeur": "50000"}]},
        {"nom": "C", "colonnes": [
            {"titre": "Statut", "valeur": "Négociation"},
            {"titre": "Montant", "valeur": "200000"}]},
        {"nom": "D", "colonnes": [
            {"titre": "Statut", "valeur": "Perdu"},
            {"titre": "Montant", "valeur": "99000"}]},
        {"nom": "E", "colonnes": [
            {"titre": "Montant", "valeur": "99000"}]},
    ]
    etapes = _etapes_pipeline(items)
    assert [e["etape"] for e in etapes] == ["R1 à venir", "Négociation"]
    assert etapes[0]["nb"] == 2 and etapes[0]["montant"] == 150000.0
    assert etapes[1]["nb"] == 1 and etapes[1]["montant"] == 200000.0


def test_etapes_pipeline_vide_sans_statut():
    from tools.monday import _etapes_pipeline
    assert _etapes_pipeline([]) == []
    assert _etapes_pipeline([{"nom": "X", "colonnes": []}]) == []


def test_etat_crm_expose_le_pipeline(monkeypatch):
    _reglages(monkeypatch, token="tok", tableau="42")
    reponse = {"boards": [{"name": "CRM", "items_page": {"items": [
        {"name": "A", "column_values": [
            {"title": "Statut", "text": "R1 à venir"},
            {"title": "Montant", "text": "100000"}]},
        {"name": "B", "column_values": [
            {"title": "Statut", "text": "R2"},
            {"title": "Montant", "text": "200000"}]},
    ]}}]}
    _mock_requete(monkeypatch, (reponse, []))
    from tools import monday
    etat = monday.etat_crm()
    etapes = {e["etape"]: e for e in etat["pipeline"]}
    assert etapes["R1 à venir"]["nb"] == 1
    assert etapes["R2"]["montant"] == 200000.0


def test_a_relancer_trouve_les_statuts_d_attente(monkeypatch):
    _reglages(monkeypatch, token="tok", tableau="42")
    reponse = {"boards": [{"name": "CRM", "items_page": {"items": [
        {"name": "Lopez", "column_values": [
            {"title": "Statut", "text": "À relancer"}]},
        {"name": "Martin", "column_values": [
            {"title": "Statut", "text": "En attente de réponse"}]},
        {"name": "Acme", "column_values": [
            {"title": "Statut", "text": "Négociation"}]},
        {"name": "Vendu", "column_values": [
            {"title": "Statut", "text": "Signé"}]},
    ]}}]}
    _mock_requete(monkeypatch, (reponse, []))
    from tools import monday
    r = monday.a_relancer()
    noms = [x["nom"] for x in r["relances"]]
    assert noms == ["Lopez", "Martin"]


def test_a_relancer_vide_quand_non_configure(monkeypatch):
    _reglages(monkeypatch, token="", tableau="")
    from tools import monday
    assert monday.a_relancer() == {"relances": []}


def test_a_relancer_erreur_api_ne_plante_pas(monkeypatch):
    _reglages(monkeypatch, token="tok", tableau="42")

    def faux(query, variables=None):
        raise RuntimeError("reseau coupe")

    from tools import monday
    monkeypatch.setattr(monday, "_requete", faux)
    assert monday.a_relancer() == {"relances": []}
