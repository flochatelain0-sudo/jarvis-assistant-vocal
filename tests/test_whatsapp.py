"""WhatsApp (tools/whatsapp.py) : normalisation des numeros, config manquante,
outil enregistre au registre avec confirmation N3."""
import pytest

from core import registre
from tools import whatsapp as wa

@pytest.fixture(autouse=True)
def registre_purge():
    yield
    registre.refuser_toutes()


def test_numero_normalise_avec_whatsapp():
    assert wa._numero("whatsapp:+33612345678") == "whatsapp:+33612345678"


def test_numero_normalise_sans_prefixe():
    assert wa._numero("+33612345678") == "whatsapp:+33612345678"
    assert wa._numero("06 12 34 56 78") == "whatsapp:+33612345678"


def test_envoi_sans_config_repond_un_message():
    from core.config import reglage
    res = wa.envoyer_whatsapp("+33612345678", "bonjour")
    assert "n'est pas configure" in res


def test_outil_enregistre_avec_confirmation():
    o = registre.get("envoyer_whatsapp")
    assert o is not None
    assert o.confirmation is True
    assert registre.est_n3("envoyer_whatsapp")
    assert registre.niveau("envoyer_whatsapp") == "N3"


def test_annonce_montre_le_numero():
    a = wa._annonce_envoi({"numero": "+33612345678"})
    assert "+33612345678" in a


def test_routage_expose_whatsapp():
    from core.routage_intentions import modules_pour_phrase
    modules = modules_pour_phrase("envoie un whatsapp au 0612345678")
    assert "whatsapp" in modules
