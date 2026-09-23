"""Mode d'action MANUAL / AUTO (core/registre.py, doctrine de la console).

La console affiche : MANUAL = chaque action sensible demande ; AUTO = Jarvis
agit seul SAUF N3 (envois, suppressions, argent, PC) qui demande TOUJOURS.
doit_confirmer() est LA doctrine, un seul endroit pour toutes les surfaces
(voix bureau, satellite, page Operator).
"""
import pytest

from core import registre
from core.config import definir, reglage


@pytest.fixture(autouse=True)
def mode_reinitialise():
    definir("securite.autopilote", "manual")
    yield
    definir("securite.autopilote", "manual")


def test_mode_defaut_manual():
    assert registre.mode_autopilote() == "manual"


def test_definir_mode_persiste_et_normalise():
    assert registre.definir_mode_autopilote("AUTO") == "auto"
    assert registre.mode_autopilote() == "auto"
    assert reglage("securite.autopilote") == "auto"
    definir("securite.autopilote", "manual")
    assert registre.definir_mode_autopilote("n'importe quoi") == "manual"


def test_n1_ne_demande_jamais_meme_en_manual():
    registre._REGISTRE["outilsur"] = registre.Outil(
        lambda **k: "ok", "outilsur", "N1 de test", {}, False, False, None,
        None, False, "auto")
    try:
        assert registre.doit_confirmer("outilsur") is False
        registre.definir_mode_autopilote("auto")
        assert registre.doit_confirmer("outilsur") is False
    finally:
        registre._REGISTRE.pop("outilsur", None)


def test_n3_demande_toujours_meme_en_auto():
    # envoyer_mail est N3 (verrouille) : aucun mode ne l'autonomise.
    registre._REGISTRE["envoyer_mail"] = registre.Outil(
        lambda **k: "ok", "envoyer_mail", "N3 de test", {}, True, False, None,
        None, False, "auto")
    try:
        assert registre.doit_confirmer("envoyer_mail") is True
        registre.definir_mode_autopilote("auto")
        assert registre.doit_confirmer("envoyer_mail") is True
    finally:
        registre._REGISTRE.pop("envoyer_mail", None)


def test_n2_demande_en_manual_agit_en_auto():
    registre._REGISTRE["outilsensible"] = registre.Outil(
        lambda **k: "ok", "outilsensible", "N2 de test", {}, True, False, None,
        None, False, "auto")
    try:
        # MANUAL : confirmation requise (pas de 'toujours autoriser')
        assert registre.doit_confirmer("outilsensible") is True
        # AUTO : Jarvis agit seul
        registre.definir_mode_autopilote("auto")
        assert registre.doit_confirmer("outilsensible") is False
    finally:
        registre._REGISTRE.pop("outilsensible", None)
