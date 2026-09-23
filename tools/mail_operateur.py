"""AI Email Operator — tri de la boite, brouillons, validation, enchainement.

Workflow (adaptation du prompt AI Email Operator, doctrine N3 respectee) :
- ETAPE 1 : scan reel de la boite (IMAP), categorisation en trois classes,
  rapport chiffre des stats et des actions preparees en arriere-plan.
- ETAPE 2 : presentation des mails restants un par un : enjeu en une phrase,
  brouillon de reponse prerédige.
- ETAPE 3 : la voix (ou la page Operator) confirme, modifie (consigne libre)
  ou annule. Ajustement immediat du brouillon, puis confirmation finale.
- ETAPE 4 : enchainement automatique sur le mail suivant, bilan final avec
  temps estime gagne.

DOCTRINE : un ENVOI et une SUPPRESSION sont TOUJOURS N3 (voir core/registre).
Rien n'est jete ni envoye ici : les actions passent par la file de
confirmation du registre. Le feu vert vient TOUJOURS de Florian, en MANUAL
comme en AUTO. « Traité automatiquement » signifie : brouillon pret ET en
file d'envoi, pas d'envoi silencieux.
"""

import logging

from core.registre import outil

LOG = logging.getLogger("jarvis.mail_operateur")

_NOMBRE_DEFAUT = 15
_MINUTES_PAR_MAIL = 2     # temps estime gagne par mail traite (bilan final)
_MAX_CARTE = 12           # mails affiches dans la carte console

# Sujets typiques d'un mail a reponse simple/factuelle : confirmation,
# acces, notification, livraison... Le reste (hors pub) est « a valider ».
_MOTS_REPONSE_SIMPLE = ("confirmation", "confirme", "acces", "reinitialisation",
                        "mot de passe", "livraison", "commande", "bienvenue",
                        "inscription", "notification", "paiement", "facture")

# File interne : mails restants a presenter, dans l'ordre.
_RESTANTS = []
_TRAITES = {"spam": 0, "auto": 0, "valides": 0}


def _entetes(nombre: int = _NOMBRE_DEFAUT):
    """Scan reel de la boite : derniers mails, expediteur, objet, etiquette
    pub/spam. Alimente AUSSI l'etat de tools.mail (_DERNIERS_MAILS,
    _ETIQUETTES) pour que mettre_a_la_corbeille / vider_poubelle agissent
    sur la meme liste. Renvoie None si la messagerie n'est pas configuree."""
    from email.utils import parseaddr
    from tools import mail as m
    if not m._mail_configure():
        return None
    try:
        imap = m._imap()
        imap.select("INBOX")
        _, donnees = imap.uid("search", None, "ALL")
        ids = donnees[0].split()
        derniers = ids[-max(1, int(nombre)):][::-1]
        m._DERNIERS_MAILS.clear()
        m._DERNIERS_MAILS.extend(derniers)
        m._ETIQUETTES.clear()
        resultats = []
        for i, num in enumerate(derniers, 1):
            _, d = imap.uid("fetch", num,
                            "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT)])")
            entete = d[0][1].decode("utf-8", "replace") if d and d[0] else ""
            exp, sujet = "", ""
            for ligne in entete.splitlines():
                bas = ligne.lower()
                if bas.startswith("from:"):
                    exp = m._decoder_entete(ligne[5:].strip())
                elif bas.startswith("subject:"):
                    sujet = m._decoder_entete(ligne[8:].strip())
            nom, adresse = parseaddr(exp)
            etiquette = m._etiqueter_spam(adresse or exp, sujet)
            if etiquette:
                m._ETIQUETTES[num] = etiquette
            resultats.append({
                "numero": i, "uid": num,
                "nom": nom or adresse or exp, "adresse": adresse,
                "sujet": sujet, "spam": bool(etiquette),
            })
        imap.logout()
        return resultats
    except Exception:
        LOG.exception("mail_operateur : scan IMAP impossible")
        return None


def _sans_accent(texte: str) -> str:
    table = str.maketrans("àâäéèêëîïôöùûüç", "aaaeeeeiioouuuc")
    return str(texte or "").lower().translate(table)


def _est_reponse_simple(entete: dict) -> bool:
    """Mail repondable par une reponse factuelle simple."""
    sujet = _sans_accent(entete.get("sujet"))
    return any(mot in sujet for mot in _MOTS_REPONSE_SIMPLE)


def _categoriser(entetes: list) -> tuple:
    """Trois categories : (pub/spam, reponse simple, a valider)."""
    spam = [e for e in entetes if e.get("spam")]
    uids_spam = {e["uid"] for e in spam}
    simples, valider = [], []
    for e in entetes:
        if e["uid"] in uids_spam:
            continue
        e["categorie"] = "auto" if _est_reponse_simple(e) else "valider"
        (simples if e["categorie"] == "auto" else valider).append(e)
    return spam, simples, valider


def _rediger_reponse(entete: dict, contexte: str) -> str:
    """Brouillon de reponse genere par le LLM a partir du VRAI mail."""
    try:
        from core import llm
        consigne = (
            "Redige une reponse courte et professionnelle, en francais, a ce "
            "mail. Trois phrases maximum, factuelle, basee UNIQUEMENT sur les "
            "informations du mail original (n'invente ni creneau, ni prix, ni "
            "donnee absente). Termine par une formule de politesse.\n\n"
            + str(contexte or "")
        )
        reponse = llm.llm().repondre(consigne, [], [])
        return " ".join(
            b.text for b in reponse.blocs
            if getattr(b, "type", "") == "text" and getattr(b, "text", "")
        ).strip()
    except Exception:
        LOG.exception("mail_operateur : redaction impossible")
        return ""


def _reviser(corps: str, consigne: str) -> str:
    """Reecrit le brouillon selon la consigne libre de l'utilisateur."""
    try:
        from core import llm
        demande = (
            f"Modifie ce brouillon de mail selon cette consigne : « {consigne} ». "
            "Renvoie UNIQUEMENT le nouveau texte du mail, sans commentaire.\n\n"
            + str(corps or "")
        )
        reponse = llm.llm().repondre(demande, [], [])
        return " ".join(
            b.text for b in reponse.blocs
            if getattr(b, "type", "") == "text" and getattr(b, "text", "")
        ).strip()
    except Exception:
        LOG.exception("mail_operateur : revision impossible")
        return ""


def _mettre_en_attente(nom_outil: str, args: dict) -> None:
    """Range une action (corbeille, envoi) dans la file de confirmation.
    Jamais executee ici : N3, le feu vert vient de la voix ou de la page."""
    try:
        from core import registre
        objet = registre.get(nom_outil)
        if objet is not None:
            registre.mettre_en_attente(objet, args)
    except Exception:
        LOG.exception("mail_operateur : mise en file impossible (%s)", nom_outil)


def _carte_mail(e, brouillon):
    """Carte pour UN mail presente : qui, sujet, brouillon propose.
    Jamais d'exception : le visuel ne casse pas le vocal."""
    try:
        from core import operator
        operator.carte_briefing({
            "client": (e.get("nom") or "contact")[:30],
            "rdv": (e.get("sujet") or "sans objet")[:70],
            "champs": [{"titre": "Reponse proposee",
                        "valeur": str(brouillon or "")[:220]}],
        })
    except Exception:
        pass


def _traiter_suivant() -> str:
    """Presente le mail suivant de la file : enjeu + brouillon + envoi N3 en
    file. Bilan final quand la file est vide."""
    if not _RESTANTS:
        total = _TRAITES["spam"] + _TRAITES["auto"] + _TRAITES["valides"]
        minutes = total * _MINUTES_PAR_MAIL
        _carte_mail({"nom": "Bilan final",
                     "sujet": f"{total} mail(s) gere(s) — {minutes} min gagnees"},
                    "")
        return (f"Tout est traite ! {total} mail(s) gere(s) ce matin, tu viens "
                f"de gagner environ {minutes} minutes. Bonne journee !")
    from tools import mail as m
    e = _RESTANTS.pop(0)
    nom = e.get("nom") or "un contact"
    sujet = e.get("sujet") or "sans objet"
    # Lecture REELLE du mail complet pour fonder le brouillon.
    try:
        contenu = m.lire_mail(e["numero"])
    except Exception:
        contenu = f"Mail de {nom}, objet {sujet}."
    brouillon = _rediger_reponse(e, contenu)
    if brouillon:
        objet = sujet if sujet.lower().startswith("re:") else "Re: " + sujet
        if e.get("adresse"):
            m.preparer_mail(e["adresse"], objet, brouillon)
        if e.get("categorie") == "auto":
            _TRAITES["auto"] += 1
            intro = (f"Mail simple traite pour toi : {nom} te demande "
                     f"« {sujet} ».")
        else:
            _TRAITES["valides"] += 1
            intro = (f"Il reste un mail qui attend ton avis : {nom} te demande "
                     f"« {sujet} ».")
        _mettre_en_attente("envoyer_mail", {})
        _carte_mail(e, brouillon)
        return (intro
                + f" Reponse proposee : {brouillon}"
                + " Dis « oui » pour confirmer l'envoi, ou dis-moi ce qu'il "
                  "faut modifier (heure, ton, contenu).")
    return (f"Je n'ai pas reussi a preparer la reponse pour {nom} "
            f"(« {sujet} »). Traite-le manuellement ou relance-moi.")


# Sujets de mails d'alerte securite : a verifier en priorite.
_MOTS_SECURITE = ("security alert", "reset your password", "password reset",
                  "confirmation code", "verification code", "sign-in",
                  "new sign in", "security warning", "suspicious")

# Expediteurs systemes : notification sans action attendue.
_EXPEDITEURS_SYSTEME = ("no-reply", "noreply", "donotreply", "notification",
                        "postmaster", "mailer-daemon")


def _est_securite(entete: dict) -> bool:
    sujet = _sans_accent(entete.get("sujet"))
    return any(mot in sujet for mot in _MOTS_SECURITE)


def _est_systeme(entete: dict) -> bool:
    adresse = _sans_accent(entete.get("adresse") or "")
    sujet = _sans_accent(entete.get("sujet"))
    if any(mot in adresse for mot in _EXPEDITEURS_SYSTEME):
        return not _est_securite(entete)
    return any(mot in sujet for mot in ("survey", "sondage"))


def _categoriser_rendu(entetes: list) -> dict:
    """Quatre familles pour le compte rendu affiche : securite, reponse
    attendue, interne, notifications. Les pubs/spams deja etiquetees sont
    ecartees du rendu (elles restent gerables via vider_poubelle)."""
    familles = {"securite": [], "attente": [], "interne": [], "notifs": []}
    try:
        from core.config import reglage
        domaine = str(reglage("mail.adresse", "") or "").split("@")[-1].lower()
    except Exception:
        domaine = ""
    for e in entetes:
        if e.get("spam"):
            continue
        if _est_securite(e):
            familles["securite"].append(e)
            continue
        if _est_systeme(e):
            familles["notifs"].append(e)
            continue
        adresse = _sans_accent(e.get("adresse") or "")
        if domaine and adresse.endswith("@" + domaine):
            familles["interne"].append(e)
        else:
            familles["attente"].append(e)
    return familles


def _carte_compte_rendu(familles: dict) -> None:
    """Injecte la carte du compte rendu dans la console (core.operator),
    sans jamais faire echouer le compte rendu vocal si la page est fermee."""
    try:
        from core import operator
        correspondances = {
            "securite": ("A verifier en priorite - securite", "\U0001F512"),
            "attente": ("En attente de ta reponse", "\U0001F465"),
            "interne": ("Interne - " + domaine_entreprise(), "\U0001F3E2"),
            "notifs": ("Notifications", "\U0001F4E9"),
        }
        categories = []
        for cle, (titre, icone) in correspondances.items():
            mails = familles.get(cle) or []
            if not mails:
                continue
            categories.append({
                "titre": titre,
                "icone": icone,
                "mails": [{
                    "expediteur": m.get("nom") or "un contact",
                    "objet": m.get("sujet") or "sans objet",
                    "detail": "",
                    "action": "Verification conseillee" if cle == "securite"
                              else "Reponse attendue" if cle == "attente"
                              else "Information" if cle == "interne"
                              else "Sans action",
                } for m in mails],
            })
        operator.carte_mails({
            "titre": "Compte rendu de tes mails",
            "categories": categories,
        })
    except Exception:
        LOG.exception("mail_operateur : injection carte mails impossible")


# ------------------------------------------------------------------
# Compte rendu intelligent (style Mistral Work) : lecture des CORPS des
# mails, analyse LLM groupee, resumes fideles au contenu reel et
# brouillons de reponse proposes. Doctrine N3 intacte : rien n'est envoye
# sans confirmation explicite de Florian.

_MAX_CORPS = 2500          # caracteres du corps transmis au LLM par mail
_MAILS_PAR_LOT = 6          # mails analyses par appel LLM
_MAX_BROUILLOTS = 3         # brouillons prepares par compte rendu

_GROUPE_REPONSE = ("A REPONDRE", "reponse", "repondre")
_GROUPE_ATTENTION = ("ATTENTION", "attention", "verifier", "a verifier")
_GROUPE_INFO = ("INFO", "info", "information", "pour info", "fyi")


def _lire_corps(uid) -> str:
    """Corps texte d'un mail par son UID (BODY.PEEK : ne marque pas lu).
    Renvoie "" en cas d'echec : le compte rendu ne plante jamais."""
    from tools import mail as m
    try:
        import email as _email
        imap = m._imap()
        imap.select("INBOX")
        _, d = imap.uid("fetch", uid, "(BODY.PEEK[])")
        brut = d[0][1] if d and d[0] else b""
        imap.logout()
        message = _email.message_from_bytes(brut)
        return m._corps_texte(message).strip()
    except Exception:
        LOG.exception("mail_operateur : lecture du corps impossible")
        return ""


def _analyser_lot(entetes: list) -> list:
    """Analyse LLM d'un lot de mails : renvoie pour chaque mail un dict
    {indice, groupe, resume, action, brouillon} bases sur le VRAI contenu.
    Repli deterministe si le LLM est indisponible ou renvoie un JSON invalide.
    """
    from core import llm as _llm
    lignes = []
    for i, e in enumerate(entetes):
        corps = e.get("corps") or ""
        if len(corps) > _MAX_CORPS:
            corps = corps[:_MAX_CORPS]
        lignes.append(
            f"### MAIL {i + 1}\nDe: {e.get('nom')} <{e.get('adresse')}>")
        lignes.append(f"Objet: {e.get('sujet')}\n{corps}")
    modele_json = (
        '{"indice": <numero du mail>, "groupe": "A REPONDRE | ATTENTION | INFO", '
        '"resume": "1-2 phrases fideles au contenu reel du mail, en francais, '
        'avec les noms, dates et montants exacts", "action": "l action concrete a '
        'faire (ou Aucune action)", "brouillon": "une reponse en francais prete a '
        'envoyer si groupe=A REPONDRE, sinon chaine vide"}'
    )
    consigne = (
        "Tu es l'assistant email de Florian. Analyse ces mails et renvoie "
        "UNIQUEMENT un tableau JSON (sans texte autour, sans bloc de code) "
        "avec un objet par mail, dans l'ordre, selon ce modele :\n"
        + modele_json + "\n\n"
        "Regles de groupe : A REPONDRE = quelqu'un attend une reponse de "
        "Florian ; ATTENTION = securite, facture impayee, echec d'envoi ou "
        "information demandant une verification ; INFO = le reste "
        "(confirmations, rapports internes, newsletters utiles).\n\n"
        + "\n\n".join(lignes)
    )
    try:
        reponse = _llm.llm().repondre(consigne, [], [])
        brut = " ".join(
            b.text for b in reponse.blocs
            if getattr(b, "type", "") == "text" and getattr(b, "text", "")
        ).strip()
        import json as _json
        debut, fin = brut.find("["), brut.rfind("]")
        if debut >= 0 and fin > debut:
            analyses = _json.loads(brut[debut:fin + 1])
            if isinstance(analyses, list):
                return [a for a in analyses if isinstance(a, dict)]
    except Exception:
        LOG.exception("mail_operateur : analyse LLM impossible, repli")
    # Repli : liste vide -> le compte rendu retombe sur les familles
    # deterministes locales (_categoriser_rendu).
    return []


def _groupe_depuis_texte(groupe: str, entete: dict) -> str:
    """Groupe final d'un mail : l'avis du LLM, corrige par les regles
    deterministes de securite (jamais de mail sensible en INFO)."""
    g = _sans_accent(str(groupe or ""))
    if _est_securite(entete):
        return "attention"
    if any(mot in g for mot in _GROUPE_ATTENTION):
        return "attention"
    if any(mot in g for mot in _GROUPE_REPONSE):
        return "reponse"
    if any(mot in g for mot in _GROUPE_INFO):
        return "info"
    return "info"


def _consolider_groupe(groupe: str, entete: dict) -> str:
    """Affine le groupe avec les heuristiques locales : interne / notif."""
    if _est_securite(entete):
        return "attention"
    if groupe == "reponse":
        return "reponse"
    if _est_systeme(entete):
        return "info"
    return groupe or "info"


def router_compte_rendu_mails(phrase: str):
    """Route deterministe : les formulations de compte rendu mail declenchent
    directement l'outil, sans passer par le LLM (qui improvise parfois une
    reponse sans appeler l'outil -> ni carte ni action dans la console).
    Renvoie (nom_outil, arguments) ou None."""
    p = _sans_accent(phrase)
    if not any(mot in p for mot in ("mail", "email", "courriel", "boite")):
        return None
    intentions_rendu = (
        "compte rendu", "compte-rendu", "recap", "resume", "resume moi",
        "quels mails", "quels email", "qu est ce que j ai recu",
        "qu ai je recu", "mes mails du jour", "mes mails d aujourd hui",
        "j ai quoi comme mail", "j ai recu quoi",
    )
    intentions_tri = (
        "traite mes mails", "fais le tri", "trie mes mails",
        "fais le tri de ma boite", "mes mails du matin", "ou j en suis sur mes mails",
    )
    if any(mot in p for mot in intentions_tri):
        return "operateur_mails", {}
    if any(mot in p for mot in ("lire", "lis mes", "j ai quoi")):
        return "lire_mails", {}
    if any(mot in p for mot in intentions_rendu):
        return "compte_rendu_mails", {}
    return None


def domaine_entreprise() -> str:
    try:
        from core.config import reglage
        return str(reglage("mail.adresse", "") or "").split("@")[-1] or "entreprise"
    except Exception:
        return "entreprise"


@outil(
    nom="compte_rendu_mails",
    description=(
        "Compte rendu intelligent des derniers mails recus : lit les CORPS "
        "des mails, les regroupe (a te repondre / a verifier / pour info), "
        "resume chaque mail fidelement a son contenu reel et PREPARE des "
        "brouillons de reponse (jamais envoyes sans confirmation). AFFICHE "
        "le detail dans la console ET resume a voix haute. Pour \u00ab compte "
        "rendu de mes mails \u00bb, \u00ab quels mails j'ai recu \u00bb, \u00ab resume mes mails "
        "\u00bb, \u00ab recap de mes mails \u00bb."
    ),
    parametres={
        "type": "object",
        "properties": {
            "nombre": {"type": "integer",
                       "description": "Combien de mails scanner (20 par defaut)."}
        },
    },
    lent=True,
    phrase_attente="Je lis tes mails et je prepare le compte rendu, un instant.",
)
def compte_rendu_mails(nombre: int = 20) -> str:
    """Compte rendu type Mistral Work : groupes + resumes fideles aux
    CORPS reels + brouillons proposes, affiche dans la console et resume
    a voix haute. Doctrine N3 : aucun envoi sans confirmation."""
    entetes = _entetes(max(1, min(int(nombre or 20), 50)))
    if entetes is None:
        return ("La messagerie n'est pas configuree ou injoignable. "
                "Renseigne la section mail de config.yaml.")
    if not entetes:
        return "Ta boite de reception est vide. Rien a signaler."
    entetes = [e for e in entetes if not e.get("spam")]
    if not entetes:
        return ("Rien a signaler : uniquement de la pub ou du spam, ecartes "
                "du compte rendu. Dis \u00ab vide la poubelle \u00bb pour les jeter.")

    # 1) Lecture des corps (reelle) pour fonder les resumes.
    for e in entetes:
        e["corps"] = _lire_corps(e["uid"])

    # 2) Analyse LLM par lots, avec repli deterministe (familles locales).
    analyses = {}
    for debut in range(0, len(entetes), _MAILS_PAR_LOT):
        lot = entetes[debut:debut + _MAILS_PAR_LOT]
        for a in _analyser_lot(lot):
            try:
                indice = int(a.get("indice", 0))
            except (TypeError, ValueError):
                continue
            if 1 <= indice <= len(lot):
                analyses[debut + indice - 1] = a

    # Repli : familles deterministes pour les mails sans analyse LLM.
    familles = _categoriser_rendu(entetes)
    _GROUPE_DEFAUT = {"securite": "attention", "attente": "reponse",
                      "interne": "info", "notifs": "info"}
    defauts = {}
    for cle, groupe in _GROUPE_DEFAUT.items():
        for e in familles.get(cle) or []:
            defauts[e["uid"]] = groupe

    groupes = {"reponse": [], "attention": [], "info": []}
    for i, e in enumerate(entetes):
        a = analyses.get(i) or {}
        if a:
            groupe = _consolider_groupe(
                _groupe_depuis_texte(a.get("groupe", ""), e), e)
        else:
            groupe = defauts.get(e["uid"], "info")
        e["resume"] = str(a.get("resume", "")).strip()[:400]
        e["action"] = str(a.get("action", "")).strip()[:200]
        e["brouillon"] = str(a.get("brouillon", "")).strip()
        groupes[groupe].append(e)

    # 3) Brouillons proposes : le PREMIER mail a repondre part en file N3,
    # les autres restent consultables dans la carte.
    brouillons_prete = []
    for e in groupes["reponse"]:
        if not e.get("brouillon") or not e.get("adresse"):
            continue
        brouillons_prete.append(e)
        if len(brouillons_prete) >= _MAX_BROUILLOTS:
            break
    if brouillons_prete:
        from tools import mail as m
        premier = brouillons_prete[0]
        sujet = premier.get("sujet") or ""
        objet = sujet if sujet.lower().startswith("re:") else "Re: " + sujet
        m.preparer_mail(premier["adresse"], objet, premier["brouillon"])

    # 4) Carte console detaillee : 3 groupes, resumes fideles, actions et
    # brouillons visibles. Jamais d'exception : le vocal continue.
    try:
        from core import operator
        correspondances = (
            ("reponse", "A te repondre", "\U0001F4E9"),
            ("attention", "A verifier en priorite", "\U0001F512"),
            ("info", "Pour info - sans action", "\U0001F4CA"),
        )
        categories = []
        for cle, titre, icone in correspondances:
            mails = groupes.get(cle) or []
            if not mails:
                continue
            categories.append({
                "titre": titre,
                "icone": icone,
                "mails": [{
                    "expediteur": e.get("nom") or "un contact",
                    "objet": e.get("sujet") or "sans objet",
                    "detail": e.get("resume")
                              or (e.get("corps") or "")[:200],
                    "action": e.get("action")
                              or ("Reponse attendue" if cle == "reponse"
                                  else "Verification conseillee" if cle == "attention"
                                  else "Aucune action"),
                    "brouillon": e.get("brouillon") or "",
                } for e in mails[:10]],
            })
        operator.carte_mails({
            "titre": "Compte rendu de tes mails",
            "categories": categories,
        })
    except Exception:
        LOG.exception("mail_operateur : injection carte mails impossible")

    # 5) Resume vocal : groupes + points clus + premiere action.
    total = sum(len(v) for v in groupes.values())
    morceaux = [f"Compte rendu de tes mails : {total} mail(s) a signaler."]
    if groupes["reponse"]:
        noms = ", ".join(
            (e.get("nom") or "un contact") for e in groupes["reponse"][:3])
        morceaux.append(
            f"{len(groupes['reponse'])} mail(s) attendent ta reponse : {noms}.")
        if brouillons_prete:
            morceaux.append(
                f"J'ai prepare un brouillon pour {brouillons_prete[0].get('nom')}, "
                "dis \u00ab envoie \u00bb pour le valider.")
    if groupes["attention"]:
        noms = ", ".join(
            (e.get("nom") or "un contact") for e in groupes["attention"][:3])
        morceaux.append(
            f"{len(groupes['attention'])} point(s) a verifier : {noms}.")
    if groupes["info"]:
        morceaux.append(
            f"Et {len(groupes['info'])} mail(s) d'information sans action.")
    morceaux.append("Le detail et les brouillons sont affiches dans la console.")
    return " ".join(morceaux)


@outil(
    nom="operateur_mails",
    description=(
        "AI Email Operator : scan la boite de reception, categorise les mails "
        "(pub/spam a jeter, reponses simples preparees automatiquement, mails "
        "importants a valider), fait le rapport chiffre, prepare les brouillons "
        "et propose chaque envoi a la confirmation (jamais d'envoi silencieux). "
        "Pour « traite mes mails », « fais le tri de ma boite », « mes mails du "
        "matin », « ou j'en suis sur mes mails »."
    ),
    parametres={
        "type": "object",
        "properties": {
            "nombre": {"type": "integer",
                       "description": "Combien de mails scanner (15 par defaut)."}
        },
    },
    lent=True,
    phrase_attente="Je fais le tri de ta boite mail, un instant.",
)
def operateur_mails(nombre: int = _NOMBRE_DEFAUT) -> str:
    """Etape 1 : rapport chiffre + premiere action proposee."""
    entetes = _entetes(nombre)
    if entetes is None:
        return ("La messagerie n'est pas configuree ou injoignable. "
                "Renseigne la section mail de config.yaml.")
    if not entetes:
        return "Ta boite de reception est vide. Rien a faire ce matin."
    spam, simples, valider = _categoriser(entetes)
    _RESTANTS.clear()
    _RESTANTS.extend(simples + valider)
    _TRAITES.update({"spam": len(spam), "auto": 0, "valides": 0})
    try:
        from core import operator
        champs = []
        if spam:
            champs.append({"titre": "Poubelles",
                           "valeur": f"{len(spam)} pub/spam a jeter"})
        if simples:
            champs.append({"titre": "Traites auto",
                           "valeur": f"{len(simples)} reponse simple preparee"})
        if valider:
            noms = ", ".join(e.get("nom", "")[:20] for e in valider[:4])
            champs.append({"titre": "A valider",
                           "valeur": f"{len(valider)} - {noms}"})
        for e in entetes[:_MAX_CARTE]:
            champs.append({"titre": (e.get("nom") or "?")[:24],
                           "valeur": (e.get("sujet") or "sans objet")[:60]})
        operator.carte_briefing({"client": "Compte rendu mails",
                                 "champs": champs})
    except Exception:
        pass


    morceaux = [
        f"Tu avais {len(entetes)} mail(s) ce matin. "
        "Voici ce que j'ai fait en arriere-plan :"
    ]
    if spam:
        morceaux.append(
            f"- {len(spam)} mail(s) pub ou spam identifies, prets a jeter "
            "avec une seule confirmation.")
        _mettre_en_attente("vider_poubelle", {})
    if simples:
        morceaux.append(
            f"- {len(simples)} mail(s) simple(s) que je peux traiter "
            "directement (confirmation, acces, notification) : brouillon pret, "
            "envoi a confirmer.")
    if valider:
        morceaux.append(
            f"- {len(valider)} mail(s) important(s) attendent ton avis.")
    suite = _traiter_suivant()
    if suite:
        morceaux.append(suite)
    return " ".join(morceaux)


@outil(
    nom="operateur_mail_suivant",
    description=(
        "Passe au mail suivant de la session AI Email Operator : resume l'enjeu, "
        "propose un brouillon de reponse et met l'envoi en confirmation. A "
        "appeler juste apres un envoi confirme ou une annulation, pour "
        "enchainement fluide. Termine par le bilan final quand la file est vide."
    ),
    parametres={"type": "object", "properties": {}},
)
def operateur_mail_suivant() -> str:
    """Etapes 2 a 4 : mail suivant, ou bilan final."""
    return _traiter_suivant()


@outil(
    nom="ajuster_brouillon_mail",
    description=(
        "Modifie le brouillon de mail en cours selon une consigne libre "
        "(« met plutot 16h », « sois plus formel », « raccourcis »), puis "
        "redemande la confirmation d'envoi. Ne JAMAIS envoyer directement."
    ),
    parametres={
        "type": "object",
        "properties": {
            "consigne": {"type": "string",
                         "description": "Ce qu'il faut changer dans le brouillon."}
        },
        "required": ["consigne"],
    },
)
def ajuster_brouillon_mail(consigne: str) -> str:
    """Etape 3bis : ajustement du brouillon sur consigne, sans envoi."""
    from tools import mail as m
    brouillon = m.brouillon()
    if not brouillon or not brouillon.get("corps"):
        return ("Aucun brouillon en cours. Lance d'abord le traitement de "
                "tes mails (operateur_mails).")
    consigne = str(consigne or "").strip()
    if not consigne:
        return "Dis-moi ce qu'il faut modifier dans le brouillon."
    nouveau = _reviser(brouillon["corps"], consigne)
    if not nouveau:
        return ("Je n'ai pas reussi a modifier le brouillon. Reformule ta "
                "consigne, ou dicte-moi le texte complet.")
    m.modifier_brouillon(corps=nouveau)
    return (f"Note, brouillon modifie. Nouvelle version : {nouveau}. "
            "Est-ce que tu confirmes l'envoi ?")
