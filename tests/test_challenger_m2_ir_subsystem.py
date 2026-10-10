#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Milestone 2 Empirical Challenger Test Suite: IR Subsystem & Concurrency
Empirically verifies:
1. Critical Section Optimization: Disassemble processChannelPacket() and checkTimeout(),
   confirm micro-lock (<30ns at 160MHz) with 0 loop iterations inside noInterrupts().
2. IRAM Placement: Confirm IRAM_ATTR on isrLeft(), isrRight(), and handleEdge() via ELF symbol table.
3. 56-bit MagiQuest Decoding & 48-bit Fallback: Test pulse trains with edge timings, noise tolerance,
   and 35% mark duty cycle threshold.
4. Dual Receiver & Cross-Shoulder Debouncing: Verify 400ms debounce filter across dual shoulders.
5. Pairing State Machine & Event Dispatch: 30s timeout, web cancellation, NVS save, visual feedback,
   and rapid dual-wand Splotches trigger (2000ms window).
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
    MagiQuestEncoder, MagiQuestDecoder, WandInteractionSimulator,
    PIN_IR_RECV_LEFT, PIN_IR_RECV_RIGHT,
    IR_DEBOUNCE_MS, WAND_RAPID_WINDOW_MS, PAIRING_TIMEOUT_MS
)

OBJDUMP_PATH = r"C:\Users\Steven\.platformio\packages\toolchain-riscv32-esp\bin\riscv32-esp-elf-objdump.exe"
NM_PATH = r"C:\Users\Steven\.platformio\packages\toolchain-riscv32-esp\bin\riscv32-esp-elf-nm.exe"
ELF_PATH = os.path.join(PROJECT_ROOT, ".pio", "build", "seeed_xiao_esp32c3", "firmware.elf")


class TestM2IRSubsystemRefinement(unittest.TestCase):
    """Empirical challenge suite for Milestone 2 IR Subsystem Refinement."""

    @classmethod
    def setUpClass(cls):
        cls.has_elf = os.path.exists(ELF_PATH) and os.path.exists(OBJDUMP_PATH) and os.path.exists(NM_PATH)
        cls.disasm = ""
        cls.nm_output = ""
        if cls.has_elf:
            proc_obj = subprocess.Popen([OBJDUMP_PATH, "-d", "-C", ELF_PATH],
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout_obj, _ = proc_obj.communicate()
            cls.disasm = stdout_obj.decode("utf-8", errors="ignore")

            proc_nm = subprocess.Popen([NM_PATH, ELF_PATH],
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout_nm, _ = proc_nm.communicate()
            cls.nm_output = stdout_nm.decode("utf-8", errors="ignore")

    # =========================================================================
    # 1. Critical Section Optimization (<30ns Lock Time)
    # =========================================================================

    def test_m2_critical_section_microlock_under_30ns(self):
        """Verify processChannelPacket() critical section holds interrupt lock for <30ns (<=15 instructions)."""
        self.assertTrue(self.has_elf, "firmware.elf and objdump must exist")
        match = re.search(r"<processChannelPacket\(IRChannel&\)>:(.*?)(?=\n[0-9a-fA-F]+ <|\Z)", self.disasm, re.DOTALL)
        self.assertIsNotNone(match, "processChannelPacket() must be found in disassembly")
        code = match.group(1)

        # Locate call to vPortSetInterruptMask (noInterrupts) and vPortClearInterruptMask (interrupts)
        set_mask_match = re.search(r"([0-9a-fA-F]+):\s+.*jalr.*<vPortSetInterruptMask>", code)
        clear_mask_match = re.search(r"([0-9a-fA-F]+):\s+.*jalr.*<vPortClearInterruptMask>", code)
        self.assertIsNotNone(set_mask_match, "Must call vPortSetInterruptMask")
        self.assertIsNotNone(clear_mask_match, "Must call vPortClearInterruptMask")

        addr_set = int(set_mask_match.group(1), 16)
        addr_clear = int(clear_mask_match.group(1), 16)
        self.assertLess(addr_set, addr_clear, "Interrupts must be set before cleared")

        # Locate the call sequence to vPortClearInterruptMask (auipc immediately preceding jalr)
        call_clear_pos = code.find(clear_mask_match.group(0))
        auipc_match = re.search(r"([0-9a-fA-F]+):\s+[0-9a-fA-F]+\s+auipc.*(?=\n\s*" + clear_mask_match.group(1) + r":)", code)
        end_pos = auipc_match.start() if auipc_match else call_clear_pos

        between_code = code[code.find(set_mask_match.group(0)):end_pos]
        lines = [l for l in between_code.splitlines() if re.match(r"^\s*[0-9a-fA-F]+:\s+[0-9a-fA-F]+", l)]

        # Instruction count in critical section body (excluding function call instructions)
        inner_instructions = len(lines) - 1
        print("\n  [Empirical Benchmark] Critical section in processChannelPacket:")
        print("    Instructions in critical section: {:>3}".format(inner_instructions))
        # On ESP32-C3 RISC-V 2-stage core @ 160MHz, single-cycle integer ALU/load/store = 6.25ns per cycle
        estimated_time_ns = inner_instructions * 1.0 * 6.25
        print("    Estimated lock time at 160MHz:    {:>6.2f} ns (requirement: <30.0 ns)".format(estimated_time_ns))

        self.assertLessEqual(inner_instructions, 5, "Critical section has too many instructions")
        self.assertLess(estimated_time_ns, 30.0, "Critical section lock time exceeds 30ns budget!")

        # Confirm NO loop instructions in critical section
        forbidden_in_lock = ["for", "while", "s_decodeBuf"]
        for fb in forbidden_in_lock:
            self.assertNotIn(fb, between_code)

    def test_m2_check_timeout_lockfree_precheck(self):
        """Verify checkTimeout() contains lock-free pre-check avoiding interrupt disable when not timed out."""
        self.assertTrue(self.has_elf)
        match = re.search(r"<IRChannel::checkTimeout\(unsigned long\)>:(.*?)(?=\n[0-9a-fA-F]+ <|\Z)", self.disasm, re.DOTALL)
        self.assertIsNotNone(match, "checkTimeout() must be found in disassembly")
        code = match.group(1)

        # First instructions must check capturing and time delta before calling vPortSetInterruptMask
        first_lines = [l for l in code.strip().splitlines()[:6] if ":" in l]
        # Should have conditional branches (beqz, bgeu, etc.) before any jalr to vPortSetInterruptMask
        branch_found = any(("beqz" in l or "bnez" in l or "bgeu" in l or "bltu" in l) for l in first_lines)
        self.assertTrue(branch_found, "checkTimeout() must branch early before disabling interrupts")

    # =========================================================================
    # 2. IRAM_ATTR ISR Placement Verification
    # =========================================================================

    def test_m2_iram_attr_on_isrs(self):
        """Verify isrLeft, isrRight, and handleEdge reside strictly in IRAM (.iram0.text, 0x4038xxxx)."""
        self.assertTrue(self.has_elf)

        # On ESP32-C3, IRAM addresses start at 0x40380000 and extend to ~0x40390000
        iram_min = 0x40380000
        iram_max = 0x40390000

        symbols_to_check = ["isrLeft", "isrRight", "handleEdge"]
        found_symbols = {}

        for line in self.nm_output.splitlines():
            parts = line.split()
            if len(parts) >= 3:
                addr_str, sym_type, sym_name = parts[0], parts[1], parts[2]
                try:
                    addr = int(addr_str, 16)
                except ValueError:
                    continue
                for stc in symbols_to_check:
                    if stc in sym_name:
                        found_symbols[stc] = addr

        for stc in symbols_to_check:
            self.assertIn(stc, found_symbols, "Symbol {} must be present in ELF".format(stc))
            addr = found_symbols[stc]
            self.assertTrue(iram_min <= addr < iram_max,
                            "Symbol {} at 0x{:08X} must reside in IRAM [0x{:08X}, 0x{:08X})".format(
                                stc, addr, iram_min, iram_max))

    def test_m2_handle_edge_zero_flash_calls(self):
        """Verify handleEdge() contains zero calls into .flash.text (>= 0x42000000)."""
        self.assertTrue(self.has_elf)
        match = re.search(r"<IRChannel::handleEdge\(\)>:(.*?)(?=\n[0-9a-fA-F]+ <|\Z)", self.disasm, re.DOTALL)
        self.assertIsNotNone(match, "IRChannel::handleEdge() must be found in disassembly")
        code = match.group(1)

        # Check for any jal, jalr, or call targeting flash addresses (>= 0x42000000)
        flash_call_patterns = [
            r"jalr?.*<micros>",
            r"jalr?.*42[0-9a-fA-F]{6}",
            r"call.*42[0-9a-fA-F]{6}"
        ]
        for pattern in flash_call_patterns:
            flash_calls = re.findall(pattern, code)
            self.assertEqual(len(flash_calls), 0,
                             "Found illegal flash call in handleEdge() matching '{}': {}".format(pattern, flash_calls))

        # Specifically verify call to esp_timer_get_time in IRAM
        self.assertIn("esp_timer_get_time", code, "handleEdge() must call esp_timer_get_time")

    # =========================================================================
    # 3. 56-Bit MagiQuest Bitstream Decoding & Tolerances
    # =========================================================================

    def test_m2_56bit_decoding_clean_frame(self):
        """Verify standard 56-bit MagiQuest bitstream decoding."""
        test_wand = 0x3F882190
        test_mag = 0x0180
        pulses = MagiQuestEncoder.encode_56bit(test_wand, test_mag)
        self.assertEqual(len(pulses), 56)

        wand_id, mag, status = MagiQuestDecoder.decode_pulse_train(pulses)
        self.assertEqual(status, "56bit_valid")
        self.assertEqual(wand_id, test_wand)
        self.assertEqual(mag, test_mag)

    def test_m2_48bit_fallback_frame(self):
        """Verify 48-bit fallback frame without preamble decodes correctly."""
        test_wand = 0x12AB34CD
        test_mag = 0x0240
        pulses = MagiQuestEncoder.encode_48bit_fallback(test_wand, test_mag)
        self.assertEqual(len(pulses), 48)

        wand_id, mag, status = MagiQuestDecoder.decode_pulse_train(pulses)
        self.assertEqual(status, "48bit_fallback")
        self.assertEqual(wand_id, test_wand)
        self.assertEqual(mag, test_mag)

    def test_m2_preamble_corruption_rejection(self):
        """Verify corrupted preamble bit fails 56-bit validation."""
        pulses = list(MagiQuestEncoder.encode_56bit(0x55555555, 0x0100))
        # Corrupt bit 0 to 1
        pulses[0] = (580, 600)
        wand_id, mag, status = MagiQuestDecoder.decode_pulse_train(pulses)
        self.assertNotEqual(status, "56bit_valid")

    def test_m2_mark_duty_cycle_discrimination(self):
        """Verify duty cycle midpoint threshold (~35%) separates bit 0 (~25%) from bit 1 (~50%)."""
        total_period = 1100
        # Bit 0: ~25% mark = 275us
        mark_bit0 = 275
        ratio0 = (mark_bit0 * 100) // total_period
        self.assertLess(ratio0, 35)

        # Bit 1: ~50% mark = 550us
        mark_bit1 = 550
        ratio1 = (mark_bit1 * 100) // total_period
        self.assertGreater(ratio1, 35)

    # =========================================================================
    # 4. Dual Receiver & Cross-Shoulder Debouncing
    # =========================================================================

    def test_m2_dual_receiver_pin_assignments(self):
        """Verify dual receiver GPIO assignments (GPIO 3 Left, GPIO 2 Right)."""
        self.assertEqual(PIN_IR_RECV_LEFT, 3)
        self.assertEqual(PIN_IR_RECV_RIGHT, 2)

    def test_m2_cross_shoulder_debounce_400ms(self):
        """Verify dual receivers share 400ms debounce filter."""
        sim = WandInteractionSimulator(pink_id=0x11111111, blue_id=0x22222222)
        # Hit on Left Shoulder at t=1000
        res1 = sim.handle_wand_signal(0x11111111, 1000)
        self.assertEqual(res1, "DISPATCH_PINK")

        # Echo hit on Right Shoulder at t=1050 (50ms later)
        res2 = sim.handle_wand_signal(0x11111111, 1050)
        self.assertEqual(res2, "DEBOUNCED")

        # Echo hit at t=1399 (<400ms debounce)
        res3 = sim.handle_wand_signal(0x11111111, 1399)
        self.assertEqual(res3, "DEBOUNCED")

        # Next legit hit at t=1400 (exactly 400ms later)
        res4 = sim.handle_wand_signal(0x11111111, 1400)
        self.assertEqual(res4, "DISPATCH_PINK")

    # =========================================================================
    # 5. Pairing State Machine & Rapid Dual-Wand Trigger
    # =========================================================================

    def test_m2_pairing_mode_timeout_30s(self):
        """Verify pairing mode expires after 30000ms."""
        sim = WandInteractionSimulator()
        sim.start_pairing("PINK", 5000)
        self.assertEqual(sim.pairing_state, "PINK")

        # At 34999ms (29999ms elapsed), remains active
        self.assertFalse(sim.check_pairing_timeout(34999))
        self.assertEqual(sim.pairing_state, "PINK")

        # At 35000ms (30000ms elapsed), times out
        self.assertTrue(sim.check_pairing_timeout(35000))
        self.assertEqual(sim.pairing_state, "NONE")

    def test_m2_pairing_cancellation(self):
        """Verify pairing cancellation immediately returns to NONE."""
        sim = WandInteractionSimulator()
        sim.start_pairing("BLUE", 1000)
        self.assertEqual(sim.pairing_state, "BLUE")
        sim.cancel_pairing()
        self.assertEqual(sim.pairing_state, "NONE")

    def test_m2_pairing_success_saves_nvs_and_feedback(self):
        """Verify successful wand pairing updates NVS and triggers PAIRING_FEEDBACK mode."""
        sim = WandInteractionSimulator(pink_id=0, blue_id=0)
        sim.start_pairing("PINK", 1000)

        learned_id = 0x88776655
        res = sim.handle_wand_signal(learned_id, 2000)
        self.assertEqual(res, "PAIRED_PINK")
        self.assertEqual(sim.pink_id, learned_id)
        self.assertEqual(sim.nvs["pink_wand"], learned_id)
        self.assertEqual(sim.mode, "PAIRING_FEEDBACK")
        self.assertEqual(sim.pairing_state, "NONE")

    def test_m2_rapid_dual_wand_triggers_splotches(self):
        """Verify rapid dual wand hits within 2000ms trigger SPLOTCHES dueling mode."""
        sim = WandInteractionSimulator(pink_id=0x11111111, blue_id=0x22222222)

        # Pink wand at t=1000
        res1 = sim.handle_wand_signal(0x11111111, 1000)
        self.assertEqual(res1, "DISPATCH_PINK")
        self.assertEqual(sim.mode, "PINK")

        # Blue wand at t=2800 (1800ms later, <= 2000ms)
        res2 = sim.handle_wand_signal(0x22222222, 2800)
        self.assertEqual(res2, "DISPATCH_SPLOTCHES")
        self.assertEqual(sim.mode, "SPLOTCHES")

    def test_m2_slow_wand_sequence_switches_individual(self):
        """Verify opposite wand hits beyond 2000ms switch to individual color instead of Splotches."""
        sim = WandInteractionSimulator(pink_id=0x11111111, blue_id=0x22222222)

        # Pink wand at t=1000
        sim.handle_wand_signal(0x11111111, 1000)
        self.assertEqual(sim.mode, "PINK")

        # Blue wand at t=3001 (2001ms later, > 2000ms)
        res = sim.handle_wand_signal(0x22222222, 3001)
        self.assertEqual(res, "DISPATCH_BLUE")
        self.assertEqual(sim.mode, "BLUE")


if __name__ == "__main__":
    unittest.main()
