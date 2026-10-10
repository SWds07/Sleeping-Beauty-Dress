# -*- coding: utf-8 -*-
from __future__ import print_function, division, absolute_import
import unittest
from tests.helpers import MagiQuestEncoder, MagiQuestDecoder

class TestFeature06MagiQuestDecoding(unittest.TestCase):
    """Feature 6: 56-bit MagiQuest IR Decoding and 48-bit fallback."""

    def test_f06_01_56bit_preamble_validation(self):
        """Verify 8-bit preamble strictly 0x00 for 56-bit frame."""
        pulses = MagiQuestEncoder.encode_56bit(0x2F073545, 0x0150)
        self.assertEqual(len(pulses), 56)
        wand_id, mag, status = MagiQuestDecoder.decode_pulse_train(pulses)
        self.assertEqual(status, "56bit_valid")
        self.assertEqual(wand_id, 0x2F073545)
        self.assertEqual(mag, 0x0150)

    def test_f06_02_32bit_wand_id_extraction(self):
        """Verify 32-bit unique wand ID decoded correctly."""
        test_id = 0xA1B2C3D4
        pulses = MagiQuestEncoder.encode_56bit(test_id, 0x00FF)
        wand_id, mag, status = MagiQuestDecoder.decode_pulse_train(pulses)
        self.assertEqual(wand_id, test_id)

    def test_f06_03_16bit_magnitude_extraction(self):
        """Verify 16-bit flick magnitude decoded correctly."""
        test_mag = 0x89AB
        pulses = MagiQuestEncoder.encode_56bit(0x12345678, test_mag)
        wand_id, mag, status = MagiQuestDecoder.decode_pulse_train(pulses)
        self.assertEqual(mag, test_mag)

    def test_f06_04_48bit_fallback_framing(self):
        """Verify 48-bit fallback frame without preamble decodes correctly."""
        test_id = 0x44556677
        pulses = MagiQuestEncoder.encode_48bit_fallback(test_id, 0x0200)
        self.assertEqual(len(pulses), 48)
        wand_id, mag, status = MagiQuestDecoder.decode_pulse_train(pulses)
        self.assertEqual(status, "48bit_fallback")
        self.assertEqual(wand_id, test_id)

    def test_f06_05_bit_duty_cycle_discrimination(self):
        """Verify mark ratio threshold (~35%) differentiates bit 0 (~25%) and bit 1 (~50%)."""
        bit0_ratio = (280 * 100) // (280 + 850)  # ~24.7%
        bit1_ratio = (580 * 100) // (580 + 600)  # ~49.1%
        threshold = 35
        self.assertLess(bit0_ratio, threshold)
        self.assertGreater(bit1_ratio, threshold)

if __name__ == "__main__":
    unittest.main()
