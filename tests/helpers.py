# -*- coding: utf-8 -*-
from __future__ import print_function, division, absolute_import
import json
import os
import re
import struct

# ============================================================================
# Constant Definitions (matching Config.h & Technical Specifications)
# ============================================================================
COLOR_PINK_HEX = "#FF1493"
COLOR_BLUE_HEX = "#0078FF"
COLOR_SPARKLE_HEX = "#FFFFF0"
COLOR_OFF_HEX = "#000000"

COLOR_PINK_RGB = (255, 20, 147)
COLOR_BLUE_RGB = (0, 120, 255)
COLOR_SPARKLE_RGB = (255, 255, 240)
COLOR_OFF_RGB = (0, 0, 0)

LED_DEFAULT_BRIGHTNESS = 160
LED_MAX_BRIGHTNESS = 160
ANIMATION_FPS = 40
ANIMATION_FRAME_MS = 25

NUM_LEDS_SKIRT = 100
NUM_LEDS_LSLEEVE = 25
NUM_LEDS_RSLEEVE = 25
NUM_LEDS_UPPER = 50
NUM_LEDS_TOTAL = 150

PIN_LED_SKIRT = 4
PIN_LED_UPPER = 5
PIN_LED_RSLEEVE_DISABLED = 6

PIN_IR_RECV_LEFT = 3
PIN_IR_RECV_RIGHT = 2

WAND_RAPID_WINDOW_MS = 2000
IR_DEBOUNCE_MS = 400
PAIRING_TIMEOUT_MS = 30000
PAIRING_FEEDBACK_MS = 1500
PAIRING_CYCLE_MS = 500

WIFI_AP_SSID = "Sleeping-Beauty-Dress"
WIFI_AP_IP = "192.168.4.1"
DNS_PORT = 53
HTTP_PORT = 80

BLE_DEVICE_NAME = "Aurora-Dress"
BLE_SERVICE_UUID = "19590001-d1e5-4e3b-9a14-c0104d4e5353"
BLE_CHAR_TELEMETRY_UUID = "19590002-d1e5-4e3b-9a14-c0104d4e5353"
BLE_CHAR_COMMAND_UUID = "19590003-d1e5-4e3b-9a14-c0104d4e5353"
BLE_CHAR_BRIGHTNESS_UUID = "19590004-d1e5-4e3b-9a14-c0104d4e5353"
BLE_CCCD_DESCRIPTOR_UUID = "00002902-0000-1000-8000-00805f9b34fb"

BLE_CMD_SET_OFF = 0x01
BLE_CMD_SET_PINK = 0x02
BLE_CMD_SET_BLUE = 0x03
BLE_CMD_SET_SPLOTCHES = 0x04
BLE_CMD_PAIR_PINK = 0x10
BLE_CMD_PAIR_BLUE = 0x11
BLE_CMD_PAIR_CANCEL = 0x12

NVS_NAMESPACE = "auroradress"
NVS_KEY_PINK_WAND = "pink_wand"
NVS_KEY_BLUE_WAND = "blue_wand"

# ============================================================================
# Color & Brightness Model
# ============================================================================
def hex_to_rgb(hex_str):
    hex_clean = hex_str.lstrip('#')
    return (int(hex_clean[0:2], 16), int(hex_clean[2:4], 16), int(hex_clean[4:6], 16))

def rgb_to_hex(r, g, b):
    return "#{:02X}{:02X}{:02X}".format(r, g, b)

def scale_color(rgb, brightness):
    clamped_b = min(LED_MAX_BRIGHTNESS, max(0, brightness))
    r = min(255, max(0, rgb[0]))
    g = min(255, max(0, rgb[1]))
    b = min(255, max(0, rgb[2]))
    return (
        (r * clamped_b) // 255,
        (g * clamped_b) // 255,
        (b * clamped_b) // 255
    )

# ============================================================================
# MagiQuest Protocol Encoder / Decoder Model
# ============================================================================
class MagiQuestEncoder(object):
    @staticmethod
    def encode_56bit(wand_id, magnitude=0x0100):
        # 56 bits: 8-bit preamble (0x00) + 32-bit wand ID + 16-bit magnitude
        preamble = 0x00
        bits = []
        for i in range(7, -1, -1):
            bits.append((preamble >> i) & 1)
        for i in range(31, -1, -1):
            bits.append((wand_id >> i) & 1)
        for i in range(15, -1, -1):
            bits.append((magnitude >> i) & 1)
        
        pulses = []
        for b in bits:
            if b == 0:
                pulses.append((280, 850))  # mark 280us, space 850us
            else:
                pulses.append((580, 600))  # mark 580us, space 600us
        return pulses

    @staticmethod
    def encode_48bit_fallback(wand_id, magnitude=0x0100):
        # 48 bits: 32-bit wand ID + 16-bit magnitude (no preamble)
        bits = []
        for i in range(31, -1, -1):
            bits.append((wand_id >> i) & 1)
        for i in range(15, -1, -1):
            bits.append((magnitude >> i) & 1)
        
        pulses = []
        for b in bits:
            if b == 0:
                pulses.append((280, 850))
            else:
                pulses.append((580, 600))
        return pulses

class MagiQuestDecoder(object):
    MIN_BIT_US = 650
    MAX_BIT_US = 1750
    RATIO_THRESHOLD = 35  # % mark duty cycle threshold

    @classmethod
    def decode_pulse_train(cls, pulses):
        if len(pulses) < 48:
            return None, None, "insufficient_pulses"
        
        decoded_bits = []
        for mark, space in pulses:
            period = mark + space
            if period < cls.MIN_BIT_US or period > cls.MAX_BIT_US:
                return None, None, "invalid_bit_period"
            ratio = (mark * 100) // period
            bit = 1 if ratio >= cls.RATIO_THRESHOLD else 0
            decoded_bits.append(bit)
        
        # Pass 1: check 56-bit frame with 8-bit preamble == 0x00
        if len(decoded_bits) >= 56:
            preamble_bits = decoded_bits[:8]
            preamble_val = 0
            for b in preamble_bits:
                preamble_val = (preamble_val << 1) | b
            if preamble_val == 0:
                wand_bits = decoded_bits[8:40]
                wand_id = 0
                for b in wand_bits:
                    wand_id = (wand_id << 1) | b
                mag_bits = decoded_bits[40:56]
                mag = 0
                for b in mag_bits:
                    mag = (mag << 1) | b
                return wand_id, mag, "56bit_valid"

        # Pass 2: check 48-bit fallback
        if len(decoded_bits) >= 48:
            wand_bits = decoded_bits[:32]
            wand_id = 0
            for b in wand_bits:
                wand_id = (wand_id << 1) | b
            mag_bits = decoded_bits[32:48]
            mag = 0
            for b in mag_bits:
                mag = (mag << 1) | b
            return wand_id, mag, "48bit_fallback"

        return None, None, "decode_failed"

# ============================================================================
# Wand Interaction & State Machine Simulator
# ============================================================================
class WandInteractionSimulator(object):
    def __init__(self, pink_id=0x2F073545, blue_id=0x1A2B3C4D):
        self.pink_id = pink_id
        self.blue_id = blue_id
        self.mode = "OFF"
        self.brightness = LED_DEFAULT_BRIGHTNESS
        self.pairing_state = "NONE"
        self.pairing_start_time = 0
        self.last_pink_time = 0
        self.last_blue_time = 0
        self.last_signal_time = 0
        self.last_received_code = 0
        self.nvs = {
            NVS_KEY_PINK_WAND: pink_id,
            NVS_KEY_BLUE_WAND: blue_id
        }

    def start_pairing(self, mode, now_ms):
        self.pairing_state = mode  # "PINK" or "BLUE"
        self.pairing_start_time = now_ms

    def cancel_pairing(self):
        self.pairing_state = "NONE"
        self.pairing_start_time = 0

    def check_pairing_timeout(self, now_ms):
        if self.pairing_state != "NONE":
            if now_ms - self.pairing_start_time >= PAIRING_TIMEOUT_MS:
                self.pairing_state = "NONE"
                self.pairing_start_time = 0
                return True
        return False

    def handle_wand_signal(self, code, now_ms):
        # 1. Debounce check
        if code == self.last_received_code and (now_ms - self.last_signal_time < IR_DEBOUNCE_MS):
            return "DEBOUNCED"
        
        self.last_received_code = code
        self.last_signal_time = now_ms

        # 2. Pairing active?
        if self.pairing_state == "PINK":
            self.pink_id = code
            self.nvs[NVS_KEY_PINK_WAND] = code
            self.pairing_state = "NONE"
            self.mode = "PAIRING_FEEDBACK"
            return "PAIRED_PINK"
        elif self.pairing_state == "BLUE":
            self.blue_id = code
            self.nvs[NVS_KEY_BLUE_WAND] = code
            self.pairing_state = "NONE"
            self.mode = "PAIRING_FEEDBACK"
            return "PAIRED_BLUE"

        # 3. Operational wand dispatch
        if code == self.pink_id:
            self.last_pink_time = now_ms
            if self.last_blue_time > 0 and (now_ms - self.last_blue_time <= WAND_RAPID_WINDOW_MS):
                self.mode = "SPLOTCHES"
                self.last_pink_time = 0
                self.last_blue_time = 0
                return "DISPATCH_SPLOTCHES"
            else:
                self.mode = "PINK"
                return "DISPATCH_PINK"
        elif code == self.blue_id:
            self.last_blue_time = now_ms
            if self.last_pink_time > 0 and (now_ms - self.last_pink_time <= WAND_RAPID_WINDOW_MS):
                self.mode = "SPLOTCHES"
                self.last_pink_time = 0
                self.last_blue_time = 0
                return "DISPATCH_SPLOTCHES"
            else:
                self.mode = "BLUE"
                return "DISPATCH_BLUE"
        else:
            return "UNKNOWN_WAND"

    def handle_rest_request(self, endpoint, params=None):
        params = params or {}
        if endpoint == "/api/status":
            pink_str = "0x{:08X}".format(self.pink_id) if self.pink_id != 0 else "Not Paired"
            blue_str = "0x{:08X}".format(self.blue_id) if self.blue_id != 0 else "Not Paired"
            return 200, {
                "mode": self.mode,
                "pinkWand": pink_str,
                "blueWand": blue_str,
                "pairing": self.pairing_state,
                "brightness": self.brightness
            }
        elif endpoint == "/setPink":
            self.mode = "PINK"
            return 200, {"status": "ok", "mode": "PINK"}
        elif endpoint == "/setBlue":
            self.mode = "BLUE"
            return 200, {"status": "ok", "mode": "BLUE"}
        elif endpoint == "/setSplotches":
            self.mode = "SPLOTCHES"
            return 200, {"status": "ok", "mode": "SPLOTCHES"}
        elif endpoint == "/setOff":
            self.mode = "OFF"
            return 200, {"status": "ok", "mode": "OFF"}
        elif endpoint == "/register/pink":
            self.start_pairing("PINK", 1000)
            return 200, {"status": "ok", "pairing": "PINK"}
        elif endpoint == "/register/blue":
            self.start_pairing("BLUE", 1000)
            return 200, {"status": "ok", "pairing": "BLUE"}
        elif endpoint == "/register/cancel":
            self.cancel_pairing()
            return 200, {"status": "ok", "pairing": "NONE"}
        elif endpoint in ("/brightness", "/setBrightness"):
            if "val" in params:
                try:
                    val = int(params["val"])
                    val = min(255, max(0, val))
                    self.brightness = min(LED_MAX_BRIGHTNESS, val)
                except ValueError:
                    pass
            return 200, {"status": "ok"}
        elif endpoint in ("/generate_204", "/hotspot-detect.html", "/canonical.html", "/ncsi.txt", "/connecttest.txt"):
            return 302, {"Location": "http://192.168.4.1/"}
        else:
            # 404 catch-all redirects to portal
            return 302, {"Location": "http://192.168.4.1/"}

    def handle_ble_command(self, opcode, now_ms=1000):
        if opcode == BLE_CMD_SET_OFF:
            self.mode = "OFF"
            return "OK"
        elif opcode == BLE_CMD_SET_PINK:
            self.mode = "PINK"
            return "OK"
        elif opcode == BLE_CMD_SET_BLUE:
            self.mode = "BLUE"
            return "OK"
        elif opcode == BLE_CMD_SET_SPLOTCHES:
            self.mode = "SPLOTCHES"
            return "OK"
        elif opcode == BLE_CMD_PAIR_PINK:
            self.start_pairing("PINK", now_ms)
            return "OK"
        elif opcode == BLE_CMD_PAIR_BLUE:
            self.start_pairing("BLUE", now_ms)
            return "OK"
        elif opcode == BLE_CMD_PAIR_CANCEL:
            self.cancel_pairing()
            return "OK"
        return "UNKNOWN_OPCODE"

    def handle_ble_brightness(self, val):
        val = min(255, max(0, int(val)))
        self.brightness = min(LED_MAX_BRIGHTNESS, val)
        return "OK"

    def get_ble_telemetry_bytes(self):
        mode_map = {"OFF": 0, "PINK": 1, "BLUE": 2, "SPLOTCHES": 3, "PAIRING_FEEDBACK": 4}
        pairing_map = {"NONE": 0, "PINK": 1, "BLUE": 2}
        m = mode_map.get(self.mode, 0)
        p = pairing_map.get(self.pairing_state, 0)
        return pack_telemetry(m, self.brightness, p, self.pink_id, self.blue_id, self.last_received_code)

def pack_telemetry(mode_val, brightness, pairing_val, pink_id, blue_id, last_id):
    """Packs 15-byte little-endian DressTelemetryPacket struct."""
    return struct.pack("<BBBIII", mode_val, min(255, max(0, brightness)), pairing_val, pink_id, blue_id, last_id)

def unpack_telemetry(data):
    """Unpacks 15-byte little-endian DressTelemetryPacket struct."""
    if len(data) < 15:
        return None
    mode_val, brightness, pairing_val, pink_id, blue_id, last_id = struct.unpack("<BBBIII", data[:15])
    return {
        "mode": mode_val,
        "brightness": brightness,
        "pairingState": pairing_val,
        "pinkWandId": pink_id,
        "blueWandId": blue_id,
        "lastWandId": last_id
    }

