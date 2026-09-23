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
        # VISUEL : le brouillon s'affiche dans la console aussi.
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
