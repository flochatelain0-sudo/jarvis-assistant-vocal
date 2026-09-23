"""Agent Mistral (Agents API) : delegation arriere-plan a outils serveur.

Doctrine verifiee :
- l'agent ne peut PAS toucher la machine : aucun outil local transmis,
  seul du TEXTE revient dans la boucle locale (voix + ecran) ;
- accusé immédiat, resultat en tache de fond, filtre confidentialite ;
- repli propre : cle absente, API en erreur, reponse vide ;
- route deterministe sans improvisation du LLM.
"""

import json
import threading
import time

import pytest

from tools import agent_mistral


class _ReponseHTTP:
    def __init__(self, status=200, corps=None):
        self.status_code = status
        self.text = json.dumps(corps or {})

    def json(self):
        return json.loads(self.text)


def _reponse_agent(texte="Voici la synthese demandee."):
    return _ReponseHTTP(200, {"choices": [{"message": {"content": texte}}]})


@pytest.fixture()
def config_agent(monkeypatch):
    """Cle + agent preconfigures pour tous les tests."""
    monkeypatch.setattr(agent_mistral, "_cle", lambda: "cle-test")
    monkeypatch.setattr(agent_mistral, "_identite", lambda: {"agent_id": "ag-123"})
    monkeypatch.setattr(agent_mistral, "_connecteurs", lambda: [])
    return monkeypatch


def _attendre_fin(thread_timeout=5):
    """Attend que les threads de delegation se terminent."""
    limite = time.time() + thread_timeout
    while time.time() < limite:
        threads = [t for t in threading.enumerate()
                   if t.name.startswith("deleguer-agent-mistral")]
        if not threads:
            return True
        time.sleep(0.05)
    return False


def test_agent_disponible_avec_cle_et_agent(config_agent):
    assert agent_mistral.agent_disponible() is True


def test_agent_indisponible_sans_cle(monkeypatch):
    monkeypatch.setattr(agent_mistral, "_cle", lambda: "")
    assert agent_mistral.agent_disponible() is False


def test_appel_envoie_la_tache_et_lagent_id(config_agent, monkeypatch):
    captures = []

    def faux_post(url, headers=None, data=None, timeout=None):
        captures.append({"url": url, "headers": headers,
                         "data": json.loads(data), "timeout": timeout})
        return _reponse_agent("Resultat : 3 agences identifiees.")

    monkeypatch.setattr(agent_mistral.requests, "post", faux_post)
    texte = agent_mistral._appeler("Trouve des agences study abroad en Asie.")
    assert texte == "Resultat : 3 agences identifiees."
    assert len(captures) == 1
    requete = captures[0]
    assert requete["url"].endswith("/v1/agents/completions")
    assert requete["headers"]["Authorization"] == "Bearer cle-test"
    assert requete["data"]["agent_id"] == "ag-123"
    assert requete["data"]["messages"][0]["content"].startswith("Trouve")
    # Doctrine : AUCUN outil local n'est transmis a l'agent.
    assert "tools" not in requete["data"]


def test_appel_mode_direct_active_web_search(monkeypatch):
    monkeypatch.setattr(agent_mistral, "_cle", lambda: "cle-test")
    monkeypatch.setattr(agent_mistral, "_identite",
                        lambda: {"model": "mistral-small-latest"})
    monkeypatch.setattr(agent_mistral, "_connecteurs",
                        lambda: [{"type": "web_search"}])
    captures = []

    def faux_post(url, headers=None, data=None, timeout=None):
        captures.append(json.loads(data))
        return _reponse_agent()

    monkeypatch.setattr(agent_mistral.requests, "post", faux_post)
    agent_mistral._appeler("veille concurrentielle")
    assert captures[0]["model"] == "mistral-small-latest"
    assert captures[0]["tools"] == [{"type": "web_search"}]


def test_appel_echec_api_leve_erreur(config_agent, monkeypatch):
    monkeypatch.setattr(agent_mistral.requests, "post",
                        lambda *a, **k: _ReponseHTTP(401, {"error": "nope"}))
    with pytest.raises(RuntimeError, match="401"):
        agent_mistral._appeler("tache")


def test_appel_reponse_vide_leve_erreur(config_agent, monkeypatch):
    monkeypatch.setattr(agent_mistral.requests, "post",
                        lambda *a, **k: _ReponseHTTP(200, {"choices": [{}]}))
    with pytest.raises(RuntimeError, match="vide"):
        agent_mistral._appeler("tache")


def test_delegation_accuse_immediat_puis_resultat_vocal(config_agent, monkeypatch):
    monkeypatch.setattr(agent_mistral.requests, "post",
                        lambda *a, **k: _reponse_agent("Synthese complete. "
                                                       "Premiere partie."))
    monkeypatch.setattr("core.voix.parler", lambda texte: captures.append(texte))
    captures = []
    accuse = agent_mistral.deleguer_en_fond("Fais une veille sur la concurrence.")
    assert "confie" in accuse          # reponse immediate, sans attendre
    assert _attendre_fin()
    assert any("L'agent Mistral a termine" in t for t in captures)
    assert any("Synthese complete" in t for t in captures)


def test_delegation_echec_annonce_vocal(config_agent, monkeypatch):
    def faux_post(*a, **k):
        raise RuntimeError("reseau casse")
    monkeypatch.setattr(agent_mistral.requests, "post", faux_post)
    monkeypatch.setattr("core.voix.paroler", lambda t: None, raising=False)
    monkeypatch.setattr("core.voix.parler", lambda t: None)
    accuse = agent_mistral.deleguer_en_fond("tache")
    assert "confie" in accuse
    assert _attendre_fin()   # le worker echoue proprement, sans crash


def test_resume_vocal_coupe_proprement():
    long = "Une phrase complete. " * 60
    resume = agent_mistral._resume_vocal(long, max_car=100)
    assert len(resume) <= 110
    assert resume.endswith((".", "!", "?", "..."))


def test_router_deterministe():
    assert agent_mistral.router_agent_mistral(
        "demande a l'agent Mistral de faire une veille sur les eSIM") == \
        ("deleguer_agent_mistral",
         {"tache": "demande a l'agent Mistral de faire une veille sur les eSIM"})
    assert agent_mistral.router_agent_mistral(
        "delegue a Mistral cette recherche de fond") is not None
    assert agent_mistral.router_agent_mistral("ouvre netflix") is None
    assert agent_mistral.router_agent_mistral(
        "cherche des leads study abroad") is None


def test_outil_enregistre_et_protege():
    from core import registre
    assert registre.niveau("deleguer_agent_mistral") in ("N1", "N2")
    outil = registre.get("deleguer_agent_mistral")
    assert outil is not None
    assert outil.mcp_expose is False     # jamais declenchable a distance


def test_deleguer_en_fond_bascule_sur_mistral(monkeypatch):
    """deleguer_en_fond (utilise partout) doit passer par l'agent Mistral
    des qu'il est configure ; Hermes n'est plus qu'un repli."""
    from tools import deleguer_a_hermes

    appels = {"mistral": 0, "hermes": 0}
    monkeypatch.setattr(agent_mistral, "agent_disponible", lambda: True)
    monkeypatch.setattr(agent_mistral, "_appeler",
                        lambda tache: appels.__setitem__(
                            "mistral", appels["mistral"] + 1) or "Resultat Mistral.")
    monkeypatch.setattr(deleguer_a_hermes, "_appeler_hermes",
                        lambda tache, session="": appels.__setitem__(
                            "hermes", appels["hermes"] + 1) or ("Hermes", 0, 0, ""))
    monkeypatch.setattr(deleguer_a_hermes, "_ajouter_tache",
                        lambda session, tache: {"id": "t1", "session": "s"})
    monkeypatch.setattr(deleguer_a_hermes, "_finir_tache",
                        lambda *a, **k: None)
    monkeypatch.setattr(deleguer_a_hermes, "_journaliser",
                        lambda tache, resultat: None)
    monkeypatch.setattr(deleguer_a_hermes, "_maj_tokens", lambda: None)
    monkeypatch.setattr(deleguer_a_hermes, "_pousser_hud", lambda: None)
    monkeypatch.setattr(deleguer_a_hermes.voix, "parler", lambda texte: None)
    monkeypatch.setattr("core.confidentialite.filtrer",
                        lambda texte, max_car=500: str(texte))

    accuse = deleguer_a_hermes.deleguer_en_fond("veille concurrentielle")
    assert "agent Mistral" in accuse
    limite = time.time() + 5
    while time.time() < limite and appels["mistral"] == 0:
        time.sleep(0.05)
    assert appels["mistral"] == 1
    assert appels["hermes"] == 0        # Hermes n'est JAMAIS appele si Mistral est la


def test_deleguer_en_fond_repli_hermes(monkeypatch):
    """Sans cle Mistral, la delegation redescend proprement vers Hermes."""
    from tools import deleguer_a_hermes

    appels = {"mistral": 0, "hermes": 0}
    monkeypatch.setattr(agent_mistral, "agent_disponible", lambda: False)
    monkeypatch.setattr(agent_mistral, "_appeler",
                        lambda tache: appels.__setitem__(
                            "mistral", appals := appels["mistral"] + 1) or "")
    monkeypatch.setattr(deleguer_a_hermes, "_appeler_hermes",
                        lambda tache, session="": appels.__setitem__(
                            "hermes", appels["hermes"] + 1)
                        or ("Resultat Hermes.", 0, 0, ""))
    monkeypatch.setattr(deleguer_a_hermes, "_ajouter_tache",
                        lambda session, tache: {"id": "t1", "session": "s"})
    monkeypatch.setattr(deleguer_a_hermes, "_finir_tache",
                        lambda *a, **k: None)
    monkeypatch.setattr(deleguer_a_hermes, "_journaliser",
                        lambda tache, resultat: None)
    monkeypatch.setattr(deleguer_a_hermes, "_maj_tokens", lambda: None)
    monkeypatch.setattr(deleguer_a_hermes, "_pousser_hud", lambda: None)
    monkeypatch.setattr(deleguer_a_hermes.voix, "parler", lambda texte: None)
    monkeypatch.setattr("core.confidentialite.filtrer",
                        lambda texte, max_car=500: str(texte))

    accuse = deleguer_a_hermes.deleguer_en_fond("analyse de fond")
    assert "Hermes" in accuse
    limite = time.time() + 5
    while time.time() < limite and appels["hermes"] == 0:
        time.sleep(0.05)
    assert appels["hermes"] == 1
    assert appels["mistral"] == 0
