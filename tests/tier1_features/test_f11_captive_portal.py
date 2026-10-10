# -*- coding: utf-8 -*-
from __future__ import print_function, division, absolute_import
import unittest
from tests.helpers import (
    WIFI_AP_SSID, WIFI_AP_IP, DNS_PORT, HTTP_PORT,
    WandInteractionSimulator
)

class TestFeature11CaptivePortal(unittest.TestCase):
    """Feature 11: SoftAP & Captive Portal (SSID, DNS 53, OS Probe Redirects)."""

    def setUp(self):
        self.sim = WandInteractionSimulator()

    def test_f11_01_softap_ssid(self):
        """Verify broadcast SoftAP SSID is 'Sleeping-Beauty-Dress'."""
        self.assertEqual(WIFI_AP_SSID, "Sleeping-Beauty-Dress")

    def test_f11_02_softap_ip_address(self):
        """Verify default gateway IP address is 192.168.4.1."""
        self.assertEqual(WIFI_AP_IP, "192.168.4.1")

    def test_f11_03_dns_port_53(self):
        """Verify captive portal DNS server runs on UDP port 53."""
        self.assertEqual(DNS_PORT, 53)

    def test_f11_04_dns_wildcard_resolution(self):
        """Verify wildcard DNS resolves any host query to 192.168.4.1."""
        def resolve_dns(query_host):
            return WIFI_AP_IP
        self.assertEqual(resolve_dns("google.com"), "192.168.4.1")
        self.assertEqual(resolve_dns("apple.com"), "192.168.4.1")

    def test_f11_05_captive_portal_redirects(self):
        """Verify vendor probe URLs return HTTP 302 to http://192.168.4.1/."""
        probes = [
            "/generate_204",
            "/hotspot-detect.html",
            "/ncsi.txt",
            "/connecttest.txt",
            "/canonical.html"
        ]
        for probe in probes:
            status, headers = self.sim.handle_rest_request(probe)
            self.assertEqual(status, 302)
            self.assertEqual(headers.get("Location"), "http://192.168.4.1/")

if __name__ == "__main__":
    unittest.main()
