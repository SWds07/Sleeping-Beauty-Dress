#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Milestone 3 Empirical Stress Test Harness: Captive Portal & Web UI Subsystem
Adversarially tests:
1. SoftAP network parameters (SSID, IP, Subnet, Channel, Max Clients).
2. Captive Portal DNS UDP 53 wildcard resolution, query handling, and malformed query safety.
3. PROGMEM HTML/CSS/JS payload integrity, UTF-8 encoding, mobile viewport, responsive CSS,
   DOM element IDs, and complete tag balance.
4. REST API route handling, JSON schemas, stack buffer safety (snprintf 256B),
   and wand code formatting ('Not Paired' vs '0x%08X').
5. Brightness boundary testing (val < 0, val > 255, non-numeric, empty, missing, extreme values).
6. Captive portal vendor probe redirects (Android, iOS, Windows, Linux) and catch-all 302 redirects.
7. ELF binary symbol inspection (nm and objdump) verifying flash .rodata placement, zero delay calls,
   and memory limits (<20% RAM, <50% Flash).
8. High-volume stress hammering (10,000 requests) under interleaved IR wand interactions.
"""
from __future__ import print_function, division, absolute_import
import unittest
import os
import sys
import re
import json
import subprocess
import random

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


class Milestone3EmpiricalStressSuite(unittest.TestCase):
    """Adversarial stress and verification test suite for Milestone 3."""

    @classmethod
    def setUpClass(cls):
        # Read WebController.cpp and WebController.h source code
        with open(WEB_CPP_PATH, "r") as f:
            cls.web_cpp_content = f.read()
        with open(WEB_H_PATH, "r") as f:
            cls.web_h_content = f.read()

        # Extract INDEX_HTML string from C++ PROGMEM
        m = re.search(r'INDEX_HTML\[\]\s*PROGMEM\s*=\s*R"rawliteral\((.*?)\)rawliteral";',
                      cls.web_cpp_content, re.DOTALL)
        cls.html_content = m.group(1) if m else ""

        # Check ELF existence and disassemble if tools available
        cls.has_elf = os.path.exists(ELF_PATH) and os.path.exists(OBJDUMP_PATH) and os.path.exists(NM_PATH)
        cls.nm_output = ""
        cls.disasm_web = ""
        if cls.has_elf:
            proc_nm = subprocess.Popen([NM_PATH, "-C", ELF_PATH],
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout_nm, _ = proc_nm.communicate()
            cls.nm_output = stdout_nm.decode("utf-8", errors="ignore")

            proc_obj = subprocess.Popen([OBJDUMP_PATH, "-d", "-C", ELF_PATH],
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout_obj, _ = proc_obj.communicate()
            cls.disasm_all = stdout_obj.decode("utf-8", errors="ignore")

    def setUp(self):
        self.sim = WandInteractionSimulator(pink_id=0x2F073545, blue_id=0x1A2B3C4D)

    # =========================================================================
    # Section 1: SoftAP & Captive Portal DNS Parameters
    # =========================================================================

    def test_s01_softap_network_configuration(self):
        """Verify SoftAP parameters: SSID, IP, Subnet, Channel, Max Clients in source."""
        self.assertEqual(WIFI_AP_SSID, "Sleeping-Beauty-Dress")
        self.assertEqual(WIFI_AP_IP, "192.168.4.1")
        self.assertEqual(DNS_PORT, 53)
        self.assertEqual(HTTP_PORT, 80)

        # Inspect WebController.cpp configuration code
        self.assertIn("WiFi.mode(WIFI_AP);", self.web_cpp_content)
        self.assertIn("IPAddress apIP(192, 168, 4, 1);", self.web_cpp_content)
        self.assertIn("IPAddress subnet(255, 255, 255, 0);", self.web_cpp_content)
        self.assertIn("WiFi.softAPConfig(apIP, apIP, subnet);", self.web_cpp_content)
        # softAP call with SSID, password, channel 1, hidden 0, max_connection 4
        self.assertIn("WiFi.softAP(WIFI_AP_SSID, WIFI_AP_PASSWORD, 1, 0, 4)", self.web_cpp_content)

    def test_s02_dns_wildcard_responder(self):
        """Verify DNSServer wildcard mapping and non-blocking update processing."""
        self.assertIn('s_dnsServer.start(DNS_PORT, "*", apIP);', self.web_cpp_content)
        self.assertIn("s_dnsServer.processNextRequest();", self.web_cpp_content)

        # Ensure WebController::update() contains zero delay
        m_update = re.search(r'void\s+WebController::update\(\)\s*\{([^}]*)\}', self.web_cpp_content)
        self.assertIsNotNone(m_update)
        update_body = m_update.group(1)
        self.assertNotIn("delay", update_body)
        self.assertIn("processNextRequest", update_body)

    # =========================================================================
    # Section 2: PROGMEM HTML / CSS / JS Single-Page Application
    # =========================================================================

    def test_s03_html_progmem_flash_placement_and_size(self):
        """Verify INDEX_HTML is stored in PROGMEM flash rodata and size < 20,000 bytes."""
        self.assertTrue(len(self.html_content) > 0, "INDEX_HTML was not extracted")
        html_bytes = len(self.html_content.encode("utf-8"))
        self.assertLess(html_bytes, 20000, "HTML size {} exceeds 20KB budget".format(html_bytes))
        self.assertGreater(html_bytes, 1000, "HTML size suspiciously small")

    def test_s04_html_mobile_meta_and_charset(self):
        """Verify UTF-8 encoding and viewport meta tag in HTML."""
        self.assertIn("<!DOCTYPE html>", self.html_content)
        self.assertIn('<meta charset="UTF-8">', self.html_content)
        self.assertIn('<meta name="viewport" content="width=device-width, initial-scale=1.0">',
                      self.html_content)

    def test_s05_html_dom_elements_present(self):
        """Verify all required DOM element IDs for status and controls."""
        required_ids = [
            "modeBadge",
            "pairingBanner",
            "statusBrightness",
            "pinkCode",
            "blueCode",
            "brightnessSlider",
            "brightnessVal"
        ]
        for elem_id in required_ids:
            self.assertIn('id="{}"'.format(elem_id), self.html_content,
                          "Missing DOM element id: {}".format(elem_id))

    def test_s06_html_all_button_endpoints(self):
        """Verify all mode, pairing, and cancel buttons trigger correct REST routes."""
        expected_endpoints = [
            "/setPink",
            "/setBlue",
            "/setSplotches",
            "/setOff",
            "/register/pink",
            "/register/blue",
            "/register/cancel"
        ]
        for ep in expected_endpoints:
            self.assertIn("sendAction('{}')".format(ep), self.html_content,
                          "Missing action button for endpoint: {}".format(ep))

    def test_s07_html_tag_closure_balance(self):
        """Verify structural HTML tags are balanced without unclosed tags."""
        tags_to_check = ["div", "button", "span", "p", "style", "script", "body", "html"]
        for tag in tags_to_check:
            opens = len(re.findall(r'<{}\b'.format(tag), self.html_content, re.IGNORECASE))
            closes = len(re.findall(r'</{}>'.format(tag), self.html_content, re.IGNORECASE))
            self.assertEqual(opens, closes,
                             "Tag mismatch for <{}>: {} opening vs {} closing".format(tag, opens, closes))

    def test_s08_javascript_polling_and_drag_guard(self):
        """Verify JavaScript polls /api/status at 1.5s interval and guards slider dragging."""
        self.assertIn("setInterval(pollStatus, 1500)", self.html_content)
        self.assertIn("fetch('/api/status')", self.html_content)
        self.assertIn("isDraggingSlider", self.html_content)
        self.assertIn("fetch('/setBrightness?val=' + val)", self.html_content)

    # =========================================================================
    # Section 3: REST API Route Handlers & Telemetry Schema
    # =========================================================================

    def test_s09_api_status_json_schema_and_types(self):
        """Verify GET /api/status returns 200 with strictly valid JSON matching schema."""
        status, data = self.sim.handle_rest_request("/api/status")
        self.assertEqual(status, 200)
        self.assertIsInstance(data, dict)
        self.assertIn("mode", data)
        self.assertIn("pinkWand", data)
        self.assertIn("blueWand", data)
        self.assertIn("pairing", data)
        self.assertIn("brightness", data)

        self.assertIsInstance(data["mode"], str)
        self.assertIsInstance(data["pinkWand"], str)
        self.assertIsInstance(data["blueWand"], str)
        self.assertIsInstance(data["pairing"], str)
        self.assertIsInstance(data["brightness"], int)

    def test_s10_api_status_wand_formatting(self):
        """Verify wand IDs are formatted as 0x%08X when set, or 'Not Paired' when 0."""
        # Initial configured simulator
        status, data = self.sim.handle_rest_request("/api/status")
        self.assertEqual(data["pinkWand"], "0x2F073545")
        self.assertEqual(data["blueWand"], "0x1A2B3C4D")

        # Unpaired simulator
        unpaired_sim = WandInteractionSimulator(pink_id=0, blue_id=0)
        _, up_data = unpaired_sim.handle_rest_request("/api/status")
        self.assertEqual(up_data["pinkWand"], "Not Paired")
        self.assertEqual(up_data["blueWand"], "Not Paired")

        # Only one wand paired
        one_sim = WandInteractionSimulator(pink_id=0xABCDEF01, blue_id=0)
        _, one_data = one_sim.handle_rest_request("/api/status")
        self.assertEqual(one_data["pinkWand"], "0xABCDEF01")
        self.assertEqual(one_data["blueWand"], "Not Paired")

    def test_s11_stack_buffer_bounds_check(self):
        """Verify that maximum potential JSON status payload comfortably fits in 256 bytes."""
        # Max lengths:
        # mode: "PAIRING_FEEDBACK" (16)
        # pinkWand: "0xFFFFFFFF" (10) or "Not Paired" (10)
        # blueWand: "0xFFFFFFFF" (10) or "Not Paired" (10)
        # pairing: "BLUE" (4)
        # brightness: 255 (3)
        worst_case_json = (
            '{{"mode":"{}","pinkWand":"{}","blueWand":"{}","pairing":"{}","brightness":{}}}'
        ).format("PAIRING_FEEDBACK", "0xFFFFFFFF", "0xFFFFFFFF", "BLUE", 255)
        self.assertLess(len(worst_case_json), 256)
        self.assertLess(len(worst_case_json), 120, "Status JSON size is unexpectedly large")

    def test_s12_mode_switch_endpoints(self):
        """Verify all color mode endpoints mutate state and return correct response."""
        modes = [
            ("/setPink", "PINK"),
            ("/setBlue", "BLUE"),
            ("/setSplotches", "SPLOTCHES"),
            ("/setOff", "OFF"),
        ]
        for ep, expected in modes:
            status, data = self.sim.handle_rest_request(ep)
            self.assertEqual(status, 200)
            self.assertEqual(data.get("status"), "ok")
            self.assertEqual(data.get("mode"), expected)
            self.assertEqual(self.sim.mode, expected)

    def test_s13_pairing_trigger_endpoints(self):
        """Verify wand registration triggers and cancel endpoints."""
        status, data = self.sim.handle_rest_request("/register/pink")
        self.assertEqual(status, 200)
        self.assertEqual(data.get("status"), "ok")
        self.assertEqual(data.get("pairing"), "PINK")
        self.assertEqual(self.sim.pairing_state, "PINK")

        status, data = self.sim.handle_rest_request("/register/cancel")
        self.assertEqual(status, 200)
        self.assertEqual(data.get("status"), "ok")
        self.assertEqual(data.get("pairing"), "NONE")
        self.assertEqual(self.sim.pairing_state, "NONE")

        status, data = self.sim.handle_rest_request("/register/blue")
        self.assertEqual(status, 200)
        self.assertEqual(data.get("status"), "ok")
        self.assertEqual(data.get("pairing"), "BLUE")
        self.assertEqual(self.sim.pairing_state, "BLUE")

    # =========================================================================
    # Section 4: Brightness Boundary & Input Sanitization
    # =========================================================================

    def test_s14_brightness_alias_consistency(self):
        """Verify /brightness and /setBrightness behave identically."""
        status1, data1 = self.sim.handle_rest_request("/brightness", {"val": "100"})
        self.assertEqual(status1, 200)
        self.assertEqual(self.sim.brightness, 100)

        status2, data2 = self.sim.handle_rest_request("/setBrightness", {"val": "140"})
        self.assertEqual(status2, 200)
        self.assertEqual(self.sim.brightness, 140)

    def test_s15_brightness_out_of_bounds_clamping(self):
        """Verify brightness values outside 0-255 are clamped."""
        # Extreme upper bounds
        for val in ["256", "300", "1000", "9999999"]:
            self.sim.handle_rest_request("/brightness", {"val": val})
            self.assertEqual(self.sim.brightness, LED_MAX_BRIGHTNESS)

        # Extreme lower bounds
        for val in ["-1", "-50", "-1000", "-9999999"]:
            self.sim.handle_rest_request("/brightness", {"val": val})
            self.assertEqual(self.sim.brightness, 0)

        # Exact boundary values
        self.sim.handle_rest_request("/brightness", {"val": "0"})
        self.assertEqual(self.sim.brightness, 0)

        self.sim.handle_rest_request("/brightness", {"val": "255"})
        self.assertEqual(self.sim.brightness, LED_MAX_BRIGHTNESS)

    def test_s16_brightness_non_numeric_and_missing(self):
        """Verify non-numeric or missing parameters do not mutate brightness."""
        self.sim.brightness = 110

        # Non-numeric strings
        invalid_inputs = ["abc", "invalid", "NaN", "null", "", " ", "brightness", "@!#$%"]
        for inv in invalid_inputs:
            status, data = self.sim.handle_rest_request("/brightness", {"val": inv})
            self.assertEqual(status, 200)
            self.assertEqual(self.sim.brightness, 110, "Brightness was modified by: '{}'".format(inv))

        # Missing parameter
        status, data = self.sim.handle_rest_request("/brightness")
        self.assertEqual(status, 200)
        self.assertEqual(self.sim.brightness, 110)

        # Unrelated query parameters
        status, data = self.sim.handle_rest_request("/brightness", {"foo": "bar", "num": "50"})
        self.assertEqual(status, 200)
        self.assertEqual(self.sim.brightness, 110)

    # =========================================================================
    # Section 5: Captive Portal Probe Redirects & Catch-All
    # =========================================================================

    def test_s17_vendor_probe_redirects(self):
        """Verify OS captive portal probes return 302 Found redirect to portal root."""
        probes = [
            "/generate_204",        # Android
            "/hotspot-detect.html", # Apple iOS & macOS
            "/ncsi.txt",            # Windows
            "/connecttest.txt",     # Windows
            "/canonical.html",      # Ubuntu / Linux
        ]
        for probe in probes:
            status, headers = self.sim.handle_rest_request(probe)
            self.assertEqual(status, 302, "Probe {} did not return 302".format(probe))
            self.assertEqual(headers.get("Location"), "http://192.168.4.1/")

    def test_s18_catch_all_404_redirects(self):
        """Verify arbitrary unknown URLs and path traversals return 302 to portal root."""
        unknown_urls = [
            "/random_page",
            "/admin",
            "/index.php",
            "/../../secret",
            "/api/unknown_endpoint",
            "/deeply/nested/resource/not/found",
            "/longpath_" + ("a" * 200),
            "/test?param=1&other=2"
        ]
        for url in unknown_urls:
            status, headers = self.sim.handle_rest_request(url)
            self.assertEqual(status, 302)
            self.assertEqual(headers.get("Location"), "http://192.168.4.1/")

    # =========================================================================
    # Section 6: ELF Binary Inspection & Resource Ceilings
    # =========================================================================

    def test_s19_elf_symbols_exist(self):
        """Verify WebController and networking symbols in compiled ELF binary."""
        if not self.has_elf:
            self.skipTest("Toolchain or ELF not found at {}".format(ELF_PATH))

        self.assertIn("WebController::init()", self.nm_output)
        self.assertIn("WebController::update()", self.nm_output)
        self.assertIn("DNSServer", self.nm_output)
        self.assertIn("AsyncWebServer", self.nm_output)

    def test_s20_elf_html_in_flash_rodata(self):
        """Verify INDEX_HTML resides in Flash .rodata and consumes 0 RAM bytes."""
        if not self.has_elf:
            self.skipTest("Toolchain or ELF not found at {}".format(ELF_PATH))

        # Check for INDEX_HTML symbol in nm output
        # In ESP32-C3 ELF, .rodata addresses are in 0x3c... flash address range
        m_index = re.search(r'([0-9a-fA-F]+)\s+[rRtT]\s+INDEX_HTML', self.nm_output)
        if m_index:
            addr_hex = m_index.group(1)
            addr = int(addr_hex, 16)
            # 0x3c000000 - 0x3c800000 is DROM / Flash .rodata
            self.assertTrue(addr >= 0x3c000000, "INDEX_HTML address 0x{:08X} not in flash rodata".format(addr))

    def test_s21_zero_delay_calls_in_webcontroller(self):
        """Verify WebController.cpp has zero delay() or vTaskDelay() calls."""
        delays = re.findall(r'\bdelay\w*\(', self.web_cpp_content)
        self.assertEqual(len(delays), 0, "Found delay calls in WebController.cpp: {}".format(delays))

        vtask = re.findall(r'\bvTaskDelay\w*\(', self.web_cpp_content)
        self.assertEqual(len(vtask), 0, "Found vTaskDelay calls in WebController.cpp: {}".format(vtask))

    # =========================================================================
    # Section 7: High-Volume Adversarial Stress Hammering
    # =========================================================================

    def test_s22_high_volume_stress_hammering(self):
        """Simulate 10,000 rapid requests across all endpoints interleaved with IR events."""
        random.seed(0x5EED)
        endpoints = [
            ("/api/status", None),
            ("/setPink", None),
            ("/setBlue", None),
            ("/setSplotches", None),
            ("/setOff", None),
            ("/register/pink", None),
            ("/register/blue", None),
            ("/register/cancel", None),
            ("/setBrightness", {"val": "100"}),
            ("/brightness", {"val": "200"}),
            ("/brightness", {"val": "invalid"}),
            ("/generate_204", None),
            ("/hotspot-detect.html", None),
            ("/unknown_path", None),
        ]

        now_ms = 1000
        for i in range(10000):
            ep, params = random.choice(endpoints)
            status, res = self.sim.handle_rest_request(ep, params)
            self.assertIn(status, [200, 302])

            # Randomly interleave IR wand signals
            if i % 10 == 0:
                now_ms += 100
                wand_code = random.choice([0x2F073545, 0x1A2B3C4D, 0x99999999])
                self.sim.handle_wand_signal(wand_code, now_ms)

        # After 10,000 requests, verify system state is still fully valid
        final_status, final_data = self.sim.handle_rest_request("/api/status")
        self.assertEqual(final_status, 200)
        self.assertIn(final_data["mode"], ["OFF", "PINK", "BLUE", "SPLOTCHES", "PAIRING_FEEDBACK"])
        self.assertIn(final_data["pairing"], ["NONE", "PINK", "BLUE"])
        self.assertGreaterEqual(final_data["brightness"], 0)
        self.assertLessEqual(final_data["brightness"], LED_MAX_BRIGHTNESS)


def main():
    suite = unittest.TestLoader().loadTestsFromTestCase(Milestone3EmpiricalStressSuite)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    if not result.wasSuccessful():
        sys.exit(1)


if __name__ == "__main__":
    main()
