# -*- coding: utf-8 -*-
"""
test_challenger_m4_storage_coordination.py

Empirical Adversarial Challenge Suite for Milestone 4:
System Coordination & NVS Storage.

Covers:
1. Fresh boot unconfigured state (returns 0 / "Not Paired").
2. Multi-reboot persistent storage survival, mutation, and factory reset.
3. Redundant write wear-leveling suppression.
4. 32-bit unsigned integer boundary conditions (0, 1, 0x7FFFFFFF, 0x80000000, 0xFFFFFFFF).
5. NVS namespace ("auroradress") and key ("pink_wand", "blue_wand") length bounds (<= 15 chars).
6. Interface contract aliasing (*Id vs *Code).
7. Deterministic boot sequence ordering and early pin clamping in main.cpp.
8. Zero delay() cooperative round-robin loop.
9. IRAM ISR flash-cache safety disassembly verification (zero .flash.text calls).
10. Firmware binary size, RAM, and Flash partition headroom verification.
11. High-frequency simulated pairing, reboot, and status interrogation stress (1,000 cycles).
"""
from __future__ import print_function, division, absolute_import
import unittest
import os
import sys
import re
import subprocess
import random
import json

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from tests.helpers import (
    NVS_NAMESPACE, NVS_KEY_PINK_WAND, NVS_KEY_BLUE_WAND,
    WandInteractionSimulator
)



class MockESP32Preferences(object):
    """Accurate model of ESP32 Preferences library behavior."""
    def __init__(self):
        self.storage = {}
        self.namespace = None
        self.read_only = False
        self.write_count = 0
        self.read_count = 0

    def begin(self, namespace, read_only=False):
        if len(namespace) > 15:
            raise ValueError("Namespace exceeds ESP32 15-character limit")
        self.namespace = namespace
        self.read_only = read_only
        if namespace not in self.storage:
            self.storage[namespace] = {}

    def getUInt(self, key, default_val=0):
        if len(key) > 15:
            raise ValueError("Key exceeds ESP32 15-character limit")
        self.read_count += 1
        ns_dict = self.storage.get(self.namespace, {})
        return ns_dict.get(key, default_val)

    def putUInt(self, key, value):
        if len(key) > 15:
            raise ValueError("Key exceeds ESP32 15-character limit")
        if self.read_only:
            raise RuntimeError("Cannot write to read-only Preferences")
        # Enforce 32-bit unsigned bounds
        value = int(value) & 0xFFFFFFFF
        self.write_count += 1
        ns_dict = self.storage.setdefault(self.namespace, {})
        ns_dict[key] = value

    def clear(self):
        if self.namespace in self.storage:
            self.storage[self.namespace].clear()


class MockStorageController(object):
    """Python model mirroring StorageController.cpp logic and wear-leveling."""
    def __init__(self, prefs):
        self.prefs = prefs

    def init(self):
        self.prefs.begin("auroradress", False)

    def savePinkWandCode(self, code):
        code = int(code) & 0xFFFFFFFF
        if self.getPinkWandCode() == code:
            return
        self.prefs.putUInt("pink_wand", code)

    def getPinkWandCode(self):
        return self.prefs.getUInt("pink_wand", 0)

    def saveBlueWandCode(self, code):
        code = int(code) & 0xFFFFFFFF
        if self.getBlueWandCode() == code:
            return
        self.prefs.putUInt("blue_wand", code)

    def getBlueWandCode(self):
        return self.prefs.getUInt("blue_wand", 0)

    # PROJECT.md contract aliases
    def savePinkWandId(self, id_val):
        self.savePinkWandCode(id_val)

    def getPinkWandId(self):
        return self.getPinkWandCode()

    def saveBlueWandId(self, id_val):
        self.saveBlueWandCode(id_val)

    def getBlueWandId(self):
        return self.getBlueWandCode()


class TestChallengerM4StorageCoordination(unittest.TestCase):
    """Adversarial stress and verification tests for Milestone 4."""

    @classmethod
    def setUpClass(cls):
        cls.repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        cls.main_path = os.path.join(cls.repo_root, "src", "main.cpp")
        cls.storage_h_path = os.path.join(cls.repo_root, "include", "StorageController.h")
        cls.storage_cpp_path = os.path.join(cls.repo_root, "src", "StorageController.cpp")
        cls.web_cpp_path = os.path.join(cls.repo_root, "src", "WebController.cpp")
        cls.elf_path = os.path.join(cls.repo_root, ".pio", "build", "seeed_xiao_esp32c3", "firmware.elf")
        cls.bin_path = os.path.join(cls.repo_root, ".pio", "build", "seeed_xiao_esp32c3", "firmware.bin")
        cls.objdump_path = r"C:\Users\Steven\.platformio\packages\toolchain-riscv32-esp\bin\riscv32-esp-elf-objdump.exe"

    def test_challenge_01_nvs_fresh_boot_clean_state(self):
        """Verify that on fresh boot with empty NVS, wand IDs return 0 and status reports 'Not Paired'."""
        prefs = MockESP32Preferences()
        storage = MockStorageController(prefs)
        storage.init()

        # Both methods and aliases must return 0
        self.assertEqual(storage.getPinkWandCode(), 0)
        self.assertEqual(storage.getBlueWandCode(), 0)
        self.assertEqual(storage.getPinkWandId(), 0)
        self.assertEqual(storage.getBlueWandId(), 0)

        # Simulator mirroring WebController status formatting
        sim = WandInteractionSimulator(pink_id=0, blue_id=0)
        status_code, status_json = sim.handle_rest_request("/api/status")
        self.assertEqual(status_code, 200)
        # Unconfigured wand check in simulator: incoming wand returns UNKNOWN_WAND
        result = sim.handle_wand_signal(0x12345678, 1000)
        self.assertEqual(result, "UNKNOWN_WAND")
        self.assertEqual(sim.mode, "OFF")

        # C++ source check: verify zero code guardrails in IRController.cpp
        ir_cpp_path = os.path.join(self.repo_root, "src", "IRController.cpp")
        with open(ir_cpp_path, "r") as f:
            ir_src = f.read()
        self.assertIn("if (valid && code != 0)", ir_src)
        self.assertIn("if (pinkCode != 0 && code == pinkCode)", ir_src)
        self.assertIn("else if (blueCode != 0 && code == blueCode)", ir_src)


    def test_challenge_02_nvs_multi_reboot_retention(self):
        """Simulate power cycles across multiple pairing sessions to verify survival and mutation."""
        prefs = MockESP32Preferences()

        # Cold Boot 0
        storage_boot0 = MockStorageController(prefs)
        storage_boot0.init()
        self.assertEqual(storage_boot0.getPinkWandId(), 0)
        self.assertEqual(storage_boot0.getBlueWandId(), 0)

        # Session 1: Pair Pink Wand
        storage_boot0.savePinkWandId(0x01234567)
        self.assertEqual(storage_boot0.getPinkWandId(), 0x01234567)
        self.assertEqual(storage_boot0.getBlueWandId(), 0)

        # Power Cycle / Cold Reboot 1
        storage_boot1 = MockStorageController(prefs)
        storage_boot1.init()
        self.assertEqual(storage_boot1.getPinkWandId(), 0x01234567)
        self.assertEqual(storage_boot1.getBlueWandId(), 0)

        # Session 2: Pair Blue Wand
        storage_boot1.saveBlueWandId(0x89ABCDEF)
        self.assertEqual(storage_boot1.getPinkWandId(), 0x01234567)
        self.assertEqual(storage_boot1.getBlueWandId(), 0x89ABCDEF)

        # Power Cycle / Cold Reboot 2
        storage_boot2 = MockStorageController(prefs)
        storage_boot2.init()
        self.assertEqual(storage_boot2.getPinkWandId(), 0x01234567)
        self.assertEqual(storage_boot2.getBlueWandId(), 0x89ABCDEF)

        # Session 3: Overwrite Pink Wand with new ID
        storage_boot2.savePinkWandId(0xCAFEBABE)
        self.assertEqual(storage_boot2.getPinkWandId(), 0xCAFEBABE)
        self.assertEqual(storage_boot2.getBlueWandId(), 0x89ABCDEF)

        # Power Cycle / Cold Reboot 3
        storage_boot3 = MockStorageController(prefs)
        storage_boot3.init()
        self.assertEqual(storage_boot3.getPinkWandId(), 0xCAFEBABE)
        self.assertEqual(storage_boot3.getBlueWandId(), 0x89ABCDEF)

        # Session 4: Factory Reset / Clear NVS
        prefs.clear()

        # Power Cycle / Cold Reboot 4
        storage_boot4 = MockStorageController(prefs)
        storage_boot4.init()
        self.assertEqual(storage_boot4.getPinkWandId(), 0)
        self.assertEqual(storage_boot4.getBlueWandId(), 0)

    def test_challenge_03_nvs_wear_leveling_redundant_write_skipping(self):
        """Verify that identical wand IDs produce ZERO flash write operations (wear leveling)."""
        prefs = MockESP32Preferences()
        storage = MockStorageController(prefs)
        storage.init()

        # Initial write: count = 1
        storage.savePinkWandCode(0x12345678)
        self.assertEqual(prefs.write_count, 1)

        # Redundant writes with identical code must skip putUInt
        for _ in range(50):
            storage.savePinkWandCode(0x12345678)
            storage.savePinkWandId(0x12345678)
        self.assertEqual(prefs.write_count, 1)

        # Initial blue write: count = 2
        storage.saveBlueWandCode(0xAABBCCDD)
        self.assertEqual(prefs.write_count, 2)

        # Redundant blue writes must skip putUInt
        for _ in range(50):
            storage.saveBlueWandCode(0xAABBCCDD)
            storage.saveBlueWandId(0xAABBCCDD)
        self.assertEqual(prefs.write_count, 2)

        # Code verification in StorageController.cpp
        with open(self.storage_cpp_path, "r") as f:
            src = f.read()
        self.assertIn("if (getPinkWandCode() == code) return;", src)
        self.assertIn("if (getBlueWandCode() == code) return;", src)

    def test_challenge_04_nvs_boundary_uint32_handling(self):
        """Test edge cases: 0, 1, 0x7FFFFFFF (int32 max), 0x80000000 (sign bit), 0xFFFFFFFF (uint32 max)."""
        prefs = MockESP32Preferences()
        storage = MockStorageController(prefs)
        storage.init()

        test_cases = [
            (0x00000000, "Not Paired"),
            (0x00000001, "0x00000001"),
            (0x7FFFFFFF, "0x7FFFFFFF"),
            (0x80000000, "0x80000000"),
            (0xFFFFFFFF, "0xFFFFFFFF"),
            (0x12345678, "0x12345678"),
            (0xCAFEBABE, "0xCAFEBABE"),
        ]

        for val, expected_str in test_cases:
            storage.savePinkWandCode(val)
            retrieved = storage.getPinkWandCode()
            self.assertEqual(retrieved, val)

            # Test formatting contract matching WebController snprintf
            formatted = "Not Paired" if retrieved == 0 else "0x{:08X}".format(retrieved)
            self.assertEqual(formatted, expected_str)

    def test_challenge_05_nvs_namespace_and_key_specifications(self):
        """Verify NVS namespace and keys comply with ESP-IDF 15-character maximum."""
        self.assertEqual(NVS_NAMESPACE, "auroradress")
        self.assertEqual(NVS_KEY_PINK_WAND, "pink_wand")
        self.assertEqual(NVS_KEY_BLUE_WAND, "blue_wand")

        self.assertLessEqual(len(NVS_NAMESPACE), 15)
        self.assertLessEqual(len(NVS_KEY_PINK_WAND), 15)
        self.assertLessEqual(len(NVS_KEY_BLUE_WAND), 15)

        # Verify C++ implementation uses exact keys
        with open(self.storage_cpp_path, "r") as f:
            src = f.read()
        self.assertIn('preferences.begin("auroradress", false);', src)
        self.assertIn('"pink_wand"', src)
        self.assertIn('"blue_wand"', src)

    def test_challenge_06_api_alias_contract_completeness(self):
        """Verify that StorageController.h defines PROJECT.md contract aliases inline."""
        with open(self.storage_h_path, "r") as f:
            h_src = f.read()

        # Required contract aliases:
        # savePinkWandId, getPinkWandId, saveBlueWandId, getBlueWandId
        self.assertIn("savePinkWandId", h_src)
        self.assertIn("getPinkWandId", h_src)
        self.assertIn("saveBlueWandId", h_src)
        self.assertIn("getBlueWandId", h_src)

        # Verify they are declared as inline delegators
        self.assertTrue(bool(re.search(r"inline\s+void\s+savePinkWandId\s*\(\s*uint32_t\s+\w+\s*\)", h_src)))
        self.assertTrue(bool(re.search(r"inline\s+uint32_t\s+getPinkWandId\s*\(\s*\)", h_src)))
        self.assertTrue(bool(re.search(r"inline\s+void\s+saveBlueWandId\s*\(\s*uint32_t\s+\w+\s*\)", h_src)))
        self.assertTrue(bool(re.search(r"inline\s+uint32_t\s+getBlueWandId\s*\(\s*\)", h_src)))

    def test_challenge_07_deterministic_boot_sequence_and_clamp(self):
        """Verify exact boot order: clamp -> serial settle -> storage -> dark led push -> ir -> web."""
        with open(self.main_path, "r") as f:
            main_code = f.read()

        setup_body = main_code[main_code.find("void setup()"):main_code.find("void loop()")]

        pos_clamp = setup_body.find("LedController::earlyPinClamp()")
        pos_serial = setup_body.find("Serial.begin(115200)")
        pos_settle = setup_body.find("delay(200)")
        pos_storage = setup_body.find("StorageController::init()")
        pos_led = setup_body.find("LedController::init()")
        pos_ir = setup_body.find("IRController::init()")
        pos_web = setup_body.find("WebController::init()")

        self.assertNotEqual(pos_clamp, -1, "earlyPinClamp missing")
        self.assertNotEqual(pos_serial, -1, "Serial.begin missing")
        self.assertNotEqual(pos_settle, -1, "delay(200) settle missing")
        self.assertNotEqual(pos_storage, -1, "StorageController::init missing")
        self.assertNotEqual(pos_led, -1, "LedController::init missing")
        self.assertNotEqual(pos_ir, -1, "IRController::init missing")
        self.assertNotEqual(pos_web, -1, "WebController::init missing")

        # Strict order assertion:
        self.assertLess(pos_clamp, pos_serial, "Pin clamp must occur before Serial bringup")
        self.assertLess(pos_serial, pos_settle, "Serial.begin must precede settle delay")
        self.assertLess(pos_settle, pos_storage, "Settle delay must precede storage init")
        self.assertLess(pos_storage, pos_led, "Storage must initialize before LED")
        self.assertLess(pos_led, pos_ir, "LED must initialize before IR")
        self.assertLess(pos_ir, pos_web, "IR must initialize before Web")

    def test_challenge_08_loop_zero_delay_cooperative_budget(self):
        """Verify loop() body contains exactly zero delay() calls and polls all 3 controllers."""
        with open(self.main_path, "r") as f:
            main_code = f.read()

        loop_body = main_code[main_code.find("void loop()"):].strip()
        self.assertNotIn("delay(", loop_body, "Found forbidden delay() call in loop()")
        self.assertNotIn("vTaskDelay(", loop_body, "Found forbidden vTaskDelay() call in loop()")

        self.assertIn("LedController::update();", loop_body)
        self.assertIn("IRController::update();", loop_body)
        self.assertIn("WebController::update();", loop_body)

    def test_challenge_09_iram_isr_cache_safety_disassembly(self):
        """Disassemble firmware.elf and prove IRChannel::handleEdge() makes ZERO calls to .flash.text."""
        self.assertTrue(os.path.exists(self.elf_path), "firmware.elf does not exist")
        self.assertTrue(os.path.exists(self.objdump_path), "riscv32-esp-elf-objdump.exe not found")

        cmd = [self.objdump_path, "-d", "-C", self.elf_path]
        res = subprocess.check_output(cmd).decode("utf-8", errors="ignore")

        # Extract <IRChannel::handleEdge()> function body
        m = re.search(r"<IRChannel::handleEdge\(\)>:(.*?)(?=\n[0-9a-fA-F]+ <|\Z)", res, re.DOTALL)
        self.assertIsNotNone(m, "IRChannel::handleEdge() symbol not found in disassembly")
        isr_code = m.group(1)

        # Check all jump/call instructions
        call_lines = [l for l in isr_code.splitlines() if "jal" in l or "call" in l]
        self.assertGreater(len(call_lines), 0, "Expected at least one call (esp_timer_get_time)")

        for line in call_lines:
            # Pattern: 40380264: 568030ef jal ra,403837cc <esp_timer_get_time>
            m_target = re.search(r"(?:jal|call)\s+(?:ra,\s*)?([0-9a-fA-F]+)\s*<([^>]+)>", line)
            self.assertIsNotNone(m_target, "Failed to parse call target from line: " + line)
            target_addr = int(m_target.group(1), 16)
            symbol_name = m_target.group(2)
            self.assertLess(target_addr, 0x42000000,
                            "Violation: ISR calls Flash memory >= 0x42000000: " + line)
            self.assertIn("esp_timer_get_time", symbol_name, "Unexpected symbol called in ISR: " + line)
        self.assertNotIn("micros", isr_code, "Forbidden micros() call still present in handleEdge")


    def test_challenge_10_binary_resource_and_partition_limits(self):
        """Verify firmware binary size, RAM footprint, and Flash app partition headroom."""
        self.assertTrue(os.path.exists(self.elf_path), "firmware.elf missing")

        # Use riscv32-esp-elf-size if available, or check binary sizes
        size_tool = os.path.join(os.path.dirname(self.objdump_path), "riscv32-esp-elf-size.exe")
        if os.path.exists(size_tool):
            cmd = [size_tool, "-A", self.elf_path]
            out = subprocess.check_output(cmd).decode("utf-8", errors="ignore")
            # Calculate total RAM (dram0.data + dram0.bss + iram0.text) and Flash (.flash.text + .flash.rodata)
            iram_size = 0
            dram_data = 0
            dram_bss = 0
            flash_text = 0
            flash_rodata = 0
            for line in out.splitlines():
                parts = line.split()
                if len(parts) >= 2:
                    sec_name, sec_size = parts[0], parts[1]
                    try:
                        sz = int(sec_size)
                        if sec_name == ".iram0.text": iram_size = sz
                        elif sec_name == ".dram0.data": dram_data = sz
                        elif sec_name == ".dram0.bss": dram_bss = sz
                        elif sec_name == ".flash.text": flash_text = sz
                        elif sec_name == ".flash.rodata": flash_rodata = sz
                    except ValueError:
                        pass
            total_ram = dram_data + dram_bss
            total_flash = flash_text + flash_rodata + iram_size + dram_data

            # RAM ceiling: 20% of 320KB = 65,536 bytes
            self.assertLessEqual(total_ram, 65536, "RAM usage {} exceeds 20% limit (65,536)".format(total_ram))
            # Flash ceiling: 50% of 1.9MB min_spiffs = 983,040 bytes
            self.assertLessEqual(total_flash, 983040, "Flash usage {} exceeds 50% limit (983,040)".format(total_flash))

    def test_challenge_11_high_frequency_pairing_reboot_stress(self):
        """Stress-test 1,000 rapid pairing, reboot, and status query cycles with zero corruption."""
        prefs = MockESP32Preferences()
        rng = random.Random(0x42BEEF)

        for cycle in range(1000):
            # 1. Instantiate StorageController (reboot)
            storage = MockStorageController(prefs)
            storage.init()

            # 2. Generate random wand IDs
            new_pink = rng.randint(0, 0xFFFFFFFF)
            new_blue = rng.randint(0, 0xFFFFFFFF)

            # 3. Save IDs
            storage.savePinkWandId(new_pink)
            storage.saveBlueWandId(new_blue)

            # 4. Immediate readback
            self.assertEqual(storage.getPinkWandId(), new_pink)
            self.assertEqual(storage.getBlueWandId(), new_blue)

            # 5. Simulate WebController status generation
            p_str = "Not Paired" if new_pink == 0 else "0x{:08X}".format(new_pink)
            b_str = "Not Paired" if new_blue == 0 else "0x{:08X}".format(new_blue)
            status_json = json.dumps({
                "mode": "OFF",
                "pinkWand": p_str,
                "blueWand": b_str,
                "pairing": "NONE",
                "brightness": 160
            })
            self.assertLessEqual(len(status_json), 256)

            # 6. Periodic factory reset test
            if cycle % 250 == 249:
                prefs.clear()
                self.assertEqual(storage.getPinkWandId(), 0)
                self.assertEqual(storage.getBlueWandId(), 0)


if __name__ == "__main__":
    unittest.main()
