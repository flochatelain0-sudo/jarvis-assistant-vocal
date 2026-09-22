"""Triage heuristique des mails sans valeur (poubelle) dans lire_mails.

La suppression reste une action confirmee (mettre_a_la_corbeille, N2) :
l'etiquette [poubelle] est purement informative, pour que le modele propose
le tri — jamais une suppression automatique.
"""
from tools.mail import _etiqueter_spam


def test_newsletter_est_poubelle():
    assert _etiqueter_spam("news@shop.com", "Notre newsletter de la semaine") == "poubelle"


def test_promo_avec_reduction_est_poubelle():
    assert _etiqueter_spam("promo@brand.io", "-30% sur toute la collection") == "poubelle"


def test_mail_important_n_est_pas_poubelle():
    assert _etiqueter_spam("pierre@client.fr", "Meeting Thursday?") == ""


def test_noreply_seul_ne_suffit_pas():
    assert _etiqueter_spam("noreply@github.com", "Your PR was merged") == ""


def test_noreply_plus_promo_est_poubelle():
    assert _etiqueter_spam("noreply@shop.com", "Notre promotion du mois") == "poubelle"
