"""File de validation multi-actions (core/registre.py).

La file « a valider » doit montrer TOUTES les actions en attente, pas
seulement la derniere. La voix confirme toujours la plus ancienne
(comportement historique preserve) ; la page Operator liste tout.
"""

import pytest

from core import operator, registre


@pytest.fixture(autouse=True)
def file_purgee():
    yield
    registre.refuser_toutes()


def _outil_test(nom="outil_test"):
    return registre.Outil(
        lambda **k: f"fait : {k.get('quoi', nom)}", nom, "outil de test", {},
        True, False, None,
        lambda a: f"Je vais faire {a.get('quoi')}.", False, "auto")


def test_file_vide_au_depart():
    assert registre.file_en_attente() == []
    assert registre.nom_en_attente() is None


def test_deux_actions_en_attente_visibles():
    registre.mettre_en_attente(_outil_test("a"), {"quoi": "le cafe"})
    registre.mettre_en_attente(_outil_test("b"), {"quoi": "la facture"})
    file = registre.file_en_attente()
    assert len(file) == 2
    assert file[0]["outil"] == "a"          # ordre d'arrivee
    assert file[1]["outil"] == "b"
    assert registre.nom_en_attente() == "a"  # la voix confirme la 1re


def test_valider_avance_la_file():
    registre.mettre_en_attente(_outil_test("a"), {"quoi": "le cafe"})
    registre.mettre_en_attente(_outil_test("b"), {"quoi": "la facture"})
    resultat = registre.executer_confirme()
    assert "le cafe" in str(resultat)
    assert registre.nom_en_attente() == "b"   # la suivante prend le relais


def test_refuser_vide_une_entree():
    registre.mettre_en_attente(_outil_test("a"), {"quoi": "le cafe"})
    registre.mettre_en_attente(_outil_test("b"), {"quoi": "la facture"})
    registre.annuler_confirme()
    assert [f["outil"] for f in registre.file_en_attente()] == ["b"]


def test_refuser_toutes():
    registre.mettre_en_attente(_outil_test("a"), {"quoi": "le cafe"})
    registre.mettre_en_attente(_outil_test("b"), {"quoi": "la facture"})
    assert registre.refuser_toutes() == 2
    assert registre.file_en_attente() == []


def test_operator_affiche_toute_la_file():
    registre.mettre_en_attente(_outil_test("a"), {"quoi": "le cafe"})
    registre.mettre_en_attente(_outil_test("b"), {"quoi": "la facture"})
    etat = operator.etat()
    assert len(etat["a_valider"]) == 2
    assert etat["kpis"]["en_attente"] == 2


def test_valider_depuis_operator_renvoie_le_reste():
    registre.mettre_en_attente(_outil_test("a"), {"quoi": "le cafe"})
    registre.mettre_en_attente(_outil_test("b"), {"quoi": "la facture"})
    r = operator.valider()
    assert r["ok"] and r["reste"] == 1
    r2 = operator.refuser()
    assert r2["ok"] and r2["reste"] == 0


# ------------------------------------------------- validation ciblee (page)
def test_mise_en_attente_pose_la_question_dans_la_conversation():
    registre.mettre_en_attente(_outil_test("a"), {"quoi": "le cafe"})
    from core import operator
    conv = operator.conversation()
    assert any(m.get("type") == "validation" and "le cafe" in m["texte"] for m in conv)


def test_valider_par_identifiant():
    registre.mettre_en_attente(_outil_test("a"), {"quoi": "le cafe"})
    registre.mettre_en_attente(_outil_test("b"), {"quoi": "la facture"})
    file = registre.file_en_attente()
    ident_b = file[1]["id"]
    resultat = registre.executer_confirme_id(ident_b)
    assert "la facture" in str(resultat)
    assert [f["outil"] for f in registre.file_en_attente()] == ["a"]
    assert registre.executer_confirme_id(ident_b) is None      # deja traitee


def test_refuser_par_identifiant():
    registre.mettre_en_attente(_outil_test("a"), {"quoi": "le cafe"})
    registre.mettre_en_attente(_outil_test("b"), {"quoi": "la facture"})
    ident_b = registre.file_en_attente()[1]["id"]
    assert registre.annuler_confirme_id(ident_b) is True
    assert [f["outil"] for f in registre.file_en_attente()] == ["a"]
    assert registre.annuler_confirme_id(ident_b) is False     # deja traitee


def test_operator_valider_id_route_le_bon_outil():
    from core import operator
    registre.mettre_en_attente(_outil_test("a"), {"quoi": "le cafe"})
    ident = registre.file_en_attente()[0]["id"]
    r = operator.valider_id(ident)
    assert r["ok"] and "le cafe" in r["resultat"]
    assert r["reste"] == 0
    r2 = operator.valider_id(ident)
    assert r2["ok"] is False                                  # deja traitee
