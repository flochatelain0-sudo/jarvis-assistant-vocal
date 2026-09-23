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


class _ImapFaux:
    """IMAP en memoire : enregistre les store() sans toucher au reseau."""

    def __init__(self):
        self.deplaces = []
        self.ouvert = False
        self.ferme = False

    def select(self, boite):
        self.ouvert = True
        return ("OK", [b""])

    def uid(self, commande, uid, *args):
        if commande == "store":
            self.deplaces.append(uid)
            return ("OK", [b""])
        return ("OK", [b""])

    def logout(self):
        self.ferme = True
        return ("BYE", [b""])


def _configurer_boite(monkeypatch, mails, etiquettes):
    from tools import mail as m
    m.MAIL_ADRESSE = "test@example.com"
    m.MAIL_MOT_DE_PASSE_APP = "motdepasse"
    monkeypatch.setattr(m, "_oauth_actif", lambda: False)
    m._DERNIERS_MAILS.clear()
    m._DERNIERS_MAILS.extend(mails)
    m._ETIQUETTES.clear()
    m._ETIQUETTES.update(etiquettes)
    imap = _ImapFaux()
    monkeypatch.setattr(m, "_imap", lambda: imap)
    return imap


def test_vider_poubelle_deplace_tous_les_spams_d_un_coup(monkeypatch):
    from tools import mail as m
    imap = _configurer_boite(
        monkeypatch,
        mails=[b"10", b"11", b"12"],
        etiquettes={b"10": "poubelle", b"12": "poubelle"})
    reponse = m.vider_poubelle()
    assert sorted(imap.deplaces) == [b"10", b"12"]
    assert "2 mail(s)" in reponse
    assert imap.ferme


def test_vider_poubelle_sans_spam_ne_fait_rien(monkeypatch):
    from tools import mail as m
    imap = _configurer_boite(monkeypatch, mails=[b"10"], etiquettes={})
    assert "rien a jeter" in m.vider_poubelle()
    assert imap.deplaces == []


def test_vider_poubelle_sans_liste_demande_de_lister(monkeypatch):
    from tools import mail as m
    m.MAIL_ADRESSE = "test@example.com"
    m.MAIL_MOT_DE_PASSE_APP = "motdepasse"
    monkeypatch.setattr(m, "_oauth_actif", lambda: False)
    m._DERNIERS_MAILS.clear()
    m._ETIQUETTES.clear()
    assert "lister" in m.vider_poubelle()


def test_vider_poubelle_est_enregistre_avec_confirmation():
    from core import registre
    o = registre.get("vider_poubelle")
    assert o is not None and o.confirmation is True


def test_lire_mails_remplit_les_etiquettes(monkeypatch):
    from tools import mail as m
    m._ETIQUETTES.clear()
    m._ETIQUETTES.update({b"99": "poubelle"})
    m._DERNIERS_MAILS.clear()
    m._DERNIERS_MAILS.extend([b"7"])
    assert m._ETIQUETTES.get(b"99") == "poubelle"
