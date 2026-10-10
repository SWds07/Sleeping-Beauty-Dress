#include "LedController.h"
#include "Config.h"
#include "AnimMath.h"
#include <atomic>
#include <driver/gpio.h>

// ============================================================================
// NeoPixelBus Hardware RMT Driver Instances (ESP32-C3 RMT Channels 0 & 1)
// ============================================================================
// Skirt: 100 WS2812B pixels on GPIO 4 using RMT Channel 0
static NeoPixelBus<NeoGrbFeature, NeoEsp32Rmt0Ws2812xMethod> s_stripSkirt(NUM_LEDS_SKIRT, PIN_LED_SKIRT);

// Upper Body & Sleeves: 50 WS2812B pixels on GPIO 5 using RMT Channel 1
static NeoPixelBus<NeoGrbFeature, NeoEsp32Rmt1Ws2812xMethod> s_stripUpper(NUM_LEDS_UPPER, PIN_LED_UPPER);

// ============================================================================
// Internal Storage & Framebuffers
// ============================================================================
// Unscaled master RGB buffer in .bss (150 pixels = 450 bytes)
static RgbColor s_unscaledLeds[NUM_LEDS_TOTAL];

// Segment slice pointers into master buffer
static RgbColor* const s_skirtLeds = s_unscaledLeds + OFFSET_LED_SKIRT;
static RgbColor* const s_upperLeds = s_unscaledLeds + OFFSET_LED_UPPER;

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

// Persistent hardware state tracking: records what mode is currently rendered on physical LEDs
static LedMode s_renderedMode = static_cast<LedMode>(255);

// ============================================================================
// Public Interface Implementation
// ============================================================================

void LedController::earlyPinClamp() {
    pinMode(PIN_LED_SKIRT, OUTPUT);
    digitalWrite(PIN_LED_SKIRT, LOW);
    gpio_pulldown_en((gpio_num_t)PIN_LED_SKIRT);
    gpio_pullup_dis((gpio_num_t)PIN_LED_SKIRT);

    pinMode(PIN_LED_UPPER, OUTPUT);
    digitalWrite(PIN_LED_UPPER, LOW);
    gpio_pulldown_en((gpio_num_t)PIN_LED_UPPER);
    gpio_pullup_dis((gpio_num_t)PIN_LED_UPPER);

    delayMicroseconds(400);
}

void LedController::init() {
    Serial.println(F("[LedController] Initializing NeoPixelBus hardware RMT drivers..."));
    earlyPinClamp();

    // 1. Initialize NeoPixelBus RMT hardware peripherals
    s_stripSkirt.Begin();
    s_stripUpper.Begin();

    // 2. Synchronous dark clear push before WiFi or IR bringup (guarantees zero-white boot)
    s_stripSkirt.ClearTo(COLOR_DARK_BLACK);
    s_stripUpper.ClearTo(COLOR_DARK_BLACK);
    s_stripSkirt.Show();
    s_stripUpper.Show();

    while (!s_stripSkirt.CanShow() || !s_stripUpper.CanShow()) {
        delayMicroseconds(50);
    }
    delayMicroseconds(400);

    // 3. Clear master framebuffer
    for (uint16_t i = 0; i < NUM_LEDS_TOTAL; i++) {
        s_unscaledLeds[i] = COLOR_DARK_BLACK;
    }

    s_currentMode.store(LedMode::OFF, std::memory_order_release);
    s_needsRedraw.store(true, std::memory_order_release);
    s_renderedMode = static_cast<LedMode>(255);
    s_lastFrameTime = millis();
}

void LedController::pushPhysicalFrame() {
    uint8_t b = s_brightness.load(std::memory_order_relaxed);
    if (b > LED_MAX_BRIGHTNESS) {
        b = LED_MAX_BRIGHTNESS;
    }

    // Lossless integer brightness scaling: (c * brightness) / 255
    for (uint16_t i = 0; i < NUM_LEDS_SKIRT; i++) {
        RgbColor c = s_skirtLeds[i];
        uint8_t r = (uint8_t)(((uint16_t)c.R * b) / 255);
        uint8_t g = (uint8_t)(((uint16_t)c.G * b) / 255);
        uint8_t bl = (uint8_t)(((uint16_t)c.B * b) / 255);
        s_stripSkirt.SetPixelColor(i, RgbColor(r, g, bl));
    }

    for (uint16_t j = 0; j < NUM_LEDS_UPPER; j++) {
        RgbColor c = s_upperLeds[j];
        uint8_t r = (uint8_t)(((uint16_t)c.R * b) / 255);
        uint8_t g = (uint8_t)(((uint16_t)c.G * b) / 255);
        uint8_t bl = (uint8_t)(((uint16_t)c.B * b) / 255);
        s_stripUpper.SetPixelColor(j, RgbColor(r, g, bl));
    }

    // Non-blocking hardware push via RMT FIFO/DMA
    if (s_stripSkirt.CanShow() && s_stripUpper.CanShow()) {
        s_stripSkirt.Show();
        s_stripUpper.Show();
    }
}

void LedController::update() {
    uint32_t now = millis();

    // Non-blocking ~40 FPS frame throttling (25ms)
    if (now - s_lastFrameTime < LED_FRAME_INTERVAL_MS) {
        return;
    }
    s_lastFrameTime = now;

    // Check if brightness was updated asynchronously
    bool brightnessChanged = s_brightnessDirty.exchange(false, std::memory_order_acq_rel);

    LedMode mode = s_currentMode.load(std::memory_order_acquire);
    bool modeChanged = (mode != s_renderedMode);
    bool redrawRequested = s_needsRedraw.exchange(false, std::memory_order_acq_rel);
    bool shouldRedraw = modeChanged || brightnessChanged || redrawRequested;

    switch (mode) {
        case LedMode::OFF:
            if (shouldRedraw) {
                Serial.println(F("[LedController] Outputting OFF (Black) to GPIO 4 & 5"));
                for (uint16_t i = 0; i < NUM_LEDS_TOTAL; i++) {
                    s_unscaledLeds[i] = COLOR_DARK_BLACK;
                }
                pushPhysicalFrame();
                s_renderedMode = mode;
            }
            // Bus idling: static frames are not pushed continuously
            break;

        case LedMode::PINK:
            if (shouldRedraw) {
                Serial.println(F("[LedController] Outputting PINK to GPIO 4 & 5"));
                for (uint16_t i = 0; i < NUM_LEDS_TOTAL; i++) {
                    s_unscaledLeds[i] = COLOR_AURORA_PINK;
                }
                pushPhysicalFrame();
                s_renderedMode = mode;
            }
            // Bus idling: static frames are not pushed continuously
            break;

        case LedMode::BLUE:
            if (shouldRedraw) {
                Serial.println(F("[LedController] Outputting BLUE to GPIO 4 & 5"));
                for (uint16_t i = 0; i < NUM_LEDS_TOTAL; i++) {
                    s_unscaledLeds[i] = COLOR_AURORA_BLUE;
                }
                pushPhysicalFrame();
                s_renderedMode = mode;
            }
            // Bus idling: static frames are not pushed continuously
            break;

        case LedMode::SPLOTCHES:
            if (modeChanged) {
                Serial.println(F("[LedController] Running SPLOTCHES animation on GPIO 4 & 5"));
            }
            renderSplotchesFrame(now);
            pushPhysicalFrame();
            s_renderedMode = LedMode::SPLOTCHES;
            break;

        case LedMode::PAIRING_FEEDBACK:
            if (modeChanged) {
                Serial.println(F("[LedController] Running PAIRING_FEEDBACK animation on GPIO 4 & 5"));
            }
            renderPairingFeedbackFrame(now);
            pushPhysicalFrame();
            s_renderedMode = s_currentMode.load(std::memory_order_acquire);
            break;
    }
}

void LedController::setPink() {
    Serial.println(F("[LedController] Mode requested: PINK"));
    s_currentMode.store(LedMode::PINK, std::memory_order_release);
    s_needsRedraw.store(true, std::memory_order_release);
}

void LedController::setBlue() {
    Serial.println(F("[LedController] Mode requested: BLUE"));
    s_currentMode.store(LedMode::BLUE, std::memory_order_release);
    s_needsRedraw.store(true, std::memory_order_release);
}

void LedController::triggerSplotches() {
    Serial.println(F("[LedController] Mode requested: SPLOTCHES"));
    s_currentMode.store(LedMode::SPLOTCHES, std::memory_order_release);
    s_needsRedraw.store(true, std::memory_order_release);
}

void LedController::setOff() {
    Serial.println(F("[LedController] Mode requested: OFF"));
    s_currentMode.store(LedMode::OFF, std::memory_order_release);
    s_needsRedraw.store(true, std::memory_order_release);
}

void LedController::showPairingFeedback(bool isPink) {
    s_feedbackIsPink.store(isPink, std::memory_order_relaxed);
    s_feedbackStartTime.store(millis(), std::memory_order_relaxed);
    s_currentMode.store(LedMode::PAIRING_FEEDBACK, std::memory_order_release);
    s_needsRedraw.store(true, std::memory_order_release);
}

void LedController::triggerPairingFeedback(bool isPink) {
    showPairingFeedback(isPink);
}

void LedController::setMode(LedMode mode) {
    switch (mode) {
        case LedMode::OFF:              setOff(); break;
        case LedMode::PINK:             setPink(); break;
        case LedMode::BLUE:             setBlue(); break;
        case LedMode::SPLOTCHES:        triggerSplotches(); break;
        case LedMode::PAIRING_FEEDBACK: showPairingFeedback(true); break;
    }
}

LedMode LedController::getCurrentMode() {
    return s_currentMode.load(std::memory_order_acquire);
}

LedMode LedController::getMode() {
    return getCurrentMode();
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

RgbColor LedController::computeSplotchColor(uint8_t noise, uint8_t duelThreshold) {
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
    RgbColor color = blend(COLOR_AURORA_BLUE, COLOR_AURORA_PINK, t);

    // 3. Add spell clash highlight energy (peaks at center of clash)
    int16_t absDiff = abs(diff);
    uint8_t clashGlow = (uint8_t)(((SPLOTCH_BOUNDARY_WIDTH - absDiff) * 60) / SPLOTCH_BOUNDARY_WIDTH);
    color.R = qadd8(color.R, clashGlow);
    color.G = qadd8(color.G, clashGlow);
    color.B = qadd8(color.B, clashGlow);

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

    // 2. Upper Body & Sleeves (50 LEDs on PIN_LED_UPPER)
    for (uint16_t j = 0; j < NUM_LEDS_UPPER; j++) {
        uint16_t x = (uint16_t)(j * SPLOTCH_SLEEVE_SCALE) - (s_driftX >> 1);
        uint16_t y = 2000;
        uint8_t noise = inoise8(x, y, s_timeZ);
        s_upperLeds[j] = computeSplotchColor(noise, duelThreshold);
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
        RgbColor finalColor = isPink ? COLOR_AURORA_PINK : COLOR_AURORA_BLUE;
        for (uint16_t i = 0; i < NUM_LEDS_TOTAL; i++) {
            s_unscaledLeds[i] = finalColor;
        }
        s_needsRedraw.store(true, std::memory_order_release);
        return;
    }

    // 3 sinusoidal breathing pulses over 1500ms (500ms per cycle)
    uint32_t cycleElapsed = elapsed % PAIRING_CYCLE_MS;
    uint8_t phase = (uint8_t)((cycleElapsed * 256) / PAIRING_CYCLE_MS);
    uint8_t wave = sin8(phase);

    bool isPink = s_feedbackIsPink.load(std::memory_order_relaxed);
    RgbColor baseColor = isPink ? COLOR_AURORA_PINK : COLOR_AURORA_BLUE;
    RgbColor pulseColor(
        (uint8_t)(((uint16_t)baseColor.R * wave) / 255),
        (uint8_t)(((uint16_t)baseColor.G * wave) / 255),
        (uint8_t)(((uint16_t)baseColor.B * wave) / 255)
    );

    for (uint16_t i = 0; i < NUM_LEDS_TOTAL; i++) {
        s_unscaledLeds[i] = pulseColor;
    }

    // Sprinkle subtle pixie dust sparkles during pulse peaks
    if (wave > 180) {
        if (random8() < 20) {
            s_skirtLeds[random8(NUM_LEDS_SKIRT)] = COLOR_SPELL_SPARKLE;
        }
        if (random8() < 20) {
            s_upperLeds[random8(NUM_LEDS_UPPER)] = COLOR_SPELL_SPARKLE;
        }
    }
}
