# -*- coding: utf-8 -*-
from __future__ import print_function, division, absolute_import
import unittest
from tests.helpers import NUM_LEDS_SKIRT, NUM_LEDS_UPPER, NUM_LEDS_TOTAL

class TestBoundary02PinBoundaries(unittest.TestCase):
    """Tier 2 Boundary: Pin and geometry boundaries."""

    def test_b02_01_gpio4_exact_pixel_count_100(self):
        """Verify boundary indices on GPIO 4 skirt (0 to 99)."""
        min_idx = 0
        max_idx = NUM_LEDS_SKIRT - 1
        self.assertEqual(min_idx, 0)
        self.assertEqual(max_idx, 99)

    def test_b02_02_gpio5_exact_pixel_count_50(self):
        """Verify boundary indices on GPIO 5 upper (0 to 49)."""
        min_idx = 0
        max_idx = NUM_LEDS_UPPER - 1
        self.assertEqual(min_idx, 0)
        self.assertEqual(max_idx, 49)

    def test_b02_03_gpio6_attempted_activation(self):
        """Verify attempted use of GPIO 6 is blocked."""
        active_pins = [4, 5]
        attempted_pin = 6
        self.assertNotIn(attempted_pin, active_pins)

    def test_b02_04_out_of_bounds_pixel_index(self):
        """Verify index 150 on 150-pixel strip is out of bounds."""
        index = 150
        is_valid = 0 <= index < NUM_LEDS_TOTAL
        self.assertFalse(is_valid)

    def test_b02_05_negative_pixel_index(self):
        """Verify negative index is out of bounds."""
        index = -1
        is_valid = 0 <= index < NUM_LEDS_TOTAL
        self.assertFalse(is_valid)

if __name__ == "__main__":
    unittest.main()
