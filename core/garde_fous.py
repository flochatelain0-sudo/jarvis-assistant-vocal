"""Garde-fous d'entree : scanne les textes externes AVANT le LLM (inspire d'OpenJarvis).

Jarvis avale beaucoup de contenu externe — pages web (navigateur, reservation),
mails, LinkedIn, Instagram, captures d'ecran OCRisees. Ce module est la barriere
qui verifie ce qui entre dans l'historique du modele :

- secrets : cles API, tokens, mots de passe, chaines de connexion — un secret
  recopie dans une page ne doit jamais partir dans un prompt cloud ;
- PII : mails, telephones, cartes bancaires, SSN-US, IPv4 publiques ;
- injection de prompt : tentatives classiques de detournement (« ignore toutes
  les instructions precedentes », « you are now... », appels de code caches).

Trois modes, du plus doux au plus ferme (comme les RedactionMode d'OpenJarvis) :

- ``observer`` : ne change rien, journalise seulement (par defaut, decouverte) ;
- `` caviarder`` : remplace les secrets/PII par des marqueurs, journalise ;
- ``bloquer`` : refuse le texte suspect (secrets/PII a risque eleve), journalise.

L'injection de prompt est TOUJOURS signalisee au journal, mais le texte passe
en mode observer/caviarder : le LLM reconnait deja la pluplart des tentatives,
le but est de garder une trace. En mode bloquer, une injection averee coupe.

Liberations volontairement simples : regex stdlib, aucun dependance externe,
aucun appel reseau. Ce n'est pas un pare-feu parfait, c'est une barriere a
motifs evidents — meme philosophie que core/confidentialite.py (qui, lui,
caviarde en SORTIE, avant la voix).
"""

import re

from core.config import reglage

# ------------------------------------------------------------------ motifs

# (regex, severite, description). severite : "critique" | "elevee" | "moyenne".
_MOTIFS_SECRETS = [
    (re.compile(r"sk-[A-Za-z0-9_-]{20,}"), "critique", "cle OpenAI"),
    (re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}"), "critique", "cle Anthropic"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "critique", "cle d'acces AWS"),
    (re.compile(r"(?:ghp|gho|ghs|ghr|github_pat)_[A-Za-z0-9_]{36,}"), "critique",
     "token GitHub"),
    (re.compile(r"xox[bpors]-[A-Za-z0-9-]{10,}"), "elevee", "token Slack"),
    (re.compile(r"(?:sk|pk)_(?:test|live)_[A-Za-z0-9]{20,}"), "critique",
     "cle Stripe"),
    (re.compile(r"AIza[A-Za-z0-9_-]{35}"), "critique", "cle Google API"),
    (re.compile(r"-----BEGIN (?:RSA )?PRIVATE KEY-----"), "critique",
     "cle privee"),
    (re.compile(r"(?:postgres|mysql|mongodb|redis)://[^\s]{10,}"), "elevee",
     "chaine de connexion"),
    (re.compile(r"""(?:password|passwd|pwd)\s*[=:]\s*['"][^'"]{4,}['"]"""),
     "elevee", "mot de passe en clair"),
    (re.compile(r"""(?:api_key|secret_key|auth_token)\s*[=:]\s*['"][^'"]{8,}['"]"""),
     "elevee", "cle/jetons de config"),
]

_MOTIFS_PII = [
    (re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),
     "moyenne", "adresse mail"),
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "critique", "SSN (US)"),
    (re.compile(r"\b4\d{3}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b"), "critique",
     "carte Visa"),
    (re.compile(r"\b5[1-5]\d{2}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b"), "critique",
     "carte Mastercard"),
    (re.compile(r"\b3[47]\d{2}[\s-]?\d{6}[\s-]?\d{5}\b"), "critique",
     "carte Amex"),
    (re.compile(r"\b(?:\+1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
     "moyenne", "telephone (US)"),
    (re.compile(r"\b(?:\+33|0)[1-9](?:[\s.-]?\d{2}){4}\b"), "moyenne",
     "telephone (France)"),
    (re.compile(r"\b(?:IBAN|BIC)\b[^\n]{5,}"), "elevee", "IBAN/BIC"),
    (re.compile(
        r"\b(?!10\.)(?!172\.(?:1[6-9]|2\d|3[01])\.)(?!192\.168\.)(?!127\.)(?!0\.)"
        r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"), "moyenne", "IPv4 publique"),
]

# Tentatives de detournement classiques. Le LLM peut en reverifier le fond,
# mais le motif evident doit au moins finir au journal.
_MOTIFS_INJECTION = [
    (re.compile(r"(?i)ignore\s+(all\s+)?(previous|prior|above)"
               r"\s+(instructions?|prompts?|rules?)"), "elevee",
     "override de la consigne systeme"),
    (re.compile(r"(?i)you\s+are\s+now\s+(?:a\s+)?(?:different|new|my)"),
     "elevee", "changement d'identite"),
    (re.compile(r"(?i)disregard\s+(all\s+)?(?:previous|prior|your)"
               r"\s+(?:instructions?|programming|rules?)"), "elevee",
     "non-prise en compte des regles"),
    (re.compile(r"(?i)(?:execute|run|eval)\s*\(\s*['\"]"), "elevee",
     "appel de code cache"),
    (re.compile(r"(?i)system\s*prompt\s*[:=]"), "elevee",
     "injection de consigne systeme"),
    (re.compile(r"(?i)reveal\s+(?:your|the)\s+(?:system|initial)"
               r"\s+(?:prompt|instructions?)"), "elevee",
     "vol de la consigne systeme"),
]

# ------------------------------------------------------------------ resultats


class Constat:
    """Un motif detecte dans un texte (severite + extrait borne)."""

    __slots__ = ("type", "severite", "description", "extrait")

    def __init__(self, type_, severite, description, extrait):
        self.type = type_
        self.severite = severite
        self.description = description
        self.extrait = (extrait or "")[:80]     # jamais le secret complet

    def __repr__(self):
        return (f"Constat({self.type}, {self.severite}, {self.description}, "
                f"{self.extrait[:20]!r})")


class Rapport:
    """Resultat du scan d'un texte. ``propre`` = aucun motif trouve."""

    def __init__(self, constats=None, bloque=False):
        self.constats = constats or []
        self.bloque = bloque

    @property
    def propre(self):
        return not self.constats

    def plus_grave(self):
        """La severite maximale trouvee ("" si rien)."""
        ordre = {"critique": 3, "elevee": 2, "moyenne": 1}
        return max((ordre.get(c.severite, 0) for c in self.constats), default=0)

    def __repr__(self):
        return f"Rapport({len(self.constats)} constats, bloque={self.bloque})"


class TexteRefuse(Exception):
    """Levée en mode bloquer quand le texte presente un risque trop eleve."""

    def __init__(self, rapport):
        super().__init__("texte externe refuse par les garde-fous")
        self.rapport = rapport


# ------------------------------------------------------------------ scanners


def scanner(texte, scan_pii=True):
    """Retourne la liste des constats (secrets + PII + injection) d'un texte."""
    constats = []
    t = str(texte or "")
    for motif, severite, description in _MOTIFS_SECRETS:
        for m in motif.finditer(t):
            constats.append(Constat("secret", severite, description,
                                    m.group(0)))
    if scan_pii:
        for motif, severite, description in _MOTIFS_PII:
            for m in motif.finditer(t):
                constats.append(Constat("pii", severite, description,
                                        m.group(0)))
    for motif, severite, description in _MOTIFS_INJECTION:
        for m in motif.finditer(t):
            constats.append(Constat("injection", severite, description,
                                    m.group(0)))
    return constats


def caviarder(texte):
    """Remplace secrets et PII par des marqueurs, en conservant la mise en forme.

    Les marqueurs gardent la severite : ``[cle:critique]``, ``[mail]``...
    """
    t = str(texte or "")
    for motif, severite, description in _MOTIFS_SECRETS:
        t = motif.sub(f"[{description}:caviarde]", t)
    for motif, severite, description in _MOTIFS_PII:
        t = motif.sub(f"[{description}:caviarde]", t)
    return t


def _mode_courant():
    """Mode configure (securite.garde_fous.entree) : observer|caviarder|bloquer."""
    m = str(reglage("securite.garde_fous_entree", "observer") or "observer")
    return m if m in ("observer", "caviarder", "bloquer") else "observer"


def verifier(texte, source="", scan_pii=True):
    """Applique la politique a un texte externe AVANT qu'il entre dans le LLM.

    Retourne le texte eventuellement caviarde. En mode bloquer, une detection
    de secret ou de PII critique/elevee leve ``TexteRefuse`` ; une injection
    averee aussi. Toute detection est journalisee (categorie securite), sans
    jamais journaliser le secret lui-meme (seul un extrait borne, caviarde).

    Ce module ne leve JAMAIS pour une erreur interne : un garde-fou qui
    crashe n'a pas le droit de couper l'assistant.
    """
    try:
        constats = scanner(texte, scan_pii=scan_pii)
        if not constats:
            return str(texte or "")

        mode = _mode_courant()
        from core import operator
        resume = ", ".join(f"{c.type}/{c.severite}:{c.description}"
                           for c in constats[:5])
        detail = f"source={source or 'externe'} mode={mode} constats=[{resume}]"
        if mode == "bloquer":
            grave = [c for c in constats
                     if c.severite in ("critique", "elevee")]
            injection = [c for c in constats if c.type == "injection"]
            if grave or injection:
                operator.journaliser("securite", "Contenu externe refuse",
                                     detail, resultat="bloque")
                raise TexteRefuse(Rapport(constats, bloque=True))
        elif mode == "caviarder":
            texte = caviarder(texte)
            operator.journaliser("securite", "Contenu externe caviarde",
                                 detail, resultat="caviarde")
            return texte
        else:
            operator.journaliser("securite", "Contenu externe suspect",
                                 detail, resultat="observe")
        return str(texte or "")
    except TexteRefuse:
        raise
    except Exception:
        # Un garde-fou en echec ne doit jamais couper la reponse.
        return str(texte or "")


def proteger_historique(historique, source=""):
    """Caviarde tous les messages utilisateur externes d'un historique.

    Applique ``verifier`` sur chaque message role=user a contenu textuel, en
    place. Les messages assistant et les tool_result ne sont pas retouches :
    ils viennent du modele ou d'outils de confiance. En mode bloquer, un
    message refuse est remplace par un avertissement type pour que le modele
    sache pourquoi le contenu est absent.
    """
    if not isinstance(historique, list):
        return historique
    for message in historique:
        if not isinstance(message, dict) or message.get("role") != "user":
            continue
        contenu = message.get("content")
        if not isinstance(contenu, str) or not contenu:
            continue
        try:
            message["content"] = verifier(contenu, source=source)
        except TexteRefuse:
            message["content"] = (
                "[Contenu externe refuse par les garde-fous de securite : "
                "secret ou tentative d'injection detecte.]")
    return historique
