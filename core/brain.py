"""The Brain : la memoire qui se remplit toute seule.

Apres chaque tour de conversation, un extraiteur passe en revue le dernier
message de l'utilisateur et en tire ce qui merite d'etre retenu :
  - une preference (« je prefere qu'on m'appelle Florian »)
  - un proche (« ma femme s'appelle Lea » / « appelle Sophie »)
  - un projet en cours (« on demenage le 12 »)
  - un fait utile (« mon vol AF123 part a 6h »)

Rien n'est ajoute si l'information est deja connue : le Brain deduplique.
Toujours editable/oubliable via les outils remember/recall/forget et la page
Operator (« Le Cerveau »). Jamais de secret (mots de passe, cles) : ces motifs
sont exclus volontairement.

L'extraction est HEURISTIQUE (motifs regex) : zero token, zero latence ajoutee.
Le LLM garde son outil `remember` pour les cas subtils ; ce module attrape le
facile a la volee.
"""

import re

from core import memoire
from core.util import sans_accents

# Motifs d'extraction (ordre = priorite). Chaque entree : (regex, categorie).
# La cle est le groupe 1 (facultatif), le contenu le groupe 2.
_MOTIFS = [
    # Preferences : « je prefere X », « j'aime X », « je veux toujours X »
    (re.compile(r"\b(?:je pr[eé]f[eè]re|j'aime|je voudrais toujours|"
                r"je veux que tu|fais toujours)\s+(.{4,90})",
                re.IGNORECASE), "preferences"),
    # Proches : « ma femme s'appelle X », « mon pere est X », « appele X, mon frere »
    (re.compile(r"\b(?:ma|mon|mes)\s+(femme|mari|copine|copain|p[eè]re|m[eè]re|"
                r"fr[eè]re|soeur|fille|fils|associ[eé]|associee)\s+"
                r"(?:s\s*[''\u2019 ]?\s*appelle|est|c'est)?\s*"
                r"([A-ZÉÈÊ][\wéèêàç-]{1,30})",
                re.IGNORECASE), "people"),
    # Projets : « mon projet X », « je travaille sur X », « on demenage »
    (re.compile(r"\b(?:mon projet|je travaille sur|je prepare|on demenage|"
                r"je lance)\s+(.{3,60})", re.IGNORECASE), "projects"),
]

# Jamais retenu : secrets et donnees sensibles, memes si un motif matche.
_EXCLUSIONS = re.compile(
    r"\b(mot\s*de\s*passe|password|api[_\s]?key|cl[eé]\s*api|secret|"
    r"token|bic|iban|\d{4}\s*\d{4}\s*\d{4}\s*\d{4})\b", re.IGNORECASE)

# Mots-temoins d'un proche mentionne sans lien de parente (« appelle Sophie »)
_APPELS = re.compile(
    r"\b(?:appelle|previens|ecris|M.{0,3}line|message)\s+"
    r"([A-ZÉÈÊ][\wéèêàç-]{1,30})\b")


def extraire(message):
    """Renvoie la liste [(categorie, cle, contenu)] retenu depuis message."""
    message = (message or "").strip()
    if not message or len(message) > 400 or _EXCLUSIONS.search(message):
        return []
    retenus = []
    for motif, categorie in _MOTIFS:
        m = motif.search(message)
        if m:
            contenu = m.group(1).strip(" .,;!?")
            if categorie == "people":
                # group(1) = lien de parente, group(2) = prenom ; cle = prenom
                relation = m.group(1).lower()
                contenu = m.group(2).strip(" .,;!?")
                cle = contenu
                possessif = "sa" if relation in ("femme", "copine", "mere",
                                               "soeur", "fille", "associee") else "son"
                contenu = f"{possessif} {relation} : {contenu}"
            else:
                cle = contenu[:40]
            if 2 <= len(contenu):
                retenus.append((categorie, cle, contenu))
            break     # un seul retenu par message : pas de sur-apprentissage
    return retenus


def nourrir(message):
    """Extrait et memorise depuis le dernier message de l'utilisateur.

    Renvoie le nombre d'informations reellement ajoutees (0 = rien de neuf).
    """
    ajoutes = 0
    m = memoire.charger()
    modifie = False
    for categorie, cle, contenu in extraire(message):
        if categorie == "facts":
            if contenu not in m["facts"]:
                m["facts"].append(contenu)
                modifie = True
                ajoutes += 1
        else:
            if cle and contenu and m[categorie].get(cle) != contenu:
                m[categorie][cle] = contenu
                modifie = True
                ajoutes += 1
    if modifie:
        memoire.sauver(m)
    return ajoutes


def vue_brain():
    """L'etat du Brain pour la page Operator : tout ce que Jarvis sait."""
    m = memoire.charger()
    return {
        "preferences": [{"cle": k, "contenu": v} for k, v in
                        sorted(m["preferences"].items())],
        "people": [{"cle": k, "contenu": v} for k, v in
                   sorted(m["people"].items())],
        "projects": [{"cle": k, "contenu": v} for k, v in
                     sorted(m["projects"].items())],
        "facts": [{"contenu": f} for f in m["facts"]],
    }
