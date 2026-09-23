"""Buts (core/buts.py) + Integrations (core/integrations.py).

Les buts de la console ZOEY OS sont persistes dans data/buts.json ; leur
statut se DEDUIT des integrations reellement connectees — rien de simule.
Les integrations lisent config.yaml et les jetons, elles ne creent aucun
droit nouveau.
"""
import pytest

from core import buts, integrations
from core.config import definir_volatile


@pytest.fixture(autouse=True)
def donnees_isolees(tmp_path, monkeypatch):
    """buts.json isole : les tests ne touchent jamais le vrai fichier."""
    monkeypatch.setattr(buts, "_FICHIER", tmp_path / "buts.json")
    monkeypatch.setattr(buts, "_BUTS", None)
    yield


@pytest.fixture
def sans_config():
    """Une config vide : aucune integration configuree."""
    avant_mail = definir_volatile("mail.adresse", "")
    avant_mdp = definir_volatile("mail.mot_de_passe_app", "")
    avant_oauth = definir_volatile("mail.oauth", False)
    yield
    definir_volatile("mail.adresse", avant_mail)
    definir_volatile("mail.mot_de_passe_app", avant_mdp)
    definir_volatile("mail.oauth", avant_oauth)


def test_modele_seme_une_seule_fois():
    assert buts.initialiser_modele() is True
    n = len(buts.lister())
    assert n == 6
    assert buts.initialiser_modele() is False      # idempotent
    assert len(buts.lister()) == n


def test_les_six_buts_du_modele_sont_bien_la():
    buts.initialiser_modele()
    titres = [b["titre"] for b in buts.lister()]
    assert "Get my inbox and calendar under control" in titres
    assert "Keep family logistics off my mind" in titres
    for b in buts.lister():
        assert b["statut"] in ("JUST SET", "IN PROGRESS", "DONE")
        assert isinstance(b["requis"], list)


def test_ajouter_but_sans_titre_refuse():
    assert buts.ajouter("   ") is None
    assert buts.ajouter("") is None


def test_ajouter_et_supprimer():
    but = buts.ajouter("Tester mes emails", ["gmail"])
    assert but is not None and but["titre"] == "Tester mes emails"
    assert but["requis"][0]["id"] == "gmail"
    assert buts.supprimer(but["id"]) is True
    assert buts.supprimer(but["id"]) is False


def test_requis_inconnu_ignored():
    but = buts.ajouter("But bizarre", ["gmail", "pas_une_integration"])
    assert [r["id"] for r in but["requis"]] == ["gmail"]


def test_statut_suivra_les_integrations(sans_config):
    """Sans config mail, le but Gmail reste JUST SET ; branche le mail
    (adresse + mdp) et il passe IN PROGRESS (gcal requis manque)."""
    but = buts.ajouter("Inbox sous controle", ["gmail", "gcal"])
    assert but["statut"] == "JUST SET"
    definir_volatile("mail.adresse", "moi@gmail.com")
    definir_volatile("mail.mot_de_passe_app", "abcd efgh ijkl mnop")
    vue = [b for b in buts.lister() if b["id"] == but["id"]][0]
    assert vue["statut"] == "IN PROGRESS"
    assert vue["requis"][0]["connecte"] is True
    assert vue["requis"][1]["connecte"] is False


def test_integrations_ne_levent_jamais():
    etat = integrations.etat()
    assert isinstance(etat, dict) and len(etat) >= 8
    for v in etat.values():
        assert set(v.keys()) == {"id", "nom", "connecte", "detail"}


def test_gmail_non_configure_sans_config(sans_config):
    etat = integrations.etat()
    assert etat["gmail"]["connecte"] is False
    assert "config.yaml" in etat["gmail"]["detail"]


def test_gmail_configure_via_mdp(sans_config):
    definir_volatile("mail.adresse", "moi@gmail.com")
    definir_volatile("mail.mot_de_passe_app", "abcd efgh ijkl mnop")
    assert integrations.est_connecte("gmail") is True


def test_est_connecte_inconnu_est_false():
    assert integrations.est_connecte("nimporte") is False


def test_etat_operator_expose_buts_et_integrations(sans_config, tmp_path, monkeypatch):
    from core import operator
    monkeypatch.setattr(operator, "_JOURNAL", tmp_path / "journal.json")
    monkeypatch.setattr(operator, "_ENTREES", None)
    etat = operator.etat()
    assert "buts" in etat and len(etat["buts"]) == 6
    assert "integrations" in etat and "gmail" in etat["integrations"]
