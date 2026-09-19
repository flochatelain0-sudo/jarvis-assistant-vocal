"""Spotify : ajoute la musique reconnue à une playlist « Jarvis Finds ».

« ajoute-la à ma playlist » (la dernière musique reconnue), et option d'ajout
AUTOMATIQUE à chaque reconnaissance (spotify.auto_ajout). Auth OAuth : login une
fois (scripts/spotify_login.py), refresh_token réutilisé ensuite.

N1/N2 (écriture dans TA playlist). Non exposé au MCP par défaut. Voir docs/spotify.md.
"""
import base64
import json
import os
import threading
import time
from pathlib import Path
from urllib.parse import quote

try:
    import truststore
    truststore.inject_into_ssl()
except Exception:
    pass
import requests

from core.config import reglage
from core.registre import outil
from core.util import sans_accents

_RACINE = Path(__file__).resolve().parent.parent
_API = "https://api.spotify.com/v1"
_TOKEN = {"access": None, "exp": 0.0}
_PLAYLIST_ID = None
_VERROU = threading.Lock()


# ------------------------------------------------------ auth

def _fichier_token():
    return _RACINE / (reglage("spotify.dossier", "logs/spotify")) / "token.json"


def _refresh_token():
    f = _fichier_token()
    if f.exists():
        try:
            return (json.loads(f.read_text(encoding="utf-8")) or {}).get("refresh_token")
        except Exception:
            pass
    return reglage("spotify.refresh_token", "") or None


def _configure():
    return bool(reglage("spotify.client_id", "") and reglage("spotify.client_secret", "")
                and _refresh_token())


def _msg_config():
    return ("Spotify n'est pas connecté. Crée une app sur developer.spotify.com, mets "
            "client_id/secret dans config.yaml, puis lance "
            "« python scripts/spotify_login.py » — voir docs/spotify.md.")


def _access():
    if _TOKEN["access"] and time.time() < _TOKEN["exp"] - 30:
        return _TOKEN["access"]
    cid = reglage("spotify.client_id", "")
    secret = reglage("spotify.client_secret", "")
    auth = base64.b64encode(f"{cid}:{secret}".encode()).decode()
    r = requests.post("https://accounts.spotify.com/api/token",
                      data={"grant_type": "refresh_token",
                            "refresh_token": _refresh_token()},
                      headers={"Authorization": f"Basic {auth}"}, timeout=15)
    r.raise_for_status()
    d = r.json()
    _TOKEN["access"] = d["access_token"]
    _TOKEN["exp"] = time.time() + int(d.get("expires_in", 3600))
    return _TOKEN["access"]


def _h():
    return {"Authorization": f"Bearer {_access()}",
            "Content-Type": "application/json"}


# ------------------------------------------------------ playlist / recherche

def _me():
    return requests.get(f"{_API}/me", headers=_h(), timeout=15).json()


def _playlist_id(nom=None, creer=True):
    """Id d'une playlist par son nom. nom=None -> playlist par defaut (spotify.playlist,
    creee si absente). Un nom explicite n'est PAS cree s'il n'existe pas (creer=False
    conseille) -> renvoie None pour eviter une playlist creee par erreur de dictee."""
    global _PLAYLIST_ID
    par_defaut = nom is None
    cible = nom or reglage("spotify.playlist", "Jarvis Finds")
    if par_defaut and _PLAYLIST_ID:
        return _PLAYLIST_ID
    with _VERROU:
        url = f"{_API}/me/playlists?limit=50"
        while url:
            d = requests.get(url, headers=_h(), timeout=15).json()
            for pl in d.get("items", []):
                if sans_accents((pl.get("name") or "").lower()) == sans_accents(cible.lower()):
                    if par_defaut:
                        _PLAYLIST_ID = pl["id"]
                    return pl["id"]
            url = d.get("next")
        if not creer:
            return None
        uid = _me()["id"]
        r = requests.post(f"{_API}/users/{uid}/playlists", headers=_h(),
                          data=json.dumps({"name": cible, "public": False,
                                           "description": "Trouvailles de Jarvis."}),
                          timeout=15)
        r.raise_for_status()
        pid = r.json()["id"]
        if par_defaut:
            _PLAYLIST_ID = pid
        return pid


def _chercher_uri(titre, artiste):
    q = f"track:{titre} artist:{artiste}" if artiste else f"track:{titre}"
    r = requests.get(f"{_API}/search", headers=_h(),
                     params={"q": q, "type": "track", "limit": 1}, timeout=15)
    items = (r.json().get("tracks", {}) or {}).get("items", [])
    return items[0]["uri"] if items else None


def _chercher_media(recherche, type_media):
    """Premier titre/playlist Spotify correspondant à la recherche."""
    type_api = "playlist" if type_media == "playlist" else "track"
    r = requests.get(f"{_API}/search", headers=_h(), params={
        "q": recherche, "type": type_api, "limit": 1,
    }, timeout=15)
    r.raise_for_status()
    bloc = r.json().get(f"{type_api}s", {}) or {}
    items = [item for item in (bloc.get("items", []) or []) if item]
    return items[0] if items else None


def _demarrer_lecture(uri, type_media):
    corps = ({"context_uri": uri} if type_media == "playlist"
             else {"uris": [uri]})
    return requests.put(f"{_API}/me/player/play", headers=_h(),
                        data=json.dumps(corps), timeout=15)


def _deja_present(pid, uri):
    """Évite les doublons : l'URI est-elle déjà dans la playlist ?"""
    try:
        url = f"{_API}/playlists/{pid}/tracks?fields=items(track(uri)),next&limit=100"
        while url:
            d = requests.get(url, headers=_h(), timeout=15).json()
            for it in d.get("items", []):
                if ((it.get("track") or {}).get("uri")) == uri:
                    return True
            url = d.get("next")
    except Exception:
        pass
    return False


def _ajouter_titre(titre, artiste, playlist=None):
    """Ajoute (titre, artiste) à la playlist voulue (None = celle par défaut)."""
    if not (titre and str(titre).strip()):
        return "Je ne sais pas quelle musique ajouter."
    uri = _chercher_uri(titre, artiste)
    if not uri:
        return f"Je n'ai pas trouvé « {titre} » sur Spotify."
    demande = playlist.strip() if (playlist and playlist.strip()) else None
    pid = _playlist_id(demande, creer=(demande is None))
    if not pid:
        return (f"Je n'ai pas trouvé la playlist « {demande} » chez toi. "
                "Crée-la d'abord dans Spotify, ou dis-la sans préciser (j'utilise "
                f"{reglage('spotify.playlist', 'Jarvis Finds')}).")
    if _deja_present(pid, uri):
        return f"« {titre} » est déjà dans la playlist."
    r = requests.post(f"{_API}/playlists/{pid}/tracks", headers=_h(),
                      data=json.dumps({"uris": [uri]}), timeout=15)
    r.raise_for_status()
    nom = demande or reglage("spotify.playlist", "Jarvis Finds")
    return f"Ajoutée à {nom} : {titre}" + (f" de {artiste}." if artiste else ".")


# ------------------------------------------------------ auto-ajout (depuis musique)

def auto_ajouter(titre, artiste):
    """Appelé après une reconnaissance : ajoute en fond si spotify.auto_ajout."""
    if not reglage("spotify.auto_ajout", False) or not _configure():
        return
    def worker():
        try:
            _ajouter_titre(titre, artiste)
        except Exception:
            pass
    threading.Thread(target=worker, daemon=True, name="spotify-auto").start()


# ------------------------------------------------------ outils

@outil(
    nom="ajouter_a_playlist",
    description="Ajoute la DERNIÈRE musique reconnue (ou un titre donné) à une playlist "
                "Spotify. Par défaut « Jarvis Finds » ; précise une playlist avec le "
                "paramètre playlist. Pour « ajoute-la à ma playlist », « mets cette "
                "chanson dans ma playlist Chill », « ajoute ça à Spotify ».",
    parametres={
        "type": "object",
        "properties": {
            "titre": {"type": "string", "description": "Titre (optionnel ; vide = la "
                      "dernière musique reconnue)."},
            "artiste": {"type": "string", "description": "Artiste (optionnel)."},
            "playlist": {"type": "string", "description": "Nom d'une playlist précise "
                         "(optionnel ; vide = la playlist par défaut). Doit déjà exister."},
        },
    },
    lent=True,
    phrase_attente="J'ajoute ça à ta playlist.",
    mcp_expose=False,
    affichage="jamais",
)
def ajouter_a_playlist(titre: str = "", artiste: str = "", playlist: str = "") -> str:
    if not _configure():
        return _msg_config()
    if not (titre and titre.strip()):
        try:
            from tools import musique
            derniere = musique.derniere_reconnaissance()
        except Exception:
            derniere = None
        if not derniere:
            return "Je n'ai pas de musique récente à ajouter. Dis d'abord « c'est quoi cette musique ? »."
        titre, artiste = derniere
    try:
        return _ajouter_titre(titre, artiste, playlist)
    except requests.HTTPError as e:
        code = getattr(e.response, "status_code", 0)
        if code == 403:
            return ("Spotify refuse l'accès (403) : soit le droit d'écriture des "
                    "playlists n'est pas accordé, soit l'app est en mode développement "
                    "avec un autre compte. Relance « python scripts/spotify_login.py » "
                    "et clique bien « Agree » sur l'écran des permissions.")
        return f"Spotify a échoué ({str(e)[:120]})."
    except Exception as e:
        return f"Spotify a échoué ({str(e)[:120]})."


@outil(
    nom="lire_spotify",
    description="Recherche puis lance directement un morceau ou une playlist Spotify. "
                "Pour « joue Blinding Lights sur Spotify », « lance ma playlist Chill ». "
                "Ne sert pas à ajouter un morceau à une playlist.",
    parametres={
        "type": "object",
        "properties": {
            "recherche": {"type": "string", "description": "Nom du titre ou de la playlist."},
            "type_media": {"type": "string", "enum": ["titre", "playlist"]},
        },
        "required": ["recherche"],
    },
    lent=True,
    phrase_attente="Je cherche ça sur Spotify.",
    mcp_expose=False,
    affichage="jamais",
)
def lire_spotify(recherche: str, type_media: str = "titre") -> str:
    """Lance via Spotify Connect, avec repli sur l'application de bureau."""
    recherche = str(recherche or "").strip()
    type_media = "playlist" if type_media == "playlist" else "titre"
    if not recherche:
        return "Dis-moi quel titre ou quelle playlist lancer."

    if not _configure():
        try:
            os.startfile("spotify:search:" + quote(recherche, safe=""))
            return f"J'ai ouvert la recherche Spotify pour « {recherche} »."
        except Exception:
            return _msg_config()

    try:
        item = None
        if type_media == "playlist":
            pid = _playlist_id(recherche, creer=False)
            if pid:
                item = {"uri": f"spotify:playlist:{pid}", "name": recherche}
        if item is None:
            item = _chercher_media(recherche, type_media)
        if not item or not item.get("uri"):
            return f"Je n'ai pas trouvé « {recherche} » sur Spotify."

        nom = item.get("name") or recherche
        reponse = _demarrer_lecture(item["uri"], type_media)
        if reponse.status_code == 204:
            return f"Je lance « {nom} » sur Spotify."

        # Sans appareil Spotify Connect actif, sans Premium ou avec un ancien
        # jeton OAuth, le lien profond reste une action sûre et sans Astra.
        os.startfile(item["uri"])
        if reponse.status_code == 403:
            return (f"J'ai ouvert « {nom} » dans Spotify. Pour la lecture automatique, "
                    "reconnecte Spotify une fois afin d'autoriser le contrôle de lecture.")
        return f"J'ai ouvert « {nom} » dans Spotify."
    except requests.HTTPError as e:
        return f"Spotify a échoué ({str(e)[:120]})."
    except Exception as e:
        return f"Spotify a échoué ({str(e)[:120]})."
