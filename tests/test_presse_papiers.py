"""Sentinelle presse-papiers : lecture seule, classification sans exception."""
from tools import presse_papiers


def test_analyser_url():
    res = presse_papiers.analyser("https://exemple.com/page")
    assert res[0][0] == "lien"
    assert "exemple.com" in res[0][1]


def test_analyser_email():
    res = presse_papiers.analyser("pierre@client.fr")
    assert res[0][0] == "email"
    assert res[0][1] == "pierre@client.fr"


def test_analyser_telephone():
    res = presse_papiers.analyser("06 12 34 56 78")
    assert res[0][0] == "telephone"


def test_analyser_code():
    res = presse_papiers.analyser("def f(x): return {x}")
    assert res[0][0] == "code"


def test_analyser_texte_simple():
    res = presse_papiers.analyser("un texte simple")
    assert res[0][0] == "texte"


def test_analyser_document_multiligne():
    texte = "ligne un\nligne deux\nligne trois"
    res = presse_papiers.analyser(texte)
    assert res[0][0] == "document"
    assert "3 lignes" in res[0][1]


def test_analyser_vide():
    assert presse_papiers.analyser("") == []


def test_lire_pressee_papiers_vide_est_lisible(monkeypatch):
    monkeypatch.setattr(presse_papiers, "_lire", lambda: "")
    reponse = presse_papiers.lire_presse_papiers()
    assert "vide" in reponse


def test_lire_presse_papiers_propose_une_action(monkeypatch):
    monkeypatch.setattr(presse_papiers, "_lire",
                        lambda: "https://exemple.com/article")
    reponse = presse_papiers.lire_presse_papiers()
    assert "lien" in reponse
    assert "ouvre" in reponse
