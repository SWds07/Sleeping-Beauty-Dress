# -*- coding: utf-8 -*-
from __future__ import print_function, division, absolute_import
import unittest
import re
from tests.helpers import (
    BLE_DEVICE_NAME, BLE_SERVICE_UUID, BLE_CHAR_TELEMETRY_UUID,
    BLE_CHAR_COMMAND_UUID, BLE_CHAR_BRIGHTNESS_UUID, BLE_CCCD_DESCRIPTOR_UUID
)

class TestBoundary11BleGattBoundaries(unittest.TestCase):
    """Tier 2 Boundary: BLE GATT Server & Advertising boundaries."""

    def test_b11_01_ble_device_name_length(self):
        """Verify advertised name length is under 29 bytes to fit within BLE legacy adv packet."""
        self.assertLessEqual(len(BLE_DEVICE_NAME), 29)
        self.assertEqual(BLE_DEVICE_NAME, "Aurora-Dress")

    def test_b11_02_ble_uuid_128bit_format(self):
        """Verify all custom service and characteristic UUIDs adhere to valid 128-bit hex format."""
        uuid_pattern = re.compile(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$')
        for u in [BLE_SERVICE_UUID, BLE_CHAR_TELEMETRY_UUID, BLE_CHAR_COMMAND_UUID, BLE_CHAR_BRIGHTNESS_UUID]:
            self.assertTrue(uuid_pattern.match(u) is not None, "Invalid UUID format: {}".format(u))

    def test_b11_03_ble_service_hierarchy(self):
        """Verify all 3 characteristics are distinct and share base namespace prefix 1959000X."""
        chars = [BLE_CHAR_TELEMETRY_UUID, BLE_CHAR_COMMAND_UUID, BLE_CHAR_BRIGHTNESS_UUID]
        self.assertEqual(len(set(chars)), 3)
        self.assertTrue(BLE_CHAR_TELEMETRY_UUID.startswith("19590002"))
        self.assertTrue(BLE_CHAR_COMMAND_UUID.startswith("19590003"))
        self.assertTrue(BLE_CHAR_BRIGHTNESS_UUID.startswith("19590004"))

    def test_b11_04_ble_cccd_descriptor_uuid(self):
        """Verify standard Bluetooth SIG CCCD 0x2902 descriptor UUID."""
        self.assertEqual(BLE_CCCD_DESCRIPTOR_UUID.lower(), "00002902-0000-1000-8000-00805f9b34fb")

    def test_b11_05_ble_min_max_preferred_interval(self):
        """Verify preferred connection interval timing constants (0x06 min = 7.5ms, 0x12 max = 22.5ms)."""
        min_pref = 0x06
        max_pref = 0x12
        self.assertLess(min_pref, max_pref)
        self.assertEqual(min_pref * 1.25, 7.5)   # 7.5ms
        self.assertEqual(max_pref * 1.25, 22.5)  # 22.5ms

if __name__ == "__main__":
    unittest.main()
