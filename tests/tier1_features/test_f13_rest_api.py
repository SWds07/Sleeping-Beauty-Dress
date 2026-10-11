# -*- coding: utf-8 -*-
from __future__ import print_function, division, absolute_import
import unittest
from tests.helpers import (
    WandInteractionSimulator,
    BLE_CMD_SET_OFF, BLE_CMD_SET_PINK, BLE_CMD_SET_BLUE, BLE_CMD_SET_SPLOTCHES,
    BLE_CMD_PAIR_PINK, BLE_CMD_PAIR_BLUE, BLE_CMD_PAIR_CANCEL,
    unpack_telemetry
)

class TestFeature13BleCommandBrightness(unittest.TestCase):
    """Feature 13: BLE Command & Brightness Control Protocols (1-byte Opcodes & Brightness)."""

    def setUp(self):
        self.sim = WandInteractionSimulator(pink_id=0x12345678, blue_id=0x87654321)

    def test_f13_01_command_mode_opcodes(self):
        """Verify 1-byte command opcodes for mode transitions."""
        commands = [
            (BLE_CMD_SET_PINK, "PINK"),
            (BLE_CMD_SET_BLUE, "BLUE"),
            (BLE_CMD_SET_SPLOTCHES, "SPLOTCHES"),
            (BLE_CMD_SET_OFF, "OFF")
        ]
        for opcode, expected_mode in commands:
            res = self.sim.handle_ble_command(opcode)
            self.assertEqual(res, "OK")
            self.assertEqual(self.sim.mode, expected_mode)

    def test_f13_02_command_pairing_opcodes(self):
        """Verify 1-byte command opcodes for wand pairing triggers and cancellation."""
        res = self.sim.handle_ble_command(BLE_CMD_PAIR_PINK)
        self.assertEqual(res, "OK")
        self.assertEqual(self.sim.pairing_state, "PINK")

        res = self.sim.handle_ble_command(BLE_CMD_PAIR_CANCEL)
        self.assertEqual(res, "OK")
        self.assertEqual(self.sim.pairing_state, "NONE")

        res = self.sim.handle_ble_command(BLE_CMD_PAIR_BLUE)
        self.assertEqual(res, "OK")
        self.assertEqual(self.sim.pairing_state, "BLUE")

    def test_f13_03_brightness_characteristic_control(self):
        """Verify 1-byte brightness characteristic write updates dress brightness."""
        res = self.sim.handle_ble_brightness(120)
        self.assertEqual(res, "OK")
        self.assertEqual(self.sim.brightness, 120)

    def test_f13_04_unknown_opcode_safety(self):
        """Verify unknown opcodes (e.g. 0x99) are safely handled and ignored."""
        res = self.sim.handle_ble_command(0x99)
        self.assertEqual(res, "UNKNOWN_OPCODE")

    def test_f13_05_ble_state_notification_sync(self):
        """Verify BLE commands immediately update packed telemetry state."""
        self.sim.handle_ble_command(BLE_CMD_SET_BLUE)
        self.sim.handle_ble_brightness(110)
        raw = self.sim.get_ble_telemetry_bytes()
        telemetry = unpack_telemetry(raw)
        self.assertEqual(telemetry["mode"], 2)  # BLUE=2
        self.assertEqual(telemetry["brightness"], 110)

if __name__ == "__main__":
    unittest.main()
