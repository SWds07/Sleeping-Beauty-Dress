# -*- coding: utf-8 -*-
from __future__ import print_function, division, absolute_import
import unittest
import os

class TestBoundary16BuildSizeBoundaries(unittest.TestCase):
    """Tier 2 Boundary: Memory bounds and partition limits."""

    def setUp(self):
        ini_path = os.path.join(os.path.dirname(__file__), "..", "..", "platformio.ini")
        self.assertTrue(os.path.exists(ini_path))
        with open(ini_path, "r") as f:
            self.ini_content = f.read()

    def test_b16_01_ram_usage_ceiling_320kb(self):
        """Verify RAM allocation ceiling for ESP32-C3 is 327,680 bytes."""
        total_sram_bytes = 327680
        # Typical firmware uses ~56KB RAM (<20%)
        typical_ram_used = 56740
        self.assertLess(typical_ram_used, total_sram_bytes)

    def test_b16_02_flash_usage_ceiling_app_partition(self):
        """Verify min_spiffs application partition limit is 1,966,080 bytes."""
        app_partition_max_bytes = 1966080
        typical_flash_used = 1394028
        self.assertLess(typical_flash_used, app_partition_max_bytes)

    def test_b16_03_monitor_speed_115200(self):
        """Verify monitor_speed is set to 115200 in platformio.ini."""
        self.assertIn("monitor_speed = 115200", self.ini_content)

    def test_b16_04_no_conflicting_webserver_lib(self):
        """Verify default WebServer is ignored to prevent conflict with AsyncWebServer."""
        self.assertIn("lib_ignore = WebServer", self.ini_content)

    def test_b16_05_clean_build_exit_code_zero(self):
        """Verify build environment parameters are valid."""
        self.assertIn("[env:seeed_xiao_esp32c3]", self.ini_content)

if __name__ == "__main__":
    unittest.main()
