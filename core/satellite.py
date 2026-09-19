"""Satellites — Jarvis dans une AUTRE pièce (Raspberry Pi, futur ESP32).

Un satellite est une extension du CORPS de Jarvis (oreilles + bouche + visage
déportés). Le CERVEAU reste sur le PC : le satellite capte l'audio, le PC
transcrit (Whisper) → LLM + outils → TTS, et renvoie l'audio + des événements
d'état pour le visage/HUD du boîtier. Hermes n'est pas concerné.

PROTOCOLE (volontairement simple et transport-agnostique -> un ESP32 l'utilise
À L'IDENTIQUE) : un WebSocket /satellite, deux types de trames :
  • TRAMES TEXTE = messages de CONTRÔLE, JSON (voir docs/satellite.md) ;
  • TRAMES BINAIRES = audio PCM brut 16 bits little-endian, mono, 16 kHz.

Client -> serveur :
  {"type":"hello","satellite":"cuisine","token":"..."}   (auth + identité)
  <frames binaires PCM>                                   (pendant une phrase)
  {"type":"fin_parole"}                                   (fin d'énoncé -> traiter)
  {"type":"ping"}
Serveur -> client :
  {"type":"pret","piece":"cuisine"}
  {"type":"etat","etat":"ecoute|reflexion|parole|attente_confirmation|veille"}
  {"type":"texte","texte":"..."}                          (réponse affichable)
  {"type":"audio_debut","freq":24000}                     (puis frames binaires)
  {"type":"audio_fin"}
  {"type":"relance","secondes":8}                          (suivi sans wake word)
  {"type":"veille_forcee"}                                  (wake word requis)
  {"type":"erreur","message":"..."}

SÉCURITÉ : LAN-only (jamais exposé via ngrok — cf. la garde X-Forwarded), un
TOKEN par satellite (config satellites[].token, comparé en timing-safe). Un
satellite a les droits d'une commande vocale à la maison : N1/N2 direct, N3 avec
CONFIRMATION vocale sur le satellite lui-même (aller-retour attente_confirmation).

MULTI-PIÈCES : chaque satellite a une `piece` (config) injectée en contexte -> «
allume la lumière » depuis la cuisine cible la cuisine par défaut.

MODE NUIT (prévu, PAS implémenté) : le protocole et la config laissent la place à
un satellite Pi qui, PC éteint, assurerait la domotique en autonomie et
réveillerait le PC via la Tapo (cf. wol.md). Rien ici ne le rend impossible :
le dispatch est isolé (_traiter), la détection « PC éteint » se ferait côté Pi.
"""
import asyncio
import json
import ipaddress
import logging
import secrets
import socket
import threading
import time

from core.config import reglage

LOG = logging.getLogger("jarvis.satellite")

TAUX = 16000                      # PCM entrant : 16 kHz mono 16-bit LE (comme le micro PC)
_MAX_UTTERANCE = TAUX * 2 * 30    # garde-fou : 30 s d'audio max par énoncé (octets)
_APP_LAN = None
_SERVEUR_LAN = None


def _origine_locale_ou_lan(ws) -> bool:
    """Refuse les reverse proxies et les clients hors du réseau local.

    Le tunnel ngrok termine sa connexion sur le PC en loopback, donc l'adresse
    socket seule ne suffit pas : ses en-têtes ``Forwarded``/``X-Forwarded-*``
    sont également bloqués. Un satellite réel arrive directement avec une
    adresse privée du LAN.
    """
    entetes = getattr(ws, "headers", {}) or {}
    for nom in ("forwarded", "x-forwarded-for", "x-forwarded-host",
                "x-forwarded-proto", "x-real-ip"):
        if entetes.get(nom):
            return False
    client = getattr(ws, "client", None)
    hote = str(getattr(client, "host", "") or "").split("%", 1)[0]
    try:
        adresse = ipaddress.ip_address(hote)
    except ValueError:
        return False
    return adresse.is_loopback or adresse.is_private or adresse.is_link_local


def _satellites():
    """Dict id -> {piece, token, wake} depuis config.yaml (section satellites)."""
    out = {}
    for s in (reglage("satellites", []) or []):
        if isinstance(s, dict) and s.get("id"):
            out[str(s["id"])] = {
                "piece": str(s.get("piece", "") or ""),
                "token": str(s.get("token", "") or ""),
                "wake": str(s.get("wake", "appareil") or "appareil"),  # "appareil" | "serveur"
            }
    return out


def _systeme(piece):
    """Prompt système du satellite : Jarvis, avec le contexte de pièce."""
    base = ("Tu es Jarvis, assistant vocal, répondant depuis un satellite dans une "
            "pièce de la maison. Réponds en UNE à deux phrases courtes, en français, "
            "avec ta personnalité. Utilise les outils quand c'est utile.")
    if piece:
        base += (f" CONTEXTE : ce satellite est dans « {piece} ». Si l'utilisateur "
                 f"parle d'une lumière/pièce SANS préciser laquelle, utilise « {piece} » "
                 "par défaut.")
    return base


class _Session:
    """État d'une connexion satellite : identité, pièce, audio en cours, et une
    éventuelle action N3 en attente de confirmation vocale."""
    def __init__(self):
        self.satellite = None
        self.piece = ""
        self.audio = bytearray()
        self.historique = []
        self.en_attente = None     # (Outil, args) N3 à confirmer, ou None
        self.accuse_index = 0


def _transcrire(pcm_bytes):
    """PCM 16-bit LE mono 16 kHz -> texte (faster-whisper, modèle partagé lazy)."""
    import numpy as np
    audio = (np.frombuffer(bytes(pcm_bytes), dtype=np.int16).astype(np.float32) / 32768.0)
    if audio.size < TAUX * 0.3:
        return ""
    modele = _whisper()
    if modele is None:
        return ""
    segments, _ = modele.transcribe(audio, language="fr", beam_size=1)
    return " ".join(s.text for s in segments).strip()


_WHISPER = None


def _whisper():
    """Whisper dédié au satellite.

    Le Jarvis principal utilise déjà le GPU. Charger un second modèle dessus peut
    faire échouer CTranslate2 avec ``CUDA failed`` ; le satellite privilégie donc
    un petit modèle CPU/int8, stable et suffisamment rapide pour de courtes phrases.
    """
    global _WHISPER
    if _WHISPER is None:
        try:
            from faster_whisper import WhisperModel
            nom = reglage("satellite_lan.whisper_modele", "small")
            appareil = reglage("satellite_lan.whisper_device", "cpu")
            calcul = reglage("satellite_lan.whisper_compute_type", "int8")
            _WHISPER = WhisperModel(nom, device=appareil, compute_type=calcul)
            LOG.info(
                "satellite: Whisper %s sur %s (%s)", nom, appareil, calcul
            )
        except Exception:
            LOG.exception("satellite: chargement Whisper")
            _WHISPER = None
    return _WHISPER


def _tts_pcm(texte):
    """Synthétise `texte` -> (pcm_bytes 16-bit LE mono, frequence_hz) ou (b"", 0)."""
    try:
        from core.tts import tts
        res = tts().synthetiser(texte)
        if not res:
            return b"", 0
        import numpy as np
        audio, freq = res
        pcm = np.asarray(audio, dtype=np.int16).tobytes()
        return pcm, int(freq)
    except Exception:
        LOG.exception("satellite: TTS")
        return b"", 0


_TTS_COURT = {}
_TTS_COURT_LOCK = threading.Lock()
_ACCUSES_COURTS = (
    "Mmh, je vois.",
    "D'accord, un instant.",
    "Oui, je regarde.",
)


def _tts_pcm_court(texte):
    """TTS mis en cache pour les accusés répétés du satellite.

    Le premier passage utilise le moteur vocal configuré ; les suivants évitent
    un nouvel appel cloud et partent presque immédiatement.
    """
    with _TTS_COURT_LOCK:
        if texte in _TTS_COURT:
            return _TTS_COURT[texte]
        resultat = _tts_pcm(texte)
        if resultat[0]:
            _TTS_COURT[texte] = resultat
        return resultat


def _accuse_court(session):
    texte = _ACCUSES_COURTS[session.accuse_index % len(_ACCUSES_COURTS)]
    session.accuse_index += 1
    return texte


def _phrase_progression(phrase):
    """Retour vocal court, relié à l'intention, pendant un traitement long."""
    from core.util import sans_accents
    p = sans_accents((phrase or "").lower())
    if any(m in p for m in (
            "cherche", "recherche", "sur internet", "sur le web", "trouve-moi",
            "trouve moi", "actualite", "derniere nouvelle")):
        return "Je lance la recherche."
    if "meteo" in p or "temps fait" in p:
        return "Je regarde la météo."
    if any(m in p for m in ("quelle heure", "donne-moi l'heure", "donne moi l'heure")):
        return "Je vérifie l'heure."
    if any(m in p for m in (
            "allume", "eteins", "éteins", "ouvre", "ferme", "lance", "mets ",
            "augmente", "baisse")):
        return "Je m'en occupe."
    if any(m in p for m in ("pourquoi", "comment", "quel", "quelle", "est-ce")):
        return "Je vérifie ça."
    return "Mmh, je réfléchis."


def _demande_veille(phrase):
    """Détecte une demande explicite de retour au mot d'activation."""
    import re
    from core.util import sans_accents
    p = " ".join(re.sub(
        r"[^a-z0-9]+", " ", sans_accents((phrase or "").lower())
    ).split())
    expressions = (
        "mets toi en veille",
        "met toi en veille",
        "passe en veille",
        "va en veille",
        "dors",
        "endors toi",
        "rendors toi",
        "arrete d ecouter",
        "arrete de m ecouter",
    )
    return any(expression in p for expression in expressions)


def _executer_outil(nom, args):
    """Exécute un outil N1/N2 (les N3 ne passent JAMAIS par ici)."""
    from core import registre
    outil = registre.get(nom)
    if outil is None:
        return f"Outil inconnu : {nom}"
    try:
        return str(outil.fonction(**(args or {})))
    except Exception:
        LOG.exception("satellite: outil %s", nom)
        return "Erreur pendant l'action."


def traiter_texte(session, phrase):
    """Fait tourner la phrase dans le LLM + outils, avec contexte pièce et droits
    maison (N1/N2 direct, N3 -> mis en attente de confirmation). Renvoie un dict
    {reponse, attente_confirmation(bool)}."""
    from core import registre
    from core.llm import llm
    P = llm()
    if not P.disponible():
        return {"reponse": "Le cerveau de Jarvis n'est pas disponible.", "attente_confirmation": False}

    session.historique.append({"role": "user", "content": phrase})
    faits = []
    for _ in range(5):
        try:
            rep = P.repondre(_systeme(session.piece), session.historique,
                             registre.schemas_api(local_seulement=(P.nom == "Ollama")))
        except Exception as e:
            LOG.exception("satellite: appel modèle")
            return {"reponse": f"Erreur du cerveau ({e}).", "attente_confirmation": False}

        if getattr(rep, "stop_reason", None) != "tool_use":
            texte = " ".join(b.text for b in rep.content
                             if getattr(b, "type", None) == "text").strip()
            session.historique.append({"role": "assistant", "content": texte or "C'est fait."})
            return {"reponse": texte or ("C'est fait." if faits else "D'accord."),
                    "attente_confirmation": False}

        session.historique.append({"role": "assistant", "content": rep.content})
        resultats = []
        for b in rep.content:
            if getattr(b, "type", None) != "tool_use":
                continue
            # N3 : action critique -> on NE l'exécute pas ; on la met en attente et
            # on demande confirmation vocale sur le satellite (aller-retour).
            if registre.est_n3(b.name):
                session.en_attente = (b.name, b.input or {})
                o = registre.get(b.name)
                q = None
                if o is not None and getattr(o, "annonce", None):
                    try:
                        q = o.annonce(b.input or {})
                    except Exception:
                        q = None
                return {"reponse": (q or "C'est une action critique.") + " Tu confirmes ? (oui / non)",
                        "attente_confirmation": True}
            res = _executer_outil(b.name, b.input or {})
            faits.append(b.name)
            resultats.append({"type": "tool_result", "tool_use_id": b.id, "content": str(res)})
        session.historique.append({"role": "user", "content": resultats})
    return {"reponse": "Commande trop longue à traiter.", "attente_confirmation": False}


def _resoudre_confirmation(session, phrase):
    """L'utilisateur répond oui/non à une action N3 en attente. Renvoie le texte."""
    from core.util import sans_accents
    nom, args = session.en_attente
    session.en_attente = None
    p = sans_accents(phrase.lower())
    oui = any(m in p for m in ("oui", "ok", "vas-y", "vas y", "confirme", "d'accord", "daccord", "fais"))
    if not oui:
        return "D'accord, j'annule."
    return _executer_outil(nom, args)


# ---------------------------------------------------------------- WebSocket

def monter_routes(app):
    """Monte le WebSocket /satellite sur le serveur unifié (appelé par core.serveur)."""
    from fastapi import WebSocket, WebSocketDisconnect

    @app.websocket("/satellite")
    async def satellite(ws: WebSocket):
        if not _origine_locale_ou_lan(ws):
            LOG.warning("satellite: connexion hors LAN refusee")
            await ws.close(code=1008, reason="satellite accessible uniquement sur le LAN")
            return
        await ws.accept()
        cfg = _satellites()
        sess = _Session()

        async def envoyer(obj):
            await ws.send_text(json.dumps(obj, ensure_ascii=False))

        async def etat(e):
            await envoyer({"type": "etat", "etat": e})

        async def envoyer_audio(texte, court=False):
            synthese = _tts_pcm_court if court else _tts_pcm
            pcm, freq = await asyncio.to_thread(synthese, texte)
            if pcm:
                await envoyer({"type": "audio_debut", "freq": freq})
                for i in range(0, len(pcm), 4096):
                    await ws.send_bytes(pcm[i:i + 4096])
                await envoyer({"type": "audio_fin"})

        async def parler(texte):
            """Envoie le texte (affichage) puis l'audio TTS (frames binaires)."""
            await envoyer({"type": "texte", "texte": texte})
            await etat("parole")
            await envoyer_audio(texte)

        async def progresser(texte):
            """Parle brièvement sans ajouter l'accusé à l'historique LLM."""
            await envoyer({"type": "progression", "texte": texte})
            await etat("parole")
            await envoyer_audio(texte, court=True)
            await etat("reflexion")

        async def proposer_relance(secondes=None):
            if not bool(reglage("satellite_lan.conversation_suivie", True)):
                return
            try:
                duree = float(secondes if secondes is not None else reglage(
                    "satellite_lan.fenetre_relance", 8.0))
            except (TypeError, ValueError):
                duree = 8.0
            duree = max(0.0, min(duree, 30.0))
            if duree:
                await envoyer({"type": "relance", "secondes": duree})

        try:
            while True:
                msg = await ws.receive()
                # 1) trame binaire = audio PCM
                if "bytes" in msg and msg["bytes"] is not None:
                    if sess.satellite is None:      # pas encore authentifié
                        continue
                    sess.audio.extend(msg["bytes"])
                    if len(sess.audio) > _MAX_UTTERANCE:
                        sess.audio = sess.audio[-_MAX_UTTERANCE:]
                    continue
                # 2) trame texte = contrôle
                if "text" not in msg or msg["text"] is None:
                    if msg.get("type") == "websocket.disconnect":
                        break
                    continue
                try:
                    data = json.loads(msg["text"])
                except Exception:
                    continue
                typ = data.get("type")

                if typ == "hello":
                    sid = str(data.get("satellite", ""))
                    conf = cfg.get(sid)
                    if not conf or not conf["token"] or not secrets.compare_digest(
                            str(data.get("token", "")), conf["token"]):
                        await envoyer({"type": "erreur", "message": "satellite inconnu ou token invalide"})
                        await ws.close(code=1008)
                        return
                    sess.satellite, sess.piece = sid, conf["piece"]
                    LOG.info("satellite connecté : %s (pièce %s)", sid, sess.piece or "?")
                    await envoyer({"type": "pret", "piece": sess.piece})
                    await etat("veille")

                elif typ == "fin_parole" and sess.satellite:
                    audio = bytes(sess.audio)
                    sess.audio = bytearray()
                    await etat("reflexion")
                    transcription = asyncio.create_task(
                        asyncio.to_thread(_transcrire, audio))
                    if bool(reglage("satellite_lan.accuse_immediat", True)):
                        await progresser(_accuse_court(sess))
                    try:
                        attente_stt = float(reglage(
                            "satellite_lan.progression_transcription_apres", 5.0))
                    except (TypeError, ValueError):
                        attente_stt = 5.0
                    try:
                        phrase = await asyncio.wait_for(
                            asyncio.shield(transcription), timeout=max(0.1, attente_stt))
                    except asyncio.TimeoutError:
                        await progresser("Je t'ai bien entendue, je traite ça.")
                        phrase = await transcription
                    if not phrase:
                        await parler("Je n'ai rien entendu.")
                        await proposer_relance()
                        await etat("veille")
                        continue
                    await envoyer({"type": "transcription", "texte": phrase})
                    if _demande_veille(phrase):
                        # Une mise en veille annule aussi une éventuelle action N3
                        # encore en attente : elle ne doit jamais être confirmée plus tard.
                        sess.en_attente = None
                        await parler("D'accord, je me mets en veille.")
                        await envoyer({"type": "veille_forcee"})
                        await etat("veille")
                        continue
                    if sess.en_attente:                         # réponse à une confirmation N3
                        rep = _resoudre_confirmation(sess, phrase)
                        await parler(rep)
                        await proposer_relance()
                        await etat("veille")
                        continue
                    traitement = asyncio.create_task(
                        asyncio.to_thread(traiter_texte, sess, phrase))
                    try:
                        attente_llm = float(reglage(
                            "satellite_lan.progression_traitement_apres", 4.0))
                    except (TypeError, ValueError):
                        attente_llm = 4.0
                    try:
                        r = await asyncio.wait_for(
                            asyncio.shield(traitement), timeout=max(0.1, attente_llm))
                    except asyncio.TimeoutError:
                        await progresser(_phrase_progression(phrase))
                        r = await traitement
                    if r["attente_confirmation"]:
                        await envoyer({"type": "texte", "texte": r["reponse"]})
                        await etat("attente_confirmation")
                        await envoyer_audio(r["reponse"])
                        await proposer_relance(12.0)
                    else:
                        await parler(r["reponse"])
                        await proposer_relance()
                        await etat("veille")

                elif typ == "ping":
                    await envoyer({"type": "pong"})

        except WebSocketDisconnect:
            pass
        except Exception:
            LOG.exception("satellite: boucle WS")
        finally:
            LOG.info("satellite déconnecté : %s", sess.satellite)

    LOG.info("satellite: route /satellite montée (LAN, token par satellite)")


def _app_lan():
    """Application FastAPI minimale exposée au LAN : `/satellite` seulement."""
    global _APP_LAN
    if _APP_LAN is None:
        from fastapi import FastAPI
        _APP_LAN = FastAPI(
            title="Jarvis Satellite LAN",
            docs_url=None,
            redoc_url=None,
            openapi_url=None,
        )
        monter_routes(_APP_LAN)
    return _APP_LAN


def demarrer_lan():
    """Démarre le listener satellite dédié sans exposer le serveur unifié.

    Le port n'est ouvert que lorsqu'au moins un satellite est configuré. Le
    panneau, le cockpit, l'inbox iPhone et Twilio restent sur le listener
    loopback principal.
    """
    global _SERVEUR_LAN
    if not _satellites() or not bool(reglage("satellite_lan.actif", True)):
        return
    if _SERVEUR_LAN and _SERVEUR_LAN.is_alive():
        return

    import uvicorn
    hote = str(reglage("satellite_lan.host", "0.0.0.0") or "0.0.0.0")
    port = int(reglage("satellite_lan.port", 8791))
    serveur = uvicorn.Server(uvicorn.Config(
        _app_lan(), host=hote, port=port, log_level="warning"))

    def run():
        try:
            serveur.run()
        except Exception:
            LOG.exception("satellite: serveur LAN")

    _SERVEUR_LAN = threading.Thread(
        target=run, daemon=True, name="satellite-lan")
    _SERVEUR_LAN.start()
    for _ in range(40):
        try:
            socket.create_connection(("127.0.0.1", port), 0.15).close()
            break
        except OSError:
            time.sleep(0.15)
    LOG.info("satellite: listener LAN actif sur %s:%d", hote, port)
