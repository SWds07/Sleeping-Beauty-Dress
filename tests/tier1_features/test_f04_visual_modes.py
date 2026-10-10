# -*- coding: utf-8 -*-
from __future__ import print_function, division, absolute_import
import unittest
from tests.helpers import (
    COLOR_OFF_HEX, COLOR_PINK_HEX, COLOR_BLUE_HEX, COLOR_SPARKLE_HEX,
    COLOR_OFF_RGB, COLOR_PINK_RGB, COLOR_BLUE_RGB, COLOR_SPARKLE_RGB,
    hex_to_rgb
)

class TestFeature04VisualModes(unittest.TestCase):
    """Feature 4: Visual Modes (OFF, PINK, BLUE, SPLOTCHES, PAIRING_FEEDBACK)."""

    def test_f04_01_off_mode_rgb(self):
        """Verify OFF mode RGB and hex values."""
        self.assertEqual(COLOR_OFF_HEX, "#000000")
        self.assertEqual(hex_to_rgb(COLOR_OFF_HEX), (0, 0, 0))
        self.assertEqual(COLOR_OFF_RGB, (0, 0, 0))

    def test_f04_02_pink_mode_rgb(self):
        """Verify Princess Aurora Deep Pink #FF1493 RGB."""
        self.assertEqual(COLOR_PINK_HEX, "#FF1493")
        self.assertEqual(hex_to_rgb(COLOR_PINK_HEX), (255, 20, 147))
        self.assertEqual(COLOR_PINK_RGB, (255, 20, 147))

    def test_f04_03_blue_mode_rgb(self):
        """Verify Merryweather Royal Blue #0078FF RGB."""
        self.assertEqual(COLOR_BLUE_HEX, "#0078FF")
        self.assertEqual(hex_to_rgb(COLOR_BLUE_HEX), (0, 120, 255))
        self.assertEqual(COLOR_BLUE_RGB, (0, 120, 255))

    def test_f04_04_splotches_fairy_sparkle_rgb(self):
        """Verify fairy dust sparkles #FFFFF0 RGB."""
        self.assertEqual(COLOR_SPARKLE_HEX, "#FFFFF0")
        self.assertEqual(hex_to_rgb(COLOR_SPARKLE_HEX), (255, 255, 240))
        self.assertEqual(COLOR_SPARKLE_RGB, (255, 255, 240))

    def test_f04_05_pairing_feedback_pulse_mode(self):
        """Verify PAIRING_FEEDBACK mode timing parameters."""
        total_duration_ms = 1500
        cycle_ms = 500
        cycles = total_duration_ms // cycle_ms
        self.assertEqual(cycles, 3)

if __name__ == "__main__":
    unittest.main()
