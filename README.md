# Sleeping-Beauty-Dress

An interactive, color-changing Princess Aurora Halloween dress using an ESP32 microcontroller, WS2812B addressable LEDs, dual-shoulder 38KHz IR receivers, and an embedded captive portal web interface to detect and respond to MagiQuest wands.

---

## 1. Hardware Architecture & Wiring

### Microcontroller & Components
* **MCU**: Seeed Studio XIAO ESP32-C3 (160MHz single-core RISC-V, 4MB Flash, 320KB SRAM).
* **LEDs**: 150 WS2812B addressable LEDs driven by `makuna/NeoPixelBus @ ^2.8.4` over dedicated hardware RMT channels:
  - Skirt: 100 LEDs on GPIO 4 (D2, RMT Channel 0)
  - Upper Body & Sleeves: 50 LEDs on GPIO 5 (D3, RMT Channel 1)
  - GPIO 6 (D4): Permanently disabled (ESP32-C3 has strictly 2 RMT TX channels)
* **Sensors**: Dual 38KHz Digital IR Demodulator Receivers (one on each shoulder for 360° wand target acquisition):
  - Left Shoulder: GPIO 3 (D1)
  - Right Shoulder: GPIO 2 (D0)
* **Power**: 5V USB battery pack powering the board via USB-C or $V_{IN}$ pad, with power rail bus to LED 5V/GND.

### Wiring & Pinout Table

| Function | Pin | Logic Level | Power Connection | Notes |
|---|---|---|---|---|
| **Left Shoulder IR** | GPIO 3 (D1) | 3.3V Input | **Connect to 3.3V Rail** | Internal pull-up enabled |
| **Right Shoulder IR**| GPIO 2 (D0) | 3.3V Input | **Connect to 3.3V Rail** | Internal pull-up enabled |
| **Skirt LEDs** | GPIO 4 (D2) | 5V Output (WS2812B) | 5V Battery Rail | 100 LEDs (RMT 0) |
| **Upper Body LEDs** | GPIO 5 (D3) | 5V Output (WS2812B) | 5V Battery Rail | 50 LEDs (RMT 1) |
| **GPIO 6 (Disabled)**| GPIO 6 (D4) | N/A | N/A | Disabled (ESP32-C3 limit: 2 RMT TX channels) |

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

### Current Implementation: Software Interrupts with IRAM Cache Safety
* **Interrupt Driver**: Uses **GPIO edge-triggered software CPU interrupts** (`attachInterrupt(..., CHANGE)`) on GPIO 3 (Left Shoulder) and GPIO 2 (Right Shoulder).
* **IRAM Flash Cache Safety**: Timestamping uses ESP-IDF native `esp_timer_get_time()`, residing 100% in IRAM (`.iram0.text`) with zero branches to SPI flash (`.flash.text`). This prevents ESP32 cache disabled panics when pairing new wands and committing IDs to NVS flash storage.
* **Ping-Pong (Double) Buffering**: Each shoulder receiver channel has independent double buffers (`rawbuf[2][160]`). While one completed frame is published to the main loop, subsequent repeat bursts write to the alternate buffer, preventing overwrite or corruption. Index swapping executes in 4 CPU instructions.
* **Fast 3.5ms Inter-Burst Silence Timeout**: Intra-packet bit spaces are $\le 1000\mu\text{s}$, while inter-burst gaps are $\ge 10\text{ms}$. Setting the silence timeout to 3.5ms isolates each burst immediately, cutting reaction latency from $\sim 280\text{ms}$ down to $\sim 3.5\text{ms}$.
* **Strict 56-Bit Preamble Validation**: Requires exact 56-bit alignment and verifies `(data >> 48) == 0x00`. Prevents bit-slipped frames from generating false IDs (e.g., `0xD8854475` or `0x31C11685`).

### Universal Studios Harry Potter Wands Incompatibility
* **Why they cannot be used with this system**:
  - Universal Studios interactive wands are **passive retro-reflective reflectors** containing **no battery, no circuit board, and no IR LEDs**.
  - They operate via a tiny retroreflective bead at the wand tip that reflects ambient IR light back to high-speed camera sensors embedded in park displays, which perform computer vision gesture tracking.
  - They do not emit 38KHz pulsed light and cannot be detected by photodiode demodulator modules.
  - MagiQuest wands are active transmitters and remain the standard for IR-based interactive cosplay.

---

## 3. Hardware Architecture & Hardware Upgrades

### 1. Hardware RMT Peripheral Driver (`NeoPixelBus`)
* The ESP32-C3 features strictly 2 hardware RMT TX channels (Channel 0 and Channel 1).
* `makuna/NeoPixelBus @ ^2.8.4` maps dedicated hardware RMT methods directly to the pins:
  - `NeoEsp32Rmt0Ws2812xMethod` drives **GPIO 4 (D2, Skirt, 100 LEDs)** via RMT Channel 0.
  - `NeoEsp32Rmt1Ws2812xMethod` drives **GPIO 5 (D3, Upper Body & Sleeves, 50 LEDs)** via RMT Channel 1.
  - GPIO 6 (D4) is permanently disabled to respect the 2-channel hardware limit.
* **Zero Interrupt Masking**: Unlike bit-banging drivers, RMT hardware transmits frames via dedicated DMA/FIFO buffers in hardware. Frame rendering never disables CPU interrupts and never causes dropped IR wand pulses.
* **Power-On Dark Clamp**: `LedController::earlyPinClamp()` holds GPIO 4 and GPIO 5 `LOW` with internal pull-downs enabled and holds for $>400\mu\text{s}$ before initializing peripheral registers, eliminating the power-on solid-white latch-up.

### 2. Drop-in MCU Upgrade: Seeed Studio XIAO ESP32-S3 (Optional)
* **When to upgrade?**:
  - If additional hardware RMT channels are desired (e.g. driving 3 or more independent LED strips) or simultaneous high-throughput WiFi + BLE is required.
* **The XIAO ESP32-S3 advantage**:
  - **Exact same physical form-factor and pinout**: Drops directly into the existing dress socket with zero wiring changes.
  - **Dual-Core Xtensa LX7 @ 240MHz**: Web and animations run on Core 0, while IR edge capture and decoding run on Core 1 completely uninterrupted.
  - 8 RMT channels (4 TX, 4 RX), 8MB Flash, 512KB SRAM, 2MB PSRAM.

### 3. Receiver Upgrade: Vishay TSOP38238
* Upgrading generic VS1838B clones to genuine **Vishay TSOP38238** (or TSOP34838) receivers provides superior optical filtering against sunlight and theatrical stage lighting, with active AGC4 noise suppression and consistent pulse-width reproduction.

---

## 4. Software Controllers Overview

* **`include/Config.h`**: Central definitions for hardware pins, LED counts, brightness limits (1500mA brownout protection cap), animation timing, and soft AP credentials.
* **`StorageController`**: Persistent non-volatile storage (NVS via ESP32 `Preferences`) for 32-bit wand IDs (`pinkWandCode` and `blueWandCode`).
* **`LedController`**: Hardware RMT `NeoPixelBus` driver on GPIO 4 and GPIO 5 with early power-on pin clamp (preventing solid white lockup) and standalone procedural animations (`AnimMath.h`):
  - `PINK`: Solid Princess Aurora Pink (`#FF1493`).
  - `BLUE`: Solid Fairy Merryweather Blue (`#0078FF`).
  - `SPLOTCHES`: Procedural noise color duel animation with turbulent advection, clash boundary sparkle (`#FFFFF0`), and dueling wave oscillation.
  - `OFF`: Low-power blank state.
  - `PAIRING_FEEDBACK`: Visual breathing pulses.
* **`IRController`**: Dual-receiver driver on Left/Right shoulders with `IRAM_ATTR` interrupt safety, cache-safe `esp_timer_get_time()`, ping-pong buffering, 3.5ms burst separation, custom 56-bit MagiQuest decoder, and pairing state machine.
* **`WebController`**: Standalone WiFi Access Point (`"Sleeping-Beauty-Dress"` @ `192.168.4.1`) and DNS captive portal serving an asynchronous mobile web interface on port 80 with REST endpoints.

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

### REST API Reference

The asynchronous web server exposes the following zero-heap HTTP GET endpoints:

| Endpoint | Method | Response | Description |
|---|---|---|---|
| `/` | `GET` | `text/html` | Serves the single-page responsive control app stored in `PROGMEM` |
| `/api/status` | `GET` | `application/json` | Returns live status: `{"mode":"...","pinkWand":"...","blueWand":"...","pairing":"...","brightness":...}` |
| `/setPink` | `GET` | `application/json` | Overrides lighting to Princess Aurora Deep Pink (`#FF1493`) |
| `/setBlue` | `GET` | `application/json` | Overrides lighting to Merryweather Royal Blue (`#0078FF`) |
| `/setSplotches`| `GET` | `application/json` | Overrides lighting to dynamic dueling Splotches animation with fairy dust |
| `/setOff` | `GET` | `application/json` | Turns off all LEDs (`#000000`) |
| `/register/pink`| `GET` | `application/json` | Enters 30-second pairing window for the Pink Wand |
| `/register/blue`| `GET` | `application/json` | Enters 30-second pairing window for the Blue Wand |
| `/register/cancel`| `GET` | `application/json`| Cancels active wand pairing window |
| `/setBrightness?val=<0-255>`| `GET`| `application/json`| Adjusts master LED brightness (also available at `/brightness`) |

---

## 6. Build & Flashing

Built using PlatformIO Core targeting the `seeed_xiao_esp32c3` environment:

```powershell
# Compile firmware in release mode
pio run

# Flash to board via USB-C
pio run --target upload

# Open serial monitor (115200 baud)
pio device monitor -b 115200
```

### Memory Footprint
* **RAM**: 12.8% (41,876 / 327,680 bytes)
* **Flash**: 42.4% (833,426 / 1,966,080 bytes)

---

## 7. Automated E2E Test Suite

The repository includes a comprehensive 196-test automated verification suite located in `tests/`:

```powershell
# Run the complete test suite
python tests/run_tests.py
```

### Test Coverage Hierarchy
* **Tier 1: Feature Coverage (85 tests)**: 5 tests for each of the 17 system features (`tests/tier1_features/`).
* **Tier 2: Boundary & Corner Cases (85 tests)**: 5 tests for each feature probing timing, memory limits, and signal noise (`tests/tier2_boundaries/`).
* **Tier 3: Cross-Feature Combinations (17 tests)**: Pairwise subsystem concurrency testing (`tests/tier3_cross_feature/`).
* **Tier 4: Real-World Scenarios (9 tests)**: Full multi-step operational journeys (`tests/tier4_real_world/`).

---

## 8. Bluetooth Low Energy & Android Companion Architecture

For environments where WiFi captive portals are inconvenient, the repository defines a dedicated Bluetooth Low Energy (BLE 5.0) GATT profile specification to support a native Android companion app.

* Specification Document: [`docs/BLUETOOTH_SPECIFICATION.md`](docs/BLUETOOTH_SPECIFICATION.md)
* Includes complete GATT service hierarchy (`19590001-...`), packed binary telemetry structs, 1-byte command opcodes, and prompt requirements for generating the native Kotlin / Jetpack Compose Android client in a separate repository.

