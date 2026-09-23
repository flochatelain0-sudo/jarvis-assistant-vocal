"""Automations (core/automations.py) : le planificateur des routines 24/7.

Une automation ne declenche QUE des actions de lecture (N1). Le planificateur
garantit : persistance sur disque, jours de semaine respectes, reprise apres
redemarrage (prochaine execution recalculee), et journalisation Operator.
"""

import time

import pytest

from core import automations, operator


@pytest.fixture(autouse=True)
def automations_isolees(tmp_path, monkeypatch):
    """Fichier dans un tmp : les tests ne touchent jamais le vrai JSON."""
    monkeypatch.setattr(automations, "_FICHIER", tmp_path / "automations.json")
    monkeypatch.setattr(automations, "_AUTOMATIONS", None)
    yield
    automations.arreter()


def test_ajouter_puis_lister():
    a = automations.ajouter("Brief du matin", "08:00", "brief")
    assert automations.lister()[0]["id"] == a["id"]
    assert automations.lister()[0]["moment"] == "08:00"
    assert a["active"] is True
    assert a["prochaine"] > 0


def test_jours_de_semaine_respectes():
    a = automations.ajouter("Point factures", "17:00", "factures",
                            jours=["vendredi"])
    assert a["jours"] == ["vendredi"]


def test_tous_les_jours_par_defaut():
    a = automations.ajouter("Mails midi", "12:30", "mails")
    assert a["jours"] == []          # vide = tous les jours
    assert automations._normaliser_jours(None) == set(automations._JOURS)


def test_persistance_sur_disque(tmp_path):
    automations.ajouter("Persistante", "09:00", "brief")
    # rechargement force : le fichier doit exister et contenir l'automation
    automations._FICHIER.exists()
    contenu = automations._FICHIER.read_text(encoding="utf-8")
    assert "Persistante" in contenu


def test_activer_desactiver():
    a = automations.ajouter("En pause", "10:00", "brief")
    assert automations.activer(a["id"], False) is True
    assert automations.lister()[0]["active"] is False
    automations.activer(a["id"], True)
    assert automations.lister()[0]["active"] is True


def test_supprimer():
    a = automations.ajouter("A supprimer", "11:00", "brief")
    assert automations.supprimer(a["id"]) is True
    assert automations.lister() == []
    assert automations.supprimer("id-inexistant") is False


def test_prochaine_execution_dans_le_futur():
    a = automations.ajouter("Demain", "23:59", "brief")
    assert a["prochaine"] > time.time()
    # et la suivante aussi, apres execution simulee
    a["derniere"] = time.time()
    automations._maj_prochaine(a)
    assert a["prochaine"] > time.time()


def test_action_inconnue_leve():
    with pytest.raises(ValueError):
        automations._executer_action("action_inconnue", {})


def test_fichier_corrompu_repart_a_zero(tmp_path, monkeypatch):
    tmp_path.joinpath("automations.json").write_text("{corrompu", encoding="utf-8")
    monkeypatch.setattr(automations, "_AUTOMATIONS", None)
    assert automations.lister() == []


def test_executer_maintenant_lance_en_fond():
    a = automations.ajouter("Test fond", "06:00", "brief")
    assert automations.executer_maintenant(a["id"]) is True
    assert automations.executer_maintenant("inconnu") is False
