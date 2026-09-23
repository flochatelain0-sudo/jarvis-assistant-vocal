"""Gestion des fichiers locaux : Jarvis lit, cree, modifie, deplace.

Vraie pile OS : Path/subprocess natifs, pas de simulation. Les operations
restent dans les dossiers AUTORISES (config fichiers.dossiers, defaut :
home utilisateur + Bureau + Documents + Telechargements) — un LLM ne doit
jamais pouvoir errer dans tout le disque, et surtout pas sortir du disque.

SECURITE (doctrine du projet) :
- lister_fichiers / lire_fichier    : N1, lecture seule, direct.
- ecrire_fichier                    : N2, confirmation.
- deplacer_fichier / copier_fichier : N2, confirmation.
- supprimer_fichier                 : N3 TOUJOURS (suppression = feu vert
  obligatoire, quel que soit le mode MANUAL/AUTO).

Jamais de secret : les fichiers .env, config.yaml, jetons et cles sont
illisibles par ces outils (meme en lecture).
"""

import logging
import shutil
from pathlib import Path

from core.config import reglage
from core.registre import outil

LOG = logging.getLogger("jarvis.fichiers")

# Fichiers INTERDITS meme en lecture : secrets, jetons, cles.
_INTERDITS = (
    "config.yaml",
    "config.yml",
    ".env",
    "integrations_oauth.json",
    "buts.json",
    "credentials.json",
    "google_token_agenda.json",
    "token.json",
    "secrets.json",
)

_PREFIX_INTERDITS = ("google_token", "google_secret", "client_secret", ".ssh", ".aws")


def _dossiers_autorises() -> list[Path]:
    """Racines autorisees pour toutes les operations fichiers."""
    configure = reglage("fichiers.dossiers", None)
    if configure:
        return [Path(str(d)).expanduser().resolve() for d in configure]
    home = Path.home()
    racines = [home]
    for nom in ("Desktop", "Bureau", "Documents", "Downloads", "Telechargements"):
        candidat = home / nom
        if candidat.is_dir():
            racines.append(candidat)
    return racines


def _est_interdit(chemin: Path) -> bool:
    """True si le fichier porte un secret (jamais lisible, jamais modifiable)."""
    nom = chemin.name.lower()
    if nom in _INTERDITS:
        return True
    return any(nom.startswith(p.lower()) for p in _PREFIX_INTERDITS)


def _resoudre(chemin: str) -> Path:
    """Resout un chemin utilisateur et refuse tout ce qui sort des racines.

    Renvoie un Path absolu, contenu dans l'une des racines autorisees.
    Leve PermissionError sinon (path traversal, disque entier, secrets).
    """
    p = Path(chemin).expanduser()
    if p.is_absolute():
        resolu = p.resolve()
    else:
        racines = _dossiers_autorises()
        resolu = next(
            ((r / p).resolve() for r in racines if (r / p).exists()),
            (racines[0] / p).resolve(),
        )
    for racine in _dossiers_autorises():
        if resolu == racine or racine in resolu.parents:
            if _est_interdit(resolu):
                raise PermissionError("fichier protege (secret)")
            return resolu
    raise PermissionError("hors des dossiers autorises")


def _relatif(chemin: Path) -> str:
    """Affiche un chemin relatif au home quand c'est possible."""
    try:
        return str(chemin.relative_to(Path.home()))
    except ValueError:
        return str(chemin)


@outil(
    nom="lister_fichiers",
    description="Liste les fichiers d'un dossier autorise (nom, taille, date de modification).",
    confirmation=False,
)
def lister_fichiers(dossier: str = "", motif: str = "") -> str:
    """Liste jusqu'a 200 entrees, triees par date de modification.

    Sans argument, on liste la premiere racine autorisee (le home par defaut).
    """
    try:
        base = _dossiers_autorises()[0] if not dossier or dossier == "~" else _resoudre(dossier)
    except PermissionError:
        return "Je ne liste que les dossiers autorises (Bureau, Documents, Telechargements...)."
    if not base.is_dir():
        return f"Ce dossier n'existe pas : {_relatif(base)}"
    entrees = []
    for entree in base.iterdir():
        if motif and motif.lower() not in entree.name.lower():
            continue
        if _est_interdit(entree):
            continue
        try:
            stat = entree.stat()
        except OSError:
            continue
        entrees.append((stat.st_mtime, entree, stat))
    entrees.sort(reverse=True)
    if not entrees:
        return f"Aucun fichier dans {_relatif(base)}."
    lignes = []
    for _, entree, stat in entrees[:200]:
        type_ = "dossier" if entree.is_dir() else f"{stat.st_size:,} octets"
        lignes.append(f"{entree.name} — {type_}")
    return f"{len(entrees)} entree(s) dans {_relatif(base)} :\n" + "\n".join(lignes)


@outil(
    nom="lire_fichier",
    description="Lit un fichier texte autorise (jusqu'a 20000 caracteres).",
    confirmation=False,
)
def lire_fichier(chemin: str) -> str:
    """Lit un fichier texte ; refuse les binaires et les secrets."""
    try:
        cible = _resoudre(chemin)
    except PermissionError:
        return "Ce fichier est protege ou hors des dossiers autorises."
    if not cible.is_file():
        return f"Ce fichier n'existe pas : {_relatif(cible)}"
    if cible.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".mp4", ".mp3", ".wav", ".zip", ".pdf", ".exe"}:
        return f"{cible.name} est un fichier binaire, je ne peux pas l'afficher comme texte."
    try:
        contenu = cible.read_text(encoding="utf-8", errors="replace")
    except OSError as erreur:
        return f"Lecture impossible : {erreur}"
    if len(contenu) > 20000:
        contenu = contenu[:20000] + "\n… (fichier tronque)"
    return f"{_relatif(cible)} :\n{contenu}"


@outil(
    nom="ecrire_fichier",
    description="Cree ou complete un fichier texte (contenu) dans un dossier autorise.",
    confirmation=True,
    annonce="Je m'apprete a ecrire un fichier.",
)
def ecrire_fichier(chemin: str, contenu: str, mode: str = "remplacer") -> str:
    """Ecrit `contenu` dans `chemin` ; mode=ajouter complete a la fin."""
    try:
        cible = _resoudre(chemin)
    except PermissionError:
        return "Ce fichier est protege ou hors des dossiers autorises."
    if mode not in ("remplacer", "ajouter"):
        return "Mode inconnu : utiliser 'remplacer' ou 'ajouter'."
    if _est_interdit(cible):
        return "Ce fichier est protege, je ne le modifie pas."
    try:
        cible.parent.mkdir(parents=True, exist_ok=True)
        if mode == "ajouter" and cible.exists():
            with cible.open("a", encoding="utf-8") as f:
                f.write(contenu)
        else:
            cible.write_text(contenu, encoding="utf-8")
    except OSError as erreur:
        return f"Ecriture impossible : {erreur}"
    verbe = "complete" if mode == "ajouter" else "ecrit"
    return f"Fichier {verbe} : {_relatif(cible)} ({len(contenu):,} caracteres)"


@outil(
    nom="deplacer_fichier",
    description="Deplace ou renomme un fichier dans les dossiers autorises.",
    confirmation=True,
    annonce="Je m'apprete a deplacer un fichier.",
)
def deplacer_fichier(source: str, destination: str) -> str:
    """Deplace (ou renomme) un fichier, sans ecraser une cible existante."""
    try:
        src = _resoudre(source)
        dst = _resoudre(destination)
    except PermissionError:
        return "Deplacement refuse : fichier protege ou hors des dossiers autorises."
    if not src.exists():
        return f"La source n'existe pas : {_relatif(src)}"
    if _est_interdit(src) or _est_interdit(dst):
        return "Deplacement refuse : fichier protege."
    if dst.exists():
        return f"Un element porte deja ce nom : {_relatif(dst)}"
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
    except OSError as erreur:
        return f"Deplacement impossible : {erreur}"
    return f"Deplace : {_relatif(src)} -> {_relatif(dst)}"


@outil(
    nom="copier_fichier",
    description="Copie un fichier dans les dossiers autorises.",
    confirmation=True,
    annonce="Je m'apprete a copier un fichier.",
)
def copier_fichier(source: str, destination: str) -> str:
    """Copie un fichier, sans ecraser une cible existante."""
    try:
        src = _resoudre(source)
        dst = _resoudre(destination)
    except PermissionError:
        return "Copie refusee : fichier protege ou hors des dossiers autorises."
    if not src.is_file():
        return f"La source n'existe pas : {_relatif(src)}"
    if _est_interdit(src) or _est_interdit(dst):
        return "Copie refusee : fichier protege."
    if dst.exists():
        return f"Un element porte deja ce nom : {_relatif(dst)}"
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(src), str(dst))
    except OSError as erreur:
        return f"Copie impossible : {erreur}"
    return f"Copie : {_relatif(src)} -> {_relatif(dst)}"


@outil(
    nom="supprimer_fichier",
    description="Supprime definitivement un fichier (pas les dossiers).",
    confirmation=True,
    annonce="Je m'apprete a supprimer un fichier. Confirmation obligatoire.",
)
def supprimer_fichier(chemin: str) -> str:
    """Suppression N3 : TOUJOURS confirmee par l'utilisateur."""
    try:
        cible = _resoudre(chemin)
    except PermissionError:
        return "Ce fichier est protege ou hors des dossiers autorises."
    if not cible.exists():
        return f"Ce fichier n'existe pas : {_relatif(cible)}"
    if _est_interdit(cible):
        return "Ce fichier est protege, je ne le supprime pas."
    if cible.is_dir():
        return "Je ne supprime pas un dossier complet. Demande-moi fichier par fichier."
    try:
        cible.unlink()
    except OSError as erreur:
        return f"Suppression impossible : {erreur}"
    return f"Supprime : {_relatif(cible)}"
