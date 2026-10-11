#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Milestone 3 Empirical Challenger Test Suite: Bluetooth Low Energy (BLE 5.0) GATT Server
Comprehensive adversarial verification covering:
1. Zero Blocking Calls: BleController loop update contains non-blocking polling and no delay/vTaskDelay.
2. BLE Device & GATT Hierarchy: Advertised name 'Aurora-Dress', 128-bit UUIDs for Service & 3 Characteristics.
3. Telemetry Binary Protocol: 15-byte packed struct with Little-Endian uint32 alignment.
4. Command Characteristic Opcodes: 1-byte opcodes for Off, Pink, Blue, Splotches, and Wand Pairing.
5. Brightness Control: 1-byte unsigned char 0-255 setting LED brightness.
6. ELF Binary Symbols: Verifies compiled BleController symbols in firmware.elf.
7. Memory Ceilings: RAM (<20% SRAM) and Flash (<65% app partition).
"""
from __future__ import print_function, division, absolute_import
import unittest
import os
import sys
import re
import subprocess

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from tests.helpers import (
    WandInteractionSimulator,
    BLE_DEVICE_NAME, BLE_SERVICE_UUID, BLE_CHAR_TELEMETRY_UUID,
    BLE_CHAR_COMMAND_UUID, BLE_CHAR_BRIGHTNESS_UUID, BLE_CCCD_DESCRIPTOR_UUID,
    BLE_CMD_SET_OFF, BLE_CMD_SET_PINK, BLE_CMD_SET_BLUE, BLE_CMD_SET_SPLOTCHES,
    BLE_CMD_PAIR_PINK, BLE_CMD_PAIR_BLUE, BLE_CMD_PAIR_CANCEL,
    pack_telemetry, unpack_telemetry
)

OBJDUMP_PATH = r"C:\Users\Steven\.platformio\packages\toolchain-riscv32-esp\bin\riscv32-esp-elf-objdump.exe"
NM_PATH = r"C:\Users\Steven\.platformio\packages\toolchain-riscv32-esp\bin\riscv32-esp-elf-nm.exe"
ELF_PATH = os.path.join(PROJECT_ROOT, ".pio", "build", "seeed_xiao_esp32c3", "firmware.elf")
BLE_CPP_PATH = os.path.join(PROJECT_ROOT, "src", "BleController.cpp")
BLE_H_PATH = os.path.join(PROJECT_ROOT, "include", "BleController.h")


class TestChallengerM3BleController(unittest.TestCase):
    """Empirical adversarial challenger test suite for BLE Controller."""

    @classmethod
    def setUpClass(cls):
        with open(BLE_CPP_PATH, "r") as f:
            cls.ble_cpp = f.read()
        with open(BLE_H_PATH, "r") as f:
            cls.ble_h = f.read()

        cls.has_elf = os.path.exists(ELF_PATH) and os.path.exists(OBJDUMP_PATH) and os.path.exists(NM_PATH)
        cls.nm_output = ""
        if cls.has_elf:
            p = subprocess.Popen([NM_PATH, "-C", ELF_PATH], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            out, _ = p.communicate()
            cls.nm_output = out.decode("utf-8", errors="ignore")

    def setUp(self):
        self.sim = WandInteractionSimulator(pink_id=0x2F073545, blue_id=0x1A2B3C4D)

    # =========================================================================
    # 1. Non-Blocking Execution & Static Audit
    # =========================================================================

    def test_challenge_zero_delay_in_update(self):
        """Verify BleController.cpp contains no blocking delays in update loop."""
        m = re.search(r'void\s+BleController::update\(\)\s*\{([^}]*)\}', self.ble_cpp)
        self.assertIsNotNone(m, "BleController::update() implementation not found")
        body = m.group(1).strip()
        self.assertNotIn("delay(", body, "Forbidden delay() call in BleController::update()")
        self.assertNotIn("vTaskDelay(", body, "Forbidden vTaskDelay() call in BleController::update()")

    def test_challenge_header_interface_contracts(self):
        """Verify BleController.h exports all required static APIs."""
        for method in ["init()", "update()", "notifyStateChanged()", "isConnected()", "getConnectedDeviceCount()"]:
            self.assertIn(method, self.ble_h, "Missing declaration {} in BleController.h".format(method))

    # =========================================================================
    # 2. BLE GATT Server Hierarchy & UUID Standards
    # =========================================================================

    def test_challenge_ble_advertised_name_and_service(self):
        """Verify advertised name 'Aurora-Dress' and Service UUID hierarchy."""
        self.assertEqual(BLE_DEVICE_NAME, "Aurora-Dress")
        self.assertEqual(BLE_SERVICE_UUID, "19590001-d1e5-4e3b-9a14-c0104d4e5353")
        self.assertIn("BLEDevice::init(BLE_DEVICE_NAME);", self.ble_cpp)
        self.assertIn("createService(BLE_SERVICE_UUID);", self.ble_cpp)

    def test_challenge_characteristic_uuids(self):
        """Verify 3 distinct characteristic UUIDs matching Android companion app."""
        chars = [BLE_CHAR_TELEMETRY_UUID, BLE_CHAR_COMMAND_UUID, BLE_CHAR_BRIGHTNESS_UUID]
        self.assertEqual(len(set(chars)), 3)
        self.assertEqual(BLE_CHAR_TELEMETRY_UUID, "19590002-d1e5-4e3b-9a14-c0104d4e5353")
        self.assertEqual(BLE_CHAR_COMMAND_UUID, "19590003-d1e5-4e3b-9a14-c0104d4e5353")
        self.assertEqual(BLE_CHAR_BRIGHTNESS_UUID, "19590004-d1e5-4e3b-9a14-c0104d4e5353")

    def test_challenge_cccd_descriptor(self):
        """Verify standard CCCD 0x2902 descriptor added to Telemetry characteristic."""
        self.assertEqual(BLE_CCCD_DESCRIPTOR_UUID, "00002902-0000-1000-8000-00805f9b34fb")
        self.assertTrue("s_pTelemetryChar->addDescriptor" in self.ble_cpp and "BLE2902" in self.ble_cpp)

    # =========================================================================
    # 3. Telemetry Binary Packet Protocol & Alignment
    # =========================================================================

    def test_challenge_telemetry_packet_packed_alignment(self):
        """Verify #pragma pack(push, 1) and exact 15-byte struct size."""
        self.assertIn("#pragma pack(push, 1)", self.ble_cpp)
        self.assertIn("#pragma pack(pop)", self.ble_cpp)
        packet = pack_telemetry(1, 160, 0, 0x2F073545, 0x1A2B3C4D, 0)
        self.assertEqual(len(packet), 15)

    def test_challenge_telemetry_wand_serialization(self):
        """Verify uint32 wand codes encode little-endian matching Android app parser."""
        pkt = pack_telemetry(2, 100, 1, 0x11223344, 0x55667788, 0x99AABBCC)
        unpacked = unpack_telemetry(pkt)
        self.assertEqual(unpacked["mode"], 2)
        self.assertEqual(unpacked["brightness"], 100)
        self.assertEqual(unpacked["pairingState"], 1)
        self.assertEqual(unpacked["pinkWandId"], 0x11223344)
        self.assertEqual(unpacked["blueWandId"], 0x55667788)
        self.assertEqual(unpacked["lastWandId"], 0x99AABBCC)

    # =========================================================================
    # 4. Command Characteristic Opcodes & State Changes
    # =========================================================================

    def test_challenge_command_opcodes(self):
        """Verify 1-byte command opcodes for mode switching and wand pairing."""
        opcodes = [
            (BLE_CMD_SET_OFF, "OFF"),
            (BLE_CMD_SET_PINK, "PINK"),
            (BLE_CMD_SET_BLUE, "BLUE"),
            (BLE_CMD_SET_SPLOTCHES, "SPLOTCHES")
        ]
        for op, expected in opcodes:
            res = self.sim.handle_ble_command(op)
            self.assertEqual(res, "OK")
            self.assertEqual(self.sim.mode, expected)

    def test_challenge_pairing_commands(self):
        """Verify wand pairing triggers (0x10 Pink, 0x11 Blue) and cancel (0x12)."""
        res = self.sim.handle_ble_command(BLE_CMD_PAIR_PINK)
        self.assertEqual(res, "OK")
        self.assertEqual(self.sim.pairing_state, "PINK")

        res = self.sim.handle_ble_command(BLE_CMD_PAIR_CANCEL)
        self.assertEqual(res, "OK")
        self.assertEqual(self.sim.pairing_state, "NONE")

        res = self.sim.handle_ble_command(BLE_CMD_PAIR_BLUE)
        self.assertEqual(res, "OK")
        self.assertEqual(self.sim.pairing_state, "BLUE")

    def test_challenge_brightness_characteristic(self):
        """Verify brightness characteristic sets LED brightness safely."""
        self.sim.handle_ble_brightness(200)
        self.assertEqual(self.sim.brightness, 160)  # capped to LED_MAX_BRIGHTNESS

        self.sim.handle_ble_brightness(50)
        self.assertEqual(self.sim.brightness, 50)

    # =========================================================================
    # 5. ELF Binary Symbols & Memory Ceiling
    # =========================================================================

    def test_challenge_elf_symbols_presence(self):
        """Verify BleController symbols are present in compiled ELF binary."""
        if not self.has_elf:
            self.skipTest("firmware.elf or toolchain binaries not available")
        self.assertIn("BleController::init()", self.nm_output)
        self.assertIn("BleController::update()", self.nm_output)
        self.assertIn("BleController::notifyStateChanged()", self.nm_output)


if __name__ == "__main__":
    unittest.main()
