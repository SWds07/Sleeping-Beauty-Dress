#ifndef LED_CONTROLLER_H
#define LED_CONTROLLER_H

#include <Arduino.h>
#include <NeoPixelBus.h>
#include <stdint.h>
#include "Config.h"
#include "AnimMath.h"

// ============================================================================
// Princess Aurora & Merryweather Color Palette (NeoPixelBus RgbColor)
// ============================================================================
#define COLOR_AURORA_PINK   RgbColor(255, 20, 147)  // Princess Aurora Deep Pink (#FF1493)
#define COLOR_AURORA_BLUE   RgbColor(0, 120, 255)   // Merryweather Vivid Royal Blue (#0078FF)
#define COLOR_SPELL_SPARKLE RgbColor(255, 255, 240) // Fairy Dust Gold/White Sparkle (#FFFFF0)
#define COLOR_DARK_BLACK    RgbColor(0, 0, 0)       // Dark / Off (#000000)

/**
 * @brief LED operational modes for the Sleeping Beauty Dress
 */
enum class LedMode : uint8_t {
    OFF = 0,
    PINK,
    BLUE,
    SPLOTCHES,
    PAIRING_FEEDBACK
};

using VisualMode = LedMode;

/**
 * @brief Controller for 150 WS2812B LEDs across 2 hardware RMT channels (Skirt GPIO 4, Upper GPIO 5)
 */
class LedController {
public:
    /**
     * @brief Early hardware pin clamp and pulldown to prevent floating gate lockup at cold boot.
     * Enforces >=400µs reset hold prior to driver bringup.
     */
    static void earlyPinClamp();

    /**
     * @brief Initializes NeoPixelBus hardware RMT drivers on GPIO 4 and GPIO 5,
     * clears all pixels to dark, and performs synchronous initial show before WiFi bringup.
     */
    static void init();

    /**
     * @brief Non-blocking frame update routine called in loop().
     * Throttles rendering to ~40 FPS (25ms) using non-blocking millis() timer.
     * Static modes push once and idle RMT bus; animations update each frame.
     */
    static void update();

    // Mode triggers (thread-safe, lock-free)
    static void setPink();
    static void setBlue();
    static void triggerSplotches();
    static void setOff();
    static void showPairingFeedback(bool isPink = true);
    static void triggerPairingFeedback(bool isPink = true);
    static void setMode(LedMode mode);

    // Mode and State Inspection
    static LedMode getCurrentMode();
    static LedMode getMode();
    static const char* getModeString();

    // Brightness Control
    static void setBrightness(uint8_t brightness);
    static uint8_t getBrightness();

private:
    // Internal rendering routines (executed strictly on the main loop thread)
    static void renderSplotchesFrame(uint32_t now);
    static void renderPairingFeedbackFrame(uint32_t now);
    static RgbColor computeSplotchColor(uint8_t noise, uint8_t duelThreshold);
    static void pushPhysicalFrame();
};

#endif // LED_CONTROLLER_H
