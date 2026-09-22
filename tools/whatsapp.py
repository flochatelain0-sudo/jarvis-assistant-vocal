"""WhatsApp via Twilio : envoyer un message, relancer un numero.Envoie par l'API Twilio (whatsapp:+33...). Configuration dans config.yaml :    whatsapp:
      sid: "ACxxxxxxxx"           # Account SID Twilio
      token: "auth_token"         # Auth Token Twilio      expediteur: "whatsapp:+14155238886"   # numero WhatsApp Twilio envoyer_whatsapp est marque confirmation=True : Jarvis demande toujours
l'accord avant d'envoyer (doctrine 95/5 — un message ecrit engage).
"""
import logging
import urllib.parse
import urllib.request

from core.config import reglage
from core.registre import outil

LOG = logging.getLogger("jarvis")


def _config():
    """(sid, token, expediteur) ou None si Twilio n'est pas configure."""
    sid = (reglage("whatsapp.sid", "") or "").strip()
    token = (reglage("whatsapp.token", "") or "").strip()
    expediteur = (reglage("whatsapp.expediteur", "") or "").strip()
    if not (sid and token and expediteur):
        return None
    return sid, token, expediteur


def _numero(n):
    """Normalise un numero saisi en format international whatsapp:+33...
    Le 0 initial est l'indicatif national francais : on le remplace par +33."""
    n = (n or "").strip().replace(" ", "").replace("-", "").replace(".", "")
    if n.startswith("whatsapp:"):
        return n
    if n.startswith("+"):
        return "whatsapp:" + n
    if n.startswith("0"):
        return "whatsapp:+33" + n[1:]
    return "whatsapp:+" + n


def envoyer_whatsapp(numero: str, message: str) -> str:
    """Envoie le message WhatsApp via l'API Twilio."""
    conf = _config()
    if not conf:
        return ("WhatsApp n'est pas configure : mets whatsapp.sid, whatsapp.token "
                "et whatsapp.expediteur dans config.yaml (docs/whatsapp.md).")
    sid, token, expediteur = conf
    url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
    donnees = urllib.parse.urlencode({
        "From": expediteur,
        "To": _numero(numero),
        "Body": message,
    }).encode()
    requete = urllib.request.Request(url, data=donnees)
    import base64
    auth = base64.b64encode(f"{sid}:{token}".encode()).decode()
    requete.add_header("Authorization", f"Basic {auth}")
    try:
        with urllib.request.urlopen(requete, timeout=15) as rep:
            rep.read()
        return f"Message WhatsApp envoye a {numero}."
    except Exception as e:
        LOG.exception("envoi WhatsApp")
        return f"Echec de l'envoi WhatsApp : {e}"


def _annonce_envoi(args):
    return f"Je vais envoyer le message WhatsApp a {args.get('numero', 'ce numero')}."


@outil(
    nom="envoyer_whatsapp",
    description="Envoie un message WhatsApp a un numero via Twilio. Pour "
                "'envoie un WhatsApp a John au 06 12 34 56 78 disant bonjour', "
                "'relance la famille Lopez sur WhatsApp'. Le numero doit etre "
                "en format international (+33...).",
    parametres={
        "type": "object",
        "properties": {
            "numero": {"type": "string", "description": "Numero international (+33...)."},
            "message": {"type": "string", "description": "Texte du message."},
        },
        "required": ["numero", "message"],
    },
    confirmation=True,
    annonce=_annonce_envoi,
)
def outil_envoyer_whatsapp(numero: str, message: str) -> str:
    return envoyer_whatsapp(numero, message)
