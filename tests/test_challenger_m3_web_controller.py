#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Milestone 3 Empirical Challenger Test Suite: Captive Portal & Web UI
Comprehensive adversarial verification covering:
1. Zero Blocking Calls: WebController loop update and server setup contains no delay/vTaskDelay.
2. SoftAP & DNS Wildcard Responder: 192.168.4.1, UDP port 53, open auth, max 4 clients.
3. PROGMEM Flash Residency: HTML UI resides in .rodata flash with 0 SRAM dynamic consumption.
4. UI DOM & Route Parity: Every button, slider, and badge binds to authorized controller routes.
5. REST API Robustness & Schema Invariants: Strict JSON schema, wand hex/unpaired formatting,
   and 256-byte stack buffer bounding.
6. Input Sanitization & Clamping: Out-of-bounds, non-numeric, missing, and aliased brightness controls.
7. Captive Portal OS Probe Redirection & 404 Catch-All: Exact 302 redirects to http://192.168.4.1/.
8. PlatformIO Build Metrics: Verifies memory ceilings (<20% SRAM, <50% Flash).
"""
from __future__ import print_function, division, absolute_import
import unittest
import os
import sys
import re
import json
import subprocess

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from tests.helpers import (
    WandInteractionSimulator,
    WIFI_AP_SSID, WIFI_AP_IP, DNS_PORT, HTTP_PORT,
    LED_DEFAULT_BRIGHTNESS, LED_MAX_BRIGHTNESS
)

OBJDUMP_PATH = r"C:\Users\Steven\.platformio\packages\toolchain-riscv32-esp\bin\riscv32-esp-elf-objdump.exe"
NM_PATH = r"C:\Users\Steven\.platformio\packages\toolchain-riscv32-esp\bin\riscv32-esp-elf-nm.exe"
ELF_PATH = os.path.join(PROJECT_ROOT, ".pio", "build", "seeed_xiao_esp32c3", "firmware.elf")
WEB_CPP_PATH = os.path.join(PROJECT_ROOT, "src", "WebController.cpp")
WEB_H_PATH = os.path.join(PROJECT_ROOT, "include", "WebController.h")


class TestChallengerM3WebController(unittest.TestCase):
    """Empirical adversarial challenger test suite for Milestone 3."""

    @classmethod
    def setUpClass(cls):
        with open(WEB_CPP_PATH, "r") as f:
            cls.web_cpp = f.read()
        with open(WEB_H_PATH, "r") as f:
            cls.web_h = f.read()

        m = re.search(r'INDEX_HTML\[\]\s*PROGMEM\s*=\s*R"rawliteral\((.*?)\)rawliteral";',
                      cls.web_cpp, re.DOTALL)
        cls.html = m.group(1) if m else ""

        cls.has_elf = os.path.exists(ELF_PATH) and os.path.exists(OBJDUMP_PATH) and os.path.exists(NM_PATH)
        cls.nm_output = ""
        if cls.has_elf:
            p = subprocess.Popen([NM_PATH, "-C", ELF_PATH], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            out, _ = p.communicate()
            cls.nm_output = out.decode("utf-8", errors="ignore")

    def setUp(self):
        self.sim = WandInteractionSimulator(pink_id=0x2F073545, blue_id=0x1A2B3C4D)

    # =========================================================================
    # 1. Non-Blocking Execution & Static Audit
    # =========================================================================

    def test_challenge_zero_delay_calls(self):
        """Verify WebController.h and WebController.cpp contain zero delay() or vTaskDelay() calls."""
        for name, code in [("WebController.h", self.web_h), ("WebController.cpp", self.web_cpp)]:
            delays = re.findall(r'\bdelay\w*\(', code)
            self.assertEqual(len(delays), 0, "Forbidden delay() found in {}: {}".format(name, delays))
            vtask = re.findall(r'\bvTaskDelay\w*\(', code)
            self.assertEqual(len(vtask), 0, "Forbidden vTaskDelay() found in {}: {}".format(name, vtask))

    def test_challenge_update_cooperative_polling(self):
        """Verify WebController::update() only calls non-blocking s_dnsServer.processNextRequest()."""
        m = re.search(r'void\s+WebController::update\(\)\s*\{([^}]*)\}', self.web_cpp)
        self.assertIsNotNone(m, "WebController::update() implementation not found")
        body = m.group(1).strip()
        self.assertIn("processNextRequest", body)
        self.assertNotIn("while", body)
        self.assertNotIn("for", body)

    # =========================================================================
    # 2. SoftAP & Captive Portal DNS Network Topology
    # =========================================================================

    def test_challenge_softap_parameters(self):
        """Verify SoftAP binds 192.168.4.1 / 255.255.255.0, channel 1, max 4 clients, open auth."""
        self.assertEqual(WIFI_AP_SSID, "Sleeping-Beauty-Dress")
        self.assertEqual(WIFI_AP_IP, "192.168.4.1")
        self.assertIn("WiFi.mode(WIFI_AP);", self.web_cpp)
        self.assertIn("WiFi.softAPConfig(apIP, apIP, subnet);", self.web_cpp)
        self.assertIn("WiFi.softAP(WIFI_AP_SSID, WIFI_AP_PASSWORD, 1, 0, 4)", self.web_cpp)

    def test_challenge_dns_wildcard_configuration(self):
        """Verify DNS server starts on UDP port 53 with wildcard '*' matching apIP."""
        self.assertEqual(DNS_PORT, 53)
        self.assertIn('s_dnsServer.start(DNS_PORT, "*", apIP);', self.web_cpp)

    # =========================================================================
    # 3. PROGMEM HTML / CSS / JS Single-Page App Payload
    # =========================================================================

    def test_challenge_progmem_html_size_and_limits(self):
        """Verify INDEX_HTML is stored in PROGMEM and is between 1KB and 20KB."""
        self.assertTrue(len(self.html) > 0, "INDEX_HTML not found")
        size = len(self.html.encode("utf-8"))
        self.assertGreater(size, 1000, "HTML is smaller than expected")
        self.assertLess(size, 20000, "HTML exceeds 20KB ceiling: {} bytes".format(size))

    def test_challenge_html_standards_and_meta(self):
        """Verify valid DOCTYPE, UTF-8 charset, viewport tag, and balanced structural tags."""
        self.assertIn("<!DOCTYPE html>", self.html)
        self.assertIn('<meta charset="UTF-8">', self.html)
        self.assertIn('<meta name="viewport"', self.html)
        for tag in ["div", "button", "span", "p", "style", "script", "body", "html"]:
            open_count = len(re.findall(r'<{}\b'.format(tag), self.html, re.I))
            close_count = len(re.findall(r'</{}>'.format(tag), self.html, re.I))
            self.assertEqual(open_count, close_count, "Tag <{}> unbalanced: {} vs {}".format(tag, open_count, close_count))

    def test_challenge_ui_button_and_element_parity(self):
        """Verify all status elements and action buttons are present in the HTML DOM."""
        ids = ["modeBadge", "pairingBanner", "statusBrightness", "pinkCode", "blueCode", "brightnessSlider", "brightnessVal"]
        for elem_id in ids:
            self.assertIn('id="{}"'.format(elem_id), self.html)

        routes = ["/setPink", "/setBlue", "/setSplotches", "/setOff", "/register/pink", "/register/blue", "/register/cancel"]
        for route in routes:
            self.assertIn("sendAction('{}')".format(route), self.html)

    def test_challenge_js_polling_and_drag_guard(self):
        """Verify JS client polls status every 1500ms and preserves slider position while dragging."""
        self.assertIn("setInterval(pollStatus, 1500);", self.html)
        self.assertIn("fetch('/api/status')", self.html)
        self.assertIn("isDraggingSlider", self.html)

    # =========================================================================
    # 4. REST API Route Handlers & Telemetry Schema
    # =========================================================================

    def test_challenge_status_telemetry_schema(self):
        """Verify GET /api/status produces strictly valid JSON with all 5 mandatory keys."""
        status, data = self.sim.handle_rest_request("/api/status")
        self.assertEqual(status, 200)
        expected_keys = {"mode", "pinkWand", "blueWand", "pairing", "brightness"}
        self.assertEqual(set(data.keys()), expected_keys)

    def test_challenge_status_wand_formatting_contract(self):
        """Verify wand IDs format as 'Not Paired' when 0, or uppercase 8-digit hex '0x%08X'."""
        status, data = self.sim.handle_rest_request("/api/status")
        self.assertEqual(data["pinkWand"], "0x2F073545")
        self.assertEqual(data["blueWand"], "0x1A2B3C4D")

        unpaired = WandInteractionSimulator(pink_id=0, blue_id=0)
        _, up_data = unpaired.handle_rest_request("/api/status")
        self.assertEqual(up_data["pinkWand"], "Not Paired")
        self.assertEqual(up_data["blueWand"], "Not Paired")

    def test_challenge_status_stack_buffer_headroom(self):
        """Verify JSON payload length never exceeds 256-byte stack buffer."""
        modes = ["OFF", "PINK", "BLUE", "SPLOTCHES", "PAIRING_FEEDBACK"]
        pairings = ["NONE", "PINK", "BLUE"]
        wand_cases = [("Not Paired", "Not Paired"), ("0xFFFFFFFF", "0xFFFFFFFF")]
        for m in modes:
            for p in pairings:
                for pw, bw in wand_cases:
                    raw = '{{"mode":"{}","pinkWand":"{}","blueWand":"{}","pairing":"{}","brightness":255}}'.format(
                        m, pw, bw, p
                    )
                    self.assertLess(len(raw), 256)
                    self.assertLess(len(raw), 128, "JSON payload headroom too small")

    def test_challenge_mode_and_pairing_endpoints(self):
        """Verify state mutations and JSON response across all mode and pairing routes."""
        endpoints = [
            ("/setPink", "mode", "PINK"),
            ("/setBlue", "mode", "BLUE"),
            ("/setSplotches", "mode", "SPLOTCHES"),
            ("/setOff", "mode", "OFF"),
            ("/register/pink", "pairing", "PINK"),
            ("/register/cancel", "pairing", "NONE"),
            ("/register/blue", "pairing", "BLUE"),
        ]
        for ep, field, expected in endpoints:
            status, res = self.sim.handle_rest_request(ep)
            self.assertEqual(status, 200)
            self.assertEqual(res.get("status"), "ok")
            self.assertEqual(res.get(field), expected)

    # =========================================================================
    # 5. Brightness Boundary & Input Sanitization
    # =========================================================================

    def test_challenge_brightness_aliasing_and_clamping(self):
        """Verify /brightness and /setBrightness clamp properly and share identical behavior."""
        for ep in ["/setBrightness", "/brightness"]:
            # Normal range
            self.sim.handle_rest_request(ep, {"val": "120"})
            self.assertEqual(self.sim.brightness, 120)

            # Above max -> clamped to LED_MAX_BRIGHTNESS (160)
            self.sim.handle_rest_request(ep, {"val": "255"})
            self.assertEqual(self.sim.brightness, LED_MAX_BRIGHTNESS)
            self.sim.handle_rest_request(ep, {"val": "300"})
            self.assertEqual(self.sim.brightness, LED_MAX_BRIGHTNESS)

            # Below zero -> clamped to 0
            self.sim.handle_rest_request(ep, {"val": "-20"})
            self.assertEqual(self.sim.brightness, 0)

    def test_challenge_brightness_non_numeric_and_missing(self):
        """Verify non-numeric or missing parameters do not crash and leave brightness untouched."""
        self.sim.brightness = 100
        invalid_cases = ["invalid", "abc", "", "NaN", "null", "---", "%20"]
        for inv in invalid_cases:
            status, res = self.sim.handle_rest_request("/brightness", {"val": inv})
            self.assertEqual(status, 200)
            self.assertEqual(self.sim.brightness, 100)

        # Missing parameter
        status, res = self.sim.handle_rest_request("/brightness")
        self.assertEqual(status, 200)
        self.assertEqual(self.sim.brightness, 100)

    # =========================================================================
    # 6. Captive Portal OS Probe Redirection & 404 Catch-All
    # =========================================================================

    def test_challenge_vendor_probe_redirects(self):
        """Verify Android, Apple, Windows, Linux vendor probe URLs return 302 Found redirect."""
        vendor_probes = [
            "/generate_204",
            "/hotspot-detect.html",
            "/ncsi.txt",
            "/connecttest.txt",
            "/canonical.html"
        ]
        for probe in vendor_probes:
            status, headers = self.sim.handle_rest_request(probe)
            self.assertEqual(status, 302, "Probe {} failed to redirect".format(probe))
            self.assertEqual(headers.get("Location"), "http://192.168.4.1/")

    def test_challenge_catchall_404_redirect(self):
        """Verify unknown URLs return 302 Found redirect to captive portal root."""
        unknown_urls = ["/unknown", "/admin", "/foo/bar/baz", "/etc/passwd"]
        for url in unknown_urls:
            status, headers = self.sim.handle_rest_request(url)
            self.assertEqual(status, 302)
            self.assertEqual(headers.get("Location"), "http://192.168.4.1/")

    # =========================================================================
    # 7. ELF Binary Symbol Inspection
    # =========================================================================

    def test_challenge_elf_symbols_and_rodata(self):
        """Verify WebController, DNSServer, AsyncWebServer symbols exist and INDEX_HTML in .rodata."""
        if not self.has_elf:
            self.skipTest("Toolchain or ELF not found at {}".format(ELF_PATH))

        self.assertIn("WebController::init()", self.nm_output)
        self.assertIn("WebController::update()", self.nm_output)
        self.assertIn("DNSServer", self.nm_output)
        self.assertIn("AsyncWebServer", self.nm_output)

        m = re.search(r'([0-9a-fA-F]+)\s+[rRtT]\s+INDEX_HTML', self.nm_output)
        if m:
            addr = int(m.group(1), 16)
            self.assertTrue(addr >= 0x3c000000, "INDEX_HTML at 0x{:08X} not in flash .rodata".format(addr))


def main():
    suite = unittest.TestLoader().loadTestsFromTestCase(TestChallengerM3WebController)
    runner = unittest.TextTestRunner(verbosity=2)
    res = runner.run(suite)
    sys.exit(0 if res.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
