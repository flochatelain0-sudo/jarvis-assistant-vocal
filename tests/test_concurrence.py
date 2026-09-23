"""Tests veille concurrentielle : extraction de prix reels, journalisation."""

from tools import concurrence


def test_enregistres():
    from core import registre
    registre.charger_outils()
    assert registre.niveau("surveiller_concurrent") == "N1"
    assert registre.niveau("veille_marche") == "N1"


def test_prix_euros():
    texte = "Formule Starter 29,99 € par mois. Pro 99 € Business 299,00 €"
    prix = concurrence.extraire_prix(texte)
    assert 29.99 in prix and 99.0 in prix and 299.0 in prix


def test_prix_dollars():
    prix = concurrence.extraire_prix("Basic $9.99, Premium $49")
    assert 9.99 in prix and 49.0 in prix


def test_prix_grands_nombres():
    prix = concurrence.extraire_prix("1 299,00 € et 2,499.00 $")
    assert 1299.0 in prix
    assert 2499.0 in prix


def test_aucun_prix():
    assert concurrence.extraire_prix("rien a signaler ici") == []


def test_prix_plafonne():
    # des chiffres aberrants (ids, timestamps) ne sont pas des prix
    prix = concurrence.extraire_prix("commande 123456789 € non")
    assert all(p < 1_000_000 for p in prix)


def test_resume_prix():
    resume = concurrence._resume_prix([10.0, 20.0, 30.0])
    assert "3 prix" in resume and "min 10.00" in resume and "max 30.00" in resume


def test_sujet_vide(monkeypatch):
    monkeypatch.setattr("tools.web.chercher_web", lambda r: "resultats")
    reponse = concurrence.veille_marche("")
    assert "Précise" in reponse
    reponse2 = concurrence.veille_marche("SEA")
    assert "resultats" in reponse2


def test_sans_chrome(monkeypatch):
    # sans navigateur pilote : message clair, et surtout on ne lance JAMAIS
    # la machinerie Playwright/CDP dans les tests (elle laisse une boucle
    # d'evenements active qui casse les tests async suivants).
    monkeypatch.setattr("tools.navigateur._connexion", lambda auto=True: None)
    reponse = concurrence.surveiller_concurrent()
    assert "Chrome" in reponse
