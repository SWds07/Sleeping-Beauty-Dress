#ifndef LED_CONTROLLER_H
#define LED_CONTROLLER_H

#include <Arduino.h>
#include <FastLED.h>
#include <stdint.h>

// ============================================================================
// Princess Aurora & Merryweather Color Palette
// ============================================================================
#define COLOR_AURORA_PINK   CRGB(255, 20, 147)  // Princess Aurora Deep Pink (#FF1493)
#define COLOR_AURORA_BLUE   CRGB(0, 120, 255)   // Merryweather Vivid Royal Blue (#0078FF)
#define COLOR_SPELL_SPARKLE CRGB(255, 255, 240) // Fairy Dust Gold/White Sparkle

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

/**
 * @brief Controller for 150 WS2812B LEDs across 3 dress segments (Skirt, Left Sleeve, Right Sleeve)
 */
class LedController {
public:
    /**
     * @brief Initializes FastLED controllers across 3 hardware pins,
     * configures power limits (5V, 1500mA), and clears all LEDs.
     */
    static void init();

    /**
     * @brief Non-blocking frame update routine called in loop().
     * Throttles rendering to 40 FPS (25ms) using non-blocking millis() timer.
     * Static modes push once and idle RMT; animations update each frame.
     */
    static void update();

    // Mode triggers (thread-safe, lock-free)
    static void setPink();
    static void setBlue();
    static void triggerSplotches();
    static void setOff();
    static void showPairingFeedback(bool isPink);

    // Mode and State Inspection
    static LedMode getCurrentMode();
    static const char* getModeString();

    // Brightness Control
    static void setBrightness(uint8_t brightness);
    static uint8_t getBrightness();

private:
    // Internal rendering routines (executed strictly on the main loop thread)
    static void renderSplotchesFrame(uint32_t now);
    static void renderPairingFeedbackFrame(uint32_t now);
    static CRGB computeSplotchColor(uint8_t noise, uint8_t duelThreshold);
};

#endif // LED_CONTROLLER_H
