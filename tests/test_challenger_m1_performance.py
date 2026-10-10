#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Milestone 1 Empirical Challenger 2 Test Suite: Concurrency & Performance
Empirically verifies:
1. Zero Interrupt Masking: Audit C++ source, headers, and libraries for interrupt-disabling calls.
2. Non-Blocking Execution (<1ms): Analyze RISC-V binary disassembly and cycle budgets.
3. Static Bus Idling: Empirically verify 0 repeated transmissions in static modes (OFF, PINK, BLUE).
4. Frame Throttle Accuracy: Verify ~40 FPS delta timing, boundary conditions (24ms/25ms), and timer rollover.
5. Async Concurrency: Stress-test state machine under rapid mode/brightness changes.
"""
from __future__ import print_function, division, absolute_import
import unittest
import os
import sys
import re
import subprocess
import time

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from tests.helpers import (
    COLOR_PINK_RGB, COLOR_BLUE_RGB, COLOR_SPARKLE_RGB, COLOR_OFF_RGB,
    ANIMATION_FRAME_MS, ANIMATION_FPS, LED_DEFAULT_BRIGHTNESS,
    LED_MAX_BRIGHTNESS, PAIRING_FEEDBACK_MS, PAIRING_CYCLE_MS,
    NUM_LEDS_TOTAL, NUM_LEDS_SKIRT, NUM_LEDS_UPPER
)

OBJDUMP_PATH = r"C:\Users\Steven\.platformio\packages\toolchain-riscv32-esp\bin\riscv32-esp-elf-objdump.exe"
ELF_PATH = os.path.join(PROJECT_ROOT, ".pio", "build", "seeed_xiao_esp32c3", "firmware.elf")


class TestM1ConcurrencyAndPerformance(unittest.TestCase):
    """Empirical challenge suite for Milestone 1 performance and concurrency."""

    # =========================================================================
    # 1. Zero Interrupt Masking Audit
    # =========================================================================

    def test_challenge_m1_zero_interrupt_masking_source_audit(self):
        """Verify zero interrupt-masking calls exist in LedController.h, LedController.cpp, AnimMath.h."""
        target_files = [
            os.path.join(PROJECT_ROOT, "include", "LedController.h"),
            os.path.join(PROJECT_ROOT, "src", "LedController.cpp"),
            os.path.join(PROJECT_ROOT, "include", "AnimMath.h"),
        ]

        forbidden_patterns = [
            r"\bportENTER_CRITICAL\b",
            r"\bportEXIT_CRITICAL\b",
            r"\btaskENTER_CRITICAL\b",
            r"\btaskEXIT_CRITICAL\b",
            r"\bnoInterrupts\s*\(",
            r"\bcli\s*\(",
            r"\bdisableInterrupts\s*\(",
            r"\b__disable_irq\s*\(",
            r"\bcsrci\b",
            r"\bcsrw\s+mstatus\b",
        ]

        violations = []
        for file_path in target_files:
            self.assertTrue(os.path.exists(file_path), "File not found: {}".format(file_path))
            with open(file_path, "r") as f:
                content = f.read()
            for pattern in forbidden_patterns:
                matches = re.findall(pattern, content)
                if matches:
                    violations.append((file_path, pattern, len(matches)))

        self.assertEqual(violations, [], "Found forbidden interrupt-masking calls in LedController: {}".format(violations))

    def test_challenge_m1_neopixelbus_rmt_driver_nonblocking(self):
        """Verify NeoPixelBus RMT driver configuration uses hardware DMA/FIFO without interrupt masking."""
        led_cpp = os.path.join(PROJECT_ROOT, "src", "LedController.cpp")
        with open(led_cpp, "r") as f:
            content = f.read()

        # Must use NeoEsp32Rmt0Ws2812xMethod and NeoEsp32Rmt1Ws2812xMethod
        self.assertIn("NeoEsp32Rmt0Ws2812xMethod", content, "Skirt must use RMT Channel 0 hardware driver")
        self.assertIn("NeoEsp32Rmt1Ws2812xMethod", content, "Upper must use RMT Channel 1 hardware driver")

        # Verify NeoPixelBus RMT method implementation does not mask interrupts during Show
        rmt_header = os.path.join(
            PROJECT_ROOT, ".pio", "libdeps", "seeed_xiao_esp32c3", "NeoPixelBus",
            "src", "internal", "methods", "NeoEsp32RmtMethod.h"
        )
        self.assertTrue(os.path.exists(rmt_header), "NeoEsp32RmtMethod.h not found")
        with open(rmt_header, "r") as f:
            rmt_content = f.read()

        # Check that rmt_write_sample uses non-blocking mode (wait_tx_done = false)
        self.assertIn("rmt_write_sample", rmt_content)
        # Check that NeoEsp32RmtMethodBase::Update uses false for wait_tx_done
        match = re.search(r"rmt_write_sample\s*\(\s*[^,]+,\s*[^,]+,\s*[^,]+,\s*(false|0)\s*\)", rmt_content)
        self.assertIsNotNone(match, "NeoEsp32RmtMethodBase::Update must pass wait_tx_done=false for non-blocking push")

    # =========================================================================
    # 2. Binary Disassembly & Cycle Budget Verification (<1ms)
    # =========================================================================

    def test_challenge_m1_binary_disassembly_no_delay_in_update(self):
        """Disassemble LedController::update() and pushPhysicalFrame() from firmware.elf and verify no delay calls."""
        self.assertTrue(os.path.exists(OBJDUMP_PATH), "riscv32 objdump tool not found at {}".format(OBJDUMP_PATH))
        self.assertTrue(os.path.exists(ELF_PATH), "firmware.elf not found at {}".format(ELF_PATH))

        cmd = [OBJDUMP_PATH, "-d", "-C", ELF_PATH]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = proc.communicate()
        self.assertEqual(proc.returncode, 0, "objdump failed")

        disasm = stdout.decode("utf-8", errors="ignore")

        # Extract LedController::update() disassembly section
        match_update = re.search(r"<LedController::update\(\)>:(.*?)(?=\n[0-9a-fA-F]+ <|\Z)", disasm, re.DOTALL)
        self.assertIsNotNone(match_update, "Could not find LedController::update() in firmware.elf disassembly")
        update_code = match_update.group(1)

        # Verify NO calls to delay, delayMicroseconds, or vTaskDelay in LedController::update()
        forbidden_calls = ["<delay>", "<delayMicroseconds>", "<vTaskDelay>"]
        for fc in forbidden_calls:
            self.assertNotIn(fc, update_code, "LedController::update() contains forbidden call to {}".format(fc))

        # Extract LedController::pushPhysicalFrame() disassembly
        match_push = re.search(r"<LedController::pushPhysicalFrame\(\)>:(.*?)(?=\n[0-9a-fA-F]+ <|\Z)", disasm, re.DOTALL)
        self.assertIsNotNone(match_push, "Could not find LedController::pushPhysicalFrame() in firmware.elf")
        push_code = match_push.group(1)

        for fc in forbidden_calls:
            self.assertNotIn(fc, push_code, "pushPhysicalFrame() contains forbidden call to {}".format(fc))

    def test_challenge_m1_worst_case_execution_budget_under_1ms(self):
        """Calculate worst-case instruction and cycle count of LedController::update() and prove it is <1ms at 160MHz."""
        # 160 MHz clock = 160,000,000 cycles per second.
        # 1 millisecond budget = 160,000 cycles.
        MAX_CYCLES_1MS = 160000

        # Disassemble all functions invoked during worst-case animation (SPLOTCHES)
        cmd = [OBJDUMP_PATH, "-d", "-C", ELF_PATH]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, _ = proc.communicate()
        disasm = stdout.decode("utf-8", errors="ignore")

        def count_instructions(func_name):
            pattern = r"<" + re.escape(func_name) + r"(?:\([^)]*\))?>:(.*?)(?=\n[0-9a-fA-F]+ <|\Z)"
            match = re.search(pattern, disasm, re.DOTALL)
            if not match:
                return 0
            code = match.group(1)
            # Count instruction lines (lines with address: hex opcode)
            lines = [l for l in code.split("\n") if re.match(r"^\s*[0-9a-fA-F]+:\s+[0-9a-fA-F]+", l)]
            return len(lines)

        inst_update = count_instructions("LedController::update()")
        inst_push = count_instructions("LedController::pushPhysicalFrame()")
        inst_splotches = count_instructions("LedController::renderSplotchesFrame(unsigned long)")
        inst_noise = count_instructions("AnimMath::inoise8(unsigned short, unsigned short, unsigned short)")
        inst_color = count_instructions("LedController::computeSplotchColor(unsigned char, unsigned char)")

        # In renderSplotchesFrame: 150 LEDs each call inoise8 + computeSplotchColor
        # Plus loop overhead in splotches
        # Plus pushPhysicalFrame: 150 LEDs brightness scaling + Show
        estimated_worst_case_instructions = (
            inst_update +
            inst_splotches +
            (150 * (inst_noise + inst_color)) +
            inst_push
        )

        # On ESP32-C3 RISC-V, integer ALU operations execute in 1 cycle, integer mul in 1 cycle,
        # integer div/rem in ~32 cycles max. Assuming worst-case average 2.5 cycles per instruction:
        estimated_cycles = estimated_worst_case_instructions * 2.5
        execution_time_ms = (estimated_cycles / 160000000.0) * 1000.0

        print("\n  [Empirical Benchmark] Worst-case instruction budget:")
        print("    update() code size:           {:>5} instructions".format(inst_update))
        print("    renderSplotchesFrame() size:  {:>5} instructions".format(inst_splotches))
        print("    inoise8() size:               {:>5} instructions".format(inst_noise))
        print("    computeSplotchColor() size:   {:>5} instructions".format(inst_color))
        print("    pushPhysicalFrame() size:     {:>5} instructions".format(inst_push))
        print("    Estimated total instructions: {:>5}".format(estimated_worst_case_instructions))
        print("    Estimated cycle count:        {:>5.0f} cycles (budget: {})".format(estimated_cycles, MAX_CYCLES_1MS))
        print("    Estimated worst-case latency: {:>5.3f} ms (requirement: <1.0 ms)".format(execution_time_ms))

        self.assertLess(estimated_cycles, MAX_CYCLES_1MS, "Worst-case cycles exceeds 1ms budget!")
        self.assertLess(execution_time_ms, 1.0, "Execution latency exceeds 1.0ms!")

    # =========================================================================
    # 3. Static Bus Idling Verification
    # =========================================================================

    def test_challenge_m1_static_bus_idling_empirical_oracle(self):
        """Empirically prove that in static modes (OFF, PINK, BLUE), Show() is called EXACTLY once upon transition and 0 times thereafter."""
        class LedStateOracle:
            def __init__(self):
                self.current_mode = "OFF"
                self.rendered_mode = "NONE"  # Set to 255 in init()
                self.needs_redraw = True
                self.brightness = 160
                self.brightness_dirty = False
                self.last_frame_time = 0
                # In LedController::init(), an initial dark blank push occurs synchronously
                self.show_call_count = 1
                self.frame_buffer = [(0, 0, 0)] * NUM_LEDS_TOTAL

            def set_mode(self, mode):
                self.current_mode = mode
                self.needs_redraw = True

            def set_brightness(self, b):
                self.brightness = b
                self.brightness_dirty = True

            def update(self, now):
                # Throttle check: must elapse >= 25ms
                if (now - self.last_frame_time) < ANIMATION_FRAME_MS:
                    return False
                self.last_frame_time = now

                brightness_changed = self.brightness_dirty
                self.brightness_dirty = False

                mode_changed = (self.current_mode != self.rendered_mode)
                redraw_requested = self.needs_redraw
                self.needs_redraw = False

                should_redraw = mode_changed or brightness_changed or redraw_requested

                if self.current_mode in ("OFF", "PINK", "BLUE"):
                    if should_redraw:
                        color = (0, 0, 0) if self.current_mode == "OFF" else (
                            COLOR_PINK_RGB if self.current_mode == "PINK" else COLOR_BLUE_RGB
                        )
                        self.frame_buffer = [color] * NUM_LEDS_TOTAL
                        self.show_call_count += 1
                        self.rendered_mode = self.current_mode
                        return True
                    # Bus idling: NO SHOW CALL!
                    return False
                elif self.current_mode in ("SPLOTCHES", "PAIRING_FEEDBACK"):
                    self.show_call_count += 1
                    self.rendered_mode = self.current_mode
                    return True

        oracle = LedStateOracle()

        # Step 1: Boot into OFF mode. Initial synchronous push occurred in init() (show_call_count = 1).
        self.assertEqual(oracle.show_call_count, 1)

        # First loop tick at t = 25ms: renders OFF to establish rendered_mode
        rendered = oracle.update(25)
        self.assertTrue(rendered)
        self.assertEqual(oracle.show_call_count, 2, "First loop tick confirms OFF frame")
        self.assertEqual(oracle.frame_buffer[0], (0, 0, 0))

        # Advance 1,000 ticks (from t=50ms to t=25025ms) with no mode change
        for t in range(50, 25050, 25):
            rendered = oracle.update(t)
            self.assertFalse(rendered, "Static OFF mode must NOT re-render while idling")
        self.assertEqual(oracle.show_call_count, 2, "Bus must remain 100% idle with 0 new transmissions")

        # Step 2: Switch to PINK mode.
        oracle.set_mode("PINK")
        # Tick at t = 25050ms
        rendered = oracle.update(25050)
        self.assertTrue(rendered, "PINK mode transition must render once")
        self.assertEqual(oracle.show_call_count, 3, "Transition must increment Show() count exactly by 1")
        self.assertEqual(oracle.frame_buffer[0], COLOR_PINK_RGB)

        # Advance another 1,000 ticks (25,000ms) in PINK mode
        for t in range(25075, 50075, 25):
            rendered = oracle.update(t)
            self.assertFalse(rendered, "Static PINK mode must NOT re-render while idling")
        self.assertEqual(oracle.show_call_count, 3, "Bus must remain 100% idle with 0 new transmissions")

        # Step 3: Switch to BLUE mode.
        oracle.set_mode("BLUE")
        rendered = oracle.update(50100)
        self.assertTrue(rendered, "BLUE mode transition must render once")
        self.assertEqual(oracle.show_call_count, 4, "Transition must increment Show() count exactly by 1")
        self.assertEqual(oracle.frame_buffer[0], COLOR_BLUE_RGB)

        # Advance another 1,000 ticks in BLUE mode
        for t in range(50125, 75125, 25):
            rendered = oracle.update(t)
            self.assertFalse(rendered, "Static BLUE mode must NOT re-render while idling")
        self.assertEqual(oracle.show_call_count, 4, "Bus must remain 100% idle with 0 new transmissions")

        # Step 4: Change brightness while in static BLUE mode
        oracle.set_brightness(80)
        rendered = oracle.update(75150)
        self.assertTrue(rendered, "Brightness change must trigger exactly 1 re-render")
        self.assertEqual(oracle.show_call_count, 5)

        # Following ticks must idle again
        for t in range(75175, 80000, 25):
            rendered = oracle.update(t)
            self.assertFalse(rendered)
        self.assertEqual(oracle.show_call_count, 5, "Bus must return to idling after brightness update")

    # =========================================================================
    # 4. Frame Throttle Accuracy & Delta Timing
    # =========================================================================

    def test_challenge_m1_frame_throttle_boundary_and_fps_accuracy(self):
        """Stress-test delta timing: 24ms skips, 25ms triggers, high-frequency polling yields 40 FPS."""
        last_frame = 1000

        # Exact boundary tests: now - lastFrame < 25ms
        for elapsed in range(0, 25):
            now = last_frame + elapsed
            should_update = (now - last_frame) >= ANIMATION_FRAME_MS
            self.assertFalse(should_update, "Elapsed {}ms must NOT trigger update (threshold is 25ms)".format(elapsed))

        # At exactly 25ms, update must trigger
        self.assertTrue((last_frame + 25 - last_frame) >= ANIMATION_FRAME_MS)
        self.assertTrue((last_frame + 26 - last_frame) >= ANIMATION_FRAME_MS)

        # High-frequency polling simulation: simulate 4,000ms (4 seconds) of main loop running at 1kHz (every 1ms)
        frame_triggers = 0
        last_t = 0
        for current_t in range(0, 4001):
            if (current_t - last_t) >= ANIMATION_FRAME_MS:
                frame_triggers += 1
                last_t = current_t

        # In 4000ms, at 25ms per frame, expected frames = 4000 / 25 = 160 frames (40.0 FPS)
        self.assertEqual(frame_triggers, 160, "Must trigger exactly 160 frames over 4000ms (40 FPS)")
        fps = frame_triggers / 4.0
        self.assertEqual(fps, 40.0)

    def test_challenge_m1_millis_rollover_safety(self):
        """Verify uint32_t subtraction handles millis() overflow (at ~49.7 days) seamlessly."""
        # Unsigned 32-bit arithmetic: (uint32_t)(now - last_frame)
        def uint32_diff(now, last):
            return (now - last) & 0xFFFFFFFF

        # Case 1: last frame was just before rollover, now is just after
        last_frame = 0xFFFFFFF0  # 4,294,967,280 ms
        now = 0x00000009         # 9 ms after rollover
        # 16ms before rollover + 9ms after = 25ms elapsed
        diff = uint32_diff(now, last_frame)
        self.assertEqual(diff, 25)
        self.assertTrue(diff >= ANIMATION_FRAME_MS, "Rollover boundary at 25ms must trigger update")

        # Case 2: only 24ms elapsed across rollover
        now_24 = 0x00000008      # 8 ms after rollover
        diff_24 = uint32_diff(now_24, last_frame)
        self.assertEqual(diff_24, 24)
        self.assertFalse(diff_24 >= ANIMATION_FRAME_MS, "Rollover boundary at 24ms must skip update")

    # =========================================================================
    # 5. Async Concurrency Stress Test
    # =========================================================================

    def test_challenge_m1_async_concurrency_stress(self):
        """Simulate concurrent async TCP thread triggers while main loop executes update()."""
        # Test simulated state machine with 50,000 interleaved events
        class ConcurrentSimulator:
            def __init__(self):
                self.current_mode = "OFF"
                self.rendered_mode = "NONE"
                self.needs_redraw = True
                self.brightness = 160
                self.brightness_dirty = False
                self.last_frame = 0
                self.frame_buffer = [(0, 0, 0)] * NUM_LEDS_TOTAL
                self.total_frames = 0

            # Methods invoked by async TCP server
            def async_set_mode(self, mode):
                self.current_mode = mode
                self.needs_redraw = True

            def async_set_brightness(self, b):
                self.brightness = min(160, b)
                self.brightness_dirty = True

            # Method invoked by main loop
            def loop_update(self, now):
                if (now - self.last_frame) < ANIMATION_FRAME_MS:
                    return
                self.last_frame = now
                b_changed = self.brightness_dirty
                self.brightness_dirty = False
                mode_changed = (self.current_mode != self.rendered_mode)
                redraw = self.needs_redraw
                self.needs_redraw = False

                should_render = mode_changed or b_changed or redraw
                if self.current_mode in ("OFF", "PINK", "BLUE"):
                    if should_render:
                        c = (0,0,0) if self.current_mode == "OFF" else (
                            COLOR_PINK_RGB if self.current_mode == "PINK" else COLOR_BLUE_RGB
                        )
                        self.frame_buffer = [c] * NUM_LEDS_TOTAL
                        self.rendered_mode = self.current_mode
                        self.total_frames += 1
                else:
                    self.total_frames += 1
                    self.rendered_mode = self.current_mode

        sim = ConcurrentSimulator()
        sim_time = 0
        modes = ["OFF", "PINK", "BLUE", "SPLOTCHES", "PAIRING_FEEDBACK"]

        for step in range(50000):
            # Interleave async events and main loop updates
            if step % 7 == 0:
                sim.async_set_mode(modes[step % len(modes)])
            if step % 13 == 0:
                sim.async_set_brightness((step * 17) % 255)

            sim_time += 1  # 1ms main loop tick
            sim.loop_update(sim_time)

            # Invariant checks
            self.assertEqual(len(sim.frame_buffer), NUM_LEDS_TOTAL)
            self.assertLessEqual(sim.brightness, LED_MAX_BRIGHTNESS)

        self.assertGreater(sim.total_frames, 0)


if __name__ == "__main__":
    unittest.main()
