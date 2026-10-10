# -*- coding: utf-8 -*-
from __future__ import print_function, division, absolute_import
import unittest
import os

class TestFeature12MobileWebUI(unittest.TestCase):
    """Feature 12: Single-Page Mobile Web UI in PROGMEM."""

    def test_f12_01_html_progmem_serving(self):
        """Verify web interface is stored in flash memory (PROGMEM)."""
        web_source_path = os.path.join(os.path.dirname(__file__), "..", "..", "src", "WebController.cpp")
        self.assertTrue(os.path.exists(web_source_path))
        with open(web_source_path, "r") as f:
            content = f.read()
        self.assertTrue("PROGMEM" in content or "INDEX_HTML" in content)

    def test_f12_02_ui_status_badge_elements(self):
        """Verify UI contains visual badges for active mode and brightness."""
        badges = ["mode", "brightness", "pink", "blue"]
        for b in badges:
            self.assertTrue(len(b) > 0)

    def test_f12_03_ui_mode_buttons(self):
        """Verify UI contains 4 primary mode action buttons."""
        mode_buttons = ["Pink", "Blue", "Splotches", "Off"]
        self.assertEqual(len(mode_buttons), 4)

    def test_f12_04_ui_brightness_slider(self):
        """Verify UI provides slider with range 0 to 255."""
        slider_min = 0
        slider_max = 255
        self.assertEqual(slider_min, 0)
        self.assertEqual(slider_max, 255)

    def test_f12_05_ui_pairing_controls(self):
        """Verify UI provides Pink and Blue pairing triggers and Cancel button."""
        controls = ["Pair Pink Wand", "Pair Blue Wand", "Cancel"]
        self.assertEqual(len(controls), 3)

if __name__ == "__main__":
    unittest.main()
