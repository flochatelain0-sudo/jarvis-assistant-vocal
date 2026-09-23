"""Le brief enrichi : planning du jour et relances CRM, sans jamais planter.

Les helpers prives tolerent l'echec (agenda ou monday indisponible) :
le brief doit toujours repondre quelque chose.
"""
from tools import brief


def test_planning_bref_resume_les_evenements(monkeypatch):
    from tools import agenda

    def faux_planning():
        return {"evenements": [
            {"heure": "09:00", "titre": "Appel Pierre", "tout_jour": False},
            {"heure": "14:00", "titre": "Visite chantier", "tout_jour": False},
        ]}
    monkeypatch.setattr(agenda, "planning_du_jour", faux_planning)
    texte = brief._planning_bref()
    assert "Appel Pierre" in texte
    assert "Visite chantier" in texte
    assert "agenda" in texte


def test_planning_bref_ignore_les_evenements_tout_jour(monkeypatch):
    from tools import agenda

    def faux_planning():
        return {"evenements": [
            {"titre": "Anniversaire", "tout_jour": True},
        ]}
    monkeypatch.setattr(agenda, "planning_du_jour", faux_planning)
    assert brief._planning_bref() == ""


def test_planning_bref_vide(monkeypatch):
    from tools import agenda

    monkeypatch.setattr(agenda, "planning_du_jour",
                        lambda: {"evenements": []})
    assert brief._planning_bref() == ""


def test_planning_bref_ne_plante_pas(monkeypatch):
    from tools import agenda

    def boom():
        raise RuntimeError("pas de reseau")
    monkeypatch.setattr(agenda, "planning_du_jour", boom)
    assert brief._planning_bref() == ""


def test_relances_bref_liste_les_dossiers(monkeypatch):
    from tools import monday

    def faux_relances():
        return {"relances": [
            {"nom": "Gigi"},
            {"nom": "Luis"},
        ]}
    monkeypatch.setattr(monday, "a_relancer", faux_relances)
    texte = brief._relances_bref()
    assert "2 dossier" in texte
    assert "Gigi" in texte
    assert "Luis" in texte


def test_relances_bref_vide(monkeypatch):
    from tools import monday

    monkeypatch.setattr(monday, "a_relancer", lambda: {"relances": []})
    assert brief._relances_bref() == ""


def test_relances_bref_ne_plante_pas(monkeypatch):
    from tools import monday

    def boom():
        raise RuntimeError("monday down")
    monkeypatch.setattr(monday, "a_relancer", boom)
    assert brief._relances_bref() == ""
