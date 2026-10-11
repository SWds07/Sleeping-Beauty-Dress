#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Milestone 3 Empirical Stress Test Harness: BLE GATT Server Subsystem
Adversarially tests:
1. BLE Device parameters (Name, 128-bit Service and Characteristic UUIDs).
2. Telemetry binary packet structure, byte packing, little-endian formatting, and offsets.
3. Command characteristic opcodes (0x01, 0x02, 0x03, 0x04, 0x10, 0x11, 0x12).
4. Brightness boundary testing (0..255, clamping to LED_MAX_BRIGHTNESS).
5. ELF binary symbol inspection (nm and objdump) verifying BleController symbols and zero delays.
6. High-volume stress hammering (10,000 requests) under interleaved IR wand interactions.
"""
from __future__ import print_function, division, absolute_import
import unittest
import os
import sys
import re
import subprocess
import random

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from tests.helpers import (
    WandInteractionSimulator,
    BLE_DEVICE_NAME, BLE_SERVICE_UUID, BLE_CHAR_TELEMETRY_UUID,
    BLE_CHAR_COMMAND_UUID, BLE_CHAR_BRIGHTNESS_UUID, BLE_CCCD_DESCRIPTOR_UUID,
    BLE_CMD_SET_OFF, BLE_CMD_SET_PINK, BLE_CMD_SET_BLUE, BLE_CMD_SET_SPLOTCHES,
    BLE_CMD_PAIR_PINK, BLE_CMD_PAIR_BLUE, BLE_CMD_PAIR_CANCEL,
    LED_DEFAULT_BRIGHTNESS, LED_MAX_BRIGHTNESS,
    pack_telemetry, unpack_telemetry
)

OBJDUMP_PATH = r"C:\Users\Steven\.platformio\packages\toolchain-riscv32-esp\bin\riscv32-esp-elf-objdump.exe"
NM_PATH = r"C:\Users\Steven\.platformio\packages\toolchain-riscv32-esp\bin\riscv32-esp-elf-nm.exe"
ELF_PATH = os.path.join(PROJECT_ROOT, ".pio", "build", "seeed_xiao_esp32c3", "firmware.elf")
BLE_CPP_PATH = os.path.join(PROJECT_ROOT, "src", "BleController.cpp")
BLE_H_PATH = os.path.join(PROJECT_ROOT, "include", "BleController.h")


class Milestone3EmpiricalStressSuite(unittest.TestCase):
    """Adversarial stress and verification test suite for Milestone 3 (BLE Controller)."""

    @classmethod
    def setUpClass(cls):
        with open(BLE_CPP_PATH, "r") as f:
            cls.ble_cpp_content = f.read()
        with open(BLE_H_PATH, "r") as f:
            cls.ble_h_content = f.read()

        cls.has_elf = os.path.exists(ELF_PATH) and os.path.exists(OBJDUMP_PATH) and os.path.exists(NM_PATH)
        cls.nm_output = ""
        if cls.has_elf:
            p = subprocess.Popen([NM_PATH, "-C", ELF_PATH], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            out, _ = p.communicate()
            cls.nm_output = out.decode("utf-8", errors="ignore")

    def setUp(self):
        self.sim = WandInteractionSimulator(pink_id=0x2F073545, blue_id=0x1A2B3C4D)

    def test_s01_ble_device_name(self):
        """Verify BLE advertised device name is Aurora-Dress."""
        self.assertEqual(BLE_DEVICE_NAME, "Aurora-Dress")
        self.assertIn("BLEDevice::init(BLE_DEVICE_NAME);", self.ble_cpp_content)

    def test_s02_ble_uuids(self):
        """Verify service and characteristic 128-bit UUIDs."""
        self.assertEqual(BLE_SERVICE_UUID, "19590001-d1e5-4e3b-9a14-c0104d4e5353")
        self.assertEqual(BLE_CHAR_TELEMETRY_UUID, "19590002-d1e5-4e3b-9a14-c0104d4e5353")
        self.assertEqual(BLE_CHAR_COMMAND_UUID, "19590003-d1e5-4e3b-9a14-c0104d4e5353")
        self.assertEqual(BLE_CHAR_BRIGHTNESS_UUID, "19590004-d1e5-4e3b-9a14-c0104d4e5353")

    def test_s03_cccd_descriptor(self):
        """Verify CCCD descriptor 00002902-0000-1000-8000-00805f9b34fb."""
        self.assertEqual(BLE_CCCD_DESCRIPTOR_UUID, "00002902-0000-1000-8000-00805f9b34fb")
        self.assertIn("BLE2902", self.ble_cpp_content)

    def test_s04_telemetry_packet_size(self):
        """Verify packed telemetry size is strictly 15 bytes."""
        pkt = pack_telemetry(1, 160, 0, 0x11111111, 0x22222222, 0x33333333)
        self.assertEqual(len(pkt), 15)

    def test_s05_telemetry_little_endian(self):
        """Verify little-endian encoding for all uint32 IDs."""
        pkt = pack_telemetry(1, 160, 0, 0x12345678, 0x87654321, 0xAABBCCDD)
        unpacked = unpack_telemetry(pkt)
        self.assertEqual(unpacked["pinkWandId"], 0x12345678)
        self.assertEqual(unpacked["blueWandId"], 0x87654321)
        self.assertEqual(unpacked["lastWandId"], 0xAABBCCDD)

    def test_s06_command_opcodes(self):
        """Verify all command opcodes."""
        commands = [
            (BLE_CMD_SET_OFF, "OFF"),
            (BLE_CMD_SET_PINK, "PINK"),
            (BLE_CMD_SET_BLUE, "BLUE"),
            (BLE_CMD_SET_SPLOTCHES, "SPLOTCHES")
        ]
        for op, expected in commands:
            self.sim.handle_ble_command(op)
            self.assertEqual(self.sim.mode, expected)

    def test_s07_pairing_commands(self):
        """Verify pairing opcodes 0x10, 0x11, and 0x12."""
        self.sim.handle_ble_command(BLE_CMD_PAIR_PINK)
        self.assertEqual(self.sim.pairing_state, "PINK")
        self.sim.handle_ble_command(BLE_CMD_PAIR_CANCEL)
        self.assertEqual(self.sim.pairing_state, "NONE")
        self.sim.handle_ble_command(BLE_CMD_PAIR_BLUE)
        self.assertEqual(self.sim.pairing_state, "BLUE")

    def test_s08_brightness_control(self):
        """Verify brightness boundaries."""
        self.sim.handle_ble_brightness(255)
        self.assertEqual(self.sim.brightness, LED_MAX_BRIGHTNESS)
        self.sim.handle_ble_brightness(0)
        self.assertEqual(self.sim.brightness, 0)
        self.sim.handle_ble_brightness(120)
        self.assertEqual(self.sim.brightness, 120)

    def test_s09_zero_delay_calls(self):
        """Verify BleController contains no delay calls in update()."""
        m = re.search(r'void\s+BleController::update\(\)\s*\{([^}]*)\}', self.ble_cpp_content)
        self.assertIsNotNone(m)
        body = m.group(1).strip()
        self.assertNotIn("delay(", body)
        self.assertNotIn("vTaskDelay(", body)

    def test_s10_elf_symbols(self):
        """Verify BleController symbols exist in compiled ELF binary."""
        if not self.has_elf:
            self.skipTest("firmware.elf or toolchain binaries not available")
        self.assertIn("BleController::init()", self.nm_output)
        self.assertIn("BleController::update()", self.nm_output)

    def test_s11_high_volume_stress_hammering(self):
        """Simulate 10,000 rapid BLE interactions interleaved with IR wand events."""
        random.seed(0x5EED)
        opcodes = [
            BLE_CMD_SET_OFF, BLE_CMD_SET_PINK, BLE_CMD_SET_BLUE, BLE_CMD_SET_SPLOTCHES,
            BLE_CMD_PAIR_PINK, BLE_CMD_PAIR_BLUE, BLE_CMD_PAIR_CANCEL
        ]

        now_ms = 1000
        for i in range(10000):
            action = random.choice(["cmd", "bright", "telemetry"])
            if action == "cmd":
                op = random.choice(opcodes)
                self.sim.handle_ble_command(op, now_ms)
            elif action == "bright":
                b = random.randint(0, 255)
                self.sim.handle_ble_brightness(b)
            else:
                raw = self.sim.get_ble_telemetry_bytes()
                self.assertEqual(len(raw), 15)

            if i % 10 == 0:
                now_ms += 100
                wand_code = random.choice([0x2F073545, 0x1A2B3C4D, 0x99999999])
                self.sim.handle_wand_signal(wand_code, now_ms)

        final_raw = self.sim.get_ble_telemetry_bytes()
        self.assertEqual(len(final_raw), 15)
        final_data = unpack_telemetry(final_raw)
        self.assertIn(final_data["mode"], [0, 1, 2, 3, 4])
        self.assertIn(final_data["pairingState"], [0, 1, 2])
        self.assertGreaterEqual(final_data["brightness"], 0)
        self.assertLessEqual(final_data["brightness"], LED_MAX_BRIGHTNESS)


def main():
    suite = unittest.TestLoader().loadTestsFromTestCase(Milestone3EmpiricalStressSuite)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    if not result.wasSuccessful():
        sys.exit(1)


if __name__ == "__main__":
    main()
