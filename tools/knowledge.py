"""Base de connaissances : les documents de l'utilisateur, references rapides.

Stockage : JSON plat dans data/knowledge.json (un document = id, titre,
contenu, source, date). Pas de RAG lourd : les documents courts sont
injectables tels quels dans le contexte du modele, les longs resumes
d'abord par l'IA (outils existants). LECTURE D'UN FICHIER TEXTE UNIQUE,
sans execution : .txt, .md, .csv, .json au maximum 200 Ko.

Doctrine 95/5 : l'ajout et l'injection sont des actions N1 (sans risque,
locales, sans envoi) ; la suppression est confirmee comme une note.
"""
import json
import re
import threading
import time
from pathlib import Path

from core.registre import outil

_RACINE = Path(__file__).resolve().parent.parent
_DOSSIER = _RACINE / "data"
_FICHIER = _DOSSIER / "knowledge.json"
_MAX_TAILLE = 200 * 1024
_MAX_DOCUMENTS = 200

_VERROU = threading.RLock()
_DOCUMENTS = None


def _charger():
    global _DOCUMENTS
    if _DOCUMENTS is not None:
        return _DOCUMENTS
    with _VERROU:
        if _DOCUMENTS is None:
            try:
                _DOCUMENTS = json.loads(_FICHIER.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                _DOCUMENTS = []
            if not isinstance(_DOCUMENTS, list):
                _DOCUMENTS = []
        return _DOCUMENTS


def _sauver():
    _FICHIER.parent.mkdir(parents=True, exist_ok=True)
    _FICHIER.write_text(
        json.dumps(_DOCUMENTS[-_MAX_DOCUMENTS:], ensure_ascii=False, indent=1),
        encoding="utf-8")


def _titre_de(contenu, nom_fichier=""):
    for ligne in contenu.splitlines():
        ligne = ligne.strip().lstrip("#").strip()
        if ligne:
            return ligne[:80]
    return (nom_fichier or "document").strip()[:80] or "document"


def documents():
    """Les documents recents, du plus recent au plus ancien."""
    with _VERROU:
        return list(reversed(_charger()))


def ajouter_depuis_texte(contenu, titre="", source="texte"):
    """Ajoute un document (contenu texte). Retourne le nouveau document."""
    contenu = (contenu or "").strip()
    if not contenu:
        raise ValueError("document vide")
    if len(contenu) > _MAX_TAILLE:
        raise ValueError("document trop volumineux (200 Ko max)")
    with _VERROU:
        docs = _charger()
        doc = {
            "id": int(time.time() * 1000) % (10 ** 12),
            "titre": (titre or _titre_de(contenu, source)).strip()[:80],
            "contenu": contenu,
            "source": source[:120],
            "ts": time.time(),
        }
        docs.append(doc)
        global _DOCUMENTS
        _DOCUMENTS = docs
        _sauver()
        return doc


def ajouter_depuis_fichier(chemin):
    """Ajoute un document depuis un fichier texte du disque (lecture seule)."""
    p = Path(chemin).expanduser()
    if not p.is_file():
        raise FileNotFoundError(str(p))
    if p.suffix.lower() not in {".txt", ".md", ".csv", ".json"}:
        raise ValueError(f"format non supporte : {p.suffix}")
    if p.stat().st_size > _MAX_TAILLE:
        raise ValueError("fichier trop volumineux (200 Ko max)")
    contenu = p.read_text(encoding="utf-8", errors="replace")
    return ajouter_depuis_texte(contenu, titre="", source=p.name)


def retrouver(ident):
    """Le document d'id `ident`, ou None."""
    with _VERROU:
        for d in _charger():
            if d.get("id") == ident:
                return d
    return None


def _extrait(contenu, taille=1200):
    if len(contenu) <= taille:
        return contenu
    return contenu[:taille] + " [...]"


@outil(
    nom="lire_document",
    description="Lit un document de la base de connaissances et le resume. "
                "Pour 'resume le document X', 'qu'est-ce que dit mon doc "
                "sur les garanties ?', 'relis mes notes du produit'. "
                "Utilise aussi l'outil si une question porte sur un sujet "
                "deja documente (fiche produit, offre, proces verbal).",
    lent=False,
    phrase_attente="Je relis ce document.",
)
def lire_document(recherche: str) -> str:
    """Resume le document le plus proche de la recherche, par mots-cles."""
    recherche = (recherche or "").strip()
    if not recherche:
        return ("Quelle document veux-tu que je lise ? "
                "Voici les recents : "
                + ", ".join(d["titre"] for d in documents()[:5] or ["aucun"])
                + ".")
    mots = {m for m in re.split(r"\W+", recherche.lower()) if len(m) > 2}
    meilleur, score = None, 0
    for d in documents():
        texte = (d.get("titre", "") + " " + d.get("contenu", "")).lower()
        s = sum(1 for m in mots if m in texte)
        if s > score:
            meilleur, score = d, s
    if not meilleur or score == 0:
        return (f"Je ne trouve pas de document correspondant a "
                f"\u00ab {recherche} \u00bb. Veux-tu que je l'ajoute ?")
    return (f"Document \u00ab {meilleur['titre']} \u00bb (source : "
            f"{meilleur.get('source', 'texte')}) : "
            f"{_extrait(meilleur['contenu'])}")


@outil(
    nom="ajouter_document",
    description="Ajoute un document a la base de connaissances : une fiche "
                "produit, une offre, un proces-verbal, des notes. Pour "
                "'ajoute ce document dans ta memoire', 'retiens cette "
                "fiche produit', 'ajoute ce fichier'.",
    lent=False,
    phrase_attente="J'enregistre ce document.",
)
def ajouter_document(contenu: str, titre: str = "") -> str:
    """Ajoute un document fourni en texte, ou lit un fichier du disque."""
    contenu = (contenu or "").strip()
    chemin = None
    if not contenu and titre:
        chemin = titre
        titre = ""
    if chemin:
        try:
            doc = ajouter_depuis_fichier(chemin)
        except (FileNotFoundError, ValueError) as e:
            return f"Je n'ai pas pu ajouter ce document : {e}."
    else:
        try:
            doc = ajouter_depuis_texte(contenu, titre=titre)
        except ValueError as e:
            return f"Je n'ai pas pu ajouter ce document : {e}."
    return (f"Document ajoute : \u00ab {doc['titre']} \u00bb "
            f"({len(doc['contenu'])} caracteres). "
            f"Je peux le resumer ou le relier a tes questions.")


@outil(
    nom="lister_documents",
    description="Liste les documents de la base de connaissances. "
                "Pour 'mes documents', 'qu'est-ce que tu as en memoire ?'.",
    lent=False,
    phrase_attente="Je regarde ta base de connaissances.",
)
def lister_documents() -> str:
    docs = documents()
    if not docs:
        return ("Ta base de connaissances est vide. "
                "Dis-moi \u00ab ajoute ce document \u00bb pour commencer.")
    titres = [d["titre"] for d in docs[:10]]
    return (f"{len(docs)} document(s) en base : "
            + " ; ".join(titres) + ".")
