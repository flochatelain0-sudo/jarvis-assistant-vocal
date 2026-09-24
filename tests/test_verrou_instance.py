"""Un seul Jarvis a la fois (verrou d'instance).

L'autostart launchd (KeepAlive) et un lancement manuel pouvaient coexister :
deux micros, deux voix, chaque reponse dite deux fois. Le verrou flock doit
empecher le second processus de demarrer, et le message doit nommer le PID
du premier (diagnostic, pas de mystere).
"""
import subprocess
import sys

import pytest

jarvis14 = pytest.importorskip("jarvis14")


def test_deuxieme_processus_bloque_et_message_clair(tmp_path, monkeypatch):
    """Un verrou deja pris => le 2e processus s'arrete en le disant."""
    # Un premier processus tient le verrou (le notre).
    premier = jarvis14._verrou_instance()
    assert premier[0] is not None, "le premier doit obtenir le verrou"
    try:
        # Le second, dans un VRAI processus isole (flock est par processus).
        code = (
            "import sys; sys.path.insert(0, %r); import jarvis14; "
            "verrou, _ = jarvis14._verrou_instance(); "
            "sys.exit(0 if verrou is None else 1)"
        ) % str(jarvis14.__file__ and __import__("pathlib").Path(
            jarvis14.__file__).parent)
        resultat = subprocess.run([sys.executable, "-c", code],
                                  capture_output=True, text=True, timeout=60)
        assert resultat.returncode == 0, (
            "le second processus devait refuser de demarrer : "
            f"{resultat.stdout} {resultat.stderr}")
        assert "Un Jarvis tourne deja" in resultat.stdout
    finally:
        premier[0].close()


def test_fichier_porte_le_pid(tmp_path):
    """Le fichier de verrou contient le PID du detenteur : diagnostic lisible."""
    verrou, chemin = jarvis14._verrou_instance()
    try:
        import os
        assert chemin.read_text().strip() == str(os.getpid())
    finally:
        verrou.close()
