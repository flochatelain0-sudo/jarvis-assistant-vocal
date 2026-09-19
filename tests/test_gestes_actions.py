"""Tests purs des raccourcis déclenchés par les gestes."""
import unittest

from core.gestes import _navigation_horizontale, _raccourci_zoom


class NavigationGestesTests(unittest.TestCase):
    def test_navigation_par_defaut_reste_dans_application_active(self):
        self.assertEqual(
            _navigation_horizontale("suivant"),
            ("ctrl+tab", "🗂 Onglet suivant"),
        )
        self.assertEqual(
            _navigation_horizontale("precedent"),
            ("ctrl+shift+tab", "🗂 Onglet précédent"),
        )

    def test_ancien_alt_tab_reste_disponible_par_configuration(self):
        self.assertEqual(
            _navigation_horizontale("suivant", "applications"),
            ("alt+tab", "🪟 Application suivante"),
        )
        self.assertEqual(
            _navigation_horizontale("precedent", "alt_tab"),
            ("alt+shift+tab", "🪟 Application précédente"),
        )

    def test_zoom_utilise_les_raccourcis_de_application_active(self):
        self.assertEqual(
            _raccourci_zoom("agrandir"),
            ("ctrl+=", "🔎 Zoom avant"),
        )
        self.assertEqual(
            _raccourci_zoom("reduire"),
            ("ctrl+-", "🔍 Zoom arrière"),
        )


if __name__ == "__main__":
    unittest.main()
