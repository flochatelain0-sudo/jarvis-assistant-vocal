"""Factures (facture.net) — LECTURE SEULE via ton profil Chrome dédié (ChromeJarvis).

Jarvis ouvre ton tableau de bord facture.net (déjà connecté dans ChromeJarvis) et
te le RÉSUME à voix haute : factures impayées, montants dus, relances. Il n'agit
JAMAIS (aucune création/modif/envoi). Session expirée -> il te le dit clairement,
pas d'échec silencieux.

SÉCURITÉ (doctrine règle 2 : credentials/sessions côté Jarvis uniquement) :
  - mcp_expose=False : données financières, JAMAIS exposées à Hermes ni au pont.
  - Montants et noms de clients ne sont PAS écrits dans les logs (contenu sensible).
  - Ajoute facture.net à navigateur.domaines_proteges pour verrouiller le "lecture
    seule" même si un jour un autre outil tentait d'y agir.

Config : factures.url = l'URL de ton tableau de bord (copiée depuis ChromeJarvis
une fois connecté). Voir aussi docs/navigateur.md pour le profil dédié.
"""
from core.config import reglage
from core.registre import outil

# Indices qu'on est retombé sur une page de connexion (session expirée).
_INDICES_LOGIN = ("mot de passe", "se connecter", "connexion", "identifiant",
                  "s'identifier", "login", "sign in", "password")


@outil(
    nom="factures_statut",
    description="Lit ton tableau de bord facture.net et résume ta facturation : "
                "factures IMPAYÉES, montants dus, relances à faire. LECTURE SEULE, "
                "aucune action. Pour « où j'en suis sur mes factures », « mes "
                "impayés », « qui me doit de l'argent », « statut facturation ».",
    parametres={"type": "object", "properties": {}},
    lent=True,
    phrase_attente="Je regarde tes factures, un instant.",
    mcp_expose=False,
)
def factures_statut() -> str:
    url = (reglage("factures.url", "") or "").strip()
    if not url:
        return ("Je ne sais pas où est ton tableau de bord facture.net. Renseigne "
                "factures.url dans config.yaml (l'URL de ta page, une fois connecté "
                "dans le profil Chrome « ChromeJarvis »).")

    from tools.navigateur import _connexion, _contexte
    browser = _connexion()
    if browser is None:
        return ("Chrome n'est pas joignable. Lance « Chrome + Jarvis » (profil "
                "ChromeJarvis) puis redemande-moi.")

    page = None
    try:
        page = _contexte(browser).new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=20000)
        page.wait_for_timeout(1800)                 # laisser le tableau de bord (JS) se remplir
        texte = (page.inner_text("body") or "").strip()
        url_finale = (page.url or "").lower()
    except Exception as e:
        return f"Je n'ai pas pu ouvrir facture.net ({str(e)[:80]})."
    finally:
        try:
            if page:
                page.close()
        except Exception:
            pass

    bas = texte.lower()
    # Session expirée : redirigé vers une page de connexion, ou page courte de login.
    if any(x in url_finale for x in ("login", "connexion", "signin", "sign-in")) or \
            (len(texte) < 500 and any(m in bas for m in _INDICES_LOGIN)):
        return ("Ta session facture.net a expiré. Reconnecte-toi UNE fois dans le "
                "profil Chrome « ChromeJarvis » (lance « Chrome + Jarvis »), puis "
                "redemande-moi le statut de tes factures.")
    if len(texte) < 40:
        return "Le tableau de bord facture.net semble vide ou n'a pas chargé — réessaie."

    # Rapport type Work : analyse LLM du contenu REEL, carte groupee dans la
    # console et resume vocal fidele (nombres et montants exacts).
    # NB : contenu financier sensible -> volontairement PAS logge ici.
    from core import rapport_work
    elements = [{"titre": "Tableau de bord facture.net",
                 "contenu": texte[:3500]}]
    consigne = rapport_work.consigne_analyse(
        "Statut facturation", elements,
        "A TRAITER = facture impayee a relancer par Florian ; ATTENTION = "
        "echeance depassee, montant important ou anomalie ; INFO = le reste "
        "(factures payees, brouillons, menus). Ignore les menus et le pied "
        "de page.",
        demande_brouillon=False)
    analyses = rapport_work.groupes_analyses(consigne, elements,
                                              replis={0: "attention"})
    a = analyses.get(0) or {}
    resume = a.get("resume") or texte[:300]
    action = a.get("action") or ""
    groupes = {"reponse": [], "attention": [], "info": []}
    groupe = (a.get("repli") or
              rapport_work.normaliser_groupe(a.get("groupe", ""), "attention"))
    groupes[groupe].append({
        "expediteur": "facture.net", "objet": "Statut facturation",
        "resume": resume, "action": action, "brouillon": ""})
    rapport_work.carte(
        "Statut de tes factures",
        (("reponse", "Relances a faire", "\U0001F4E9"),
         ("attention", "A verifier", "\U0001F512"),
         ("info", "Pour info", "\U0001F4CA")),
        groupes)
    total = (resume + " " + action).strip()
    return (total + " Le detail est affiche dans la console.") if total \
        else "Voici le tableau de bord facture.net."
