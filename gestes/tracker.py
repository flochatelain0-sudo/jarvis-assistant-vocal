"""Tracker de gestes de la main — SOUS-PROCESS ISOLE (Python 3.11 + MediaPipe).

Frontiere vie privee : ce process est le SEUL a voir l'image de la webcam. Aucune
image n'est stockee, loggee ni transmise — seuls des *labels de gestes* ("poing",
"mode_fenetres"...) partent vers Jarvis en loopback local (POST /api/gestes, avec
un token). MediaPipe (nouvelle API Tasks) tourne en CPU (XNNPACK).

Lance par core/gestes.py (Jarvis 3.13). Config passee via l'env GESTES_CONF (JSON).
Mode calibration : `--calibrate` (affiche la camera + landmarks + seuils reglables).

Vocabulaire v2 (gestes FIABLES, tenus) :
  main ouverte immobile -> pause ; pouce leve -> lecture ; poing -> couper Jarvis
  2 doigts -> mode fenetres, puis main ouverte + swipe horizontal/vertical
  3 doigts -> mode audio, puis main ouverte + swipe horizontal/vertical
Chaque mode attend une paume ouverte brièvement stable après la pose de sélection
et ne permet qu'une action avant de se fermer.
"""
import json
import os
import sys
import time

import cv2
import numpy as np
import requests
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision as mp_vision
import mediapipe as mp

# Indices des 21 landmarks de la main (MediaPipe).
POIGNET = 0
POUCE_MCP, POUCE_IP, POUCE_TIP = 2, 3, 4
INDEX_TIP, MAJEUR_TIP, ANN_TIP, AURIC_TIP = 8, 12, 16, 20
INDEX_PIP, MAJEUR_PIP, ANN_PIP, AURIC_PIP = 6, 10, 14, 18
INDEX_MCP, MAJEUR_MCP, AURIC_MCP = 5, 9, 17


# ============================================================ classifieurs PURS
# (fonctions sans effet de bord, testables avec des landmarks synthetiques)

def _d(a, b):
    return float(np.hypot(a[0] - b[0], a[1] - b[1]))


def doigt_leve(lm, tip, pip):
    """Détecte un doigt tendu quelle que soit l'orientation de la main.

    Comparer les coordonnées Y ne fonctionne que doigts vers le haut : pendant
    un swipe horizontal, une vraie paume ouverte devenait donc un « poing ».
    Un doigt tendu a son extrémité sensiblement plus loin du poignet que sa PIP.
    La marge est proportionnelle à la taille apparente de la main.
    """
    echelle = max(0.05, _d(lm[POIGNET], lm[MAJEUR_MCP]))
    return _d(lm[tip], lm[POIGNET]) > _d(lm[pip], lm[POIGNET]) + 0.22 * echelle


def pouce_ouvert(lm):
    """Pouce ecarte : bout du pouce loin du bord interne de la main (index MCP)."""
    return _d(lm[POUCE_TIP], lm[INDEX_MCP]) > 0.10


def doigts_tendus(lm):
    """Nombre de doigts tendus (index..auriculaire), hors pouce."""
    paires = ((INDEX_TIP, INDEX_PIP), (MAJEUR_TIP, MAJEUR_PIP),
              (ANN_TIP, ANN_PIP), (AURIC_TIP, AURIC_PIP))
    return sum(1 for tip, pip in paires if doigt_leve(lm, tip, pip))


def _doigts(lm):
    """État index, majeur, annulaire, auriculaire (True = tendu)."""
    return tuple(doigt_leve(lm, tip, pip) for tip, pip in (
        (INDEX_TIP, INDEX_PIP), (MAJEUR_TIP, MAJEUR_PIP),
        (ANN_TIP, ANN_PIP), (AURIC_TIP, AURIC_PIP)))


def est_main_ouverte(lm):
    # 4 doigts tendus (index..auriculaire) suffisent : la detection du pouce ecarte
    # est trop variable selon la main/l'angle pour etre exigee.
    return doigts_tendus(lm) >= 4


def est_main_deployee(lm):
    """Paume assez ouverte pour piloter un mode déjà explicitement armé.

    Trois doigts suffisent ici : le choix 2/3 doigts a déjà été validé et le
    cooldown empêche cette tolérance de sélectionner accidentellement un mode.
    """
    return doigts_tendus(lm) >= 3


def est_deux_doigts(lm):
    """Index + majeur, les deux autres repliés : sélection Fenêtres."""
    return _doigts(lm) == (True, True, False, False)


def est_trois_doigts(lm):
    """Index + majeur + annulaire, auriculaire replié : sélection Audio."""
    return _doigts(lm) == (True, True, True, False)


def est_pouce_leve(lm):
    """Pouce franchement vertical, les quatre autres doigts repliés."""
    return (doigts_tendus(lm) == 0
            and lm[POUCE_TIP][1] < lm[POUCE_IP][1] - 0.035
            and _d(lm[POUCE_TIP], lm[INDEX_MCP]) > 0.10)


def est_poing(lm):
    return doigts_tendus(lm) == 0 and not est_pouce_leve(lm)


def centre_main(lm):
    """Centre stable de la paume pour mesurer un swipe sans dépendre d'un doigt."""
    points = (POIGNET, INDEX_MCP, MAJEUR_MCP, AURIC_MCP)
    return (sum(lm[i][0] for i in points) / len(points),
            sum(lm[i][1] for i in points) / len(points))


def pose(lm):
    """Nom de la pose statique courante, ou None."""
    if est_main_ouverte(lm):
        return "main_ouverte"
    if est_trois_doigts(lm):
        return "mode_audio"
    if est_deux_doigts(lm):
        return "mode_fenetres"
    if est_pouce_leve(lm):
        return "pouce_leve"
    if est_poing(lm):
        return "poing"
    return None


# ==================================================================== FSM

class MachineGestes:
    """Machine à états anti-faux-positifs avec modes explicites temporaires."""

    def __init__(self, conf):
        s = conf.get("seuils", {})
        self.tenue_s = float(s.get("tenue_s", 1.4))
        self.tenue_mode_s = float(s.get("tenue_mode_s", 0.9))
        self.cooldown_s = float(s.get("cooldown_s", 0.8))
        self.swipe_seuil = float(s.get("swipe_seuil", 0.20))
        self.swipe_vertical_seuil = float(s.get("swipe_vertical_seuil", 0.18))
        self.swipe_fenetre_s = float(s.get("swipe_fenetre_s", 1.0))
        self.swipe_dominance = float(s.get("swipe_dominance", 1.20))
        self.swipe_pret_s = float(s.get("swipe_pret_s", 0.35))
        self.stabilite_seuil = float(s.get("stabilite_seuil", 0.06))
        self.inverser_vertical = bool(s.get("inverser_vertical", False))
        self.mode_duree_s = float(s.get("mode_duree_s", 30.0))

        self._geste_courant = None      # geste tenu en cours d'observation
        self._depuis = 0.0              # depuis quand il est tenu
        self._dernier_envoi = -1e9      # cooldown global (1er geste jamais bloque)
        self.mode = None                # None | fenetres | audio
        self._mode_jusqu = 0.0
        self._attend_relachement = False
        self._attend_absence = False    # après une action, main hors cadre obligatoire
        self._hist_xy = []              # (t, x, y) après sélection d'un mode
        self._pret_depuis = 0.0         # début de l'immobilité avant un swipe
        self._pret_position = None      # position de référence pendant l'immobilité
        self._pret_confirme = False     # le trajet de retour n'est jamais un swipe
        self.debug_evenement = ""       # diagnostic local affiché en calibration

    def _cooldown_ok(self, t):
        return (t - self._dernier_envoi) >= self.cooldown_s

    def _reinitialiser_tenue(self):
        self._geste_courant = None
        self._depuis = 0.0

    def _reinitialiser_pret(self):
        self._hist_xy.clear()
        self._pret_depuis = 0.0
        self._pret_position = None
        self._pret_confirme = False

    def _fermer_mode(self):
        self.mode = None
        self._mode_jusqu = 0.0
        self._attend_relachement = False
        self._reinitialiser_pret()

    @property
    def etat_swipe(self):
        """État lisible par l'écran de calibration, sans exposer de landmarks."""
        if not self.mode:
            return "-"
        if self._attend_absence:
            return "sors la main du cadre"
        if self._attend_relachement:
            return "ouvre la main"
        if not self._pret_confirme:
            return "stabilise la main ouverte"
        return "PRET - swipe maintenant"

    def _tenir(self, instant, t, duree=None, marquer_cooldown=True):
        """True une seule fois quand une pose est restée stable assez longtemps."""
        if instant != self._geste_courant:
            self._geste_courant = instant
            self._depuis = t
            return False
        attente = self.tenue_s if duree is None else duree
        if instant is not None and (t - self._depuis) >= attente and self._cooldown_ok(t):
            # Verrouille cette pose jusqu'à un vrai changement/relâchement.
            self._geste_courant = instant
            self._depuis = float("inf")
            if marquer_cooldown:
                self._dernier_envoi = t
            return True
        return False

    def alimenter(self, lm, t):
        """lm = 21 (x,y) normalises, ou None si aucune main. Renvoie un label ou None."""
        if lm is None:
            self._reinitialiser_tenue()
            self._reinitialiser_pret()
            self._attend_absence = False
            if self._attend_relachement:
                self._attend_relachement = False
            return None

        if self.mode and t >= self._mode_jusqu:
            ancien_mode = self.mode
            self._fermer_mode()
            self.debug_evenement = f"mode_{ancien_mode}_expire"

        if self._attend_absence:
            return None

        instant = pose(lm)

        # Le poing reste un arrêt d'urgence, même lorsqu'un mode est armé.
        if instant == "poing" and self._tenir("poing", t):
            self._fermer_mode()
            return "poing"

        if self.mode:
            # Après 2/3 doigts, une paume ouverte remplace naturellement la pose
            # de sélection. Sortir la main du cadre fonctionne aussi, sans être
            # obligatoire. La stabilisation ci-dessous absorbe la transition.
            if self._attend_relachement:
                if not est_main_deployee(lm):
                    return None
                self._attend_relachement = False
                self._reinitialiser_pret()

            # Une action de mode exige une main entière ouverte en mouvement.
            if not est_main_deployee(lm):
                self._reinitialiser_pret()
                self._reinitialiser_tenue()
                return None
            x, y = centre_main(lm)

            # Le changement de pose ou le retour dans le champ crée un grand
            # déplacement artificiel. On attend donc une brève immobilité, puis
            # seulement on ouvre une fenêtre de mesure pour le vrai swipe.
            if not self._pret_confirme:
                if self._pret_position is None:
                    self._pret_position = (x, y)
                    self._pret_depuis = t
                    return None
                dx_pret = x - self._pret_position[0]
                dy_pret = y - self._pret_position[1]
                if (dx_pret * dx_pret + dy_pret * dy_pret) ** 0.5 > self.stabilite_seuil:
                    self._pret_position = (x, y)
                    self._pret_depuis = t
                    return None
                # Mesure image par image : une dérive lente et naturelle de la
                # main ne remet pas sans cesse le chronomètre à zéro.
                self._pret_position = (x, y)
                if (t - self._pret_depuis) < self.swipe_pret_s:
                    return None
                self._pret_confirme = True
                self._hist_xy = [(t, x, y)]
                return None

            self._hist_xy.append((t, x, y))
            self._hist_xy = [p for p in self._hist_xy if t - p[0] <= self.swipe_fenetre_s]
            if len(self._hist_xy) < 3 or not self._cooldown_ok(t):
                return None
            dx = self._hist_xy[-1][1] - self._hist_xy[0][1]
            dy = self._hist_xy[-1][2] - self._hist_xy[0][2]
            horizontal = abs(dx) >= self.swipe_seuil and abs(dx) >= abs(dy) * self.swipe_dominance
            vertical = (abs(dy) >= self.swipe_vertical_seuil
                        and abs(dy) >= abs(dx) * self.swipe_dominance)
            if not horizontal and not vertical:
                return None

            vers_bas = dy > 0
            if self.inverser_vertical:
                vers_bas = not vers_bas

            if self.mode == "fenetres":
                if horizontal:
                    resultat = "fenetre_droite" if dx > 0 else "fenetre_gauche"
                else:
                    resultat = "defilement_bas" if vers_bas else "defilement_haut"
            else:
                if horizontal:
                    resultat = "piste_suivante" if dx > 0 else "piste_precedente"
                else:
                    resultat = "volume_bas" if vers_bas else "volume_haut"
            self._dernier_envoi = t
            # Le mode reste actif pour permettre plusieurs swipes successifs.
            # Une sortie complète de la main reste obligatoire entre deux
            # actions afin qu'un seul mouvement ne soit jamais compté deux fois.
            self._reinitialiser_pret()
            self._mode_jusqu = t + self.mode_duree_s
            self._attend_absence = True
            return resultat

        # Hors mode : les poses 2/3 doigts arment une famille d'actions.
        if instant in {"mode_fenetres", "mode_audio"}:
            if self._tenir(instant, t, self.tenue_mode_s, marquer_cooldown=False):
                self.mode = "fenetres" if instant == "mode_fenetres" else "audio"
                self._mode_jusqu = t + self.mode_duree_s
                self._attend_relachement = True
                self._reinitialiser_pret()
                return instant
            return None

        if instant in {"main_ouverte", "pouce_leve"} and self._tenir(instant, t):
            return instant
        if instant not in {"main_ouverte", "pouce_leve", "poing"}:
            self._reinitialiser_tenue()
        return None


# ==================================================================== I/O

def _envoyer(url, token, geste):
    try:
        requests.post(url, json={"geste": geste},
                      headers={"X-Gestes-Token": token}, timeout=1.5)
    except Exception:
        pass  # Jarvis occupe / injoignable : on ignore, jamais de blocage


def _landmarks_np(res):
    """Extrait la 1re main en liste de (x,y) normalises, ou None."""
    if not res.hand_landmarks:
        return None
    return [(p.x, p.y) for p in res.hand_landmarks[0]]


def boucle(conf, calibrer=False):
    device = int(conf.get("device", 0))
    fps = int(conf.get("fps", 24))
    url = conf.get("url", "http://127.0.0.1:8790/api/gestes")
    token = conf.get("token", "")
    modele = conf.get("model_path", "gestes/models/hand_landmarker.task")

    conf_det = float(conf.get("confiance_detection", 0.7))
    conf_track = float(conf.get("confiance_suivi", 0.7))
    base = mp_python.BaseOptions(model_asset_path=modele)
    options = mp_vision.HandLandmarkerOptions(
        base_options=base, num_hands=1,
        running_mode=mp_vision.RunningMode.VIDEO,
        min_hand_detection_confidence=conf_det, min_tracking_confidence=conf_track)
    landmarker = mp_vision.HandLandmarker.create_from_options(options)

    cap = cv2.VideoCapture(device, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, int(conf.get("largeur", 640)))
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, int(conf.get("hauteur", 480)))
    if not cap.isOpened():
        print(f"[gestes] webcam device {device} introuvable", file=sys.stderr)
        return

    fsm = MachineGestes(conf)
    periode = 1.0 / max(5, fps)
    historique_gestes = []
    print(f"[gestes] tracker demarre (device {device}, {fps} fps){' — CALIBRATION' if calibrer else ''}",
          file=sys.stderr)

    try:
        while True:
            t0 = time.time()
            ok, frame = cap.read()
            if not ok:
                time.sleep(0.05)
                continue
            frame = cv2.flip(frame, 1)  # miroir naturel
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            res = landmarker.detect_for_video(image, int(t0 * 1000))
            lm = _landmarks_np(res)

            geste = fsm.alimenter(lm, t0)
            if geste:
                historique_gestes.append(geste)
                historique_gestes[:] = historique_gestes[-4:]
            if calibrer and fsm.debug_evenement:
                historique_gestes.append(fsm.debug_evenement)
                historique_gestes[:] = historique_gestes[-4:]
                fsm.debug_evenement = ""
            if geste and not calibrer:
                _envoyer(url, token, geste)

            if calibrer:
                _afficher_calibration(frame, lm, fsm, historique_gestes, t0)
                k = cv2.waitKey(1) & 0xFF
                if not _touches_calibration(k, fsm):
                    break

            dt = time.time() - t0
            if dt < periode:
                time.sleep(periode - dt)
    finally:
        cap.release()
        if calibrer:
            cv2.destroyAllWindows()
        landmarker.close()


# --------------------------------------------------------- mode calibration

def _afficher_calibration(frame, lm, fsm, historique_gestes, maintenant):
    h, w = frame.shape[:2]
    if lm is not None:
        for x, y in lm:
            cv2.circle(frame, (int(x * w), int(y * h)), 4, (0, 255, 0), -1)
        infos = [f"pose : {pose(lm) or '-'}  doigts : {doigts_tendus(lm)}",
                 f"ouverte:{est_main_ouverte(lm)}  pouce:{est_pouce_leve(lm)}  "
                 f"2:{est_deux_doigts(lm)}  3:{est_trois_doigts(lm)}  poing:{est_poing(lm)}",
                 f"main deployee pour swipe:{est_main_deployee(lm)}"]
    else:
        infos = ["aucune main detectee"]
    restant = max(0.0, fsm._mode_jusqu - maintenant) if fsm.mode else 0.0
    infos += [f"mode:{fsm.mode or '-'} ({restant:.1f}s)  etape:{fsm.etat_swipe}",
              f"tenue:{fsm.tenue_s:.2f}  mode tenue:{fsm.tenue_mode_s:.2f} "
              f"pret:{fsm.swipe_pret_s:.2f}",
              f"cooldown:{fsm.cooldown_s:.2f}  swipe H:{fsm.swipe_seuil:.2f} "
              f"V:{fsm.swipe_vertical_seuil:.2f}  axe V:{'inverse' if fsm.inverser_vertical else 'normal'}",
              "[t/T] tenue -/+  [c/C] cooldown -/+  [w/W] swipe H -/+",
              "[v/V] swipe V -/+  [i] inverser V  [s] sauver  [q] quitter"]
    if historique_gestes:
        infos.insert(0, ">>> HIST : " + " > ".join(historique_gestes))
    for i, ligne in enumerate(infos):
        cv2.putText(frame, ligne, (10, 24 + i * 22), cv2.FONT_HERSHEY_SIMPLEX,
                    0.55, (0, 255, 255), 1, cv2.LINE_AA)
    cv2.imshow("Jarvis — calibration gestes", frame)


def _touches_calibration(k, fsm):
    if k in (ord("q"), 27):
        return False
    if k == ord("t"):
        fsm.tenue_s = max(0.3, fsm.tenue_s - 0.1)
    elif k == ord("T"):
        fsm.tenue_s = min(3.0, fsm.tenue_s + 0.1)
    elif k == ord("c"):
        fsm.cooldown_s = max(0.5, fsm.cooldown_s - 0.1)
    elif k == ord("C"):
        fsm.cooldown_s = min(5.0, fsm.cooldown_s + 0.1)
    elif k == ord("w"):
        fsm.swipe_seuil = max(0.10, fsm.swipe_seuil - 0.01)
    elif k == ord("W"):
        fsm.swipe_seuil = min(0.60, fsm.swipe_seuil + 0.01)
    elif k == ord("v"):
        fsm.swipe_vertical_seuil = max(0.10, fsm.swipe_vertical_seuil - 0.01)
    elif k == ord("V"):
        fsm.swipe_vertical_seuil = min(0.60, fsm.swipe_vertical_seuil + 0.01)
    elif k == ord("i"):
        fsm.inverser_vertical = not fsm.inverser_vertical
    elif k == ord("s"):
        seuils = {
            "tenue_s": round(fsm.tenue_s, 2),
            "tenue_mode_s": round(fsm.tenue_mode_s, 2),
            "cooldown_s": round(fsm.cooldown_s, 2),
            "swipe_seuil": round(fsm.swipe_seuil, 3),
            "swipe_vertical_seuil": round(fsm.swipe_vertical_seuil, 3),
            "swipe_fenetre_s": round(fsm.swipe_fenetre_s, 2),
            "swipe_dominance": round(fsm.swipe_dominance, 2),
            "swipe_pret_s": round(fsm.swipe_pret_s, 2),
            "stabilite_seuil": round(fsm.stabilite_seuil, 3),
            "inverser_vertical": fsm.inverser_vertical,
            "mode_duree_s": round(fsm.mode_duree_s, 2),
        }
        chemin = os.path.join(os.path.dirname(os.path.abspath(__file__)), "calibration.json")
        with open(chemin, "w", encoding="utf-8") as f:
            json.dump({"seuils": seuils}, f, ensure_ascii=False, indent=2)
        print(f"[gestes] seuils sauvegardes -> {chemin}", file=sys.stderr)
    return True


def main():
    conf = json.loads(os.environ.get("GESTES_CONF", "{}"))
    calibrer = "--calibrate" in sys.argv
    boucle(conf, calibrer=calibrer)


if __name__ == "__main__":
    main()
