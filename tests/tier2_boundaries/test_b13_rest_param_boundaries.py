# -*- coding: utf-8 -*-
from __future__ import print_function, division, absolute_import
import unittest
from tests.helpers import WandInteractionSimulator, LED_MAX_BRIGHTNESS

class TestBoundary13RestParamBoundaries(unittest.TestCase):
    """Tier 2 Boundary: REST API parameter validation and boundary clamping."""

    def setUp(self):
        self.sim = WandInteractionSimulator(pink_id=0, blue_id=0)

    def test_b13_01_brightness_param_above_255(self):
        """Verify val=300 is clamped to LED_MAX_BRIGHTNESS (160)."""
        status, data = self.sim.handle_rest_request("/brightness", {"val": "300"})
        self.assertEqual(status, 200)
        self.assertEqual(self.sim.brightness, LED_MAX_BRIGHTNESS)

    def test_b13_02_brightness_param_negative(self):
        """Verify val=-50 is clamped to 0."""
        status, data = self.sim.handle_rest_request("/brightness", {"val": "-50"})
        self.assertEqual(status, 200)
        self.assertEqual(self.sim.brightness, 0)

    def test_b13_03_brightness_param_non_numeric(self):
        """Verify non-numeric val=invalid does not crash and leaves brightness unchanged."""
        original = self.sim.brightness
        status, data = self.sim.handle_rest_request("/brightness", {"val": "invalid"})
        self.assertEqual(status, 200)
        self.assertEqual(self.sim.brightness, original)

    def test_b13_04_brightness_param_missing(self):
        """Verify /brightness without val parameter succeeds without modifying brightness."""
        original = self.sim.brightness
        status, data = self.sim.handle_rest_request("/brightness")
        self.assertEqual(status, 200)
        self.assertEqual(self.sim.brightness, original)

    def test_b13_05_unpaired_wand_status_format(self):
        """Verify wand ID of 0 is formatted as 'Not Paired' in status JSON."""
        status, data = self.sim.handle_rest_request("/api/status")
        self.assertEqual(status, 200)
        self.assertEqual(data.get("pinkWand"), "Not Paired")
        self.assertEqual(data.get("blueWand"), "Not Paired")

if __name__ == "__main__":
    unittest.main()
