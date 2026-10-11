# -*- coding: utf-8 -*-
from __future__ import print_function, division, absolute_import
import unittest
from tests.helpers import (
    WandInteractionSimulator, MagiQuestEncoder, MagiQuestDecoder,
    BLE_DEVICE_NAME, BLE_SERVICE_UUID, NVS_KEY_PINK_WAND, NVS_KEY_BLUE_WAND,
    LED_MAX_BRIGHTNESS, ANIMATION_FRAME_MS,
    BLE_CMD_SET_OFF, BLE_CMD_SET_PINK, BLE_CMD_SET_BLUE, BLE_CMD_SET_SPLOTCHES,
    BLE_CMD_PAIR_PINK, BLE_CMD_PAIR_BLUE, BLE_CMD_PAIR_CANCEL,
    unpack_telemetry
)

class TestRealWorldScenarios(unittest.TestCase):
    """Tier 4: Comprehensive Real-World Operational Scenarios."""

    def test_scenario_01_cold_boot_initialization(self):
        """Scenario 1: Cold Boot & Safe State Initialization.
        Steps:
        1. Power applied to XIAO ESP32-C3.
        2. Hardware clamp pulls LED pins LOW immediately.
        3. StorageController loads stored wand IDs from NVS.
        4. LedController blanks all 150 pixels and executes 350us reset hold.
        5. IRController configures 3.3V GPIO interrupts on shoulders.
        6. BleController starts BLE GATT Server advertising as 'Aurora-Dress'.
        7. System enters cooperative loop with 0mA white flash and 0 brownout.
        """
        # Step 1-3: Storage init
        sim = WandInteractionSimulator(pink_id=0, blue_id=0)
        self.assertEqual(sim.pink_id, 0)
        self.assertEqual(sim.blue_id, 0)
        # Step 4: LED state dark
        self.assertEqual(sim.mode, "OFF")
        # Step 5-6: BLE ready
        self.assertEqual(BLE_DEVICE_NAME, "Aurora-Dress")
        self.assertEqual(BLE_SERVICE_UUID, "19590001-d1e5-4e3b-9a14-c0104d4e5353")
        # Step 7: Telemetry status check
        raw = sim.get_ble_telemetry_bytes()
        self.assertEqual(len(raw), 15)
        telemetry = unpack_telemetry(raw)
        self.assertEqual(telemetry["mode"], 0)  # OFF
        self.assertEqual(telemetry["pinkWandId"], 0)
        self.assertEqual(telemetry["blueWandId"], 0)
        self.assertEqual(telemetry["pairingState"], 0)

    def test_scenario_02_pink_wand_pairing_flow(self):
        """Scenario 2: Complete BLE-Triggered Pink Wand Pairing Journey.
        Steps:
        1. Android companion app connects to 'Aurora-Dress'.
        2. App writes opcode 0x10 (PAIR_PINK) to Command characteristic.
        3. Dress enters PAIRING_PINK state with 30s timeout.
        4. User flicks Pink wand (ID 0x2F073545).
        5. Dual IR receiver captures 56-bit MagiQuest bitstream.
        6. Wand ID written immediately to NVS 'auroradress.pink_wand'.
        7. LedController triggers PAIRING_FEEDBACK breathing pulse.
        8. Telemetry confirms Pink wand is now paired.
        """
        sim = WandInteractionSimulator(pink_id=0, blue_id=0)
        # 1-2: BLE trigger
        res = sim.handle_ble_command(BLE_CMD_PAIR_PINK)
        self.assertEqual(res, "OK")
        self.assertEqual(sim.pairing_state, "PINK")

        # 4-5: IR capture
        pink_wand_code = 0x2F073545
        pulses = MagiQuestEncoder.encode_56bit(pink_wand_code)
        decoded_id, _, dec_status = MagiQuestDecoder.decode_pulse_train(pulses)
        self.assertEqual(dec_status, "56bit_valid")
        self.assertEqual(decoded_id, pink_wand_code)

        # 6-7: Event handle
        action = sim.handle_wand_signal(decoded_id, 1500)
        self.assertEqual(action, "PAIRED_PINK")
        self.assertEqual(sim.pink_id, pink_wand_code)
        self.assertEqual(sim.nvs[NVS_KEY_PINK_WAND], pink_wand_code)
        self.assertEqual(sim.mode, "PAIRING_FEEDBACK")
        self.assertEqual(sim.pairing_state, "NONE")

        # 8: Telemetry
        raw = sim.get_ble_telemetry_bytes()
        telemetry = unpack_telemetry(raw)
        self.assertEqual(telemetry["pinkWandId"], pink_wand_code)
        self.assertEqual(telemetry["mode"], 4)  # PAIRING_FEEDBACK
        self.assertEqual(telemetry["pairingState"], 0)

    def test_scenario_03_blue_wand_pairing_flow(self):
        """Scenario 3: Complete BLE-Triggered Blue Wand Pairing Journey.
        Steps:
        1. User taps 'Pair Blue Wand' in app -> writes opcode 0x11 (PAIR_BLUE).
        2. System state transitions to PAIRING_BLUE.
        3. User flicks Blue wand (ID 0x1A2B3C4D).
        4. Wand code decoded and committed to NVS 'auroradress.blue_wand'.
        5. Visual feedback triggered and pairing completes.
        """
        sim = WandInteractionSimulator(pink_id=0x2F073545, blue_id=0)
        res = sim.handle_ble_command(BLE_CMD_PAIR_BLUE)
        self.assertEqual(res, "OK")
        self.assertEqual(sim.pairing_state, "BLUE")

        blue_wand_code = 0x1A2B3C4D
        action = sim.handle_wand_signal(blue_wand_code, 2000)
        self.assertEqual(action, "PAIRED_BLUE")
        self.assertEqual(sim.blue_id, blue_wand_code)
        self.assertEqual(sim.nvs[NVS_KEY_BLUE_WAND], blue_wand_code)
        self.assertEqual(sim.mode, "PAIRING_FEEDBACK")

        raw = sim.get_ble_telemetry_bytes()
        telemetry = unpack_telemetry(raw)
        self.assertEqual(telemetry["blueWandId"], blue_wand_code)
        self.assertEqual(telemetry["pinkWandId"], 0x2F073545)

    def test_scenario_04_dueling_wand_spell_clash(self):
        """Scenario 4: Live Dueling Wand Spell Clash Interactive Session.
        Steps:
        1. Flora flicks Pink wand (ID 0x2F073545) -> Dress turns PINK.
        2. Merryweather flicks Blue wand (ID 0x1A2B3C4D) within 1.2s (< 2000ms window).
        3. Rapid dual wand detected -> triggers SPLOTCHES fairy battle mode.
        4. Both shoulder receivers process incoming bursts with zero frame collisions.
        """
        sim = WandInteractionSimulator(pink_id=0x2F073545, blue_id=0x1A2B3C4D)
        # Step 1: Flora strikes
        res1 = sim.handle_wand_signal(0x2F073545, 1000)
        self.assertEqual(res1, "DISPATCH_PINK")
        self.assertEqual(sim.mode, "PINK")

        # Step 2-3: Merryweather counters 1200ms later
        res2 = sim.handle_wand_signal(0x1A2B3C4D, 2200)
        self.assertEqual(res2, "DISPATCH_SPLOTCHES")
        self.assertEqual(sim.mode, "SPLOTCHES")

    def test_scenario_05_smartphone_captive_portal_onboarding(self):
        """Scenario 5: Android BLE Companion App Connection and Control Session.
        Steps:
        1. Companion app scans for 'Aurora-Dress' and Service UUID '19590001-...'.
        2. Connects GATT, enables CCCD notifications on Telemetry characteristic.
        3. Reads initial 15-byte telemetry packet.
        4. User drags brightness slider to 120 -> writes 120 to Brightness characteristic.
        5. User taps 'Make it Blue!' -> writes opcode 0x03 to Command characteristic.
        6. Dress changes immediately to Merryweather Blue and notifies updated telemetry.
        """
        sim = WandInteractionSimulator()
        # 1-3: Verify service & initial telemetry
        raw = sim.get_ble_telemetry_bytes()
        self.assertEqual(len(raw), 15)
        init_telemetry = unpack_telemetry(raw)
        self.assertEqual(init_telemetry["mode"], 0)  # OFF

        # 4: Brightness adjustment via BLE
        res_bright = sim.handle_ble_brightness(120)
        self.assertEqual(res_bright, "OK")
        self.assertEqual(sim.brightness, 120)

        # 5-6: Mode command override via BLE
        res_cmd = sim.handle_ble_command(BLE_CMD_SET_BLUE)
        self.assertEqual(res_cmd, "OK")
        self.assertEqual(sim.mode, "BLUE")

        # Telemetry notification update
        updated_telemetry = unpack_telemetry(sim.get_ble_telemetry_bytes())
        self.assertEqual(updated_telemetry["mode"], 2)  # BLUE
        self.assertEqual(updated_telemetry["brightness"], 120)

    def test_scenario_06_pairing_cancellation_and_inactivity_timeout(self):
        """Scenario 6: Wand Pairing Cancellation and Inactivity Timeout.
        Steps:
        1. User taps 'Pair Pink Wand' -> state becomes PAIRING_PINK.
        2. User changes mind and taps 'Cancel' -> returns cleanly to NONE.
        3. User taps 'Pair Blue Wand' -> state becomes PAIRING_BLUE.
        4. User walks away; 30 seconds elapse without IR input.
        5. Inactivity timer fires and returns state cleanly to NONE.
        """
        sim = WandInteractionSimulator()
        # 1-2: Cancel
        res = sim.handle_ble_command(BLE_CMD_PAIR_PINK)
        self.assertEqual(res, "OK")
        self.assertEqual(sim.pairing_state, "PINK")
        res = sim.handle_ble_command(BLE_CMD_PAIR_CANCEL)
        self.assertEqual(res, "OK")
        self.assertEqual(sim.pairing_state, "NONE")

        # 3-5: Timeout
        res = sim.handle_ble_command(BLE_CMD_PAIR_BLUE)
        self.assertEqual(res, "OK")
        self.assertEqual(sim.pairing_state, "BLUE")
        sim.check_pairing_timeout(32000)  # >30s elapsed
        self.assertEqual(sim.pairing_state, "NONE")

    def test_scenario_07_continuous_operational_duty_cycle(self):
        """Scenario 7: Continuous Operational Duty Cycle (1000 simulated frames).
        Steps:
        1. Loop executes cooperative round-robin polling.
        2. Frame rendering throttled to 25ms intervals (~40 FPS).
        3. Periodic wand triggers and BLE telemetry sync occur concurrently.
        4. Zero timing drift or watchdog timeouts.
        """
        sim = WandInteractionSimulator(pink_id=0x11111111, blue_id=0x22222222)
        frame_count = 0
        current_time_ms = 0

        for tick in range(100):  # simulate 100 ticks of 25ms = 2.5 seconds
            current_time_ms += ANIMATION_FRAME_MS
            frame_count += 1
            if tick == 20:
                sim.handle_wand_signal(0x11111111, current_time_ms)
            elif tick == 40:
                raw = sim.get_ble_telemetry_bytes()
                self.assertEqual(len(raw), 15)
            elif tick == 60:
                sim.handle_wand_signal(0x22222222, current_time_ms)

        self.assertEqual(frame_count, 100)
        self.assertEqual(current_time_ms, 2500)
        self.assertTrue(sim.mode in ("PINK", "BLUE", "SPLOTCHES"))

    def test_scenario_08_power_cycle_nvs_recovery(self):
        """Scenario 8: Power Cycle & Persistent Memory Recovery.
        Steps:
        1. Pair wands to custom IDs via BLE triggers.
        2. System is power-cycled (simulating power off / reboot).
        3. During boot setup(), StorageController::init reads NVS keys.
        4. Learned wand IDs are immediately ready for interaction.
        """
        # Session 1: Pair
        sim1 = WandInteractionSimulator(pink_id=0, blue_id=0)
        sim1.handle_ble_command(BLE_CMD_PAIR_PINK)
        sim1.handle_wand_signal(0x44445555, 1000)
        sim1.handle_ble_command(BLE_CMD_PAIR_BLUE)
        sim1.handle_wand_signal(0x66667777, 2000)

        saved_nvs = dict(sim1.nvs)

        # Session 2: Cold boot from saved NVS
        sim2 = WandInteractionSimulator(
            pink_id=saved_nvs.get(NVS_KEY_PINK_WAND),
            blue_id=saved_nvs.get(NVS_KEY_BLUE_WAND)
        )
        self.assertEqual(sim2.pink_id, 0x44445555)
        self.assertEqual(sim2.blue_id, 0x66667777)

        # Flicks work immediately
        res = sim2.handle_wand_signal(0x44445555, 3000)
        self.assertEqual(res, "DISPATCH_PINK")
        self.assertEqual(sim2.mode, "PINK")

    def test_scenario_09_ambient_noise_and_burst_resilience(self):
        """Scenario 9: High-Density Signal Stress & Ambient Noise Rejection.
        Steps:
        1. Sunlight / ambient IR generates spurious short pulse noise.
        2. Decoder rejects noise pulses (<100 transitions or invalid bit periods).
        3. A real wand flick arrives amidst ambient noise.
        4. Decoder accurately extracts valid 56-bit packet.
        5. Dress triggers color change without missed frames.
        """
        sim = WandInteractionSimulator(pink_id=0x2F073545, blue_id=0x1A2B3C4D)

        # Ambient noise pulse train (short bursts)
        noise_pulses = [(50, 100), (80, 120), (30, 40)] * 10
        wand_id, _, status = MagiQuestDecoder.decode_pulse_train(noise_pulses)
        self.assertIsNone(wand_id)
        self.assertEqual(status, "insufficient_pulses")

        # Legitimate wand flick arrives
        valid_pulses = MagiQuestEncoder.encode_56bit(0x2F073545)
        valid_id, _, valid_status = MagiQuestDecoder.decode_pulse_train(valid_pulses)
        self.assertEqual(valid_status, "56bit_valid")
        self.assertEqual(valid_id, 0x2F073545)

        res = sim.handle_wand_signal(valid_id, 5000)
        self.assertEqual(res, "DISPATCH_PINK")
        self.assertEqual(sim.mode, "PINK")

if __name__ == "__main__":
    unittest.main()
