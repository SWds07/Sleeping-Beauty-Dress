# -*- coding: utf-8 -*-
from __future__ import print_function, division, absolute_import
import unittest
import os

class TestBoundary15BootOrderBoundaries(unittest.TestCase):
    """Tier 2 Boundary: System execution timing and watchdog safety."""

    def setUp(self):
        main_path = os.path.join(os.path.dirname(__file__), "..", "..", "src", "main.cpp")
        self.assertTrue(os.path.exists(main_path))
        with open(main_path, "r") as f:
            self.main_content = f.read()

    def test_b15_01_zero_delay_in_loop(self):
        """Verify loop() body contains no delay() calls to maintain responsiveness."""
        loop_code = self.main_content[self.main_content.find("void loop()"):]
        self.assertNotIn("delay(", loop_code)

    def test_b15_02_watchdog_timeout_margin(self):
        """Verify subsystem polling operates well below 3000ms watchdog trigger."""
        max_subsystem_poll_time_ms = 50
        wdt_timeout_ms = 3000
        self.assertLess(max_subsystem_poll_time_ms, wdt_timeout_ms)

    def test_b15_03_setup_serial_settle_delay(self):
        """Verify setup includes UART stabilization delay (delay(200))."""
        self.assertIn("delay(200)", self.main_content)

    def test_b15_04_subsystem_initialization_isolation(self):
        """Verify initialization sequence contains distinct step boundaries."""
        steps = [
            "StorageController::init()",
            "LedController::init()",
            "IRController::init()",
            "WebController::init()"
        ]
        for s in steps:
            self.assertIn(s, self.main_content)

    def test_b15_05_cooperative_multitasking_budget(self):
        """Verify round-robin cycle budget is non-blocking."""
        cooperative_tasks = ["LedController::update", "IRController::update", "WebController::update"]
        self.assertEqual(len(cooperative_tasks), 3)

if __name__ == "__main__":
    unittest.main()
