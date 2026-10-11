# -*- coding: utf-8 -*-
from __future__ import print_function, division, absolute_import
import unittest
from tests.helpers import WandInteractionSimulator, LED_MAX_BRIGHTNESS, unpack_telemetry

class TestBoundary13BleParamBoundaries(unittest.TestCase):
    """Tier 2 Boundary: BLE Command and Brightness parameter validation and boundary clamping."""

    def setUp(self):
        self.sim = WandInteractionSimulator(pink_id=0, blue_id=0)

    def test_b13_01_brightness_param_above_255(self):
        """Verify brightness values above 255 are clamped to LED_MAX_BRIGHTNESS (160)."""
        res = self.sim.handle_ble_brightness(300)
        self.assertEqual(res, "OK")
        self.assertEqual(self.sim.brightness, LED_MAX_BRIGHTNESS)

    def test_b13_02_brightness_param_negative(self):
        """Verify negative brightness values are clamped to 0."""
        res = self.sim.handle_ble_brightness(-50)
        self.assertEqual(res, "OK")
        self.assertEqual(self.sim.brightness, 0)

    def test_b13_03_brightness_param_non_numeric(self):
        """Verify unknown opcodes return UNKNOWN_OPCODE and leave mode unchanged."""
        original_mode = self.sim.mode
        res = self.sim.handle_ble_command(0xEE)
        self.assertEqual(res, "UNKNOWN_OPCODE")
        self.assertEqual(self.sim.mode, original_mode)

    def test_b13_04_brightness_param_missing(self):
        """Verify zero brightness sets LEDs off/dark without error."""
        res = self.sim.handle_ble_brightness(0)
        self.assertEqual(res, "OK")
        self.assertEqual(self.sim.brightness, 0)

    def test_b13_05_unpaired_wand_status_format(self):
        """Verify unassigned wand IDs are encoded as 0 in telemetry."""
        raw = self.sim.get_ble_telemetry_bytes()
        telemetry = unpack_telemetry(raw)
        self.assertEqual(telemetry["pinkWandId"], 0)
        self.assertEqual(telemetry["blueWandId"], 0)

if __name__ == "__main__":
    unittest.main()
