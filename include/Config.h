#ifndef CONFIG_H
#define CONFIG_H

#include <stdint.h>
#include <driver/rmt.h>

// ============================================================================
// Hardware Pin Definitions (Seeed Studio XIAO ESP32-C3)
// ============================================================================
// GPIO 3 (D1 / A1): Digital input for Left Shoulder 38KHz IR receiver (VCC -> 3.3V)
// GPIO 2 (D0 / A0): Digital input for Right Shoulder 38KHz IR receiver (VCC -> 3.3V)
// NOTE: Power IR receivers from 3.3V rail (NOT 5V) to prevent ESD diode clamping & pulse distortion.
// GPIO 4 (D2 / A2): FastLED data line for Skirt (100 LEDs)
// GPIO 5 (D3 / A3): FastLED data line for Left Sleeve (25 LEDs)
// GPIO 6 (D4):      FastLED data line for Right Sleeve (25 LEDs)
#define PIN_IR_RECV_LEFT   3  // Left Shoulder IR Receiver (GPIO 3 / D1)
#define PIN_IR_RECV_RIGHT  2  // Right Shoulder IR Receiver (GPIO 2 / D0)
#define PIN_IR_RECV        PIN_IR_RECV_LEFT  // Compatibility alias

// ============================================================================
// Hardware RMT (Remote Control Transceiver) Configuration
// ============================================================================
// Channel assignments tailored for target MCU:
// - ESP32-C3: 4 total channels (0-1 TX, 2-3 RX) -> Left: Ch 2, Right: Ch 3
// - ESP32-S3: 8 total channels (0-3 TX, 4-7 RX) -> Left: Ch 4, Right: Ch 5
#if defined(CONFIG_IDF_TARGET_ESP32S3)
  #define RMT_RX_CHANNEL_LEFT   RMT_CHANNEL_4
  #define RMT_RX_CHANNEL_RIGHT  RMT_CHANNEL_5
#elif defined(CONFIG_IDF_TARGET_ESP32C3)
  #define RMT_RX_CHANNEL_LEFT   RMT_CHANNEL_2
  #define RMT_RX_CHANNEL_RIGHT  RMT_CHANNEL_3
#else
  #define RMT_RX_CHANNEL_LEFT   RMT_CHANNEL_0
  #define RMT_RX_CHANNEL_RIGHT  RMT_CHANNEL_1
#endif

// RMT clock divider: 80MHz APB clock / 80 = 1MHz -> 1 tick = 1 microsecond (us)
#define RMT_CLK_DIV               80
// Silicon hardware filter: ignore noise spikes shorter than 80us
#define RMT_FILTER_TICKS_THRESH   80
// Silicon hardware idle threshold: 3500us of silence terminates RX burst
#define RMT_IDLE_THRESHOLD_TICKS  3500
// Ringbuffer capacity per channel in bytes (holds multiple complete frames)
#define RMT_RING_BUF_SIZE         1024

#define PIN_LED_SKIRT   4
#define PIN_LED_LSLEEVE 5
#define PIN_LED_RSLEEVE 6

// ============================================================================
// LED Geometry Configuration
// ============================================================================
#define NUM_LEDS_SKIRT   100
#define NUM_LEDS_LSLEEVE 25
#define NUM_LEDS_RSLEEVE 25
#define NUM_LEDS_TOTAL   150

// Buffer slice offsets within master buffer
#define OFFSET_LED_SKIRT   0
#define OFFSET_LED_LSLEEVE (NUM_LEDS_SKIRT)                    // 100
#define OFFSET_LED_RSLEEVE (NUM_LEDS_SKIRT + NUM_LEDS_LSLEEVE) // 125

// ============================================================================
// FastLED Setup & Power Management
// ============================================================================
#define LED_CHIPSET            WS2812B
#define LED_COLOR_ORDER        GRB
#define LED_DEFAULT_BRIGHTNESS 160   // Baseline brightness (~63% of 255)
#define LED_MAX_VOLTS          5     // 5V WS2812B power rail
#define LED_MAX_MILLIAMPS      1500  // Maximum current cap to prevent battery brownout

// Compatibility aliases
#define LED_MAX_BRIGHTNESS      LED_DEFAULT_BRIGHTNESS
#define LED_POWER_VOLTS         LED_MAX_VOLTS
#define LED_POWER_MAX_MILLIAMPS LED_MAX_MILLIAMPS

// ============================================================================
// Animation & Frame Rate Configuration
// ============================================================================
#define ANIMATION_FPS      40  // Target 40 FPS
#define ANIMATION_FRAME_MS 25  // 25ms per frame (1000 / ANIMATION_FPS)

// Compatibility aliases
#define LED_TARGET_FPS        ANIMATION_FPS
#define LED_FRAME_INTERVAL_MS ANIMATION_FRAME_MS

// ============================================================================
// Splotches Procedural Tuning Parameters
// ============================================================================
#define SPLOTCH_SKIRT_SCALE    26  // Spatial frequency along skirt (10 cells / 100 LEDs)
#define SPLOTCH_SLEEVE_SCALE   32  // Spatial frequency along sleeves (3 cells / 25 LEDs)
#define SPLOTCH_DRIFT_SPEED    3   // Turbulent advection drift speed per frame
#define SPLOTCH_MORPH_SPEED    2   // 3D noise time evolution speed per frame
#define SPLOTCH_BOUNDARY_WIDTH 14  // Boundary transition half-width (anti-aliased clash zone)
#define SPLOTCH_DUEL_BPM       7   // BPM of the dueling spell power shift (~8.5s cycle)
#define SPLOTCH_SPARKLE_CHANCE 2   // Pixie dust sparkle chance (out of 255, ~0.8%)

// ============================================================================
// Pairing Feedback Timing
// ============================================================================
#define PAIRING_FEEDBACK_MS 1500  // 1.5 seconds total feedback duration
#define PAIRING_CYCLE_MS    500   // 3 breathing cycles of 500ms each

// Compatibility aliases
#define PAIRING_FEEDBACK_DURATION_MS PAIRING_FEEDBACK_MS
#define PAIRING_FEEDBACK_CYCLE_MS    PAIRING_CYCLE_MS

// ============================================================================
// Wand & IR Constants
// ============================================================================
#define WAND_RAPID_WINDOW_MS 2000   // Window to detect both wands -> Splotches
#define IR_DEBOUNCE_MS       400    // Minimum interval between repeated wand triggers
#define PAIRING_TIMEOUT_MS   30000  // Inactivity timeout for wand pairing mode (30s)

// ============================================================================
// WiFi SoftAP & Web Portal Defaults
// ============================================================================
#define WIFI_AP_SSID     "Sleeping-Beauty-Dress"
#define WIFI_AP_PASSWORD ""   // Open access point
#define HTTP_PORT        80   // HTTP web server port
#define DNS_PORT         53   // DNS captive portal port

// Compatibility aliases
#define WIFI_AP_PASS        WIFI_AP_PASSWORD
#define HTTP_SERVER_PORT    HTTP_PORT
#define CAPTIVE_PORTAL_PORT DNS_PORT

#endif // CONFIG_H
