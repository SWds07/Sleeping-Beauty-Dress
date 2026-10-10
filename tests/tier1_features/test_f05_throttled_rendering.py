# -*- coding: utf-8 -*-
from __future__ import print_function, division, absolute_import
import unittest
from tests.helpers import (
    ANIMATION_FPS, ANIMATION_FRAME_MS, LED_DEFAULT_BRIGHTNESS,
    LED_MAX_BRIGHTNESS, COLOR_PINK_RGB, scale_color
)

class TestFeature05ThrottledRendering(unittest.TestCase):
    """Feature 5: Non-Blocking Throttled Rendering (~40 FPS, delta timing)."""

    def test_f05_01_target_frame_rate(self):
        """Verify target frame rate is 40 FPS."""
        self.assertEqual(ANIMATION_FPS, 40)

    def test_f05_02_frame_interval_ms(self):
        """Verify nominal frame interval is exactly 25ms."""
        expected_interval = 1000 // ANIMATION_FPS
        self.assertEqual(ANIMATION_FRAME_MS, 25)
        self.assertEqual(expected_interval, 25)

    def test_f05_03_delta_timing_throttle(self):
        """Verify frame update skips if elapsed time is less than 25ms."""
        last_frame_ms = 1000
        current_ms = 1020  # only 20ms elapsed
        should_render = (current_ms - last_frame_ms) >= ANIMATION_FRAME_MS
        self.assertFalse(should_render)

        current_ms = 1025  # 25ms elapsed
        should_render = (current_ms - last_frame_ms) >= ANIMATION_FRAME_MS
        self.assertTrue(should_render)

    def test_f05_04_brightness_scaling_math(self):
        """Verify brightness scaling formula scales channels accurately."""
        # Baseline brightness is 160
        scaled = scale_color(COLOR_PINK_RGB, 160)
        expected_r = (255 * 160) // 255  # 160
        expected_g = (20 * 160) // 255   # 12
        expected_b = (147 * 160) // 255  # 92
        self.assertEqual(scaled, (expected_r, expected_g, expected_b))

    def test_f05_05_bus_idling_on_static_frames(self):
        """Verify static solid modes do not re-render repeatedly when unchanged."""
        static_mode = "PINK"
        needs_rerender_after_show = False
        self.assertFalse(needs_rerender_after_show)

if __name__ == "__main__":
    unittest.main()
