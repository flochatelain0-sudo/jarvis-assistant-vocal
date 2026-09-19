"""Outils vocaux : activer/couper ou calibrer les gestes de la main (webcam).

Le tracking tourne dans un sous-process isolé (Python 3.11 + MediaPipe) ; voir
core/gestes.py et docs/gestes.md. mcp_expose=False : la caméra n'est JAMAIS pilotable
à distance (ni MCP, ni Hermes).
"""
import re

from core.registre import outil
from core.util import sans_accents


def _mots_commande(phrase: str):
    """Normalise une commande et retire wake word/formules de politesse."""
    mots = re.sub(
        r"[^a-z0-9]+", " ", sans_accents((phrase or "").lower())
    ).split()
    prefixes = (
        ("hey", "jarvis"), ("jarvis",),
        ("est", "ce", "que", "tu", "peux"), ("peux", "tu"), ("tu", "peux"),
        ("s", "il", "te", "plait"), ("stp",),
    )
    change = True
    while mots and change:
        change = False
        for prefixe in prefixes:
            if tuple(mots[:len(prefixe)]) == prefixe:
                del mots[:len(prefixe)]
                change = True
                break
    return mots


def demande_mode_visio(phrase: str):
    """True=active la détection visible, False=la coupe, None=pas un ordre visio."""
    mots = _mots_commande(phrase)
    if "visio" not in mots:
        return None
    texte = " ".join(mots)
    if any(expression in texte for expression in (
            "quitte le mode visio", "quitter le mode visio",
            "sors du mode visio", "sort du mode visio",
            "coupe le mode visio", "desactive le mode visio",
            "arrete le mode visio", "ferme le mode visio")):
        return False
    if mots and mots[0] in {
            "passe", "passer", "mets", "met", "active", "activer",
            "lance", "lancer", "ouvre", "ouvrir", "demarre", "demarrer"}:
        return True
    return None


def demande_calibration_gestes(phrase: str) -> bool:
    """Vrai uniquement pour un ordre explicite d'ouverture de la calibration."""
    mots = _mots_commande(phrase)
    if not mots or mots[0] not in {
            "lance", "lancer", "ouvre", "ouvrir", "demarre", "demarrer",
            "calibre", "calibrer", "teste", "tester"}:
        return False
    texte = " ".join(mots)
    calibration = "calibr" in texte or "reconnaissance" in texte
    cible = any(m in mots for m in ("geste", "gestes", "main", "mains", "webcam"))
    return calibration and cible


def demande_demo_gestes(phrase: str) -> bool:
    """Vrai pour un ordre explicite de démo visible avec actions réelles."""
    mots = _mots_commande(phrase)
    if not mots or mots[0] not in {
            "lance", "lancer", "ouvre", "ouvrir", "demarre", "demarrer",
            "active", "activer", "montre", "montrer", "teste", "tester"}:
        return False
    cible = any(m in mots for m in ("geste", "gestes", "main", "mains", "webcam"))
    visible = ("demo" in mots or "video" in mots
               or ("calibration" in mots and "action" in mots))
    return cible and visible


@outil(
    nom="controler_gestes",
    description="Active ou coupe le contrôle par gestes de la main (webcam). A utiliser "
                "pour 'active les gestes', 'coupe les gestes', 'allume/éteins la caméra "
                "des gestes', 'Jarvis regarde mes mains' ou 'quitte le mode visio'.",
    parametres={
        "type": "object",
        "properties": {
            "actif": {"type": "boolean", "description": "true = activer, false = couper."}
        },
        "required": ["actif"],
    },
)
def controler_gestes(actif: bool) -> str:
    from core import gestes
    return gestes.demarrer() if actif else gestes.arreter()


@outil(
    nom="lancer_calibration_gestes",
    description="Ouvre sur le PC la fenêtre locale de calibration de la webcam et "
                "des gestes. À utiliser pour 'lance/ouvre la calibration des gestes', "
                "'je veux calibrer mes mains' ou 'teste la reconnaissance des mains'. "
                "Ne pas confondre avec controler_gestes, qui active le contrôle réel.",
    parametres={"type": "object", "properties": {}},
)
def lancer_calibration_gestes() -> str:
    from core import gestes
    return gestes.lancer_calibration()


@outil(
    nom="lancer_demo_gestes",
    description="Ouvre la caméra avec les repères et les diagnostics visibles, tout "
                "en appliquant réellement les gestes sur le PC. Pour 'ouvre la démo "
                "des gestes', 'lance les gestes visibles pour ma vidéo' ou "
                "'passe en mode visio'. Local uniquement.",
    parametres={"type": "object", "properties": {}},
    mcp_expose=False,
)
def lancer_demo_gestes() -> str:
    from core import gestes
    return gestes.demarrer_demo()
