# Test Infrastructure & Specification: Sleeping Beauty Dress Firmware

## 1. Test Philosophy
The test infrastructure for the Sleeping Beauty Dress firmware adheres to strict **opaque-box, requirement-driven verification**:
- **Implementation Agnostic**: Tests are derived strictly from user requirements (`ORIGINAL_REQUEST.md`) and technical interface specifications (`PROJECT.md`, `spec.md`). Tests validate observable inputs, outputs, frame encodings, protocols, state machines, timing constraints, and hardware configuration invariants without depending on internal implementation private variables or transient compiler optimizations.
- **Progressive Testability**: Tests are partitioned by functional boundaries so each tier and subsystem can be independently evaluated during milestone development and full integration.
- **Deterministic Oracles**: Every test case references an authoritative specification oracle (e.g. 56-bit MagiQuest bitstream timings, standard CIE RGB color codes, NVS namespace and key schemas, HTTP/1.1 REST responses, and PlatformIO compilation parameters).
- **Adversarial & Fault Injection**: In addition to happy path behaviors, the suite exercises extreme edge cases, pulse timing jitter, buffer overflows, concurrent rapid inputs, network probe redirections, boundary clamping, and non-blocking scheduling bounds.

---

## 2. Test Methodology

The test suite applies four formal verification methodologies across four distinct test tiers:

### 2.1 Category-Partition Method (Tier 1: Feature Coverage)
Every feature among the 17 identified features in `PROJECT.md` is decomposed into distinct functional categories and equivalence classes. For each feature, at least 5 targeted test cases exercise:
1. Primary happy path functional operation.
2. Parameter variation within valid operating ranges.
3. Subsystem interface contract validation.
4. Nominal state transition.
5. Invariant preservation.

### 2.2 Boundary Value Analysis (Tier 2: Boundary & Corner Cases)
For each feature, boundary and stress conditions are identified at the extreme edges of valid and invalid domains:
1. Off-by-one and threshold values (e.g., pulse duration limits 650µs and 1750µs, 2000ms wand succession threshold, 30000ms pairing timeout).
2. Clamping and saturation boundaries (e.g., brightness values 0, 160, 255, >255).
3. Frame buffer and memory boundary limits (e.g., 100 pixels, 50 pixels, 0 pixels, buffer overflow clamping at 159).
4. Timing jitter tolerances (e.g., mark duty cycles at 30%, 35%, 38%).
5. Invalid/malformed input rejection (e.g., non-zero preambles, missing HTTP query parameters, empty payloads).

### 2.3 Pairwise Combinatorial Testing (Tier 3: Cross-Feature Interactions)
Features interact concurrently in an embedded real-time environment. Tier 3 evaluates pairwise feature intersections to guarantee zero resource contention and race-condition immunity:
- NeoPixelBus RMT transmission concurrent with GPIO IR edge interrupts.
- Web UI REST color overrides during active wand pairing mode.
- NVS flash write commit during active 40 FPS LED rendering.
- Captive portal DNS request bursts while handling rapid dual-wand succession.
- Rapid wand triggers while switching brightness levels.

### 2.4 Real-World Workload Scenarios (Tier 4: Operational Scenarios)
Tier 4 models multi-step end-to-end user journeys replicating real-world operational workflows:
- Cold boot sequence from power-on dark clamp through WiFi SoftAP and IR standby.
- Complete wand pairing workflow: web trigger -> physical wand detection -> NVS persistence -> breathing feedback -> solid color transition.
- Dueling wand interactive session: alternating Pink/Blue hits followed by simultaneous hits triggering dueling Splotches mode.
- Mobile phone connection and captive portal onboarding flow with vendor probe interception.
- Power cycle state restoration and persistence recovery.

---

## 3. Feature Coverage Matrix (17 Features across Tiers 1–4)

| # | Feature | Subsystem | Tier 1 (Feature) | Tier 2 (Boundaries) | Tier 3 (Cross-Feature) | Tier 4 (Real-World) |
|---|---------|-----------|------------------|---------------------|------------------------|---------------------|
| 1 | Replace FastLED with NeoPixelBus | LED / Build | 5 tests (`T1_F01_*`) | 5 tests (`T2_B01_*`) | Pairwise with IR / Web | Cold Boot Journey |
| 2 | Phased Pin Architecture (GPIO 4 & 5) | LED Hardware | 5 tests (`T1_F02_*`) | 5 tests (`T2_B02_*`) | Pairwise with RMT TX | Full Dress Lighting |
| 3 | Power-On Dark Clamp (Zero White Lockup) | LED Power | 5 tests (`T1_F03_*`) | 5 tests (`T2_B03_*`) | Pairwise with Boot Seq | Power Cycle Restore |
| 4 | Visual Modes (OFF, PINK, BLUE, SPLOTCHES) | LED Effects | 5 tests (`T1_F04_*`) | 5 tests (`T2_B04_*`) | Pairwise with REST API | Live Wand Duel Session |
| 5 | Non-Blocking Throttled Rendering (~40 FPS) | LED Engine | 5 tests (`T1_F05_*`) | 5 tests (`T2_B05_*`) | Pairwise with ISR Loop | Continuous Runtime |
| 6 | 56-Bit MagiQuest IR Decoding | IR Protocol | 5 tests (`T1_F06_*`) | 5 tests (`T2_B06_*`) | Pairwise with Dual Recv| Wand Signal Ingestion |
| 7 | Dual 38KHz IR Receivers (GPIO 2 & 3) | IR Hardware | 5 tests (`T1_F07_*`) | 5 tests (`T2_B07_*`) | Pairwise with Debounce | 360° Reception Stress |
| 8 | IR Event Dispatch (Pink, Blue, Splotches) | Interaction | 5 tests (`T1_F08_*`) | 5 tests (`T2_B08_*`) | Pairwise with LED Modes| Dueling Spell Clash |
| 9 | Wand Pairing State Machine (30s Timeout) | Pairing | 5 tests (`T1_F09_*`) | 5 tests (`T2_B09_*`) | Pairwise with Web / NVS| Complete Wand Pairing |
| 10 | Zero Resource Contention (No RMT Collision)| Hardware System | 5 tests (`T1_F10_*`) | 5 tests (`T2_B10_*`) | Pairwise with LED RMT | Full Concurrency Stress |
| 11 | SoftAP & Captive Portal (Port 53 DNS) | Networking | 5 tests (`T1_F11_*`) | 5 tests (`T2_B11_*`) | Pairwise with REST API | Mobile Portal Connect |
| 12 | Single-Page Mobile Web UI (PROGMEM) | Web UI | 5 tests (`T1_F12_*`) | 5 tests (`T2_B12_*`) | Pairwise with Status API| Phone Browser Session |
| 13 | REST API Endpoints (Control & Status) | REST API | 5 tests (`T1_F13_*`) | 5 tests (`T2_B13_*`) | Pairwise with LED Modes| Remote Control Stress |
| 14 | Preferences NVS Storage (`auroradress`) | NVS Flash | 5 tests (`T1_F14_*`) | 5 tests (`T2_B14_*`) | Pairwise with Pairing | Flash Persistence |
| 15 | Boot Sequencing & Coordination (`main.cpp`) | System | 5 tests (`T1_F15_*`) | 5 tests (`T2_B15_*`) | Pairwise with Polling | System Initialization |
| 16 | PlatformIO Clean Build (`pio run`) | Build System | 5 tests (`T1_F16_*`) | 5 tests (`T2_B16_*`) | Pairwise with Memory | Firmware Build & Sizing |
| 17 | 100% E2E Test Suite & Adversarial Hardening | QA / Test Infra | 5 tests (`T1_F17_*`) | 5 tests (`T2_B17_*`) | Pairwise with All Tiers| Systemic Stability |

**Test Count Breakdown**:
- **Tier 1 (Feature Coverage)**: 17 features × 5 tests = **85 tests**
- **Tier 2 (Boundary & Corner Cases)**: 17 features × 5 tests = **85 tests**
- **Tier 3 (Cross-Feature Combinations)**: 17 pairwise test cases = **17 tests**
- **Tier 4 (Real-World Scenarios)**: 9 comprehensive scenarios = **9 tests**
- **Total Test Count**: **196 tests**

---

## 4. Test Execution & Reporting Framework

The test suite is driven by `tests/run_tests.py`, an automated test runner designed for zero-dependency execution across both Python 2.7 and Python 3.x environments.
- **Execution Command**:
  ```powershell
  python tests/run_tests.py
  ```
  or
  ```powershell
  py -3 tests/run_tests.py
  ```
- **Reporting Output**:
  - Detailed test case result logging with test name, tier classification, execution status, and timing.
  - Subsystem breakdown and feature matrix summary.
  - Granular tier summaries (Tier 1, Tier 2, Tier 3, Tier 4).
  - Explicit pass/fail summary and non-zero exit code on failure.
