"""Operator : le CRM d'Jarvis — journal des actions IA et file de validation.

Pendant que tu dors (ou pendant que tu travailles), Jarvis agit : il lit tes
mails, prepare des reponses, relance des factures, qualifie des prospects.
Cette page rend tout cela VISIBLE et pilotable :

  - « Pendant que tu dormais » : chaque action automatique executee (sans
    confirmation, donc N1 : lectures, recherches, resumes) est journalisee.
  - « A valider » : les actions en attente de ton feu vert (N2/N3) — les memes
    que la confirmation vocale — apparaissent ici ; tu peux valider ou
    refuser depuis la page, comme a la voix.

DOCTRINE 95/5 : Jarvis fait les 95 % tout seul, les 5 % sensibles exigent ton
feu vert. Cette page ne cree AUCUN droit nouveau : elle ne fait que afficher
et decider sur des actions qui auraient de toute facon demande ta
confirmation. Valider depuis le panneau local equivaut a dire « oui » a la
voix.

SECURITE : routes LOCALES uniquement (meme garde que le panneau), ecritures
en JSON uniquement (anti-CSRF). Le journal ne contient jamais de secrets —
des lignes d'activite : outil, cible, heure, resultat.
"""

import itertools
import json
import logging
import queue
import threading
import time
from pathlib import Path

from core.config import reglage

LOG = logging.getLogger("jarvis.operator")

_RACINE = Path(__file__).resolve().parent.parent
_JOURNAL = _RACINE / "data" / "operator_journal.json"
_MAX_ENTREES = 500              # journal borne : pas de croissance infinie

_VERROU = threading.RLock()     # reentrant : journaliser appelle _charger sous verrou
_ENTREES = None                 # liste chargee paresseusement

# Messages texte envoyes depuis la page Operator : consommes par la boucle
# principale de l'assistant, entre deux ecoutes micro. La reponse est rendue
# a la page via _REPONSES (id -> texte).
_MESSAGES = queue.Queue()
_REPONSES = {}
_COMPTEUR = itertools.count(1)


# ------------------------------------------------------------------ journal

def _charger():
    """Charge le journal une fois, toleramment (fichier absent/corrompu)."""
    global _ENTREES
    if _ENTREES is not None:
        return _ENTREES
    with _VERROU:
        if _ENTREES is None:
            try:
                _ENTREES = json.loads(_JOURNAL.read_text(encoding="utf-8"))
                if not isinstance(_ENTREES, list):
                    _ENTREES = []
            except (OSError, ValueError):
                _ENTREES = []
    return _ENTREES


def _sauver():
    try:
        _JOURNAL.parent.mkdir(parents=True, exist_ok=True)
        _JOURNAL.write_text(json.dumps(_ENTREES, ensure_ascii=False, indent=1),
                            encoding="utf-8")
    except OSError:
        LOG.exception("journal operator : ecriture impossible")


def journaliser(categorie, titre, detail="", resultat="ok"):
    """Ajoute une ligne au journal (« Pendant que tu dormais »).

    categorie : lecture | mail | facture | agenda | crm | systeme
    titre     : phrase courte, ex. « 3 mails tries »
    """
    entree = {
        "ts": time.time(),
        "categorie": str(categorie)[:24],
        "titre": str(titre)[:160],
        "detail": str(detail)[:400],
        "resultat": str(resultat)[:16] if resultat else "ok",
    }
    with _VERROU:
        _ = _charger()
        _ENTREES.insert(0, entree)
        del _ENTREES[_MAX_ENTREES:]
        _sauver()
    return entree


# ------------------------------------------------------------ file de validation

def _file_validation():
    """TOUTES les actions en attente de confirmation (registre), en ordre."""
    from core import registre
    return registre.file_en_attente()


def _nuit():
    """Vrai s'il est entre 22h et 7h : periode « Pendant que tu dormais »."""
    heure = time.localtime().tm_hour
    return heure >= 22 or heure < 7


def _kpis():
    """Chiffres du haut de page, depuis le journal reel des 24 dernieres heures."""
    entrees = _charger()
    limite = time.time() - 24 * 3600
    recentes = [e for e in entrees if e.get("ts", 0) >= limite]
    par_categorie = {}
    for e in recentes:
        c = e.get("categorie", "autre")
        par_categorie[c] = par_categorie.get(c, 0) + 1
    return {
        "actions_24h": len(recentes),
        "en_attente": len(_file_validation()),
        "par_categorie": par_categorie,
        "periode_nuit": _nuit(),
    }


def _taches():
    """Les taches deleguees a Hermes (en cours / terminees), pour la vue Taches."""
    try:
        from tools.deleguer_a_hermes import taches_liste
        return taches_liste()[:30]
    except Exception:
        return []


def _vie():
    """Etat vivant de l'assistant (HUD) : ecoute, reflexion, parole.

    L'Operator est la page unique de Jarvis : elle affiche aussi le pouls de
    l'assistant, pas seulement ses actions. Le HUD reste la source de verite.
    """
    try:
        import hud
        return {
            "etat": hud._ETAT.get("etat", "veille"),
            "modele": hud._ETAT.get("modele", ""),
            "routage": hud._ETAT.get("routage", ""),
            "micro": hud._ETAT.get("micro", False),
        }
    except Exception:
        return {"etat": "veille", "modele": "", "routage": "", "micro": False}


def _fil_vocal():
    """Dernieres transcriptions voix (toi + Jarvis), rejouees dans le chat.

    Le HUD tient l'historique borne ; l'Operator se contente de le relire pour
    que la conversation ecrite et la conversation vocale ne fassent qu'une.
    """
    try:
        import hud
        return [{"t": e.get("t", ""), "texte": e.get("texte", e.get("detail", "")),
                 "nom": e.get("nom", "")}
                for e in list(hud._HISTORIQUE)]
    except Exception:
        return []


def etat():
    """L'etat complet servi a la page Operator (API GET)."""
    return {
        "kpis": _kpis(),
        "a_valider": _file_validation(),
        "journal": _charger()[:60],
        "taches": _taches(),
        "vie": _vie(),
        "fil_vocal": _fil_vocal(),
    }


def profil():
    """Nom de l'utilisateur pour la top bar (config utilisateur.nom)."""
    nom = (reglage("utilisateur.nom", "") or "Moi").strip()
    return {"nom": nom[:40] or "Moi"}


def valider():
    """Valide l'action en attente — l'equivalent d'un « oui » a la voix."""
    from core import registre
    if not registre.nom_en_attente():
        return {"ok": False, "message": "Aucune action en attente."}
    nom = registre.nom_en_attente()
    resultat = registre.executer_confirme(memoriser=False)
    journaliser("validation", f"Action validée depuis la page : {nom}",
                str(resultat)[:400])
    return {"ok": True, "resultat": str(resultat)[:400], "reste": len(registre.file_en_attente())}


def refuser():
    """Refuse l'action en attente — l'equivalent d'un « non » a la voix."""
    from core import registre
    if not registre.nom_en_attente():
        return {"ok": False, "message": "Aucune action en attente."}
    nom = registre.nom_en_attente()
    registre.annuler_confirme()
    journaliser("validation", f"Action refusée depuis la page : {nom}")
    return {"ok": True, "message": f"{nom} annulé.", "reste": len(registre.file_en_attente())}


def refuser_tout():
    """Vide toute la file de validation depuis la page."""
    from core import registre
    n = registre.refuser_toutes()
    if n:
        journaliser("validation", f"{n} action(s) refusée(s) depuis la page")
    return {"ok": True, "message": f"{n} action(s) refusée(s)."}


# ------------------------------------------------------- messagerie ecrite

# Derniers echanges affiches dans la page (bornes).
_CONVERSATION = []
_MAX_CONV = 40


def envoyer_message(texte):
    """Demande tapee sur la page Operator : mise en file pour la boucle.

    La reponse arrive plus tard (reponse_message) ; la page pollera avec
    l'identifiant renvoye ici. Jamais bloquant.
    """
    texte = (texte or "").strip()
    if not texte:
        return {"ok": False, "message": "Message vide."}
    if len(texte) > 600:
        return {"ok": False, "message": "Message trop long (600 caracteres max)."}
    ident = next(_COMPTEUR)
    _MESSAGES.put({"id": ident, "texte": texte})
    with _VERROU:
        _CONVERSATION.append({"role": "vous", "texte": texte, "ts": time.time()})
        del _CONVERSATION[:-_MAX_CONV]
    journaliser("lecture", f"Demande écrite : {texte[:80]}")
    return {"ok": True, "id": ident}


def message_suivant():
    """Prochaine demande a traiter, ou None (appelle par la boucle principale)."""
    try:
        return _MESSAGES.get_nowait()
    except queue.Empty:
        return None


def reponse_message(ident, texte):
    """Depose la reponse de l'assistant pour la page (et l'affiche)."""
    with _VERROU:
        _REPONSES[ident] = (str(texte or "")[:2000], time.time())
        _CONVERSATION.append({"role": "jarvis", "texte": str(texte or "")[:2000],
                             "ts": time.time()})
        del _CONVERSATION[:-_MAX_CONV]
        # purger les reponses de plus de 10 minutes : pas de fuite memoire
        limite = time.time() - 600
        for cle in [k for k, v in list(_REPONSES.items()) if v[1] < limite]:
            del _REPONSES[cle]



def lire_reponse(ident):
    """La page demande la reponse ; disparait une fois lue (consommee)."""
    with _VERROU:
        valeur = _REPONSES.pop(int(ident), None)
    return valeur[0] if valeur else None


def conversation():
    """Derniers echanges, pour affichage immediat a l'ouverture de la page."""
    with _VERROU:
        return list(_CONVERSATION)


# ------------------------------------------------------------------ routes

def monter_routes(app):
    """Routes du CRM Operator, LOCALES uniquement, meme garde que le panneau."""
    from fastapi import Request
    from fastapi.responses import HTMLResponse, JSONResponse

    def garde(request: Request):
        if request.headers.get("x-forwarded-for") or request.headers.get("x-forwarded-host"):
            return JSONResponse({"ok": False,
                                 "message": "Operator accessible en local uniquement."},
                                status_code=403)
        hote = (getattr(request.client, "host", "") or "").strip().lower()
        if hote not in {"127.0.0.1", "::1", "localhost"}:
            return JSONResponse({"ok": False,
                                 "message": "Operator accessible en local uniquement."},
                                status_code=403)
        if request.method not in ("GET", "HEAD"):
            ct = (request.headers.get("content-type", "") or "").lower()
            if "application/json" not in ct:
                return JSONResponse({"ok": False, "message": "Content-Type invalide."},
                                    status_code=415)
        return None

    html = _RACINE / "web" / "operator.html"

    @app.get("/operator")
    def operator_page(request: Request):
        refus = garde(request)
        if refus:
            return refus
        if not html.exists():
            return HTMLResponse("<h1>Operator</h1><p>web/operator.html manquant.</p>",
                                status_code=500)
        return HTMLResponse(html.read_text(encoding="utf-8"))

    @app.get("/api/operator/etat")
    def api_etat(request: Request):
        return garde(request) or etat()

    @app.get("/api/operator/profil")
    def api_profil(request: Request):
        return garde(request) or profil()

    @app.post("/api/operator/valider")
    def api_valider(request: Request):
        refus = garde(request)
        if refus:
            return refus
        return valider()

    @app.post("/api/operator/message")
    async def api_message(request: Request):
        refus = garde(request)
        if refus:
            return refus
        corps = {}
        try:
            corps = await request.json()
        except Exception:
            corps = {}
        return envoyer_message((corps or {}).get("texte", ""))

    @app.get("/api/operator/reponse/{ident}")
    def api_reponse(ident: int, request: Request):
        refus = garde(request)
        if refus:
            return refus
        texte = lire_reponse(ident)
        return {"pret": texte is not None, "texte": texte or ""}

    @app.get("/api/operator/conversation")
    def api_conversation(request: Request):
        refus = garde(request)
        if refus:
            return refus
        return {"messages": conversation()}

    @app.post("/api/operator/refuser")
    def api_refuser(request: Request):
        refus = garde(request)
        if refus:
            return refus
        return refuser()

    @app.post("/api/operator/refuser_tout")
    def api_refuser_tout(request: Request):
        refus = garde(request)
        if refus:
            return refus
        return refuser_tout()

    # ---------------------------------------------------------- automations

    @app.get("/api/operator/automations")
    def api_automations(request: Request):
        refus = garde(request)
        if refus:
            return refus
        from core import automations as autos
        return {"automations": autos.lister()}

    @app.post("/api/operator/automations")
    async def api_automation_creer(request: Request):
        refus = garde(request)
        if refus:
            return refus
        from core import automations as autos
        corps = {}
        try:
            corps = await request.json() or {}
        except Exception:
            corps = {}
        auto = autos.ajouter(
            corps.get("nom", "Automation"),
            corps.get("moment", "08:00"),
            corps.get("action", "brief"),
            jours=corps.get("jours"),
            parametres=corps.get("parametres") if isinstance(corps.get("parametres"), dict) else None,
        )
        return {"ok": True, "automation": auto}

    @app.post("/api/operator/automations/{identifiant}/basculer")
    async def api_automation_basculer(identifiant: str, request: Request):
        refus = garde(request)
        if refus:
            return refus
        from core import automations as autos
        corps = {}
        try:
            corps = await request.json() or {}
        except Exception:
            corps = {}
        ok = autos.activer(identifiant, bool(corps.get("active", True)))
        return {"ok": ok}

    @app.post("/api/operator/automations/{identifiant}/tester")
    def api_automation_tester(identifiant: str, request: Request):
        refus = garde(request)
        if refus:
            return refus
        from core import automations as autos
        return {"ok": autos.executer_maintenant(identifiant)}

    @app.delete("/api/operator/automations/{identifiant}")
    def api_automation_supprimer(identifiant: str, request: Request):
        refus = garde(request)
        if refus:
            return refus
        from core import automations as autos
        return {"ok": autos.supprimer(identifiant)}

    # --------------------------------------------------------------- brain

    @app.get("/api/operator/brain")
    def api_brain(request: Request):
        refus = garde(request)
        if refus:
            return refus
        from core import brain
        return brain.vue_brain()

    # ------------------------------------------------------------- CRM monday

    @app.get("/api/operator/crm")
    def api_crm(request: Request):
        refus = garde(request)
        if refus:
            return refus
        from tools.monday import etat_crm
        return etat_crm()

    @app.post("/api/operator/brain/oublier")
    async def api_brain_oublier(request: Request):
        refus = garde(request)
        if refus:
            return refus
        from tools.memoire import forget
        corps = {}
        try:
            corps = await request.json() or {}
        except Exception:
            corps = {}
        sujet = (corps.get("sujet") or "").strip()
        if not sujet:
            return {"ok": False, "message": "Sujet manquant."}
        journaliser("systeme", f"Mémoire effacée depuis la page : {sujet[:60]}")
        return {"ok": True, "message": forget(sujet)}
