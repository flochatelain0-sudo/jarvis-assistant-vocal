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


def _traiter_suivant() -> str:
    """Presente le mail suivant de la file : enjeu + brouillon + envoi N3 en
    file. Bilan final quand la file est vide."""
    if not _RESTANTS:
        total = _TRAITES["spam"] + _TRAITES["auto"] + _TRAITES["valides"]
        minutes = total * _MINUTES_PAR_MAIL
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
        return (intro
                + f" Reponse proposee : {brouillon}"
                + " Dis « oui » pour confirmer l'envoi, ou dis-moi ce qu'il "
                  "faut modifier (heure, ton, contenu).")
    return (f"Je n'ai pas reussi a preparer la reponse pour {nom} "
            f"(« {sujet} »). Traite-le manuellement ou relance-moi.")


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
