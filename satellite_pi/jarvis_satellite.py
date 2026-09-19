#!/usr/bin/env python3
"""Client audio satellite Jarvis pour Raspberry Pi ou machine Linux compatible.

Le dossier satellite_pi/ peut être déployé sans le reste du dépôt. Le client :
  1. écoute le micro et détecte « Hey Jarvis » SUR LE PI (openWakeWord) ;
  2. capture ta phrase jusqu'au silence, l'envoie en PCM 16 kHz au PC
     (WebSocket /satellite) ;
  3. joue l'audio de réponse renvoyé par le PC sur le haut-parleur ;
  4. se reconnecte automatiquement si le serveur est temporairement indisponible.

Config : satellite_pi/config.yaml (pc_url, satellite_id, token, pièce côté PC,
device micro/haut-parleur). Voir docs/satellite_pi.md.

Dépendances : sounddevice, numpy, openwakeword, websockets, pyyaml (+ le modèle
hey_jarvis fourni par openwakeword). Cf. requirements.txt.
"""
import asyncio
import json
import queue
import sys
import threading
import time
from math import gcd
from pathlib import Path

import numpy as np
import sounddevice as sd
import yaml
from scipy.signal import resample_poly

RACINE = Path(__file__).resolve().parent
TAUX = 16000            # 16 kHz mono, comme attendu par openWakeWord ET par le PC
BLOC = 1280             # 80 ms


def _conf():
    p = RACINE / "config.yaml"
    if not p.exists():
        print("config.yaml manquant — copie config.exemple.yaml en config.yaml.")
        sys.exit(1)
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}


class Micro:
    """Capture micro + wake word (openWakeWord) + capture d'énoncé (VAD simple).
    Tourne dans un thread ; pousse chaque énoncé complet (PCM int16 bytes) dans une
    file pour l'envoi au PC."""

    def __init__(self, conf, file_sortie, occupe):
        self.conf = conf
        self.file = file_sortie
        self.occupe = occupe
        self.stop = threading.Event()
        self.seuil_reveil = float(conf.get("seuil_reveil", 0.5))
        self.gain_reveil = float(conf.get("gain_reveil", 1.0))
        self.gain_audio = float(conf.get("gain_audio", 1.0))
        self.seuil_silence = float(conf.get("seuil_silence", 0.010))
        self.silence_fin = float(conf.get("silence_fin", 1.0))
        self.duree_max = float(conf.get("duree_max", 15))
        self.attente_parole = float(conf.get("attente_parole", 3.0))
        self.device = conf.get("micro", None)
        self.sortie = conf.get("haut_parleur", None)
        try:
            info = sd.query_devices(self.device, "input")
            self.taux_capture = int(round(info.get("default_samplerate") or TAUX))
        except Exception:
            self.taux_capture = TAUX
        self.bloc_capture = int(round(BLOC * self.taux_capture / TAUX))

    def _reveil(self):
        import openwakeword
        from openwakeword.model import Model
        chemin = (Path(openwakeword.__file__).parent / "resources" / "models"
                  / "hey_jarvis_v0.1.onnx")
        return Model(wakeword_model_paths=[str(chemin)])

    def _niveau(self, bloc):
        return float(np.sqrt(np.mean(bloc ** 2)))

    def _vers_16k(self, bloc):
        """Ramène un bloc capturé au taux natif du micro vers 16 kHz."""
        if self.taux_capture == TAUX:
            return bloc
        facteur = gcd(TAUX, self.taux_capture)
        return resample_poly(
            bloc, TAUX // facteur, self.taux_capture // facteur
        ).astype(np.float32)

    def _lire_bloc(self, flux):
        bloc, _ = flux.read(self.bloc_capture)
        return self._vers_16k(bloc.flatten())

    def _bip(self):
        """Petit accusé sonore local : l'utilisateur peut parler après le bip."""
        try:
            info = sd.query_devices(self.sortie, "output")
            taux = int(round(info.get("default_samplerate") or 48_000))
            duree = 0.11
            t = np.arange(int(taux * duree), dtype=np.float32) / taux
            enveloppe = np.minimum(1.0, np.minimum(t / 0.012, (duree - t) / 0.025))
            signal = (0.15 * enveloppe * np.sin(2 * np.pi * 880 * t)).astype(np.float32)
            sd.play(signal, samplerate=taux, device=self.sortie)
            sd.wait()
        except Exception as exc:
            print("  [audio] bip impossible:", exc)

    def run(self):
        reveil = self._reveil()
        flux = sd.InputStream(
            samplerate=self.taux_capture,
            channels=1,
            dtype="float32",
            device=self.device,
            blocksize=self.bloc_capture,
        )
        flux.start()
        if self.taux_capture != TAUX:
            print(
                f"  [audio] micro {self.taux_capture} Hz -> 16000 Hz "
                f"({self.bloc_capture} -> {BLOC} échantillons)"
            )
        if self.gain_reveil != 1.0:
            print(
                f"  [wake] gain x{self.gain_reveil:g}, "
                f"seuil {self.seuil_reveil:g}"
            )
        print("Satellite prêt. Dites « Hey Jarvis ».")
        try:
            while not self.stop.is_set():
                bloc = self._lire_bloc(flux)
                if self.occupe.is_set():
                    reveil.reset()
                    continue
                bloc_reveil = np.clip(bloc * self.gain_reveil, -1, 1)
                scores = reveil.predict((bloc_reveil * 32767).astype(np.int16))
                if max(scores.values()) < self.seuil_reveil:
                    continue
                reveil.reset()
                print("  [wake] Hey Jarvis — j'écoute")
                self._bip()
                # Le micro continue de tourner pendant le bip. Purge son écho
                # résiduel avant d'attendre la question, sinon Whisper reçoit
                # parfois seulement le bip puis du silence.
                for _ in range(2):
                    self._lire_bloc(flux)
                # Capture la question APRES le wake word. On attend d'abord le
                # début de la parole, puis `silence_fin` secondes de silence.
                morceaux, debut, dernier = [], time.time(), None
                while not self.stop.is_set():
                    b = self._lire_bloc(flux)
                    maintenant = time.time()
                    if self._niveau(b) > self.seuil_silence:
                        dernier = maintenant
                    if dernier is not None:
                        morceaux.append(b)
                        if maintenant - dernier > self.silence_fin:
                            break
                    elif maintenant - debut > self.attente_parole:
                        print("  [micro] aucune question après le wake word")
                        break
                    if maintenant - debut > self.duree_max:
                        break
                if not morceaux:
                    continue
                audio = np.concatenate(morceaux)
                print(
                    f"  [micro] capture {len(audio) / TAUX:.2f}s "
                    f"rms={self._niveau(audio):.4f} "
                    f"pic={float(np.max(np.abs(audio))):.4f} "
                    f"gain_envoi=x{self.gain_audio:g}"
                )
                audio_envoi = np.clip(audio * self.gain_audio, -1, 1)
                pcm = (audio_envoi * 32767).astype(np.int16).tobytes()
                self.occupe.set()
                self.file.put(pcm)
        finally:
            flux.stop(); flux.close()


def _jouer(pcm, freq):
    """Joue du PCM 16-bit mono à `freq` Hz sur le haut-parleur."""
    try:
        audio = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
        sd.play(audio, samplerate=freq, device=CONF.get("haut_parleur", None))
        sd.wait()
    except Exception as e:
        print("  [audio] lecture impossible:", e)


async def _session(url, satellite, token, file_audio, occupe):
    """Une connexion au PC : envoie les énoncés de la file, joue les réponses."""
    import websockets
    async with websockets.connect(url, max_size=None) as ws:
        await ws.send(json.dumps({"type": "hello", "satellite": satellite, "token": token}))
        # attendre pret
        while True:
            m = await ws.recv()
            if isinstance(m, str) and json.loads(m).get("type") == "pret":
                print("  [pc] connecté."); break
            if isinstance(m, str) and json.loads(m).get("type") == "erreur":
                print("  [pc] refusé:", json.loads(m).get("message")); return

        async def emetteur():
            while True:
                try:
                    pcm = file_audio.get_nowait()
                except queue.Empty:
                    # Évite de laisser un thread bloqué lors d'un arrêt systemd.
                    await asyncio.sleep(0.05)
                    continue
                for i in range(0, len(pcm), 4096):
                    await ws.send(pcm[i:i + 4096])
                await ws.send(json.dumps({"type": "fin_parole"}))

        tache_emet = asyncio.create_task(emetteur())
        try:
            audio, freq = bytearray(), TAUX
            while True:
                m = await ws.recv()
                if isinstance(m, (bytes, bytearray)):
                    audio.extend(m); continue
                d = json.loads(m)
                t = d.get("type")
                if t == "etat":
                    print(f"  [état] {d.get('etat')}")
                    if d.get("etat") == "veille":
                        occupe.clear()
                elif t == "transcription":
                    print(f"  [entendu] {d.get('texte')}")
                elif t == "texte":
                    print(f"  [réponse] {d.get('texte')}")
                elif t == "audio_debut":
                    audio, freq = bytearray(), int(d.get("freq", TAUX))
                elif t == "audio_fin":
                    _jouer(bytes(audio), freq); audio = bytearray()
                elif t == "erreur":
                    print("  [erreur]", d.get("message"))
        finally:
            tache_emet.cancel()


async def _boucle(url, satellite, token, file_audio, occupe):
    """Reconnexion automatique tant que le PC n'est pas joignable."""
    prevenu = False
    while True:
        try:
            await _session(url, satellite, token, file_audio, occupe)
            prevenu = False
        except Exception as e:
            occupe.clear()
            if not prevenu:
                print(f"  [serveur] injoignable ({str(e)[:60]}) — nouvelle tentative…")
                prevenu = True
            await asyncio.sleep(3)


CONF = {}


def main():
    global CONF
    CONF = _conf()
    url = str(CONF.get("pc_url", "")).strip()
    satellite = str(CONF.get("satellite_id", "")).strip()
    token = str(CONF.get("token", "")).strip()
    manquants = [nom for nom, valeur in (
        ("pc_url", url), ("satellite_id", satellite), ("token", token)
    ) if not valeur]
    if manquants:
        print("configuration manquante dans config.yaml : " + ", ".join(manquants))
        sys.exit(1)
    if not url.startswith(("ws://", "wss://")):
        print("pc_url doit commencer par ws:// ou wss://")
        sys.exit(1)

    file_audio = queue.Queue()
    occupe = threading.Event()
    micro = Micro(CONF, file_audio, occupe)
    threading.Thread(target=micro.run, name="micro", daemon=True).start()
    try:
        asyncio.run(_boucle(url, satellite, token, file_audio, occupe))
    except KeyboardInterrupt:
        micro.stop.set()
        print("\nAu revoir.")


if __name__ == "__main__":
    main()
