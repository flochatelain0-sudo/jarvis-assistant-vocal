"""Execution de commandes shell par Jarvis : N3, bornee et journalisee.

Le shell est l'outil le plus dangereux de la pile OS : il obtient donc le
traitement le plus strict de tout le projet.

DOCTRINE (alignee sur astra_pc.py) :
- N3 TOUJOURS : aucune commande ne s'execute sans feu vert explicite de
  Florian, quel que soit le mode MANUAL/AUTO.
- Rien de destructif : rm -rf racine, format, registre Windows, kills
  systeme, sudo, modifications de securite — refuses AVANT l'execution,
  avec une raison claire (meme constat que astra_pc._RISQUES).
- Jamais de secret : aucune commande ne doit exposer ou lire un mot de
  passe, une cle API, un token ou le config.yaml.
- Borne : timeout (defaut 60 s), sortie cappee a 4000 caracteres,
  repertoire de travail = home.
- Journalise : chaque execution part dans le journal operateur
  (operator.journaliser), commande + duree + code de retour.
- Pas de shell interactif, pas de tunnel, pas d'ecoute reseau entrante.
"""

import subprocess
import time
from pathlib import Path

from core.config import reglage
from core.registre import outil

# Commandes/systemes TOUJOURS refuses, meme avec confirmation.
_INTERDITS = (
    "rm -rf /", "rm -rf /*", "rm -rf ~", "rm -rf $home",
    "format ", "mkfs", "dd if=", ":(){",
    "reg add", "reg delete", "regedit", "regedits",
    "shutdown", "reboot", "halt", "poweroff",
    "sudo rm", "chmod 777 /", "chown -r /",
    "taskkill /f /im explorer",
    "netsh advfirewall", "set-executionpolicy",
    "curl http", "curl -x", "ssh -r", "ssh -l", "ssh -d",
    "ngrok", "cloudflared tunnel", "kubectl delete",
    "passwd", "shadow", "authorized_keys",
)

# Mots interdits partout dans la commande (secrets, exfiltration).
_MOTS_INTERDITS = (
    "config.yaml", ".env", "credentials.json", "integrations_oauth.json",
    "client_secret", "api_key", "apikey", "password=", "passwd",
    "--priv-key", "--private-key", "id_rsa",
    "authorization:", "bearer ", "x-api-key",
)

_TIMEOUT_DEFAUT = 60
_CAP_SORTIE = 4000


def _verifier(commande: str) -> str:
    """Renvoie la raison du refus, ou '' si la commande est acceptable."""
    bas = str(commande or "").lower().strip()
    if not bas:
        return "commande vide"
    for motif in _INTERDITS:
        if motif in bas:
            return f"motif interdit ({motif.strip()})"
    for mot in _MOTS_INTERDITS:
        if mot in bas:
            return f"secret ou donnee sensible dans la commande ({mot})"
    if "nmap" in bas or "masscan" in bas:
        return "scan reseau refuse"
    return ""


@outil(
    nom="executer_commande",
    description=(
        "Execute une commande shell locale apres confirmation obligatoire. "
        "Refuse les commandes destructives ou sensibles. Sortie limitee."
    ),
    confirmation=True,
    annonce="Je m'apprete a executer une commande sur ton ordinateur. Confirmation obligatoire.",
)
def executer_commande(commande: str, timeout: int = _TIMEOUT_DEFAUT) -> str:
    """Execute la commande apres controle de securite, avec timeout et cap."""
    raison = _verifier(commande)
    if raison:
        return f"Commande refusee : {raison}."

    duree_max = min(int(timeout or _TIMEOUT_DEFAUT), 300)
    debut = time.time()
    try:
        resultat = subprocess.run(
            commande,
            shell=True,
            capture_output=True,
            text=True,
            timeout=duree_max,
            cwd=str(Path.home()),
        )
    except subprocess.TimeoutExpired:
        return (
            f"Commande arretee : elle depassait {duree_max} secondes. "
            "Rien n'a ete perdu, mais relance-la en plus court ou precise un timeout."
        )
    except OSError as erreur:
        return f"Execution impossible : {erreur}"

    duree = time.time() - debut
    sortie = (resultat.stdout or "") + (resultat.stderr or "")
    sortie = sortie.strip()
    if len(sortie) > _CAP_SORTIE:
        sortie = sortie[:_CAP_SORTIE] + "\n… (sortie tronquee)"
    _journaliser(commande, duree, resultat.returncode)
    entete = f"Termine en {duree:.1f}s (code {resultat.returncode})."
    if sortie:
        return f"{entete}\n{sortie}"
    return f"{entete} (aucune sortie)"


def _journaliser(commande: str, duree: float, code: int) -> None:
    """Trace l'execution dans le journal operateur, sans jamais logger un secret."""
    try:
        from core import operator
        operator.journaliser("systeme", f"shell : {commande} ({duree:.1f}s, code {code})")
    except Exception:  # pragma: no cover - le journal ne doit jamais casser le shell
        pass
