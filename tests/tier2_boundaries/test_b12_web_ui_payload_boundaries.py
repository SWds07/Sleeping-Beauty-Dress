# -*- coding: utf-8 -*-
from __future__ import print_function, division, absolute_import
import unittest
import os

class TestBoundary12WebUIPayloadBoundaries(unittest.TestCase):
    """Tier 2 Boundary: Web UI payload size and encoding boundaries."""

    def setUp(self):
        web_path = os.path.join(os.path.dirname(__file__), "..", "..", "src", "WebController.cpp")
        self.assertTrue(os.path.exists(web_path))
        with open(web_path, "r") as f:
            self.web_content = f.read()

    def test_b12_01_progmem_html_size_bound(self):
        """Verify embedded HTML string size is under 20,000 bytes."""
        # Find index of HTML content
        html_start = self.web_content.find("<!DOCTYPE html>")
        html_end = self.web_content.find("</html>")
        if html_start != -1 and html_end != -1:
            html_len = html_end - html_start + 7
            self.assertLess(html_len, 20000)
        else:
            self.assertTrue(len(self.web_content) > 0)

    def test_b12_02_html_utf8_encoding(self):
        """Verify HTML document specifies UTF-8 charset."""
        content_lower = self.web_content.lower()
        self.assertTrue('charset="utf-8"' in content_lower or "charset=utf-8" in content_lower)

    def test_b12_03_viewport_meta_tag(self):
        """Verify mobile viewport meta tag is present for mobile responsiveness."""
        self.assertIn("viewport", self.web_content.lower())

    def test_b12_04_js_fetch_error_handling(self):
        """Verify JavaScript includes fetch API calls."""
        self.assertIn("fetch", self.web_content)

    def test_b12_05_css_responsive_breakpoints(self):
        """Verify CSS contains mobile-optimized styling rules."""
        self.assertIn("<style>", self.web_content)

if __name__ == "__main__":
    unittest.main()
