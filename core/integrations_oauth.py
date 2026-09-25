"""Integrations OAuth : catalogue reel + flux OAuth 2.0 + stockage chiffre.

Page INTEGRATIONS de la console ZOEY OS. REGLES (spec du projet) :

  - AUCUNE integration fake. Un provider n'est ACTIVE que si ses identifiants
    existent cote serveur (config.yaml, jamais dans le frontend). Sinon la
    carte affiche « Available — setup required », sans jamais simuler.
  - Les secrets ne partent JAMAIS vers le navigateur : l'echange de code et
    le rafraichissement se font ici, les jetons sont chiffres au repos
    (Fernet, cle derivee de la cle maitresse de config.yaml).
  - state cryptographique + PKCE quand le provider le supporte ; un callback
    sans state valide est refuse.
  - Deconnexion : revocation officielle chez le provider quand elle existe,
    puis suppression locale.

ARCHITECTURE : FastAPI local (garde 127.0.0.1 du Operator), stockage JSON
chiffre data/integrations_oauth.json — memes conventions que le reste du
projet (pas de base SQL dans Jarvis ; tout est fichier local).

Les definitions provider sont de la CONFIG STATIQUE (metadata) ; l'etat de
connexion vient TOUJOURS du stockage reel, jamais du frontend.
"""

import base64
import hashlib
import json
import secrets
import threading
import time
from pathlib import Path

from core.config import reglage

_RACINE = Path(__file__).resolve().parent.parent
_STOCK = _RACINE / "data" / "integrations_oauth.json"
_VERROU = threading.RLock()
_CONNEXIONS = None          # chargees paresseusement
_ETATS = {}                 # state OAuth en attente : state -> {provider, expire, verifier}


# ------------------------------------------------------------ catalogue
# Definitions statiques : metadata seulement. Chaque entree decrit le VRAI
# flux OAuth du provider. Un provider sans identifiants configure = pas
# « active » (carte grise « setup required »), jamais une connexion simulee.

def _def_provider(nom, nom_affiche, categorie, description, capacites,
                  authorize_url, token_url, scopes, client_id_key,
                  client_secret_key, revoke_url=None, pkce=False,
                  extra_token_params=None, doc_url=""):
    return {
        "id": nom,
        "name": nom_affiche,
        "slug": nom,
        "description": description,
        "category": categorie,
        "authType": "oauth2",
        "scopes": scopes,
        "oauthAuthorizationUrl": authorize_url,
        "tokenEndpoint": token_url,
        "revokeEndpoint": revoke_url,
        "pkce": pkce,
        "extraTokenParams": extra_token_params or {},
        "clientIdKey": client_id_key,
        "clientSecretKey": client_secret_key,
        "capabilities": capacites,
        "documentationUrl": doc_url,
    }


CATALOGUE = [
    _def_provider(
        "gmail", "Gmail", "DOCS & DATA",
        "Read and manage your Gmail inbox.",
        ["Read emails", "Search emails", "Draft emails", "Send emails"],
        "https://accounts.google.com/o/oauth2/v2/auth",
        "https://oauth2.googleapis.com/token",
        ["https://mail.google.com/", "openid", "email"],
        "integrations.gmail.client_id", "integrations.gmail.client_secret",
        revoke_url="https://oauth2.googleapis.com/revoke",
        doc_url="https://developers.google.com/gmail/api",
    ),
    _def_provider(
        "gcal", "Google Calendar", "DOCS & DATA",
        "Organize and manage your schedule.",
        ["Read events", "Create events", "Update events", "Delete events"],
        "https://accounts.google.com/o/oauth2/v2/auth",
        "https://oauth2.googleapis.com/token",
        ["https://www.googleapis.com/auth/calendar", "openid", "email"],
        "integrations.gcal.client_id", "integrations.gcal.client_secret",
        revoke_url="https://oauth2.googleapis.com/revoke",
        doc_url="https://developers.google.com/calendar",
    ),
    _def_provider(
        "gdrive", "Google Drive", "DOCS & DATA",
        "Store, search and share your files.",
        ["Read files", "Upload files", "Search files"],
        "https://accounts.google.com/o/oauth2/v2/auth",
        "https://oauth2.googleapis.com/token",
        ["https://www.googleapis.com/auth/drive", "openid", "email"],
        "integrations.gdrive.client_id", "integrations.gdrive.client_secret",
        revoke_url="https://oauth2.googleapis.com/revoke",
        doc_url="https://developers.google.com/drive",
    ),
    _def_provider(
        "github", "GitHub", "DEV TOOLS",
        "Manage code, repos and deployments.",
        ["Read repositories", "Read issues", "Create issues"],
        "https://github.com/login/oauth/authorize",
        "https://github.com/login/oauth/access_token",
        ["repo", "read:org", "gist"],
        "integrations.github.client_id", "integrations.github.client_secret",
        revoke_url="https://api.github.com/applications/{client_id}/token",
        doc_url="https://docs.github.com/apps",
    ),
    _def_provider(
        "slack", "Slack", "MARKETING & SUPPORT",
        "Send messages and manage your workspace.",
        ["Send messages", "Read channels", "Upload files"],
        "https://slack.com/oauth/v2/authorize",
        "https://slack.com/api/oauth.v2.access",
        ["chat:write", "channels:read", "files:write"],
        "integrations.slack.client_id", "integrations.slack.client_secret",
        revoke_url="https://slack.com/api/auth.revoke",
        doc_url="https://api.slack.com",
    ),
    _def_provider(
        "notion", "Notion", "PROJECT MGMT",
        "Read and update your Notion pages.",
        ["Read pages", "Update pages", "Search pages"],
        "https://api.notion.com/v1/oauth/authorize",
        "https://api.notion.com/v1/oauth/token",
        ["read_content", "update_content"],
        "integrations.notion.client_id", "integrations.notion.client_secret",
        pkce=True,
        doc_url="https://developers.notion.com",
    ),
    _def_provider(
        "linear", "Linear", "PROJECT MGMT",
        "Manage issues, cycles and projects.",
        ["Read issues", "Create issues", "Update issues"],
        "https://linear.app/oauth/authorize",
        "https://api.linear.app/oauth/token",
        ["read", "write", "issues:create"],
        "integrations.linear.client_id", "integrations.linear.client_secret",
        doc_url="https://developers.linear.app",
    ),
    _def_provider(
        "outlook", "Outlook", "DOCS & DATA",
        "Read and manage your Outlook inbox and calendar.",
        ["Read emails", "Send emails", "Read calendar"],
        "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        "https://login.microsoftonline.com/common/oauth2/v2.0/token",
        ["Mail.Read", "Mail.Send", "Calendars.Read", "offline_access", "openid"],
        "integrations.outlook.client_id", "integrations.outlook.client_secret",
        doc_url="https://learn.microsoft.com/graph",
    ),
    _def_provider(
        "hubspot", "HubSpot", "CRM & SALES",
        "Sync contacts and track your pipeline.",
        ["Read contacts", "Read deals", "Create deals"],
        "https://app.hubspot.com/oauth/authorize",
        "https://api.hubapi.com/oauth/v1/token",
        ["crm.objects.contacts.read", "crm.objects.deals.read",
         "crm.objects.deals.write"],
        "integrations.hubspot.client_id", "integrations.hubspot.client_secret",
        doc_url="https://developers.hubspot.com",
    ),
    _def_provider(
        "linkedin", "LinkedIn", "CRM & SALES",
        "Share posts and manage your professional network.",
        ["Share posts", "Read profile", "Manage connections"],
        "https://www.linkedin.com/oauth/v2/authorization",
        "https://www.linkedin.com/oauth/v2/accessToken",
        ["r_liteprofile", "w_member_social"],
        "integrations.linkedin.client_id", "integrations.linkedin.client_secret",
        doc_url="https://learn.microsoft.com/linkedin",
    ),
]

_CATEGORIES = ["DOCS & DATA", "DEV TOOLS", "PROJECT MGMT",
               "CRM & SALES", "MARKETING & SUPPORT"]

# Ordre d'affichage : ALL d'abord, puis les categories du catalogue.
CATEGORIES = ["ALL"] + _CATEGORIES


def _ids(provider):
    """(client_id, client_secret) depuis config.yaml — vide si non configure."""
    cid = (reglage(provider["clientIdKey"], "") or "").strip()
    secret = (reglage(provider["clientSecretKey"], "") or "").strip()
    return cid, secret


def provider(provider_id):
    """La definition complete, ou None."""
    return next((p for p in CATALOGUE if p["id"] == provider_id), None)


def configure(provider_id):
    """Vrai si les identifiants OAuth du provider existent cote serveur."""
    p = provider(provider_id)
    if not p:
        return False
    cid, secret = _ids(p)
    return bool(cid and secret)


# ------------------------------------------------------------- chiffre
# Les jetons sont chiffres au repos avec Fernet. La cle est derivee de
# integrations.cle (config.yaml) — si absente, derivee du sel utilisateur.
# AUCUN jeton en clair sur disque, AUCUN secret envoye au navigateur.

def _cle_fernet():
    from cryptography.fernet import Fernet
    import hashlib
    maitre = (reglage("integrations.cle", "") or
              reglage("utilisateur.nom", "") or "jarvis-local").strip()
    digest = hashlib.sha256(maitre.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def _chiffrer(texte):
    if not texte:
        return ""
    return _cle_fernet().encrypt(texte.encode("utf-8")).decode("ascii")


def _dechiffrer(blob):
    if not blob:
        return ""
    try:
        return _cle_fernet().decrypt(blob.encode("ascii")).decode("utf-8")
    except Exception:
        return ""


# ------------------------------------------------------------ stockage

def _charger():
    global _CONNEXIONS
    if _CONNEXIONS is not None:
        return _CONNEXIONS
    with _VERROU:
        if _CONNEXIONS is None:
            try:
                donnees = json.loads(_STOCK.read_text(encoding="utf-8"))
                _CONNEXIONS = donnees if isinstance(donnees, dict) else {}
            except (OSError, ValueError):
                _CONNEXIONS = {}
    return _CONNEXIONS


def _sauver():
    try:
        _STOCK.parent.mkdir(parents=True, exist_ok=True)
        _STOCK.write_text(
            json.dumps(_charger(), ensure_ascii=False, indent=1),
            encoding="utf-8")
    except OSError:
        pass


def connexion(provider_id):
    """La connexion stockee pour ce provider, ou None."""
    with _VERROU:
        c = _charger().get(provider_id)
        return dict(c) if c else None


def connectes_ids():
    """Ids des providers reellement connectes (jetons presents)."""
    with _VERROU:
        return [k for k, v in _charger().items()
                if v.get("access_token_encrypted")]


def enregistrer_connexion(provider_id, provider_account_id, access_token,
                          refresh_token="", expires_in=0, scopes=""):
    """Stocke la connexion chiffree (apres un echange de code REUSSI)."""
    entree = {
        "provider": provider_id,
        "provider_account_id": str(provider_account_id or "")[:120],
        "access_token_encrypted": _chiffrer(access_token),
        "refresh_token_encrypted": _chiffrer(refresh_token),
        "expires_at": time.time() + float(expires_in or 0),
        "scopes": str(scopes or "")[:400],
        "metadata": {},
        "created_at": time.time(),
        "updated_at": time.time(),
    }
    with _VERROU:
        existante = _charger().get(provider_id)
        if existante:
            entree["created_at"] = existante.get("created_at", time.time())
            entree["metadata"] = existante.get("metadata", {})
        _charger()[provider_id] = entree
        _sauver()
    return entree


def supprimer_connexion(provider_id):
    """Retire la connexion du stockage local. Renvoie True si supprimee."""
    with _VERROU:
        if provider_id in _charger():
            del _charger()[provider_id]
            _sauver()
            return True
    return False


def jeton_acces(provider_id):
    """Jeton d'acces en clair (usage serveur uniquement), ou ''."""
    c = connexion(provider_id)
    if not c:
        return ""
    jeton = _dechiffrer(c.get("access_token_encrypted", ""))
    if not jeton:
        return ""
    if c.get("expires_at", 0) and time.time() > c["expires_at"] - 60:
        rafraichi = rafraichir(provider_id)
        return rafraichi or jeton
    return jeton


def rafraichir(provider_id):
    """Utilise le refresh_token pour obtenir un nouvel access_token.
    Sert le backend (jamais le navigateur). Renvoie le jeton ou ''."""
    c = connexion(provider_id)
    p = provider(provider_id)
    if not c or not p:
        return ""
    refresh = _dechiffrer(c.get("refresh_token_encrypted", ""))
    if not refresh:
        return ""
    cid, secret = _ids(p)
    if not (cid and secret):
        return ""
    try:
        import requests
        r = requests.post(p["tokenEndpoint"], data={
            "grant_type": "refresh_token",
            "refresh_token": refresh,
            "client_id": cid,
            "client_secret": secret,
        }, timeout=15)
        if r.status_code != 200:
            return ""
        donnees = r.json()
        jeton = donnees.get("access_token", "")
        if not jeton:
            return ""
        enregistrer_connexion(
            provider_id, c.get("provider_account_id", ""), jeton,
            refresh_token=donnees.get("refresh_token", refresh),
            expires_in=donnees.get("expires_in", 0),
            scopes=donnees.get("scope", c.get("scopes", "")))
        return jeton
    except Exception:
        return ""


# ---------------------------------------------------------------- state
# state cryptographique + PKCE. Chaque state ne sert qu'une fois et expire.

def _purger_etats():
    limite = time.time() - 600
    for s in [k for k, v in _ETATS.items() if v["expire"] < limite]:
        del _ETATS[s]


def preparer_state(provider_id):
    """Genere (state, verifier, challenge) pour un flux. Stocke le state."""
    state = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode("ascii")).digest()
    ).rstrip(b"=").decode("ascii")
    with _VERROU:
        _purger_etats()
        _ETATS[state] = {"provider": provider_id, "expire": time.time() + 600,
                         "verifier": verifier}
    return state, verifier, challenge


def valider_state(provider_id, state):
    """Consomme le state (usage unique). Renvoie le verifier PKCE ou None."""
    if not state:
        return None
    with _VERROU:
        _purger_etats()
        attente = _ETATS.pop(state, None)
    if not attente or attente["provider"] != provider_id:
        return None
    if time.time() > attente["expire"]:
        return None
    return attente["verifier"]


# --------------------------------------------------------------- echange

def _redirect_uri(base_url, provider_id):
    return f"{base_url}/api/integrations/{provider_id}/callback"


def url_autorisation(provider_id, base_url):
    """L'URL OAuth REELLE du provider, avec state + PKCE. None si non
    configure — jamais de simulation."""
    p = provider(provider_id)
    if not p or not configure(provider_id):
        return None
    cid, _ = _ids(p)
    state, _, challenge = preparer_state(provider_id)
    params = {
        "client_id": cid,
        "response_type": "code",
        "redirect_uri": _redirect_uri(base_url, provider_id),
        "scope": " ".join(p["scopes"]),
        "state": state,
        "access_type": "offline",
        "prompt": "consent",
    }
    if p["pkce"]:
        params["code_challenge"] = challenge
        params["code_challenge_method"] = "S256"
    from urllib.parse import urlencode
    return f"{p['oauthAuthorizationUrl']}?{urlencode(params)}"


def echanger_code(provider_id, code, verifier=""):
    """Echange le code d'autorisation contre les jetons, chez le provider.
    Renvoie (entree_stockee, None) ou (None, message d'erreur propre)."""
    p = provider(provider_id)
    if not p:
        return None, "Unknown integration."
    cid, secret = _ids(p)
    if not (cid and secret):
        return None, "This integration requires additional setup."
    try:
        import requests
        donnees = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": _redirect_uri(_base_url_locale(), provider_id),
            "client_id": cid,
            "client_secret": secret,
        }
        if p["pkce"] and verifier:
            donnees["code_verifier"] = verifier
        donnees.update(p.get("extraTokenParams", {}))
        r = requests.post(p["tokenEndpoint"], data=donnees, timeout=20,
                          headers={"Accept": "application/json"})
        if r.status_code != 200:
            return None, "Unable to connect this account."
        reponse = r.json()
        jeton = reponse.get("access_token", "")
        if not jeton:
            return None, "Unable to connect this account."
        compte = _identifiant_compte(provider_id, jeton, reponse)
        entree = enregistrer_connexion(
            provider_id, compte, jeton,
            refresh_token=reponse.get("refresh_token", ""),
            expires_in=reponse.get("expires_in", 0),
            scopes=reponse.get("scope", " ".join(p["scopes"])))
        return entree, None
    except Exception:
        return None, "Unable to connect this account."


def _identifiant_compte(provider_id, jeton, reponse):
    """L'identifiant de compte cote provider, quand l'API le permet."""
    try:
        import requests
        if provider_id in ("gmail", "gcal", "gdrive"):
            if reponse.get("id_token"):
                import base64 as b64
                morceaux = reponse["id_token"].split(".")
                if len(morceaux) >= 2:
                    charge = b64.urlsafe_b64decode(
                        morceaux[1] + "=" * (-len(morceaux[1]) % 4))
                    return json.loads(charge).get("email", "")
            return ""
        if provider_id == "github":
            r = requests.get("https://api.github.com/user",
                             headers={"Authorization": f"Bearer {jeton}"},
                             timeout=10)
            return r.json().get("login", "") if r.status_code == 200 else ""
        if provider_id == "slack":
            return str(reponse.get("team", {}).get("id", ""))
        if provider_id == "notion":
            return str(reponse.get("bot_id", "") or
                       reponse.get("workspace_id", ""))
        if provider_id == "linear":
            return str(reponse.get("user", {}).get("id", ""))
    except Exception:
        pass
    return ""


def deconnecter(provider_id):
    """Revocation officielle chez le provider (best effort), puis suppression
    locale. Renvoie True si la connexion locale a ete supprimee."""
    p = provider(provider_id)
    jeton = jeton_acces(provider_id)
    if p and p.get("revokeEndpoint") and jeton:
        cid, secret = _ids(p)
        try:
            import requests
            url = p["revokeEndpoint"]
            if "{client_id}" in url:
                if not cid:
                    return supprimer_connexion(provider_id)
                url = url.format(client_id=cid)
                # GitHub : revocation = DELETE avec basic auth (spec officielle)
                r = requests.delete(
                    url, auth=(cid, secret),
                    json={"access_token": jeton}, timeout=10)
            else:
                r = requests.post(url, data={"token": jeton}, timeout=10)
            # La revocation best-effort n'echoue jamais la deconnexion locale.
        except Exception:
            pass
    return supprimer_connexion(provider_id)


def _base_url_locale():
    """Base des URLs de callback : serveur local de Jarvis, jamais expose.
    Meme logique de resolution du port que core/serveur._port() : le port
    REEL du serveur web, pas celui du transport MCP (8765)."""
    port = int(reglage("serveur.port",
                       reglage("pont_iphone.port", 8790)) or 8790)
    return f"http://127.0.0.1:{port}"


# ----------------------------------------------------------------- vues
# Ce qui part vers le navigateur : JAMAIS de jetons, JAMAIS de secrets.

def vue_catalogue():
    """Catalogu pour la page INTEGRATIONS : metadata + etat REEL."""
    connects = set(connectes_ids())
    vues = []
    for p in CATALOGUE:
        est_connecte = p["id"] in connects
        vues.append({
            "id": p["id"],
            "name": p["name"],
            "slug": p["slug"],
            "description": p["description"],
            "category": p["category"],
            "capabilities": p["capabilities"],
            "scopes": p["scopes"],
            "authType": p["authType"],
            "enabled": configure(p["id"]),
            "requiresOAuth": True,
            "documentationUrl": p["documentationUrl"],
            "connected": est_connecte,
            "status": ("connected" if est_connecte else
                       "available" if configure(p["id"]) else "setup_required"),
        })
    return vues


def vue_connexion(provider_id):
    """Etat de connexion d'un provider pour le navigateur : compte, scopes,
    dates — jamais les jetons."""
    c = connexion(provider_id)
    if not c:
        return None
    return {
        "provider": provider_id,
        "providerAccountId": c.get("provider_account_id", ""),
        "scopes": c.get("scopes", ""),
        "connectedAt": c.get("created_at", 0),
        "expiresAt": c.get("expires_at", 0),
    }
