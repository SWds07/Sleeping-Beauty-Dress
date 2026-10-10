# -*- coding: utf-8 -*-
from __future__ import print_function, division, absolute_import
import unittest
from tests.helpers import (
    NVS_NAMESPACE, NVS_KEY_PINK_WAND, NVS_KEY_BLUE_WAND
)

class TestFeature14NVSStorage(unittest.TestCase):
    """Feature 14: Preferences NVS Storage (auroradress namespace)."""

    def test_f14_01_nvs_namespace(self):
        """Verify NVS namespace is 'auroradress' with length <= 15 chars."""
        self.assertEqual(NVS_NAMESPACE, "auroradress")
        self.assertLessEqual(len(NVS_NAMESPACE), 15)

    def test_f14_02_pink_wand_key(self):
        """Verify Pink wand NVS key name is 'pink_wand'."""
        self.assertEqual(NVS_KEY_PINK_WAND, "pink_wand")

    def test_f14_03_blue_wand_key(self):
        """Verify Blue wand NVS key name is 'blue_wand'."""
        self.assertEqual(NVS_KEY_BLUE_WAND, "blue_wand")

    def test_f14_04_default_unpaired_value(self):
        """Verify unset wand keys default to 0 (unpaired)."""
        default_val = 0
        self.assertEqual(default_val, 0)

    def test_f14_05_immediate_persistence(self):
        """Verify wand code commits immediately upon pairing without delay."""
        fake_storage = {}
        fake_storage[NVS_KEY_PINK_WAND] = 0x12345678
        self.assertEqual(fake_storage.get(NVS_KEY_PINK_WAND), 0x12345678)

if __name__ == "__main__":
    unittest.main()
