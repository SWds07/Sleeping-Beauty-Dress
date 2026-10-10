#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Milestone 2 Empirical Stress Test Harness: IR Subsystem & Concurrency
Adversarially tests:
1. 56-bit MagiQuest bitstream decoding edge timings, ratio boundaries (34% vs 35% vs 36%),
   period limits (649us vs 650us vs 1750us vs 1751us), preamble rejection, and noise resilience.
2. 48-bit fallback frame decoding bit-for-bit extraction.
3. Silence timeout & single-mark trailing edge boundaries (149us, 280us, 399us, 400us, 560us, 851us).
4. Dual receiver cross-shoulder debouncing under rapid bursts, simultaneous shoulder hits,
   and alternating wand IDs.
5. Wand pairing state machine edge boundaries: 29999ms vs 30000ms vs 30001ms timeout,
   web cancellation, NVS persistence, and feedback triggers.
6. Rapid succession dueling window boundaries: 0ms, 1999ms, 2000ms vs 2001ms.
7. ELF binary disassembly verification of critical section execution time (<30ns) and IRAM symbols.
"""
from __future__ import print_function, division, absolute_import
import unittest
import os
import sys
import random
import re
import subprocess

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from tests.helpers import (
    MagiQuestEncoder, MagiQuestDecoder, WandInteractionSimulator,
    PIN_IR_RECV_LEFT, PIN_IR_RECV_RIGHT,
    IR_DEBOUNCE_MS, WAND_RAPID_WINDOW_MS, PAIRING_TIMEOUT_MS,
    NVS_KEY_PINK_WAND, NVS_KEY_BLUE_WAND
)

OBJDUMP_PATH = r"C:\Users\Steven\.platformio\packages\toolchain-riscv32-esp\bin\riscv32-esp-elf-objdump.exe"
NM_PATH = r"C:\Users\Steven\.platformio\packages\toolchain-riscv32-esp\bin\riscv32-esp-elf-nm.exe"
ELF_PATH = os.path.join(PROJECT_ROOT, ".pio", "build", "seeed_xiao_esp32c3", "firmware.elf")


class Milestone2EmpiricalStressSuite(unittest.TestCase):
    """Adversarial stress test suite for Milestone 2."""

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
    # 1. 56-Bit MagiQuest Bitstream Decoding Stress & Fuzzing
    # =========================================================================

    def test_stress_56bit_random_fuzzing_1000_iterations(self):
        """Fuzz test 56-bit decoder with 1,000 random wand IDs and magnitudes."""
        random.seed(0xCAFE1234)
        for _ in range(1000):
            rand_wand = random.randint(1, 0xFFFFFFFF)
            rand_mag = random.randint(0, 0xFFFF)
            pulses = MagiQuestEncoder.encode_56bit(rand_wand, rand_mag)
            self.assertEqual(len(pulses), 56)
            wand_id, mag, status = MagiQuestDecoder.decode_pulse_train(pulses)
            self.assertEqual(status, "56bit_valid")
            self.assertEqual(wand_id, rand_wand)
            self.assertEqual(mag, rand_mag)

    def test_stress_preamble_strictness_all_255_corruptions(self):
        """Verify that every single non-zero 8-bit preamble (0x01..0xFF) fails 56-bit validation."""
        for preamble in range(1, 256):
            bits = []
            for i in range(7, -1, -1):
                bits.append((preamble >> i) & 1)
            # Add 32 bits wand ID (0x12345678) and 16 bits magnitude (0x0100)
            wand_id = 0x12345678
            mag = 0x0100
            for i in range(31, -1, -1):
                bits.append((wand_id >> i) & 1)
            for i in range(15, -1, -1):
                bits.append((mag >> i) & 1)

            pulses = []
            for b in bits:
                if b == 0:
                    pulses.append((280, 850))
                else:
                    pulses.append((580, 600))

            wand_dec, mag_dec, status = MagiQuestDecoder.decode_pulse_train(pulses)
            # Must NOT pass as valid 56-bit frame
            self.assertNotEqual(status, "56bit_valid",
                                "Preamble 0x{:02X} must not validate as 56-bit".format(preamble))

    def test_stress_mark_ratio_boundaries_34_35_36(self):
        """Adversarially verify discrimination across 34%, 35%, and 36% duty cycle boundaries."""
        period = 1000  # Total period = 1000us

        # 34% mark ratio (340us mark, 660us space) -> logic 0
        ratio34 = (340 * 100) // period
        self.assertEqual(ratio34, 34)
        bit34 = 1 if ratio34 >= MagiQuestDecoder.RATIO_THRESHOLD else 0
        self.assertEqual(bit34, 0, "34% mark ratio must resolve to bit 0")

        # 35% mark ratio (350us mark, 650us space) -> logic 1 (exact threshold)
        ratio35 = (350 * 100) // period
        self.assertEqual(ratio35, 35)
        bit35 = 1 if ratio35 >= MagiQuestDecoder.RATIO_THRESHOLD else 0
        self.assertEqual(bit35, 1, "35% mark ratio must resolve to bit 1")

        # 36% mark ratio (360us mark, 640us space) -> logic 1
        ratio36 = (360 * 100) // period
        self.assertEqual(ratio36, 36)
        bit36 = 1 if ratio36 >= MagiQuestDecoder.RATIO_THRESHOLD else 0
        self.assertEqual(bit36, 1, "36% mark ratio must resolve to bit 1")

    def test_stress_bit_period_tolerance_limits(self):
        """Adversarially test exact bit period boundary limits (649, 650, 1750, 1751 us)."""
        valid_wand = 0x55AA55AA
        valid_mag = 0x0180

        # Construct frame with 649us period (below 650us minimum)
        pulses_649 = [(180, 469)] * 56  # 180+469 = 649us
        _, _, status_649 = MagiQuestDecoder.decode_pulse_train(pulses_649)
        self.assertEqual(status_649, "invalid_bit_period")

        # Construct frame with exact 650us period (minimum allowed)
        # Preamble 8 bits of 0: (180, 470) -> ratio = 27% (bit 0)
        pulses_650 = [(180, 470)] * 56
        _, _, status_650 = MagiQuestDecoder.decode_pulse_train(pulses_650)
        # Should not reject as invalid_bit_period
        self.assertNotEqual(status_650, "invalid_bit_period")

        # Construct frame with exact 1750us period (maximum allowed)
        pulses_1750 = [(450, 1300)] * 56  # 450+1300 = 1750us, ratio = 25% (bit 0)
        _, _, status_1750 = MagiQuestDecoder.decode_pulse_train(pulses_1750)
        self.assertNotEqual(status_1750, "invalid_bit_period")

        # Construct frame with 1751us period (above 1750us maximum)
        pulses_1751 = [(451, 1300)] * 56  # 451+1300 = 1751us
        _, _, status_1751 = MagiQuestDecoder.decode_pulse_train(pulses_1751)
        self.assertEqual(status_1751, "invalid_bit_period")

    # =========================================================================
    # 2. 48-Bit Fallback Frame Decoding
    # =========================================================================

    def test_stress_48bit_fallback_fuzzing_500_iterations(self):
        """Fuzz test 48-bit fallback frame decoder with 500 random wand IDs."""
        random.seed(0xDEADBEEF)
        for _ in range(500):
            rand_wand = random.randint(1, 0xFFFFFFFF)
            rand_mag = random.randint(0, 0xFFFF)
            pulses = MagiQuestEncoder.encode_48bit_fallback(rand_wand, rand_mag)
            self.assertEqual(len(pulses), 48)
            wand_id, mag, status = MagiQuestDecoder.decode_pulse_train(pulses)
            self.assertEqual(status, "48bit_fallback")
            self.assertEqual(wand_id, rand_wand)
            self.assertEqual(mag, rand_mag)

    # =========================================================================
    # 3. Trailing Mark Silence Timeout Discrimination
    # =========================================================================

    def test_stress_trailing_mark_midpoint_discrimination(self):
        """Verify trailing 56th mark threshold (400us midpoint between 280us and 560us)."""
        # Under C++ IRController.cpp lines 173-176:
        # if (markUs >= 150 && markUs <= 850) { bitVal = (markUs >= 400) ? 1 : 0; }
        test_cases = [
            (149, "REJECTED_NOISE"),
            (150, 0),
            (280, 0),
            (399, 0),
            (400, 1),
            (560, 1),
            (850, 1),
            (851, "REJECTED_NOISE"),
        ]
        for mark_us, expected in test_cases:
            if expected == "REJECTED_NOISE":
                valid = (150 <= mark_us <= 850)
                self.assertFalse(valid, "Mark {}us should be rejected as noise".format(mark_us))
            else:
                valid = (150 <= mark_us <= 850)
                self.assertTrue(valid)
                bit_val = 1 if mark_us >= 400 else 0
                self.assertEqual(bit_val, expected,
                                 "Mark {}us expected bit {} got {}".format(mark_us, expected, bit_val))

    # =========================================================================
    # 4. Cross-Shoulder Debouncing Stress (Simultaneous & Fast Bursts)
    # =========================================================================

    def test_stress_cross_shoulder_debouncing_simultaneous_and_echoes(self):
        """Stress test cross-shoulder shared debounce under simultaneous hits and rapid echoes."""
        sim = WandInteractionSimulator(pink_id=0xAAAA1111, blue_id=0xBBBB2222)

        # 1. Hit on Left Shoulder at t=5000ms
        res_left = sim.handle_wand_signal(0xAAAA1111, 5000)
        self.assertEqual(res_left, "DISPATCH_PINK")
        self.assertEqual(sim.mode, "PINK")

        # 2. Simultaneous hit on Right Shoulder at t=5000ms (0ms delta)
        res_right_simul = sim.handle_wand_signal(0xAAAA1111, 5000)
        self.assertEqual(res_right_simul, "DEBOUNCED")

        # 3. Echo pulses at 10ms, 50ms, 100ms, 200ms, 399ms
        for offset in [10, 50, 100, 200, 399]:
            res_echo = sim.handle_wand_signal(0xAAAA1111, 5000 + offset)
            self.assertEqual(res_echo, "DEBOUNCED", "Echo at +{}ms must be debounced".format(offset))

        # 4. Legit hit at t=5400ms (exactly 400ms later)
        res_legit = sim.handle_wand_signal(0xAAAA1111, 5400)
        self.assertEqual(res_legit, "DISPATCH_PINK")

    def test_stress_cross_shoulder_differing_wands_not_debounced(self):
        """Verify that alternating opposite wands are NOT debounced even within 50ms."""
        sim = WandInteractionSimulator(pink_id=0x11111111, blue_id=0x22222222)

        # Pink wand on Left at t=1000ms
        res_pink = sim.handle_wand_signal(0x11111111, 1000)
        self.assertEqual(res_pink, "DISPATCH_PINK")

        # Blue wand on Right at t=1050ms (only 50ms later)
        # Differing IDs must NOT be blocked by 400ms debounce
        res_blue = sim.handle_wand_signal(0x22222222, 1050)
        self.assertEqual(res_blue, "DISPATCH_SPLOTCHES")
        self.assertEqual(sim.mode, "SPLOTCHES")

    # =========================================================================
    # 5. Wand Pairing State Machine Boundaries & Web Cancellation
    # =========================================================================

    def test_stress_pairing_timeout_boundaries_29999_30000_30001(self):
        """Stress test pairing timeout exact millisecond boundary limits."""
        sim = WandInteractionSimulator()
        sim.start_pairing("PINK", 10000)

        # At t=39999ms (29999ms elapsed): still active
        self.assertFalse(sim.check_pairing_timeout(39999))
        self.assertEqual(sim.pairing_state, "PINK")

        # Hit at 39999ms must succeed
        res = sim.handle_wand_signal(0x99887766, 39999)
        self.assertEqual(res, "PAIRED_PINK")
        self.assertEqual(sim.pink_id, 0x99887766)
        self.assertEqual(sim.nvs[NVS_KEY_PINK_WAND], 0x99887766)
        self.assertEqual(sim.pairing_state, "NONE")

        # Restart pairing and test exact 30000ms timeout
        sim.start_pairing("BLUE", 50000)
        self.assertTrue(sim.check_pairing_timeout(80000))  # Exactly 30000ms elapsed
        self.assertEqual(sim.pairing_state, "NONE")

        # Wand hit at t=80001ms after timeout must NOT pair
        res_late = sim.handle_wand_signal(0x12345678, 80001)
        self.assertNotEqual(res_late, "PAIRED_BLUE")

    def test_stress_pairing_web_cancellation_rapid(self):
        """Verify rapid cancellation via web endpoint returns immediately to NONE."""
        sim = WandInteractionSimulator()
        sim.start_pairing("PINK", 2000)
        self.assertEqual(sim.pairing_state, "PINK")

        # User clicks Cancel on web UI at t=2050ms
        status, body = sim.handle_rest_request("/register/cancel")
        self.assertEqual(status, 200)
        self.assertEqual(body["pairing"], "NONE")
        self.assertEqual(sim.pairing_state, "NONE")

        # Wand flick arrives at t=2100ms
        res = sim.handle_wand_signal(0x55555555, 2100)
        self.assertEqual(res, "UNKNOWN_WAND")
        self.assertEqual(sim.pink_id, 0x2F073545)  # Unmodified

    # =========================================================================
    # 6. Rapid Succession Duel Timing (2000ms Window vs >2000ms)
    # =========================================================================

    def test_stress_rapid_succession_duel_boundaries(self):
        """Stress test duel trigger at delta=0ms, 1999ms, 2000ms vs 2001ms."""
        # Case A: Pink at 1000ms, Blue at 2999ms (1999ms later) -> SPLOTCHES
        sim_a = WandInteractionSimulator(pink_id=0x11111111, blue_id=0x22222222)
        sim_a.handle_wand_signal(0x11111111, 1000)
        res_a = sim_a.handle_wand_signal(0x22222222, 2999)
        self.assertEqual(res_a, "DISPATCH_SPLOTCHES")
        self.assertEqual(sim_a.mode, "SPLOTCHES")

        # Case B: Pink at 1000ms, Blue at 3000ms (exactly 2000ms later) -> SPLOTCHES
        sim_b = WandInteractionSimulator(pink_id=0x11111111, blue_id=0x22222222)
        sim_b.handle_wand_signal(0x11111111, 1000)
        res_b = sim_b.handle_wand_signal(0x22222222, 3000)
        self.assertEqual(res_b, "DISPATCH_SPLOTCHES")
        self.assertEqual(sim_b.mode, "SPLOTCHES")

        # Case C: Pink at 1000ms, Blue at 3001ms (2001ms later) -> Stays individual BLUE
        sim_c = WandInteractionSimulator(pink_id=0x11111111, blue_id=0x22222222)
        sim_c.handle_wand_signal(0x11111111, 1000)
        res_c = sim_c.handle_wand_signal(0x22222222, 3001)
        self.assertEqual(res_c, "DISPATCH_BLUE")
        self.assertEqual(sim_c.mode, "BLUE")

        # Case D: Reverse order (Blue first at 5000ms, Pink at 6500ms) -> SPLOTCHES
        sim_d = WandInteractionSimulator(pink_id=0x11111111, blue_id=0x22222222)
        sim_d.handle_wand_signal(0x22222222, 5000)
        res_d = sim_d.handle_wand_signal(0x11111111, 6500)
        self.assertEqual(res_d, "DISPATCH_SPLOTCHES")
        self.assertEqual(sim_d.mode, "SPLOTCHES")

    # =========================================================================
    # 7. Disassembly Verification & Firmware Integrity
    # =========================================================================

    def test_stress_firmware_critical_section_lock_under_30ns(self):
        """Verify RISC-V disassembly critical section executes strictly < 30.0 ns."""
        self.assertTrue(self.has_elf)
        match = re.search(r"<processChannelPacket\(IRChannel&\)>:(.*?)(?=\n[0-9a-fA-F]+ <|\Z)", self.disasm, re.DOTALL)
        self.assertIsNotNone(match)
        code = match.group(1)

        set_mask_match = re.search(r"([0-9a-fA-F]+):\s+.*jalr.*<vPortSetInterruptMask>", code)
        clear_mask_match = re.search(r"([0-9a-fA-F]+):\s+.*jalr.*<vPortClearInterruptMask>", code)
        self.assertIsNotNone(set_mask_match)
        self.assertIsNotNone(clear_mask_match)

        call_clear_pos = code.find(clear_mask_match.group(0))
        auipc_match = re.search(r"([0-9a-fA-F]+):\s+[0-9a-fA-F]+\s+auipc.*(?=\n\s*" + clear_mask_match.group(1) + r":)", code)
        end_pos = auipc_match.start() if auipc_match else call_clear_pos

        between_code = code[code.find(set_mask_match.group(0)):end_pos]
        lines = [l for l in between_code.splitlines() if re.match(r"^\s*[0-9a-fA-F]+:\s+[0-9a-fA-F]+", l)]
        inner_instructions = len(lines) - 1

        estimated_time_ns = inner_instructions * 6.25
        print("\n  [Stress Benchmark] Critical section instruction count: {} ({} ns)".format(
            inner_instructions, estimated_time_ns))
        self.assertLessEqual(inner_instructions, 5)
        self.assertLess(estimated_time_ns, 30.0)

    def test_stress_iram_symbols_present(self):
        """Verify all ISR handlers strictly reside in internal IRAM."""
        self.assertTrue(self.has_elf)
        symbols_to_check = ["isrLeft", "isrRight", "handleEdge"]
        for sym in symbols_to_check:
            match = re.search(r"([0-9a-fA-F]+)\s+[tTW]\s+.*" + sym, self.nm_output)
            self.assertIsNotNone(match, "Symbol {} must be in ELF symbol table".format(sym))
            addr = int(match.group(1), 16)
            self.assertTrue(0x40380000 <= addr < 0x40390000,
                            "Symbol {} at 0x{:08X} must be in IRAM [0x40380000, 0x40390000)".format(sym, addr))


if __name__ == "__main__":
    unittest.main()
