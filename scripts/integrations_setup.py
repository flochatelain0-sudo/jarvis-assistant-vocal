#!/usr/bin/env python3
"""Installation rapide des integrations OAuth — une commande pour tout.

Usage :
    uv run python scripts/integrations_setup.py                  # interactif
    uv run python scripts/integrations_setup.py github            # un provider

Pour chaque provider : affiche la redirect URI a copier dans la console
du provider, demande client_id et client_secret, les enregistre dans
config.yaml, puis propose de passer au suivant. Aucun secret n'est logge.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import definir, reglage  # noqa: E402
from core import integrations_oauth as io  # noqa: E402

PORT = io._base_url_locale().rsplit(":", 1)[-1]

SETUP = {
    "gmail": "https://console.cloud.google.com/apis/credentials",
    "gcal": "https://console.cloud.google.com/apis/credentials",
    "gdrive": "https://console.cloud.google.com/apis/credentials",
    "github": "https://github.com/settings/developers",
    "linkedin": "https://www.linkedin.com/developers/apps",
    "slack": "https://api.slack.com/apps",
    "notion": "https://www.notion.so/my-integrations",
    "linear": "https://linear.app/settings/api",
    "outlook": "https://portal.azure.com",
    "hubspot": "https://developers.hubspot.com",
}


def demander(invite: str) -> str:
    try:
        return input(invite).strip()
    except (EOFError, KeyboardInterrupt):
        return ""


def installer(provider: str) -> bool:
    p = io.provider(provider)
    if not p:
        print(f"  Provider inconnu : {provider}")
        return False
    cid = (reglage(p["clientIdKey"], "") or "").strip()
    if cid:
        print(f"  {p['name']} : DEJA configure (client_id ...{cid[-6:]})")
        if demander("  Remplacer ? [o/N] ").lower() != "o":
            return True
    print(f"\n=== {p['name']} ===")
    if provider in SETUP:
        print(f"  1. Ouvre : {SETUP[provider]}")
    redirect = f"http://127.0.0.1:{PORT}/api/integrations/{provider}/callback"
    print(f"  2. Redirect URI a copier la-bas :\n     {redirect}")
    identifiant = demander("  3. Client ID : ")
    if not identifiant:
        print("  Abandon (client ID vide).")
        return False
    secret = demander("  4. Client Secret : ")
    if not secret:
        print("  Abandon (secret vide).")
        return False
    definir(p["clientIdKey"], identifiant)
    definir(p["clientSecretKey"], secret)
    print(f"  OK — {p['name']} enregistre dans config.yaml.")
    return True


def main() -> None:
    cles = sorted(SETUP)
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if args:
        for provider in args:
            installer(provider)
        return
    print(f"Installation rapide des integrations (serveur local :{PORT}).")
    print(f"Providers : {', '.join(cles)}")
    print("Ctrl+C pour sortir a tout moment.\n")
    try:
        while True:
            provider = demander("Provider (ou Entree pour finir) : ").lower()
            if not provider:
                break
            installer(provider)
    except KeyboardInterrupt:
        pass
    print("\nRecapitulatif :")
    for provider in cles:
        p = io.provider(provider)
        if p and (reglage(p["clientIdKey"], "") or "").strip():
            print(f"  {p['name']:<18} CONFIGURE")
    print("\nRelance Jarvis puis : http://127.0.0.1:" + PORT +
          "/operator -> page INTEGRATIONS.")


if __name__ == "__main__":
    main()
