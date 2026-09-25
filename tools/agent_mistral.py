"""Delegation a l'agent Mistral AI (Agents API, outils SERVEUR).

Troisieme cerveau, volontairement SPECIALISE, a cote de Jarvis (boucle
vocale interactive, API directe) et d'Hermes (reflexion locale) :

  - Jarvis garde la boucle temps reel : ecouter -> Mistral (API directe)
    -> lire/ecrire la reponse, avec TOUS les outils locaux (Chrome, souris,
    CRM monday) sous confirmation vocale.
  - L'agent Mistral prend le relais pour les taches qui profitent d'OUTILS
    SERVEUR : recherche web profonde multi-sources, synthese documentaire,
    veille concurrentielle, comparaisons. Les connecteurs (web_search,
    code_interpreter...) s'executent COTE MISTRAL, sans toucher a ta
    machine : aucune action locale, donc aucun risque de contourner la
    doctrine de confirmation.

FLUX (meme schéma que deleguer_a_hermes) :
  1. Jarvis repond TOUT DE SUITE « je confie ca a l'agent Mistral » ;
  2. en tache de fond : POST /v1/agents/completions (agent_id preconfigure
     dans config.yaml, sinon mode direct model + connecteurs web_search) ;
  3. le resultat revient TOUJOURS dans la boucle locale : resume lu a voix
     haute (filtre confidentialite), ecrit dans l'overlay, journalise dans
     logs/agent_mistral/ — et une carte console si le resultat est structuré.

SECURITE :
  - tache et resultat passes par core.confidentialite (caviardage fichier,
    filtre vocal) : la meme doctrine que Hermes ;
  - mcp_expose=False : jamais declenchable a distance ;
  - aucun outil LOCAL n'est transmis a l'agent : il ne peut pas toucher
    Chrome, la souris, le clavier ou le CRM ; il ne produit que du TEXTE ;
  - repli : sans cle Mistral ou sans reseau, Jarvis le dit clairement.
"""

import json
import logging
import threading
import time
from datetime import datetime
from pathlib import Path

from core import voix, confidentialite
from core.config import reglage
from core.registre import outil
from core.util import sans_accents

try:
    import truststore
    truststore.inject_into_ssl()
except Exception:
    pass

import requests

LOG = logging.getLogger("jarvis.agent_mistral")

_DOSSIER = Path(__file__).resolve().parent.parent / "logs" / "agent_mistral"
_MAX_CARACTERES_TACHE = 4000


def _cle() -> str:
    return str(reglage("mistral.cle", "") or "").strip()


def agent_disponible() -> bool:
    """Vrai si la delegation a l'agent Mistral est possible (cle + id/model)."""
    return bool(_cle()) and bool(_identite())


def _identite() -> dict:
    """Agent preconfigure (agent_id) ou mode direct (model + connecteurs)."""
    agent_id = str(reglage("agent_mistral.agent_id", "") or "").strip()
    if agent_id:
        return {"agent_id": agent_id}
    modele = str(reglage("agent_mistral.modele",
                          "mistral-small-latest") or "").strip()
    return {"model": modele}


def _connecteurs() -> list:
    """Connecteurs SERVEUR actives pour le mode direct (rien de local)."""
    if str(reglage("agent_mistral.agent_id", "") or "").strip():
        return []                      # l'agent porte deja ses outils
    actifs = reglage("agent_mistral.connecteurs", ["web_search"]) or []
    return [{"type": str(c)} for c in actifs]


def _appeler(tache: str) -> str:
    """Un appel complet a l'Agents API. Renvoie le texte final ou leve."""
    cle = _cle()
    if not cle:
        raise RuntimeError("cle Mistral absente (mistral.cle)")
    base = str(reglage("mistral.url", "https://api.mistral.ai/v1") or "")
    base = base.rstrip("/").replace("/v1", "") + "/v1"
    corps = {
        "messages": [{"role": "user", "content": tache[:_MAX_CARACTERES_TACHE]}],
        **_identite(),
    }
    connecteurs = _connecteurs()
    if connecteurs:
        corps["tools"] = connecteurs
    reponse = requests.post(
        f"{base}/agents/completions",
        headers={"Authorization": f"Bearer {cle}",
                 "Content-Type": "application/json"},
        data=json.dumps(corps), timeout=int(reglage("agent_mistral.timeout", 300)),
    )
    if reponse.status_code != 200:
        raise RuntimeError(f"API Mistral {reponse.status_code} : "
                           f"{reponse.text[:200]}")
    donnees = reponse.json()
    choix = (donnees.get("choices") or [{}])[0]
    message = choix.get("message") or {}
    contenu = str(message.get("content") or "").strip()
    if not contenu:
        raise RuntimeError("reponse de l'agent vide")
    return contenu


def _journaliser(tache: str, resultat: str) -> None:
    """Archive caviardee de la delegation (meme retention que Hermes)."""
    try:
        import shutil
        retention = max(0, int(reglage("agent_mistral.retention_jours", 30)))
        _DOSSIER.mkdir(parents=True, exist_ok=True)
        if retention:
            limite = time.time() - retention * 86400
            for ancien in _DOSSIER.glob("delegation-*.md"):
                try:
                    if ancien.stat().st_mtime < limite:
                        ancien.unlink()
                except OSError:
                    pass
        horo = datetime.now().strftime("%Y%m%d-%H%M%S")
        tache_sure = confidentialite.caviarder(tache)
        resultat_sur = confidentialite.caviarder(resultat)
        (_DOSSIER / f"delegation-{horo}.md").write_text(
            f"# Delegation agent Mistral {horo}\n\n## Tache\n{tache_sure}\n\n"
            f"## Resultat\n{resultat_sur}\n", encoding="utf-8")
    except Exception:
        LOG.exception("agent_mistral : journalisation impossible")


def _resume_vocal(resultat: str, max_car: int = 500) -> str:
    """Version courte du resultat pour la voix : premiers paragraphes,
    sans casser une phrase au milieu."""
    texte = " ".join((resultat or "").split())
    if len(texte) <= max_car:
        return texte
    coupe = texte[:max_car]
    point = max(coupe.rfind("."), coupe.rfind("!"), coupe.rfind("?"))
    return (coupe[:point + 1] if point > max_car // 2
            else coupe.rsplit(" ", 1)[0] + "...")


def deleguer_en_fond(tache: str) -> str:
    """Delegue en tache de fond ; accuse immediat, resultat vocal + ecran."""
    tache = (tache or "").strip()
    if not tache:
        return "Je n'ai pas compris la tache a confier a l'agent Mistral."

    def worker():
        try:
            resultat = _appeler(tache)
            _journaliser(tache, resultat)
            resume = confidentialite.filtrer(
                _resume_vocal(resultat,
                              int(reglage("agent_mistral.resume_max", 500))))
            voix.parler("L'agent Mistral a termine. " + resume)
            try:
                import overlay
                overlay.afficher(resume, type="reponse")
            except Exception:
                pass
        except Exception as e:
            voix.parler("La delegation a l'agent Mistral a echoue. "
                        + confidentialite.filtrer(str(e), 120))

    threading.Thread(target=worker, daemon=True,
                     name="deleguer-agent-mistral").start()
    return ("Je confie ca a l'agent Mistral (recherche web et synthese cote "
            "serveur). Je te previens des que c'est pret.")


@outil(
    nom="deleguer_agent_mistral",
    description=(
        "Confie une tache de RECHERCHE WEB PROFONDE, de VEILLE, de SYNTHESE "
        "ou d'ANALYSE MULTI-SOURCES a l'agent Mistral AI (Agents API). Ses "
        "outils (recherche web, execution de code) tournent COTE SERVEUR : "
        "il ne touche jamais a ta machine, il ne produit que du texte, et "
        "le resultat te est lu a voix haute et affiche. A appeler DE "
        "TOI-MEME pour 'demande a l'agent Mistral', 'fais une recherche "
        "profonde sur...', 'veille sur la concurrence', 'compare et "
        "synthetise...'. NE PAS utiliser pour une question simple, ni pour "
        "une action locale (ouvrir Chrome, ecrire dans le CRM, cliquer)."
    ),
    parametres={
        "type": "object",
        "properties": {
            "tache": {"type": "string",
                      "description": "La tache a confier, formulee clairement, "
                                     "avec le contexte et le livrable attendu."},
        },
        "required": ["tache"],
    },
    lent=True,
    phrase_attente="Je confie ca a l'agent Mistral.",
    mcp_expose=False,
)
def deleguer_agent_mistral(tache: str) -> str:
    """Delegation arriere-plan a l'agent Mistral (outils serveur)."""
    return deleguer_en_fond(tache)


def router_agent_mistral(phrase: str, piece: str = ""):
    """Route deterministe : les demandes explicites a l'agent Mistral
    declenchent l'outil sans improvisation du LLM. Renvoie (nom_outil,
    arguments) ou None."""
    p = sans_accents(str(phrase or "").lower())
    if not any(mot in p for mot in ("mistral", "agent")):
        return None
    if not any(mot in p for mot in ("delegue", "deleguer", "demande a",
                                    "demande ", "lance", "confie",
                                    "fais une recherche profonde",
                                    "recherche de fond", "veille")):
        return None
    return "deleguer_agent_mistral", {"tache": str(phrase or "").strip()}
