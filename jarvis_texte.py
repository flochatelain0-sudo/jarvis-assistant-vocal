"""Jarvis en mode texte : remplace la boucle vocale quand il n'y a pas de materiel audio.

Meme pipeline que la voix (routage, outils, confirmations N2/N3, garde-fous) :

- openWakeWord + Whisper  -> une ligne tapee au clavier (input)
- TTS (Piper/Kokoro/OS)   -> la console (print)

Utile aussi pour un serveur sans micro (Docker, VPS, test). Usage :

    uv run python jarvis_texte.py

Le reste est importe de jarvis14 : rien n'est duplique, on reutilise
repondre(), le registre, la memoire, les serveurs web. Les commandes
d'arret : "quit", "exit", Ctrl+C. Toute action en attente de
confirmation (N2/N3) se valide par "oui" (ou "oui, toujours" pour
memoriser l'autorisation d'un N2), "non" pour refuser.
"""

import jarvis14 as jarvis
from core import memoire, registre
from core.llm import llm


def main():
    print("Chargement des modeles et outils...")
    registre.charger_outils()

    fournisseur = llm()
    if not fournisseur.disponible():
        print(f"ATTENTION : le LLM {fournisseur.nom} n'est pas joignable "
              "(mode local : lance 'ollama serve' et verifie ollama.modele).")
    else:
        print(f"LLM actif : {fournisseur.nom} ({getattr(fournisseur, 'modele', '')}).")

    faits = memoire.charger()
    if faits:
        print(f"Memoire : {len(faits)} information(s).")
    jarvis._refaire_systeme(faits)
    jarvis.voix.definir_parleur(lambda texte: print(f"  [TTS] {texte}"))

    # Serveur web unifie (Operator/panneau en loopback) : utile meme sans micro.
    try:
        from core import serveur as serveur_web
        serveur_web.demarrer()
        print("Serveur web : http://127.0.0.1:8790/operator (loopback).")
    except Exception:
        pass

    historique = []
    jarvis.demarrer_drain_ecrit(historique)   # messages de la page Operator

    print('\nJarvis texte pret. Tape ta phrase ("quit" pour sortir).\n')
    while True:
        try:
            demande = input("Vous : ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nAu revoir.")
            break
        if not demande:
            continue
        if demande.lower() in ("quit", "exit"):
            print("Au revoir.")
            break
        # Toute action en attente de confirmation (N2/N3) se valide par
        # oui/non. "oui, toujours" memorise l'autorisation d'un N2 (comme
        # la voix) ; un N3 refuse la memorisation mais agit pour ce tour.
        p = demande.lower()
        if p.startswith(("oui", "ok", "vas-y", "vas y", "confirme",
                         "d'accord", "daccord")):
            if registre.file_en_attente():
                resultat = registre.executer_confirme(
                    memoriser="toujours" in p)
                print("  Jarvis : " + (resultat or "C'est fait.") + "\n")
                continue
        texte, _ = jarvis.traiter_ecrit(demande, historique)
        if not texte:
            print("  Jarvis : C'est fait.\n")


if __name__ == "__main__":
    main()
