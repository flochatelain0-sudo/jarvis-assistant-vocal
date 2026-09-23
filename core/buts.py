"""Buts : les objectifs de Florian, persistes et pilotables depuis la console.

La console ZOEY OS affiche « Get my inbox and calendar under control » avec
les integrations que chaque but requiert. Ici, c'est REEL : les buts vivent
dans data/buts.json, le statut se deduit des integrations reellement
connectees (core/integrations.py), et l'ajout/modification/suppression est
dispo depuis la console ET depuis la conversation Jarvis.

Aucun droit nouveau : un but n'est qu'une ligne d'objectif + la liste des
integrations requises ; il ne declenche rien tout seul.
"""

import json
import threading
import time
import uuid
from pathlib import Path

_RACINE = Path(__file__).resolve().parent.parent
_FICHIER = _RACINE / "data" / "buts.json"
_VERROU = threading.RLock()
_BUTS = None
_MAX = 50


def _charger():
    global _BUTS
    if _BUTS is not None:
        return _BUTS
    with _VERROU:
        if _BUTS is None:
            try:
                donnees = json.loads(_FICHIER.read_text(encoding="utf-8"))
                _BUTS = donnees if isinstance(donnees, list) else []
            except (OSError, ValueError):
                _BUTS = []
    return _BUTS


def _sauver():
    try:
        _FICHIER.parent.mkdir(parents=True, exist_ok=True)
        _FICHIER.write_text(
            json.dumps(_charger(), ensure_ascii=False, indent=1),
            encoding="utf-8")
    except OSError:
        pass


def _statut(but):
    """JUST SET tant qu'aucune integration requise n'est connectee ;
    IN PROGRESS des qu'une l'est ; DONE si toutes le sont."""
    from core import integrations
    requis = but.get("requis") or []
    if not requis:
        return "JUST SET"
    connectes = sum(1 for r in requis if integrations.est_connecte(r))
    if connectes == 0:
        return "JUST SET"
    if connectes >= len(requis):
        return "DONE"
    return "IN PROGRESS"


def _vue(but):
    """Le but, enrichi du statut deduit et de l'etat de chaque requis."""
    from core import integrations
    etats = integrations.etat()
    v = dict(but)
    v["statut"] = _statut(but)
    v["requis"] = [
        {"id": r, "connecte": bool(etats.get(r, {}).get("connecte", False))}
        for r in (but.get("requis") or [])
    ]
    return v


def lister():
    """Tous les buts, avec statut deduit des integrations reelles."""
    with _VERROU:
        return [_vue(b) for b in _charger()]


def ajouter(titre, requis=None):
    """Cree un but ; renvoie la vue complete. Titre borne, id stable."""
    titre = str(titre or "").strip()[:120]
    if not titre:
        return None
    with _VERROU:
        from core import integrations
        valides = set(integrations.etat().keys())
        but = {
            "id": f"but-{uuid.uuid4().hex[:12]}",
            "titre": titre,
            "requis": [r for r in (requis or []) if r in valides][:8],
            "cree": time.time(),
        }
        _charger().append(but)
        del _charger()[_MAX:]
        _sauver()
        return _vue(but)


def renommer(ident, titre):
    """Change le titre d'un but (edition depuis la console)."""
    with _VERROU:
        for b in _charger():
            if b.get("id") == ident:
                b["titre"] = str(titre or "").strip()[:120] or b["titre"]
                _sauver()
                return _vue(b)
    return None


def supprimer(ident):
    """Supprime un but definitivement."""
    with _VERROU:
        autos = _charger()
        avant = len(autos)
        _BUTS[:] = [b for b in autos if b.get("id") != ident]
        _sauver()
        return len(_BUTS) < avant


def initialiser_modele():
    """Seme les six buts de demarrage si le fichier est vide (premiere
    ouverture de la console). Idempotent : ne fait rien si un but existe."""
    with _VERROU:
        if _charger():
            return False
    modeles = [
        ("Get my inbox and calendar under control", ["gmail", "gcal"]),
        ("Ship my current project to production", ["github", "pc"]),
        ("Launch and run campaigns without an agency", ["mailchimp", "canva"]),
        ("Grow my audience with better content", ["canva", "navigateur"]),
        ("Find and price winning products faster", ["shopify", "navigateur"]),
        ("Keep family logistics off my mind", ["gcal"]),
    ]
    for titre, requis in modeles:
        ajouter(titre, requis)
    return True
