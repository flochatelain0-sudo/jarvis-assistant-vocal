"""Le chat ecrit ne doit prononcer la reponse qu'UNE seule fois.

`repondre()` prononce deja la reponse finale (pipeline commun avec la voix).
Le drain du chat ecrit la prononcait une seconde fois via `a_prononcer` :
chaque question tapee sur la page Operator etait lue deux fois a voix haute.
Regression testee ici : le second element du retour de traiter_ecrit doit
rester vide pour une reponse normale, et la reponse doit etre prononcee
exactement une fois au total.
"""
import pytest

jarvis14 = pytest.importorskip("jarvis14")


@pytest.fixture
def _mute(monkeypatch):
    monkeypatch.setattr(jarvis14, "dire", lambda texte, interruptible=True: None)
    monkeypatch.setattr(jarvis14, "_hud", lambda *a, **k: None)
    monkeypatch.setattr(jarvis14, "_afficher_overlay", lambda texte: None)
    monkeypatch.setattr(jarvis14, "_hud_status", lambda: None)
    monkeypatch.setattr(jarvis14, "_nourrir_brain", lambda message: None)


def test_reponse_normale_pas_reprononcee(monkeypatch, _mute):
    prononces = []
    monkeypatch.setattr(jarvis14, "dire",
                        lambda texte, interruptible=True: prononces.append(texte))

    def _repondre(historique):
        return "Bonjour, je suis Jarvis."

    monkeypatch.setattr(jarvis14, "repondre", _repondre)
    historique = []
    affiche, a_prononcer = jarvis14.traiter_ecrit("qui es-tu ?", historique)
    assert affiche == "Bonjour, je suis Jarvis."
    assert a_prononcer == ""
    assert prononces == []          # le pipeline a deja parle ; rien a rejouer


def test_reponse_vide_dite_une_seule_fois(monkeypatch, _mute):
    prononces = []
    monkeypatch.setattr(jarvis14, "dire",
                        lambda texte, interruptible=True: prononces.append(texte))
    monkeypatch.setattr(jarvis14, "repondre", lambda historique: "")
    historique = []
    affiche, a_prononcer = jarvis14.traiter_ecrit("coupe le son", historique)
    assert affiche == "C'est fait."
    assert a_prononcer == ""
    assert prononces == ["C'est fait."]   # une seule prononciation au total


def test_sentinel_confirm_ne_reprononce_pas_lannonce(monkeypatch, _mute):
    from core import registre

    prononces = []
    monkeypatch.setattr(jarvis14, "dire",
                        lambda texte, interruptible=True: prononces.append(texte))
    monkeypatch.setattr(jarvis14, "repondre",
                        lambda historique: jarvis14.SENTINEL_CONFIRM)
    monkeypatch.setattr(registre, "annonce_en_attente",
                        lambda: "Je vais envoyer le message.")
    historique = []
    affiche, a_prononcer = jarvis14.traiter_ecrit("envoie le message", historique)
    assert affiche == "Je vais envoyer le message."
    assert a_prononcer == ""
    assert prononces == []
