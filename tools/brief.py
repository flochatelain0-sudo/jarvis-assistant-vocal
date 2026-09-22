"""Brief : heure + meteo + apercu des derniers mails, en un seul outil."""
from core.registre import outil
from tools.mail import _mail_configure, lire_mails
from tools.meteo import meteo
from tools.temps import heure_et_date


@outil(
    nom="faire_brief",
    description="Fait un brief : l'heure, la meteo et un apercu des derniers mails. "
                "A utiliser quand l'utilisateur dit 'fais-moi un brief', 'quoi de "
                "neuf', 'ma journee'. Apres le brief, propose de lire, repondre ou "
                "jeter un mail.",
    lent=True,
    phrase_attente="D'accord, je te prepare ton brief, un instant.",
)
def faire_brief() -> str:
    """Brief du moment : heure, meteo, deadlines Loopstr et apercu des nouveaux mails."""
    morceaux = [heure_et_date(), meteo()]
    try:
        from tools.loopstr import deadlines_brief
        deadlines = deadlines_brief()
        if deadlines:
            morceaux.append(deadlines)
    except Exception:
        pass
    try:
        from tools.suivi import contenus_du_brief
        retard = contenus_du_brief()
        if retard:
            morceaux.append(retard)
    except Exception:
        pass
    if _mail_configure():
        morceaux.append(lire_mails(5))
    planning = _planning_bref()
    if planning:
        morceaux.append(planning)
    relances = _relances_bref()
    if relances:
        morceaux.append(relances)
    return " ".join(morceaux)


def _planning_bref():
    """Le planning du jour en une phrase, pour le brief. "" si agenda
    indisponible ou vide : le brief ne doit jamais planter."""
    try:
        from tools.agenda import planning_du_jour
        p = planning_du_jour()
        evs = [e for e in p.get("evenements", [])
               if not e.get("tout_jour") and e.get("titre")]
        if not evs:
            return ""
        morceaux = [f"{e['heure']} {e['titre']}".strip() for e in evs[:5]]
        return "Dans ton agenda aujourd'hui : " + " ; ".join(morceaux) + "."
    except Exception:
        return ""


def _relances_bref():
    """Les dossiers a relancer (statuts d'attente monday) en une phrase."""
    try:
        from tools.monday import a_relancer
        r = a_relancer().get("relances") or []
        if not r:
            return ""
        noms = [x.get("nom", "") for x in r[:4] if x.get("nom")]
        return (f"{len(r)} dossier(s) CRM attendent une relance : "
                + ", ".join(noms) + ".")
    except Exception:
        return ""
