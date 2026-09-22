"""monday.com — connecteur CRM officiel (API GraphQL v2).

Ton CRM monday.com, pilotable a la voix ET depuis la page Operator :
  - lecture   : tableaux, items, colonnes (N1, sans confirmation)
  - ecriture  : creation/modification d'item (N2, confirmation vocale — la
                meme file que tout le reste)

CONFIG (config.yaml) :
  monday:
    token: "eyJ..."        # monday.com -> avatar -> Developers -> My access tokens
    tableau: 1234567890     # ID du tableau principal (l'URL : /boards/<ID>)

L'ID du tableau est dans l'URL de ton board monday.com. Le token se cree dans
monday.com : avatar en haut a droite > Developers > My access tokens.

SECURITE :
  - mcp_expose=False : jamais expose aux agents externes.
  - Le token ne sort jamais des appels API ; jamais logge, jamais journalise.
"""

import json
import re

import requests

from core.config import reglage
from core.registre import outil


def _journal_echec(contexte, detail):
    """Trace l'echec monday dans le journal Operator (visible sur la page)."""
    try:
        from core import operator
        operator.journaliser("crm", f"monday : {contexte}", str(detail)[:200])
    except Exception:
        pass

_API = "https://api.monday.com/v2"
_TIMEOUT = 20


def _token():
    return (reglage("monday.token", "") or "").strip()


def _tableau():
    try:
        return int(str(reglage("monday.tableau", "") or "0").strip() or 0)
    except (ValueError, TypeError):
        return 0


def _configue():
    return bool(_token() and _tableau())


def _message_non_configure():
    return ("monday.com n'est pas configuré. Dans config.yaml, ajoute sous "
            "`monday:` ton `token:` (monday.com → avatar → Developers → My "
            "access tokens) et `tableau:` (l'ID dans l'URL de ton board).")


def _requete(query, variables=None):
    """Appel GraphQL ; renvoie (donnees, erreurs). Leve en cas d'erreur HTTP."""
    reponse = requests.post(
        _API,
        json={"query": query, "variables": variables or {}},
        headers={"Authorization": _token(), "Content-Type": "application/json"},
        timeout=_TIMEOUT,
    )
    reponse.raise_for_status()
    corps = reponse.json()
    return corps.get("data") or {}, corps.get("errors") or []


# ------------------------------------------------------------------ lecture


@outil(
    nom="monday_tableaux",
    description="Liste tes tableaux monday.com via l'API (ID + nom). C'est "
                "l'outil à utiliser POUR TOUTE question sur ton CRM monday.com : "
                "« mes tableaux monday », « quel est mon CRM », « où j'en suis sur "
                "mon CRM ». JAMAIS browser_open pour monday : la donnée CRM se lit "
                "par l'API, pas en ouvrant le site. LECTURE SEULE.",
    parametres={"type": "object", "properties": {}},
    mcp_expose=False,
)
def monday_tableaux() -> str:
    if not _token():
        return _message_non_configure()
    try:
        donnees, erreurs = _requete(
            "{ boards(limit: 25) { id name } }")
    except Exception as e:
        return f"Impossible de joindre monday.com ({str(e)[:80]})."
    if erreurs:
        return f"monday.com a répondu : {erreurs[0].get('message', '')[:120]}."
    tableaux = donnees.get("boards") or []
    if not tableaux:
        return "Aucun tableau accessible avec ce token."
    lignes = [f"{t['name']} (ID {t['id']})" for t in tableaux[:15]]
    return "Tes tableaux monday.com : " + " ; ".join(lignes)


@outil(
    nom="monday_items",
    description="Lit les items d'un tableau monday.com (nom + colonnes). Pour "
                "« où j'en suis sur mes clients monday », « mon pipeline », "
                "« les items de mon CRM ». LECTURE SEULE, aucun changement.",
    parametres={
        "type": "object",
        "properties": {
            "tableau": {"type": "string",
                        "description": "ID du tableau (optionnel : défaut = "
                                       "config monday.tableau)."},
            "limite": {"type": "integer",
                       "description": "Nombre max d'items (défaut 10)."},
        },
    },
    lent=True,
    phrase_attente="Je regarde ton CRM monday, un instant.",
    mcp_expose=False,
)
def monday_items(tableau: str = "", limite: int = 10) -> str:
    if not _configue() and not tableau:
        return _message_non_configure()
    id_tableau = int(tableau) if str(tableau or "").strip().isdigit() else _tableau()
    if not id_tableau:
        return "Donne-moi l'ID du tableau, ou renseigne monday.tableau dans config.yaml."
    try:
        donnees, erreurs = _requete(
            """query ($id: [ID!], $n: Int!) {
                 boards(ids: $id) { name
                   items_page(limit: $n) { items { name
                     column_values { text } } } } }""",
            {"id": [str(id_tableau)], "n": max(1, min(int(limite or 10), 25))},
        )
    except Exception as e:
        return f"Impossible de joindre monday.com ({str(e)[:80]})."
    if erreurs:
        return f"monday.com a répondu : {erreurs[0].get('message', '')[:120]}."
    boards = donnees.get("boards") or []
    if not boards:
        return "Tableau introuvable — vérifie l'ID (l'URL : /boards/<ID>)."
    items = ((boards[0].get("items_page") or {}).get("items")) or []
    if not items:
        return f"Aucun item dans « {boards[0].get('name', 'ce tableau')} »."
    lignes = []
    for it in items:
        valeurs = [cv.get("text") or "" for cv in it.get("column_values") or []]
        colonnes = " · ".join(v for v in valeurs if v)[:150]
        lignes.append(f"{it.get('name', '?')}" + (f" — {colonnes}" if colonnes else ""))
    return (f"Voici « {boards[0].get('name')} ». Résume à voix haute en 2 phrases "
            f"max. Items :\n" + "\n".join(lignes)[:3500])


# ----------------------------------------------------------------- ecriture


def _annonce_creation(args):
    return (f"créer l'item « {args.get('nom', '?')} » dans ton tableau monday.com")


@outil(
    nom="monday_creer_item",
    description="Crée un item dans ton tableau monday.com. Pour « ajoute un "
                "client Acme dans monday », « crée une affaire… ». DEMANDE "
                "CONFIRMATION avant d'écrire (règle 95/5).",
    parametres={
        "type": "object",
        "properties": {
            "nom": {"type": "string", "description": "Nom de l'item."},
            "colonnes": {"type": "string",
                         "description": "JSON des colonnes à remplir, ex "
                                        "'{\"statut\": \"En cours\", "
                                        "\"montant\": \"1200\"}'. Optionnel."},
        },
        "required": ["nom"],
    },
    confirmation=True,
    annonce=_annonce_creation,
    mcp_expose=False,
)
def monday_creer_item(nom: str, colonnes: str = "") -> str:
    """Crée l'item (après confirmation)."""
    if not _configue():
        return _message_non_configure()
    valeurs = {}
    if (colonnes or "").strip():
        try:
            valeurs = json.loads(colonnes)
            if not isinstance(valeurs, dict):
                valeurs = {}
        except ValueError:
            return "JSON invalide pour colonnes."
    try:
        donnees, erreurs = _requete(
            """mutation ($b: Int!, $n: String!, $c: JSON) {
                 create_item(board_id: $b, item_name: $n,
                            column_values: $c) { id } }""",
            {"b": _tableau(), "n": nom, "c": json.dumps(valeurs)},
        )
    except Exception as e:
        return f"La création a échoué ({str(e)[:80]})."
    if erreurs:
        return f"monday.com a refusé : {erreurs[0].get('message', '')[:120]}."
    ident = ((donnees.get("create_item") or {}).get("id")) or "?"
    return f"Item créé dans monday.com (ID {ident})."


def _annonce_maj(args):
    return (f"modifier l'item « {args.get('nom', '?')} » dans monday.com "
            f"({args.get('colonnes', '')[:60]})")


@outil(
    nom="monday_maj_item",
    description="Modifie un item monday.com existant (recherche par nom, puis "
                "mise à jour des colonnes). Pour « passe le client Acme en "
                "signé dans monday ». DEMANDE CONFIRMATION (règle 95/5).",
    parametres={
        "type": "object",
        "properties": {
            "nom": {"type": "string", "description": "Nom de l'item à modifier."},
            "colonnes": {"type": "string",
                         "description": "JSON des colonnes à changer, ex "
                                        "'{\"statut\": \"Signé\"}'."},
        },
        "required": ["nom", "colonnes"],
    },
    confirmation=True,
    annonce=_annonce_maj,
    mcp_expose=False,
)
def monday_maj_item(nom: str, colonnes: str) -> str:
    """Met à jour l'item (après confirmation)."""
    if not _configue():
        return _message_non_configure()
    try:
        valeurs = json.loads(colonnes)
        assert isinstance(valeurs, dict)
    except (ValueError, AssertionError):
        return "Le paramètre colonnes doit être un JSON valide."
    try:
        items, cursor = [], None
        for _ in range(4):
            variables = {"b": [str(_tableau())], "n": 25}
            if cursor:
                variables["c"] = cursor
            donnees, erreurs = _requete(
                """query ($b: [ID!], $n: Int!, $c: String) {
                     boards(ids: $b) { items_page(limit: $n, cursor: $c) {
                       cursor items { id name } } } }""",
                variables,
            )
            if erreurs:
                break
            boards = donnees.get("boards") or []
            page = (boards[0].get("items_page") or {}) if boards else {}
            items.extend(page.get("items") or [])
            cursor = page.get("cursor")
            if not cursor:
                break
    except Exception as e:
        return f"Impossible de joindre monday.com ({str(e)[:80]})."
    cible = next((it for it in items
                  if (it.get("name") or "").strip().lower() == (nom or "").strip().lower()), None)
    if cible is None:
        return f"Aucun item « {nom} » trouvé dans ton tableau."
    try:
        _, erreurs = _requete(
            """mutation ($id: ID!, $c: JSON!) {
                 update_column_values(item_id: $id, board_id: %d,
                                      column_values: $c) { id } }""" % _tableau(),
            {"id": cible["id"], "c": json.dumps(valeurs)},
        )
    except Exception as e:
        return f"La modification a échoué ({str(e)[:80]})."
    if erreurs:
        return f"monday.com a refusé : {erreurs[0].get('message', '')[:120]}."
    return f"Item « {nom} » mis à jour dans monday.com."


# --------------------------------------------------------------- pour l'Operator

def etat_crm():
    """Vue CRM pour la page Operator : les items du tableau principal."""
    if not _configue():
        return {"configure": False, "items": []}
    try:
        items, nom_tableau = [], ""
        cursor = None
        for _ in range(5):
            variables = {"b": [str(_tableau())], "n": 25}
            if cursor:
                variables["c"] = cursor
            donnees, erreurs = _requete(
                """query ($b: [ID!], $n: Int!, $c: String) { boards(ids: $b) { name
                    items_page(limit: $n, cursor: $c) { cursor items { name
                      column_values { id title text } } } } }""",
                variables,
            )
            if erreurs:
                _journal_echec("erreur API", erreurs[0])
                return {"configure": True, "erreur": str(erreurs[0])[:120], "items": []}
            boards = donnees.get("boards") or []
            if not boards:
                break
            nom_tableau = nom_tableau or (boards[0].get("name") or "")
            page = boards[0].get("items_page") or {}
            for it in page.get("items") or []:
                colonnes = []
                for cv in it.get("column_values") or []:
                    texte = cv.get("text") or ""
                    if texte and len(colonnes) < 6:
                        colonnes.append({"titre": cv.get("title") or cv.get("id") or "",
                                         "valeur": texte[:60]})
                items.append({
                    "nom": it.get("name", ""),
                    "colonnes": colonnes,
                })
            cursor = page.get("cursor")
            if not cursor or len(items) >= 100:
                break
        return {"configure": True, "tableau": nom_tableau, "items": items}
    except Exception as e:
        _journal_echec("injoignable", e)
        return {"configure": True, "erreur": str(e)[:120], "items": []}


# ---------------------------------------------------------------- briefing

def _chercher_items(nom, limite=30):
    """Items du tableau principal dont le nom contient `nom` (insensible a la
    casse et aux accents). Renvoie [(id, nom, [(titre, valeur), ...])]."""
    items, cursor = [], None
    cible = re.sub(r"\s+", " ", (nom or "").strip().lower())
    for _ in range(4):
        variables = {"b": [str(_tableau())], "n": 25}
        if cursor:
            variables["c"] = cursor
        donnees, erreurs = _requete(
            """query ($b: [ID!], $n: Int!, $c: String) { boards(ids: $b) {
                 items_page(limit: $n, cursor: $c) { cursor items { id name
                   column_values { id title text } } } } }""",
            variables,
        )
        if erreurs:
            break
        boards = donnees.get("boards") or []
        if not boards:
            break
        page = boards[0].get("items_page") or {}
        for it in page.get("items") or []:
            nom_item = (it.get("name") or "").strip()
            if cible and cible not in nom_item.lower():
                continue
            colonnes = []
            for cv in it.get("column_values") or []:
                texte = cv.get("text") or ""
                if texte:
                    colonnes.append((cv.get("title") or "", texte[:80]))
            items.append((it.get("id"), nom_item, colonnes))
            if len(items) >= limite:
                return items
        cursor = page.get("cursor")
        if not cursor:
            break
    return items


@outil(
    nom="brief_client",
    description="Prepare le briefing d'un appel client : fiche CRM monday "
                "(colonnes : montant, statut, historique...), RDV du jour "
                "correspondant dans l'agenda, et 3 questions de closing "
                "generees selon les donnees. Pour \u00ab brief-moi sur mon "
                "appel avec Pierre \u00bb, \u00ab prepare mon appel avec "
                "Acme \u00bb. Affiche la fiche complete sur la page Operator "
                "et resume a voix haute. LECTURE SEULE.",
    parametres={
        "type": "object",
        "properties": {
            "client": {
                "type": "string",
                "description": "Nom du client \u00e0 chercher dans monday.",
            },
        },
        "required": ["client"],
    },
    lent=True,
    phrase_attente="Je prepare ton briefing.",
    mcp_expose=False,
)
def brief_client(client: str = "") -> str:
    """Briefing avant appel : fiche monday + RDV du jour + carte sur la page."""
    if not _configue():
        return _message_non_configure()
    client = (client or "").strip()
    if not client:
        return "Quel client ?"
    try:
        items = _chercher_items(client)
    except Exception as e:
        return f"Impossible de joindre monday.com ({str(e)[:80]})."
    if not items:
        return f"Je ne trouve aucun client \u00ab {client} \u00bb dans ton CRM monday."

    fiche = items[0]
    _, nom, colonnes = fiche
    champs = {t.lower(): v for t, v in colonnes}

    rdv = ""
    try:
        from tools.agenda import planning_du_jour
        planning = planning_du_jour()
        for ev in planning.get("evenements", []):
            titre = (ev.get("titre") or "").lower()
            if client.lower() in titre or any(
                    mot and mot in titre for mot in client.lower().split()):
                rdv = (f"{ev.get('heure', '')} {ev.get('titre', '')}").strip()
                break
    except Exception:
        rdv = ""

    questions = _questions_closing(champs, rdv, colonnes)

    try:
        from core import operator
        operator.carte_briefing({
            "client": nom,
            "champs": [{"titre": t, "valeur": v} for t, v in colonnes[:8]],
            "rdv": rdv,
            "questions": questions,
        })
    except Exception:
        pass

    resume = f"{nom}"
    if rdv:
        resume += f" \u2014 RDV {rdv}"
    nb_champs = len(colonnes)
    resume += (f" : {nb_champs} informations dans la fiche"
               if nb_champs else "")
    return (f"Voici ton briefing pour {nom}. La fiche complete est affichee "
            f"sur la page Operator avec les 3 questions a poser. "
            + " ".join(f"{i+1}. {q}" for i, q in enumerate(questions)))


def _questions_closing(champs, rdv, colonnes):
    """3 questions de closing, adaptees aux donnees disponibles."""
    questions = []
    texte_champs = " ".join(v.lower() for v in champs.values())
    if any(mot in texte_champs for mot in
           ("banque", "financement", "credit", "pret")):
        questions.append(
            "Ou en es-tu de l'accord de principe de ta banque ?")
    else:
        questions.append(
            "Ou en es-tu du financement de ton projet ?")
    if any(mot in texte_champs for mot in
           ("notaire", "terrain", "compromis", "signe", "signature")):
        questions.append(
            "Le terrain est-il secured et le compromis signe chez le notaire ?")
    else:
        questions.append("Qu'est-ce qui pourrait bloquer la decision ?")
    questions.append(
        "Qu'est-ce qui t'empecherait de lancer le projet ce mois-ci ?")
    return questions[:3]


# ------------------------------------------------- route prioritaire

_MOTS_CRM = {"tableau", "tableaux", "item", "items", "crm", "client",
             "clients", "affaire", "affaires", "contact", "contacts",
             "board", "boards", "pipeline"}
_VERBES_OUVERTURE = {"ouvre", "ouvrir", "va", "vas", "aller", "site",
                     "navigateur", "chrome"}
_VERBES_ECRITURE = {"ajoute", "ajouter", "cree", "creer", "modifie", "modifier",
                    "supprime", "supprimer", "passe", "changer", "change",
                    "update", "mets", "mettre", "enregistre", "sauvegarde"}


def router_commande_monday(phrase, piece=""):
    """Questions monday en lecture : route directe, sans laisser le LLM choisir.

    Renvoie (nom_outil, arguments) pour les lectures CRM (« mes tableaux
    monday », « ou j'en suis sur mon CRM »), ou None sinon. Les ecritures
    (creer/modifier un item) restent au LLM : elles exigent une extraction
    d'arguments et une confirmation 95/5.
    """
    from core.util import sans_accents
    mots = re.sub(r"[^a-z0-9]+", " ",
                  sans_accents(str(phrase or "").lower())).split()
    if "monday" not in mots and "mondays" not in mots:
        return None
    if set(mots) & _VERBES_ECRITURE:
        return None
    if any(v in mots for v in _VERBES_OUVERTURE) and not (set(mots) & _MOTS_CRM):
        return None
    if any(m in mots for m in ("tableau", "tableaux", "board", "boards")):
        return ("monday_tableaux", {})
    if set(mots) & _MOTS_CRM:
        return ("monday_items", {"limite": 10})
    if "ou" in mots and "suis" in mots:
        return ("monday_tableaux", {})
    return None