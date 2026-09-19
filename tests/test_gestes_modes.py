"""Tests purs du vocabulaire v2 et de la machine de gestes.

MediaPipe/OpenCV vivent dans le venv Python 3.11 du tracker. Ces stubs permettent
de tester la logique géométrique depuis le venv principal sans charger la caméra.
"""
import sys
import types
import unittest
import math


def _module(nom):
    module = types.ModuleType(nom)
    sys.modules[nom] = module
    return module


_module("cv2")
_module("requests")
mp = _module("mediapipe")
tasks = _module("mediapipe.tasks")
mp_python = _module("mediapipe.tasks.python")
vision = _module("mediapipe.tasks.python.vision")
mp.tasks = tasks
tasks.python = mp_python
mp_python.vision = vision

from gestes.tracker import (  # noqa: E402
    MachineGestes,
    est_deux_doigts,
    est_main_deployee,
    est_main_ouverte,
    est_poing,
    est_pouce_leve,
    est_trois_doigts,
)


def _main(doigts=0, pouce=False, x=0.5, y=0.5):
    """Landmarks synthétiques : `doigts` premiers doigts tendus."""
    lm = [(x, y) for _ in range(21)]
    lm[0] = (x, y + 0.15)
    paires = ((5, 6, 8, -0.09), (9, 10, 12, -0.03),
              (13, 14, 16, 0.03), (17, 18, 20, 0.09))
    for i, (mcp, pip, tip, dx) in enumerate(paires):
        lm[mcp] = (x + dx, y + 0.03)
        lm[pip] = (x + dx, y - 0.04)
        lm[tip] = (x + dx, y - 0.24 if i < doigts else y + 0.08)
    lm[3] = (x - 0.12, y - 0.02)
    lm[4] = (x - 0.12, y - 0.22) if pouce else (x - 0.07, y + 0.02)
    return lm


def _tourner(lm, angle):
    """Tourne les landmarks autour du poignet, comme une main inclinée."""
    ox, oy = lm[0]
    cos_a, sin_a = math.cos(angle), math.sin(angle)
    return [(ox + (x - ox) * cos_a - (y - oy) * sin_a,
             oy + (x - ox) * sin_a + (y - oy) * cos_a) for x, y in lm]


def _fsm():
    return MachineGestes({"seuils": {
        "tenue_s": 1.0,
        "tenue_mode_s": 0.5,
        "cooldown_s": 0.1,
        "swipe_seuil": 0.20,
        "swipe_vertical_seuil": 0.20,
        "swipe_fenetre_s": 1.0,
        "swipe_dominance": 1.1,
        "swipe_pret_s": 0.3,
        "stabilite_seuil": 0.06,
        "mode_duree_s": 5.0,
        "zoom_seuil": 0.12,
        "zoom_reduire_seuil": 0.08,
        "zoom_tenue_s": 0.4,
        "zoom_stabilite_seuil": 0.03,
    }})


class ClassifieursTests(unittest.TestCase):
    def test_cinq_poses_sont_distinctes(self):
        self.assertTrue(est_main_ouverte(_main(4)))
        self.assertTrue(est_deux_doigts(_main(2)))
        self.assertTrue(est_trois_doigts(_main(3)))
        self.assertTrue(est_pouce_leve(_main(0, pouce=True)))
        self.assertTrue(est_poing(_main(0)))
        self.assertTrue(est_main_deployee(_main(3)))

    def test_main_ouverte_reste_ouverte_a_l_horizontale(self):
        horizontale = _tourner(_main(4), math.pi / 2)
        self.assertTrue(est_main_ouverte(horizontale))
        self.assertFalse(est_poing(horizontale))


class ModesTests(unittest.TestCase):
    def test_deux_mains_ouvertes_ecartees_zoom_avant(self):
        fsm = _fsm()
        mains = [_main(4, x=0.30), _main(4, x=0.60)]
        self.assertIsNone(fsm.alimenter_plusieurs(mains, 0.0))
        self.assertIsNone(fsm.alimenter_plusieurs(mains, 0.45))
        self.assertEqual(fsm.etat_zoom, "PRET - ecarte ou rapproche")
        self.assertIsNone(fsm.alimenter_plusieurs(
            [_main(4, x=0.26), _main(4, x=0.64)], 0.55))
        self.assertEqual(fsm.alimenter_plusieurs(
            [_main(4, x=0.20), _main(4, x=0.75)], 0.65), "zoom_agrandir")
        self.assertEqual(fsm.etat_zoom, "retire au moins une main")

    def test_deux_mains_rapprochees_zoom_arriere_et_exigent_une_absence(self):
        fsm = _fsm()
        mains = [_main(4, x=0.20), _main(4, x=0.80)]
        fsm.alimenter_plusieurs(mains, 0.0)
        fsm.alimenter_plusieurs(mains, 0.45)
        self.assertEqual(fsm.alimenter_plusieurs(
            [_main(4, x=0.32), _main(4, x=0.68)], 0.60), "zoom_reduire")
        # Garder deux mains, même sans deux paumes ouvertes, ne réarme pas le zoom.
        self.assertIsNone(fsm.alimenter_plusieurs(
            [_main(2, x=0.32), _main(4, x=0.68)], 1.20))
        self.assertEqual(fsm.etat_zoom, "retire au moins une main")
        # Une main sortie du cadre autorise ensuite une nouvelle stabilisation.
        self.assertIsNone(fsm.alimenter_plusieurs([_main(4, x=0.3)], 1.30))
        self.assertEqual(fsm.etat_zoom, "montre 2 mains ouvertes")

    def test_zoom_arriere_est_plus_sensible_que_zoom_avant(self):
        fsm = _fsm()
        mains = [_main(4, x=0.25), _main(4, x=0.75)]
        fsm.alimenter_plusieurs(mains, 0.0)
        fsm.alimenter_plusieurs(mains, 0.45)
        # Un rapprochement de 0,09 dépasse le seuil arrière (0,08).
        self.assertEqual(fsm.alimenter_plusieurs(
            [_main(4, x=0.295), _main(4, x=0.705)], 0.55), "zoom_reduire")

        fsm.alimenter_plusieurs([_main(4, x=0.3)], 0.65)
        fsm.alimenter_plusieurs(mains, 0.75)
        fsm.alimenter_plusieurs(mains, 1.20)
        # Le même écartement reste sous le seuil avant (0,12).
        self.assertIsNone(fsm.alimenter_plusieurs(
            [_main(4, x=0.205), _main(4, x=0.795)], 1.30))

    def test_deux_mains_non_ouvertes_ne_declenchent_pas_le_zoom(self):
        fsm = _fsm()
        for t in (0.0, 0.5, 1.0):
            self.assertIsNone(fsm.alimenter_plusieurs(
                [_main(2, x=0.2), _main(4, x=0.8)], t))
        self.assertEqual(fsm.etat_zoom, "montre 2 mains ouvertes")

    def test_poing_reste_prioritaire_avec_deux_mains_visibles(self):
        fsm = _fsm()
        mains = [_main(0, x=0.3), _main(4, x=0.7)]
        self.assertIsNone(fsm.alimenter_plusieurs(mains, 0.0))
        self.assertEqual(fsm.alimenter_plusieurs(mains, 1.1), "poing")

    def test_main_ouverte_et_pouce_sont_tenus_une_seule_fois(self):
        fsm = _fsm()
        self.assertIsNone(fsm.alimenter(_main(4), 0.0))
        self.assertEqual(fsm.alimenter(_main(4), 1.1), "main_ouverte")
        self.assertIsNone(fsm.alimenter(_main(4), 2.5))
        fsm.alimenter(None, 2.6)
        self.assertIsNone(fsm.alimenter(_main(0, pouce=True), 3.0))
        self.assertEqual(fsm.alimenter(_main(0, pouce=True), 4.1), "pouce_leve")

    def test_mode_fenetres_accepte_plusieurs_swipes(self):
        fsm = _fsm()
        self.assertIsNone(fsm.alimenter(_main(2), 0.0))
        self.assertEqual(fsm.alimenter(_main(2), 0.6), "mode_fenetres")
        # On peut passer directement de 2 doigts à la paume ouverte.
        self.assertIsNone(fsm.alimenter(_main(4, x=0.2), 0.7))
        self.assertIsNone(fsm.alimenter(_main(4, x=0.2), 1.05))
        self.assertIsNone(fsm.alimenter(_main(4, x=0.3), 1.15))
        self.assertEqual(fsm.alimenter(_main(4, x=0.55), 1.25), "fenetre_droite")
        self.assertEqual(fsm.mode, "fenetres")
        self.assertEqual(fsm.etat_swipe, "sors la main du cadre")

        # La même main ne peut pas déclencher deux fois sans quitter le cadre.
        self.assertIsNone(fsm.alimenter(_main(4, x=0.2), 1.4))
        self.assertIsNone(fsm.alimenter(None, 1.5))
        self.assertIsNone(fsm.alimenter(_main(4, x=0.60), 1.6))
        self.assertIsNone(fsm.alimenter(_main(4, x=0.60), 1.95))
        self.assertIsNone(fsm.alimenter(_main(4, x=0.50), 2.05))
        self.assertEqual(fsm.alimenter(_main(4, x=0.25), 2.15), "fenetre_gauche")
        self.assertEqual(fsm.mode, "fenetres")

        # On peut encore repartir dans le même sens sans réarmer les 2 doigts.
        self.assertIsNone(fsm.alimenter(None, 2.25))
        self.assertIsNone(fsm.alimenter(_main(4, x=0.60), 2.35))
        self.assertIsNone(fsm.alimenter(_main(4, x=0.60), 2.70))
        self.assertIsNone(fsm.alimenter(_main(4, x=0.50), 2.80))
        self.assertEqual(fsm.alimenter(_main(4, x=0.25), 2.90), "fenetre_gauche")

    def test_mode_audio_vertical_regle_le_volume(self):
        fsm = _fsm()
        fsm.alimenter(_main(3), 0.0)
        self.assertEqual(fsm.alimenter(_main(3), 0.6), "mode_audio")
        self.assertIsNone(fsm.alimenter(_main(4, y=0.65), 0.7))
        self.assertIsNone(fsm.alimenter(_main(4, y=0.65), 1.05))
        self.assertIsNone(fsm.alimenter(_main(4, y=0.55), 1.15))
        self.assertEqual(fsm.alimenter(_main(4, y=0.30), 1.25), "volume_haut")

    def test_axe_vertical_peut_etre_inverse_par_calibration(self):
        fsm = _fsm()
        fsm.inverser_vertical = True
        fsm.alimenter(_main(3), 0.0)
        self.assertEqual(fsm.alimenter(_main(3), 0.6), "mode_audio")
        self.assertIsNone(fsm.alimenter(_main(4, y=0.65), 0.7))
        self.assertIsNone(fsm.alimenter(_main(4, y=0.65), 1.05))
        self.assertIsNone(fsm.alimenter(_main(4, y=0.55), 1.15))
        self.assertEqual(fsm.alimenter(_main(4, y=0.30), 1.25), "volume_bas")

    def test_mode_accepte_une_paume_partiellement_occultee(self):
        fsm = _fsm()
        fsm.alimenter(_main(2), 0.0)
        self.assertEqual(fsm.alimenter(_main(2), 0.6), "mode_fenetres")
        self.assertIsNone(fsm.alimenter(_main(3, x=0.2), 0.7))
        self.assertIsNone(fsm.alimenter(_main(3, x=0.2), 1.05))
        self.assertIsNone(fsm.alimenter(_main(3, x=0.3), 1.12))
        self.assertEqual(fsm.alimenter(_main(3, x=0.5), 1.20), "fenetre_droite")

    def test_retour_dans_le_cadre_ne_compte_pas_comme_swipe(self):
        fsm = _fsm()
        fsm.alimenter(_main(2), 0.0)
        self.assertEqual(fsm.alimenter(_main(2), 0.6), "mode_fenetres")
        fsm.alimenter(None, 0.7)
        self.assertIsNone(fsm.alimenter(_main(4, x=0.1), 0.8))
        # Grand mouvement pendant la phase de stabilisation : aucun geste.
        self.assertIsNone(fsm.alimenter(_main(4, x=0.6), 0.9))
        self.assertIsNone(fsm.alimenter(_main(4, x=0.6), 1.25))
        self.assertEqual(fsm.etat_swipe, "PRET - swipe maintenant")
        self.assertIsNone(fsm.alimenter(_main(4, x=0.5), 1.35))
        self.assertEqual(fsm.alimenter(_main(4, x=0.25), 1.45), "fenetre_gauche")

    def test_derive_lente_n_empeche_pas_l_etat_pret(self):
        fsm = _fsm()
        fsm.alimenter(_main(2), 0.0)
        self.assertEqual(fsm.alimenter(_main(2), 0.6), "mode_fenetres")
        self.assertIsNone(fsm.alimenter(_main(4, x=0.20), 0.70))
        self.assertIsNone(fsm.alimenter(_main(4, x=0.24), 0.82))
        self.assertIsNone(fsm.alimenter(_main(4, x=0.28), 0.94))
        self.assertIsNone(fsm.alimenter(_main(4, x=0.32), 1.06))
        self.assertEqual(fsm.etat_swipe, "PRET - swipe maintenant")

    def test_swipe_sans_mode_ne_declenche_rien(self):
        fsm = _fsm()
        self.assertIsNone(fsm.alimenter(_main(4, x=0.2), 0.0))
        self.assertIsNone(fsm.alimenter(_main(4, x=0.5), 0.2))

    def test_expiration_du_mode_est_visible_en_calibration(self):
        fsm = _fsm()
        fsm.alimenter(_main(2), 0.0)
        self.assertEqual(fsm.alimenter(_main(2), 0.6), "mode_fenetres")
        self.assertIsNone(fsm.alimenter(_main(4), 5.7))
        self.assertIsNone(fsm.mode)
        self.assertEqual(fsm.debug_evenement, "mode_fenetres_expire")


if __name__ == "__main__":
    unittest.main()
