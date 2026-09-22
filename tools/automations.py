"""Automations vocales : cree, liste, supprime des routines recurrentes.

« Jarvis, chaque matin fais-moi un brief » -> automation tous les jours a 08:00.
« chaque vendredi, ou j'en suis sur mes factures » -> action factures le
vendredi a 17:00 (heure par defaut modifiable).

SECURITE : la creation d'une automation est N1 (elle ne declenche que des
actions de lecture deja autorisees), mais l'heure exacte reste modifiable dans
la page Operator. Aucune action N2/N3 n'est jamais executee par une automation.
"""

import re

from core import automations
from core.registre import outil
from core.util import sans_accents

_ACTIONS = {
    "brief": {"mots": {"brief", "matin", "journee", "point"},
              "moment": "08:00"},
    "mails": {"mots": {"mail", "mails", "mails", "boite", "courrier"},
              "moment": "12:30"},
    "agenda": {"mots": {"agenda", "calendrier", "evenements", "rendez"},
               "moment": "21:00"},
    "factures": {"mots": {"facture", "factures", "impaye", "impayes",
                          "facturation", "relance"},
                 "moment": "17:00"},
}

_JOURS = {"lundi": "lundi", "mardi": "mardi", "mercredi": "mercredi",
          "jeudi": "jeudi", "vendredi": "vendredi", "samedi": "samedi",
          "dimanche": "dimanche",
          "matin": None, "soir": None, "midi": None, "semaine": "semaine"}


def _deviner_action(phrase):
    mots = set(sans_accents((phrase or "").lower()).split())
    for action, conf in _ACTIONS.items():
        if mots & conf["mots"]:
            return action, conf["moment"]
    return "brief", "08:00"


def _deviner_jours(phrase):
    """'chaque vendredi' -> ['vendredi'] ; 'chaque jour' -> tous les jours."""
    normalisee = sans_accents((phrase or "").lower())
    if re.search(r"\bchaque jour\b|\btous les jours\b|\bquotidien", normalisee):
        return []
    jours = []
    for j in ("lundi", "mardi", "mercredi", "jeudi", "vendredi",
              "samedi", "dimanche"):
        if j in normalisee:
            jours.append(j)
    if "semaine" in normalisee and "fin de" not in normalisee:
        return ["lundi", "mardi", "mercredi", "jeudi", "vendredi"]
    if "week" in normalisee or "fin de semaine" in normalisee:
        return ["samedi", "dimanche"]
    return jours


def _deviner_moment(phrase, defaut):
    """Extrait une heure ('a 7h', 'a 7h30', 'a 07:00') sinon renvoie le defaut."""
    m = re.search(r"\b(?:a|à)\s*(\d{1,2})\s*[h:](\d{2})?\b",
                  sans_accents(phrase or "").lower())
    if m:
        return f"{int(m.group(1)):02d}:{m.group(2) or '00'}"
    return defaut


@outil(
    nom="automation_creer",
    description="Cree une routine recurrente qui tournera toute seule. A "
                "utiliser quand l'utilisateur dit 'chaque matin', 'tous les "
                "vendredis', 'chaque jour a 9h fais...'. Precise l'action "
                "(brief/mails/agenda/factures), l'heure et les jours.",
    parametres={
        "type": "object",
        "properties": {
            "nom": {"type": "string",
                    "description": "Nom court de la routine, ex 'Brief du matin'."},
            "action": {"type": "string",
                       "enum": ["brief", "mails", "agenda", "factures"],
                       "description": "Ce que Jarvis fera a chaque execution."},
            "heure": {"type": "string",
                      "description": "Heure d'execution, format HH:MM. "
                                     "Ex '08:00'."},
            "jours": {"type": "array", "items": {"type": "string"},
                      "description": "Jours d'execution : lundi a dimanche. "
                                     "Vide = tous les jours."},
        },
        "required": ["nom", "action"],
    },
)
def automation_creer(nom: str, action: str, heure: str = "", jours=None) -> str:
    """Cree l'automation et confirme a voix haute."""
    action = action if action in _ACTIONS else "brief"
    moment = (heure or "").strip() or _ACTIONS[action]["moment"]
    auto = automations.ajouter(nom, moment, action, jours=jours)
    jours_txt = "tous les jours" if not auto["jours"] else ", ".join(auto["jours"])
    return (f"C'est programme : {auto['nom']} — {action} a {auto['moment']}, "
            f"{jours_txt}. Tu la verras dans l'Operator, tu peux l'y desactiver.")


@outil(
    nom="automation_liste",
    description="Liste les automations recurrentes actives. A utiliser quand "
                "l'utilisateur demande 'mes routines', 'qu'est-ce que tu fais "
                "tout seul', 'mes automations'.",
    parametres={"type": "object", "properties": {}},
)
def automation_liste() -> str:
    autos = automations.lister()
    if not autos:
        return ("Aucune automation pour l'instant. Dis par exemple : "
                "'chaque matin, fais-moi un brief'.")
    lignes = []
    for a in autos:
        etat = "active" if a.get("active") else "en pause"
        jours = "tous les jours" if not a.get("jours") else ", ".join(a["jours"])
        lignes.append(f"{a['nom']} : {a['action']} a {a['moment']}, "
                      f"{jours} ({etat})")
    return "Tes automations : " + " ; ".join(lignes)


@outil(
    nom="automation_supprimer",
    description="Supprime une automation recurrente. A utiliser quand "
                "l'utilisateur dit 'arrete le brief du matin', 'supprime ma "
                "routine...'.",
    parametres={
        "type": "object",
        "properties": {
            "nom": {"type": "string",
                    "description": "Nom (ou debut du nom) de l'automation."},
        },
        "required": ["nom"],
    },
    confirmation=True,
)
def automation_supprimer(nom: str) -> str:
    """Supprime par nom approximatif."""
    cible = sans_accents((nom or "").lower()).strip()
    for a in automations.lister():
        if cible in sans_accents(a["nom"].lower()):
            if automations.supprimer(a["id"]):
                return f"Automation {a['nom']} supprimee."
    return f"Aucune automation ne ressemble a {nom}."
