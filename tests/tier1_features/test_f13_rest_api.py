# -*- coding: utf-8 -*-
from __future__ import print_function, division, absolute_import
import unittest
from tests.helpers import WandInteractionSimulator

class TestFeature13RestAPI(unittest.TestCase):
    """Feature 13: REST API Endpoints (/api/status, overrides, pairing, brightness)."""

    def setUp(self):
        self.sim = WandInteractionSimulator(pink_id=0x12345678, blue_id=0x87654321)

    def test_f13_01_api_status_json_schema(self):
        """Verify /api/status returns required JSON schema fields."""
        status, data = self.sim.handle_rest_request("/api/status")
        self.assertEqual(status, 200)
        self.assertIn("mode", data)
        self.assertIn("pinkWand", data)
        self.assertIn("blueWand", data)
        self.assertIn("pairing", data)
        self.assertIn("brightness", data)

    def test_f13_02_set_color_endpoints(self):
        """Verify color switching endpoints."""
        endpoints = [
            ("/setPink", "PINK"),
            ("/setBlue", "BLUE"),
            ("/setSplotches", "SPLOTCHES"),
            ("/setOff", "OFF")
        ]
        for ep, expected_mode in endpoints:
            status, data = self.sim.handle_rest_request(ep)
            self.assertEqual(status, 200)
            self.assertEqual(data.get("mode"), expected_mode)
            self.assertEqual(self.sim.mode, expected_mode)

    def test_f13_03_register_endpoints(self):
        """Verify wand pairing triggers and cancel endpoints."""
        status, data = self.sim.handle_rest_request("/register/pink")
        self.assertEqual(status, 200)
        self.assertEqual(data.get("pairing"), "PINK")

        status, data = self.sim.handle_rest_request("/register/cancel")
        self.assertEqual(status, 200)
        self.assertEqual(data.get("pairing"), "NONE")

        status, data = self.sim.handle_rest_request("/register/blue")
        self.assertEqual(status, 200)
        self.assertEqual(data.get("pairing"), "BLUE")

    def test_f13_04_brightness_endpoint(self):
        """Verify brightness endpoint adjusts brightness value."""
        status, data = self.sim.handle_rest_request("/setBrightness", {"val": "120"})
        self.assertEqual(status, 200)
        self.assertEqual(self.sim.brightness, 120)

    def test_f13_05_catch_all_redirect_302(self):
        """Verify unknown paths return 302 redirect."""
        status, headers = self.sim.handle_rest_request("/unknown/path")
        self.assertEqual(status, 302)
        self.assertEqual(headers.get("Location"), "http://192.168.4.1/")

if __name__ == "__main__":
    unittest.main()
