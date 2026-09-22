"""Operator (core/operator.py) : journal, KPIs, validation locale uniquement.

Le CRM « AI Operator » ne cree AUCUN droit nouveau : la file « a valider »
reflete le mecanisme EXISTANT de confirmation vocale (registre._EN_ATTENTE),
et valider/refuser depuis la page equivaut au oui/non vocal. Les tests le
verifient, ainsi que le garde « local uniquement » et le journal borne.
"""

import json
import sys

import pytest

from core import operator, registre


@pytest.fixture(autouse=True)
def journal_isole(tmp_path, monkeypatch):
    """Journal dans un tmp : les tests ne touchent jamais le vrai fichier."""
    monkeypatch.setattr(operator, "_JOURNAL", tmp_path / "journal.json")
    monkeypatch.setattr(operator, "_ENTREES", None)
    yield
    registre.annuler_confirme()


def _un_outil(monkeypatch):
    """Un faux outil en attente, comme le fait la confirmation vocale."""
    outil = registre.Outil(
        lambda **k: "fait", "outil_test",
        "outil de test", {}, True, False, None,
        lambda a: f"Je vais faire {a.get('quoi')}.", False, "auto")
    registre.mettre_en_attente(outil, {"quoi": "le café"})
    return outil


# ------------------------------------------------------------------ journal

def test_journaliser_et_relire():
    operator.journaliser("mail", "3 mails triés", "boîte INBOX")
    etat = operator.etat()
    assert etat["journal"][0]["titre"] == "3 mails triés"
    assert etat["journal"][0]["categorie"] == "mail"


def test_journal_persiste_sur_disque():
    operator.journaliser("crm", "Client Acme ajouté")
    operator._ENTREES = None                      # force la relecture disque
    assert any("Acme" in e["titre"] for e in operator._charger())


def test_journal_borne_en_taille(monkeypatch):
    monkeypatch.setattr(operator, "_MAX_ENTREES", 5)
    for i in range(12):
        operator.journaliser("lecture", f"ligne {i}")
    assert len(operator._charger()) == 5
    assert operator._charger()[0]["titre"] == "ligne 11"


def test_journaliser_tronque_les_entrees():
    operator.journaliser("mail", "x" * 500, "y" * 1000)
    e = operator._charger()[0]
    assert len(e["titre"]) <= 160
    assert len(e["detail"]) <= 400


def test_journal_corrompu_repart_a_zero(tmp_path, monkeypatch):
    (tmp_path / "journal.json").write_text("{pas du json", encoding="utf-8")
    monkeypatch.setattr(operator, "_ENTREES", None)
    assert operator._charger() == []


# ---------------------------------------------------------------- KPIs 24 h

def test_kpis_comptent_les_dernieres_24h():
    import time
    operator.journaliser("mail", "vieux mail", "")
    operator._ENTREES[-1]["ts"] = time.time() - 3 * 24 * 3600   # hors fenetre
    operator.journaliser("mail", "mail récent")
    kpis = operator.etat()["kpis"]
    assert kpis["actions_24h"] == 1
    assert kpis["par_categorie"]["mail"] == 1


# ------------------------------------------------------------ file de validation

def test_file_vide_sans_action_en_attente():
    registre.annuler_confirme()
    assert operator.etat()["a_valider"] == []
    assert operator.etat()["kpis"]["en_attente"] == 0


def test_file_reflete_le_registre(monkeypatch):
    _un_outil(monkeypatch)
    file = operator.etat()["a_valider"]
    assert len(file) == 1
    assert file[0]["outil"] == "outil_test"
    assert file[0]["annonce"].startswith("Je vais faire")


# --------------------------------------------------------- valider / refuser

def test_valider_execute_l_action_en_attente(monkeypatch):
    _un_outil(monkeypatch)
    res = operator.valider()
    assert res["ok"] is True
    assert res["resultat"] == "fait"
    assert registre.nom_en_attente() is None      # file videe


def test_valider_sans_action_refuse():
    registre.annuler_confirme()
    assert operator.valider()["ok"] is False


def test_refuser_annule_sans_executer(monkeypatch):
    _un_outil(monkeypatch)
    res = operator.refuser()
    assert res["ok"] is True
    assert registre.nom_en_attente() is None


def test_validation_journallee(monkeypatch):
    _un_outil(monkeypatch)
    operator.valider()
    assert any(e["categorie"] == "validation" for e in operator._charger())


# ------------------------------------------------------------------- routes

class _Client:
    """Client bas niveau : host simulable pour tester le garde local."""

    def __init__(self, host="127.0.0.1", forwarded=False):
        self.host = host
        self.forwarded = forwarded


class _Req:
    """Faux Request : json() renvoie une coroutine, comme le vrai FastAPI."""

    def __init__(self, host="127.0.0.1", forwarded=False, method="GET", corps=None):
        import types
        self.client = _Client(host)
        self.headers = {"x-forwarded-for": "1.2.3.4"} if forwarded else {}
        if method == "POST":
            self.headers["content-type"] = "application/json"
        self.method = method
        self._corps = corps if corps is not None else {}

    async def json(self):
        if isinstance(self._corps, Exception):
            raise self._corps
        return self._corps


def _app_routes():
    import types
    app = types.SimpleNamespace()
    app.routes = []
    app.get = lambda chemin: (lambda f: app.routes.append((chemin, f)) or f)
    app.post = lambda chemin: (lambda f: app.routes.append((chemin, f)) or f)
    app.delete = lambda chemin: (lambda f: app.routes.append((chemin, f)) or f)
    operator.monter_routes(app)
    return app


def test_page_operator_refuse_le_tunnel():
    app = _app_routes()
    page = dict(app.routes)["/operator"]
    reponse = page(_Req(forwarded=True))
    assert reponse.status_code == 403


def test_api_refuse_le_lan():
    app = _app_routes()
    etat = dict(app.routes)["/api/operator/etat"]
    assert etat(_Req(host="192.168.1.5")).status_code == 403
    assert isinstance(etat(_Req()), dict)      # local : etat servi, pas un refus


def test_post_exige_json():
    app = _app_routes()
    valider = dict(app.routes)["/api/operator/valider"]
    req = _Req(method="POST")
    req.headers = {"content-type": "text/plain"}
    assert valider(req).status_code == 415


# ------------------------------------------------- routes POST asynchrones

def _attendre(appel):
    import asyncio
    resultat = appel()
    if asyncio.iscoroutine(resultat):
        resultat = asyncio.run(resultat)
    return resultat


def test_route_message_lit_le_corps_async():
    app = _app_routes()
    route = dict(app.routes)["/api/operator/message"]
    req = _Req(method="POST", corps={"texte": "lis mes mails"})
    res = _attendre(lambda: route(req))
    assert res["ok"] is True
    m = operator.message_suivant()
    assert m["texte"] == "lis mes mails"


def test_route_message_corps_invalide_ne_plante_pas():
    app = _app_routes()
    route = dict(app.routes)["/api/operator/message"]
    req = _Req(method="POST", corps=ValueError("pas du json"))
    res = _attendre(lambda: route(req))
    assert res["ok"] is False


def test_route_automation_basculer_lit_le_corps_async(tmp_path, monkeypatch):
    from core import automations as autos
    monkeypatch.setattr(autos, "_FICHIER", tmp_path / "automations.json")
    monkeypatch.setattr(autos, "_AUTOMATIONS", None)
    auto = autos.ajouter("Test", "08:00", "brief")
    app = _app_routes()
    route = dict(app.routes)["/api/operator/automations/{identifiant}/basculer"]
    req = _Req(method="POST", corps={"active": False})
    res = _attendre(lambda: route(auto["id"], req))
    assert res["ok"] is True


def test_route_automation_creer_lit_le_corps_async(tmp_path, monkeypatch):
    from core import automations as autos
    monkeypatch.setattr(autos, "_FICHIER", tmp_path / "automations.json")
    monkeypatch.setattr(autos, "_AUTOMATIONS", None)
    app = _app_routes()
    route = dict(app.routes)["/api/operator/automations"]
    req = _Req(method="POST",
               corps={"nom": "Brief test", "moment": "08:00", "action": "brief"})
    res = _attendre(lambda: route(req))
    assert res["ok"] is True
    assert res["automation"]["nom"] == "Brief test"


def test_route_brain_oublier_lit_le_corps_async(monkeypatch):
    app = _app_routes()
    route = dict(app.routes)["/api/operator/brain/oublier"]
    req = _Req(method="POST", corps={"sujet": "test"})
    res = _attendre(lambda: route(req))
    assert "ok" in res


# --------------------------------------------------------- messagerie ecrite

def test_message_ecrit_file_et_reponse():
    operator.envoyer_message("lis mes mails")
    m = operator.message_suivant()
    assert m["texte"] == "lis mes mails"
    assert operator.message_suivant() is None      # file videe
    operator.reponse_message(m["id"], "Voici tes 3 mails.")
    assert operator.lire_reponse(m["id"]) == "Voici tes 3 mails."
    assert operator.lire_reponse(m["id"]) is None  # consommee une fois


def test_message_en_attente_ne_consomme_pas():
    assert operator.message_en_attente() is False
    operator.envoyer_message("premiere question")
    assert operator.message_en_attente() is True
    assert operator.message_en_attente() is True          # toujours la
    assert operator.message_suivant()["texte"] == "premiere question"
    assert operator.message_en_attente() is False         # consommee


def test_message_vide_ou_trop_long_refuse():
    assert operator.envoyer_message("  ")["ok"] is False
    assert operator.envoyer_message("x" * 700)["ok"] is False


def test_conversation_garde_les_derniers():
    for i in range(50):
        operator.envoyer_message(f"message {i}")
    assert len(operator.conversation()) <= 40


# ------------------------------------------------------------------ vie + fil vocal

def test_etat_expose_la_vie_de_l_assistant():
    etat = operator.etat()
    assert "vie" in etat
    assert etat["vie"]["etat"] in {"veille", "ecoute", "reflexion", "parole"}
    assert "fil_vocal" in etat
    assert isinstance(etat["fil_vocal"], list)


def test_fil_vocal_rejoue_les_transcriptions_du_hud(monkeypatch):
    import types

    class _Hud(types.SimpleNamespace):
        _HISTORIQUE = [
            {"t": "vous", "texte": "allume la lumiere"},
            {"t": "outil", "nom": "luminotes", "detail": "chambre"},
            {"t": "jarvis", "texte": "C'est fait."},
        ]

    monkeypatch.setitem(sys.modules, "hud", _Hud)
    fil = operator._fil_vocal()
    roles = [e["t"] for e in fil]
    assert roles == ["vous", "outil", "jarvis"]
    assert fil[0]["texte"] == "allume la lumiere"


# ---------------------------------------------------------------- carte briefing

def test_carte_briefing_injectee_dans_la_conversation():
    from core import operator
    operator.carte_briefing({
        "client": "Acme",
        "rdv": "14:00",
        "champs": [{"titre": "Budget", "valeur": "285k"}],
        "questions": ["Ou en es-tu du financement ?",
                      "Qu'est-ce qui pourrait bloquer la decision ?",
                      "Qu'est-ce qui t'empecherait de lancer ce mois-ci ?"],
    })
    messages = operator.conversation()
    briefings = [m for m in messages if m.get("type") == "briefing"]
    assert briefings, "aucune carte briefing dans la conversation"
    b = briefings[-1]
    assert b["client"] == "Acme" and b["rdv"] == "14:00"
    assert len(b["questions"]) == 3

# ------------------------------------------------------------------ traitement
def _vider_files_ecrites():
    while operator.message_en_attente():
        operator.message_suivant()
    for item in list(operator.etat_traitement()["en_cours"]):
        operator.fin_traitement(item["id"])


def test_etat_traitement_vide_puis_en_cours():
    _vider_files_ecrites()
    assert operator.etat_traitement() == {"en_cours": [], "en_attente": 0}
    operator.debut_traitement(17)
    etat = operator.etat_traitement()
    assert etat["en_cours"] and etat["en_cours"][0]["id"] == 17
    assert etat["en_cours"][0]["depuis"] >= 0
    operator.fin_traitement(17)
    assert operator.etat_traitement() == {"en_cours": [], "en_attente": 0}


def test_fin_traitement_expire_ajoute_un_message():
    operator.debut_traitement(21)
    operator.fin_traitement(21, a_expire=True)
    msgs = operator.conversation()
    assert any("Delai depasse" in (m.get("texte") or "") for m in msgs)
    assert operator.etat_traitement()["en_cours"] == []


def test_fin_traitement_inconnu_ne_plante_pas():
    operator.fin_traitement(999)


def test_etat_traitement_compte_les_messages_en_attente():
    _vider_files_ecrites()
    operator.envoyer_message("premiere")
    operator.envoyer_message("deuxieme")
    etat = operator.etat_traitement()
    assert etat["en_attente"] == 2
    assert operator.message_suivant()["texte"] == "premiere"
    assert operator.message_suivant()["texte"] == "deuxieme"
    assert operator.etat_traitement()["en_attente"] == 0


def test_question_validation_note_l_outil(monkeypatch):
    registre.annuler_confirme()
    _un_outil(monkeypatch)
    from core import registre as r
    # simuler ce que fait jarvis14 quand un outil attend son feu vert
    file = r.file_en_attente()
    assert file, "la file d'attente devrait contenir l'outil"
    operator.question_validation(file[0]["id"], file[0]["outil"],
                                 file[0]["niveau"], file[0]["annonce"])
    msgs = operator.conversation()
    v = msgs[-1]
    assert v["type"] == "validation" and v["outil"] == "outil_test"
    assert v["texte"].endswith("Tu confirmes ?")
    registre.annuler_confirme()
