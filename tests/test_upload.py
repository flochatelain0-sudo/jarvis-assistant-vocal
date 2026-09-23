"""Tests upload : validation sources, vraie requete multipart sur serveur local."""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from tools import upload


@pytest.fixture()
def bac(tmp_path, monkeypatch):
    monkeypatch.setattr("tools.fichiers._dossiers_autorises", lambda: [tmp_path.resolve()])
    return tmp_path


def test_enregistres():
    from core import registre
    registre.charger_outils()
    assert registre.niveau("envoyer_fichier") == "N2"
    assert registre.niveau("upload_navigateur") == "N2"


def test_source_upload_valide(bac):
    fichier = bac / "doc.txt"
    fichier.write_text("contenu", encoding="utf-8")
    assert upload._source_upload("doc.txt") == fichier


def test_source_absente(bac):
    with pytest.raises(FileNotFoundError):
        upload._source_upload("rien.txt")


def test_secret_refuse(bac):
    (bac / "config.yaml").write_text("secret", encoding="utf-8")
    with pytest.raises(PermissionError):
        upload._source_upload("config.yaml")


def test_trop_volumineux(bac, monkeypatch):
    fichier = bac / "gros.bin"
    fichier.write_bytes(b"x")
    monkeypatch.setattr(upload, "_TAILLE_MAX", 0)
    with pytest.raises(ValueError):
        upload._source_upload("gros.bin")


def test_url_invalide(bac):
    fichier = bac / "doc.txt"
    fichier.write_text("x", encoding="utf-8")
    reponse = upload.envoyer_fichier("doc.txt", "ftp://exemple.fr")
    assert "http://" in reponse


def test_vrai_upload_multipart(bac, monkeypatch):
    """Vraie requete : petit serveur HTTP local, reponse verifiee.

    La suite complete stubbe parfois sys.modules['requests'] (tests OAuth).
    On rebind explicitement le vrai module pour que l'upload reste reel ici.
    """
    import requests as vrai_requests
    monkeypatch.setattr(upload, "requests", vrai_requests)
    recu: dict = {}

    class Gestionnaire(BaseHTTPRequestHandler):
        def do_POST(self):
            taille = int(self.headers.get("Content-Length", 0))
            corps = self.rfile.read(taille)
            recu["multipart"] = b"filename=" in corps or b"doc.txt" in corps
            recu["contenu"] = b"contenu-upload" in corps
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"ok": True}).encode("utf-8"))
            return

        def log_message(self, *args):
            pass

    serveur = HTTPServer(("127.0.0.1", 0), Gestionnaire)
    port = serveur.server_address[1]
    thread = threading.Thread(target=serveur.serve_forever, daemon=True)
    thread.start()
    try:
        fichier = bac / "doc.txt"
        fichier.write_text("contenu-upload", encoding="utf-8")
        reponse = upload.envoyer_fichier("doc.txt", f"http://127.0.0.1:{port}/up")
        assert "HTTP 200" in reponse
        assert '"ok"' in reponse
        assert recu["multipart"] and recu["contenu"]
    finally:
        serveur.shutdown()


def test_upload_navigateur_sans_chrome(bac, monkeypatch):
    fichier = bac / "doc.txt"
    fichier.write_text("x", encoding="utf-8")
    monkeypatch.setattr("tools.navigateur._connexion", lambda auto=True: None)
    reponse = upload.upload_navigateur("doc.txt")
    assert "Chrome" in reponse
