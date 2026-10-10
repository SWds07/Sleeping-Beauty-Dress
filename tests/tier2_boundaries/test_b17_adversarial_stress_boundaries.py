# -*- coding: utf-8 -*-
from __future__ import print_function, division, absolute_import
import unittest
from tests.helpers import MagiQuestDecoder, WandInteractionSimulator

class TestBoundary17AdversarialStressBoundaries(unittest.TestCase):
    """Tier 2 Boundary: Adversarial stress testing and corruption resistance."""

    def setUp(self):
        self.sim = WandInteractionSimulator(pink_id=0x11111111, blue_id=0x22222222)

    def test_b17_01_malformed_ir_noise_stream(self):
        """Verify stream of random pulse periods does not crash decoder."""
        noise_stream = [(100, 200), (3000, 50), (10, 10)] * 20
        wand_id, mag, status = MagiQuestDecoder.decode_pulse_train(noise_stream)
        self.assertIsNone(wand_id)
        self.assertEqual(status, "invalid_bit_period")

    def test_b17_02_rapid_web_endpoint_hammering(self):
        """Verify handling 20 consecutive HTTP override calls deterministically."""
        endpoints = ["/setPink", "/setBlue", "/setSplotches", "/setOff"] * 5
        for ep in endpoints:
            status, data = self.sim.handle_rest_request(ep)
            self.assertEqual(status, 200)
            self.assertEqual(data.get("status"), "ok")

    def test_b17_03_pairing_cancellation_during_burst(self):
        """Verify cancelling pairing immediately resets state to NONE."""
        self.sim.start_pairing("PINK", 1000)
        self.sim.cancel_pairing()
        self.assertEqual(self.sim.pairing_state, "NONE")
        res = self.sim.handle_wand_signal(0x99999999, 1050)
        self.assertNotEqual(res, "PAIRED_PINK")

    def test_b17_04_extreme_brightness_values(self):
        """Verify extreme brightness values (-9999 and 99999) are safely clamped."""
        self.sim.handle_rest_request("/brightness", {"val": "-9999"})
        self.assertEqual(self.sim.brightness, 0)

        self.sim.handle_rest_request("/brightness", {"val": "99999"})
        self.assertEqual(self.sim.brightness, 160)

    def test_b17_05_rapid_color_mode_thrashing(self):
        """Verify rapid alternating wand triggers update mode state reliably."""
        for i in range(10):
            ts = 1000 + i * 500  # every 500ms (beyond 400ms debounce)
            code = 0x11111111 if (i % 2 == 0) else 0x22222222
            res = self.sim.handle_wand_signal(code, ts)
            self.assertTrue(res in ("DISPATCH_PINK", "DISPATCH_BLUE", "DISPATCH_SPLOTCHES"))

if __name__ == "__main__":
    unittest.main()
