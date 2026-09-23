"""Le widget calendrier mensuel de la page Operator (planning_mois).

Jamais bloquant : agenda non configure -> mois vide, pas d'exception.
Les evenements hors du mois demande (recurrences a cheval) sont exclus.
"""
import pytest

from tools import agenda


class _CalFaux:
    def __init__(self, jours):
        self._jours = jours

    def calendarList(self):
        return self

    def list(self):
        return self

    def execute(self):
        return {"items": [{"id": "1", "summary": "Perso", "accessRole": "reader"}]}


def _service_faux(monkeypatch, evenements_par_mois):
    service = _CalFaux(None)

    class _Events:
        def list(self, **kw):
            return self

        def execute(self):
            return {"items": evenements_par_mois}

    service.events = lambda: _Events()
    monkeypatch.setattr(agenda, "_service", lambda: service)
    monkeypatch.setattr(agenda, "_calendriers",
                        lambda s: {"1": {"nom": "Perso"}})
    return service


def test_planning_mois_agenda_indisponible(monkeypatch):
    def boom():
        raise RuntimeError("pas de token")
    monkeypatch.setattr(agenda, "_service", boom)
    r = agenda.planning_mois()
    assert r["configure"] is False
    assert r["jours"] == {}


def test_planning_mois_mois_invalide():
    r = agenda.planning_mois(mois=13)
    assert r["configure"] is False


def test_planning_mois_compte_les_evenements(monkeypatch):
    evs = [
        {"summary": "RDV 1", "start": {"dateTime": "2026-09-03T10:00:00+02:00"}},
        {"summary": "RDV 2", "start": {"dateTime": "2026-09-03T14:00:00+02:00"}},
        {"summary": "RDV 3", "start": {"dateTime": "2026-09-15T09:00:00+02:00"}},
    ]
    _service_faux(monkeypatch, evs)
    r = agenda.planning_mois(annee=2026, mois=9)
    assert r["configure"] is True
    assert r["jours"] == {3: 2, 15: 1}


def test_planning_mois_ignore_les_autres_mois(monkeypatch):
    evs = [
        {"summary": "Hors mois", "start": {"date": "2026-10-02"}},
    ]
    _service_faux(monkeypatch, evs)
    r = agenda.planning_mois(annee=2026, mois=9)
    assert r["jours"] == {}


def test_planning_mois_evenements_tout_jour(monkeypatch):
    evs = [
        {"summary": "Anniversaire", "start": {"date": "2026-09-07"}},
    ]
    _service_faux(monkeypatch, evs)
    r = agenda.planning_mois(annee=2026, mois=9)
    assert r["jours"] == {7: 1}
