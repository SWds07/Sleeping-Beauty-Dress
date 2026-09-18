# Sleeping-Beauty-Dress

An interactive, color-changing Princess Aurora Halloween dress using an ESP32 microcontroller, WS2812B addressable LEDs, dual-shoulder 38KHz IR receivers, and an embedded captive portal web interface to detect and respond to MagiQuest wands.

---

## 1. Hardware Architecture & Wiring

### Microcontroller & Components
* **MCU**: Seeed Studio XIAO ESP32-C3 (160MHz single-core RISC-V, 4MB Flash, 400KB SRAM).
* **LEDs**: 150 WS2812B addressable LEDs split across 3 data pins:
  - Skirt: 100 LEDs on GPIO 4 (D2)
  - Left Sleeve: 25 LEDs on GPIO 5 (D3)
  - Right Sleeve: 25 LEDs on GPIO 6 (D4)
* **Sensors**: Dual 38KHz Digital IR Demodulator Receivers (one on each shoulder for 360° wand target acquisition):
  - Left Shoulder: GPIO 3 (D1)
  - Right Shoulder: GPIO 2 (D0)
* **Power**: 5V USB battery pack powering the board via USB-C or $V_{IN}$ pad, with power rail bus to LED 5V/GND.

### Wiring & Pinout Table

| Function | Pin | Logic Level | Power Connection | Notes |
|---|---|---|---|---|
| **Left Shoulder IR** | GPIO 3 (D1) | 3.3V Input | **Connect to 3.3V Rail** | Internal pull-up enabled |
| **Right Shoulder IR**| GPIO 2 (D0) | 3.3V Input | **Connect to 3.3V Rail** | Internal pull-up enabled |
| **Skirt LEDs** | GPIO 4 (D2) | 5V Output (WS2812B) | 5V Battery Rail | 100 LEDs |
| **Left Sleeve LEDs** | GPIO 5 (D3) | 5V Output (WS2812B) | 5V Battery Rail | 25 LEDs |
| **Right Sleeve LEDs**| GPIO 6 (D4) | 5V Output (WS2812B) | 5V Battery Rail | 25 LEDs |

> [!IMPORTANT]
> **IR Receiver Operating Voltage (3.3V vs. 5V)**:
> Always power the 38KHz IR receiver modules from the **3.3V rail** (XIAO `3V3` pin), **NOT from 5V**.
> * Most IR demodulators (VS1838B, TSOP38238) have internal pull-ups to $V_{CC}$. If powered with 5V, the data line idles at 5.0V.
> * The ESP32-C3 GPIO pins are rated for a maximum of $V_{DD} + 0.3\text{V} \approx 3.6\text{V}$.
> * Exposing the pins to 5V triggers internal ESD clamping diodes, which rounds off pulse edges and distorts microsecond pulse timings (turning 280µs pulses into >400µs), causing dropped packets and erroneous IDs.
> * Modern 38kHz receivers run natively from 2.5V to 5.5V. Operating at 3.3V provides crisp, clean square waves without level-shifting.

---

## 2. IR Wand Detection Architecture

### MagiQuest Protocol Specification
MagiQuest wands (Creative Kingdoms / Great Wolf Lodge) emit active 38KHz pulse-width modulated IR packets:
* **Carrier Frequency**: 38 KHz
* **Bit Period**: $\sim 1120\mu\text{s} - 1150\mu\text{s}$ (constant mark + space period)
* **Bit 0**: Short Mark ($\sim 280\mu\text{s}$, $\approx 25\%$), Long Space ($\sim 840\mu\text{s}$)
* **Bit 1**: Long Mark ($\sim 560\mu\text{s}$, $\approx 50\%$), Medium Space ($\sim 560\mu\text{s}$)
* **Payload (56 bits)**:
  - **Preamble (8 bits)**: Strictly `0x00` (8 zero bits)
  - **Wand ID (32 bits)**: Unique hardware serial code (e.g. `0x2F073545`)
  - **Magnitude (16 bits)**: Flick force / tilt sensor reading
* **Wand Transmission Behavior**:
  - When flicked, a wand transmits **2 to 4 repeated bursts** separated by $10\text{ms} - 25\text{ms}$ gaps.

### Current Implementation: Software Interrupts vs. Hardware RMT
* **Current Driver**: We are currently utilizing **GPIO edge-triggered software CPU interrupts** (`attachInterrupt(..., CHANGE)` with `micros()` timestamping), **not the hardware RMT peripheral**.
* **Ping-Pong (Double) Buffering**: Each shoulder receiver channel has independent double buffers (`rawbuf[2][160]`). While one completed frame is published to the main loop, subsequent repeat bursts write to the alternate buffer, preventing overwrite or corruption.
* **Fast 3.5ms Inter-Burst Silence Timeout**: Intra-packet bit spaces are $\le 1000\mu\text{s}$, while inter-burst gaps are $\ge 10\text{ms}$. Setting the silence timeout to 3.5ms isolates each burst immediately, cutting reaction latency from $\sim 280\text{ms}$ down to $\sim 3.5\text{ms}$.
* **Strict 56-Bit Preamble Validation**: Requires exact 56-bit alignment and verifies `(data >> 48) == 0x00`. Prevents bit-slipped frames from generating false IDs (e.g., `0xD8854475` or `0x31C11685`).

### Universal Studios Harry Potter Wands Incompatibility
* **Why they cannot be used with this system**:
  - Universal Studios interactive wands are **passive retro-reflective reflectors** containing **no battery, no circuit board, and no IR LEDs**.
  - They operate via a tiny retroreflective bead at the wand tip that reflects ambient IR light back to high-speed camera sensors embedded in park displays, which perform computer vision gesture tracking.
  - They do not emit 38KHz pulsed light and cannot be detected by photodiode demodulator modules.
  - MagiQuest wands are active transmitters and remain the standard for IR-based interactive cosplay.

---

## 3. Hardware Roadmap & Upgrade Options

### 1. Drop-in MCU Upgrade: Seeed Studio XIAO ESP32-S3
* **Why upgrade?**:
  - On the single-core ESP32-C3, `FastLED.show()` must disable CPU interrupts during WS2812B bit-banging ($\sim 4.5\text{ms}$ per frame for 150 LEDs across 3 pins). If a wand flick occurs during that window, edges can be missed.
* **The XIAO ESP32-S3 advantage**:
  - **Exact same physical form-factor and pinout**: Drops directly into the existing dress socket with zero wiring changes.
  - **Dual-Core Xtensa LX7 @ 240MHz**: FastLED and the Async Web Server run on Core 0, while IR edge capture and decoding run on Core 1 completely uninterrupted.
  - 8MB Flash / 512KB SRAM / 2MB PSRAM.

### 2. Hardware RMT Peripheral Migration (on ESP32-C3)
* If remaining on the ESP32-C3, the driver can be migrated to the internal ESP-IDF **RMT (Remote Control Transceiver)** peripheral.
* The RMT hardware uses dedicated hardware counters and DMA channels to record pulse durations independently of the CPU, making it immune to `FastLED.show()` interrupt masking without requiring a second microcontroller.

### 3. Receiver Upgrade: Vishay TSOP38238
* Upgrading generic VS1838B clones to genuine **Vishay TSOP38238** (or TSOP34838) receivers provides superior optical filtering against sunlight and theatrical stage lighting, with active AGC4 noise suppression and consistent pulse-width reproduction.

---

## 4. Software Controllers Overview

* **`include/Config.h`**: Central definitions for hardware pins, LED counts, brightness limits (1500mA brownout protection cap), animation timing, and soft AP credentials.
* **`StorageController`**: Persistent non-volatile storage (NVS via ESP32 `Preferences`) for 32-bit wand IDs (`pinkWandCode` and `blueWandCode`).
* **`LedController`**: FastLED driver across 3 pins (Skirt, Left Sleeve, Right Sleeve) implementing non-blocking 40 FPS updates:
  - `PINK`: Solid Princess Aurora Pink (`0xFF1493`).
  - `BLUE`: Solid Fairy Merryweather Blue (`0x0078FF`).
  - `SPLOTCHES`: Procedural Perlin-noise 3D color duel animation with turbulent advection, clash boundary sparkle, and dueling wave oscillation.
  - `OFF`: Low-power blank state.
  - Pairing feedback breathing pulses.
* **`IRController`**: Dual-receiver driver on Left/Right shoulders with ping-pong buffering, 3.5ms burst separation, custom 56-bit MagiQuest decoder, and pairing state machine.
* **`WebController`**: Standalone WiFi Access Point (`"Sleeping-Beauty-Dress"`) and DNS captive portal serving an asynchronous mobile web interface on port 80.

---

## 5. Web Portal & Wand Pairing Guide

1. Power the dress via a 5V battery bank.
2. On your phone, connect to the WiFi network **`Sleeping-Beauty-Dress`** (no password required).
3. The captive portal will open automatically (or navigate to `http://192.168.4.1/` in any browser).
4. **Pairing a Wand**:
   - Tap **"Register Pink Wand"** (banner will flash "PAIRING ACTIVE: Flick PINK Wand now!").
   - Wave/flick the wand near either shoulder.
   - The dress flashes pink 3 times to confirm pairing, and saves the 32-bit ID permanently to flash.
   - Repeat for **"Register Blue Wand"**.
5. **Dueling Spell (Splotches)**:
   - Flick the Pink Wand, then flick the Blue Wand within 2.0 seconds. The dress automatically shifts into the animated "Dueling Splotches" mode.
6. **Manual Overrides**:
   - Use the web interface buttons (Pink, Blue, Splotches, Off, and Brightness Slider) for immediate manual control.

---

## 6. Build & Compilation

Built using PlatformIO Core:

```powershell
# Compile firmware
pio run

# Flash to device via USB
pio run --target upload

# Open serial monitor
pio device monitor -b 115200
```

