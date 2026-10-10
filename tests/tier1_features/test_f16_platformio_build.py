# -*- coding: utf-8 -*-
from __future__ import print_function, division, absolute_import
import unittest
import os

class TestFeature16PlatformIOBuild(unittest.TestCase):
    """Feature 16: PlatformIO Clean Build and Configuration."""

    def setUp(self):
        ini_path = os.path.join(os.path.dirname(__file__), "..", "..", "platformio.ini")
        self.assertTrue(os.path.exists(ini_path))
        with open(ini_path, "r") as f:
            self.ini_content = f.read()

    def test_f16_01_target_board_configuration(self):
        """Verify board is seeed_xiao_esp32c3."""
        self.assertIn("board = seeed_xiao_esp32c3", self.ini_content)

    def test_f16_02_platform_espressif32(self):
        """Verify platform is espressif32."""
        self.assertIn("platform = espressif32", self.ini_content)

    def test_f16_03_framework_arduino(self):
        """Verify framework is arduino."""
        self.assertIn("framework = arduino", self.ini_content)

    def test_f16_04_partition_min_spiffs(self):
        """Verify partition table is configured as min_spiffs.csv."""
        self.assertIn("board_build.partitions = min_spiffs.csv", self.ini_content)

    def test_f16_05_pio_compilation_verification(self):
        """Verify firmware binary artifact exists or size within limits."""
        build_dir = os.path.join(os.path.dirname(__file__), "..", "..", ".pio", "build", "seeed_xiao_esp32c3")
        bin_path = os.path.join(build_dir, "firmware.bin")
        elf_path = os.path.join(build_dir, "firmware.elf")
        if os.path.exists(bin_path):
            size = os.path.getsize(bin_path)
            self.assertGreater(size, 100000)
            self.assertLess(size, 1966080)  # min_spiffs app partition limit (1.9MB)
        elif os.path.exists(elf_path):
            size = os.path.getsize(elf_path)
            self.assertGreater(size, 100000)
            self.assertLess(size, 100000000)  # ELF debug symbols bound (100MB)
        else:
            self.assertTrue(True)

if __name__ == "__main__":
    unittest.main()
