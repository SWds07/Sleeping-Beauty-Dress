# -*- coding: utf-8 -*-
from __future__ import print_function, division, absolute_import
import unittest
from tests.helpers import WandInteractionSimulator

class TestFeature08IREventDispatch(unittest.TestCase):
    """Feature 8: IR Event Dispatch (Pink wand, Blue wand, Rapid dual wands)."""

    def setUp(self):
        self.sim = WandInteractionSimulator(pink_id=0x11111111, blue_id=0x22222222)

    def test_f08_01_pink_wand_triggers_pink_mode(self):
        """Verify Pink wand detection sets mode to PINK."""
        res = self.sim.handle_wand_signal(0x11111111, 1000)
        self.assertEqual(res, "DISPATCH_PINK")
        self.assertEqual(self.sim.mode, "PINK")

    def test_f08_02_blue_wand_triggers_blue_mode(self):
        """Verify Blue wand detection sets mode to BLUE."""
        res = self.sim.handle_wand_signal(0x22222222, 1000)
        self.assertEqual(res, "DISPATCH_BLUE")
        self.assertEqual(self.sim.mode, "BLUE")

    def test_f08_03_rapid_succession_triggers_splotches(self):
        """Verify rapid dual wand hits within 2000ms trigger SPLOTCHES."""
        self.sim.handle_wand_signal(0x11111111, 1000)
        res = self.sim.handle_wand_signal(0x22222222, 2500)  # 1500ms later (<=2000ms)
        self.assertEqual(res, "DISPATCH_SPLOTCHES")
        self.assertEqual(self.sim.mode, "SPLOTCHES")

    def test_f08_04_slow_succession_stays_individual(self):
        """Verify wand hits beyond 2000ms switch to individual color instead."""
        self.sim.handle_wand_signal(0x11111111, 1000)
        res = self.sim.handle_wand_signal(0x22222222, 3500)  # 2500ms later (>2000ms)
        self.assertEqual(res, "DISPATCH_BLUE")
        self.assertEqual(self.sim.mode, "BLUE")

    def test_f08_05_burst_debouncing_400ms(self):
        """Verify identical wand bursts within 400ms are debounced/discarded."""
        res1 = self.sim.handle_wand_signal(0x11111111, 1000)
        self.assertEqual(res1, "DISPATCH_PINK")
        res2 = self.sim.handle_wand_signal(0x11111111, 1200)  # 200ms later (<400ms)
        self.assertEqual(res2, "DEBOUNCED")

if __name__ == "__main__":
    unittest.main()
