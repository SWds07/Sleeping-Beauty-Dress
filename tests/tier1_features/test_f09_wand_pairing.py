# -*- coding: utf-8 -*-
from __future__ import print_function, division, absolute_import
import unittest
from tests.helpers import WandInteractionSimulator, PAIRING_TIMEOUT_MS

class TestFeature09WandPairing(unittest.TestCase):
    """Feature 9: Wand Pairing State Machine (30s timeout, pairing modes)."""

    def setUp(self):
        self.sim = WandInteractionSimulator()

    def test_f09_01_start_pairing_pink(self):
        """Verify entering pairing mode for Pink wand."""
        self.sim.start_pairing("PINK", 1000)
        self.assertEqual(self.sim.pairing_state, "PINK")

    def test_f09_02_start_pairing_blue(self):
        """Verify entering pairing mode for Blue wand."""
        self.sim.start_pairing("BLUE", 1000)
        self.assertEqual(self.sim.pairing_state, "BLUE")

    def test_f09_03_pairing_timeout_30s(self):
        """Verify pairing mode times out after 30000ms."""
        self.sim.start_pairing("PINK", 1000)
        timed_out = self.sim.check_pairing_timeout(31000)  # 30000ms elapsed
        self.assertTrue(timed_out)
        self.assertEqual(self.sim.pairing_state, "NONE")

    def test_f09_04_cancel_pairing_immediate(self):
        """Verify immediate cancellation of pairing mode."""
        self.sim.start_pairing("PINK", 1000)
        self.sim.cancel_pairing()
        self.assertEqual(self.sim.pairing_state, "NONE")

    def test_f09_05_successful_pairing_triggers_feedback(self):
        """Verify wand detection during pairing triggers feedback mode."""
        self.sim.start_pairing("PINK", 1000)
        new_wand = 0x99887766
        res = self.sim.handle_wand_signal(new_wand, 2000)
        self.assertEqual(res, "PAIRED_PINK")
        self.assertEqual(self.sim.pink_id, new_wand)
        self.assertEqual(self.sim.mode, "PAIRING_FEEDBACK")
        self.assertEqual(self.sim.pairing_state, "NONE")

if __name__ == "__main__":
    unittest.main()
