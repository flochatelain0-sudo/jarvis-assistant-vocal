"""Integrations : l'etat REEL de connexion de chaque plateforme.

La console ZOEY OS affiche « Connect Gmail », « Connect GitHub »... Derriere,
il n'y a pas de bouton magique : une plateforme est connectee quand sa
config existe (config.yaml) ou son jeton est pose (google_token_*.json).
Ce module fait le pont — il LIT, il ne cree aucun droit nouveau.

Chaque integration expose :
  id        : cle stable cote console
  nom       : libelle affiche
  connecte  : vrai si la plateforme est prete a l'emploi
  detail    : ce qui manque, phrase courte, ou vide si tout va bien
"""

import threading
from pathlib import Path

from core.config import reglage

_RACINE = Path(__file__).resolve().parent.parent
_VERROU = threading.RLock()


def _fichier_existe(cle_config, defaut):
    chemin = reglage(cle_config, defaut) or defaut
    p = Path(chemin)
    p = p if p.is_absolute() else (_RACINE / p)
    return p.exists()


def _gmail_connecte():
    adresse = (reglage("mail.adresse", "") or "").strip()
    oauth = bool(reglage("mail.oauth", False))
    mdp = bool((reglage("mail.mot_de_passe_app", "") or "").strip())
    token = _fichier_existe("mail.token", "google_token_mail.json")
    if not adresse:
        return False, "Adresse Gmail absente de config.yaml (mail.adresse)."
    if oauth or mdp or token:
        return True, ""
    return False, "Mot de passe d'application ou OAuth requis (mail.mot_de_passe_app)."


def _agenda_connecte():
    token = _fichier_existe("agenda.token", "google_token_agenda.json")
    ident = _fichier_existe("agenda.credentials", "google_credentials.json")
    if token:
        return True, ""
    if ident:
        return False, "Identifiants presents — lance scripts/google_login.py agenda."
    return False, "google_credentials.json absent. Voir docs/agenda.md."


def _navigateur_connecte():
    actif = bool(reglage("navigateur.actif", True))
    if not actif:
        return False, "Navigateur desactive (navigateur.actif)."
    return True, ""


def _pc_connecte():
    if bool(reglage("astra_pc.actif", True)):
        return True, ""
    return False, "Astra desactive (astra_pc.actif)."


def _voix_connecte():
    # Le micro du HUD est vivant si la boucle tourne ; cote console on
    # considere l'audio configure des que l'entree par defaut existe.
    return True, ""


def _llm_connecte():
    for cle in ("anthropic.cle", "mistral.cle", "openai.cle", "google.cle",
                "groq.cle"):
        if (reglage(cle, "") or "").strip():
            return True, ""
    return False, "Aucune cle LLM dans config.yaml (anthropic.cle, mistral.cle...)."


# id -> (nom, fn) ; fn() -> (connecte, detail)
_INTEGRATIONS = {
    "gmail": ("Gmail", _gmail_connecte),
    "gcal": ("Google Calendar", _agenda_connecte),
    "github": ("GitHub", lambda: (False, "Non integre — passe par les outils navigateur.")),
    "mailchimp": ("Mailchimp", lambda: (False, "Non integre.")),
    "canva": ("Canva", lambda: (False, "Non integre.")),
    "shopify": ("Shopify", lambda: (False, "Non integre.")),
    "navigateur": ("Browser access", _navigateur_connecte),
    "pc": ("Local machine", _pc_connecte),
    "voix": ("Voice", _voix_connecte),
    "llm": ("LLM API", _llm_connecte),
}


def etat():
    """Etat de toutes les integrations, pour la console. Ne leve jamais."""
    avec = {}
    for ident, (nom, fn) in _INTEGRATIONS.items():
        try:
            connecte, detail = fn()
        except Exception:
            connecte, detail = False, "Etat indisponible."
        avec[ident] = {"id": ident, "nom": nom, "connecte": bool(connecte),
                       "detail": str(detail)[:160]}
    return avec


def est_connecte(ident):
    """Vrai si l'integration ident est prete (False si inconnue)."""
    avec = etat()
    return bool(avec.get(ident, {}).get("connecte"))
