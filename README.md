# Sleeping-Beauty-Dress

An interactive, color-changing Princess Aurora Halloween dress using an ESP32 microcontroller, WS2812B addressable LEDs, dual-shoulder 38KHz IR receivers, and a Bluetooth Low Energy (BLE 5.0) GATT server communicating with a native Android companion app (`Aurora-Dress-Companion`) to detect and respond to MagiQuest wands.

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

* **`include/Config.h`**: Central definitions for hardware pins, LED counts, brightness limits (1500mA brownout protection cap), animation timing, BLE GATT service/characteristic UUIDs, and command opcodes.
* **`StorageController`**: Persistent non-volatile storage (NVS via ESP32 `Preferences`) for 32-bit wand IDs (`pinkWandCode` and `blueWandCode`).
* **`LedController`**: Hardware RMT `NeoPixelBus` driver on GPIO 4 and GPIO 5 with early power-on pin clamp (preventing solid white lockup) and standalone procedural animations (`AnimMath.h`):
  - `PINK`: Solid Princess Aurora Pink (`#FF1493`).
  - `BLUE`: Solid Fairy Merryweather Blue (`#0078FF`).
  - `SPLOTCHES`: Procedural noise color duel animation with turbulent advection, clash boundary sparkle (`#FFFFF0`), and dueling wave oscillation.
  - `OFF`: Low-power blank state.
  - `PAIRING_FEEDBACK`: Visual breathing pulses.
* **`IRController`**: Dual-receiver driver on Left/Right shoulders with `IRAM_ATTR` interrupt safety, cache-safe `esp_timer_get_time()`, ping-pong buffering, 3.5ms burst separation, custom 56-bit MagiQuest decoder, and pairing state machine.
* **`BleController`**: Standalone native ESP32 BLE 5.0 GATT server (`Aurora-Dress`, Service `19590001-d1e5-4e3b-9a14-c0104d4e5353`). Manages a 15-byte Little-Endian packed binary telemetry characteristic with NOTIFY/READ (`19590002-...`), 1-byte command input with WRITE/WRITE_NO_RESPONSE (`19590003-...`), and master brightness control (`19590004-...`), with non-blocking cooperative advertising recovery.

---

## 5. Android Companion App & Wand Pairing Guide

1. Power the dress via a 5V battery bank.
2. Launch the **Aurora Dress Companion** app on your Android smartphone (BLE 5.0 enabled).
3. The app automatically scans for and connects to the **`Aurora-Dress`** BLE peripheral advertising the Aurora Primary Service UUID (`19590001-d1e5-4e3b-9a14-c0104d4e5353`).
4. **Pairing a Wand**:
   - Tap **"Pair Pink Wand"** in the companion app (sends opcode `0x10`). The dress enters a 30-second pairing window and telemetry reports `PAIRING_PINK`.
   - Flick the Pink Wand near either shoulder.
   - The dress flashes pink 3 times to confirm pairing, permanently saves the 32-bit ID to NVS flash (`pink_wand`), and resumes normal operation.
   - Repeat for **"Pair Blue Wand"** (sends opcode `0x11`).
   - Tap **"Cancel Pairing"** (sends opcode `0x12`) if needed to abort pairing before timeout.
5. **Dueling Spell (Splotches)**:
   - Flick the Pink Wand, then flick the Blue Wand within 2.0 seconds. The dress automatically shifts into the animated "Dueling Splotches" mode.
6. **Manual Lighting & Brightness Controls**:
   - Use the companion app buttons for immediate lighting overrides: Pink (`0x02`), Blue (`0x03`), Splotches (`0x04`), or Off (`0x01`).
   - Adjust the brightness slider in the app (writes directly to characteristic `19590004-...` with values `0`–`255`).

### BLE GATT Architecture & Protocol Reference

The native ESP32 BLE GATT server exposes the following service and characteristics:

| UUID | Characteristic | Properties | Description |
|---|---|---|---|
| `19590001-d1e5-4e3b-9a14-c0104d4e5353` | Primary Service | N/A | Aurora Dress Primary BLE Service |
| `19590002-d1e5-4e3b-9a14-c0104d4e5353` | Live Telemetry | `READ`, `NOTIFY` | 15-byte little-endian binary telemetry struct |
| `19590003-d1e5-4e3b-9a14-c0104d4e5353` | Command Input | `WRITE`, `WRITE_NO_RESP` | 1-byte control opcode |
| `19590004-d1e5-4e3b-9a14-c0104d4e5353` | Brightness Control | `READ`, `WRITE`, `WRITE_NO_RESP` | 1-byte brightness value (`0`–`255`) |
| `00002902-0000-1000-8000-00805f9b34fb` | CCCD Descriptor | `READ`, `WRITE` | Client Characteristic Configuration Descriptor for Telemetry |

#### Live Telemetry Packet (15 Bytes, Little-Endian)

| Byte Offset | Field | Data Type | Valid Values & Encoding |
|---|---|---|---|
| `[0]` | Mode | `uint8_t` | `0x00`: OFF, `0x01`: PINK, `0x02`: BLUE, `0x03`: SPLOTCHES, `0x04`: PAIRING_FEEDBACK |
| `[1]` | Brightness | `uint8_t` | Master brightness level (`0` to `255`) |
| `[2]` | Pairing State | `uint8_t` | `0x00`: NONE / IDLE, `0x01`: PAIR_PINK, `0x02`: PAIR_BLUE |
| `[3..6]` | Pink Wand ID | `uint32_t` | 32-bit paired Pink Wand code (little-endian; `0x00000000` if unassigned) |
| `[7..10]` | Blue Wand ID | `uint32_t` | 32-bit paired Blue Wand code (little-endian; `0x00000000` if unassigned) |
| `[11..14]` | Last Wand ID | `uint32_t` | Most recently detected 32-bit IR wand code (little-endian) |

#### Command Opcodes (1 Byte)

| Opcode | Command | Effect |
|---|---|---|
| `0x01` | `CMD_SET_OFF` | Turn off all LEDs (`#000000`) |
| `0x02` | `CMD_SET_PINK` | Override lighting to Princess Aurora Deep Pink (`#FF1493`) |
| `0x03` | `CMD_SET_BLUE` | Override lighting to Merryweather Royal Blue (`#0078FF`) |
| `0x04` | `CMD_SET_SPLOTCHES` | Override lighting to dynamic dueling Splotches animation |
| `0x10` | `CMD_PAIR_PINK` | Initiate 30-second pairing window for Pink Wand |
| `0x11` | `CMD_PAIR_BLUE` | Initiate 30-second pairing window for Blue Wand |
| `0x12` | `CMD_PAIR_CANCEL` | Abort active pairing window immediately |

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
* **RAM**: 12.5% (41,028 / 327,680 bytes)
* **Flash**: 51.0% (1,003,444 / 1,966,080 bytes)

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

The firmware utilizes a native ESP32 BLE 5.0 GATT peripheral architecture paired with the `Aurora-Dress-Companion` Android application:

* **Companion App**: Native Android app built with Kotlin, Jetpack Compose, and Android BLE APIs. Discovers `Aurora-Dress`, receives live telemetry notifications, and sends command opcodes and brightness updates.
* **Specification Document**: Full binary protocol and GATT hierarchy defined in [`docs/BLUETOOTH_SPECIFICATION.md`](docs/BLUETOOTH_SPECIFICATION.md).
* **Zero Frame Drops**: BleController executes cooperative non-blocking updates in `loop()`, using non-blocking timers for advertising restart upon client disconnect without delaying NeoPixelBus RMT rendering or missing IR receiver interrupts.

