# Sleeping-Beauty-Dress

This project creates an interactive, color-changing Princess Aurora Halloween dress using an ESP32-C3, WS2812B LEDs, and IR sensors to detect signals from MagiQuest wands.

## Architecture

The firmware is built using PlatformIO and the Arduino framework.

### Hardware
- **MCU**: Seeed Studio XIAO ESP32-C3
- **LEDs**: WS2812B Fairy String Lights (up to 150 LEDs across 3 segments/pins).
- **Sensors**: 2x KOOBOOK Digital 38KHz IR Receivers.
- **Power**: 5V USB battery bank.

### Software Controllers
The codebase is scaffolded into several controllers:
- `Config.h`: Centralizes all pin definitions, LED counts, and configuration variables.
- `LedController`: Uses the `FastLED` library to handle LED animations. Needs to support:
  - Turning all LEDs Pink.
  - Turning all LEDs Blue.
  - "Splotches" animation: Pseudo-random pink and blue splotches throughout the dress.
- `IRController`: Uses the `IRremoteESP8266` library to decode 38KHz IR signals.
- `WebController`: Uses `ESPAsyncWebServer` to stand up a WiFi Access Point and captive portal / web interface for a phone to connect. It needs to provide buttons to register wands and trigger animations manually.
- `StorageController`: Uses the ESP32 `Preferences` library to save and load registered wand IR codes from non-volatile storage (NVS).

## Agent Tasks

The goal for the agent team is to implement the logic for the scaffolded classes. 

**Requirements**:
1. Implement `StorageController` to save/load two 32-bit (or 64-bit depending on IR library) integer IR codes for the Pink and Blue wands.
2. Implement `IRController` to listen for IR signals. If a signal matches the saved Pink Wand code, trigger `LedController::setPink()`. If it matches the Blue Wand code, trigger `LedController::setBlue()`. If both are received in quick succession, trigger `LedController::triggerSplotches()`.
3. Implement `WebController` to serve a simple mobile-friendly HTML page. It should have buttons to:
   - "Register Pink Wand": Tells the `IRController` to treat the next received IR code as the Pink Wand and save it via `StorageController`.
   - "Register Blue Wand": Same, but for the Blue Wand.
   - Manual override buttons to set the dress to Pink, Blue, or Splotches.
4. Implement `LedController` using `FastLED` with 3 separate data pins for different dress segments (e.g. Skirt, Left Sleeve, Right Sleeve).
5. Ensure all code compiles successfully for the `seeed_xiao_esp32c3` environment.
