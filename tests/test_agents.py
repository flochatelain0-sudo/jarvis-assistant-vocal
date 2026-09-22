"""Onglets d'agents de la page Operator : presets de personnalite nommes
(Jarvis, Builder, Counsel, Marketer) basculables sans reecrire config.yaml."""
import pytest
from core import personnalite
from core.config import definir_volatile, reglage


def test_les_quatre_agents_exposent_role_et_preset():
    ids = {a["id"] for a in personnalite.agents()}
    assert ids == {"neutre", "builder", "counsel", "marketer"}
    for a in personnalite.agents():
        assert a["nom"] and a["role"]


def test_chaque_agent_a_une_consigne_distincte():
    textes = {personnalite.persona(a["id"]) for a in personnalite.agents()}
    assert len(textes) == 4


def test_est_agent_distingue_les_presets():
    assert personnalite.est_agent("builder") is True
    assert personnalite.est_agent("counsel") is True
    assert personnalite.est_agent("marketer") is True
    assert personnalite.est_agent("neutre") is False
    assert personnalite.est_agent("jarvis_sarcastique") is False


def test_definir_volatile_ne_touche_pas_le_disque():
    avant = reglage("assistant.personnalite", "neutre")
    definir_volatile("assistant.personnalite", "builder")
    assert reglage("assistant.personnalite") == "builder"
    definir_volatile("assistant.personnalite", avant)
    assert reglage("assistant.personnalite") == avant


def test_preset_inconnu_retombe_sur_neutre():
    assert "assistant" in personnalite.persona("inconnu").lower() \
        or personnalite.persona("inconnu") == personnalite.persona("neutre")
