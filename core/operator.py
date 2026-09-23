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
            "niveau": round(float(hud._ETAT.get("niveau", 0.0) or 0.0), 3),
        }
    except Exception:
        return {"etat": "veille", "modele": "", "routage": "",
                "micro": False, "niveau": 0.0}


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
    from core import registre, integrations
    from core import buts
    buts.initialiser_modele()
    return {
        "kpis": _kpis(),
        "a_valider": _file_validation(),
        "journal": _charger()[:60],
        "taches": _taches(),
        "vie": _vie(),
        "mode": registre.mode(),
        "fil_vocal": _fil_vocal(),
        "integrations": integrations.etat(),
        "buts": buts.lister(),
    }


def profil():
    """Nom de l'utilisateur pour la top bar (config utilisateur.nom)."""
    nom = (reglage("utilisateur.nom", "") or "Moi").strip()
    return {"nom": nom[:40] or "Moi"}


def mode():
    """Mode global MANUAL / AUTO (core.registre)."""
    from core import registre
    return {"mode": registre.mode()}


def changer_mode(valeur):
    """Bascule MANUAL / AUTO depuis la console. Un N3 (suppressions, envois,
    argent) reste a confirmation dans les deux modes."""
    from core import registre
    v = str(valeur or "").strip().lower()
    if v not in ("manual", "auto"):
        return {"ok": False, "mode": registre.mode()}
    avant = registre.mode()
    apres = registre.definir_mode(v)
    if apres != avant:
        journaliser("systeme", f"Mode global : {apres.upper()}",
                    "bascule depuis la console ZOEY OS")
    return {"ok": True, "mode": apres}


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


def valider_id(ident):
    """Valide l'action identifiee (bouton d'une carte de la conversation)."""
    from core import registre
    annonce = _annonce_de_id(ident)
    resultat = registre.executer_confirme_id(int(ident), memoriser=False)
    if resultat is None:
        return {"ok": False, "message": "Action deja traitee."}
    journaliser("validation", f"Action validee depuis la page : {annonce or ident}",
                str(resultat)[:400])
    return {"ok": True, "resultat": str(resultat)[:400], "reste": len(registre.file_en_attente())}


def refuser_id(ident):
    """Refuse l'action identifiee (bouton d'une carte de la conversation)."""
    from core import registre
    annonce = _annonce_de_id(ident)
    if not registre.annuler_confirme_id(int(ident)):
        return {"ok": False, "message": "Action deja traitee."}
    journaliser("validation", f"Action refusee depuis la page : {annonce or ident}")
    return {"ok": True, "message": f"{annonce or ident} annule.", "reste": len(registre.file_en_attente())}


def _annonce_de_id(ident):
    """L'annonce de l'action identifiee, si elle est encore en file."""
    from core import registre
    for e in registre.file_en_attente():
        if e["id"] == int(ident):
            return e["annonce"]
    return None


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


def message_en_attente():
    """True si des demandes ecrites attendent (sans les consommer)."""
    return not _MESSAGES.empty()


_TRAITEMENTS = {}


def debut_traitement(ident):
    """Une demande ecrite passe en traitement (heure de debut enregistree)."""
    with _VERROU:
        _TRAITEMENTS[ident] = time.time()


def fin_traitement(ident, a_expire=False):
    """Le traitement est termine (ou expire) : plus affiche comme en cours."""
    with _VERROU:
        _TRAITEMENTS.pop(ident, None)
        if a_expire:
            _CONVERSATION.append({
                "role": "jarvis",
                "texte": "Delai depasse sur cette demande — repose-la ou "
                         "utilise la voix.",
                "ts": time.time(),
            })
            del _CONVERSATION[:-_MAX_CONV]


def etat_traitement():
    """Etat du chat ecrit pour la page : demande en cours (et depuis combien
    de temps) + demandes en attente. La page affiche ce qui se passe au lieu
    d'un compte a rebours muet."""
    with _VERROU:
        en_cours = [{"id": k, "depuis": round(time.time() - v, 1)}
                    for k, v in _TRAITEMENTS.items()]
    return {"en_cours": en_cours, "en_attente": _MESSAGES.qsize()}


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


def question_validation(ident, outil, niv, annonce):
    """Une action attend ton feu vert : la question apparait dans la conversation
    avec ses boutons Valider / Refuser, comme une vraie question de Jarvis."""
    texte = (annonce or f"Je vais executer {outil}.") + " Tu confirmes ?"
    with _VERROU:
        _CONVERSATION.append({"role": "jarvis", "type": "validation",
                              "texte": texte, "id": ident,
                              "outil": outil, "niveau": niv,
                              "ts": time.time()})
        del _CONVERSATION[:-_MAX_CONV]


def reponse_vue(texte):
    """Depose une reponse vocale dans la conversation de la console : meme
    quand la reponse ne vient PAS du pipeline ecrit (reponse vocale, route
    prioritaire), elle s'affiche dans le fil. Dedup sur le texte : une
    reponse identique consecutive n'est pas reinjectee."""
    texte = str(texte or "")[:2000]
    with _VERROU:
        if _CONVERSATION and _CONVERSATION[-1].get("texte") == texte:
            return
        _CONVERSATION.append({"role": "jarvis", "texte": texte,
                              "ts": time.time()})
        del _CONVERSATION[:-_MAX_CONV]


def conversation():

    """Derniers echanges, pour affichage immediat a l'ouverture de la page."""
    with _VERROU:
        return list(_CONVERSATION)


def carte_mails(donnees):
    """Injecte une carte de compte rendu des mails dans la conversation de
    la page (meme mecanisme que les validations). Affiche les categories
    (securite, reponse attendue, interne, notifications) et les mails de
    chaque categorie, pendant que Jarvis resume a voix haute."""
    titre = str(donnees.get("titre", "Compte rendu des mails") or
                "Compte rendu des mails")[:80]
    categories = donnees.get("categories") or []
    with _VERROU:
        _CONVERSATION.append({
            "role": "jarvis", "type": "mails",
            "texte": titre,
            "categories": [{
                "titre": str(c.get("titre", ""))[:60],
                "icone": str(c.get("icone", ""))[:8],
                "mails": [{
                    "expediteur": str(m.get("expediteur", ""))[:80],
                    "objet": str(m.get("objet", ""))[:120],
                    "detail": str(m.get("detail", ""))[:200],
                    "action": str(m.get("action", ""))[:200],
                } for m in (c.get("mails") or [])[:10]],
            } for c in categories[:6]],
            "ts": time.time(),
        })
        del _CONVERSATION[:-_MAX_CONV]


def action_vue(categorie, titre, detail="", resultat="ok"):
    """Injecte une action executee dans la conversation de la page : chaque
    outil appele par Jarvis apparait comme une carte compacte dans le fil,
    en meme temps qu'il est journalise (« Pendant que tu dormais »).
    resultat : ok | en_attente | erreur."""
    with _VERROU:
        _CONVERSATION.append({
            "role": "jarvis", "type": "action",
            "texte": str(titre)[:160],
            "categorie": str(categorie)[:24] or "autre",
            "detail": str(detail)[:400],
            "resultat": str(resultat)[:16] or "ok",
            "ts": time.time(),
        })
        del _CONVERSATION[:-_MAX_CONV]


def carte_briefing(donnees):
    """Injecte une carte de briefing client dans la conversation de la page
    (meme mecanisme que les validations). Affiche la fiche CRM, le RDV et les
    3 questions de closing, pendant que Jarvis resume a voix haute."""
    client = str(donnees.get("client", "") or "?")[:60]
    rdv = str(donnees.get("rdv", "") or "")[:80]
    champs = donnees.get("champs") or []
    questions = donnees.get("questions") or []
    with _VERROU:
        _CONVERSATION.append({
            "role": "jarvis", "type": "briefing",
            "texte": f"Briefing {client}",
            "client": client, "rdv": rdv,
            "champs": [{"titre": c.get("titre", ""), "valeur": c.get("valeur", "")}
                       for c in champs[:8]],
            "questions": [str(q)[:200] for q in questions[:3]],
            "ts": time.time(),
        })
        del _CONVERSATION[:-_MAX_CONV]


# ------------------------------------------------------------------ routes

def _redirection_console(resultat):
    """Apres un callback OAuth : renvoie la console locale avec un
    parametre de resultat — le navigateur affiche le message adequat."""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(f"/console?oauth={resultat}", status_code=302)


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

    # /operator ET /console servent la console ZOEY OS (web/console.html,
    # build React inline) : orbe vivant + conversation sur le meme moteur
    # (chat ecrit, fil vocal, validations). L'ancienne page operator.html
    # reste dans web/ si on veut la rebrancher un jour.
    html_console = _RACINE / "web" / "console.html"

    _PAGE_CACHE_CONSOLE = {"contenu": None}

    def _servir_console(request: Request):
        refus = garde(request)
        if refus:
            return refus
        if not html_console.exists():
            return HTMLResponse("<h1>Console</h1><p>web/console.html manquant.</p>",
                                status_code=500)
        if _PAGE_CACHE_CONSOLE["contenu"] is None:
            _PAGE_CACHE_CONSOLE["contenu"] = html_console.read_text(encoding="utf-8")
        return HTMLResponse(_PAGE_CACHE_CONSOLE["contenu"])

    @app.get("/operator")
    def operator_page(request: Request):
        """La page Operator EST la console ZOEY OS — local uniquement."""
        return _servir_console(request)

    @app.get("/console")
    def console_page(request: Request):
        """Alias de /operator : meme console ZOEY OS."""
        return _servir_console(request)

    @app.get("/api/operator/etat")
    def api_etat(request: Request):
        return garde(request) or etat()

    @app.get("/api/operator/profil")
    def api_profil(request: Request):
        refus = garde(request)
        if refus:
            return refus
        return profil()

    @app.get("/api/operator/mode")
    def api_mode(request: Request):
        """Mode global MANUAL / AUTO affiche par la console."""
        refus = garde(request)
        if refus:
            return refus
        return mode()

    @app.get("/api/operator/integrations")
    def api_integrations(request: Request):
        """Etat REEL de connexion de chaque plateforme (config + jetons)."""
        refus = garde(request)
        if refus:
            return refus
        from core import integrations
        return {"integrations": integrations.etat()}

    @app.get("/api/operator/buts")
    def api_buts(request: Request):
        """Les buts persistes, statut deduit des integrations connectees."""
        refus = garde(request)
        if refus:
            return refus
        from core import buts
        buts.initialiser_modele()
        return {"buts": buts.lister()}

    @app.post("/api/operator/buts")
    async def api_but_creer(request: Request):
        refus = garde(request)
        if refus:
            return refus
        corps = {}
        try:
            corps = await request.json() or {}
        except Exception:
            corps = {}
        from core import buts
        but = buts.ajouter((corps or {}).get("titre", ""),
                           (corps or {}).get("requis"))
        if but:
            journaliser("systeme", f"But créé : {but['titre'][:60]}",
                        "depuis la console ZOEY OS")
        return {"ok": but is not None, "but": but}

    @app.delete("/api/operator/buts/{ident}")
    def api_but_supprimer(ident: str, request: Request):
        refus = garde(request)
        if refus:
            return refus
        from core import buts
        return {"ok": buts.supprimer(ident)}

    @app.post("/api/operator/mode")
    async def api_mode_changer(request: Request):
        """Bascule MANUAL / AUTO. Les N3 demandent dans les deux modes."""
        refus = garde(request)
        if refus:
            return refus
        corps = {}
        try:
            corps = await request.json() or {}
        except Exception:
            corps = {}
        return changer_mode((corps or {}).get("mode", ""))

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

    @app.get("/api/operator/traitement")
    def api_traitement(request: Request):
        refus = garde(request)
        if refus:
            return refus
        return etat_traitement()

    @app.get("/api/operator/vocal")
    def api_vocal(request: Request):
        refus = garde(request)
        if refus:
            return refus
        return {"fil": _fil_vocal()}

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

    @app.get("/api/operator/planning")
    def api_planning(request: Request):
        refus = garde(request)
        if refus:
            return refus
        from tools.agenda import planning_du_jour
        return planning_du_jour()

    @app.get("/api/operator/planning/mois")
    def api_planning_mois(request: Request):
        refus = garde(request)
        if refus:
            return refus
        from tools.agenda import planning_mois
        annee = request.query_params.get("annee")
        mois = request.query_params.get("mois")
        return planning_mois(annee=annee, mois=mois)

    @app.get("/api/operator/mail/brouillon")
    def api_brouillon(request: Request):
        refus = garde(request)
        if refus:
            return refus
        from tools.mail import brouillon
        return brouillon()

    @app.post("/api/operator/mail/brouillon")
    async def api_brouillon_modifier(request: Request):
        refus = garde(request)
        if refus:
            return refus
        corps = {}
        try:
            corps = await request.json()
        except Exception:
            corps = {}
        from tools.mail import brouillon, modifier_brouillon
        ok = modifier_brouillon((corps or {}).get("destinataire"),
                                (corps or {}).get("sujet"),
                                (corps or {}).get("corps"))
        if ok:
            journaliser("mail", "Brouillon modifie depuis la page",
                        str(corps)[:200])
            return {"ok": True, "brouillon": brouillon()}
        return {"ok": False}

    @app.post("/api/operator/valider/{ident}")
    def api_valider_id(ident: int, request: Request):
        refus = garde(request)
        if refus:
            return refus
        return valider_id(ident)

    @app.post("/api/operator/refuser/{ident}")
    def api_refuser_id(ident: int, request: Request):
        refus = garde(request)
        if refus:
            return refus
        return refuser_id(ident)

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

    # -------------------------------------------------------- integrations
    # Page INTEGRATIONS : catalogue + OAuth reel. Les jetons restent cote
    # serveur (chiffres) ; le navigateur ne voit que l'etat de connexion.
    @app.get("/api/integrations")
    def api_integrations_catalogue(request: Request):
        refus = garde(request)
        if refus:
            return refus
        from core import integrations_oauth
        catalogue = integrations_oauth.vue_catalogue()
        return {
            "integrations": catalogue,
            "categories": integrations_oauth.CATEGORIES,
            "connectedCount": sum(1 for c in catalogue if c["connected"]),
        }

    @app.get("/api/integrations/connected")
    def api_integrations_connectees(request: Request):
        refus = garde(request)
        if refus:
            return refus
        from core import integrations_oauth
        return {"connected": [integrations_oauth.vue_connexion(pid)
                              for pid in integrations_oauth.connectes_ids()
                              if integrations_oauth.vue_connexion(pid)]}

    @app.get("/api/integrations/{provider}/status")
    def api_integration_statut(provider: str, request: Request):
        refus = garde(request)
        if refus:
            return refus
        from core import integrations_oauth
        p = integrations_oauth.provider(provider)
        if not p:
            return JSONResponse({"ok": False,
                                 "message": "Unknown integration."},
                                status_code=404)
        vue = integrations_oauth.vue_connexion(provider)
        return {
            "ok": True,
            "connected": vue is not None,
            "connection": vue,
            "enabled": integrations_oauth.configure(provider),
            "setupRequired": not integrations_oauth.configure(provider),
        }

    @app.post("/api/integrations/{provider}/connect")
    def api_integration_connecter(provider: str, request: Request):
        """Genere l'URL OAuth REELLE du provider (state + PKCE). Sans
        identifiants configurés : erreur propre, jamais de simulation."""
        refus = garde(request)
        if refus:
            return refus
        from core import integrations_oauth
        if not integrations_oauth.provider(provider):
            return JSONResponse({"ok": False,
                                 "message": "Unknown integration."},
                                status_code=404)
        if not integrations_oauth.configure(provider):
            return JSONResponse({"ok": False,
                                 "message": "This integration requires "
                                            "additional setup. Add its client "
                                            "ID and secret to config.yaml."},
                                status_code=409)
        url = integrations_oauth.url_autorisation(
            provider, integrations_oauth._base_url_locale())
        if not url:
            return JSONResponse({"ok": False,
                                 "message": "Unable to start the connection."},
                                status_code=500)
        journaliser("systeme", f"Connexion OAuth lancée : {provider}",
                    "page INTEGRATIONS")
        return {"ok": True, "authorizationUrl": url}

    @app.get("/api/integrations/{provider}/callback")
    def api_integration_callback(provider: str, request: Request):
        """Callback OAuth : valide le state (CSRF), echange le code, stocke
        les jetons chiffres, puis renvoie la console (page locale)."""
        refus = garde(request)
        if refus:
            return refus
        from core import integrations_oauth
        erreur = request.query_params.get("error", "")
        if erreur:
            return _redirection_console("cancelled")
        code = request.query_params.get("code", "")
        state = request.query_params.get("state", "")
        verifier = integrations_oauth.valider_state(provider, state)
        if verifier is None or not code:
            return _redirection_console("state")
        _, message = integrations_oauth.echanger_code(provider, code, verifier)
        if message:
            return _redirection_console("failed")
        journaliser("systeme", f"Intégration connectée : {provider}",
                    "OAuth autorisé depuis la page INTEGRATIONS")
        return _redirection_console("connected")

    @app.post("/api/integrations/{provider}/disconnect")
    def api_integration_deconnecter(provider: str, request: Request):
        refus = garde(request)
        if refus:
            return refus
        from core import integrations_oauth
        if not integrations_oauth.connexion(provider):
            return {"ok": False, "message": "Not connected."}
        ok = integrations_oauth.deconnecter(provider)
        if ok:
            journaliser("systeme", f"Intégration déconnectée : {provider}",
                        "révocation provider + suppression locale")
        return {"ok": ok}

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

    @app.get("/api/operator/agents")
    def api_agents(request: Request):
        refus = garde(request)
        if refus:
            return refus
        from core.personnalite import agents
        from core.config import reglage
        actif = str(reglage("assistant.personnalite", "neutre") or "neutre")
        return {"agents": agents(), "actif": actif}

    @app.post("/api/operator/agent")
    async def api_agent_changer(request: Request):
        refus = garde(request)
        if refus:
            return refus
        corps = {}
        try:
            corps = await request.json()
        except Exception:
            corps = {}
        agent = str((corps or {}).get("agent") or "").strip()
        from core.personnalite import est_agent
        from core.config import definir_volatile
        if agent == "neutre" or est_agent(agent):
            definir_volatile("assistant.personnalite", agent)
            journaliser("systeme", f"Agent actif : {agent}",
                        "changement depuis la page Operator")
            return {"ok": True, "actif": agent}
        return {"ok": False, "message": f"Agent inconnu : {agent}"}

    @app.get("/api/operator/relances")
    def api_relances(request: Request):
        refus = garde(request)
        if refus:
            return refus
        from tools.monday import a_relancer
        return a_relancer()

    @app.get("/api/operator/fiche/{nom}")
    def api_fiche(nom: str, request: Request):
        refus = garde(request)
        if refus:
            return refus
        from tools.monday import fiche_client
        fiche = fiche_client(nom)
        if not fiche:
            return {"ok": False, "message": "Client introuvable dans monday."}
        return {"ok": True, "fiche": fiche}

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

    @app.get("/api/operator/knowledge")
    def api_knowledge(request: Request):
        refus = garde(request)
        if refus:
            return refus
        from tools import knowledge
        return {"documents": [{"id": d["id"], "titre": d["titre"],
                              "source": d.get("source", ""),
                              "ts": d.get("ts", 0),
                              "taille": len(d.get("contenu", ""))}
                             for d in knowledge.documents()]}

    @app.post("/api/operator/knowledge")
    async def api_knowledge_ajouter(request: Request):
        refus = garde(request)
        if refus:
            return refus
        from tools import knowledge
        corps = {}
        try:
            corps = await request.json() or {}
        except Exception:
            corps = {}
        titre = str((corps.get("titre") or "").strip())[:80]
        contenu = str((corps.get("contenu") or "").strip())
        if not contenu:
            return {"ok": False, "message": "Contenu manquant."}
        try:
            doc = knowledge.ajouter_depuis_texte(contenu, titre=titre)
        except ValueError as e:
            return {"ok": False, "message": str(e)}
        journaliser("lecture", f"Document ajouté à la base : {doc['titre']}")
        return {"ok": True, "document": {"id": doc["id"], "titre": doc["titre"]}}

    @app.get("/api/operator/knowledge/{ident}")
    def api_knowledge_document(ident: int, request: Request):
        refus = garde(request)
        if refus:
            return refus
        from tools import knowledge
        doc = knowledge.retrouver(ident)
        if not doc:
            return {"ok": False, "message": "Document introuvable."}
        return {"ok": True, "document": doc}
