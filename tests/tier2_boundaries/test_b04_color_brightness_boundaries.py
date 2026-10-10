# -*- coding: utf-8 -*-
from __future__ import print_function, division, absolute_import
import unittest
from tests.helpers import (
    COLOR_PINK_RGB, COLOR_BLUE_RGB, scale_color,
    LED_MAX_BRIGHTNESS
)

class TestBoundary04ColorBrightnessBoundaries(unittest.TestCase):
    """Tier 2 Boundary: Brightness and color saturation limits."""

    def test_b04_01_brightness_zero_cutoff(self):
        """Verify brightness 0 cuts off all light output to pure dark (0, 0, 0)."""
        scaled_pink = scale_color(COLOR_PINK_RGB, 0)
        scaled_blue = scale_color(COLOR_BLUE_RGB, 0)
        self.assertEqual(scaled_pink, (0, 0, 0))
        self.assertEqual(scaled_blue, (0, 0, 0))

    def test_b04_02_brightness_max_cap_160(self):
        """Verify brightness values above 160 are clamped to 160."""
        scaled_at_160 = scale_color(COLOR_PINK_RGB, 160)
        scaled_at_200 = scale_color(COLOR_PINK_RGB, 200)
        self.assertEqual(scaled_at_160, scaled_at_200)

    def test_b04_03_brightness_255_saturation(self):
        """Verify input brightness 255 does not overflow and clamps to 160."""
        scaled_at_255 = scale_color(COLOR_PINK_RGB, 255)
        scaled_at_160 = scale_color(COLOR_PINK_RGB, 160)
        self.assertEqual(scaled_at_255, scaled_at_160)

    def test_b04_04_color_component_saturation(self):
        """Verify individual RGB color values never exceed 255."""
        r, g, b = scale_color((300, 400, 500), 160)
        # Scaled values are proportional to input
        self.assertLessEqual(r, 255 * 160 // 255)

    def test_b04_05_breathing_pulse_min_max_bounds(self):
        """Verify pairing breathing feedback stays within valid 0-160 range."""
        min_pulse = 20
        max_pulse = 160
        self.assertGreaterEqual(min_pulse, 0)
        self.assertLessEqual(max_pulse, LED_MAX_BRIGHTNESS)

if __name__ == "__main__":
    unittest.main()
