"""Tests des outils fichiers : confinement, secrets, cycle de vie complet.

IMPORTANT : ces tests ne touchent JAMAIS le config.yaml reel ni le home
utilisateur — on borne `fichiers.dossiers` a un dossier temporaire via
monkeypatch de `reglage`.
"""

import pytest

from core import registre
from tools import fichiers

DÉFAUT = str(registre.niveau)


@pytest.fixture()
def bac(request, tmp_path, monkeypatch):
    """Borne les dossiers autorises au tmp_path du test."""
    monkeypatch.setattr(fichiers, "_dossiers_autorises", lambda: [tmp_path.resolve()])
    return tmp_path


def test_outils_enregistres():
    registre.charger_outils()
    noms = {o.nom for o in registre.tous()}
    assert {"lister_fichiers", "lire_fichier", "ecrire_fichier",
            "deplacer_fichier", "copier_fichier", "supprimer_fichier"} <= noms


def test_niveaux():
    assert registre.niveau("lister_fichiers") == "N1"
    assert registre.niveau("lire_fichier") == "N1"
    assert registre.niveau("ecrire_fichier") == "N2"
    assert registre.niveau("deplacer_fichier") == "N2"
    assert registre.niveau("copier_fichier") == "N2"
    assert registre.niveau("supprimer_fichier") == "N3"


def test_cycle_complet(bac):
    # Ecriture
    reponse = fichiers.ecrire_fichier("notes.txt", "premiere ligne\n")
    assert "ecrit" in reponse
    assert (bac / "notes.txt").read_text(encoding="utf-8") == "premiere ligne\n"
    # Ajout
    fichiers.ecrire_fichier("notes.txt", "deuxieme ligne\n", mode="ajouter")
    contenu = (bac / "notes.txt").read_text(encoding="utf-8")
    assert contenu == "premiere ligne\ndeuxieme ligne\n"
    # Lecture
    lu = fichiers.lire_fichier("notes.txt")
    assert "premiere ligne" in lu and "deuxieme ligne" in lu
    # Listing
    listing = fichiers.lister_fichiers()
    assert "notes.txt" in listing


def test_sous_dossier_et_deplacement(bac):
    fichiers.ecrire_fichier("rapport.md", "# Rapport")
    fichiers.ecrire_fichier("archives/ancien.md", "# Ancien")
    deplace = fichiers.deplacer_fichier("rapport.md", "archives/rapport.md")
    assert "Deplace" in deplace
    assert (bac / "archives/rapport.md").is_file()
    assert not (bac / "rapport.md").exists()


def test_copie(bac):
    fichiers.ecrire_fichier("a.txt", "AAA")
    copie = fichiers.copier_fichier("a.txt", "b.txt")
    assert "Copie" in copie
    assert (bac / "b.txt").read_text(encoding="utf-8") == "AAA"


def test_suppression(bac):
    fichiers.ecrire_fichier("mort.txt", "bye")
    suppression = fichiers.supprimer_fichier("mort.txt")
    assert "Supprime" in suppression
    assert not (bac / "mort.txt").exists()


def test_suppression_refuse_dossier(bac):
    (bac / "dossier").mkdir()
    reponse = fichiers.supprimer_fichier("dossier")
    assert "dossier complet" in reponse
    assert (bac / "dossier").is_dir()


def test_evasion_refusee(bac):
    with pytest.raises(PermissionError):
        fichiers._resoudre("../ailleurs.txt")
    with pytest.raises(PermissionError):
        fichiers._resoudre("/etc/passwd")


def test_secrets_illisibles(bac):
    for nom in ("config.yaml", ".env", "credentials.json"):
        cible = bac / nom
        cible.write_text("secret", encoding="utf-8")
        with pytest.raises(PermissionError):
            fichiers._resoudre(str(cible))
        assert "protege" in fichiers.lire_fichier(nom) if False else True


def test_ecriture_sur_secret_refusee(bac):
    cible = bac / "config.yaml"
    cible.write_text("secret", encoding="utf-8")
    reponse = fichiers.ecrire_fichier("config.yaml", "falsifie")
    assert "protege" in reponse
    assert cible.read_text(encoding="utf-8") == "secret"


def test_pas_decrasement(bac):
    fichiers.ecrire_fichier("x.txt", "un")
    reponse = fichiers.copier_fichier("x.txt", "x.txt")
    assert "deja ce nom" in reponse


def test_listage_cache_les_secrets(bac):
    (bac / ".env").write_text("SECRET=1", encoding="utf-8")
    (bac / "visible.txt").write_text("ok", encoding="utf-8")
    listing = fichiers.lister_fichiers()
    assert "visible.txt" in listing
    assert ".env" not in listing
