# -*- coding: utf-8 -*-
from __future__ import print_function, division, absolute_import
import unittest
from tests.helpers import MagiQuestEncoder, MagiQuestDecoder

class TestBoundary06MagiQuestPulseBoundaries(unittest.TestCase):
    """Tier 2 Boundary: MagiQuest pulse timing boundaries and tolerance limits."""

    def test_b06_01_bit_period_under_650us(self):
        """Verify bit period of 640us (<650us min threshold) is rejected."""
        invalid_pulses = [(200, 440)] * 56  # 640us total period
        wand_id, mag, status = MagiQuestDecoder.decode_pulse_train(invalid_pulses)
        self.assertEqual(status, "invalid_bit_period")
        self.assertIsNone(wand_id)

    def test_b06_02_bit_period_over_1750us(self):
        """Verify bit period of 1760us (>1750us max threshold) is rejected."""
        invalid_pulses = [(600, 1160)] * 56  # 1760us total period
        wand_id, mag, status = MagiQuestDecoder.decode_pulse_train(invalid_pulses)
        self.assertEqual(status, "invalid_bit_period")
        self.assertIsNone(wand_id)

    def test_b06_03_corrupted_preamble_non_zero(self):
        """Verify non-zero preamble (e.g. 0x01) fails 56-bit validation."""
        valid_pulses = MagiQuestEncoder.encode_56bit(0x12345678, 0x0100)
        # Corrupt bit 7 of preamble to be a logic 1
        corrupted_pulses = list(valid_pulses)
        corrupted_pulses[7] = (580, 600)  # Logic 1
        wand_id, mag, status = MagiQuestDecoder.decode_pulse_train(corrupted_pulses)
        # 56-bit should fail; falls back to 48-bit only if sub-frame aligns
        self.assertNotEqual(status, "56bit_valid")

    def test_b06_04_47_bits_truncation(self):
        """Verify 47-pulse truncated train fails both 56-bit and 48-bit decoding."""
        truncated_pulses = [(280, 850)] * 47
        wand_id, mag, status = MagiQuestDecoder.decode_pulse_train(truncated_pulses)
        self.assertEqual(status, "insufficient_pulses")

    def test_b06_05_duty_cycle_threshold_edge(self):
        """Verify exact duty cycle threshold behavior at 34% (0) vs 35% (1)."""
        period = 1000
        # 34% mark -> 340 mark, 660 space
        ratio34 = (340 * 100) // period
        bit34 = 1 if ratio34 >= MagiQuestDecoder.RATIO_THRESHOLD else 0
        self.assertEqual(bit34, 0)

        # 35% mark -> 350 mark, 650 space
        ratio35 = (350 * 100) // period
        bit35 = 1 if ratio35 >= MagiQuestDecoder.RATIO_THRESHOLD else 0
        self.assertEqual(bit35, 1)

if __name__ == "__main__":
    unittest.main()
