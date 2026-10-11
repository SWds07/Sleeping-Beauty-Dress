# -*- coding: utf-8 -*-
from __future__ import print_function, division, absolute_import
import unittest
from tests.helpers import (
    pack_telemetry, unpack_telemetry, WandInteractionSimulator
)

class TestFeature12BleTelemetry(unittest.TestCase):
    """Feature 12: BLE Telemetry Characteristic & 15-byte Binary Packet Protocol."""

    def test_f12_01_telemetry_payload_size_15_bytes(self):
        """Verify binary telemetry payload is strictly 15 bytes."""
        packet = pack_telemetry(1, 160, 0, 0x2F073545, 0x1A2B3C4D, 0)
        self.assertEqual(len(packet), 15)

    def test_f12_02_telemetry_field_offsets(self):
        """Verify field byte offsets match Android DressTelemetryParser contract."""
        # mode=2, brightness=200, pairing=1, pink=0x11223344, blue=0x55667788, last=0x99AABBCC
        packet = bytearray(pack_telemetry(2, 200, 1, 0x11223344, 0x55667788, 0x99AABBCC))
        self.assertEqual(packet[0], 2)   # offset 0: mode
        self.assertEqual(packet[1], 200) # offset 1: brightness
        self.assertEqual(packet[2], 1)   # offset 2: pairingState

    def test_f12_03_telemetry_little_endian_uint32(self):
        """Verify 32-bit wand IDs are encoded in Little-Endian byte order."""
        raw = pack_telemetry(1, 160, 0, 0x2F073545, 0, 0)
        packet = bytearray(raw)
        # 0x2F073545 in little endian: 0x45, 0x35, 0x07, 0x2F
        self.assertEqual(packet[3], 0x45)
        self.assertEqual(packet[4], 0x35)
        self.assertEqual(packet[5], 0x07)
        self.assertEqual(packet[6], 0x2F)

        unpacked = unpack_telemetry(raw)
        self.assertEqual(unpacked["pinkWandId"], 0x2F073545)

    def test_f12_04_telemetry_unassigned_wand_zeros(self):
        """Verify unassigned wand IDs serialize as 0x00000000."""
        packet = pack_telemetry(0, 0, 0, 0, 0, 0)
        unpacked = unpack_telemetry(packet)
        self.assertEqual(unpacked["pinkWandId"], 0)
        self.assertEqual(unpacked["blueWandId"], 0)
        self.assertEqual(unpacked["lastWandId"], 0)

    def test_f12_05_telemetry_state_reflection(self):
        """Verify simulator state changes reflect in generated BLE telemetry packet."""
        sim = WandInteractionSimulator(pink_id=0x2F073545, blue_id=0x1A2B3C4D)
        sim.mode = "PINK"
        sim.brightness = 140
        sim.pairing_state = "NONE"

        raw = sim.get_ble_telemetry_bytes()
        self.assertEqual(len(raw), 15)
        unpacked = unpack_telemetry(raw)
        self.assertEqual(unpacked["mode"], 1)  # PINK=1
        self.assertEqual(unpacked["brightness"], 140)
        self.assertEqual(unpacked["pairingState"], 0)  # NONE=0
        self.assertEqual(unpacked["pinkWandId"], 0x2F073545)
        self.assertEqual(unpacked["blueWandId"], 0x1A2B3C4D)

if __name__ == "__main__":
    unittest.main()
