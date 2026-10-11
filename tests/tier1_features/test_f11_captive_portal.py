# -*- coding: utf-8 -*-
from __future__ import print_function, division, absolute_import
import unittest
from tests.helpers import (
    BLE_DEVICE_NAME, BLE_SERVICE_UUID, BLE_CHAR_TELEMETRY_UUID,
    BLE_CHAR_COMMAND_UUID, BLE_CHAR_BRIGHTNESS_UUID, BLE_CCCD_DESCRIPTOR_UUID
)

class TestFeature11BleGattServer(unittest.TestCase):
    """Feature 11: BLE 5.0 GATT Server & Device Identification (UUID Hierarchy)."""

    def test_f11_01_ble_device_name(self):
        """Verify advertised BLE device name is 'Aurora-Dress'."""
        self.assertEqual(BLE_DEVICE_NAME, "Aurora-Dress")

    def test_f11_02_ble_service_uuid(self):
        """Verify primary service UUID is 19590001-d1e5-4e3b-9a14-c0104d4e5353."""
        self.assertEqual(BLE_SERVICE_UUID, "19590001-d1e5-4e3b-9a14-c0104d4e5353")

    def test_f11_03_telemetry_char_uuid(self):
        """Verify telemetry characteristic UUID is 19590002-d1e5-4e3b-9a14-c0104d4e5353."""
        self.assertEqual(BLE_CHAR_TELEMETRY_UUID, "19590002-d1e5-4e3b-9a14-c0104d4e5353")

    def test_f11_04_command_char_uuid(self):
        """Verify command characteristic UUID is 19590003-d1e5-4e3b-9a14-c0104d4e5353."""
        self.assertEqual(BLE_CHAR_COMMAND_UUID, "19590003-d1e5-4e3b-9a14-c0104d4e5353")

    def test_f11_05_brightness_char_uuid(self):
        """Verify brightness characteristic UUID is 19590004-d1e5-4e3b-9a14-c0104d4e5353."""
        self.assertEqual(BLE_CHAR_BRIGHTNESS_UUID, "19590004-d1e5-4e3b-9a14-c0104d4e5353")

if __name__ == "__main__":
    unittest.main()
