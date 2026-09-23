"""Upload de fichiers : HTTP multipart reel ou navigateur pilote.

Deux vraies mecaniques, zero simulation :
1. envoyer_fichier : POST multipart vers une URL (ex. endpoint d'upload,
   API tiers). Borne a 200 Mo, timeout 120 s, erreur claire sinon.
2. upload_navigateur : la page ouverte dans Chrome (pilote par Jarvis via
   CDP) recoit le fichier dans son input file. On ne DEVINE pas le champ :
   Jarvis identifie le bon input file via le modele de vision si besoin.

Les fichiers sources restent confines aux dossiers autorises (meme regle
que tools/fichiers.py) ; les secrets ne partent jamais.
"""

import mimetypes
from pathlib import Path

import requests

from core import plateforme
from core.config import reglage
from core.registre import outil

from tools.fichiers import _est_interdit, _relatif, _resoudre

_TAILLE_MAX = 200 * 1024 * 1024  # 200 Mo


def _source_upload(chemin: str) -> Path:
    """Valide un fichier local pour upload : existe, autorise, pas un secret."""
    cible = _resoudre(chemin)
    if not cible.is_file():
        raise FileNotFoundError(str(cible))
    if _est_interdit(cible):
        raise PermissionError("fichier protege")
    if cible.stat().st_size > _TAILLE_MAX:
        raise ValueError("fichier trop volumineux (max 200 Mo)")
    return cible


@outil(
    nom="envoyer_fichier",
    description=(
        "Uploade un fichier local vers une URL (POST multipart). "
        "Renvoie la reponse du serveur. Confirmation obligatoire."
    ),
    confirmation=True,
    annonce="Je m'apprete a envoyer un fichier vers un serveur.",
)
def envoyer_fichier(chemin: str, url: str, champ: str = "file", champs: str = "") -> str:
    """POST multipart reel via requests ; `champs` = 'cle=valeur,cles2=v2'."""
    try:
        cible = _source_upload(chemin)
    except FileNotFoundError:
        return "Ce fichier n'existe pas dans les dossiers autorises."
    except PermissionError as erreur:
        return f"Envoi refuse : {erreur}"
    except ValueError as erreur:
        return f"Envoi refuse : {erreur}"

    if not str(url or "").startswith(("http://", "https://")):
        return "L'URL doit commencer par http:// ou https://."

    donnees: dict[str, str] = {}
    for paire in str(champs or "").split(","):
        paire = paire.strip()
        if not paire:
            continue
        if "=" not in paire:
            return f"Champ additionnel invalide (attendu cle=valeur) : {paire}"
        cle, valeur = paire.split("=", 1)
        donnees[cle.strip()] = valeur.strip()

    mime = mimetypes.guess_type(str(cible))[0] or "application/octet-stream"
    try:
        with cible.open("rb") as f:
            reponse = requests.post(
                url,
                files={champ or "file": (cible.name, f, mime)},
                data=donnees,
                timeout=120,
            )
    except requests.RequestException as erreur:
        return f"Upload impossible : {erreur}"

    corps = (reponse.text or "").strip()
    if len(corps) > 2000:
        corps = corps[:2000] + "… (tronque)"
    return (
        f"Upload termine : {_relatif(cible)} -> {url} "
        f"(HTTP {reponse.status_code})\n{corps}"
    )


@outil(
    nom="upload_navigateur",
    description=(
        "Remplit le champ fichier de la page ouverte dans Chrome avec un fichier "
        "local, puis soumet le formulaire. Confirmation obligatoire."
    ),
    confirmation=True,
    annonce="Je m'apprete a remplir un formulaire d'upload dans ton navigateur.",
)
def upload_navigateur(chemin: str, index_input: int = 0, soumettre: bool = True) -> str:
    """Charge le fichier dans le n-ieme input file de la page ouverte."""
    try:
        cible = _source_upload(chemin)
    except (FileNotFoundError, PermissionError, ValueError) as erreur:
        return f"Upload refuse : {erreur}"

    from tools import navigateur

    browser = navigateur._connexion()
    if browser is None:
        return "Je n'ai pas acces a Chrome. Lance-le (ou demande-moi d'ouvrir une page) et reessaie."
    try:
        page = navigateur._page_active(browser)
    except Exception:
        return "Aucune page ouverte dans le navigateur pilote."
    if navigateur._protege(page.url):
        return "Cette page est protegee, je n'y touche pas."

    inputs = page.locator('input[type="file"]')
    total = inputs.count()
    if total == 0:
        return "Cette page n'a aucun champ de fichier a remplir."
    if index_input >= total:
        return f"Il y a {total} champ(s) fichier ; index {index_input} inexistant."

    try:
        inputs.nth(index_input).set_input_files(str(cible))
    except Exception as erreur:
        return f"Remplissage du champ fichier impossible : {erreur}"

    if not soumettre:
        return f"Fichier charge dans le champ {index_input} : {_relatif(cible)}. Soumission manuelle."

    try:
        page.keyboard.press("Enter")
    except Exception:
        pass
    return (
        f"Fichier uploade depuis la page ouverte : {_relatif(cible)}. "
        "Verifie le resultat a l'ecran."
    )
