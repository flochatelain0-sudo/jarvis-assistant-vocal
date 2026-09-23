"""Lead generation LinkedIn : pipeline CRM reel, de l'ICP au follow-up.

DOCTRINE (alignee sur astra_pc._RISQUES et le registre N3) :
- UN ENVOI EST TOUJOURS N3. Une demande de connexion, un message LinkedIn,
  un mail de prospection : jamais sans feu vert explicite de Florian.
  L'autopilot (95/5) ne touche JAMAIS a ca.
- Les relances sont des BROUILLONS jusqu'a confirmation. Jarvis prepare,
  Florian valide, point.
- Pas de scraping de masse : les profils viennent de la page LinkedIn
  ouverte dans le navigateur pilote (lecture seule), jamais d'extraction
  industrielle contre les CGU.

Stockage : data/leads.json (meme philosophie que le journal operateur —
fichier JSON borne, aucune base externe obligatoire).
Pipeline : nouveau -> brouillon -> a_relancer -> repondu -> gagne | perdu.
"""

import datetime as dt
import json
import logging
import re
import threading
from pathlib import Path

from core.config import reglage
from core.registre import outil

LOG = logging.getLogger("jarvis.leads")

_RACINE = Path(__file__).resolve().parent.parent
_FICHIER = _RACINE / "data" / "leads.json"
_VERROU = threading.Lock()
_MAX_LEADS = 500

ETATS = ("nouveau", "brouillon", "a_relancer", "repondu", "gagne", "perdu")

# Delai de relance par defaut (en jours), configurable : leads.delai_relance.
_DELAI_DEFAUT = 4


def _charger() -> list[dict]:
    try:
        return json.loads(_FICHIER.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def _sauver(leads: list[dict]) -> None:
    try:
        _FICHIER.parent.mkdir(parents=True, exist_ok=True)
        _FICHIER.write_text(
            json.dumps(leads, ensure_ascii=False, indent=1), encoding="utf-8"
        )
    except OSError:
        LOG.exception("leads : sauvegarde impossible")


def _normaliser_etat(etat: str) -> str:
    etat = str(etat or "").strip().lower()
    return etat if etat in ETATS else "nouveau"


@outil(
    nom="ajouter_lead",
    description=(
        "Ajoute un prospect au CRM (nom, role, entreprise, raison de contact). "
        "Etat initial : nouveau."
    ),
)
def ajouter_lead(nom: str, entreprise: str = "", role: str = "", note: str = "") -> str:
    """Ajoute un lead au pipeline ; verifie l'ICP si celui-ci est configure."""
    nom = str(nom or "").strip()
    if not nom:
        return "Il me faut au moins un nom."
    with _VERROU:
        leads = _charger()
        if any((l.get("nom", "").lower() == nom.lower()) for l in leads):
            return f"{nom} est deja dans le pipeline."
        icp = _verifier_icp(entreprise, role)
        leads.insert(0, {
            "nom": nom[:120],
            "entreprise": str(entreprise or "")[:120],
            "role": str(role or "")[:120],
            "note": str(note or "")[:400],
            "etat": "nouveau",
            "icp": icp,
            "cree": dt.date.today().isoformat(),
            "relance_le": None,
            "historique": [],
        })
        del leads[_MAX_LEADS:]
        _sauver(leads)
    qualifie = "correspond a ton ICP" if icp else "hors ICP declare (a qualifier)"
    return f"Lead ajoute : {nom} ({qualifie}). Total pipeline : {len(leads)}."


def _verifier_icp(entreprise: str, role: str) -> bool:
    """Vrai si le lead matche l'ICP configure (leads.icp) ; sans ICP, tout passe."""
    icp = reglage("leads.icp", {}) or {}
    cibles_entreprise = [str(c).lower() for c in (icp.get("entreprises") or [])]
    cibles_role = [str(r).lower() for r in (icp.get("roles") or [])]
    if not cibles_entreprise and not cibles_role:
        return True
    entreprise_bas = str(entreprise or "").lower()
    role_bas = str(role or "").lower()
    if cibles_entreprise and any(c in entreprise_bas for c in cibles_entreprise):
        return True
    if cibles_role and any(r in role_bas for r in cibles_role):
        return True
    return not (cibles_entreprise or cibles_role)


@outil(
    nom="rediger_message_lead",
    description=(
        "Redige le message de contact LinkedIn (ou relance) pour un lead du "
        "pipeline. Le message reste un BROUILLON jusqu'a confirmation N3."
    ),
    lent=True,
    phrase_attente="Je redige le message.",
)
def rediger_message_lead(nom: str, relance: bool = False) -> str:
    """Genere un brouillon personnalise a partir des donnees REELLES du lead."""
    with _VERROU:
        leads = _charger()
        lead = next((l for l in leads if l.get("nom", "").lower() == str(nom).lower()), None)
        if lead is None:
            return f"{nom} n'est pas dans le pipeline. Ajoute-le d'abord."

        from core import llm

        contexte = (
            f"Nom : {lead['nom']}\n"
            f"Entreprise : {lead.get('entreprise') or 'inconnue'}\n"
            f"Role : {lead.get('role') or 'inconnu'}\n"
            f"Note : {lead.get('note') or 'aucune'}\n"
        )
        type_msg = "relance courte et amicale" if relance else "premier message de prise de contact"
        consigne = (
            f"Redige un {type_msg} LinkedIn pour ce prospect, en francais, "
            "3 phrases maximum, ton professionnel, aucune promesse exageree, "
            "pas de hashtag, pas d'emoji. Termine par une question ouverte.\n\n"
            + contexte
        )
        try:
            reponse = llm.llm().repondre(consigne, [], [])
            brouillon = " ".join(
                b.text for b in reponse.blocs if getattr(b, "type", "") == "text" and getattr(b, "text", "")
            ).strip()
        except Exception as erreur:
            return f"Redaction impossible ({erreur}). Vois le lead dans le CRM."
        if not brouillon:
            return f"Le modele n'a rien redige pour {lead['nom']}. Reformule la demande."

        lead["etat"] = "brouillon"
        if relance:
            lead["relance_le"] = dt.date.today().isoformat()
        lead.setdefault("historique", []).append({
            "date": dt.date.today().isoformat(),
            "type": "brouillon_relance" if relance else "brouillon_contact",
            "texte": brouillon[:1000],
        })
        _sauver(leads)

    try:
        from core import operator
        operator.carte_briefing({
            "client": lead["nom"][:40],
            "rdv": "Brouillon de relance" if relance else "Brouillon de contact",
            "champs": [{"titre": "Message prepare",
                        "valeur": brouillon[:220]}],
        })
    except Exception:  # pragma: no cover
        pass
    return (
        f"BROUILLON pour {lead['nom']} (aucun envoi sans ta confirmation) :\n"
        f"---\n{brouillon}\n---\n"
        "Dis « envoie-le » quand tu valides."
    )


@outil(
    nom="marquer_relance",
    description="Marque un lead comme relance aujourd'hui (sans rien envoyer).",
)
def marquer_relance(nom: str) -> str:
    """Note une relance manuelle faite par Florian lui-meme."""
    with _VERROU:
        leads = _charger()
        lead = next((l for l in leads if l.get("nom", "").lower() == str(nom).lower()), None)
        if lead is None:
            return f"{nom} n'est pas dans le pipeline."
        lead["etat"] = "a_relancer"
        lead["relance_le"] = dt.date.today().isoformat()
        _sauver(leads)
    return f"{lead['nom']} marque comme relance aujourd'hui."


@outil(
    nom="leads_a_relancer",
    description="Liste les leads dont la relance est due (delai depasse).",
)
def leads_a_relancer() -> str:
    """Calcule les relances dues a partir des dates REELLES du pipeline."""
    delai = int(reglage("leads.delai_relance", _DELAI_DEFAUT) or _DELAI_DEFAUT)
    aujourdhui = dt.date.today()
    dus = []
    with _VERROU:
        leads = _charger()
    for l in leads:
        if l.get("etat") in ("gagne", "perdu", "repondu"):
            continue
        relance = l.get("relance_le")
        cree = l.get("cree")
        reference = relance or cree
        if not reference:
            continue
        try:
            derniere = dt.date.fromisoformat(str(reference))
        except ValueError:
            continue
        if (aujourdhui - derniere).days >= delai:
            dus.append(l["nom"])
    if not dus:
        return f"Aucune relance due (delai : {delai} jours)."
    return f"{len(dus)} relance(s) due(s) : " + ", ".join(dus) + "."


@outil(
    nom="changer_etat_lead",
    description="Change l'etat d'un lead : nouveau, brouillon, a_relancer, repondu, gagne, perdu.",
)
def changer_etat_lead(nom: str, etat: str) -> str:
    """Mise a jour manuelle du pipeline par Florian."""
    etat = _normaliser_etat(etat)
    with _VERROU:
        leads = _charger()
        lead = next((l for l in leads if l.get("nom", "").lower() == str(nom).lower()), None)
        if lead is None:
            return f"{nom} n'est pas dans le pipeline."
        lead["etat"] = etat
        _sauver(leads)
    return f"{lead['nom']} : {etat}."


@outil(
    nom="pipeline_leads",
    description="Resume le pipeline : nombre de leads par etat, relances dues.",
)
def pipeline_leads() -> str:
    """Vue d'ensemble pour le dashboard et la voix."""
    with _VERROU:
        leads = _charger()
    if not leads:
        return "Pipeline vide. Ajoute un premier prospect."
    compteur: dict[str, int] = {}
    for l in leads:
        compteur[l.get("etat", "nouveau")] = compteur.get(l.get("etat", "nouveau"), 0) + 1
    lignes = [f"{etat} : {compteur[etat]}" for etat in ETATS if etat in compteur]
    return f"{len(leads)} leads — " + ", ".join(lignes) + "."


@outil(
    nom="envoyer_message_linkedin",
    description=(
        "ENVOIE le brouillon valide d'un lead : ouvre LinkedIn dans le "
        "navigateur pilote et prepare le message. Confirmation OBLIGATOIRE."
    ),
    confirmation=True,
    annonce="Je m'apprete a envoyer un message LinkedIn en ton nom. Confirmation obligatoire.",
)
def envoyer_message_linkedin(nom: str) -> str:
    """N3 : ouvre la page du lead dans le navigateur pilote, colle le brouillon.

    On ne clique jamais sur Envoyer tout seul : Florian garde la main sur
    l'envoi reel. Le message est pret a l'ecran, il n'a plus qu'a valider.
    """
    with _VERROU:
        leads = _charger()
        lead = next((l for l in leads if l.get("nom", "").lower() == str(nom).lower()), None)
        if lead is None:
            return f"{nom} n'est pas dans le pipeline."
        brouillon = None
        for h in reversed(lead.get("historique", [])):
            if h.get("type", "").startswith("brouillon") and h.get("texte"):
                brouillon = h["texte"]
                break
    if brouillon is None:
        return f"Aucun brouillon pour {nom}. Demande-moi d'abord de le rediger."

    from tools import navigateur

    browser = navigateur._connexion()
    if browser is None:
        return "Je n'ai pas acces a Chrome pour ouvrir LinkedIn."

    requete = f"https://www.linkedin.com/search/results/people/?keywords={lead['nom']}"
    try:
        page = navigateur._contexte(browser).new_page()
        page.goto(requete, wait_until="domcontentloaded", timeout=20000)
        page.bring_to_front()
    except Exception as erreur:
        return f"Ouverture de LinkedIn impossible : {erreur}"

    lead_nom = lead["nom"]
    try:
        from core import operator
        operator.journaliser("crm", f"message LinkedIn prepare pour {lead_nom}",
                             brouillon[:200], "pret")
        operator.carte_briefing({
            "client": lead_nom[:40],
            "rdv": "Brouillon LinkedIn",
            "champs": [{"titre": "Message prepare",
                        "valeur": brouillon[:220]}],
        })
    except Exception:  # pragma: no cover
        pass
    return (
        f"LinkedIn est ouvert sur la recherche de {lead_nom}, le brouillon est pret : "
        "verifie le message a l'ecran avant d'envoyer. Je ne clique jamais sur "
        "Envoyer a ta place."
    )


# ======================================================================
# Prospection web type Mistral Work : chercher de nouvelles agences study
# abroad sur le web, les dedoublonner contre le CRM, afficher la carte
# console, puis les ajouter a monday.com APRES confirmation (jamais
# d'ecriture silencieuse — meme doctrine que le reste de la plateforme).
# ======================================================================

_REQUETES_PROSPECTION = (
    "study abroad agency education consultants contact email",
    "overseas education agency international students partnerships",
    "education agent study abroad directory list contact",
)


def _chercher_web_brut(requete: str, max_resultats: int = 6) -> list:
    """Recherche web (meme moteur que tools.web), resultats bruts."""
    try:
        from ddgs import DDGS
    except ImportError:
        try:
            from duckduckgo_search import DDGS
        except ImportError:
            return []
    try:
        with DDGS() as ddgs:
            return list(ddgs.text(requete, region="wt-wt",
                                  max_results=max(1, max_resultats)))
    except Exception:
        LOG.exception("prospection : recherche web impossible")
        return []


def _extraire_agences(resultats: list) -> list:
    """LLM : extrait un JSON structure des agences trouvees.
    Repli : titres + urls des resultats, sans emails."""
    agences = []
    try:
        from core import rapport_work
        elements = [{"titre": r.get("title", ""),
                     "contenu": (r.get("body", "") + " "
                                 + r.get("href", ""))[:1200]}
                    for r in resultats]
        consigne = (
            "Tu es l'assistant prospection de Florian (PhoneBox, eSIM/telecom "
            "etudiants). Voici des resultats de recherche web. Extrait les "
            "AGENCES study abroad / education agents distinctes et renvoie "
            "UNIQUEMENT un tableau JSON (sans texte autour) : "
            '[{"nom": "nom de l agence", "site": "url du site", '
            '"pays": "pays du siege", "email": "email de contact trouve '
            '(vide si absent)", "type": "Study agent"}]\n'
            "Une seule entree par agence. Ignore les universites, les "
            "articles de blog et les annuaires generiques.\n\n"
            + "\n\n".join(f"### RESULTAT {i + 1}\n{e['titre']}\n{e['contenu']}"
                          for i, e in enumerate(elements))
        )
        analyses = rapport_work.analyser(consigne, elements)
        import json as _json
        for a in analyses:
            nom = str(a.get("nom", "")).strip()
            if not nom:
                continue
            agences.append({
                "nom": nom[:120],
                "site": str(a.get("site", "")).strip()[:200],
                "pays": str(a.get("pays", "")).strip()[:60],
                "email": str(a.get("email", "")).strip()[:120],
                "type": str(a.get("type", "Study agent")).strip()[:60],
            })
    except Exception:
        LOG.exception("prospection : extraction LLM impossible")
    if not agences:
        for r in resultats:
            titre = str(r.get("title", "")).strip()
            href = str(r.get("href", "")).strip()
            if titre and href and href.startswith("http"):
                agences.append({
                    "nom": titre[:120], "site": href[:200], "pays": "",
                    "email": "", "type": "Study agent",
                })
    return agences


def _doublons_crm(agences: list) -> tuple:
    """Separe (nouveaux, doublons) : verifie le board monday configure ET
    le pipeline local data/leads.json (noms normalises, sans casse)."""
    existants = set()
    try:
        from tools.monday import _requete, _tableau
        if _tableau():
            donnees, erreurs = _requete(
                """query ($id: [ID!]) { boards(ids: $id) {
                     items_page(limit: 100) { items { name } } } }""",
                {"id": [str(_tableau())]})
            if not erreurs:
                for b in (donnees.get("boards") or []):
                    for it in ((b.get("items_page") or {}).get("items") or []):
                        existants.add(_cle_doublon(it.get("name", "")))
    except Exception:
        LOG.exception("prospection : lecture CRM impossible, dedoublonnage local")
    with _VERROU:
        for l in _charger():
            existants.add(_cle_doublon(l.get("entreprise", "") or l.get("nom", "")))
    nouveaux, doublons = [], []
    for a in agences:
        if _cle_doublon(a["nom"]) in existants:
            doublons.append(a)
        else:
            nouveaux.append(a)
    return nouveaux, doublons


def _cle_doublon(nom: str) -> str:
    from core.util import sans_accents
    return " ".join(re.sub(r"[^a-z0-9]+", " ",
                           sans_accents(str(nom or "").lower())).split())


def _annoncer_prospection(args):
    nb = args.get("nombre", 0)
    tableau = ""
    try:
        from tools.monday import _tableau
        if _tableau():
            tableau = f" dans ton tableau monday { _tableau() }"
    except Exception:
        pass
    return (f"ajouter {nb} nouveau(x) lead(s) study abroad{tableau} "
            f"(creation monday.com)")


@outil(
    nom="prospection_leads",
    description=(
        "Cherche de NOUVELLES agences study abroad sur le web, les "
        "dedoublonne contre ton CRM monday, affiche la carte des leads "
        "trouves dans la console, puis les ajoute a monday.com APRES "
        "confirmation. Pour \u00ab cherche-moi des nouveaux leads study "
        "abroad \u00bb, \u00ab trouve des agences study abroad et ajoute-les "
        "a mon CRM \u00bb, \u00ab de la prospection \u00bb."
    ),
    parametres={
        "type": "object",
        "properties": {
            "nombre": {"type": "integer",
                       "description": "Combien de leads viser (defaut 6, max 10)."}
        },
    },
    lent=True,
    phrase_attente="Je cherche de nouvelles agences study abroad, un instant.",
    confirmation=True,
    annonce=_annoncer_prospection,
    mcp_expose=False,
)
def prospection_leads(nombre: int = 6) -> str:
    """Prospection web type Work : recherche -> extraction LLM -> dedup ->
    carte console -> creation monday EN ATTENTE DE CONFIRMATION."""
    cible = max(1, min(int(nombre or 6), 10))
    resultats = []
    for requete in _REQUETES_PROSPECTION:
        resultats.extend(_chercher_web_brut(requete))
        if len(resultats) >= cible * 3:
            break
    if not resultats:
        return ("La recherche web est indisponible (ddgs absent ou sans "
                "reseau). Relance-moi plus tard.")
    agences = _extraire_agences(resultats)[:cible]
    if not agences:
        return ("Je n'ai pas reussi a identifier de nouvelles agences dans "
                "les resultats. Reformule, ou precise une region.")
    nouveaux, doublons = _doublons_crm(agences)

    # Carte console type Work : nouveaux leads a ajouter, doublons ecartes.
    try:
        from core import rapport_work
        groupes = {
            "reponse": [{"expediteur": a["nom"], "objet": a["type"],
                         "resume": f"{a['pays'] or 'pays inconnu'} — {a['site']}",
                         "action": f"Ajouter au CRM — {a['email'] or 'email a trouver'}",
                         "brouillon": ""} for a in nouveaux],
            "attention": [{"expediteur": d["nom"], "objet": "Doublon",
                           "resume": "Deja present dans ton CRM ou ton pipeline",
                           "action": "Ecarte", "brouillon": ""}
                          for d in doublons[:6]],
            "info": [],
        }
        rapport_work.carte(
            "Prospection study abroad",
            (("reponse", "Nouvelles agences a ajouter", "\U0001F4E9"),
             ("attention", "Deja dans ton CRM", "\U0001F512"),
             ("info", "Pour info", "\U0001F4CA")),
            groupes)
    except Exception:
        LOG.exception("prospection : carte impossible")

    if not nouveaux:
        return (f"Les {len(agences)} agence(s) trouvee(s) sont TOUTES deja "
                "dans ton CRM. Rien a ajouter — le detail est dans la console.")
    # La creation monday passe par la file de confirmation (95/5) :
    # Florian entend la liste et dit oui.
    try:
        from core import registre
        from tools import monday
        objet = registre.get("monday_creer_item")
        if objet is not None and monday._configue():
            for a in nouveaux:
                colonnes = {"text_mm1c1d44": a["email"]} if a["email"] else {}
                registre.mettre_en_attente(objet, {"nom": a["nom"],
                                                    "colonnes": ""})
            premiere = nouveaux[0]["nom"]
            return (f"J'ai trouve {len(nouveaux)} nouvelle(s) agence(s) : "
                    f"{', '.join(a['nom'] for a in nouveaux[:4])}"
                    + ("..." if len(nouveaux) > 4 else "")
                    + f". Je commence par ajouter {premiere} dans monday."
                    f" Tu confirmes ? (les autres suivront, un par un)")
    except Exception:
        LOG.exception("prospection : mise en file monday impossible")
    # monday non configure : tout reste en pipeline local.
    for a in nouveaux:
        ajouter_lead(nom=a["nom"], entreprise=a["nom"],
                     note=f"Prospection web — {a['site']}")
    return (f"J'ai trouve {len(nouveaux)} nouvelle(s) agence(s) : "
            f"{', '.join(a['nom'] for a in nouveaux[:4])}. monday.com n'est "
            "pas configure : je les ai ajoutees a ton pipeline local "
            "(dis-moi quand monday est pret).")


def router_prospection_leads(phrase: str, piece: str = ""):
    """Route deterministe : les formulations de prospection de leads study
    abroad declenchent directement l'outil (sans improvisation du LLM).
    Renvoie (nom_outil, arguments) ou None."""
    from core.util import sans_accents
    p = sans_accents(str(phrase or "").lower())
    if not any(mot in p for mot in ("lead", "agence", "agencies", "agency",
                                   "prospection", "prospect", "partenaire")):
        return None
    if not any(mot in p for mot in ("cherche", "trouve", "cherche-moi",
                                    "trouve-moi", "nouveaux", "nouvelles",
                                    "de la prospection", "genere")):
        return None
    return "prospection_leads", {}
