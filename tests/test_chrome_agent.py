"""Agent Chrome LinkedIn : arriere-plan CDP + controle clavier physique.

Doctrine verifiee ici :
- lecture N1 en arriere-plan (aucun clic, aucune souris, aucune exception) ;
- pre-remplissage SANS envoi par defaut ; l'envoi clavier physique exige
  envoyer=True ET passe la confirmation N3 (geree par le registre) ;
- repli deterministe si le LLM est indisponible ou si LinkedIn demande
  une connexion (jamais de saisie d'identifiants) ;
- la carte console ne doit jamais faire planter le vocal.
"""

import pytest

from tools import chrome_agent


class _Bloc:
    def __init__(self, text):
        self.type = "text"
        self.text = text


class _Reponse:
    def __init__(self, text):
        self.blocs = [_Bloc(text)]


class _LLM:
    """LLM de test qui renvoie toujours le meme texte."""

    def __init__(self, text="Bien recu !"):
        self.text = text

    def repondre(self, consigne, hist, msgs):
        return _Reponse(self.text)


def _llm_simple(monkeypatch, text="Bien recu !"):
    monkeypatch.setattr("core.llm.llm", lambda: _LLM(text))

class _Page:
    """Faux onglet LinkedIn pilotant un DOM de test."""

    def __init__(self, conversations, connecte=True, reponse_ok=True):
        self.url = "https://www.linkedin.com/messaging/"
        self._conversations = conversations
        self._connecte = connecte
        self._reponse_ok = reponse_ok
        self.champ = ""

    def goto(self, url, **kw):
        self.url = url
        if not self._connecte:
            self.url = "https://www.linkedin.com/uas/login"

    def evaluate(self, js, *args):
        if "msg-conversation-card" in js or "messaging/thread" in js:
            return self._conversations
        if "msg-s-event-listitem" in js:
            return {"nom": "Sophie Martin",
                    "message": "Bonjour, avez-vous un moment ?"}
        if "insertText" in js:
            if self._reponse_ok:
                self.champ = str(args[0])
                return True
            return False
        if "innerText.trim() === ''" in js:
            return self.champ == ""
        if "focus" in js:
            return None
        return None

    def bring_to_front(self):
        pass


class _Browser:
    def __init__(self, page):
        self._page = page

    @property
    def contexts(self):
        browser = self

        class _Ctx:
            def pages(self):
                return [browser._page]

        class _C:
            pages = [browser._page]

            def new_page(self):
                return browser._page

        return [_C()]


def _mock_navigateur(monkeypatch, page):
    from tools import navigateur
    monkeypatch.setattr(navigateur, "_connexion", lambda auto=True: _Browser(page))
    monkeypatch.setattr(navigateur, "_MSG_ABSENT", "Chrome absent.")


def test_lecture_arriere_plan_liste_non_lus(monkeypatch):
    convs = [{"nom": "Sophie Martin", "extrait": "Bonjour...",
              "non_lu": True, "href": "https://www.linkedin.com/messaging/thread/1"},
             {"nom": "TGM Education", "extrait": "Merci...",
              "non_lu": False, "href": "https://www.linkedin.com/messaging/thread/2"}]
    page = _Page(convs)
    _mock_navigateur(monkeypatch, page)
    monkeypatch.setattr("core.rapport_work.carte", lambda *a, **k: None)
    reponse = chrome_agent.lire_messages_linkedin()
    assert "1 message(s) non lu(s)" in reponse
    assert "Sophie Martin" in reponse
    assert "TGM Education" not in reponse.split(". Dis-moi")[0]


def test_lecture_sans_non_lu(monkeypatch):
    convs = [{"nom": "TGM Education", "extrait": "Merci...",
              "non_lu": False, "href": ""}]
    _mock_navigateur(monkeypatch, _Page(convs))
    monkeypatch.setattr("core.rapport_work.carte", lambda *a, **k: None)
    assert "Aucun message non lu" in chrome_agent.lire_messages_linkedin()


def test_lecture_ecran_de_connexion(monkeypatch):
    page = _Page([], connecte=False)
    _mock_navigateur(monkeypatch, page)
    reponse = chrome_agent.lire_messages_linkedin()
    assert "connexion" in reponse
    assert "identifiants" in reponse


def test_repondre_pre_remplit_sans_envoyer(monkeypatch):
    convs = [{"nom": "Sophie Martin", "extrait": "Bonjour...",
              "non_lu": True,
              "href": "https://www.linkedin.com/messaging/thread/1"}]
    page = _Page(convs)
    _mock_navigateur(monkeypatch, page)

    class _LLMSophie:
        def repondre(self, consigne, hist, msgs):
            assert "Sophie" in consigne
            return _Reponse("Bonjour Sophie, avec plaisir !")

    monkeypatch.setattr("core.llm.llm", lambda: _LLMSophie())
    reponse = chrome_agent.repondre_messages_linkedin(filtre="Sophie")
    assert "pre-remplie" in reponse
    assert "verifie" in reponse.lower() or "Verifie" in reponse
    assert page.champ == "Bonjour Sophie, avec plaisir !"
    assert "Envoyer" in reponse  # doctrine : jamais d'envoi sans feu vert


def test_repondre_repli_llm_indisponible(monkeypatch):
    convs = [{"nom": "Sophie Martin", "extrait": "",
              "non_lu": True, "href": ""}]
    page = _Page(convs)
    _mock_navigateur(monkeypatch, page)

    class _LLM:
        def repondre(self, *a):
            raise RuntimeError("pas de reseau")

    monkeypatch.setattr("core.llm.llm", lambda: _LLM())
    reponse = chrome_agent.repondre_messages_linkedin()
    assert "pre-remplie" in reponse
    assert page.champ  # le repli deterministe a bien ete saisi


def test_envoi_clavier_physique_confirme(monkeypatch):
    convs = [{"nom": "Sophie Martin", "extrait": "",
              "non_lu": True, "href": ""}]
    page = _Page(convs)
    _mock_navigateur(monkeypatch, page)
    _llm_simple(monkeypatch)
    envoyes = []
    def _envoyer(combo):
        envoyes.append(combo)
        page.champ = ""      # LinkedIn vide le champ apres l'envoi
        return True

    monkeypatch.setattr("core.plateforme.envoyer_touches", _envoyer)
    reponse = chrome_agent.repondre_messages_linkedin(envoyer=True)
    assert envoyes == ["return"]
    assert "envoye" in reponse.lower()
    assert page.champ == ""  # le champ s'est vide apres l'envoi


def test_envoi_refuse_sans_accessibilite(monkeypatch):
    convs = [{"nom": "Sophie Martin", "extrait": "",
              "non_lu": True, "href": ""}]
    page = _Page(convs)
    _mock_navigateur(monkeypatch, page)
    _llm_simple(monkeypatch)
    monkeypatch.setattr("core.plateforme.envoyer_touches", lambda combo: False)
    reponse = chrome_agent.repondre_messages_linkedin(envoyer=True)
    assert "Accessibilite" in reponse or "clavier" in reponse
    # Le message reste pre-rempli : rien n'est perdu.
    assert page.champ


def test_repondre_sans_conversation_non_lue(monkeypatch):
    convs = [{"nom": "TGM Education", "extrait": "", "non_lu": False, "href": ""}]
    _mock_navigateur(monkeypatch, _Page(convs))
    reponse = chrome_agent.repondre_messages_linkedin()
    assert "Aucune conversation non lue" in reponse


def test_champ_introuvable_ne_plante_pas(monkeypatch):
    convs = [{"nom": "Sophie Martin", "extrait": "",
              "non_lu": True, "href": ""}]
    page = _Page(convs, reponse_ok=False)
    _mock_navigateur(monkeypatch, page)
    _llm_simple(monkeypatch)
    reponse = chrome_agent.repondre_messages_linkedin()
    assert "champ de saisie" in reponse


def test_router_deterministe(monkeypatch):
    assert chrome_agent.router_agent_linkedin("lis mes messages linkedin") == \
        ("lire_messages_linkedin", {})
    assert chrome_agent.router_agent_linkedin(
        "reponds a Sophie sur LinkedIn") == ("repondre_messages_linkedin", {})
    assert chrome_agent.router_agent_linkedin("ouvre netflix") is None
    assert chrome_agent.router_agent_linkedin(
        "cherche des leads study abroad") is None


def test_niveau_permission_n3():
    from core import registre
    assert registre.niveau("repondre_messages_linkedin") == "N3"
    assert registre.niveau("lire_messages_linkedin") == "N1"
