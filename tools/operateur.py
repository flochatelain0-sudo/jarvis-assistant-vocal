"""AI Operator — boucle executive : synthese chiffree, actions, enchainement.

Doctrine (alignee sur le prompt AI Operator, 1:1) :
- ETAPE 1 : Jarvis resume les evenements recents en points cles chiffres.
- ETAPE 2 : il presente les entites concernees (nom, motif).
- ETAPE 3 : confirmation explicite (voix ou page Operator) AVANT execution.
- ETAPE 4 : apres l'action, la file du registre propose le sujet suivant.

Securite : aucune action n'est executee ici. Les actions proposees passent
par la file de confirmation du registre (registre.mettre_en_attente) — le
feu vert vient TOUJOURS de Florian, en MANUAL comme en AUTO. Les envois
(mail, LinkedIn) restent N3 dans tous les cas.
"""

import logging

from core.registre import outil

LOG = logging.getLogger("jarvis.operateur")

_MAX_ENTITES = 8


def _resume_mails() -> dict:
    """Mails non lus (IMAP UNSEEN) si la boite est configuree."""
    try:
        from tools.mail import _mail_configure, _imap
        if not _mail_configure():
            return {"dispo": False, "non_lus": 0}
        with _imap() as imap:
            statut, donnees = imap.search(None, "UNSEEN")
            if statut != "OK" or not donnees:
                return {"dispo": True, "non_lus": 0}
            return {"dispo": True,
                    "non_lus": len((donnees[0] or b"").split())}
    except Exception:
        LOG.exception("operateur : comptage mails impossible")
        return {"dispo": False, "non_lus": 0}


def _resume_factures() -> dict:
    """Impayes facture.net : l'outil factures_statut gere deja l'ouverture
    du navigateur. Ici on signale seulement que la source est configuree."""
    try:
        from core.config import reglage
        url = str(reglage("factures.url", "") or "").strip()
        return {"dispo": bool(url), "url": bool(url)}
    except Exception:
        return {"dispo": False, "url": False}


def _resume_crm() -> dict:
    """Dossiers CRM a relancer (monday)."""
    try:
        from tools.monday import a_relancer
        relances = a_relancer().get("relances") or []
        return {"dispo": True, "relances": relances}
    except Exception:
        return {"dispo": False, "relances": []}


def _resume_leads() -> dict:
    """Leads a relancer (pipeline data/leads.json, meme regle que
    leads_a_relancer : etat a_relancer, ou brouillon/nouveau jamais relance)."""
    try:
        from tools import leads as module_leads
        with module_leads._VERROU:
            lus = module_leads._charger()
        dues = [l for l in lus if l.get("etat") == "a_relancer"]
        return {"dispo": True, "relances": dues}
    except Exception:
        return {"dispo": False, "relances": []}


def _agreger() -> dict:
    """Toutes les sources en un etat chiffre, lecture seule."""
    return {
        "mails": _resume_mails(),
        "factures": _resume_factures(),
        "crm": _resume_crm(),
        "leads": _resume_leads(),
    }


def _lignes_carte(sources: dict) -> list[dict]:
    """Lignes de la carte recapitulative ({titre, valeur})."""
    lignes = []
    mails = sources["mails"]
    if mails["dispo"]:
        lignes.append({"titre": "Mails", "valeur": f"{mails['non_lus']} non lu(s)"})
    if sources["factures"]["dispo"]:
        lignes.append({"titre": "Factures", "valeur": "statut disponible (facture.net)"})
    crm = sources["crm"]
    if crm["dispo"] and crm["relances"]:
        lignes.append({"titre": "CRM",
                       "valeur": f"{len(crm['relances'])} dossier(s) a relancer"})
    leads = sources["leads"]
    if leads["dispo"] and leads["relances"]:
        lignes.append({"titre": "Leads",
                       "valeur": f"{len(leads['relances'])} prospect(s) a relancer"})
    return lignes


def _premiere_action(sources: dict):
    """(outil, args) de la premiere action proposee, ou None.
    Priorite : leads a relancer. On prepare le brouillon (N1, sans risque) puis
    on met l'ENVOI en file (N3, doctrine : un envoi attend TOUJOURS le feu
    vert). Les relances CRM monday n'ont pas d'outil d'envoi — Jarvis les
    annonce, l'utilisateur decide (fiche, mail prepare manuellement, etc.)."""
    if sources["leads"]["dispo"] and sources["leads"]["relances"]:
        lead = sources["leads"]["relances"][0]
        if lead.get("nom"):
            return "envoyer_message_linkedin", {"nom": lead["nom"]}
    return None


@outil(
    nom="operateur_journee",
    description=(
        "AI Operator : synthese chiffree de l'activite (mails non lus, impayes "
        "facture.net, relances CRM monday, leads LinkedIn a relancer), carte "
        "recapitulative dans la console, premiere action mise en attente de "
        "confirmation, puis enchainement automatique sur le sujet suivant. "
        "Pour « ou j'en suis », « fais le point », « la journee », « statut "
        "de l'entreprise », « brief operateur »."
    ),
    parametres={"type": "object", "properties": {}},
    lent=True,
    phrase_attente="Je fais le point sur ta journee, un instant.",
)
def operateur_journee() -> str:
    """Etape 1 du flux : recapitulatif chiffre + action proposee (en file)."""
    sources = _agreger()
    lignes = _lignes_carte(sources)
    if not lignes:
        return ("Rien a signaler : aucun impaye, aucune relance en attente, "
                "boite mail maitrisee. Qu'est-ce qu'on encha^ine ?")

    try:
        from core import operator
        operator.carte_briefing({"client": "Point du jour", "champs": lignes})
    except Exception:
        pass

    morceaux = [f"Point du jour : {len(lignes)} sujet(s) en attente."]
    for l in lignes:
        morceaux.append(f"{l['titre']} : {l['valeur']}.")
    if sources["crm"]["dispo"] and sources["crm"]["relances"]:
        noms = ", ".join(r.get("nom", "") for r in sources["crm"]["relances"][:4]
                         if r.get("nom"))
        if noms:
            morceaux.append(f"Dossiers CRM qui attendent : {noms}. "
                            "Demande « brief » sur l'un d'eux pour la fiche.")
    if sources["leads"]["dispo"] and sources["leads"]["relances"]:
        noms = ", ".join(l.get("nom", "") for l in sources["leads"]["relances"][:4]
                         if l.get("nom"))
        if noms:
            morceaux.append(f"Prospects a relancer : {noms}.")

    action = _premiere_action(sources)
    if action:
        sujet, args = action
        # Brouillon N1 (sans risque) prepare immediatement, ENVOI N3 en file.
        brouillon = ""
        try:
            from tools.leads import rediger_message_lead
            brouillon = rediger_message_lead(args["nom"], relance=True)
        except Exception:
            LOG.exception("operateur_journee : brouillon lead impossible")
        if brouillon and not brouillon.startswith(("BROUILLON",)):
            morceaux.append(brouillon)
        else:
            morceaux.append(
                f"Brouillon de relance prepare pour {args['nom']} — dis « oui » "
                "pour l'envoi, « non » pour ignorer.")
        _mettre_en_attente(sujet, args)

    return " ".join(morceaux)


def _mettre_en_attente(sujet: str, args: dict) -> None:
    """Range l'action proposee dans la file de confirmation (jamais execute)."""
    try:
        from core import registre
        outil_obj = registre.get(sujet)
        if outil_obj is not None:
            registre.mettre_en_attente(outil_obj, args)
    except Exception:
        LOG.exception("operateur_journee : mise en file impossible pour %s", sujet)
