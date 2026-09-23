"""Integrations OAuth (core/integrations_oauth.py) : catalogue + flux + stockage.

REGLE ABSOLUE du projet : aucune integration fake. Un provider sans
identifiants cote serveur = « setup required », jamais « connected ».
Les jetons sont chiffres au repos, les secrets ne quittent jamais le
serveur, et un callback sans state valide est refuse.
"""
import time

import pytest

from core import integrations_oauth as io
from core.config import definir_volatile


@pytest.fixture(autouse=True)
def stock_isole(tmp_path, monkeypatch):
    """Le stockage chiffre est isole : jamais le vrai fichier."""
    monkeypatch.setattr(io, "_STOCK", tmp_path / "integrations_oauth.json")
    monkeypatch.setattr(io, "_CONNEXIONS", None)
    io._ETATS.clear()
    yield
    io._ETATS.clear()


@pytest.fixture(autouse=True)
def config_isolee(monkeypatch):
    """Aucun client_id/secret par defaut : tout provider est « setup required ».
    definir_volatile ecrit dans le dict EN MEMOIRE — restaure apres le test."""
    from core import config
    monkeypatch.setattr(config, "FICHIER", config.FICHIER.parent / "config_test_absent.yaml")
    monkeypatch.setattr(config, "_CONFIG", {})
    yield


def _configurer_provider(pid, cid="id-123", secret="sec-456"):
    p = io.provider(pid)
    definir_volatile(p["clientIdKey"], cid)
    definir_volatile(p["clientSecretKey"], secret)


# ---------------------------------------------------------------- catalogue

def test_catalogue_expose_metadata_sans_jetons():
    for vue in io.vue_catalogue():
        assert vue["connected"] is False           # rien connecte
        assert vue["enabled"] is False            # rien configure
        assert vue["status"] == "setup_required"
        assert vue["capabilities"]
        assert vue["scopes"]
        # JAMAIS de secret dans la vue navigateur
        assert "client_secret" not in vue
        assert "token" not in str([k for k in vue.keys()])


def test_provider_configure_passe_available():
    _configurer_provider("github")
    vue = [v for v in io.vue_catalogue() if v["id"] == "github"][0]
    assert vue["enabled"] is True
    assert vue["connected"] is False
    assert vue["status"] == "available"


def test_connectes_initialement_vide():
    assert io.connectes_ids() == []
    assert "ALL" in io.CATEGORIES
    assert io.provider("gmail") is not None
    assert io.provider("nimporte") is None


# ------------------------------------------------------------------- state

def test_state_crypto_usage_unique():
    state, verifier, challenge = io.preparer_state("gmail")
    assert state and verifier and challenge
    assert len(state) >= 30
    # challenge = S256(verifier)
    import base64, hashlib
    attendu = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    assert challenge == attendu
    # consommable UNE fois
    assert io.valider_state("gmail", state) == verifier
    assert io.valider_state("gmail", state) is None


def test_state_refuse_mauvais_provider():
    state, _, _ = io.preparer_state("github")
    assert io.valider_state("gmail", state) is None


def test_state_refuse_sans_state():
    assert io.valider_state("gmail", "") is None
    assert io.valider_state("gmail", None) is None


def test_state_expire():
    state, _, _ = io.preparer_state("gmail")
    io._ETATS[state]["expire"] = time.time() - 1
    assert io.valider_state("gmail", state) is None


# -------------------------------------------------------------- url OAuth

def test_url_autorisation_refusee_sans_config():
    assert io.url_autorisation("github", "http://127.0.0.1:8765") is None


def test_url_autorisation_reelle_avec_config():
    _configurer_provider("github", cid="mon-client-id")
    url = io.url_autorisation("github", "http://127.0.0.1:8765")
    assert url.startswith("https://github.com/login/oauth/authorize?")
    assert "client_id=mon-client-id" in url
    assert "state=" in url
    assert "redirect_uri=http%3A%2F%2F127.0.0.1%3A8765%2Fapi%2Fintegrations%2Fgithub%2Fcallback" in url
    # le SECRET n'apparait jamais dans l'URL (public, visible du navigateur)
    assert "sec-456" not in url


def test_url_pkce_pour_notion():
    _configurer_provider("notion")
    url = io.url_autorisation("notion", "http://127.0.0.1:8765")
    assert "code_challenge=" in url
    assert "code_challenge_method=S256" in url


# --------------------------------------------------------- stockage chiffre

def test_connexion_stockee_chiffree_et_lisible():
    io.enregistrer_connexion("github", "flochatelain", "jeton-brut-visible",
                             refresh_token="refresh-brut", expires_in=3600)
    # chiffre au repos : le jeton n'est JAMAIS en clair dans le fichier
    brut = io._STOCK.read_text(encoding="utf-8")
    assert "jeton-brut-visible" not in brut
    assert "refresh-brut" not in brut
    # lisible cote serveur uniquement
    assert io.jeton_acces("github") == "jeton-brut-visible"
    vue = io.vue_connexion("github")
    assert vue["providerAccountId"] == "flochatelain"
    assert "token" not in vue


def test_supprimer_connexion():
    io.enregistrer_connexion("slack", "team-1", "tok")
    assert io.supprimer_connexion("slack") is True
    assert io.connectes_ids() == []
    assert io.supprimer_connexion("slack") is False


def test_catalogue_reflete_connexion_reelle():
    io.enregistrer_connexion("gmail", "moi@gmail.com", "tok")
    vues = {v["id"]: v for v in io.vue_catalogue()}
    assert vues["gmail"]["connected"] is True
    assert vues["gmail"]["status"] == "connected"
    assert vues["github"]["connected"] is False
    # la connexion survit a une relecture du stockage (persistee)
    io._CONNEXIONS = None
    assert "gmail" in io.connectes_ids()


# --------------------------------------------------------------- echange

def test_echange_refuse_sans_config():
    _, message = io.echanger_code("github", "code-x")
    assert message is not None
    assert "setup" in message.lower()


def test_echange_reel_avec_provider(monkeypatch):
    """Echange REEL simule cote serveur : le module http est remplace par un
    faux qui repond comme le vrai endpoint GitHub — le reste (state, stockage,
    chiffrement) est le code de production."""
    _configurer_provider("github")
    state, verifier, _ = io.preparer_state("github")
    assert io.valider_state("github", state) == verifier

    class _Reponse:
        status_code = 200
        def json(self):
            return {"access_token": "gho_vrai_jeton", "refresh_token": "rt",
                    "expires_in": 3600, "scope": "repo"}

    def faux_post(url, data=None, **kw):
        assert url == "https://github.com/login/oauth/access_token"
        assert data["client_id"] == "id-123"
        assert data["client_secret"] == "sec-456"
        assert data["code"] == "code-reel"
        return _Reponse()

    def faux_get(url, headers=None, **kw):
        class _R:
            status_code = 200
            def json(self):
                return {"login": "flochatelain0-sudo"}
        return _R()

    import core.integrations_oauth as module
    import types
    faux_requests = types.SimpleNamespace(post=faux_post, get=faux_get,
                                           delete=lambda *a, **k: _Reponse())
    monkeypatch.setitem(sys.modules if (sys := __import__("sys")) else {}, "requests", faux_requests)

    entree, message = module.echanger_code("github", "code-reel")
    assert message is None
    assert module.jeton_acces("github") == "gho_vrai_jeton"
    vue = module.vue_connexion("github")
    assert vue["providerAccountId"] == "flochatelain0-sudo"


def test_deconnecter_supprime_meme_si_provider_indisponible():
    io.enregistrer_connexion("linear", "u-1", "tok")
    assert io.deconnecter("linear") is True
    assert io.connectes_ids() == []


# ------------------------------------------------------------------ routes

def test_routes_integrations_protegees(monkeypatch):
    """Les routes /api/integrations refusent le tunnel et le LAN, comme le
    reste de l'Operator."""
    import asyncio
    from core import operator
    import types

    app = types.SimpleNamespace()
    app.routes = []
    app.get = lambda c: (lambda f: app.routes.append((c, f)) or f)
    app.post = lambda c: (lambda f: app.routes.append((c, f)) or f)
    app.delete = lambda c: (lambda f: app.routes.append((c, f)) or f)
    operator.monter_routes(app)
    routes = dict(app.routes)

    class _Client:
        def __init__(self, host):
            self.host = host

    class _Req:
        def __init__(self, host="127.0.0.1", forwarded=False, method="GET"):
            self.client = _Client(host)
            self.method = method
            self.headers = {}
            if forwarded:
                self.headers["x-forwarded-for"] = "1.2.3.4"
            if method == "POST":
                self.headers["content-type"] = "application/json"

        async def json(self):
            return {}

    catalogue = routes["/api/integrations"]
    assert catalogue(_Req(forwarded=True)).status_code == 403
    assert catalogue(_Req(host="192.168.1.5")).status_code == 403
    r = catalogue(_Req())
    assert "integrations" in r and "categories" in r
    assert r["connectedCount"] == 0


def test_route_connect_sans_config_repond_409(monkeypatch):
    import types
    from core import operator
    app = types.SimpleNamespace()
    app.routes = []
    app.get = lambda c: (lambda f: app.routes.append((c, f)) or f)
    app.post = lambda c: (lambda f: app.routes.append((c, f)) or f)
    app.delete = lambda c: (lambda f: app.routes.append((c, f)) or f)
    operator.monter_routes(app)
    routes = dict(app.routes)

    class _Client:
        host = "127.0.0.1"

    class _Req:
        def __init__(self, method="POST"):
            self.client = _Client()
            self.method = method
            self.headers = {"content-type": "application/json"}

        async def json(self):
            return {}

    route = routes["/api/integrations/{provider}/connect"]
    reponse = route("github", _Req())
    assert reponse.status_code == 409
    assert b"setup" in reponse.body.lower()
