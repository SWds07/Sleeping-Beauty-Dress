# -*- coding: utf-8 -*-
from __future__ import print_function, division, absolute_import
import unittest
from tests.helpers import WandInteractionSimulator

class TestBoundary09PairingTimeoutBoundaries(unittest.TestCase):
    """Tier 2 Boundary: Wand pairing 30s timeout and state edge transitions."""

    def setUp(self):
        self.sim = WandInteractionSimulator()

    def test_b09_01_timeout_at_29999ms(self):
        """Verify pairing mode remains active at 29999ms elapsed."""
        self.sim.start_pairing("PINK", 1000)
        timed_out = self.sim.check_pairing_timeout(30999)  # delta = 29999ms
        self.assertFalse(timed_out)
        self.assertEqual(self.sim.pairing_state, "PINK")

    def test_b09_02_timeout_at_30000ms(self):
        """Verify pairing mode expires exactly at 30000ms elapsed."""
        self.sim.start_pairing("PINK", 1000)
        timed_out = self.sim.check_pairing_timeout(31000)  # delta = 30000ms
        self.assertTrue(timed_out)
        self.assertEqual(self.sim.pairing_state, "NONE")

    def test_b09_03_pairing_cancels_while_idle(self):
        """Verify cancel pairing when already idle (NONE) safely preserves NONE state."""
        self.assertEqual(self.sim.pairing_state, "NONE")
        self.sim.cancel_pairing()
        self.assertEqual(self.sim.pairing_state, "NONE")

    def test_b09_04_wand_hit_at_29999ms(self):
        """Verify wand received at 29999ms pairs successfully before timeout."""
        self.sim.start_pairing("PINK", 1000)
        res = self.sim.handle_wand_signal(0x55555555, 30999)
        self.assertEqual(res, "PAIRED_PINK")
        self.assertEqual(self.sim.pink_id, 0x55555555)

    def test_b09_05_wand_hit_at_30001ms(self):
        """Verify wand received after timeout (30001ms) is not paired."""
        self.sim.start_pairing("PINK", 1000)
        self.sim.check_pairing_timeout(31001)  # timeout fires
        res = self.sim.handle_wand_signal(0x55555555, 31002)
        self.assertNotEqual(res, "PAIRED_PINK")
        self.assertNotEqual(self.sim.pink_id, 0x55555555)

if __name__ == "__main__":
    unittest.main()
