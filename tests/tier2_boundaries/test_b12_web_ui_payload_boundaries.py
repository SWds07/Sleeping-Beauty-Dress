# -*- coding: utf-8 -*-
from __future__ import print_function, division, absolute_import
import unittest
import os
from tests.helpers import pack_telemetry, unpack_telemetry

class TestBoundary12BleTelemetryPayloadBoundaries(unittest.TestCase):
    """Tier 2 Boundary: BLE Telemetry payload size and encoding boundaries."""

    def setUp(self):
        ble_path = os.path.join(os.path.dirname(__file__), "..", "..", "src", "BleController.cpp")
        self.assertTrue(os.path.exists(ble_path))
        with open(ble_path, "r") as f:
            self.ble_content = f.read()

    def test_b12_01_packed_telemetry_alignment(self):
        """Verify DressTelemetryPacket struct in BleController.cpp uses 1-byte packed alignment."""
        self.assertIn("#pragma pack(push, 1)", self.ble_content)
        self.assertIn("struct DressTelemetryPacket", self.ble_content)
        self.assertIn("#pragma pack(pop)", self.ble_content)

    def test_b12_02_packed_telemetry_size_15_bytes(self):
        """Verify packed telemetry buffer is strictly 15 bytes across all value ranges."""
        packet_min = pack_telemetry(0, 0, 0, 0, 0, 0)
        packet_max = pack_telemetry(4, 255, 2, 0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF)
        self.assertEqual(len(packet_min), 15)
        self.assertEqual(len(packet_max), 15)

    def test_b12_03_telemetry_mode_boundaries(self):
        """Verify telemetry mode boundaries (0=OFF, 1=PINK, 2=BLUE, 3=SPLOTCHES, 4=PAIRING_FEEDBACK)."""
        for m in range(5):
            pkt = pack_telemetry(m, 100, 0, 0, 0, 0)
            unpacked = unpack_telemetry(pkt)
            self.assertEqual(unpacked["mode"], m)

    def test_b12_04_telemetry_pairing_state_boundaries(self):
        """Verify pairing state boundaries (0=NONE, 1=PAIR_PINK, 2=PAIR_BLUE)."""
        for p in range(3):
            pkt = pack_telemetry(0, 100, p, 0, 0, 0)
            unpacked = unpack_telemetry(pkt)
            self.assertEqual(unpacked["pairingState"], p)

    def test_b12_05_telemetry_uint32_bounds(self):
        """Verify 32-bit uint IDs roundtrip successfully up to 0xFFFFFFFF without overflow."""
        test_ids = [0x00000000, 0x2F073545, 0x1A2B3C4D, 0x7FFFFFFF, 0xFFFFFFFF]
        for tid in test_ids:
            pkt = pack_telemetry(1, 160, 0, tid, tid, tid)
            unpacked = unpack_telemetry(pkt)
            self.assertEqual(unpacked["pinkWandId"], tid)
            self.assertEqual(unpacked["blueWandId"], tid)
            self.assertEqual(unpacked["lastWandId"], tid)

if __name__ == "__main__":
    unittest.main()
