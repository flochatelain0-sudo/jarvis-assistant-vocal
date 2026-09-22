"""Base de connaissances : stockage JSON, recherche par mots-cles, outils.

Les tests utilisent un fichier isole (tmp_path) pour ne jamais toucher a
data/knowledge.json de l'utilisateur.
"""
import json

import pytest

from tools import knowledge


@pytest.fixture(autouse=True)
def _base_isolee(tmp_path, monkeypatch):
    fichier = tmp_path / "knowledge.json"
    monkeypatch.setattr(knowledge, "_FICHIER", fichier)
    monkeypatch.setattr(knowledge, "_DOSSIER", tmp_path)
    monkeypatch.setattr(knowledge, "_DOCUMENTS", None)
    yield
    knowledge._DOCUMENTS = None


def test_base_vide():
    assert knowledge.documents() == []
    assert knowledge.retrouver(123) is None


def test_ajouter_et_retrouver():
    doc = knowledge.ajouter_depuis_texte(
        "Offre constructeur\nPrix 285 000 EUR. Garantie 10 ans.",
        titre="Offre Romain")
    assert doc["titre"] == "Offre Romain"
    retrouve = knowledge.retrouver(doc["id"])
    assert retrouve is not None
    assert "285 000" in retrouve["contenu"]


def test_titre_deduit_de_la_premiere_ligne():
    doc = knowledge.ajouter_depuis_texte("Regulatory Trends Q3\nbla bla")
    assert doc["titre"] == "Regulatory Trends Q3"


def test_persistance_sur_disque():
    doc = knowledge.ajouter_depuis_texte("notes importantes", titre="Notes")
    knowledge._DOCUMENTS = None
    docs = knowledge.documents()
    assert len(docs) == 1
    assert docs[0]["id"] == doc["id"]


def test_ordre_du_plus_recent():
    knowledge.ajouter_depuis_texte("premier")
    knowledge.ajouter_depuis_texte("second")
    titres = [d["contenu"] for d in knowledge.documents()]
    assert titres == ["second", "premier"]


def test_document_vide_refuse():
    with pytest.raises(ValueError):
        knowledge.ajouter_depuis_texte("   ")


def test_trop_gros_refuse():
    with pytest.raises(ValueError):
        knowledge.ajouter_depuis_texte("x" * (knowledge._MAX_TAILLE + 1))


def test_ajouter_depuis_fichier(tmp_path):
    p = tmp_path / "fiche.md"
    p.write_text("# Fiche produit\nSpecs completes", encoding="utf-8")
    doc = knowledge.ajouter_depuis_fichier(p)
    assert doc["titre"] == "Fiche produit"
    assert doc["source"] == "fiche.md"


def test_ajouter_fichier_binaire_refuse(tmp_path):
    p = tmp_path / "doc.pdf"
    p.write_bytes(b"%PDF-1.4 fake")
    with pytest.raises(ValueError):
        knowledge.ajouter_depuis_fichier(p)


def test_outil_lire_document_trouve_par_mots_cles():
    knowledge.ajouter_depuis_texte(
        "Offre Romain : maison 120m2, 285 000 EUR, garantie 10 ans")
    knowledge.ajouter_depuis_texte("Recette crepes : farine, oeufs, lait")
    reponse = knowledge.lire_document("l'offre de Romain")
    assert "285 000" in reponse
    assert "Romain" in reponse


def test_outil_lire_document_introuvable():
    knowledge.ajouter_depuis_texte("recette crepes")
    reponse = knowledge.lire_document("processus quantique")
    assert "ne trouve pas" in reponse


def test_outil_lister_documents():
    knowledge.ajouter_depuis_texte("doc un", titre="Un")
    knowledge.ajouter_depuis_texte("doc deux", titre="Deux")
    reponse = knowledge.lister_documents()
    assert "2 document" in reponse
    assert "Un" in reponse and "Deux" in reponse


def test_outil_ajouter_document_texte():
    reponse = knowledge.ajouter_document(
        "Process verbal du 12 mars : validation du budget", titre="PV")
    assert "ajoute" in reponse.lower() or "ajouté" in reponse
    assert len(knowledge.documents()) == 1
