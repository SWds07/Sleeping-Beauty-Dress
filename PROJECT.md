# Project: Sleeping Beauty Dress Firmware Overhaul

## Architecture
- **Target Hardware**: Seeed Studio XIAO ESP32-C3 (RISC-V 32-bit single-core @ 160MHz, 320KB SRAM, 4MB Flash).
- **Core Framework**: Arduino ESP32 Core v2.0.17 (ESP-IDF v4.4.7 base), compiled via PlatformIO (`env:seeed_xiao_esp32c3`).
- **Subsystems & Peripherals**:
  - **LED Subsystem (`LedController`)**: Driven by `makuna/NeoPixelBus @ ^2.8.4` using hardware RMT Channel 0 (`NeoEsp32Rmt0Ws2812xMethod`) on GPIO 4 (100 pixels, Skirt) and hardware RMT Channel 1 (`NeoEsp32Rmt1Ws2812xMethod`) on GPIO 5 (50 pixels, Upper Body & Sleeves). GPIO 6 is permanently disabled due to ESP32-C3 hardware limit of 2 RMT TX channels. Non-blocking hardware DMA/FIFO eliminates interrupt masking.
  - **IR Reception Subsystem (`IRController`)**: Dual 38KHz IR receivers on Left Shoulder (GPIO 3 / D1) and Right Shoulder (GPIO 2 / D0), powered from 3.3V rail. Edge-triggered GPIO interrupts (`attachInterrupt(..., CHANGE)`) with microsecond timestamping and double-buffering decode 56-bit MagiQuest packets with zero RMT channel or timer contention.
  - **Captive Portal Web Subsystem (`WebController`)**: SoftAP `Sleeping-Beauty-Dress` at `192.168.4.1` with port 53 DNS redirection. Serves mobile single-page control app from flash PROGMEM and handles REST endpoints.
  - **Persistent Storage Subsystem (`StorageController`)**: ESP32 Preferences (NVS) in namespace `auroradress`, storing 32-bit wand IDs (`pink_wand`, `blue_wand`).
  - **System Coordination (`main.cpp`)**: Deterministic boot sequence (Storage → LED dark init → IR → Web) and non-blocking cooperative round-robin loop.

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Replace FastLED with NeoPixelBus | Remove FastLED and bit-banging interrupt masking; integrate NeoPixelBus 2.8.4 | M1 | ORIGINAL_REQUEST §R1 |
| 2 | Phased Pin Architecture (GPIO 4 & 5) | GPIO 4 (100 LEDs, Skirt) via RMT 0; GPIO 5 (50 LEDs, Upper) via RMT 1; disable GPIO 6 | M1 | ORIGINAL_REQUEST §R1 |
| 3 | Power-On Dark Clamp (Zero White Lockup) | Hardware LOW clamp, internal pull-down, 350µs hold, synchronous blank push before WiFi | M1 | ORIGINAL_REQUEST §R1 |
| 4 | Visual Modes | OFF (black), PINK (`#FF1493`), BLUE (`#0078FF`), SPLOTCHES (duel + `#FFFFF0` sparkles), PAIRING_FEEDBACK (breathing) | M1 | ORIGINAL_REQUEST §R1 |
| 5 | Non-Blocking Throttled Rendering | ~40 FPS animation loop with delta-timing, master brightness scaling, and bus idling | M1 | ORIGINAL_REQUEST §R1 |
| 6 | 56-bit MagiQuest IR Decoding | Custom pulse-width timing decoder for 56-bit frames (8-bit preamble + 32-bit wand ID + 16-bit magnitude) and 48-bit fallback | M2 | ORIGINAL_REQUEST §R2 |
| 7 | Dual 38KHz IR Receivers | GPIO 3 (Left Shoulder) and GPIO 2 (Right Shoulder) 3.3V edge capture with ping-pong buffering | M2 | ORIGINAL_REQUEST §R2 |
| 8 | IR Event Dispatch | Pink wand -> PINK mode; Blue wand -> BLUE mode; rapid dual wands (within 2s) -> SPLOTCHES | M2 | ORIGINAL_REQUEST §R2 |
| 9 | Wand Pairing State Machine | 30s auto-timeout pairing mode for Pink or Blue wand with cancellation and visual feedback | M2 | ORIGINAL_REQUEST §R2 |
| 10 | Zero Resource Contention | Software GPIO interrupt capture with zero RMT or hardware timer collision with LED driver | M2 | ORIGINAL_REQUEST §R2 |
| 11 | SoftAP & Captive Portal | Open SSID `Sleeping-Beauty-Dress` at 192.168.4.1, DNS captive portal on port 53 with vendor redirects | M3 | ORIGINAL_REQUEST §R3 |
| 12 | Single-Page Mobile Web UI | Responsive HTML/CSS/JS in PROGMEM showing status, mode buttons, brightness slider, pairing controls | M3 | ORIGINAL_REQUEST §R3 |
| 13 | REST API Endpoints | `/api/status`, `/setPink`, `/setBlue`, `/setSplotches`, `/setOff`, `/register/pink`, `/register/blue`, `/register/cancel`, `/brightness`, `/setBrightness` | M3 | ORIGINAL_REQUEST §R3 |
| 14 | Preferences NVS Storage | Store & load paired 32-bit wand IDs in NVS namespace `auroradress` (`pink_wand`, `blue_wand`) | M4 | ORIGINAL_REQUEST §R4 |
| 15 | Boot Sequencing & Coordination | Storage -> LED dark -> IR -> Web boot sequence, non-blocking round-robin loop in `main.cpp` | M4 | ORIGINAL_REQUEST §R5 |
| 16 | PlatformIO Clean Build | `platformio.ini` cleanup, remove dead dependencies (`IRremoteESP8266`), verified `pio run` build | M4 | ORIGINAL_REQUEST §R5 |
| 17 | 100% E2E Test Suite & Adversarial Hardening | Pass all automated E2E tests (Tiers 1-4) and Tier 5 adversarial coverage hardening | M5 | ORIGINAL_REQUEST Acceptance Criteria |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | LED Subsystem Overhaul (`LedController`) | `platformio.ini`, `Config.h`, `LedController.h`, `LedController.cpp` | none | DONE |
| M2 | IR Subsystem Refinement (`IRController`) | `IRController.h`, `IRController.cpp`, `Config.h` | M1 | DONE |
| M3 | Captive Portal & Web UI (`WebController`) | `WebController.h`, `WebController.cpp` | M1 | DONE |
| M4 | Storage & System Coordination (`main.cpp`) | `StorageController.h`, `StorageController.cpp`, `main.cpp`, `platformio.ini` | M1, M2, M3 | DONE |
| M5 | Final Integration, 100% E2E Pass & Hardening | Full system E2E verification (Tiers 1-4) and Tier 5 adversarial stress testing | M4, E2E Test Suite | DONE |

## Interface Contracts
### `LedController`
- `void init()`: Clamps pins LOW, initializes NeoPixelBus on GPIO 4 and GPIO 5, clears all pixels to dark, displays first frame synchronously.
- `void update()`: Non-blocking frame update throttled to ~40 FPS (25ms interval). Updates animations for active visual mode.
- `void setMode(VisualMode mode)`: Switches active visual mode (`OFF`, `PINK`, `BLUE`, `SPLOTCHES`, `PAIRING_FEEDBACK`).
- `VisualMode getMode()`: Returns current active visual mode.
- `void setBrightness(uint8_t b)`: Sets master brightness (0-255).
- `uint8_t getBrightness()`: Returns current master brightness.
- `void triggerPairingFeedback()`: Enters `PAIRING_FEEDBACK` breathing pulse mode.

### `IRController`
- `void init()`: Configures GPIO 3 and GPIO 2 as `INPUT_PULLUP`, attaches CHANGE interrupts, initializes ping-pong buffers.
- `void update()`: Checks for completed raw pulse buffers, decodes 56-bit MagiQuest frames, evaluates pairing mode timeout (30s), handles rapid dual-wand detection (2s), dispatches mode changes to `LedController`.
- `void startPairing(WandType type)`: Enters pairing mode for Pink or Blue wand with 30s timeout.
- `void cancelPairing()`: Exits pairing mode without saving.
- `PairingState getPairingState()`: Returns active pairing state (`NONE`, `PAIRING_PINK`, `PAIRING_BLUE`).

### `WebController`
- `void init()`: Sets up SoftAP `Sleeping-Beauty-Dress` (192.168.4.1), starts DNS server on port 53, registers HTTP route handlers and captive portal redirects.
- `void update()`: Calls `dnsServer.processNextRequest()`.

### `StorageController`
- `void init()`: Opens Preferences in namespace `auroradress`, loads stored `pink_wand` and `blue_wand` IDs.
- `uint32_t getPinkWandId()`: Returns active Pink wand ID (0 if unconfigured).
- `uint32_t getBlueWandId()`: Returns active Blue wand ID (0 if unconfigured).
- `void savePinkWandId(uint32_t id)`: Persists Pink wand ID to NVS immediately.
- `void saveBlueWandId(uint32_t id)`: Persists Blue wand ID to NVS immediately.

## Code Layout
- `platformio.ini`: PlatformIO build configuration, target `seeed_xiao_esp32c3`, libraries: `makuna/NeoPixelBus @ ^2.8.4`, `mathieucarbou/ESPAsyncWebServer`.
- `include/Config.h`: System pin definitions, LED strip geometry, animation timings, AP and network constants.
- `include/LedController.h` / `src/LedController.cpp`: NeoPixelBus LED driver, procedural animations, throttled renderer.
- `include/IRController.h` / `src/IRController.cpp`: Dual-channel software interrupt pulse capture, 56-bit MagiQuest decoder, pairing state machine.
- `include/WebController.h` / `src/WebController.cpp`: SoftAP, DNS server, PROGMEM web portal, REST API endpoints.
- `include/StorageController.h` / `src/StorageController.cpp`: Preferences NVS wrapper for wand IDs.
- `src/main.cpp`: Firmware entrypoint, setup boot sequence, non-blocking polling loop.
