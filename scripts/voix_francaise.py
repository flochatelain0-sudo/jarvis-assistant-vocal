#!/usr/bin/env python3
"""Installe une voix francaise Piper — accent FR natif, 100% local.

Usage :
    uv run python scripts/voix_francaise.py            # fr_FR-siwis-medium
    uv run python scripts/voix_francaise.py fr_FR-tom-medium

Telecharge le couple .onnx + .json depuis Hugging Face (rhasspy/piper-voices),
le place dans voix/, bascule tts.moteur sur piper, et teste une phrase.
Plus d'accent anglais : la synthese est francaise, hors ligne, gratuite.
"""

import sys
import urllib.request
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
DOSSIER = RACINE / "voix"
BASE = ("https://huggingface.co/rhasspy/piper-voices/resolve/main/fr/fr_FR/"
        "{nom}/{nom}.onnx")

VOIX_DISPONIBLES = ("fr_FR-siwis-medium", "fr_FR-tom-medium",
                   "fr_FR-upmc-medium", "fr_FR-gilles-low")


def telecharger(url: str, cible: Path) -> bool:
    try:
        print(f"  telechargement : {url}")
        with urllib.request.urlopen(url, timeout=60) as rep:
            cible.write_bytes(rep.read())
        return True
    except Exception as e:
        print(f"  echec : {e}")
        return False


def main() -> None:
    nom = sys.argv[1] if len(sys.argv) > 1 else "fr_FR-siwis-medium"
    if nom not in VOIX_DISPONIBLES:
        print(f"Voix inconnue : {nom}. Disponibles : {VOIX_DISPONIBLES}")
        sys.exit(1)
    DOSSIER.mkdir(parents=True, exist_ok=True)
    onnx, json_conf = DOSSIER / f"{nom}.onnx", DOSSIER / f"{nom}.onnx.json"
    if onnx.exists() and json_conf.exists():
        print(f"{nom} est deja installee.")
    else:
        base = BASE.format(nom=nom)
        if not telecharger(base, onnx):
            sys.exit(1)
        if not telecharger(base + ".json", json_conf):
            sys.exit(1)
    from core.config import definir
    definir("tts.moteur", "piper")
    print(f"tts.moteur = piper, voix {nom} prete dans voix/.")
    try:
        from core import tts
        tts.reinitialiser()
        audio, freq = tts.tts().synthetiser(
            "Voix francaise installee. Jarvis parle desormais sans accent.")
        if audio is not None:
            print(f"OK — {len(audio)} echantillons a {freq} Hz. Test reussi.")
        else:
            print("Le test a echoue — relance et redemande-moi un test.")
    except Exception as e:
        print(f"Test impossible ({e}) — Jarvis retombera sur la voix OS.")


if __name__ == "__main__":
    main()
