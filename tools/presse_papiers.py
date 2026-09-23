"""Sentinelle presse-papiers (inspiree du Clipboard Sentry de Brahma Echo).

Lire ce que l'utilisateur vient de copier et detecter ce que c'est :
URL, email, numero de telephone, code, montant... pour PROPOSER des actions.
LECTURE SEULE : jamais d'ecriture dans le presse-papiers, et la lecture
demande toujours l'initiative de l'utilisateur (« qu'est-ce que j'ai copie ? »).
"""
import re
import subprocess
import sys

from core.registre import outil


def _lire():
    """Le texte du presse-papiers, ou "" si vide/inaccessible."""
    try:
        if sys.platform == "darwin":
            r = subprocess.run(["pbpaste"], capture_output=True,
                               timeout=3)
            return r.stdout.decode("utf-8", "replace").strip()
        if sys.platform.startswith("win"):
            r = subprocess.run(
                ["powershell", "-NoProfile", "-Command", "Get-Clipboard"],
                capture_output=True, timeout=5)
            return r.stdout.decode("utf-8", "replace").strip()
        for cmd in (["xclip", "-o", "-selection", "clipboard"],
                    ["xsel", "-o", "-b"]):
            try:
                r = subprocess.run(cmd, capture_output=True, timeout=3)
                if r.returncode == 0:
                    return r.stdout.decode("utf-8", "replace").strip()
            except (OSError, subprocess.SubprocessError):
                continue
        return ""
    except (OSError, subprocess.SubprocessError):
        return ""


_RE_URL = re.compile(r"https?://\S+")
_RE_MAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
_RE_TEL = re.compile(
    r"(?:\+\d{1,3}[ .-]?)?(?:0\s?[1-9]|6)[ .-]?(?:\d{2}[ .-]?){3}\d{2}")


def analyser(texte):
    """Classe le contenu copie : [(type, valeur), ...], sans exception."""
    trouve = []
    for m in _RE_URL.finditer(texte):
        trouve.append(("lien", m.group(0)))
    for m in _RE_MAIL.finditer(texte):
        trouve.append(("email", m.group(0)))
    for m in _RE_TEL.finditer(texte):
        trouve.append(("telephone", m.group(0)))
    if not trouve and texte:
        lignes = [l for l in texte.splitlines() if l.strip()]
        if len(lignes) > 1:
            trouve.append(("document", f"{len(lignes)} lignes"))
        elif any(c in texte for c in "{};<>=()"):
            trouve.append(("code", texte[:60]))
        else:
            trouve.append(("texte", texte[:60]))
    return trouve


@outil(
    nom="lire_presse_papiers",
    description="Lit le presse-papiers (ce que l'utilisateur vient de copier) "
                "et detecte ce que c'est : lien, email, telephone, code, texte. "
                "Pour 'qu'est-ce que j'ai copie ?', 'regarde mon copie-colle', "
                "'traite ce que je viens de copier'. LECTURE SEULE.",
    lent=False,
    phrase_attente="Je regarde ce que tu as copie.",
)
def lire_presse_papiers() -> str:
    """Le contenu du presse-papiers, classe, avec des propositions."""
    texte = _lire()
    if not texte:
        return ("Ton presse-papiers est vide ou inaccessible "
                "(copie quelque chose d'abord).")
    decouvertes = analyser(texte)
    if not decouvertes:
        return "Ton presse-papiers semble vide."
    morceaux = [f"{t} : {v}" for t, v in decouvertes[:5]]
    apercu = texte[:200] + ("..." if len(texte) > 200 else "")
    propositions = {
        "lien": "Veux-tu que je l'ouvre ou que je resume la page ?",
        "email": "Veux-tu que je prepare un mail pour cet adresse ?",
        "telephone": "Veux-tu que je l'ajoute a un contact ?",
        "code": "Veux-tu que je l'explique ou le corrige ?",
        "document": "Veux-tu que je le resume ?",
        "texte": "Veux-tu que je fasse quelque chose avec ?",
    }
    suggestion = propositions.get(decouvertes[0][0], "")
    return (f"Tu as copie ceci — {', '.join(morceaux)}. "
            f"Apercu : {apercu}. {suggestion}")
