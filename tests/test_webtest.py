import unittest
from unittest.mock import patch

from pc.webui import PAGE, open_dashboard


class WebDashboardTests(unittest.TestCase):
    def test_dashboard_has_live_state_and_timed_override_controls(self):
        self.assertIn("État en direct", PAGE)
        self.assertIn("Affiché sur le pet", PAGE)
        self.assertIn('value="15"', PAGE)
        self.assertIn("/manual-state", PAGE)
        self.assertIn("/manual-state/clear", PAGE)
        self.assertIn("/health", PAGE)
        self.assertIn("/pet/next", PAGE)
        self.assertIn("Installer", PAGE)
        self.assertIn("Activer", PAGE)
        self.assertIn("pet-canvas", PAGE)
        self.assertIn("/pets/activate", PAGE)
        self.assertIn("preview-pet", PAGE)
        self.assertIn("localStorage", PAGE)
        self.assertIn("/pet-preview/", PAGE)
        self.assertIn("Pet affiché sur le web", PAGE)
        self.assertIn("activeDevicePet", PAGE)
        self.assertIn("localStorage.setItem('openbuddy-web-preview-pet'", PAGE)
        live_panel = PAGE.split("<h2>État en direct</h2>", 1)[1].split("</section>", 1)[0]
        self.assertIn("pet-canvas", live_panel)
        self.assertIn("preview-pet", live_panel)
        self.assertNotIn("Aperçu web indépendant", PAGE)

    def test_launcher_adds_discovery_token_in_fragment(self):
        with patch("pc.webui.webbrowser.open", return_value=True) as open_browser:
            self.assertTrue(open_dashboard("http://127.0.0.1:19847/", "a" * 64))
        open_browser.assert_called_once_with("http://127.0.0.1:19847/#token=" + "a" * 64)


if __name__ == "__main__":
    unittest.main()
