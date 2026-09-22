#!/usr/bin/env python
"""Diagnostic Voxtral : teste la voix configuree et liste les voix disponibles.

Usage : uv run python scripts/voix_voxtral.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import reglage
from core import tts


def principal():
    cle = str(reglage("mistral.cle", "") or "").strip()
    if not cle:
        print("Aucune cle mistral.cle dans config.yaml.")
        raise SystemExit(1)
    url = str(reglage("mistral.url", "https://api.mistral.ai/v1") or
                "https://api.mistral.ai/v1")
    print(f"URL configuree : {url}")
    if url.rstrip("/") != "https://api.mistral.ai/v1":
        print("  ! ATTENTION : mistral.url ne pointe pas sur l'API officielle")
        print("    Mistral. Corrige config.yaml ->")
        print('    mistral:\n      url: "https://api.mistral.ai/v1"')

    voix = str(reglage("voxtral.voix", "fr_female") or "").strip()
    print(f"\nVoix configuree : {voix}")

    print("\n1. Voix disponibles sur ton compte (presets) :")
    try:
        reponse = tts.lister_voix_voxtral()
        items = reponse.get("items", []) if isinstance(reponse, dict) else (reponse or [])
        if not items:
            print("  (aucune voix preset listee : essaie le Studio Mistral)")
        for v in items[:40]:
            if isinstance(v, dict):
                nom = v.get("name") or "?"
                vid = v.get("id") or "?"
                typ = v.get("type") or "?"
                langues = ",".join(v.get("languages") or [])
                print(f"  - {nom} (id: {vid}, type: {typ}, langues: {langues})")
            else:
                print("  -", v)
    except Exception as e:
        print(f"  Erreur en listant les voix : {e}")

    print("\n2. Test de synthese avec la voix configuree :")
    provider = tts.VoxtralProvider()
    try:
        resultat = provider.synthetiser("Bonjour Florian, je suis Jarvis.")
        if resultat is None:
            print("  Echec silencieux (voir message d'erreur plus haut).")
        else:
            audio, freq = resultat
            print(f"  OK : {len(audio)} echantillons a {freq} Hz.")
            sortie = Path(__file__).resolve().parent.parent / "voix"
            sortie = sortie / "test_voxtral.wav"
            import wave
            with wave.open(str(sortie), "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(freq)
                w.writeframes(audio.tobytes())
            print(f"  Ecrit : voix/test_voxtral.wav (ouvre-le pour ecouter)")
    except Exception as e:
        print(f"  Erreur : {e}")


if __name__ == "__main__":
    principal()
