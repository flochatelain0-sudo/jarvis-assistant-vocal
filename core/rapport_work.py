"""Rapports type Mistral Work, partagés par tous les outils de la plateforme.

Un rapport Work, c'est trois choses, toujours garanties :
1. une analyse du CONTENU REEL (le LLM resume chaque element, avec les
   noms, dates et montants exacts — jamais d'invention) ;
2. une CARTE groupee dans la console (reutilise operator.carte_mails,
   le composant ChatPanel l'affiche deja : categories, resumes, actions,
   brouillons) ;
3. un resume vocal structure par groupes.

Repli deterministe obligatoire : si le LLM est indisponible ou renvoie
un JSON invalide, le rapport retombe sur les groupes fournis par l'outil
appelant — un rapport ne plante JAMAIS et ne reste JAMAIS sans affichage.
"""

import logging

LOG = logging.getLogger("jarvis.rapport_work")

_MAX_CARACTERES = 2500      # par element, transmis au LLM
_ELEMENTS_PAR_LOT = 6       # elements analyses par appel LLM

GROUPES = ("reponse", "attention", "info")


def _texte_blocs(reponse) -> str:
    return " ".join(
        b.text for b in reponse.blocs
        if getattr(b, "type", "") == "text" and getattr(b, "text", "")
    ).strip()


def analyser(consigne: str, elements: list) -> list:
    """Analyse LLM d'un lot d'elements : renvoie une liste de dicts
    {indice, groupe, resume, action, brouillon} bases sur le contenu reel.
    Liste vide en cas d'echec : l'appelant applique son repli deterministe.
    """
    from core import llm
    try:
        reponse = llm.llm().repondre(consigne, [], [])
        brut = _texte_blocs(reponse)
        import json
        debut, fin = brut.find("["), brut.rfind("]")
        if debut >= 0 and fin > debut:
            analyses = json.loads(brut[debut:fin + 1])
            if isinstance(analyses, list):
                return [a for a in analyses if isinstance(a, dict)]
    except Exception:
        LOG.exception("rapport_work : analyse LLM impossible, repli")
    return []


def consigne_analyse(titre_rapport: str, elements: list,
                     regles_groupe: str, demande_brouillon: bool) -> str:
    """Construit la consigne LLM standard d'un rapport Work."""
    modele_json = (
        '{"indice": <numero de l element>, "groupe": "A TRAITER | ATTENTION | INFO", '
        '"resume": "1-2 phrases fideles au contenu reel, en francais, avec les '
        'noms, dates et montants exacts", "action": "l action concrete a faire '
        '(ou Aucune action)", "brouillon": "reponse en francais prete a envoyer '
        'si groupe=A TRAITER, sinon chaine vide"}'
    )
    lignes = []
    for i, e in enumerate(elements):
        contenu = str(e.get("contenu") or "")[:_MAX_CARACTERES]
        lignes.append(
            f"### ELEMENT {i + 1}\n{e.get('titre', '')}\n{contenu}")
    return (
        f"Tu es l'assistant personnel de Florian. Tu prepares le rapport "
        f"« {titre_rapport} ». Analyse ces elements et renvoie UNIQUEMENT un "
        "tableau JSON (sans texte autour, sans bloc de code), un objet par "
        f"element, dans l'ordre, selon ce modele :\n"
        + modele_json + "\n\n"
        "Groupes : " + regles_groupe + "\n"
        + ("Propose un brouillon seulement pour les elements A TRAITER.\n"
           if demande_brouillon else "Brouillon : chaine vide partout.\n")
        + "Ne JAMAIS inventer de donnees absentes du contenu reel.\n\n"
        + "\n\n".join(lignes)
    )


def groupes_analyses(consigne: str, elements: list,
                     replis: dict = None) -> dict:
    """Analyse LLM par lots + repli deterministe. Renvoie un dict par element :
    {indice: {groupe, resume, action, brouillon}}. `replis` mappe l'indice vers
    le groupe deterministe local en cas d'echec LLM (defaut : « info »)."""
    replis = replis or {}
    analyses = {}
    for debut in range(0, len(elements), _ELEMENTS_PAR_LOT):
        lot = elements[debut:debut + _ELEMENTS_PAR_LOT]
        for a in analyser(consigne, lot):
            try:
                indice = int(a.get("indice", 0))
            except (TypeError, ValueError):
                continue
            if 1 <= indice <= len(lot):
                analyses[debut + indice - 1] = a
    resultats = {}
    for i in range(len(elements)):
        a = analyses.get(i) or {}
        resultats[i] = {
            "groupe": str(a.get("groupe", "")).strip().upper(),
            "resume": str(a.get("resume", "")).strip()[:400],
            "action": str(a.get("action", "")).strip()[:200],
            "brouillon": str(a.get("brouillon", "")).strip(),
            "repli": replis.get(i, "info") if not a else "",
        }
    return resultats


def carte(titre: str, correspondances: tuple, groupes: dict,
          resume_vocal=None) -> None:
    """Injecte la carte groupee dans la console. `correspondances` =
    ((cle, titre_carte, icone), ...) dans l'ordre d'affichage. `groupes` =
    {cle: [element, ...]} ou chaque element porte resume/action/brouillon.
    Jamais d'exception : le vocal continue meme si la page est fermee."""
    try:
        from core import operator
        categories = []
        for cle, titre_carte, icone in correspondances:
            elements = groupes.get(cle) or []
            if not elements:
                continue
            categories.append({
                "titre": titre_carte,
                "icone": icone,
                "mails": [{
                    "expediteur": str(e.get("expediteur") or e.get("titre")
                                     or "?")[:80],
                    "objet": str(e.get("objet") or "")[:120],
                    "detail": str(e.get("resume") or e.get("contenu", ""))[:200],
                    "action": str(e.get("action") or "")[:200],
                    "brouillon": str(e.get("brouillon") or "")[:400],
                } for e in elements[:10]],
            })
        if categories:
            operator.carte_mails({"titre": titre, "categories": categories})
    except Exception:
        LOG.exception("rapport_work : injection carte impossible")


def normaliser_groupe(groupe_llm: str, repli: str = "info") -> str:
    """Ramene le groupe renvoye par le LLM a un des 3 groupes standard ;
    si le LLM n'a rien dit de reconnaissable, renvoie le repli local."""
    g = str(groupe_llm or "").lower()
    if any(mot in g for mot in ("traiter", "repondre", "reponse", "action")):
        return "reponse"
    if any(mot in g for mot in ("attention", "verifier", "verifie", "urgent")):
        return "attention"
    if "info" in g:
        return "info"
    return repli or "info"
