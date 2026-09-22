"""The Brain (core/brain.py) : la memoire qui se remplit toute seule.

L'extraction est heuristique : zero token, zero latence. Les tests verifient
les motifs principaux, la deduplication, et surtout l'EXCLUSION des secrets —
un mot de passe ne doit JAMAIS atterrir dans la memoire.
"""

import pytest

from core import brain, memoire


@pytest.fixture(autouse=True)
def memoire_isolee(tmp_path, monkeypatch):
    """memory.json dans un tmp : les tests ne touchent jamais le vrai."""
    monkeypatch.setattr(memoire, "FICHIER", tmp_path / "memory.json")
    yield


def test_extrait_une_preference():
    retenus = brain.extraire("je prefere les reponses courtes")
    assert len(retenus) == 1
    categorie, cle, contenu = retenus[0]
    assert categorie == "preferences"
    assert "courtes" in contenu


def test_extrait_un_proche():
    retenus = brain.extraire("ma femme s appelle Lea")
    assert retenus, "le proche doit etre extrait"
    categorie, cle, contenu = retenus[0]
    assert categorie == "people"
    assert cle == "Lea"
    assert "femme" in contenu and "Lea" in contenu


def test_extrait_un_proche_avec_apostrophe():
    retenus = brain.extraire("mon pere est Bernard")
    assert retenus and retenus[0][1] == "Bernard"


def test_extrait_un_projet():
    retenus = brain.extraire("je travaille sur le lancement de la boutique")
    assert retenus and retenus[0][0] == "projects"


def test_ne_retient_pas_un_secret():
    assert brain.extraire("mon mot de passe est hunter2") == []
    assert brain.extraire("ma cle api est sk-12345") == []
    assert brain.extraire("mon iban est 1234 5678 9012 3456") == []


def test_ne_retient_pas_une_question_banale():
    assert brain.extraire("quel temps fait-il") == []
    assert brain.extraire("") == []


def test_nourrir_deduplique():
    assert brain.nourrir("je prefere les reponses courtes") == 1
    assert brain.nourrir("je prefere les reponses courtes") == 0   # deja su
    m = memoire.charger()
    assert len(m["preferences"]) == 1


def test_nourrir_persiste():
    brain.nourrir("ma femme s appelle Lea")
    m = memoire.charger()
    assert "Lea" in m["people"]


def test_vue_brain_pour_la_page():
    brain.nourrir("je prefere les reponses courtes")
    v = brain.vue_brain()
    assert all(k in v for k in ("preferences", "people", "projects", "facts"))
    assert v["preferences"] and "courtes" in v["preferences"][0]["contenu"]


def test_message_trop_long_ignore():
    assert brain.extraire("je prefere " + "x" * 500) == []
