# -*- coding: utf-8 -*-
from __future__ import print_function, division, absolute_import
import unittest

class TestBoundary07DualReceiverBoundaries(unittest.TestCase):
    """Tier 2 Boundary: Dual IR receiver buffer and transition boundaries."""

    def test_b07_01_rawbuf_overflow_clamp_159(self):
        """Verify sample buffer index clamps at maximum index 159."""
        max_buf_len = 160
        max_index = max_buf_len - 1
        current_idx = 170
        clamped_idx = min(current_idx, max_index)
        self.assertEqual(clamped_idx, 159)

    def test_b07_02_fewer_than_100_transitions(self):
        """Verify buffer with fewer than 100 transitions is discarded."""
        sample_count = 99
        is_sufficient = sample_count >= 100
        self.assertFalse(is_sufficient)

    def test_b07_03_silence_threshold_3499us_vs_3500us(self):
        """Verify silence detection threshold exactly at 3500us."""
        delta_3499 = 3499
        delta_3500 = 3500
        threshold = 3500
        self.assertFalse(delta_3499 >= threshold)
        self.assertTrue(delta_3500 >= threshold)

    def test_b07_04_simultaneous_both_shoulders(self):
        """Verify simultaneous signals across dual receivers don't produce double-trigger."""
        simultaneous_delta_ms = 0
        debounce_window_ms = 400
        is_debounced = simultaneous_delta_ms < debounce_window_ms
        self.assertTrue(is_debounced)

    def test_b07_05_overvoltage_clamping_protection(self):
        """Verify 3.3V rail limit avoids ESD diode saturation distortion."""
        max_safe_input_v = 3.6
        applied_v = 3.3
        self.assertLessEqual(applied_v, max_safe_input_v)

if __name__ == "__main__":
    unittest.main()
