"""Mode global MANUAL / AUTO (core/registre.py).

MANUAL : les compagnons demandent avant d'agir (tout N2/N3 confirme).
AUTO   : les compagnons agissent seuls — les N2 passent sans question.
Un N3 (suppressions, envois, argent, PC) demande TOUJOURS, dans les deux
modes, et le mode ne cree aucun droit a distance (pont iPhone inchange).
"""
import pytest

from core import registre
from core.config import definir_volatile


@pytest.fixture(autouse=True)
def config_isolee(tmp_path, monkeypatch):
    """Le mode persiste dans config.yaml : les tests ne touchent jamais le vrai."""
    from core import config
    monkeypatch.setattr(config, "FICHIER", tmp_path / "config.yaml")
    monkeypatch.setattr(config, "_CONFIG", {"securite": {"mode": "manual"}})
    yield


def test_mode_defaut_manual():
    definir_volatile("securite.mode", None)
    assert registre.mode() == "manual"


def test_mode_auto_accepte():
    assert registre.definir_mode("auto") == "auto"
    assert registre.mode() == "auto"
    assert registre.definir_mode("manual") == "manual"


def test_definir_mode_valeur_invalide_ne_change_rien():
    definir_volatile("securite.mode", "auto")
    assert registre.definir_mode("n'importe") == "auto"
    assert registre.definir_mode("") == "auto"


def test_definir_mode_persiste_sur_disque(tmp_path):
    from core import config
    registre.definir_mode("auto")
    assert (tmp_path / "config.yaml").exists()
    assert config.reglage("securite.mode") == "auto"


def test_demande_confirmation_par_outil():
    ecrire = registre.Outil(lambda **k: "ok", "classeurs_ecrire_cellule",
                            "outil de test N2", {}, True, False, None, None, False)
    envoyer = registre.Outil(lambda **k: "ok", "envoyer_mail",
                             "outil de test N3", {}, True, False, None, None, False)
    lire = registre.Outil(lambda **k: "ok", "lire_mails",
                          "outil de test N1", {}, False, False, None, None, False)
    registre._REGISTRE["classeurs_ecrire_cellule"] = ecrire
    registre._REGISTRE["envoyer_mail"] = envoyer
    registre._REGISTRE["lire_mails"] = lire
    try:
        # N1 : jamais de question, quel que soit le mode
        assert registre.demande_confirmation("lire_mails") is False

        # MANUAL : N2 et N3 demandent
        definir_volatile("securite.mode", "manual")
        assert registre.demande_confirmation("classeurs_ecrire_cellule") is True
        assert registre.demande_confirmation("envoyer_mail") is True

        # AUTO : N2 agit seul, N3 demande TOUJOURS
        definir_volatile("securite.mode", "auto")
        assert registre.demande_confirmation("classeurs_ecrire_cellule") is False
        assert registre.demande_confirmation("envoyer_mail") is True

        # N2 memorise "toujours autoriser" : plus de question meme en MANUAL
        definir_volatile("securite.mode", "manual")
        definir_volatile("securite.toujours", ["classeurs_ecrire_cellule"])
        assert registre.demande_confirmation("classeurs_ecrire_cellule") is False
        definir_volatile("securite.mode", "auto")
        assert registre.demande_confirmation("classeurs_ecrire_cellule") is False
    finally:
        del registre._REGISTRE["classeurs_ecrire_cellule"]
        del registre._REGISTRE["envoyer_mail"]
        del registre._REGISTRE["lire_mails"]


def test_suppressions_sont_n3():
    for nom in ("vider_poubelle", "automation_supprimer", "delete_event",
                "envoyer_mail", "mettre_a_la_corbeille", "call_with_message"):
        assert registre.est_n3(nom), f"{nom} doit rester N3 (demande toujours)"


def test_operator_expose_le_mode():
    from core import operator
    definir_volatile("securite.mode", "auto")
    assert operator.mode() == {"mode": "auto"}
    reponse = operator.changer_mode("manual")
    assert reponse["ok"] is True
    assert reponse["mode"] == "manual"
    assert registre.mode() == "manual"
