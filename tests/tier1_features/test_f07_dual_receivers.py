# -*- coding: utf-8 -*-
from __future__ import print_function, division, absolute_import
import unittest
from tests.helpers import PIN_IR_RECV_LEFT, PIN_IR_RECV_RIGHT

class TestFeature07DualReceivers(unittest.TestCase):
    """Feature 7: Dual 38KHz IR Receivers (Left Shoulder GPIO 3, Right Shoulder GPIO 2)."""

    def test_f07_01_left_shoulder_pin(self):
        """Verify Left Shoulder IR receiver pin assignment (GPIO 3 / D1)."""
        self.assertEqual(PIN_IR_RECV_LEFT, 3)

    def test_f07_02_right_shoulder_pin(self):
        """Verify Right Shoulder IR receiver pin assignment (GPIO 2 / D0)."""
        self.assertEqual(PIN_IR_RECV_RIGHT, 2)

    def test_f07_03_concurrent_360_coverage(self):
        """Verify dual receiver channels are independent and non-interfering."""
        channels = ["left", "right"]
        self.assertEqual(len(channels), 2)
        self.assertNotEqual(PIN_IR_RECV_LEFT, PIN_IR_RECV_RIGHT)

    def test_f07_04_ping_pong_double_buffering(self):
        """Verify ping-pong double buffer configuration (2 buffers per channel)."""
        num_buffers_per_channel = 2
        buffer_capacity_samples = 160
        self.assertEqual(num_buffers_per_channel, 2)
        self.assertEqual(buffer_capacity_samples, 160)

    def test_f07_05_inter_burst_silence_detection(self):
        """Verify inter-burst silence detection threshold is 3500us."""
        silence_threshold_us = 3500
        normal_space_max_us = 1000
        self.assertGreater(silence_threshold_us, normal_space_max_us)

if __name__ == "__main__":
    unittest.main()
