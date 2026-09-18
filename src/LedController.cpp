#include "LedController.h"
#include "Config.h"
#include <atomic>

// ============================================================================
// Internal Storage & Framebuffers
// ============================================================================
// Contiguous master buffer of 150 CRGB pixels in .bss (450 bytes)
static CRGB s_leds[NUM_LEDS_TOTAL];

// Pointers to the individual dress segment slices
static CRGB* const s_skirtLeds   = s_leds + OFFSET_LED_SKIRT;
static CRGB* const s_lsleeveLeds = s_leds + OFFSET_LED_LSLEEVE;
static CRGB* const s_rsleeveLeds = s_leds + OFFSET_LED_RSLEEVE;

// ============================================================================
// Thread-Safe State Variables (safe across loopTask and async_tcp task)
// ============================================================================
static std::atomic<LedMode> s_currentMode{LedMode::OFF};
static std::atomic<bool>    s_needsRedraw{false};
static std::atomic<uint8_t> s_brightness{LED_DEFAULT_BRIGHTNESS};
static std::atomic<bool>    s_brightnessDirty{false};

// Pairing feedback animation state
static std::atomic<bool>     s_feedbackIsPink{true};
static std::atomic<uint32_t> s_feedbackStartTime{0};

// Local loop frame timing (accessed exclusively on the main loop thread)
static uint32_t s_lastFrameTime = 0;

// ============================================================================
// Public Interface Implementation
// ============================================================================

void LedController::init() {
    // 1. Register FastLED controllers for all three hardware pins
    FastLED.addLeds<LED_CHIPSET, PIN_LED_SKIRT, LED_COLOR_ORDER>(s_skirtLeds, NUM_LEDS_SKIRT);
    FastLED.addLeds<LED_CHIPSET, PIN_LED_LSLEEVE, LED_COLOR_ORDER>(s_lsleeveLeds, NUM_LEDS_LSLEEVE);
    FastLED.addLeds<LED_CHIPSET, PIN_LED_RSLEEVE, LED_COLOR_ORDER>(s_rsleeveLeds, NUM_LEDS_RSLEEVE);

    // 2. Configure power management and baseline brightness
    FastLED.setMaxPowerInVoltsAndMilliamps(LED_MAX_VOLTS, LED_MAX_MILLIAMPS);
    FastLED.setBrightness(s_brightness.load(std::memory_order_relaxed));

    // 3. Clear all LEDs to OFF at power-on
    fill_solid(s_leds, NUM_LEDS_TOTAL, CRGB::Black);
    FastLED.show();

    s_currentMode.store(LedMode::OFF, std::memory_order_release);
    s_needsRedraw.store(false, std::memory_order_release);
}

void LedController::update() {
    uint32_t now = millis();

    // Non-blocking 40 FPS frame throttling (25ms)
    if (now - s_lastFrameTime < ANIMATION_FRAME_MS) {
        return;
    }
    s_lastFrameTime = now;

    // Check if brightness was updated asynchronously
    bool brightnessChanged = s_brightnessDirty.exchange(false, std::memory_order_acq_rel);
    if (brightnessChanged) {
        FastLED.setBrightness(s_brightness.load(std::memory_order_relaxed));
    }

    // Persistent hardware state tracking: records what is currently displayed on physical LEDs
    static LedMode s_renderedMode = static_cast<LedMode>(255);

    LedMode mode = s_currentMode.load(std::memory_order_acquire);
    bool modeChanged = (mode != s_renderedMode);
    bool redrawRequested = s_needsRedraw.exchange(false, std::memory_order_acq_rel);
    bool shouldRedraw = modeChanged || brightnessChanged || redrawRequested;

    switch (mode) {
        case LedMode::OFF:
            if (shouldRedraw) {
                fill_solid(s_leds, NUM_LEDS_TOTAL, CRGB::Black);
                FastLED.show();
                s_renderedMode = mode;
            }
            break;

        case LedMode::PINK:
            if (shouldRedraw) {
                fill_solid(s_leds, NUM_LEDS_TOTAL, COLOR_AURORA_PINK);
                FastLED.show();
                s_renderedMode = mode;
            }
            break;

        case LedMode::BLUE:
            if (shouldRedraw) {
                fill_solid(s_leds, NUM_LEDS_TOTAL, COLOR_AURORA_BLUE);
                FastLED.show();
                s_renderedMode = mode;
            }
            break;

        case LedMode::SPLOTCHES:
            renderSplotchesFrame(now);
            FastLED.show();
            s_renderedMode = LedMode::SPLOTCHES;
            // CRITICALLY: REMOVE s_needsRedraw.store(false) so asynchronous mode triggers are never clobbered!
            break;

        case LedMode::PAIRING_FEEDBACK:
            renderPairingFeedbackFrame(now);
            FastLED.show();
            s_renderedMode = s_currentMode.load(std::memory_order_acquire);
            break;
    }
}

void LedController::setPink() {
    s_currentMode.store(LedMode::PINK, std::memory_order_release);
    s_needsRedraw.store(true, std::memory_order_release);
}

void LedController::setBlue() {
    s_currentMode.store(LedMode::BLUE, std::memory_order_release);
    s_needsRedraw.store(true, std::memory_order_release);
}

void LedController::triggerSplotches() {
    s_currentMode.store(LedMode::SPLOTCHES, std::memory_order_release);
    s_needsRedraw.store(true, std::memory_order_release);
}

void LedController::setOff() {
    s_currentMode.store(LedMode::OFF, std::memory_order_release);
    s_needsRedraw.store(true, std::memory_order_release);
}

void LedController::showPairingFeedback(bool isPink) {
    s_feedbackIsPink.store(isPink, std::memory_order_relaxed);
    s_feedbackStartTime.store(millis(), std::memory_order_relaxed);
    s_currentMode.store(LedMode::PAIRING_FEEDBACK, std::memory_order_release);
    s_needsRedraw.store(true, std::memory_order_release);
}

LedMode LedController::getCurrentMode() {
    return s_currentMode.load(std::memory_order_acquire);
}

const char* LedController::getModeString() {
    switch (s_currentMode.load(std::memory_order_acquire)) {
        case LedMode::OFF:              return "OFF";
        case LedMode::PINK:             return "PINK";
        case LedMode::BLUE:             return "BLUE";
        case LedMode::SPLOTCHES:        return "SPLOTCHES";
        case LedMode::PAIRING_FEEDBACK: return "PAIRING_FEEDBACK";
        default:                        return "UNKNOWN";
    }
}

void LedController::setBrightness(uint8_t brightness) {
    if (brightness > LED_MAX_BRIGHTNESS) {
        brightness = LED_MAX_BRIGHTNESS;
    }
    s_brightness.store(brightness, std::memory_order_relaxed);
    s_brightnessDirty.store(true, std::memory_order_release);
}

uint8_t LedController::getBrightness() {
    return s_brightness.load(std::memory_order_relaxed);
}

// ============================================================================
// Internal Rendering Implementations
// ============================================================================

CRGB LedController::computeSplotchColor(uint8_t noise, uint8_t duelThreshold) {
    int16_t diff = (int16_t)noise - (int16_t)duelThreshold;

    // Pure Aurora Pink territory (Flora dominant)
    if (diff > SPLOTCH_BOUNDARY_WIDTH) {
        if (random8() < SPLOTCH_SPARKLE_CHANCE) {
            return COLOR_SPELL_SPARKLE;
        }
        return COLOR_AURORA_PINK;
    }

    // Pure Merryweather Blue territory (Merryweather dominant)
    if (diff < -SPLOTCH_BOUNDARY_WIDTH) {
        if (random8() < SPLOTCH_SPARKLE_CHANCE) {
            return COLOR_SPELL_SPARKLE;
        }
        return COLOR_AURORA_BLUE;
    }

    // Dueling boundary clash zone: [-SPLOTCH_BOUNDARY_WIDTH, +SPLOTCH_BOUNDARY_WIDTH]
    // 1. Calculate interpolation factor t: 0 (pure blue) to 255 (pure pink)
    uint8_t t = (uint8_t)(((diff + SPLOTCH_BOUNDARY_WIDTH) * 255) / (2 * SPLOTCH_BOUNDARY_WIDTH));

    // 2. Base blend passing through magical iridescent violet
    CRGB color = blend(COLOR_AURORA_BLUE, COLOR_AURORA_PINK, t);

    // 3. Add spell clash highlight energy (peaks at center of clash)
    int16_t absDiff = abs(diff);
    uint8_t clashGlow = (uint8_t)(((SPLOTCH_BOUNDARY_WIDTH - absDiff) * 60) / SPLOTCH_BOUNDARY_WIDTH);
    color.r = qadd8(color.r, clashGlow);
    color.g = qadd8(color.g, clashGlow);
    color.b = qadd8(color.b, clashGlow);

    // 4. Boundary sparkles (higher probability at active spell collision)
    if (random8() < (SPLOTCH_SPARKLE_CHANCE * 3)) {
        return COLOR_SPELL_SPARKLE;
    }

    return color;
}

void LedController::renderSplotchesFrame(uint32_t now) {
    static uint16_t s_timeZ = 0;
    static uint16_t s_driftX = 0;

    s_timeZ += SPLOTCH_MORPH_SPEED;
    s_driftX += SPLOTCH_DRIFT_SPEED;

    // Dynamic dueling bias oscillating over ~8.5 seconds (7 BPM)
    uint8_t duelThreshold = beatsin8(SPLOTCH_DUEL_BPM, 92, 164);

    // 1. Skirt (100 LEDs on PIN_LED_SKIRT)
    for (uint16_t i = 0; i < NUM_LEDS_SKIRT; i++) {
        uint16_t x = (uint16_t)(i * SPLOTCH_SKIRT_SCALE) + s_driftX;
        uint16_t y = 0;
        uint8_t noise = inoise8(x, y, s_timeZ);
        s_skirtLeds[i] = computeSplotchColor(noise, duelThreshold);
    }

    // 2. Left Sleeve (25 LEDs on PIN_LED_LSLEEVE) - Y=2000, counter-drift
    for (uint16_t j = 0; j < NUM_LEDS_LSLEEVE; j++) {
        uint16_t x = (uint16_t)(j * SPLOTCH_SLEEVE_SCALE) - (s_driftX >> 1);
        uint16_t y = 2000;
        uint8_t noise = inoise8(x, y, s_timeZ);
        s_lsleeveLeds[j] = computeSplotchColor(noise, duelThreshold);
    }

    // 3. Right Sleeve (25 LEDs on PIN_LED_RSLEEVE) - Y=4000, forward drift
    for (uint16_t k = 0; k < NUM_LEDS_RSLEEVE; k++) {
        uint16_t x = (uint16_t)(k * SPLOTCH_SLEEVE_SCALE) + (s_driftX >> 1);
        uint16_t y = 4000;
        uint8_t noise = inoise8(x, y, s_timeZ);
        s_rsleeveLeds[k] = computeSplotchColor(noise, duelThreshold);
    }
}

void LedController::renderPairingFeedbackFrame(uint32_t now) {
    uint32_t startTime = s_feedbackStartTime.load(std::memory_order_relaxed);
    uint32_t elapsed = now - startTime;
    if (elapsed > 0x80000000UL) elapsed = 0;

    if (elapsed >= PAIRING_FEEDBACK_MS) {
        // Feedback duration expired; transition automatically to paired wand color
        bool isPink = s_feedbackIsPink.load(std::memory_order_relaxed);
        LedMode nextMode = isPink ? LedMode::PINK : LedMode::BLUE;
        s_currentMode.store(nextMode, std::memory_order_release);
        fill_solid(s_leds, NUM_LEDS_TOTAL, isPink ? COLOR_AURORA_PINK : COLOR_AURORA_BLUE);
        return;
    }

    // 3 sinusoidal breathing pulses over 1500ms (500ms per cycle)
    uint32_t cycleElapsed = elapsed % PAIRING_CYCLE_MS;
    uint8_t phase = (uint8_t)((cycleElapsed * 256) / PAIRING_CYCLE_MS);
    uint8_t wave = sin8(phase);

    bool isPink = s_feedbackIsPink.load(std::memory_order_relaxed);
    CRGB baseColor = isPink ? COLOR_AURORA_PINK : COLOR_AURORA_BLUE;
    CRGB pulseColor = baseColor;
    pulseColor.nscale8_video(wave);

    fill_solid(s_skirtLeds, NUM_LEDS_SKIRT, pulseColor);
    fill_solid(s_lsleeveLeds, NUM_LEDS_LSLEEVE, pulseColor);
    fill_solid(s_rsleeveLeds, NUM_LEDS_RSLEEVE, pulseColor);

    // Sprinkle subtle pixie dust sparkles during pulse peaks
    if (wave > 180) {
        if (random8() < 20) s_skirtLeds[random8(NUM_LEDS_SKIRT)] = COLOR_SPELL_SPARKLE;
        if (random8() < 10) s_lsleeveLeds[random8(NUM_LEDS_LSLEEVE)] = COLOR_SPELL_SPARKLE;
        if (random8() < 10) s_rsleeveLeds[random8(NUM_LEDS_RSLEEVE)] = COLOR_SPELL_SPARKLE;
    }
}
