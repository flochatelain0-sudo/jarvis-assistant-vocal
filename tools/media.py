"""Routage vocal déterministe des lectures multimédias courantes.

Ces commandes sont locales, réversibles et étroitement bornées. Elles évitent
donc de confier à Astra une simple pause, un changement de piste ou la recherche
d'un contenu Spotify/Netflix.
"""
import re
import time
from urllib.parse import quote_plus

from core.registre import outil
from core.util import sans_accents


_VERBES_LECTURE = {
    "mets", "met", "lance", "lancer", "joue", "jouer", "ecoute", "ecouter",
    "demarre", "demarrer",
}
_PREFIXES = (
    ("hey", "jarvis"), ("jarvis",),
    ("est", "ce", "que", "tu", "peux"),
    ("peux", "tu"), ("tu", "peux"),
    ("s", "il", "te", "plait"), ("stp",),
)
_SUFFIXES_POLITES = (
    ("s", "il", "te", "plait"), ("stp",), ("merci",),
)


def _mots(phrase):
    mots = re.sub(r"[^a-z0-9]+", " ", sans_accents(str(phrase or ""))).split()
    change = True
    while mots and change:
        change = False
        for prefixe in _PREFIXES:
            if tuple(mots[:len(prefixe)]) == prefixe:
                del mots[:len(prefixe)]
                change = True
                break
    change = True
    while mots and change:
        change = False
        for suffixe in _SUFFIXES_POLITES:
            if tuple(mots[-len(suffixe):]) == suffixe:
                del mots[-len(suffixe):]
                change = True
                break
    return mots


def _retirer_service(mots, service):
    sortie = list(mots)
    for prefixe in (("sur", service), ("dans", service), ("avec", service)):
        if tuple(sortie[-len(prefixe):]) == prefixe:
            del sortie[-len(prefixe):]
            break
    if sortie and sortie[0] == service:
        del sortie[0]
    return sortie


def router_commande_media(phrase, piece=""):
    """Renvoie ``(outil, arguments)`` pour une commande média non ambiguë."""
    mots = _mots(phrase)
    if not mots or "alexa" in mots or "echo" in mots:
        return None
    texte = " ".join(mots)

    commandes = (
        (("change de musique", "musique suivante", "piste suivante",
          "chanson suivante", "passe a la suivante", "passe au morceau suivant"),
         "suivant"),
        (("musique precedente", "piste precedente", "chanson precedente",
          "reviens a la precedente", "morceau precedent"), "precedent"),
        (("mets en pause", "met en pause", "pause la musique", "pause"), "pause"),
        (("reprends la musique", "reprend la musique", "remets la musique",
          "remet la musique", "reprends la lecture", "reprend la lecture"),
         "reprendre"),
    )
    for formulations, action in commandes:
        if texte in formulations:
            if piece:
                return "controler_spotify", {"action": action, "piece": piece}
            return "controler_media", {
                "action": "pause" if action == "reprendre" else action,
            }

    if mots[0] not in _VERBES_LECTURE:
        return None
    del mots[0]
    if mots and mots[0] in {"m", "me", "moi"}:
        del mots[0]

    if "netflix" in mots:
        mots = _retirer_service(mots, "netflix")
        for prefixe in (("la", "serie"), ("ma", "serie"), ("le", "film"),
                        ("mon", "film"), ("la", "saison"), ("ma", "saison"),
                        ("serie",), ("film",), ("saison",)):
            if tuple(mots[:len(prefixe)]) == prefixe:
                del mots[:len(prefixe)]
                break
        titre = " ".join(mots).strip()
        return ("lire_netflix", {"titre": titre}) if titre else None

    spotify_explicit = "spotify" in mots
    mots = _retirer_service(mots, "spotify")
    type_media = "titre"
    prefixes_playlist = (
        ("ma", "playlist"), ("la", "playlist"), ("une", "playlist"),
        ("playlist",),
    )
    for prefixe in prefixes_playlist:
        if tuple(mots[:len(prefixe)]) == prefixe:
            del mots[:len(prefixe)]
            type_media = "playlist"
            break
    if type_media == "titre":
        for prefixe in (("la", "chanson"), ("le", "morceau"), ("le", "titre"),
                        ("chanson",), ("morceau",), ("titre",)):
            if tuple(mots[:len(prefixe)]) == prefixe:
                del mots[:len(prefixe)]
                spotify_explicit = True
                break
    recherche = " ".join(mots).strip()
    if recherche and (spotify_explicit or type_media == "playlist"):
        args = {"recherche": recherche, "type_media": type_media}
        if piece:
            args["piece"] = piece
        return "lire_spotify", args
    return None


@outil(
    nom="lire_netflix",
    description="Recherche et lance une série ou un film précis sur Netflix sans "
                "prendre le contrôle général du PC. Pour « lance la série X sur "
                "Netflix » ou « mets le film Y sur Netflix ».",
    parametres={
        "type": "object",
        "properties": {
            "titre": {"type": "string", "description": "Titre de la série ou du film."},
        },
        "required": ["titre"],
    },
    lent=True,
    phrase_attente="J'ouvre le titre sur Netflix.",
)
def lire_netflix(titre: str) -> str:
    """Ouvre la recherche Netflix puis tente une seule action de lecture sûre."""
    titre = str(titre or "").strip()
    if not titre:
        return "Dis-moi quelle série ou quel film lancer sur Netflix."
    from tools.navigateur import browser_interact, browser_open
    ouverture = browser_open(
        url=f"https://www.netflix.com/search?q={quote_plus(titre)}")
    if "pas pu" in ouverture.lower() or "reussi" in ouverture.lower():
        return ouverture
    time.sleep(1.0)
    action = browser_interact(
        f"Sur Netflix uniquement, lance le résultat correspondant exactement à « {titre} » "
        "en cliquant sur son bouton Lecture s'il est visible ; sinon ouvre sa fiche. "
        "Ne choisis rien si la correspondance n'est pas claire.")
    if action.startswith(("C'est", "Saisi", "Voila")):
        return f"Je lance « {titre} » sur Netflix."
    return f"J'ai ouvert la recherche Netflix pour « {titre} »."
