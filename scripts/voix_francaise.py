"""Installe une voix Piper francaise native (sans accent anglais).

    python scripts/voix_francaise.py

Telecharge fr_FR-siwis-medium (voix feminine francaise native) depuis
Hugging Face, place le .onnx et son .json dans voix/, puis propose la
ligne a ajouter dans config.yaml (piper.modele). A la fin, teste la voix :
la phrase de bienvenue est synthetisee et jouee.

Si une voix Piper existe deja dans voix/, le script le signale et ne
telecharge rien (sauf --forcer).
"""

import argparse
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
DOSSIER_VOIX = RACINE / "voix"

BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/main/fr/fr_FR/siwis/medium/"
FICHIERS = ("fr_FR-siwis-medium.onnx", "fr_FR-siwis-medium.onnx.json")

PHRASE_TEST = ("Bonjour Florian, c'est Jarvis. Voici ma nouvelle voix "
               "francaise, sans accent anglais.")


def telecharger(nom: str) -> None:
    cible = DOSSIER_VOIX / nom
    if cible.exists():
        print(f"  [ok] {nom} deja present.")
        return
    url = BASE + nom
    print(f"  [..] telechargement de {nom} ...")
    with urllib.request.urlopen(url) as reponse:
        cible.write_bytes(reponse.read())
    taille = cible.stat().st_size // (1024 * 1024)
    print(f"  [ok] {nom} ({taille} Mo).")


def voix_existantes() -> list:
    return sorted(DOSSIER_VOIX.glob("*.onnx")) if DOSSIER_VOIX.exists() else []


def tester() -> bool:
    """Synthetise et joue la phrase de test ; True si la voix est audible."""
    try:
        sys.path.insert(0, str(RACINE))
        from core.tts import PiperProvider
        provider = PiperProvider()
        if not provider.disponible():
            return False
        rendu = provider.synthetiser(PHRASE_TEST)
        return bool(rendu)
    except Exception as e:
        print(f"  [!] test impossible : {e}")
        return False


def main() -> int:
    parseur = argparse.ArgumentParser(
        description="Installe la voix Piper francaise (fr_FR-siwis-medium).")
    parseur.add_argument("--forcer", action="store_true",
                         help="telecharge meme si une voix existe deja.")
    parseur.add_argument("--silence", action="store_true",
                         help="pas de test audio a la fin.")
    args = parseur.parse_args()

    print("=" * 52)
    print("  Voix francaise Piper (fr_FR-siwis-medium)")
    print("=" * 52)

    existantes = voix_existantes()
    siwis_deja_la = (DOSSIER_VOIX / FICHIERS[0]).exists()
    if not args.forcer and existantes and not siwis_deja_la:
        for v in existantes:
            print(f"  [ok] voix deja installee : {v.name}")
        print("\nUne voix Piper est deja la. Relance avec --forcer "
              "pour installer siwis par-dessus.")
        return 0
    if siwis_deja_la:
        print("  [ok] voix fr_FR-siwis-medium deja presente.")
    DOSSIER_VOIX.mkdir(parents=True, exist_ok=True)
    ok = True
    for nom in FICHIERS:
        try:
            telecharger(nom)
        except Exception as e:
            print(f"  [!] echec du telechargement de {nom} : {e}")
            print("      Verifie ta connexion, ou telecharge manuellement "
                  f"depuis\n      {BASE}")
            ok = False
    if not ok:
        return 1

    # Configuration AUTOMATIQUE : piper.modele ecrit dans config.yaml.
    # Le chemin est RELATIF A LA RACINE (core/tts.py resout piper.modele
    # depuis la racine du projet) : il faut donc voix/ devant le nom.
    try:
        sys.path.insert(0, str(RACINE))
        from core import config
        config._CONFIG = None          # forcer la relecture du fichier
        config.definir("piper.modele", "voix/fr_FR-siwis-medium.onnx")
        print("\n  [ok] config.yaml mis a jour : piper.modele = "
              "voix/fr_FR-siwis-medium.onnx")
    except Exception as e:
        print(f"\n  [!] configuration automatique impossible ({e}).")
        print("      Ajoute dans config.yaml :")
        print("        piper:")
        print("          modele: voix/fr_FR-siwis-medium.onnx")

    if not args.silence:
        print("\nTest de la voix ...")
        if tester():
            print("  [ok] Jarvis parle maintenant en francais natif.")
        else:
            print("  [!] le test audio a echoue ; verifie que piper-tts "
                  "est installe (uv add piper-tts).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
