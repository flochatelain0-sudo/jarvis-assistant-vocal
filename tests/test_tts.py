"""Tests du TTS local (Piper), indépendants du système.

Piper est le moteur de voix recommandé hors ligne : s'il échoue, Jarvis retombe
sur la voix de l'OS sans le dire fort. Ces tests vérifient qu'on appelle bien
l'API réellement présente dans la version installée.
"""
import sys
from pathlib import Path

import pytest

from core import tts

RACINE = Path(__file__).resolve().parent.parent


class _Bloc:
    """Un AudioChunk de piper-tts >= 1.3 (un par phrase)."""

    def __init__(self, octets, frequence=22050):
        self.audio_int16_bytes = octets
        self.sample_rate = frequence


class _Config:
    sample_rate = 16000        # volontairement different, pour voir qui gagne


class _VoixModerne:
    """piper-tts >= 1.3 : synthesize() rend des AudioChunk."""

    config = _Config()

    def synthesize(self, texte, *a, **kw):
        return [_Bloc(b"\x01\x02" * 100), _Bloc(b"\x03\x04" * 50)]


class _VoixAncienne:
    """piper-tts < 1.3 : synthesize_stream_raw() rend des octets."""

    config = _Config()

    def synthesize_stream_raw(self, texte):
        return [b"\x01\x02" * 100]


def _numpy():
    return pytest.importorskip("numpy")


def test_api_moderne_concatene_les_phrases():
    """Chaque phrase est un bloc : il faut TOUS les joindre, pas seulement le 1er."""
    np = _numpy()
    p = tts.PiperProvider()
    p._voix = _VoixModerne()
    audio, freq = p._rendre(np, "Deux phrases. Vraiment deux.")
    assert audio.dtype == np.int16
    assert len(audio) == 150          # (200 + 100) octets / 2
    # La fréquence vient du bloc audio, pas de la config du modèle.
    assert freq == 22050


def test_api_ancienne_toujours_geree():
    """Une installation piper < 1.3 ne doit pas être cassée par le correctif."""
    np = _numpy()
    p = tts.PiperProvider()
    p._voix = _VoixAncienne()
    audio, freq = p._rendre(np, "Bonjour")
    assert len(audio) == 100 and freq == 16000


def test_audio_vide_rend_none():
    """Rien à jouer -> None, pour que jarvis14 bascule sur la voix de l'OS."""
    np = _numpy()

    class _Muette(_VoixModerne):
        def synthesize(self, texte, *a, **kw):
            return []

    p = tts.PiperProvider()
    p._voix = _Muette()
    assert p._rendre(np, "") is None


def test_methode_appelee_existe_vraiment():
    """Le garde-fou qui aurait attrapé le bug : piper 1.6 n'a plus
    synthesize_stream_raw, et l'échec était silencieux (repli sur la voix OS)."""
    piper = pytest.importorskip("piper")
    voix = piper.PiperVoice
    assert hasattr(voix, "synthesize") or hasattr(voix, "synthesize_stream_raw"), (
        "aucune des deux API de synthese n'est disponible dans piper-tts")


@pytest.mark.skipif(not list((RACINE / "voix").glob("*.onnx")),
                    reason="aucune voix Piper (.onnx) installee dans voix/")
def test_synthese_reelle_produit_de_la_parole():
    """Bout en bout avec le vrai modele, quand il est present."""
    np = _numpy()
    pytest.importorskip("piper")
    p = tts.PiperProvider()
    assert p.disponible()
    res = p.synthetiser("Bonjour, je suis Jarvis.")
    assert res is not None, "Piper n'a rien rendu"
    audio, freq = res
    assert audio.dtype == np.int16
    assert len(audio) > freq * 0.3, "audio trop court pour etre de la parole"
    assert int(abs(audio).max()) > 1000, "audio silencieux"


# ------------------------------------------------- choix du provider (fabrique)

@pytest.fixture(autouse=True)
def _tts_neuf():
    """Chaque test repart d'un provider non construit (le module le met en cache)."""
    tts.reinitialiser()
    yield
    tts.reinitialiser()


def _fabrique(monkeypatch, mode, piper_dispo, moteur="auto"):
    monkeypatch.setattr("core.routage.mode_actuel", lambda: mode)
    monkeypatch.setattr(tts, "reglage",
                        lambda chemin, defaut=None:
                        moteur if chemin == "tts.moteur" else defaut)
    monkeypatch.setattr(tts.PiperProvider, "disponible", lambda self: piper_dispo)
    return tts.tts()


def test_mode_local_utilise_piper(monkeypatch):
    assert _fabrique(monkeypatch, "local", True).nom == "Piper"


def test_hybride_auto_utilise_piper(monkeypatch):
    """Plus de TTS cloud : auto = la voix locale installee."""
    assert _fabrique(monkeypatch, "hybride", True).nom == "Piper"


def test_hybride_sans_piper_replie_sur_l_os(monkeypatch):
    """Rien d'installe : OSProvider, qui rendra None -> voix de l'OS."""
    assert _fabrique(monkeypatch, "hybride", False).nom == "OS"


def test_ancienne_config_elevenlabs_traitee_comme_auto(monkeypatch):
    """Une config heritee avec tts.moteur=elevenlabs ne doit pas casser :"""
    assert _fabrique(monkeypatch, "hybride", True, moteur="elevenlabs").nom == "Piper"


# ------------------------------------------------- reglages de voix (Piper)

def test_sans_reglage_on_garde_les_defauts_du_modele(monkeypatch):
    """Aucun SynthesisConfig si rien n'est configure : le .onnx decide."""
    monkeypatch.setattr(tts, "reglage", lambda chemin, defaut=None: defaut)
    assert tts.PiperProvider()._synthese() is None


def test_reglages_transmis_a_piper(monkeypatch):
    pytest.importorskip("piper")
    vals = {"piper.vitesse": 1.05, "piper.expressivite": 0.8,
            "piper.variation": 1.0, "piper.volume": 1.0}
    monkeypatch.setattr(tts, "reglage",
                        lambda chemin, defaut=None: vals.get(chemin, defaut))
    cfg = tts.PiperProvider()._synthese()
    assert cfg.length_scale == 1.05
    assert cfg.noise_scale == 0.8
    assert cfg.noise_w_scale == 1.0


def test_reglage_partiel_ne_force_pas_le_reste(monkeypatch):
    """Ne regler que la vitesse ne doit pas ecraser l'intonation du modele."""
    pytest.importorskip("piper")
    monkeypatch.setattr(tts, "reglage",
                        lambda chemin, defaut=None:
                        1.2 if chemin == "piper.vitesse" else defaut)
    cfg = tts.PiperProvider()._synthese()
    assert cfg.length_scale == 1.2
    assert cfg.noise_scale is None and cfg.noise_w_scale is None

# ---------------------------------------------------------------- Kokoro

def test_kokoro_auto_detecte_les_fichiers_dans_voix(tmp_path, monkeypatch):
    monkeypatch.setattr(tts, "_RACINE", tmp_path)
    (tmp_path / "voix").mkdir()
    (tmp_path / "voix" / "kokoro-v1.0.onnx").write_bytes(b"modele")
    (tmp_path / "voix" / "voices-v1.0.bin").write_bytes(b"voix")
    provider = tts.KokoroProvider()
    assert provider.disponible() is True
    assert provider._chemins[0].endswith("kokoro-v1.0.onnx")
    assert provider._chemins[1].endswith("voices-v1.0.bin")


def test_kokoro_chemin_de_config_resolu_depuis_la_racine(tmp_path, monkeypatch):
    monkeypatch.setattr(tts, "_RACINE", tmp_path)
    (tmp_path / "voix").mkdir()
    (tmp_path / "voix" / "kokoro-v1.0.onnx").write_bytes(b"modele")
    (tmp_path / "voix" / "voices-v1.0.bin").write_bytes(b"voix")
    monkeypatch.setattr("core.config.reglage",
                        lambda cle, defaut=None: {
                            "kokoro.modele": "voix/kokoro-v1.0.onnx",
                            "kokoro.voix": "voix/voices-v1.0.bin",
                            "kokoro.voix_nom": "ff_siwis",
                        }.get(cle, defaut))
    provider = tts.KokoroProvider()
    assert provider.disponible() is True
    assert provider._chemins[0] == str(tmp_path / "voix" / "kokoro-v1.0.onnx")


def test_kokoro_introuvable_est_indisponible(tmp_path, monkeypatch):
    monkeypatch.setattr(tts, "_RACINE", tmp_path)
    monkeypatch.setattr("core.config.reglage",
                        lambda cle, defaut=None: {
                            "kokoro.modele": "", "kokoro.voix": "",
                        }.get(cle, defaut))
    provider = tts.KokoroProvider()
    assert provider.disponible() is False

# ---------------------------------------------------------------- Voxtral (cloud)

import base64
import io
import json as _json
import wave as _wave


def _wav_int16(echantillons, frequence=24000, canaux=1):
    """Un vrai WAV mono int16 en memoire, comme la reponse de l'API Mistral."""
    tampon = io.BytesIO()
    with _wave.open(tampon, "wb") as w:
        w.setnchannels(canaux)
        w.setsampwidth(2)
        w.setframerate(frequence)
        w.writeframes(echantillons)
    return tampon.getvalue()


class _ReponseHTTP:
    def __init__(self, contenu):
        self._contenu = contenu

    def read(self):
        return self._contenu

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_voxtral_choisi_par_la_fabrique(monkeypatch):
    reglages = {"tts.moteur": "voxtral", "mistral.cle": "cle-test",
                "voxtral.voix": "fr_female"}
    monkeypatch.setattr("core.routage.mode_actuel", lambda: "hybride")
    monkeypatch.setattr(tts, "reglage",
                        lambda chemin, defaut=None: reglages.get(chemin, defaut))
    assert tts.tts().nom == "Voxtral"


def test_mode_local_ignore_voxtral_et_garde_piper(monkeypatch):
    """La promesse du mode local : rien ne part sur le cloud, meme mal configure."""
    assert _fabrique(monkeypatch, "local", True, moteur="voxtral").nom == "Piper"


def test_voxtral_indisponible_sans_cle_mistral(monkeypatch):
    monkeypatch.setattr(tts, "reglage", lambda chemin, defaut=None: defaut)
    assert tts.VoxtralProvider().disponible() is False


def test_voxtral_disponible_avec_cle_et_voix(monkeypatch):
    reglages = {"mistral.cle": "cle-test", "voxtral.voix": "fr_female"}
    monkeypatch.setattr(tts, "reglage",
                        lambda chemin, defaut=None: reglages.get(chemin, defaut))
    assert tts.VoxtralProvider().disponible() is True


def test_voxtral_decode_le_wav_en_int16_24khz(monkeypatch):
    np = _numpy()
    trames = bytes(range(0, 256)) * 20
    audio_b64 = base64.b64encode(_wav_int16(trames, 24000)).decode()
    reglages = {"mistral.cle": "cle-test", "voxtral.voix": "fr_female"}

    appels = []

    def _fausse_urlopen(requete, timeout=None):
        appels.append(requete)
        return _ReponseHTTP(_json.dumps({"audio_data": audio_b64}).encode())

    monkeypatch.setattr(tts, "reglage",
                        lambda chemin, defaut=None: reglages.get(chemin, defaut))
    monkeypatch.setattr("urllib.request.urlopen", _fausse_urlopen)
    provider = tts.VoxtralProvider()
    resultat = provider.synthetiser("Bonjour, je suis Jarvis.")
    assert resultat is not None
    audio, freq = resultat
    assert audio.dtype == np.int16 and freq == 24000
    assert len(audio) == len(trames) // 2
    requete = appels[0]
    assert requete.full_url == "https://api.mistral.ai/v1/audio/speech"
    corps = _json.loads(requete.data.decode())
    assert corps == {"model": "voxtral-mini-tts-2603",
                     "input": "Bonjour, je suis Jarvis.",
                     "voice_id": "fr_female", "response_format": "wav"}
    assert requete.headers["Authorization"] == "Bearer cle-test"


def test_voxtral_erreur_reseau_rend_none(monkeypatch):
    reglages = {"mistral.cle": "cle-test", "voxtral.voix": "fr_female"}

    def _echec(requete, timeout=None):
        raise OSError("plus de reseau")

    monkeypatch.setattr(tts, "reglage",
                        lambda chemin, defaut=None: reglages.get(chemin, defaut))
    monkeypatch.setattr("urllib.request.urlopen", _echec)
    assert tts.VoxtralProvider().synthetiser("Bonjour") is None


def test_voxtral_sans_voix_est_indisponible_et_le_dit(monkeypatch):
    reglages = {"mistral.cle": "cle-test", "tts.moteur": "voxtral"}
    tts.reinitialiser()
    monkeypatch.setattr(tts, "reglage", lambda c, d=None: reglages.get(c, d))
    provider = tts.VoxtralProvider()
    assert provider.voix == ""
    assert provider.disponible() is False
    with pytest.raises(RuntimeError, match="voix_voxtral"):
        provider.synthetiser("Bonjour")


# ---------------------------------------------------------------- Gemini TTS
def test_gemini_choisi_par_la_fabrique(monkeypatch):
    reglages = {"tts.moteur": "gemini", "gemini.cle": "cle-test"}
    monkeypatch.setattr("core.routage.mode_actuel", lambda: "hybride")
    monkeypatch.setattr(tts, "reglage",
                        lambda chemin, defaut=None: reglages.get(chemin, defaut))
    assert tts.tts().nom == "Gemini"


def test_mode_local_ignore_gemini_et_garde_piper(monkeypatch):
    assert _fabrique(monkeypatch, "local", True, moteur="gemini").nom == "Piper"


def test_gemini_indisponible_sans_cle(monkeypatch):
    monkeypatch.setattr(tts, "reglage", lambda chemin, defaut=None: defaut)
    assert tts.GeminiTTSProvider().disponible() is False


def test_gemini_decode_le_pcm_en_int16_24khz(monkeypatch):
    np = _numpy()
    trames = bytes(range(0, 256)) * 20
    audio_b64 = base64.b64encode(trames).decode()
    reglages = {"gemini.cle": "cle-test", "gemini.voix_tts": "Kore"}
    appels = []

    def _fausse_urlopen(requete, timeout=None):
        appels.append(requete)
        corps = {"candidates": [{"content": {"parts": [{
            "inlineData": {"mimeType": "audio/L16;rate=24000",
                           "data": audio_b64}}]}}]}
        return _ReponseHTTP(_json.dumps(corps).encode())

    monkeypatch.setattr(tts, "reglage",
                        lambda chemin, defaut=None: reglages.get(chemin, defaut))
    monkeypatch.setattr("urllib.request.urlopen", _fausse_urlopen)
    provider = tts.GeminiTTSProvider()
    assert provider.voix == "Kore"
    resultat = provider.synthetiser("Bonjour, je suis Jarvis.")
    assert resultat is not None
    audio, freq = resultat
    assert audio.dtype == np.int16 and freq == 24000
    assert len(audio) == len(trames) // 2
    requete = appels[0]
    assert "gemini-2.5-flash-tts:generateContent" in requete.full_url
    corps = _json.loads(requete.data.decode())
    assert corps["generationConfig"]["speechConfig"]["voiceConfig"][
        "prebuiltVoiceConfig"]["voiceName"] == "Kore"
