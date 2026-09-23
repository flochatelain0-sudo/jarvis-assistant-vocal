"""Veille concurrentielle : recherche web + extraction de prix sur page ouverte.

Toute l'intelligence part de donnees REELLES :
- chercher_web (tools/web.py) pour la recherche DuckDuckGo ;
- le navigateur pilote (tools/navigateur.py) pour lire la page ouverte ;
- un extracteur de prix deterministe (regex EUR/USD/$) sur le texte reel
  de la page — jamais de tarif invente.

Chaque veille est journalisee dans l'operateur (categorie crm), donc
visible dans le dashboard « Pendant que tu dormais ».
"""

import re
import time
from urllib.parse import urlparse

from core.registre import outil

# Prix : 12,99 € / €12.99 / $12.99 / 12.99 USD / 1 299,00 €
_MOTIF_PRIX = re.compile(
    r"(?:€\s?\$?\s?)?(\d{1,3}(?:[ \u202f,]\d{3})*(?:[.,]\d{1,2})?)\s?(?:€|EUR|euros?\b|\$|USD\b)"
)
_MOTIF_PRIX_DOLLAR = re.compile(r"\$\s?(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?)")


def extraire_prix(texte: str) -> list[float]:
    """Extrait les prix reels d'un texte, en euros ou dollars, dedupliques."""
    trouves: list[float] = []
    for motif in (_MOTIF_PRIX, _MOTIF_PRIX_DOLLAR):
        for brut in motif.findall(str(texte or "")):
            propre = brut.replace("\u202f", "").replace(" ", "")
            if "." in propre and "," in propre:
                # 1,299.00 (format US) ou 1.299,00 (format EU) : le dernier gagne
                if propre.rfind(",") > propre.rfind("."):
                    propre = propre.replace(".", "").replace(",", ".")
                else:
                    propre = propre.replace(",", "")
            elif "," in propre:
                propre = propre.replace(",", ".")
            try:
                valeur = round(float(propre), 2)
            except ValueError:
                continue
            if 0.01 <= valeur <= 1_000_000 and valeur not in trouves:
                trouves.append(valeur)
    trouves.sort()
    return trouves


def _resume_prix(prix: list[float]) -> str:
    if not prix:
        return "aucun prix detecte sur la page"
    return (
        f"{len(prix)} prix detectes : min {prix[0]:.2f}, "
        f"max {prix[-1]:.2f}, median {prix[len(prix) // 2]:.2f}"
    )


@outil(
    nom="surveiller_concurrent",
    description=(
        "Analyse la page concurrente ouverte dans Chrome : prix reels, titres "
        "de produits, et resume du positionnement. Alimente le dashboard."
    ),
    lent=True,
    phrase_attente="J'analyse la page concurrente.",
)
def surveiller_concurrent() -> str:
    """Analyse l'onglet actif via le navigateur pilote (lecture seule)."""
    from tools import navigateur

    browser = navigateur._connexion()
    if browser is None:
        return (
            "Je n'ai pas acces a Chrome. Ouvre la page du concurrent "
            "(ou demande-le-moi) et relance l'analyse."
        )
    try:
        page = navigateur._page_active(browser)
    except Exception:
        return "Aucune page ouverte dans le navigateur pilote."
    if page is None:
        return "Aucune page ouverte dans le navigateur pilote."

    try:
        titre = page.title() or ""
        url = page.url or ""
        texte = page.evaluate("document.body ? document.body.innerText : ''") or ""
    except Exception as erreur:
        return f"Lecture de la page impossible : {erreur}"

    domaine = urlparse(url).netloc.replace("www.", "")
    prix = extraire_prix(texte)
    lignes = [f"{titre} ({domaine}). {_resume_prix(prix)}."]

    titres = page.evaluate(
        "Array.from(document.querySelectorAll('h1, h2')).map(h => h.innerText.trim()).filter(t => t && t.length < 120).slice(0, 6)"
    ) or []
    for t in titres:
        lignes.append(f"• {t}")

    _journal_veille(f"veille {domaine}", _resume_prix(prix))
    return "\n".join(lignes)


@outil(
    nom="veille_marche",
    description=(
        "Lance une recherche de veille sur un sujet concurrent (tarifs, "
        "lancement, positionnement) et renvoie les resultats web reels."
    ),
    lent=True,
    phrase_attente="Je lance la veille marche.",
)
def veille_marche(sujet: str) -> str:
    """Recherche web reelle via l'outil existant, puis journalisation."""
    from tools.web import chercher_web

    sujet = str(sujet or "").strip()
    if not sujet:
        return "Précise le sujet de la veille (ex. « tarifs des agences SEA 2026 »)."

    resultats = chercher_web(f"{sujet} veille concurrentielle tarifs")
    _journal_veille(f"veille {sujet[:60]}", resultats[:200])
    return f"Veille « {sujet} » :\n{resultats}"


def _journal_veille(titre: str, detail: str) -> None:
    """Trace la veille dans le journal operateur (dashboard)."""
    try:
        from core import operator
        operator.journaliser("crm", titre, detail[:380], "veille")
    except Exception:  # pragma: no cover - la veille ne doit jamais echouer sur le journal
        pass
