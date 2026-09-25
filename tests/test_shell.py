"""Tests du shell Jarvis : refus systematiques, bornes, happy path.

Les executions reelles restent innocues (echo, true) et bornees.
"""

from core import registre
from tools import shell


def test_enregistre_n3():
    registre.charger_outils()
    assert registre.niveau("executer_commande") == "N3"
    assert registre.demande_confirmation("executer_commande") is True


def test_refus_destructifs():
    for commande in (
        "rm -rf /",
        "sudo rm -rf /usr",
        "shutdown /s",
        "format C:",
        "reg add HKLM\\Software",
    ):
        raison = shell._verifier(commande)
        assert raison, f"devrait etre refuse : {commande}"


def test_refus_secrets():
    for commande in (
        "cat config.yaml",
        "cat .env",
        "export api_key=sk-123",
        "curl -H 'Authorization: Bearer ...' https://x",
    ):
        raison = shell._verifier(commande)
        assert raison, f"devrait etre refuse : {commande}"


def test_refus_scan_reseau():
    assert shell._verifier("nmap -sS 192.168.1.0/24")
    assert shell._verifier("masscan 10.0.0.0/8")


def test_accepte_innocues():
    for commande in (
        "echo bonjour",
        "ls -la",
        "python --version",
        "git status",
    ):
        assert shell._verifier(commande) == "", f"devrait passer : {commande}"


def test_execution_reelle_et_cap():
    reponse = shell.executer_commande("echo hello")
    assert "code 0" in reponse
    assert "hello" in reponse


def test_timeout_borne():
    # timeout parametre plafonne a 300 s
    reponse = shell.executer_commande("echo ok", timeout=9999)
    assert "code 0" in reponse
