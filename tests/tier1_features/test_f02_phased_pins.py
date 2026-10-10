# -*- coding: utf-8 -*-
from __future__ import print_function, division, absolute_import
import unittest
from tests.helpers import (
    PIN_LED_SKIRT, PIN_LED_UPPER, PIN_LED_RSLEEVE_DISABLED,
    NUM_LEDS_SKIRT, NUM_LEDS_UPPER, NUM_LEDS_TOTAL
)

class TestFeature02PhasedPins(unittest.TestCase):
    """Feature 2: Phased Pin Architecture (GPIO 4 Skirt, GPIO 5 Upper, GPIO 6 disabled)."""

    def test_f02_01_phase1_skirt_pin_mapping(self):
        """Verify Phase 1 Skirt mapped to GPIO 4 with 100 pixels."""
        self.assertEqual(PIN_LED_SKIRT, 4)
        self.assertEqual(NUM_LEDS_SKIRT, 100)

    def test_f02_02_phase2_upper_pin_mapping(self):
        """Verify Phase 2 Upper Body / Sleeves mapped to GPIO 5 with 50 pixels."""
        self.assertEqual(PIN_LED_UPPER, 5)
        self.assertEqual(NUM_LEDS_UPPER, 50)

    def test_f02_03_disable_gpio6_pin_invariance(self):
        """Verify GPIO 6 is permanently disabled due to 2 RMT TX channel limit."""
        self.assertEqual(PIN_LED_RSLEEVE_DISABLED, 6)
        active_pins = [PIN_LED_SKIRT, PIN_LED_UPPER]
        self.assertNotIn(PIN_LED_RSLEEVE_DISABLED, active_pins)

    def test_f02_04_total_pixel_geometry(self):
        """Verify total LED count is strictly 150 pixels (100 skirt + 50 upper)."""
        self.assertEqual(NUM_LEDS_SKIRT + NUM_LEDS_UPPER, NUM_LEDS_TOTAL)
        self.assertEqual(NUM_LEDS_TOTAL, 150)

    def test_f02_05_independent_buffer_segments(self):
        """Verify independent buffer slice offsets."""
        offset_skirt = 0
        offset_upper = NUM_LEDS_SKIRT
        self.assertEqual(offset_skirt, 0)
        self.assertEqual(offset_upper, 100)

if __name__ == "__main__":
    unittest.main()
