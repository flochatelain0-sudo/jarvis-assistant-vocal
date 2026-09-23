"""Tests AI Email Operator : categorisation, doctrine N3, enchainement, bilan."""

import pytest

from core import registre
from tools import mail_operateur as mo


class _ImapFaux:
    """IMAP factice : deux mails normaux + un mail pub."""

    def __init__(self, mails):
        self._mails = mails
        self.uid_appels = []

    def select(self, *a):
        return ("OK", [b""])

    def uid(self, commande, num, *args):
        self.uid_appels.append((commande, num, args))
        if commande == "search":
            return ("OK", [b"1 2 3"])
        mail = self._mails[int(num) - 1]
        if "HEADER" in str(args[0]):
            corps = (f"From: {mail['de']}\r\nSubject: {mail['sujet']}\r\n")
            return ("OK", [(b"1", corps.encode("utf-8"))])
        corps = (f"From: {mail['de']}\r\nSubject: {mail['sujet']}\r\n\r\n"
                 f"{mail['texte']}").encode("utf-8")
        return ("OK", [(b"1", corps)])

    def logout(self):
        return ("BYE", [b""])


@pytest.fixture()
def bac(monkeypatch):
    from tools import mail as m
    mails = [
        {"de": "Team Acme <contact@acme.fr>", "sujet": "Demande de devis urgenste",
         "texte": "Bonjour, pouvez-vous m'envoyer un devis pour 3 licences ?"},
        {"de": "noreply@shop.com", "sujet": "Newsletter -20% ce week-end",
         "texte": "Promo exclusive, desabonnez-vous ici."},
        {"de": "support@outil.io", "sujet": "Confirmation de votre inscription",
         "texte": "Votre acces est active. Bonne journee."},
    ]
    imap = _ImapFaux(mails)
    monkeypatch.setattr(m, "_mail_configure", lambda: True)
    monkeypatch.setattr(m, "_imap", lambda: imap)
    # LLM factice : renvoie un brouillon stable
    class _Bloc:
        type = "text"
        text = "Voici la reponse preparee."
    class _Reponse:
        blocs = [_Bloc()]
    class _LLM:
        def repondre(self, consigne, hist, msgs):
            return _Reponse()
    monkeypatch.setattr("core.llm.llm", lambda: _LLM())
    # journaux cartes neutralises
    monkeypatch.setattr("core.operator.question_validation", lambda *a, **k: None)
    return imap


def _vider_file():
    while registre.file_en_attente():
        registre.annuler_confirme()


def test_enregistre():
    registre.charger_outils()
    assert registre.niveau("operateur_mails") == "N1"
    assert registre.niveau("operateur_mail_suivant") == "N1"
    assert registre.niveau("ajuster_brouillon_mail") == "N1"


def test_rapport_chiffre_et_categories(bac):
    _vider_file()
    reponse = mo.operateur_mails()
    assert "3 mail(s) ce matin" in reponse
    assert "1 mail(s) pub" in reponse or "1 mail(s) pub ou spam" in reponse
    # devis = a valider ; inscription = reponse simple ; newsletter = spam
    assert "1 mail(s) important(s)" in reponse
    # le premier mail presente est la confirmation (simple, en tete de file)
    assert "Confirmation de votre inscription" in reponse
    _vider_file()


def test_aucun_envoi_sans_confirmation_doctrine(bac):
    """Doctrine N3 : l'envoi est range en file, JAMAIS execute ici."""
    from tools import mail as m
    envois = []
    monkeypatch_envoyer = pytest.MonkeyPatch()
    monkeypatch_envoyer.setattr(m, "envoyer_mail",
                                lambda: envois.append(1) or "ENVOYE")
    _vider_file()
    mo.operateur_mails()
    assert envois == []                       # aucun envoi direct
    file = registre.file_en_attente()
    noms = [f["outil"] for f in file]
    assert "envoyer_mail" in noms            # envoi en attente de feu vert
    assert "vider_poubelle" in noms          # corbeille en attente aussi
    _vider_file()
    monkeypatch_envoyer.undo()


def test_enchainement_et_bilan_final(bac):
    _vider_file()
    mo.operateur_mails()
    # 2 mails a presenter (1 simple + 1 a valider) puis bilan
    suite = mo.operateur_mail_suivant()
    assert "Confirmation de votre inscription" in suite \
        or "Demande de devis" in suite
    fin = mo.operateur_mail_suivant()
    assert "Tout est traite" in fin
    assert "minutes" in fin
    _vider_file()


def test_ajuster_brouillon_sans_envoi(bac):
    from tools import mail as m
    _vider_file()
    mo.operateur_mails()
    reponse = mo.ajuster_brouillon_mail("mets plutot 16h")
    assert "brouillon modifie" in reponse.lower()
    assert "confirmes l'envoi" in reponse
    # le corps a bien ete remplace par la revision LLM
    assert m.brouillon()["corps"] == "Voici la reponse preparee."
    _vider_file()


def test_boite_vide(bac, monkeypatch):
    from tools import mail as m
    monkeypatch.setattr(m, "_mail_configure", lambda: True)
    monkeypatch.setattr(m, "_imap", lambda: _ImapFaux([]))
    # recherche ne renvoie rien
    imap_vide = _ImapFaux([])
    def _uid_vide(commande, num, *args):
        if commande == "search":
            return ("OK", [b""])
        return ("OK", [None])
    imap_vide.uid = _uid_vide
    monkeypatch.setattr(m, "_imap", lambda: imap_vide)
    assert "vide" in mo.operateur_mails().lower()
