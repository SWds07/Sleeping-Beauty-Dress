# -*- coding: utf-8 -*-
from __future__ import print_function, division, absolute_import
import unittest
from tests.helpers import WandInteractionSimulator

class TestBoundary08DispatchTimingBoundaries(unittest.TestCase):
    """Tier 2 Boundary: Rapid wand succession and debounce timing thresholds."""

    def setUp(self):
        self.sim = WandInteractionSimulator(pink_id=0x11111111, blue_id=0x22222222)

    def test_b08_01_rapid_window_exact_2000ms(self):
        """Verify delta of exactly 2000ms qualifies as rapid succession (Splotches)."""
        self.sim.handle_wand_signal(0x11111111, 1000)
        res = self.sim.handle_wand_signal(0x22222222, 3000)  # delta = 2000ms
        self.assertEqual(res, "DISPATCH_SPLOTCHES")
        self.assertEqual(self.sim.mode, "SPLOTCHES")

    def test_b08_02_rapid_window_boundary_2001ms(self):
        """Verify delta of 2001ms (>2000ms) switches to individual color."""
        self.sim.handle_wand_signal(0x11111111, 1000)
        res = self.sim.handle_wand_signal(0x22222222, 3001)  # delta = 2001ms
        self.assertEqual(res, "DISPATCH_BLUE")
        self.assertEqual(self.sim.mode, "BLUE")

    def test_b08_03_debounce_exact_399ms(self):
        """Verify duplicate burst at 399ms (<400ms) is discarded by debounce."""
        self.sim.handle_wand_signal(0x11111111, 1000)
        res = self.sim.handle_wand_signal(0x11111111, 1399)  # delta = 399ms
        self.assertEqual(res, "DEBOUNCED")

    def test_b08_04_debounce_exact_400ms(self):
        """Verify repeated burst at exactly 400ms is accepted."""
        self.sim.handle_wand_signal(0x11111111, 1000)
        res = self.sim.handle_wand_signal(0x11111111, 1400)  # delta = 400ms
        self.assertEqual(res, "DISPATCH_PINK")

    def test_b08_05_zero_stored_wand_id(self):
        """Verify unconfigured wand ID 0 is never matched by incoming wand."""
        sim_unpaired = WandInteractionSimulator(pink_id=0, blue_id=0)
        res = sim_unpaired.handle_wand_signal(0x12345678, 1000)
        self.assertEqual(res, "UNKNOWN_WAND")

if __name__ == "__main__":
    unittest.main()
