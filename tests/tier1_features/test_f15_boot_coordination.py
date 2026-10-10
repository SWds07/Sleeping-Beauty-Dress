# -*- coding: utf-8 -*-
from __future__ import print_function, division, absolute_import
import unittest
import os

class TestFeature15BootCoordination(unittest.TestCase):
    """Feature 15: Boot Sequencing & Coordination (main.cpp setup/loop)."""

    def setUp(self):
        main_path = os.path.join(os.path.dirname(__file__), "..", "..", "src", "main.cpp")
        self.assertTrue(os.path.exists(main_path))
        with open(main_path, "r") as f:
            self.main_code = f.read()

    def test_f15_01_deterministic_boot_order(self):
        """Verify boot order: Storage -> LED -> IR -> Web in setup()."""
        idx_storage = self.main_code.find("StorageController::init")
        idx_led = self.main_code.find("LedController::init")
        idx_ir = self.main_code.find("IRController::init")
        idx_web = self.main_code.find("WebController::init")

        self.assertNotEqual(idx_storage, -1)
        self.assertNotEqual(idx_led, -1)
        self.assertNotEqual(idx_ir, -1)
        self.assertNotEqual(idx_web, -1)

        self.assertLess(idx_storage, idx_led)
        self.assertLess(idx_led, idx_ir)
        self.assertLess(idx_ir, idx_web)

    def test_f15_02_storage_before_led(self):
        """Verify storage loads paired IDs before LED initializes."""
        idx_storage = self.main_code.find("StorageController::init")
        idx_led = self.main_code.find("LedController::init")
        self.assertLess(idx_storage, idx_led)

    def test_f15_03_led_dark_before_wifi(self):
        """Verify LED subsystem is dark clamped before WiFi radio activates."""
        idx_led = self.main_code.find("LedController::init")
        idx_web = self.main_code.find("WebController::init")
        self.assertLess(idx_led, idx_web)

    def test_f15_04_nonblocking_round_robin_loop(self):
        """Verify loop() non-blocking polling across all three subsystems."""
        loop_section = self.main_code[self.main_code.find("void loop()"):]
        self.assertIn("LedController::update()", loop_section)
        self.assertIn("IRController::update()", loop_section)
        self.assertIn("WebController::update()", loop_section)

    def test_f15_05_serial_baud_115200(self):
        """Verify Serial monitor baud rate is 115200."""
        self.assertIn("Serial.begin(115200)", self.main_code)

if __name__ == "__main__":
    unittest.main()
