"""Automations : les routines recurrentes qui tournent toutes seules.

Le cœur du « 24/7 » : decris une routine une fois (« chaque matin, resume mes
mails »), Jarvis l'execute en arriere-plan, a l'heure dite, sans que tu
redemandes. Chaque execution est journalisee dans l'Operator (« Pendant que tu
dormais ») ; les actions sensibles partent dans la file de validation, comme a
la voix.

Modele de donnees (data/automations.json) :
  [{"id": "...", "nom": "Brief du matin", "moment": "08:00",
    "lundi": true, ..., "dimanche": true, "active": true,
    "action": "brief", "parametres": {...},
    "derniere": 0.0, "prochaine": 0.0}]

Actions disponibles (N1, lecture seule, sauf mention contraire) :
  - brief      : heure + meteo + apercu des derniers mails
  - mails      : resume des derniers mails non lus
  - agenda     : evenements du jour
  - factures   : statut facturation (impayes, relances)
  - memoire    : rappelle une information de la memoire
  - hermes     : delegue un travail a Hermes (worker silencieux)

SECURITE : aucune action N2/N3 n'est jamais executee directement — elles sont
mises en file (registre) et attendent ton feu vert, exactement comme la
confirmation vocale. Les automations ne creent AUCUN droit nouveau.
"""

import json
import logging
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

LOG = logging.getLogger("jarvis.automations")

_RACINE = Path(__file__).resolve().parent.parent
_FICHIER = _RACINE / "data" / "automations.json"

_VERROU = threading.RLock()
_AUTOMATIONS = None        # chargees paresseusement
_THREAD = None
_ARRET = threading.Event()

_JOURS = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")

# Recurrentes predefinies, proposables par le LLM ou depuis la page.
MODELES = {
    "brief_matin": {
        "nom": "Brief du matin", "moment": "08:00", "action": "brief",
        "description": "Chaque matin : heure, meteo et apercu des mails.",
    },
    "mails_midi": {
        "nom": "Resume des mails", "moment": "12:30", "action": "mails",
        "description": "Chaque midi : les derniers mails non lus, resumes.",
    },
    "agenda_soir": {
        "nom": "Agenda de demain", "moment": "21:00", "action": "agenda",
        "description": "Chaque soir : ce qui t'attend demain.",
    },
    "factures_vendredi": {
        "nom": "Point factures", "moment": "17:00", "action": "factures",
        "description": "Chaque vendredi : impayes et relances a faire.",
        "jours": {"vendredi"},
    },
}


# ------------------------------------------------------------------ stockage

def _charger():
    """Charge les automations, toleramment (fichier absent/corrompu)."""
    global _AUTOMATIONS
    if _AUTOMATIONS is not None:
        return _AUTOMATIONS
    with _VERROU:
        if _AUTOMATIONS is None:
            try:
                donnees = json.loads(_FICHIER.read_text(encoding="utf-8"))
                _AUTOMATIONS = donnees if isinstance(donnees, list) else []
            except (OSError, ValueError):
                _AUTOMATIONS = []
    return _AUTOMATIONS


def _sauver():
    try:
        _FICHIER.parent.mkdir(parents=True, exist_ok=True)
        _FICHIER.write_text(json.dumps(_charger(), ensure_ascii=False, indent=1),
                            encoding="utf-8")
    except OSError:
        LOG.exception("automations : ecriture impossible")


def _normaliser_jours(jours):
    """{'lundi': true, ...} ou liste ['lundi'] -> set de jours valides."""
    if isinstance(jours, dict):
        return {j for j in _JOURS if jours.get(j)}
    if isinstance(jours, (list, set)):
        return {j for j in jours if j in _JOURS}
    return set(_JOURS)


# ------------------------------------------------------------- planification

def _prochaine_execution(auto):
    """Timestamp de la prochaine execution, a partir de maintenant."""
    jours = _normaliser_jours(auto.get("jours"))
    moment = str(auto.get("moment", "08:00")).strip()
    try:
        h, m = moment.split(":", 1)
        heure_cible = datetime.now().replace(hour=int(h), minute=int(m),
                                             second=0, microsecond=0)
    except (ValueError, TypeError):
        heure_cible = datetime.now().replace(hour=8, minute=0,
                                             second=0, microsecond=0)
    if not jours:
        jours = set(_JOURS)
    # cherche le prochain jour actif, a partir d'aujourd'hui
    essai = heure_cible
    for _ in range(8):
        if _jour_fr(essai) in jours and essai > datetime.now():
            return essai.timestamp()
        essai += timedelta(days=1)
    return essai.timestamp()


def _jour_fr(d):
    """Nom du jour en francais ('lundi'...), depuis une date."""
    return _JOURS[d.weekday()]


def _maj_prochaine(auto):
    auto["prochaine"] = _prochaine_execution(auto)
    return auto


# ------------------------------------------------------------------ actions

def _journaliser(categorie, titre, detail=""):
    try:
        from core import operator
        operator.journaliser(categorie, titre, detail)
    except Exception:
        LOG.exception("journalisation operator depuis automations")


def _executer_action(action, parametres):
    """Execute une action N1 (lecture) et renvoie un resume.

    Les exceptions remontent a l'appelant : elles sont journalisees comme
    « echec » sans interrompre le planificateur.
    """
    action = (action or "brief").strip().lower()
    parametres = parametres or {}
    if action == "brief":
        from tools.brief import faire_brief
        return faire_brief()
    if action == "mails":
        from tools.mail import lire_mails
        return lire_mails(nombre=int(parametres.get("nombre", 5)))
    if action == "agenda":
        from tools.agenda import get_events
        return get_events(periode=parametres.get("periode", "aujourd'hui"))
    if action == "factures":
        from tools.factures import factures_statut
        return factures_statut()
    if action == "memoire":
        from tools.memoire import recall
        return recall(requete=parametres.get("requete", ""))
    if action == "hermes":
        from tools.deleguer_a_hermes import deleguer_en_fond
        return deleguer_en_fond(
            parametres.get("tache", "Resume la journee."),
            intro="Worker termine : ",
            session=parametres.get("session", "automations"))
    raise ValueError(f"action inconnue : {action}")


def _executer_automation(auto):
    """Une execution complete : action + journal + annonce."""
    nom = auto.get("nom", "automation")
    LOG.info("automation « %s » : execution", nom)
    try:
        resume = str(_executer_action(auto.get("action"), auto.get("parametres")))
    except Exception as e:
        LOG.exception("automation « %s » a echoue", nom)
        _journaliser("systeme", f"Automation « {nom} » en echec", str(e)[:200])
        return
    _journaliser("lecture", f"Automation « {nom} » executee", resume[:400])
    # Annonce vocale non bloquante, filtree, seulement si on ne dort pas :
    # le journal Operator garde la trace complete de toute facon.
    try:
        from core.config import reglage
        heure = datetime.now().hour
        if reglage("automations.annonces_vocales", True) and 8 <= heure < 22:
            import threading
            from core import voix
            from core import confidentialite
            texte = confidentialite.filtrer(resume[:400])
            threading.Thread(
                target=lambda: voix.parler(texte), daemon=True).start()
    except Exception:
        LOG.exception("annonce vocale de l'automation")


# --------------------------------------------------------------- API publique

def lister():
    """Toutes les automations, avec leur prochaine execution."""
    with _VERROU:
        autos = [dict(a) for a in _charger()]
    for a in autos:
        if not a.get("prochaine"):
            a["prochaine"] = _prochaine_execution(a)
    return autos


def ajouter(nom, moment, action, jours=None, parametres=None, modele=None):
    """Cree une automation. Renvoie le dict complet."""
    jours_norm = _normaliser_jours(jours)
    auto = {
        "id": f"auto-{int(time.time() * 1000) % 10**10}",
        "nom": str(nom or "Automation")[:80],
        "moment": str(moment or "08:00")[:5],
        "action": str(action or "brief")[:20],
        "jours": sorted(jours_norm) if jours_norm and jours is not None else [],
        "parametres": parametres if isinstance(parametres, dict) else {},
        "active": True,
        "derniere": 0,
        "prochaine": 0,
    }
    if modele and modele in MODELES:
        m = MODELES[modele]
        auto.update(nom=m["nom"], moment=m["moment"], action=m["action"])
    _maj_prochaine(auto)
    with _VERROU:
        _charger().append(auto)
        _sauver()
    _journaliser("systeme", f"Automation creee : {auto['nom']}",
                 f"action {auto['action']} a {auto['moment']}")
    return auto


def activer(identifiant, active=True):
    """Active/desactive une automation (pause sans suppression)."""
    with _VERROU:
        for a in _charger():
            if a.get("id") == identifiant:
                a["active"] = bool(active)
                _maj_prochaine(a)
                _sauver()
                return True
    return False


def supprimer(identifiant):
    """Supprime une automation definitivement."""
    with _VERROU:
        autos = _charger()
        avant = len(autos)
        _AUTOMATIONS[:] = [a for a in autos if a.get("id") != identifiant]
        _sauver()
        return len(_AUTOMATIONS) < avant


def executer_maintenant(identifiant):
    """Declenche une automation hors planification (bouton « Tester »)."""
    with _VERROU:
        auto = next((a for a in _charger() if a.get("id") == identifiant), None)
        auto = dict(auto) if auto else None
    if not auto:
        return False
    threading.Thread(target=_executer_automation, args=(auto,), daemon=True).start()
    return True


# ------------------------------------------------------------- planificateur

def _boucle():
    """Le planificateur : reveille chaque minute, execute ce qui est du."""
    while not _ARRET.is_set():
        try:
            maintenant = time.time()
            dues = []
            with _VERROU:
                for a in _charger():
                    if not a.get("active"):
                        continue
                    if not a.get("prochaine"):
                        _maj_prochaine(a)
                    if a["prochaine"] <= maintenant:
                        a["derniere"] = maintenant
                        _maj_prochaine(a)
                        dues.append(dict(a))
                if dues:
                    _sauver()
            for auto in dues:
                _executer_automation(auto)
        except Exception:
            LOG.exception("boucle automations")
        _ARRET.wait(60)


def demarrer():
    """Lance le planificateur en thread daemon (appele au demarrage)."""
    global _THREAD
    if _THREAD and _THREAD.is_alive():
        return
    _ARRET.clear()
    _THREAD = threading.Thread(target=_boucle, daemon=True, name="automations")
    _THREAD.start()
    LOG.info("planificateur d'automations demarre (%d active(s))",
             sum(1 for a in _charger() if a.get("active")))


def arreter():
    _ARRET.set()
