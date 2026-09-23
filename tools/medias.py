"""Lecture de medias locaux et web : videos, musiques, flux.

Vraie pile OS : on lance le lecteur REEL de la machine. Priorite :
1. VLC (interface graphique, deplacement de lecture, plein ecran) ;
2. mpv ; 3. ffplay ; 4. lecteur par defaut du systeme via plateforme.ouvrir.

Sources acceptees : fichier local (dans les dossiers autorises — memes
regles que tools/fichiers.py) ou URL http(s) directe (mp4, webm, mp3...).
"""

import shutil
import subprocess
from pathlib import Path

from core import plateforme
from core.registre import outil

from tools.fichiers import _resoudre, _relatif


def _lecteurs_disponibles() -> list[str]:
    """Lecteurs video installe, par ordre de preference (vlc > mpv > ffplay)."""
    trouves = []
    for nom in ("vlc", "mpv", "ffplay"):
        if shutil.which(nom):
            trouves.append(nom)
    return trouves


def _source_valide(source: str) -> str:
    """Valide une source locale (dossiers autorises) ou une URL directe."""
    source = str(source or "").strip()
    if not source:
        raise ValueError("source vide")
    if source.startswith(("http://", "https://")):
        if " " in source:
            raise ValueError("URL invalide")
        return source
    chemin = _resoudre(source)
    if not chemin.exists():
        raise FileNotFoundError(str(chemin))
    return str(chemin)


@outil(
    nom="jouer_media",
    description=(
        "Joue une video ou un fichier audio : chemin local (dossiers autorises) "
        "ou URL directe (mp4, webm, mp3...). Lance VLC, mpv, ffplay ou le "
        "lecteur par defaut du systeme."
    ),
    confirmation=False,
)
def jouer_media(source: str, plein_ecran: bool = False) -> str:
    """Lance la lecture dans le meilleur lecteur disponible."""
    try:
        cible = _source_valide(source)
    except FileNotFoundError:
        return "Ce fichier n'existe pas dans les dossiers autorises."
    except (PermissionError, ValueError) as erreur:
        return f"Lecture impossible : {erreur}"

    lecteurs = _lecteurs_disponibles()
    if lecteurs:
        nom = lecteurs[0]
        args = [nom]
        if plein_ecran and nom in ("vlc", "mpv"):
            args.append("--fullscreen" if nom == "mpv" else "--fullscreen")
        args.append(cible)
        try:
            subprocess.Popen(args, **plateforme.detache())
            return f"Lecture lancee ({nom}) : {cible}"
        except OSError as erreur:
            return f"Lancement de {nom} impossible : {erreur}"
    try:
        plateforme.ouvrir(cible)
        return f"Lecture lancee (lecteur par defaut) : {cible}"
    except Exception as erreur:
        return (
            f"Je n'ai trouve aucun lecteur installable (VLC, mpv...). "
            f"Ouverture impossible : {erreur}"
        )


@outil(
    nom="arreter_media",
    description="Arrete le lecteur media lance par jouer_media (vlc, mpv ou ffplay).",
    confirmation=False,
)
def arreter_media() -> str:
    """Termine les lecteurs connus ; jamais les autres processus."""
    tues = []
    for nom in ("vlc", "mpv", "ffplay"):
        if shutil.which(nom) and _tuer(nom):
            tues.append(nom)
    if tues:
        return "Lecture arretee (" + ", ".join(tues) + ")."
    return "Aucune lecture en cours a arreter."


def _tuer(nom: str) -> bool:
    """Termine proprement les instances d'un lecteur, true si au moins une tuee."""
    try:
        if plateforme.EST_WINDOWS:
            r = subprocess.run(
                ["taskkill", "/IM", f"{nom}.exe"],
                capture_output=True, text=True, timeout=10,
            )
            return r.returncode == 0
        resultat = subprocess.run(
            ["pgrep", "-x", nom], capture_output=True, text=True, timeout=10
        )
        pids = [l.strip() for l in (resultat.stdout or "").splitlines() if l.strip()]
        for pid in pids:
            subprocess.run(["kill", pid], capture_output=True, timeout=5)
        return bool(pids)
    except Exception:
        return False


@outil(
    nom="controler_lecture",
    description="Met en pause, reprend, ou arrete la lecture du lecteur media (vlc uniquement).",
    confirmation=False,
)
def controler_lecture(action: str = "pause") -> str:
    """Envoie pause/play/stop a VLC via son interface de controle."""
    action = str(action or "").strip().lower()
    if action not in ("pause", "play", "stop"):
        return "Actions connues : pause, play, stop."
    if not shutil.which("vlc"):
        return "VLC n'est pas installe, je ne peux pas controller la lecture a distance."
    if not plateforme.est_mac():
        return "Le controle a distance n'est disponible qu'avec VLC sous macOS."
    try:
        plateforme.osascript(
            f'tell application "VLC" to { {"pause": "pause", "play": "play", "stop": "stop"}[action] }'
        )
        return f"VLC : {action}."
    except Exception as erreur:
        return f"VLC ne repond pas : {erreur}"
