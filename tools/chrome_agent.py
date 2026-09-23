"""Agent Chrome LinkedIn : arriere-plan (CDP) + controle clavier/souris.

Deux doctrines complementaires, comme le reste de la plateforme :

1. ARRIERE-PLAN (defaut) : Jarvis travaille dans un onglet dedie de TON
   Chrome via le protocole CDP (reutilise tools/navigateur.py, donc tes
   sessions et tes cookies). Il lit la messagerie LinkedIn, redige les
   reponses et les PRE-REMPLIT. Ta souris et ton clavier restent a toi :
   tu continues a travailler normalement pendant qu'il agit.

2. PHYSIQUE (sur demande explicite) : Jarvis peut AUSSI toucher le clavier
   et la souris (core/plateforme.py, tools/souris.py). Pour l'envoi d'un
   message LinkedIn prepare, il passe le clavier physique (Entree) dans la
   fenetre Chrome ramenee au premier plan. Niveau N3 : confirmation vocale
   OBLIGATOIRE, jamais expose au pont distant (mcp_expose=False).

Securite :
  - lire_messages_linkedin est N1 : lecture seule, ne touche a rien ;
  - repondre_messages_linkedin est N3 : pre-remplit sans envoyer ; l'envoi
    clavier physique exige envoyer=true ET la confirmation vocale ;
  - jamais de saisie d'identifiants ; si LinkedIn demande une connexion,
    Jarvis s'arrete et te laisse te connecter toi-meme.
"""
import logging
import time

from core.config import reglage
from core.registre import outil

LOG = logging.getLogger("jarvis.chrome_agent")

_URL_MESSAGERIE = "https://www.linkedin.com/messaging/"
_CHAMP_SAISIE = '.msg-form__contenteditable, div[role="textbox"]'

# Extraction des conversations de la colonne de gauche (robuste aux
# variations du DOM : plusieurs selecteurs LinkedIn tries par fiabilite).
_JS_CONVERSATIONS = """
() => {
  const resultat = [];
  const liens = Array.from(document.querySelectorAll(
      'a[href*="/messaging/thread"], .msg-conversation-card'));
  for (const a of liens) {
    const carte = a.closest('li, .msg-conversation-card') || a;
    const nomEl = carte.querySelector(
        '.msg-conversation-card__participant-names, ' +
        '.msg-entity-lockup__entity-title, h3, h4');
    const extraitEl = carte.querySelector(
        '.msg-conversation-card__message-snippet, ' +
        '.msg-snippet-card__body-snippet, p');
    const badge = carte.querySelector(
        '.msg-conversation-card__unread-count, .msg-conversation-badge');
    const nom = ((nomEl && nomEl.innerText) || a.innerText || '')
        .split('\\n')[0].trim();
    if (!nom) continue;
    const href = (a.href && a.href.indexOf('/messaging/thread') >= 0)
        ? a.href : '';
    if (href && resultat.some(r => r.href === href)) continue;
    resultat.push({
      nom: nom.slice(0, 120),
      extrait: ((extraitEl && extraitEl.innerText) || '').trim().slice(0, 300),
      non_lu: !!badge,
      href: href,
    });
  }
  return resultat.slice(0, 20);
}
"""

# Dernier message de la conversation ouverte + nom de l'interlocuteur.
_JS_DERNIER_MESSAGE = """
() => {
  const corps = Array.from(document.querySelectorAll(
      '.msg-s-event-listitem__body, .msg-s-message-list__event'));
  const dernier = corps[corps.length - 1];
  const nomEl = document.querySelector(
      '.msg-entity-lockup__entity-title, .msg-thread__thread-title, header h2');
  return {
    nom: ((nomEl && nomEl.innerText) || '').trim(),
    message: ((dernier && dernier.innerText) || '').trim(),
  };
}
"""

# Pre-remplit le champ de reponse SANS cliquer sur Envoyer. execCommand
# declenche les evenements React de LinkedIn, ce que fill() ne fait pas
# toujours sur les contenteditable.
_JS_PREPARER_REPONSE = """
(texte) => {
  const champ = document.querySelector('.msg-form__contenteditable, div[role="textbox"]');
  if (!champ) return false;
  champ.focus();
  document.execCommand('insertText', false, texte);
  return champ.innerText.trim().length > 0;
}
"""

# Vrai si le champ est vide (message parti apres envoi).
_JS_CHAMP_VIDE = """
() => {
  const champ = document.querySelector('.msg-form__contenteditable, div[role="textbox"]');
  return !champ || champ.innerText.trim() === '';
}
"""


def _onglet(browser):
    """Onglet LinkedIn existant, sinon un nouvel onglet dedie (arriere-plan)."""
    from tools import navigateur
    for p in navigateur._pages(browser):
        try:
            if "linkedin.com" in (p.url or ""):
                return p
        except Exception:
            continue
    return navigateur._contexte(browser).new_page()


def _connecte(page):
    """Faux si LinkedIn a redirige vers une page de connexion."""
    url = (page.url or "").lower()
    return not any(m in url for m in ("login", "authwall", "signup", "uas/"))


def _lire_conversations(page):
    try:
        brut = page.evaluate(_JS_CONVERSATIONS)
    except Exception:
        LOG.exception("chrome_agent : lecture des conversations impossible")
        return []
    conversations = []
    for c in brut or []:
        if isinstance(c, dict) and c.get("nom"):
            conversations.append(c)
    return conversations


def _ouvrir_messagerie(page):
    """Ouvre la messagerie. Renvoie None si tout va bien, sinon le message."""
    try:
        page.goto(_URL_MESSAGERIE, wait_until="domcontentloaded", timeout=20000)
    except Exception as e:
        return f"Je n'ai pas pu ouvrir ta messagerie LinkedIn ({e})."
    if not _connecte(page):
        return ("LinkedIn demande une connexion : ouvre-la une fois dans Chrome, "
                "je reprendrai ensuite. Je ne saisis jamais tes identifiants.")
    return None


def _generer_reponse(nom: str, message: str) -> str:
    """Reponse LLM courte ; repli deterministe si le LLM est indisponible."""
    from core import llm
    consigne = (
        "Tu es Jarvis, l'assistant personnel de Florian, sur LinkedIn. Redige "
        "une reponse professionnelle, chaleureuse et courte (3 phrases maximum), "
        "en francais. Interlocuteur : " + str(nom or "?") + ". Message recu : \""
        + str(message or "")[:1000] + "\". Renvoie UNIQUEMENT le texte de la "
        "reponse, sans guillemets ni commentaire.")
    try:
        reponse = llm.llm().repondre(consigne, [], [])
        texte = " ".join(
            b.text for b in reponse.blocs
            if getattr(b, "type", "") == "text" and getattr(b, "text", "")
        ).strip()
        if texte:
            return texte[:1500]
    except Exception:
        LOG.exception("chrome_agent : redaction LLM impossible, repli")
    return ("Bonjour " + str(nom or "") + ", merci pour votre message ! Je "
            "prends bonne note de votre demande et je reviens vers vous tres "
            "vite avec une reponse detaillee.")


def _annoncer_reponse(args):
    if args.get("envoyer"):
        return ("Je m'apprete a repondre sur LinkedIn ET a envoyer le message "
                "avec ton clavier. Confirmation obligatoire.")
    return "Je prepare une reponse LinkedIn (pre-remplie, sans envoyer)."


@outil(
    nom="lire_messages_linkedin",
    description=(
        "Lit la messagerie LinkedIn EN ARRIERE-PLAN dans Chrome (onglet dedie, "
        "via CDP) : liste les conversations non lues, extrait le dernier "
        "message de chacune et affiche la carte dans la console. Pour "
        "« lis mes messages LinkedIn », « j'ai des messages non lus ? ». "
        "Lecture seule : ne touche ni la souris ni le clavier, tu peux "
        "continuer a travailler."
    ),
    lent=True,
    phrase_attente="Je lis ta messagerie LinkedIn en arriere-plan.",
)
def lire_messages_linkedin() -> str:
    """N1 : lecture arriere-plan de l'inbox LinkedIn + carte console."""
    from tools import navigateur
    browser = navigateur._connexion()
    if browser is None:
        return navigateur._MSG_ABSENT
    page = _onglet(browser)
    probleme = _ouvrir_messagerie(page)
    if probleme:
        return probleme
    conversations = _lire_conversations(page)
    non_lues = [c for c in conversations if c.get("non_lu")]
    lues = [c for c in conversations if not c.get("non_lu")]
    if not conversations:
        return ("Je ne vois aucune conversation : soit ta messagerie est vide, "
                "soit LinkedIn a change son interface. Ouvre-la une fois dans "
                "Chrome et relance-moi.")

    # Carte console type Work : non lus a traiter, le reste pour info.
    try:
        from core import rapport_work
        rapport_work.carte(
            "Messages LinkedIn",
            (("reponse", "Non lus, a traiter", "\U0001F4E9"),
             ("info", "Conversations a jour", "\U0001F4CA")),
            {
                "reponse": [{"expediteur": c["nom"],
                             "objet": "Message non lu",
                             "resume": c.get("extrait", ""),
                             "action": "Demande « reponds a " + c["nom"][:30]
                                       + " sur LinkedIn » pour preparer la reponse",
                             "brouillon": ""} for c in non_lues[:10]],
                "info": [{"expediteur": c["nom"], "objet": "A jour",
                          "resume": c.get("extrait", ""),
                          "action": "Aucune action", "brouillon": ""}
                         for c in lues[:10]],
            })
    except Exception:
        LOG.exception("chrome_agent : carte impossible")

    try:
        from core import operator
        operator.journaliser("linkedin",
                             f"{len(non_lues)} message(s) non lu(s) sur LinkedIn",
                             ", ".join(c["nom"] for c in non_lues[:8])[:200],
                             "lu")
    except Exception:
        LOG.exception("chrome_agent : journal impossible")

    if not non_lues:
        return ("Aucun message non lu sur LinkedIn : "
                f"{len(lues)} conversation(s) a jour.")
    noms = ", ".join(c["nom"] for c in non_lues[:4])
    return (f"{len(non_lues)} message(s) non lu(s) sur LinkedIn : {noms}"
            + ("..." if len(non_lues) > 4 else "")
            + ". Dis-moi « reponds a " + non_lues[0]["nom"][:30]
            + " sur LinkedIn » et je prepare la reponse.")


@outil(
    nom="repondre_messages_linkedin",
    description=(
        "Prepare une reponse LinkedIn : lit la conversation cible en "
        "ARRIERE-PLAN dans Chrome, redige une reponse courte par IA et la "
        "PRE-REMPLIT dans le champ de saisie. Sans envoyer=true, tu gardes la "
        "main sur l'envoi. Avec envoyer=true, Jarvis prend le controle du "
        "CLAVIER PHYSIQUE (touche Entree) pour envoyer le message. Pour "
        "« reponds a X sur LinkedIn », « reponds a mes messages LinkedIn et "
        "envoie ». Confirmation obligatoire (niveau critique)."
    ),
    parametres={
        "type": "object",
        "properties": {
            "filtre": {"type": "string",
                       "description": "Nom (ou debut de nom) de l'interlocuteur. "
                                      "Vide = premiere conversation non lue."},
            "envoyer": {"type": "boolean",
                        "description": "true = envoyer le message avec le clavier "
                                       "physique apres confirmation. Defaut : "
                                       "pre-remplir seulement."},
        },
    },
    confirmation=True,
    annonce=_annoncer_reponse,
    lent=True,
    phrase_attente="Je prepare ta reponse LinkedIn.",
    mcp_expose=False,
)
def repondre_messages_linkedin(filtre: str = "", envoyer: bool = False) -> str:
    """N3 : pre-remplit la reponse en arriere-plan ; envoi clavier physique
    seulement si l'utilisateur l'a demande ET confirme (95/5)."""
    from core.util import sans_accents
    from tools import navigateur
    browser = navigateur._connexion()
    if browser is None:
        return navigateur._MSG_ABSENT
    page = _onglet(browser)
    probleme = _ouvrir_messagerie(page)
    if probleme:
        return probleme

    conversations = _lire_conversations(page)
    if not conversations:
        return ("Je ne vois aucune conversation : ouvre ta messagerie une fois "
                "dans Chrome et relance-moi.")
    cible = None
    if (filtre or "").strip():
        f = sans_accents(filtre).lower()
        for c in conversations:
            if f in sans_accents(c["nom"]).lower():
                cible = c
                break
        if cible is None:
            return (f"Je ne trouve pas de conversation avec « {filtre} » dans "
                    "ta messagerie LinkedIn.")
    else:
        non_lues = [c for c in conversations if c.get("non_lu")]
        if not non_lues:
            return "Aucune conversation non lue a traiter sur LinkedIn."
        cible = non_lues[0]

    try:
        if cible.get("href"):
            page.goto(cible["href"], wait_until="domcontentloaded", timeout=20000)
        time.sleep(1.5)
        data = page.evaluate(_JS_DERNIER_MESSAGE)
    except Exception as e:
        return f"Je n'ai pas pu ouvrir la conversation de {cible['nom']} ({e})."
    if not (data or {}).get("message"):
        return ("Je n'ai pas reussi a lire le dernier message de "
                f"{cible['nom']} : l'interface a peut-etre change.")
    nom = (data.get("nom") or cible["nom"]).strip()
    reponse = _generer_reponse(nom, data["message"])

    pret = False
    try:
        pret = page.evaluate(_JS_PREPARER_REPONSE, reponse)
    except Exception:
        LOG.exception("chrome_agent : pre-remplissage impossible")
    if not pret:
        return (f"La reponse pour {nom} est prete, mais je n'ai pas trouve le "
                "champ de saisie a l'ecran : ouvre la conversation et relance-moi.")

    try:
        from core import operator
        operator.journaliser("linkedin", f"reponse LinkedIn preparee pour {nom}",
                             reponse[:200], "pret")
        operator.carte_briefing({
            "client": nom[:40],
            "rdv": "Brouillon LinkedIn",
            "champs": [{"titre": "Reponse pre-remplie",
                        "valeur": reponse[:220]}],
        })
    except Exception:  # pragma: no cover
        LOG.exception("chrome_agent : briefing impossible")

    if not envoyer:
        return (f"La reponse pour {nom} est pre-remplie dans Chrome, en "
                "arriere-plan : verifie-la a l'ecran, tu n'as plus qu'a cliquer "
                "sur Envoyer. Je ne clique jamais sur Envoyer sans ton feu "
                "vert.")

    # Envoi : prise de controle du CLAVIER PHYSIQUE. La confirmation N3 a
    # deja ete donnee a ce stade ; on ramene l'onglet au premier plan puis
    # on appuie sur Entree comme si l'utilisateur le faisait.
    from core import plateforme
    try:
        page.bring_to_front()
        page.evaluate("() => { const c = document.querySelector('"
                      + _CHAMP_SAISIE + "'); if (c) c.focus(); }")
        if not plateforme.envoyer_touches("return"):
            return (f"La reponse pour {nom} est pre-remplie, mais je n'ai pas "
                    "reussi a utiliser le clavier (autorisation Accessibilite "
                    "requis sur macOS). Verifie et envoie manuellement.")
        time.sleep(2)
        parti = page.evaluate(_JS_CHAMP_VIDE)
    except Exception as e:
        return (f"La reponse pour {nom} est pre-remplie, mais l'envoi a echoue "
                f"({e}). Verifie a l'ecran et envoie manuellement.")
    if parti:
        try:
            from core import operator
            operator.journaliser("linkedin", f"reponse envoyee a {nom}",
                                 reponse[:200], "envoye")
        except Exception:  # pragma: no cover
            pass
        return (f"Message envoye a {nom} (touche Entree, clavier physique). "
                "Tu peux verifier dans l'historique de la conversation.")
    return (f"Je ne suis pas sur que le message pour {nom} soit parti : "
            "verifie la conversation a l'ecran avant de relancer.")


def router_agent_linkedin(phrase: str, piece: str = ""):
    """Route deterministe : les demandes LinkedIn messaging declenchent
    l'agent Chrome sans improvisation du LLM. Renvoie (nom_outil, arguments)
    ou None."""
    from core.util import sans_accents
    p = sans_accents(str(phrase or "").lower())
    if "linkedin" not in p:
        return None
    if any(mot in p for mot in ("repond", "relance ", "reponds lui")):
        return "repondre_messages_linkedin", {}
    if any(mot in p for mot in ("message", "messagerie", "inbox", "non lu",
                               "notifications")):
        return "lire_messages_linkedin", {}
    return None
