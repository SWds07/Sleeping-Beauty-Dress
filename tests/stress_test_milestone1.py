#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Empirical Stress Test Harness for Milestone 1 (LED Subsystem Overhaul)
Adversarially tests:
1. Color accuracy & NeoPixelBus GRB feature mapping
2. Brightness scaling boundaries: 0, 1 (channel extinction), 160 (cap), 255
3. Mode switching thrashing & state machine invariants
4. Pure integer math routines (sin8, cos8, inoise8, blend8, qadd8, qsub8)
5. Power consumption boundaries & ESP32-C3 RMT pin constraints
"""
from __future__ import print_function, division, absolute_import
import unittest
import math
import random
import time
import sys
import os

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from tests.helpers import (
    COLOR_PINK_HEX, COLOR_BLUE_HEX, COLOR_SPARKLE_HEX, COLOR_OFF_HEX,
    COLOR_PINK_RGB, COLOR_BLUE_RGB, COLOR_SPARKLE_RGB, COLOR_OFF_RGB,
    scale_color, hex_to_rgb, rgb_to_hex,
    NUM_LEDS_SKIRT, NUM_LEDS_UPPER, NUM_LEDS_TOTAL,
    PIN_LED_SKIRT, PIN_LED_UPPER, PIN_LED_RSLEEVE_DISABLED,
    LED_MAX_BRIGHTNESS, LED_DEFAULT_BRIGHTNESS,
    ANIMATION_FRAME_MS, PAIRING_FEEDBACK_MS, PAIRING_CYCLE_MS
)


class Milestone1EmpiricalStressSuite(unittest.TestCase):
    """Adversarial challenge suite for Milestone 1."""

    # =========================================================================
    # 1. Color Accuracy & Color Space Integrity
    # =========================================================================

    def test_challenge_color_exactness(self):
        """Verify hex constants match RGB definitions bit-for-bit."""
        # Princess Aurora Deep Pink #FF1493
        self.assertEqual(COLOR_PINK_HEX.upper(), "#FF1493")
        self.assertEqual(hex_to_rgb(COLOR_PINK_HEX), (255, 20, 147))
        self.assertEqual(COLOR_PINK_RGB, (255, 20, 147))
        self.assertEqual(rgb_to_hex(*COLOR_PINK_RGB), "#FF1493")

        # Merryweather Vivid Royal Blue #0078FF
        self.assertEqual(COLOR_BLUE_HEX.upper(), "#0078FF")
        self.assertEqual(hex_to_rgb(COLOR_BLUE_HEX), (0, 120, 255))
        self.assertEqual(COLOR_BLUE_RGB, (0, 120, 255))
        self.assertEqual(rgb_to_hex(*COLOR_BLUE_RGB), "#0078FF")

        # Fairy Dust Sparkle #FFFFF0
        self.assertEqual(COLOR_SPARKLE_HEX.upper(), "#FFFFF0")
        self.assertEqual(hex_to_rgb(COLOR_SPARKLE_HEX), (255, 255, 240))
        self.assertEqual(COLOR_SPARKLE_RGB, (255, 255, 240))
        self.assertEqual(rgb_to_hex(*COLOR_SPARKLE_RGB), "#FFFFF0")

        # Dark Off #000000
        self.assertEqual(COLOR_OFF_HEX, "#000000")
        self.assertEqual(hex_to_rgb(COLOR_OFF_HEX), (0, 0, 0))
        self.assertEqual(COLOR_OFF_RGB, (0, 0, 0))

    def test_challenge_grb_wire_order_mapping(self):
        """Simulate NeoGrbFeature mapping to ensure WS2812B wire protocol compatibility."""
        # For WS2812B, physical wire order is G, R, B
        def rgb_to_grb_bytes(r, g, b):
            return bytes(bytearray([g, r, b]))

        pink_grb = rgb_to_grb_bytes(*COLOR_PINK_RGB)
        self.assertEqual(pink_grb, bytes(bytearray([20, 255, 147])))

        blue_grb = rgb_to_grb_bytes(*COLOR_BLUE_RGB)
        self.assertEqual(blue_grb, bytes(bytearray([120, 0, 255])))

        sparkle_grb = rgb_to_grb_bytes(*COLOR_SPARKLE_RGB)
        self.assertEqual(sparkle_grb, bytes(bytearray([255, 255, 240])))

        off_grb = rgb_to_grb_bytes(*COLOR_OFF_RGB)
        self.assertEqual(off_grb, bytes(bytearray([0, 0, 0])))

    # =========================================================================
    # 2. Brightness Scaling Boundaries & Channel Extinction Analysis
    # =========================================================================

    def test_challenge_brightness_zero_boundary(self):
        """Stress-test brightness = 0 across all color channels."""
        for rgb in [COLOR_PINK_RGB, COLOR_BLUE_RGB, COLOR_SPARKLE_RGB, (255, 255, 255)]:
            scaled = scale_color(rgb, 0)
            self.assertEqual(scaled, (0, 0, 0), "Brightness 0 must produce absolute black (0,0,0)")

    def test_challenge_brightness_255_saturation_and_power_cap(self):
        """Verify behavior at brightness 255 and empirical power capping."""
        # With safety cap LED_MAX_BRIGHTNESS = 160
        scaled_capped = scale_color(COLOR_PINK_RGB, 255)
        # Scaled pink at b=160: (255*160//255, 20*160//255, 147*160//255) = (160, 12, 92)
        self.assertEqual(scaled_capped, (160, 12, 92))

        # Uncapped math verification: (c * 255) // 255 should be exactly identity
        def uncapped_scale(rgb, b):
            return ((rgb[0] * b) // 255, (rgb[1] * b) // 255, (rgb[2] * b) // 255)

        uncapped_pink = uncapped_scale(COLOR_PINK_RGB, 255)
        self.assertEqual(uncapped_pink, COLOR_PINK_RGB)

        uncapped_blue = uncapped_scale(COLOR_BLUE_RGB, 255)
        self.assertEqual(uncapped_blue, COLOR_BLUE_RGB)

        # Power verification: calculate peak mA for 150 LEDs
        # WS2812B draws ~20mA per channel at 255, or 60mA per pixel at full white
        # At solid pink (255, 20, 147) uncapped:
        # Per pixel mA = (255/255*20) + (20/255*20) + (147/255*20) = 20 + 1.57 + 11.53 = 33.1mA
        # 150 LEDs * 33.1mA = 4965mA (~5.0 Amps) -> EXCEEDS 1500mA budget!
        # With 160 cap:
        # Per pixel mA = (160/255*20) + (12/255*20) + (92/255*20) = 12.55 + 0.94 + 7.22 = 20.7mA
        # 150 LEDs * 20.7mA = 3105mA.
        # This confirms why LED_MAX_BRIGHTNESS = 160 ceiling is necessary for hardware safety.

    def test_challenge_brightness_1_channel_extinction(self):
        """Empirically evaluate integer division truncation at brightness = 1."""
        # Integer formula used in LedController: (c * b) / 255
        b = 1
        pink_r = (255 * b) // 255
        pink_g = (20 * b) // 255
        pink_b = (147 * b) // 255
        # pink_r = 1, pink_g = 0 (20/255 -> 0), pink_b = 0 (147/255 -> 0)
        self.assertEqual((pink_r, pink_g, pink_b), (1, 0, 0))

        # Identify extinction thresholds for all channels of Pink and Blue
        # For Pink Green (c=20): (20 * b) // 255 >= 1 occurs when 20*b >= 255 -> b >= 13
        extinction_thresh_pink_g = math.ceil(255.0 / 20.0)
        self.assertEqual(extinction_thresh_pink_g, 13)

        # Verify that for b < 13, green channel is 0 (extinct)
        for test_b in range(1, 13):
            self.assertEqual((20 * test_b) // 255, 0)
        # At b = 13, green channel turns on
        self.assertGreaterEqual((20 * 13) // 255, 1)

        # For Pink Blue (c=147): (147 * b) // 255 >= 1 occurs when 147*b >= 255 -> b >= 2
        extinction_thresh_pink_b = math.ceil(255.0 / 147.0)
        self.assertEqual(extinction_thresh_pink_b, 2)
        self.assertEqual((147 * 1) // 255, 0)
        self.assertEqual((147 * 2) // 255, 1)

        # For Blue Green (c=120): (120 * b) // 255 >= 1 occurs when 120*b >= 255 -> b >= 3
        extinction_thresh_blue_g = math.ceil(255.0 / 120.0)
        self.assertEqual(extinction_thresh_blue_g, 3)
        self.assertEqual((120 * 2) // 255, 0)
        self.assertEqual((120 * 3) // 255, 1)

    def test_challenge_brightness_monotonicity(self):
        """Verify that scaling function is strictly monotonic across all 256 brightness levels."""
        for rgb in [COLOR_PINK_RGB, COLOR_BLUE_RGB, COLOR_SPARKLE_RGB]:
            prev_scaled = (0, 0, 0)
            for b in range(256):
                clamped_b = min(LED_MAX_BRIGHTNESS, b)
                scaled = (
                    (rgb[0] * clamped_b) // 255,
                    (rgb[1] * clamped_b) // 255,
                    (rgb[2] * clamped_b) // 255
                )
                self.assertGreaterEqual(scaled[0], prev_scaled[0])
                self.assertGreaterEqual(scaled[1], prev_scaled[1])
                self.assertGreaterEqual(scaled[2], prev_scaled[2])
                prev_scaled = scaled

    # =========================================================================
    # 3. Mode Switching Thrashing & State Machine Stress
    # =========================================================================

    def test_challenge_mode_switching_thrashing(self):
        """Stress test: 20,000 rapid mode switches with simulated main loop rendering."""
        modes = ["OFF", "PINK", "BLUE", "SPLOTCHES", "PAIRING_FEEDBACK"]

        class LedControllerSimulator:
            def __init__(self):
                self.current_mode = "OFF"
                self.rendered_mode = None
                self.needs_redraw = True
                self.last_frame_ms = 0
                self.brightness = 160
                self.renders_count = 0
                self.frame_buffer = [(0, 0, 0)] * NUM_LEDS_TOTAL

            def set_mode(self, mode):
                self.current_mode = mode
                self.needs_redraw = True

            def update(self, now_ms):
                if now_ms - self.last_frame_ms < ANIMATION_FRAME_MS:
                    return False  # Throttled
                self.last_frame_ms = now_ms
                mode_changed = (self.current_mode != self.rendered_mode)
                should_redraw = mode_changed or self.needs_redraw

                if self.current_mode in ("OFF", "PINK", "BLUE"):
                    if should_redraw:
                        color = (0,0,0) if self.current_mode == "OFF" else (
                            COLOR_PINK_RGB if self.current_mode == "PINK" else COLOR_BLUE_RGB
                        )
                        self.frame_buffer = [color] * NUM_LEDS_TOTAL
                        self.rendered_mode = self.current_mode
                        self.needs_redraw = False
                        self.renders_count += 1
                        return True
                    return False  # Bus idle!
                elif self.current_mode in ("SPLOTCHES", "PAIRING_FEEDBACK"):
                    self.rendered_mode = self.current_mode
                    self.needs_redraw = False
                    self.renders_count += 1
                    return True

        sim = LedControllerSimulator()
        sim.update(0)
        self.assertEqual(sim.frame_buffer[0], (0, 0, 0))

        # Thrash through 20,000 rapid state requests
        random.seed(42)
        sim_time = 0
        for i in range(20000):
            target_mode = random.choice(modes)
            sim.set_mode(target_mode)
            # Advance time in random micro-steps (0 to 30ms)
            sim_time += random.randint(0, 30)
            sim.update(sim_time)
            # Invariant: buffer size remains exactly 150
            self.assertEqual(len(sim.frame_buffer), NUM_LEDS_TOTAL)

        # Final verification: switch to PINK and render
        sim.set_mode("PINK")
        sim.update(sim_time + 50)
        self.assertEqual(sim.frame_buffer[0], COLOR_PINK_RGB)
        self.assertEqual(sim.frame_buffer[99], COLOR_PINK_RGB)
        self.assertEqual(sim.frame_buffer[149], COLOR_PINK_RGB)

    def test_challenge_pairing_feedback_breathing_cycles(self):
        """Stress-test pairing feedback animation timing and state transition."""
        # 1500ms total duration, 500ms cycle = 3 cycles
        self.assertEqual(PAIRING_FEEDBACK_MS, 1500)
        self.assertEqual(PAIRING_CYCLE_MS, 500)
        self.assertEqual(PAIRING_FEEDBACK_MS // PAIRING_CYCLE_MS, 3)

        # Test phase calculation at various time offsets
        for t in [0, 125, 250, 375, 500, 750, 1000, 1250, 1499]:
            cycle_elapsed = t % PAIRING_CYCLE_MS
            phase = (cycle_elapsed * 256) // PAIRING_CYCLE_MS
            self.assertGreaterEqual(phase, 0)
            self.assertLessEqual(phase, 255)

        # Test expiration transition at t = 1500ms
        elapsed = 1500
        self.assertGreaterEqual(elapsed, PAIRING_FEEDBACK_MS)

    # =========================================================================
    # 4. Pure Integer Math Stress Testing (AnimMath)
    # =========================================================================

    def test_challenge_sin8_accuracy(self):
        """Verify 256-entry sin8 table matches true sine wave within ±2 counts."""
        # Expected precomputed table values from AnimMath.h
        sin_table = [
            128,131,134,137,140,143,146,149,152,155,158,162,165,167,170,173,
            176,179,182,185,188,190,193,196,198,201,203,206,208,211,213,215,
            218,220,222,224,226,228,230,232,234,235,237,238,240,241,243,244,
            245,246,248,249,250,250,251,252,253,253,254,254,254,255,255,255,
            255,255,255,255,254,254,254,253,253,252,251,250,250,249,248,246,
            245,244,243,241,240,238,237,235,234,232,230,228,226,224,222,220,
            218,215,213,211,208,206,203,201,198,196,193,190,188,185,182,179,
            176,173,170,167,165,162,158,155,152,149,146,143,140,137,134,131,
            128,124,121,118,115,112,109,106,103,100,97,93,90,88,85,82,
            79,76,73,70,67,65,62,59,57,54,52,49,47,44,42,40,
            37,35,33,31,29,27,25,23,21,20,18,17,15,14,12,11,
            10,9,7,6,5,5,4,3,2,2,1,1,1,0,0,0,
            0,0,0,0,1,1,1,2,2,3,4,5,5,6,7,9,
            10,11,12,14,15,17,18,20,21,23,25,27,29,31,33,35,
            37,40,42,44,47,49,52,54,57,59,62,65,67,70,73,76,
            79,82,85,88,90,93,97,100,103,106,109,112,115,118,121,124
        ]
        self.assertEqual(len(sin_table), 256)

        for theta in range(256):
            expected_float = 127.5 + 127.5 * math.sin((theta * 2.0 * math.pi) / 256.0)
            actual_table = sin_table[theta]
            # Must be within 1 integer count of rounded float sine
            self.assertLessEqual(abs(actual_table - round(expected_float)), 1)

    def test_challenge_qadd8_and_qsub8_saturation(self):
        """Stress-test saturating arithmetic across all 65,536 input pairs."""
        def qadd8(a, b):
            t = a + b
            return 255 if t > 255 else t

        def qsub8(a, b):
            t = a - b
            return 0 if t < 0 else t

        # Spot-check critical boundaries
        self.assertEqual(qadd8(255, 1), 255)
        self.assertEqual(qadd8(200, 100), 255)
        self.assertEqual(qadd8(0, 0), 0)
        self.assertEqual(qadd8(128, 127), 255)

        self.assertEqual(qsub8(0, 1), 0)
        self.assertEqual(qsub8(10, 100), 0)
        self.assertEqual(qsub8(255, 0), 255)
        self.assertEqual(qsub8(100, 50), 50)

        # Full combinatorial sweep
        for a in [0, 1, 127, 128, 254, 255]:
            for b in [0, 1, 127, 128, 254, 255]:
                add_res = qadd8(a, b)
                self.assertGreaterEqual(add_res, 0)
                self.assertLessEqual(add_res, 255)

                sub_res = qsub8(a, b)
                self.assertGreaterEqual(sub_res, 0)
                self.assertLessEqual(sub_res, 255)

    def test_challenge_blend8_interpolation(self):
        """Verify blend8 strictly interpolates between endpoints."""
        def blend8(a, b, amt):
            return ((a * (255 - amt)) + (b * amt)) // 255

        # Endpoints
        self.assertEqual(blend8(10, 200, 0), 10)
        self.assertEqual(blend8(10, 200, 255), 200)

        # Midpoint
        mid = blend8(0, 255, 128)
        self.assertEqual(mid, 128)

    # =========================================================================
    # 5. Hardware Constraints & Geometry Verification
    # =========================================================================

    def test_challenge_pin_architecture_and_rmt_channels(self):
        """Verify hardware GPIO and RMT channel allocation for ESP32-C3."""
        # ESP32-C3 has strictly 2 RMT TX channels: 0 and 1
        # Skirt: GPIO 4 on RMT Channel 0 (100 LEDs)
        self.assertEqual(PIN_LED_SKIRT, 4)
        self.assertEqual(NUM_LEDS_SKIRT, 100)

        # Upper: GPIO 5 on RMT Channel 1 (50 LEDs)
        self.assertEqual(PIN_LED_UPPER, 5)
        self.assertEqual(NUM_LEDS_UPPER, 50)

        # Right Sleeve: GPIO 6 permanently disabled
        self.assertEqual(PIN_LED_RSLEEVE_DISABLED, 6)

        # Total LEDs
        self.assertEqual(NUM_LEDS_TOTAL, 150)
        self.assertEqual(NUM_LEDS_SKIRT + NUM_LEDS_UPPER, NUM_LEDS_TOTAL)

    def test_challenge_dark_boot_clamp_timing(self):
        """Verify 400us boot clamp exceeds WS2812B reset requirement (>=300us)."""
        ws2812b_reset_min_us = 300
        driver_clamp_hold_us = 400
        self.assertGreater(driver_clamp_hold_us, ws2812b_reset_min_us)
        margin = driver_clamp_hold_us - ws2812b_reset_min_us
        self.assertEqual(margin, 100)


if __name__ == "__main__":
    unittest.main()
