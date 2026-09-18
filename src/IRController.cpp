#include "IRController.h"
#include "Config.h"
#include "LedController.h"
#include "StorageController.h"
#include <driver/rmt.h>
#include <atomic>

// ============================================================================
// Capture Buffer & Hardware Timing Constants
// ============================================================================
static const uint16_t IR_BUF_SIZE    = 180;
static const uint16_t IR_RAW_TICK_US = 1; // RMT clock divided to 1us per tick

// ============================================================================
// Hardware RMT IR Receiver Channel
// ============================================================================
struct IRChannel {
    const char*     name;
    uint8_t         pin;
    rmt_channel_t   rmtChannel;
    RingbufHandle_t ringbuf;
    bool            initialized;
};

static IRChannel s_channelLeft  = { "Left Shoulder",  PIN_IR_RECV_LEFT,  RMT_RX_CHANNEL_LEFT,  nullptr, false };
static IRChannel s_channelRight = { "Right Shoulder", PIN_IR_RECV_RIGHT, RMT_RX_CHANNEL_RIGHT, nullptr, false };

static bool initRMTChannel(IRChannel& channel) {
    rmt_config_t config;
    config.rmt_mode                      = RMT_MODE_RX;
    config.channel                       = channel.rmtChannel;
    config.gpio_num                      = static_cast<gpio_num_t>(channel.pin);
    config.clk_div                       = RMT_CLK_DIV;
    config.mem_block_num                 = 1;
    config.rx_config.filter_en           = true;
    config.rx_config.filter_ticks_thresh = RMT_FILTER_TICKS_THRESH;
    config.rx_config.idle_threshold      = RMT_IDLE_THRESHOLD_TICKS;

    esp_err_t err = rmt_config(&config);
    if (err != ESP_OK) {
        Serial.printf("[IRController] ERROR: rmt_config failed for %s (ch %d, pin %d): %d\n",
                      channel.name, channel.rmtChannel, channel.pin, err);
        return false;
    }

    err = rmt_driver_install(channel.rmtChannel, RMT_RING_BUF_SIZE, 0);
    if (err != ESP_OK) {
        Serial.printf("[IRController] ERROR: rmt_driver_install failed for %s: %d\n",
                      channel.name, err);
        return false;
    }

    err = rmt_get_ringbuf_handle(channel.rmtChannel, &channel.ringbuf);
    if (err != ESP_OK || channel.ringbuf == nullptr) {
        Serial.printf("[IRController] ERROR: rmt_get_ringbuf_handle failed for %s: %d\n",
                      channel.name, err);
        return false;
    }

    err = rmt_rx_start(channel.rmtChannel, true);
    if (err != ESP_OK) {
        Serial.printf("[IRController] ERROR: rmt_rx_start failed for %s: %d\n",
                      channel.name, err);
        return false;
    }

    channel.initialized = true;
    return true;
}

// ============================================================================
// State Variables & Concurrency
// ============================================================================
static std::atomic<PairingMode> s_pairingMode{PairingMode::NONE};
static std::atomic<uint32_t>    s_pairingStartTime{0};
static std::atomic<uint32_t>    s_lastReceivedCode{0};

// Timestamps for debounce & rapid succession (accessed on main loop thread)
static uint32_t s_lastSignalTime = 0;
static uint32_t s_lastPinkTime   = 0;
static uint32_t s_lastBlueTime   = 0;

// Scratch buffer for safe decoding outside of interrupt context
static uint16_t s_decodeBuf[IR_BUF_SIZE];

// ============================================================================
// Robust MagiQuest Bitstream Decoder
// ============================================================================
// MagiQuest Bitstream Specification:
// - Bit period: ~1150us (Mark + Space)
// - Zero bit: Short Mark (~280us, ~24%), Long Space (~850us)
// - One bit: Long Mark (~580us, ~50%), Medium Space (~600us)
// - 56-bit payload: [8 bits header][32 bits Wand ID][16 bits Magnitude]
// - 48-bit payload: [32 bits Wand ID][16 bits Magnitude]
static bool decodeMagiQuestCustom(const uint16_t* rawbuf, uint16_t rawlen, uint32_t& wandId, uint16_t& magnitude) {
    if (!rawbuf || rawlen < 100) {
        return false;
    }

    const uint16_t kMinBitUs = 650;
    const uint16_t kMaxBitUs = 1750;

    // Scan for the start of a 56-bit frame, skipping any leading noise glitches
    uint16_t maxSearchOffset = (rawlen >= 111) ? (rawlen - 110) : 1;
    if (maxSearchOffset > 25) maxSearchOffset = 25;

    // --- Pass 1: Standard 56-bit MagiQuest frame with 8-bit 0x00 preamble ---
    for (uint16_t startOffset = 1; startOffset <= maxSearchOffset; startOffset++) {
        uint64_t data = 0;
        uint16_t bits = 0;
        uint16_t offset = startOffset;
        bool valid = true;

        while (offset + 1 < rawlen && bits < 56) {
            uint32_t markUs  = rawbuf[offset] * IR_RAW_TICK_US;
            uint32_t spaceUs = rawbuf[offset + 1] * IR_RAW_TICK_US;
            uint32_t totalUs = markUs + spaceUs;

            if (totalUs < kMinBitUs || totalUs > kMaxBitUs) {
                valid = false;
                break;
            }

            // Distinguish bit 0 (~25%) vs bit 1 (~50%) using 35% midpoint
            uint32_t markPercent = (markUs * 100) / totalUs;
            uint8_t bitVal = (markPercent >= 35) ? 1 : 0;

            data = (data << 1) | bitVal;
            bits++;
            offset += 2;

            // Fast rejection: First 8 bits must be 0x00 (preamble)
            if (bits == 8 && data != 0) {
                valid = false;
                break;
            }
        }

        // Account for final 56th bit whose trailing space is the silence timeout
        if (valid && bits == 55 && offset < rawlen) {
            uint32_t markUs = rawbuf[offset] * IR_RAW_TICK_US;
            if (markUs >= 150 && markUs <= 850) {
                uint8_t bitVal = (markUs >= 400) ? 1 : 0;
                data = (data << 1) | bitVal;
                bits++;
            }
        }

        if (valid && bits == 56) {
            // Strict preamble validation: top 8 bits MUST be 0x00
            if ((data >> 48) == 0x00) {
                uint32_t id = static_cast<uint32_t>((data >> 16) & 0xFFFFFFFFUL);
                if (id != 0) {
                    wandId = id;
                    magnitude = static_cast<uint16_t>(data & 0xFFFF);
                    return true;
                }
            }
        }
    }

    // --- Pass 2: Fallback for exact 48-bit frame (rare wands without preamble) ---
    for (uint16_t startOffset = 1; startOffset <= maxSearchOffset; startOffset++) {
        uint64_t data = 0;
        uint16_t bits = 0;
        uint16_t offset = startOffset;
        bool valid = true;

        while (offset + 1 < rawlen && bits < 48) {
            uint32_t markUs  = rawbuf[offset] * IR_RAW_TICK_US;
            uint32_t spaceUs = rawbuf[offset + 1] * IR_RAW_TICK_US;
            uint32_t totalUs = markUs + spaceUs;

            if (totalUs < kMinBitUs || totalUs > kMaxBitUs) {
                valid = false;
                break;
            }

            uint32_t markPercent = (markUs * 100) / totalUs;
            uint8_t bitVal = (markPercent >= 35) ? 1 : 0;

            data = (data << 1) | bitVal;
            bits++;
            offset += 2;
        }

        if (valid && bits == 47 && offset < rawlen) {
            uint32_t markUs = rawbuf[offset] * IR_RAW_TICK_US;
            if (markUs >= 150 && markUs <= 850) {
                uint8_t bitVal = (markUs >= 400) ? 1 : 0;
                data = (data << 1) | bitVal;
                bits++;
            }
        }

        if (valid && bits == 48) {
            uint32_t id = static_cast<uint32_t>((data >> 16) & 0xFFFFFFFFUL);
            if (id != 0) {
                wandId = id;
                magnitude = static_cast<uint16_t>(data & 0xFFFF);
                return true;
            }
        }
    }

    return false;
}

// ============================================================================
// Internal Event Processing
// ============================================================================
// ============================================================================
// Internal Event Processing via Hardware RMT
// ============================================================================
static void processChannelRMT(IRChannel& channel) {
    if (!channel.initialized || channel.ringbuf == nullptr) return;

    size_t rx_size = 0;
    // Non-blocking drain of the FreeRTOS ringbuffer filled by RMT hardware
    rmt_item32_t* items = static_cast<rmt_item32_t*>(xRingbufferReceive(channel.ringbuf, &rx_size, 0));
    if (items == nullptr || rx_size == 0) {
        return;
    }

    size_t num_items = rx_size / sizeof(rmt_item32_t);
    uint16_t sampleIdx = 1;
    s_decodeBuf[0] = 1; // Dummy entry at offset 0 to match decoder expectations

    for (size_t i = 0; i < num_items && sampleIdx < (IR_BUF_SIZE - 2); i++) {
        if (items[i].duration0 > 0) {
            s_decodeBuf[sampleIdx++] = items[i].duration0;
        }
        if (items[i].duration1 > 0) {
            s_decodeBuf[sampleIdx++] = items[i].duration1;
        }
    }

    // Return the item back to the FreeRTOS ring buffer
    vRingbufferReturnItem(channel.ringbuf, static_cast<void*>(items));

    // Immediately re-arm the RMT receiver for the next incoming transmission
    rmt_rx_start(channel.rmtChannel, true);

    if (sampleIdx < 100) {
        return;
    }

    uint32_t code = 0;
    uint16_t magnitude = 0;
    bool valid = decodeMagiQuestCustom(s_decodeBuf, sampleIdx, code, magnitude);

    uint32_t now = millis();

    if (valid && code != 0) {
        // Dual-sensor cross-talk & repeat burst debounce:
        // If the identical wand ID was received < 400ms ago on either shoulder, ignore duplicate
        if (code == s_lastReceivedCode.load(std::memory_order_relaxed) && (now - s_lastSignalTime < IR_DEBOUNCE_MS)) {
            return;
        }

        s_lastSignalTime = now;
        s_lastReceivedCode.store(code, std::memory_order_relaxed);

        Serial.printf("[IRController] %s: Decoded MagiQuest Wand ID = 0x%08X (Magnitude: %u)\n",
                      channel.name, code, magnitude);

        PairingMode currentPairing = s_pairingMode.load(std::memory_order_acquire);

        if (currentPairing == PairingMode::PINK) {
            StorageController::savePinkWandCode(code);
            s_pairingMode.store(PairingMode::NONE, std::memory_order_release);
            Serial.printf("[IRController] SUCCESS: Paired Pink Wand -> 0x%08X\n", code);
            LedController::showPairingFeedback(true);
        } else if (currentPairing == PairingMode::BLUE) {
            StorageController::saveBlueWandCode(code);
            s_pairingMode.store(PairingMode::NONE, std::memory_order_release);
            Serial.printf("[IRController] SUCCESS: Paired Blue Wand -> 0x%08X\n", code);
            LedController::showPairingFeedback(false);
        } else {
            // Operational mode matching
            uint32_t pinkCode = StorageController::getPinkWandCode();
            uint32_t blueCode = StorageController::getBlueWandCode();

            if (pinkCode != 0 && code == pinkCode) {
                Serial.printf("[IRController] %s: Pink Wand detected!\n", channel.name);
                s_lastPinkTime = now;

                if (s_lastBlueTime > 0 && (now - s_lastBlueTime <= WAND_RAPID_WINDOW_MS)) {
                    Serial.println(F("[IRController] Rapid succession detected -> Dueling Splotches!"));
                    LedController::triggerSplotches();
                    s_lastPinkTime = 0;
                    s_lastBlueTime = 0;
                } else {
                    LedController::setPink();
                }
            } else if (blueCode != 0 && code == blueCode) {
                Serial.printf("[IRController] %s: Blue Wand detected!\n", channel.name);
                s_lastBlueTime = now;

                if (s_lastPinkTime > 0 && (now - s_lastPinkTime <= WAND_RAPID_WINDOW_MS)) {
                    Serial.println(F("[IRController] Rapid succession detected -> Dueling Splotches!"));
                    LedController::triggerSplotches();
                    s_lastPinkTime = 0;
                    s_lastBlueTime = 0;
                } else {
                    LedController::setBlue();
                }
            } else {
                Serial.printf("[IRController] %s: Wand 0x%08X not matched to Pink (0x%08X) or Blue (0x%08X)\n",
                              channel.name, code, pinkCode, blueCode);
            }
        }
    } else if (sampleIdx >= 100) {
        // Log unrecognized full pulse burst for diagnosis
        Serial.printf("[IRController] %s: Unrecognized IR signal (%d samples). First pulses (us): ",
                      channel.name, sampleIdx);
        for (uint16_t i = 1; i < sampleIdx && i <= 8; i += 2) {
            Serial.printf("[M:%u S:%u] ", s_decodeBuf[i] * IR_RAW_TICK_US, s_decodeBuf[i + 1] * IR_RAW_TICK_US);
        }
        Serial.println();
    }
}

// ============================================================================
// Public Interface Implementation
// ============================================================================

void IRController::init() {
    // Configure internal pull-ups on IR receiver GPIO pins
    pinMode(PIN_IR_RECV_LEFT,  INPUT_PULLUP);
    pinMode(PIN_IR_RECV_RIGHT, INPUT_PULLUP);

    bool leftOk  = initRMTChannel(s_channelLeft);
    bool rightOk = initRMTChannel(s_channelRight);

    Serial.printf("[IRController] Hardware RMT IR Receivers initialized:\n");
    Serial.printf("               - Left Shoulder:  GPIO %d (D1), RMT Channel %d [%s]\n",
                  PIN_IR_RECV_LEFT, s_channelLeft.rmtChannel, leftOk ? "OK" : "FAILED");
    Serial.printf("               - Right Shoulder: GPIO %d (D0), RMT Channel %d [%s]\n",
                  PIN_IR_RECV_RIGHT, s_channelRight.rmtChannel, rightOk ? "OK" : "FAILED");
}

void IRController::update() {
    uint32_t now = millis();

    // 1. Check pairing mode timeout
    PairingMode currentPairing = s_pairingMode.load(std::memory_order_relaxed);
    if (currentPairing != PairingMode::NONE) {
        uint32_t elapsed = now - s_pairingStartTime.load(std::memory_order_relaxed);
        if (elapsed >= PAIRING_TIMEOUT_MS) {
            s_pairingMode.store(PairingMode::NONE, std::memory_order_release);
            Serial.println(F("[IRController] Pairing mode timed out"));
        }
    }

    // 2. Poll hardware RMT ring buffers on both channels (non-blocking)
    processChannelRMT(s_channelLeft);
    processChannelRMT(s_channelRight);
}

void IRController::startPairingPink() {
    s_pairingStartTime.store(millis(), std::memory_order_relaxed);
    s_pairingMode.store(PairingMode::PINK, std::memory_order_release);
    Serial.println(F("[IRController] Entering Pairing Mode for Pink Wand (awaiting wand flick on either shoulder...)"));
}

void IRController::startPairingBlue() {
    s_pairingStartTime.store(millis(), std::memory_order_relaxed);
    s_pairingMode.store(PairingMode::BLUE, std::memory_order_release);
    Serial.println(F("[IRController] Entering Pairing Mode for Blue Wand (awaiting wand flick on either shoulder...)"));
}

void IRController::cancelPairing() {
    s_pairingMode.store(PairingMode::NONE, std::memory_order_release);
    Serial.println(F("[IRController] Pairing Mode cancelled"));
}

PairingMode IRController::getPairingMode() {
    return s_pairingMode.load(std::memory_order_acquire);
}

bool IRController::isPairingActive() {
    return s_pairingMode.load(std::memory_order_acquire) != PairingMode::NONE;
}

uint32_t IRController::getLastReceivedCode() {
    return s_lastReceivedCode.load(std::memory_order_relaxed);
}
