"""Abstraction de la synthese vocale (TTS) : cloud ou local, meme interface.

Chaque provider expose `synthetiser(texte)` qui renvoie (audio_int16, frequence)
ou None. jarvis14 se charge de JOUER l'audio (avec sa gestion d'interruption) et
retombe sur la voix integree a l'OS si le provider renvoie None (SAPI sur
Windows, `say` sur macOS, espeak sur Linux — cf. core/plateforme).

  - PiperProvider      : local, 100% offline, voix francaise Piper (.onnx).
  - KokoroProvider     : local, kokoro-onnx (voix FR de qualite moyenne).
  - VoxtralProvider    : cloud, la voix de Mistral (voxtral-mini-tts-2603),
                         celle de Le Chat. Requiert mistral.cle + voxtral.voix.
  - OSProvider         : demande le repli gere par jarvis14.dire().

Choix par config.yaml (`tts.moteur`) et par le mode local/hybride/qualite.
Sans modele Piper installe, on retombe proprement sur la voix integree de
l'OS (SAPI sur Windows, `say` sur macOS, espeak sur Linux).

Note honnete sur le TTS local francais : Piper est recommande (voix FR eprouvees
comme fr_FR-siwis / fr_FR-tom, tres leger, temps reel sur CPU). Kokoro (kokoro-onnx)
ne propose qu'une voix FR recente et de qualite moyenne ; Piper est un meilleur
choix pour le francais aujourd'hui.
"""
import logging
from pathlib import Path

from core import plateforme
from core.config import reglage

LOG = logging.getLogger("jarvis")
_RACINE = Path(__file__).resolve().parent.parent


class ProviderTTS:
    nom = "?"

    def disponible(self):
        return True

    def synthetiser(self, texte):
        """Renvoie (numpy int16 mono, frequence_hz) ou None si indisponible."""
        return None


class OSProvider(ProviderTTS):
    """Demande volontairement le repli OS gere par jarvis14.dire()."""
    nom = "OS"


# --------------------------------------------------------------- Piper (local)

class PiperProvider(ProviderTTS):
    nom = "Piper"

    def __init__(self):
        self.modele = reglage("piper.modele", "")
        self._voix = None
        self._config = None

    def _synthese(self):
        """SynthesisConfig depuis config.yaml, ou None pour les defauts du modele.

        Les trois leviers qui rendent une voix Piper moins mecanique :
          vitesse      (length_scale) : >1 ralentit, <1 accelere
          expressivite (noise_scale)  : variation de l'intonation
          variation    (noise_w)      : variation de la duree des syllabes
        Piper part de 1.0 / 0.667 / 0.8 ; monter les deux derniers donne un
        debit moins regulier, donc plus humain.
        """
        if self._config is not None:
            return self._config or None
        try:
            from piper import SynthesisConfig
        except ImportError:
            self._config = False
            return None
        reglages = {
            "length_scale": reglage("piper.vitesse", None),
            "noise_scale": reglage("piper.expressivite", None),
            "noise_w_scale": reglage("piper.variation", None),
            "volume": reglage("piper.volume", None),
        }
        reglages = {k: float(v) for k, v in reglages.items() if v is not None}
        self._config = SynthesisConfig(**reglages) if reglages else False
        return self._config or None

    def _chemin(self):
        if not self.modele:
            # a defaut, prend le premier .onnx trouve dans voix/
            trouves = list((_RACINE / "voix").glob("*.onnx"))
            return trouves[0] if trouves else None
        p = Path(self.modele)
        return p if p.is_absolute() else (_RACINE / p)

    def disponible(self):
        c = self._chemin()
        return bool(c and c.exists())

    def _rendre(self, np, texte):
        """(audio int16, frequence) — gere les deux API de piper-tts.

        Depuis la 1.3, `synthesize(texte)` rend un flux d'AudioChunk (un par
        phrase) au lieu d'octets bruts ; `synthesize_stream_raw` a disparu. On
        garde les deux chemins pour ne pas casser une installation plus ancienne.
        """
        if hasattr(self._voix, "synthesize"):
            morceaux, frequence = [], None
            reglages = self._synthese()
            flux = (self._voix.synthesize(texte, reglages) if reglages
                    else self._voix.synthesize(texte))
            for bloc in flux:
                octets = getattr(bloc, "audio_int16_bytes", None)
                if octets is None:                       # repli : tableau float
                    arr = getattr(bloc, "audio_float_array", None)
                    if arr is not None:
                        octets = (np.asarray(arr) * 32767).astype(np.int16).tobytes()
                if octets:
                    morceaux.append(octets)
                if frequence is None:
                    frequence = getattr(bloc, "sample_rate", None)
            brut = b"".join(morceaux)
            if not brut:
                return None
            return (np.frombuffer(brut, dtype=np.int16),
                    frequence or getattr(self._voix.config, "sample_rate", 22050))

        brut = b"".join(self._voix.synthesize_stream_raw(texte))    # piper < 1.3
        return np.frombuffer(brut, dtype=np.int16), self._voix.config.sample_rate

    def synthetiser(self, texte):
        try:
            import numpy as np
            from piper import PiperVoice
        except ImportError:
            print("  [Piper] librairie piper-tts absente.")
            return None
        chemin = self._chemin()
        if chemin is None or not chemin.exists():
            print("  [Piper] aucun modele de voix (.onnx) dans voix/. Voir docs.")
            return None
        try:
            if self._voix is None:
                self._voix = PiperVoice.load(str(chemin))
            return self._rendre(np, texte)
        except Exception as e:
            print(f"  [Piper] echec ({e}), repli "
                  f"{plateforme.nom_voix_systeme()}.")
            return None


# --------------------------------------------------------------- Kokoro (local)

class KokoroProvider(ProviderTTS):
    nom = "Kokoro"

    def __init__(self):
        self.voix_nom = reglage("kokoro.voix_nom", "ff_siwis")
        self._k = None
        self._chemins = self._resoudre()

    def _resoudre(self):
        """(modele, voix) resolus depuis la racine du projet, comme Piper.

        Chemin de config (relatif ou absolu), sinon auto-detection dans voix/ :
        kokoro-v*.onnx + voices-v*.bin. Renvoie ("", "") si introuvable.
        """
        modele = reglage("kokoro.modele", "")
        voix = reglage("kokoro.voix", "")
        if modele and not Path(modele).is_absolute():
            modele = _RACINE / modele
        if voix and not Path(voix).is_absolute():
            voix = _RACINE / voix
        if modele and voix and Path(modele).exists() and Path(voix).exists():
            return str(modele), str(voix)
        try:
            onnx = sorted((_RACINE / "voix").glob("kokoro-v*.onnx"))
            bin_voices = sorted((_RACINE / "voix").glob("voices-v*.bin"))
            if onnx and bin_voices:
                return str(onnx[0]), str(bin_voices[0])
        except OSError:
            pass
        return "", ""

    def disponible(self):
        return bool(self._chemins[0])

    def synthetiser(self, texte):
        try:
            import numpy as np
            from kokoro_onnx import Kokoro
        except ImportError:
            print("  [Kokoro] librairie absente. Installe : uv add kokoro-onnx")
            return None
        if not self._chemins[0]:
            print("  [Kokoro] modele introuvable (kokoro.modele ou voix/kokoro-v*.onnx). "
                  "Voir docs/local.md.")
            return None
        try:
            if self._k is None:
                self._k = Kokoro(*self._chemins)
            samples, freq = self._k.create(texte, voice=self.voix_nom, speed=1.0, lang="fr-fr")
            audio = (np.asarray(samples) * 32767).astype(np.int16)
            return audio, freq
        except Exception as e:
            print(f"  [Kokoro] echec ({e}), repli "
                  f"{plateforme.nom_voix_systeme()}.")
            return None


# --------------------------------------------------------------- Voxtral (cloud)

class VoxtralProvider(ProviderTTS):
    """La voix de Mistral (voxtral-mini-tts-2603), celle de Le Chat.

    Appel REST direct sur /v1/audio/speech (meme API que le SDK mistralai,
    sans la dependance) : la cle et l'URL sont celles du LLM (mistral.cle /
    mistral.url). voxtral.voix est l'IDENTIFIANT d'une voix du compte Mistral
    (liste par scripts/voix_voxtral.py, ou ID d'une voix clonee dans le
    Mistral Studio). Les noms des presets (fr_female...) ne sont PAS des
    identifiants API : la reponse est un 404 invalid_voice. Sortie 24 kHz.

    AUTO-REPARATION : si la synthese echoue parce que l'identifiant configure
    n'est pas une voix du compte (404 invalid_voice, preset colle par erreur),
    Jarvis liste les voix du compte, en choisit une (meme nom, sinon la
    premiere voix francaise) et l'ENREGISTRE dans config.yaml : la voix se
    repare toute seule, sans toucher au terminal.

    Tout autre echec (reseau, credit epuise, moderation 403) rend None et
    jarvis14 bascule sur la voix de l'OS, comme pour Piper et Kokoro.
    """

    nom = "Voxtral"

    def __init__(self):
        self.voix = str(reglage("voxtral.voix", "") or "").strip()
        self.modele = str(reglage("voxtral.modele", "voxtral-mini-tts-2603")
                          or "voxtral-mini-tts-2603").strip()
        self._deja_repare = False

    def disponible(self):
        return bool(str(reglage("mistral.cle", "") or "").strip() and self.voix)

    @staticmethod
    def _voix_invalide(erreur):
        """Vrai si l'echec vient d'un identifiant de voix inconnu du compte."""
        texte = str(erreur).lower()
        if "invalid_voice" in texte or "voice not found" in texte:
            return True
        return ("http 404" in texte
                and ("voice" in texte or "preset" in texte))

    def _reparer_voix(self):
        """Résout un VRAI identifiant de voix et le sauvegarde dans config.yaml.

        Retourne le nouvel identifiant, ou None si le compte ne liste aucune
        voix (ou si l'API ne repond pas). Un seul essai par instance : on ne
        boucle jamais sur un compte sans voix.
        """
        if self._deja_repare:
            return None
        self._deja_repare = True
        try:
            reponse = lister_voix_voxtral()
        except Exception as e:
            print(f"  [Voxtral] auto-réparation impossible (liste des voix : {e}).")
            return None
        items = (reponse or {}).get("items") or []
        if not items:
            return None
        cible = self.voix.lower()
        choisie = None
        for it in items:
            if not it.get("id"):
                continue
            nom = str(it.get("name") or "").strip().lower()
            if cible and (nom == cible or nom == cible.replace("_", " ")):
                choisie = it
                break
        if choisie is None:
            francaises = [it for it in items
                          if it.get("id") and any(
                              str(l).lower().startswith("fr")
                              for l in (it.get("languages") or [""]))]
            choisie = francaises[0] if francaises else items[0]
        identifiant = str(choisie.get("id")).strip()
        try:
            from core.config import definir
            definir("voxtral.voix", identifiant)
            self.voix = identifiant
            nom = str(choisie.get("name") or "?")
            print(f"  [Voxtral] voix auto-réparée : {nom} "
                  f"(id {identifiant}) enregistré dans config.yaml.")
            return identifiant
        except Exception as e:
            print(f"  [Voxtral] voix résolue ({identifiant}) mais config.yaml "
                  f"non réécrit : {e}")
            return None

    def synthetiser(self, texte):
        if not self.voix:
            identifiant = self._reparer_voix()
            if not identifiant:
                raise RuntimeError(
                    "voxtral.voix est vide dans config.yaml : lance "
                    "'uv run python scripts/voix_voxtral.py' pour lister les "
                    "identifiants de voix de ton compte Mistral et choisis-en un.")

        resultat = self._appeler(texte)
        if resultat is None and self._voix_invalide(self._derniere_erreur or ""):
            print("  [Voxtral] identifiant de voix inconnu du compte — "
                  "auto-réparation...")
            if self._reparer_voix():
                resultat = self._appeler(texte)
        return resultat

    _derniere_erreur = None

    def _appeler(self, texte):
        """POST /audio/speech ; None si indisponible, met _derniere_erreur."""
        self._derniere_erreur = None
        cle = str(reglage("mistral.cle", "") or "").strip()
        if not cle or not self.voix:
            print("  [Voxtral] mistral.cle ou voxtral.voix manquant. "
                  "Voir docs/mistral.md.")
            return None
        try:
            import base64
            import io
            import json
            import urllib.error
            import urllib.request
            import wave

            import numpy as np
            url = (str(reglage("mistral.url", "https://api.mistral.ai/v1"))
                   or "https://api.mistral.ai/v1").rstrip("/")
            corps = json.dumps({
                "model": self.modele,
                "input": texte,
                "voice_id": self.voix,
                "response_format": "wav",
            }).encode("utf-8")
            requete = urllib.request.Request(
                f"{url}/audio/speech", data=corps, method="POST",
                headers={"Authorization": f"Bearer {cle}",
                         "Content-Type": "application/json"})
            delai = float(reglage("mistral.timeout", 90) or 90)
            try:
                with urllib.request.urlopen(requete, timeout=delai) as reponse:
                    donnees = json.loads(reponse.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                detail = e.read().decode("utf-8", "replace")[:300]
                self._derniere_erreur = f"HTTP {e.code} sur {e.url} : {detail}"
                raise RuntimeError(self._derniere_erreur)
            with wave.open(io.BytesIO(base64.b64decode(donnees["audio_data"]))) as w:
                frequence = w.getframerate()
                canaux = w.getnchannels()
                largeur = w.getsampwidth()
                trames = w.readframes(w.getnframes())
            if largeur == 2:
                audio = np.frombuffer(trames, dtype=np.int16)
            elif largeur == 4:
                audio = (np.frombuffer(trames, dtype="<i4") >> 16).astype(np.int16)
            else:
                audio = (np.frombuffer(trames, dtype="<f4")
                         * 32767).astype(np.int16)
            if canaux > 1:
                audio = audio[::canaux]
            if not len(audio):
                return None
            return audio, frequence
        except Exception as e:
            if self._derniere_erreur is None:
                self._derniere_erreur = str(e)
            print(f"  [Voxtral] echec ({e}), repli "
                  f"{plateforme.nom_voix_systeme()}.")
            return None


# --------------------------------------------------------------- Gemini (cloud)
class GeminiTTSProvider(ProviderTTS):
    """Gemini TTS (gemini-2.5-flash-tts / -pro-tts), 30 voix plurilingues.

    Utilise la meme cle que le LLM Gemini (gemini.cle, gratuite sur AI
    Studio). gemini.voix_tts choisit la voix (defaut : Kore, feminine et
    naturelle). Sortie PCM 24 kHz mono ; tout echec rend None et jarvis14
    bascule sur la voix de l'OS, comme pour les autres providers cloud.
    Requete REST directe (pas de dependance) : generateContent avec
    responseModalities AUDIO.
    """
    nom = "Gemini"

    def __init__(self):
        self.voix = str(reglage("gemini.voix_tts", "Kore") or "Kore").strip() or "Kore"
        self.modele = str(reglage("gemini.modele_tts", "gemini-2.5-flash-tts")
                          or "gemini-2.5-flash-tts").strip()

    def disponible(self):
        return bool(str(reglage("gemini.cle", "") or "").strip())

    def synthetiser(self, texte):
        cle = str(reglage("gemini.cle", "") or "").strip()
        if not cle:
            return None
        try:
            import base64
            import json
            import urllib.error
            import urllib.request
            import numpy as np
            url = ("https://generativelanguage.googleapis.com/v1beta/models/"
                   + self.modele + ":generateContent?key=" + cle)
            corps = json.dumps({
                "contents": [{
                    "parts": [{
                        "text": f"Dis en francais, naturellement : {texte}"
                    }]
                }],
                "generationConfig": {
                    "responseModalities": ["AUDIO"],
                    "speechConfig": {
                        "voiceConfig": {
                            "prebuiltVoiceConfig": {"voiceName": self.voix}
                        }
                    },
                },
            }).encode("utf-8")
            requete = urllib.request.Request(url, data=corps, method="POST",
                                             headers={"Content-Type":
                                                      "application/json"})
            delai = float(reglage("gemini.timeout", 90) or 90)
            try:
                with urllib.request.urlopen(requete, timeout=delai) as reponse:
                    donnees = json.loads(reponse.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                detail = e.read().decode("utf-8", "replace")[:300]
                raise RuntimeError(f"HTTP {e.code} sur {e.url} : {detail}")
            parts = ((donnees.get("candidates") or [{}])[0]
                     .get("content", {}).get("parts", []))
            donnees_audio = None
            mime = ""
            for part in parts:
                inline = part.get("inlineData") or {}
                if inline.get("mimeType", "").startswith("audio/"):
                    donnees_audio = inline.get("data")
                    mime = inline.get("mimeType") or ""
                    break
            if not donnees_audio:
                return None
            # le TTS Gemini renvoie du PCM 16 bits 24 kHz mono (audio/L16)
            audio = np.frombuffer(base64.b64decode(donnees_audio), dtype=np.int16)
            frequence = 24000
            if "wav" in mime:
                import io
                import wave
                with wave.open(io.BytesIO(base64.b64decode(donnees_audio))) as w:
                    frequence = w.getframerate()
                    canaux = w.getnchannels()
                    trames = w.readframes(w.getnframes())
                audio = np.frombuffer(trames, dtype=np.int16)
                if canaux > 1:
                    audio = audio[::canaux]
            if not len(audio):
                return None
            return audio, frequence
        except Exception as e:
            print(f"  [Gemini] echec ({e}), repli "
                  f"{plateforme.nom_voix_systeme()}.")
            return None



# --------------------------------------------------------------- diagnostic Voxtral

def lister_voix_voxtral():
    """Liste TOUTES les voix du compte (presets + clonees, toutes pages).
    Renvoie {"items": [...], "total": n} ou None si la cle est absacente.
    Usage : scripts/voix_voxtral.py."""
    cle = str(reglage("mistral.cle", "") or "").strip()
    if not cle:
        return None
    import json
    import urllib.error
    import urllib.request
    url = (str(reglage("mistral.url", "https://api.mistral.ai/v1"))
           or "https://api.mistral.ai/v1").rstrip("/")
    items, page, total_pages = [], 1, 1
    while page <= total_pages:
        requete = urllib.request.Request(
            f"{url}/audio/voices?type=all&page={page}&page_size=100",
            method="GET",
            headers={"Authorization": f"Bearer {cle}",
                     "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(requete, timeout=30) as reponse:
                donnees = json.loads(reponse.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:300]
            raise RuntimeError(f"HTTP {e.code} sur {e.url} : {detail}")
        items.extend(donnees.get("items", []))
        total_pages = int(donnees.get("total_pages", 1) or 1)
        page += 1
        if page > 50:
            break
    return {"items": items, "total": len(items)}


# --------------------------------------------------------------- fabrique

_TTS = None


def _provider_local():
    """Piper ou Kokoro, selon voix_locale."""
    moteur = (reglage("voix_locale", "piper") or "piper").lower()
    return KokoroProvider() if moteur == "kokoro" else PiperProvider()


def tts():
    """Provider TTS courant.

    ``tts.moteur`` peut valoir auto/piper/kokoro/voxtral/gemini/os. Voxtral est la
    voix cloud de Mistral (comme Le Chat) : uniquement en mode hybride ou
    qualite, jamais impose en mode local. En auto, on prend la voix locale
    installee, sinon le repli de l'OS.
    """
    global _TTS
    if _TTS is None:
        from core.routage import mode_actuel
        m = mode_actuel()
        moteur = (reglage("tts.moteur", "auto") or "auto").lower()
        if moteur == "auto" or moteur == "elevenlabs":
            # Valeur "elevenlabs" : ancienne config. On la traite comme auto.
            moteur = (reglage("voix_locale", "piper") or "piper").lower()
            local = _provider_local()
            if local.disponible():
                _TTS = local
            else:
                _TTS = OSProvider()
        elif moteur == "kokoro":
            _TTS = KokoroProvider()
        elif moteur == "piper":
            _TTS = PiperProvider()
        elif moteur == "voxtral":
            if m == "local":
                local = _provider_local()
                _TTS = local if local.disponible() else OSProvider()
            else:
                _TTS = VoxtralProvider()
        elif moteur == "gemini":
            if m == "local":
                local = _provider_local()
                _TTS = local if local.disponible() else OSProvider()
            else:
                _TTS = GeminiTTSProvider()
        else:
            _TTS = OSProvider()
        LOG.info("provider TTS : %s (mode %s)", _TTS.nom, m)
    return _TTS


def reinitialiser():
    """Force la reconstruction du provider TTS au prochain tts() (switch de mode)."""
    global _TTS
    _TTS = None
