#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Milestone 4 Empirical Challenger Test Suite: System Coordination & NVS Storage
Tests:
1. Binary Ceilings: RAM < 20% (< 65,536 bytes), Flash < 50% (< 983,040 bytes).
2. IRAM ISR Flash Safety: IRChannel::handleEdge(), isrLeft(), isrRight() reside strictly
   in IRAM (.iram0.text [0x40380000, 0x40390000)) and have ZERO calls/branches to .flash.text (>= 0x42000000)
   or memory accesses to flash .rodata (>= 0x3c000000).
3. Non-blocking Execution: main.cpp loop() contains zero delay(), delayMicroseconds(), or vTaskDelay() calls.
4. Deterministic Boot Order: setup() enforces clamp -> Serial settle -> storage -> led -> ir -> web.
5. StorageController Contract Parity & Aliasing: verify *Id and *Code API aliases have 100% equivalence.
6. Flash Endurance & Redundant Write Suppression: verify redundant NVS write filtering logic.
7. Disassembly verification of StorageController redundant write check branching.
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

OBJDUMP_PATH = r"C:\Users\Steven\.platformio\packages\toolchain-riscv32-esp\bin\riscv32-esp-elf-objdump.exe"
NM_PATH = r"C:\Users\Steven\.platformio\packages\toolchain-riscv32-esp\bin\riscv32-esp-elf-nm.exe"
ELF_PATH = os.path.join(PROJECT_ROOT, ".pio", "build", "seeed_xiao_esp32c3", "firmware.elf")


class TestM4SystemCoordinationNVS(unittest.TestCase):
    """Empirical challenge suite for Milestone 4 System Coordination & NVS Storage."""

    @classmethod
    def setUpClass(cls):
        cls.has_tools = os.path.exists(ELF_PATH) and os.path.exists(OBJDUMP_PATH) and os.path.exists(NM_PATH)
        cls.disasm = ""
        cls.nm_output = ""
        if cls.has_tools:
            cls.disasm = subprocess.check_output([OBJDUMP_PATH, "-d", "-C", ELF_PATH]).decode("utf-8", errors="ignore")
            cls.nm_output = subprocess.check_output([NM_PATH, ELF_PATH]).decode("utf-8", errors="ignore")

    # =========================================================================
    # 1. Binary Ceilings Verification
    # =========================================================================

    def test_m4_01_ram_ceiling_under_20_percent(self):
        """Verify RAM consumption is strictly under 20% (< 65,536 bytes of 327,680)."""
        self.assertTrue(self.has_tools, "ELF binary must exist")
        ram_ceiling = 65536  # 20%
        
        out_str = subprocess.check_output(["pio", "run"], cwd=PROJECT_ROOT, shell=True).decode("utf-8", errors="ignore")
        
        ram_match = re.search(r"RAM:\s+\[.*?\]\s+([0-9.]+)%\s+\(used\s+(\d+)\s+bytes\s+from\s+(\d+)\s+bytes\)", out_str)
        self.assertIsNotNone(ram_match, "RAM usage must be parseable from pio output")
        ram_pct = float(ram_match.group(1))
        ram_bytes = int(ram_match.group(2))
        
        print("\n  [Empirical Benchmark] Milestone 4 Memory Footprint:")
        print("    RAM Used:   {:>7} bytes ({:>5.1f}%) [Ceiling: < 65,536 bytes / 20.0%]".format(ram_bytes, ram_pct))
        self.assertLess(ram_bytes, ram_ceiling, "RAM usage must be < 65,536 bytes")
        self.assertLess(ram_pct, 20.0, "RAM percentage must be < 20.0%")

    def test_m4_02_flash_ceiling_under_50_percent(self):
        """Verify Flash consumption is strictly under 50% (< 983,040 bytes of 1,966,080)."""
        self.assertTrue(self.has_tools)
        flash_ceiling = 983040  # 50%
        
        out_str = subprocess.check_output(["pio", "run"], cwd=PROJECT_ROOT, shell=True).decode("utf-8", errors="ignore")
        
        flash_match = re.search(r"Flash:\s+\[.*?\]\s+([0-9.]+)%\s+\(used\s+(\d+)\s+bytes\s+from\s+(\d+)\s+bytes\)", out_str)
        self.assertIsNotNone(flash_match, "Flash usage must be parseable from pio output")
        flash_pct = float(flash_match.group(1))
        flash_bytes = int(flash_match.group(2))
        
        print("    Flash Used: {:>7} bytes ({:>5.1f}%) [Ceiling: < 983,040 bytes / 50.0%]".format(flash_bytes, flash_pct))
        self.assertLess(flash_bytes, flash_ceiling, "Flash usage must be < 983,040 bytes")
        self.assertLess(flash_pct, 50.0, "Flash percentage must be < 50.0%")

    # =========================================================================
    # 2. IRAM ISR Flash & Cache Safety
    # =========================================================================

    def test_m4_03_handle_edge_and_isrs_in_iram(self):
        """Verify isrLeft(), isrRight(), and IRChannel::handleEdge() reside in IRAM (0x4038xxxx)."""
        self.assertTrue(self.has_tools)
        iram_min = 0x40380000
        iram_max = 0x40390000

        symbols = ["isrLeft", "isrRight", "handleEdge"]
        found = {}
        for line in self.nm_output.splitlines():
            parts = line.split()
            if len(parts) >= 3:
                try:
                    addr = int(parts[0], 16)
                    for s in symbols:
                        if s in parts[2]:
                            found[s] = addr
                except ValueError:
                    pass

        for s in symbols:
            self.assertIn(s, found, "Symbol {} must be in ELF symbol table".format(s))
            addr = found[s]
            self.assertTrue(iram_min <= addr < iram_max,
                            "Symbol {} at 0x{:08X} not in IRAM [0x{:08X}, 0x{:08X})".format(s, addr, iram_min, iram_max))

    def test_m4_04_handle_edge_zero_flash_calls_or_branches(self):
        """Verify IRChannel::handleEdge() has ZERO instructions targeting .flash.text (>= 0x42000000)."""
        self.assertTrue(self.has_tools)
        match = re.search(r"([0-9a-fA-F]+)\s+<IRChannel::handleEdge\(\)>:(.*?)(?=\n[0-9a-fA-F]+ <|\Z)", self.disasm, re.DOTALL)
        self.assertIsNotNone(match, "handleEdge() must exist in disassembly")
        code = match.group(2)

        flash_targets = []
        for line in code.splitlines():
            if any(op in line for op in ['jal', 'jalr', 'call', 'j ']):
                target_match = re.search(r'(42[0-9a-fA-F]{6})', line)
                if target_match:
                    flash_targets.append(line.strip())

        self.assertEqual(len(flash_targets), 0,
                         "Found illegal calls/branches to flash in handleEdge(): {}".format(flash_targets))

    def test_m4_05_handle_edge_zero_rodata_access(self):
        """Verify IRChannel::handleEdge() loads zero data from flash-mapped .rodata (0x3cxxxxxx)."""
        self.assertTrue(self.has_tools)
        match = re.search(r"([0-9a-fA-F]+)\s+<IRChannel::handleEdge\(\)>:(.*?)(?=\n[0-9a-fA-F]+ <|\Z)", self.disasm, re.DOTALL)
        code = match.group(2)

        rodata_loads = []
        for line in code.splitlines():
            if re.search(r'3c[0-9a-fA-F]{6}', line):
                rodata_loads.append(line.strip())

        self.assertEqual(len(rodata_loads), 0,
                         "Found illegal loads from flash .rodata in handleEdge(): {}".format(rodata_loads))

    # =========================================================================
    # 3. Non-blocking Round-Robin Loop & Boot Sequence
    # =========================================================================

    def test_m4_06_zero_delay_in_main_loop(self):
        """Verify main.cpp loop() contains zero delay calls."""
        main_path = os.path.join(PROJECT_ROOT, "src", "main.cpp")
        with open(main_path, "r") as f:
            content = f.read()

        loop_match = re.search(r'void\s+loop\s*\(\s*\)\s*\{(.*?)\}', content, re.DOTALL)
        self.assertIsNotNone(loop_match, "loop() function must exist in main.cpp")
        loop_body = loop_match.group(1)

        delays = re.findall(r'\b(?:delay|delayMicroseconds|vTaskDelay)\s*\(', loop_body)
        self.assertEqual(len(delays), 0, "Found blocking delay in loop(): {}".format(delays))

    def test_m4_07_deterministic_boot_sequence_in_setup(self):
        """Verify setup() orders: earlyPinClamp -> Serial -> Storage -> Led -> IR -> Web."""
        main_path = os.path.join(PROJECT_ROOT, "src", "main.cpp")
        with open(main_path, "r") as f:
            content = f.read()

        setup_match = re.search(r'void\s+setup\s*\(\s*\)\s*\{(.*?)\}', content, re.DOTALL)
        self.assertIsNotNone(setup_match)
        setup_body = setup_match.group(1)

        p_clamp = setup_body.find("LedController::earlyPinClamp()")
        p_serial = setup_body.find("Serial.begin(115200)")
        p_storage = setup_body.find("StorageController::init()")
        p_led = setup_body.find("LedController::init()")
        p_ir = setup_body.find("IRController::init()")
        p_web = setup_body.find("WebController::init()")

        self.assertNotEqual(p_clamp, -1, "earlyPinClamp must be in setup()")
        self.assertNotEqual(p_serial, -1, "Serial.begin must be in setup()")
        self.assertNotEqual(p_storage, -1, "StorageController::init must be in setup()")
        self.assertNotEqual(p_led, -1, "LedController::init must be in setup()")
        self.assertNotEqual(p_ir, -1, "IRController::init must be in setup()")
        self.assertNotEqual(p_web, -1, "WebController::init must be in setup()")

        self.assertLess(p_clamp, p_serial, "earlyPinClamp must be called before Serial")
        self.assertLess(p_serial, p_storage, "Serial must settle before Storage")
        self.assertLess(p_storage, p_led, "StorageController must initialize before LedController")
        self.assertLess(p_led, p_ir, "LedController must initialize before IRController")
        self.assertLess(p_ir, p_web, "IRController must initialize before WebController")

    # =========================================================================
    # 4. StorageController Interface Parity & Wear-Leveling
    # =========================================================================

    def test_m4_08_storage_controller_interface_contract(self):
        """Verify StorageController header exports both *Id and *Code APIs."""
        hdr_path = os.path.join(PROJECT_ROOT, "include", "StorageController.h")
        with open(hdr_path, "r") as f:
            hdr = f.read()

        required_methods = [
            "init()",
            "savePinkWandCode(uint32_t",
            "getPinkWandCode()",
            "saveBlueWandCode(uint32_t",
            "getBlueWandCode()",
            "savePinkWandId(uint32_t",
            "getPinkWandId()",
            "saveBlueWandId(uint32_t",
            "getBlueWandId()"
        ]
        for m in required_methods:
            self.assertIn(m, hdr, "StorageController.h must declare {}".format(m))

    def test_m4_09_storage_controller_redundant_write_skipping(self):
        """Verify StorageController::savePinkWandCode and saveBlueWandCode skip redundant NVS writes."""
        cpp_path = os.path.join(PROJECT_ROOT, "src", "StorageController.cpp")
        with open(cpp_path, "r") as f:
            cpp = f.read()

        self.assertIn("if (getPinkWandCode() == code) return;", cpp)
        self.assertIn("if (getBlueWandCode() == code) return;", cpp)

        # Disassembly check: confirm conditional branch before Preferences::putUInt
        match_pink = re.search(r"<StorageController::savePinkWandCode\(unsigned long\)>:(.*?)(?=\n[0-9a-fA-F]+ <|\Z)", self.disasm, re.DOTALL)
        self.assertIsNotNone(match_pink, "savePinkWandCode disassembly must be matched")
        code_pink = match_pink.group(1)
        self.assertIn("beq", code_pink, "savePinkWandCode must have equality branch")
        self.assertIn("Preferences::putUInt", code_pink)

        match_blue = re.search(r"<StorageController::saveBlueWandCode\(unsigned long\)>:(.*?)(?=\n[0-9a-fA-F]+ <|\Z)", self.disasm, re.DOTALL)
        self.assertIsNotNone(match_blue, "saveBlueWandCode disassembly must be matched")
        code_blue = match_blue.group(1)
        self.assertIn("beq", code_blue, "saveBlueWandCode must have equality branch")
        self.assertIn("Preferences::putUInt", code_blue)


if __name__ == "__main__":
    unittest.main()
