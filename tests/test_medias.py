"""Tests medias : validation des sources, replis lecteur, arret."""

from pathlib import Path

import pytest

from tools import medias


@pytest.fixture()
def bac(tmp_path, monkeypatch):
    monkeypatch.setattr("tools.fichiers._dossiers_autorises", lambda: [tmp_path.resolve()])
    return tmp_path


def test_enregistres():
    from core import registre
    registre.charger_outils()
    for nom in ("jouer_media", "arreter_media", "controler_lecture"):
        assert registre.niveau(nom) == "N1"


def test_source_locale_valide(bac):
    fichier = bac / "clip.mp4"
    fichier.write_bytes(b"00")
    assert medias._source_valide("clip.mp4") == str(fichier)


def test_source_inexistante(bac):
    with pytest.raises(FileNotFoundError):
        medias._source_valide("introuvable.mp4")


def test_source_hors_zone(bac):
    with pytest.raises(PermissionError):
        medias._source_valide("/etc/passwd")


def test_url_valide():
    assert medias._source_valide("https://exemple.fr/video.mp4").startswith("https://")


def test_url_avec_espace():
    with pytest.raises(ValueError):
        medias._source_valide("https://exemple.fr/ma video.mp4")


def test_jouer_fichier_absent_message_clair(bac):
    reponse = medias.jouer_media("nulle-part.mp4")
    assert "n'existe pas" in reponse


def test_jouer_url_lance_lecteur(monkeypatch):
    appels = []
    monkeypatch.setattr(medias, "_lecteurs_disponibles", lambda: ["vlc"])
    monkeypatch.setattr(medias.subprocess, "Popen", lambda args, **kw: appels.append(args))
    reponse = medias.jouer_media("https://exemple.fr/v.mp4")
    assert "vlc" in reponse
    assert appels and appels[0][-1] == "https://exemple.fr/v.mp4"


def test_repli_sans_lecteur(monkeypatch):
    appels = []
    monkeypatch.setattr(medias, "_lecteurs_disponables", lambda: [], raising=False)
    monkeypatch.setattr(medias, "_lecteurs_disponibles", lambda: [])
    monkeypatch.setattr(medias.plateforme, "ouvrir", lambda c: appels.append(c))
    reponse = medias.jouer_media("https://exemple.fr/v.mp4")
    assert "lecteur par defaut" in reponse
    assert appels == ["https://exemple.fr/v.mp4"]


def test_arreter_sans_lecture():
    # sandbox : aucun vlc/mpv lance, on doit obtenir le message d'absence
    reponse = medias.arreter_media()
    assert ("arretee" in reponse) or ("Aucune" in reponse)
