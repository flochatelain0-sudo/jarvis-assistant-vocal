"""Outils vocaux : activer/couper ou calibrer les gestes de la main (webcam).

Le tracking tourne dans un sous-process isolé (Python 3.11 + MediaPipe) ; voir
core/gestes.py et docs/gestes.md. mcp_expose=False : la caméra n'est JAMAIS pilotable
à distance (ni MCP, ni Hermes).
"""
import re

from core.registre import outil
from core.util import sans_accents


def demande_calibration_gestes(phrase: str) -> bool:
    """Vrai uniquement pour un ordre explicite d'ouverture de la calibration."""
    mots = re.sub(
        r"[^a-z0-9]+", " ", sans_accents((phrase or "").lower())
    ).split()
    prefixes = (
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
    if not mots or mots[0] not in {
            "lance", "lancer", "ouvre", "ouvrir", "demarre", "demarrer",
            "calibre", "calibrer", "teste", "tester"}:
        return False
    texte = " ".join(mots)
    calibration = "calibr" in texte or "reconnaissance" in texte
    cible = any(m in mots for m in ("geste", "gestes", "main", "mains", "webcam"))
    return calibration and cible


@outil(
    nom="controler_gestes",
    description="Active ou coupe le contrôle par gestes de la main (webcam). A utiliser "
                "pour 'active les gestes', 'coupe les gestes', 'allume/éteins la caméra "
                "des gestes', 'Jarvis regarde mes mains'.",
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
