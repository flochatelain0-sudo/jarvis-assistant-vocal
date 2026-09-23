"""Diagnostic monday.com : pourquoi le CRM tombe en « erreur API » ?

Utilisation :
    uv run python scripts/monday_docteur.py

Verifie en sequence : token present, tableau configure, reponse de l'API,
message d'erreur exact. Affiche la correction a faire dans config.yaml.
"""
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))


def main():
    from core.config import reglage
    from tools.monday import _requete, _tableau, _token

    token = _token()
    tableau = _tableau()
    print("=== Diagnostic monday.com ===")
    print(f"1. Token   : {'OK (' + str(len(token)) + ' caracteres)' if token else 'ABSENT'}")
    if not token:
        print("   -> ajoute monday.token dans config.yaml")
        return 1
    print(f"2. Tableau : {tableau or 'non configure (monday.tableau)'}")

    print("3. Appel API (boards)...")
    try:
        donnees, erreurs = _requete(
            "query { boards(limit: 50) { id name } }")
    except Exception as e:
        print(f"   ECHEC reseau/HTTP : {e}")
        return 1
    if erreurs:
        print(f"   ERREUR API : {erreurs}")
        msg = str(erreurs[0])
        if "not authenticated" in msg.lower() or "token" in msg.lower():
            print("   -> ton token monday est invalide ou expire : "
                  "monday.com > Administration > API > My access tokens")
        elif "board" in msg.lower():
            print("   -> monday.tableau ne designe pas un tableau valide :")
            for b in donnees.get("boards") or []:
                print(f"      {b.get('name')} (ID {b.get('id')})")
        return 1
    boards = donnees.get("boards") or []
    print(f"   OK — {len(boards)} tableau(x) visible(s) :")
    for b in boards[:15]:
        marque = "  <-- config actuelle" if str(b.get("id")) == str(tableau) else ""
        print(f"      {b.get('name')} (ID {b.get('id')}){marque}")
    if tableau and not any(str(b.get("id")) == str(tableau) for b in boards):
        print(f"\n   ATTENTION : monday.tableau = {tableau} n'est pas dans la "
              "liste ci-dessus. Corrige l'ID dans config.yaml.")
        return 1
    print("\nTout est bon cote monday. Si la page Operator affiche encore "
          "« erreur API », relance Jarvis — le cache se vide au redemarrage.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
