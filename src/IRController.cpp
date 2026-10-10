#include "IRController.h"
#include "Config.h"
#include "LedController.h"
#include "StorageController.h"
#include <esp_timer.h>
#include <atomic>

// ============================================================================
// Capture Buffer & Hardware Timing Constants
// ============================================================================
// Each 56-bit MagiQuest frame consists of 112 transitions (56 marks + 56 spaces).
// 160 entries provides ample headroom for leading/trailing noise or jitter.
static const uint16_t IR_BUF_SIZE           = 160;
// Inter-packet silence timeout: 3500us (3.5ms).
// Intra-packet spaces are <= 1000us; inter-burst gaps are >= 10ms.
// 3.5ms cleanly isolates bursts and delivers instantaneous response.
static const uint32_t IR_SILENCE_TIMEOUT_US = 3500;
static const uint16_t IR_RAW_TICK_US        = 2;    // 2us resolution per sample unit

// ============================================================================
// Dual-Buffered IR Receiver Channel
// ============================================================================
// Using ping-pong buffers prevents incoming repeat bursts from overwriting
// or corrupting the packet currently being read/decoded by the main loop.
struct IRChannel {
    const char*       name;
    uint8_t           pin;
    volatile uint16_t rawbuf[2][IR_BUF_SIZE];
    volatile uint16_t rawlen[2];
    volatile uint8_t  activeBuf;   // Buffer currently written by ISR (0 or 1)
    volatile uint8_t  readyBuf;    // Buffer ready for decoding (0, 1, or 255 if none)
    volatile uint32_t lastEdgeUs;
    volatile bool     capturing;

    void IRAM_ATTR handleEdge() {
        uint32_t now = static_cast<uint32_t>(esp_timer_get_time());
        if (!capturing) {
            capturing   = true;
            uint8_t b   = activeBuf;
            rawlen[b]   = 1;
            rawbuf[b][0]= 1; // Dummy entry at offset 0
            lastEdgeUs  = now;
        } else {
            uint32_t delta = now - lastEdgeUs;
            lastEdgeUs     = now;
            uint8_t b      = activeBuf;

            // Check if delta indicates an inter-packet gap (>= 3.5ms silence)
            if (delta >= IR_SILENCE_TIMEOUT_US) {
                // The previous burst finished before this new edge arrived
                if (rawlen[b] >= 100) {
                    readyBuf  = b;
                    activeBuf = 1 - b;
                    b         = activeBuf;
                }
                // Start capturing the new incoming packet
                rawlen[b]    = 1;
                rawbuf[b][0] = 1;
                capturing    = true;
                return;
            }

            if (rawlen[b] < (IR_BUF_SIZE - 1)) {
                rawbuf[b][rawlen[b]++] = static_cast<uint16_t>(delta / IR_RAW_TICK_US);
            }
        }
    }

    void checkTimeout(uint32_t nowUs) {
        // Fast lock-free pre-check: avoid interrupt disabling if not timed out
        if (!capturing || (nowUs - lastEdgeUs < IR_SILENCE_TIMEOUT_US)) {
            return;
        }

        // Micro-critical section (<30ns): eliminate race condition with handleEdge() ISR
        noInterrupts();
        if (capturing && (nowUs - lastEdgeUs >= IR_SILENCE_TIMEOUT_US)) {
            capturing = false;
            uint8_t b = activeBuf;
            if (rawlen[b] >= 100) {
                readyBuf          = b;
                activeBuf         = 1 - b;
                rawlen[activeBuf] = 0;
            } else {
                rawlen[b] = 0;
            }
        }
        interrupts();
    }
};

static IRChannel s_channelLeft  = { "Left Shoulder",  PIN_IR_RECV_LEFT,  {{0}}, {0, 0}, 0, 255, 0, false };
static IRChannel s_channelRight = { "Right Shoulder", PIN_IR_RECV_RIGHT, {{0}}, {0, 0}, 0, 255, 0, false };

// Fast Interrupt Service Routines
static void IRAM_ATTR isrLeft() {
    s_channelLeft.handleEdge();
}

static void IRAM_ATTR isrRight() {
    s_channelRight.handleEdge();
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
// High-Performance MagiQuest Bitstream Decoder
// ============================================================================
// MagiQuest Bitstream Specification:
// - Bit period: ~1120-1150us (Mark + Space)
// - Zero bit: Short Mark (~280us, ~25%), Long Space (~840us)
// - One bit: Long Mark (~560us, ~50%), Medium Space (~560us)
// - 56-bit payload: [8 bits preamble: 0x00][32 bits Wand ID][16 bits Magnitude]
// - Strict 56-bit verification ensures zero bit-shift corruption.
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
static void processChannelPacket(IRChannel& channel) {
    uint8_t bufIdx = 255;

    // Micro-critical section (<30ns): swap active buffer index atomically
    noInterrupts();
    bufIdx = channel.readyBuf;
    channel.readyBuf = 255;
    interrupts();

    if (bufIdx >= 2) {
        return;
    }

    uint16_t len = channel.rawlen[bufIdx];
    if (len < 100) {
        channel.rawlen[bufIdx] = 0;
        return;
    }

    // Perform array copying and processing completely outside interrupt-disabled region
    for (uint16_t i = 0; i < len; i++) {
        s_decodeBuf[i] = channel.rawbuf[bufIdx][i];
    }
    channel.rawlen[bufIdx] = 0;

    uint32_t code = 0;
    uint16_t magnitude = 0;
    bool valid = decodeMagiQuestCustom(s_decodeBuf, len, code, magnitude);

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
            LedController::triggerPairingFeedback(true);
        } else if (currentPairing == PairingMode::BLUE) {
            StorageController::saveBlueWandCode(code);
            s_pairingMode.store(PairingMode::NONE, std::memory_order_release);
            Serial.printf("[IRController] SUCCESS: Paired Blue Wand -> 0x%08X\n", code);
            LedController::triggerPairingFeedback(false);
        } else {
            // Operational mode matching
            uint32_t pinkCode = StorageController::getPinkWandCode();
            uint32_t blueCode = StorageController::getBlueWandCode();

            if (pinkCode != 0 && code == pinkCode) {
                Serial.printf("[IRController] %s: Pink Wand detected!\n", channel.name);
                s_lastPinkTime = now;

                if (s_lastBlueTime > 0 && (now - s_lastBlueTime <= WAND_RAPID_WINDOW_MS)) {
                    Serial.println(F("[IRController] Rapid succession detected -> Dueling Splotches!"));
                    LedController::setMode(VisualMode::SPLOTCHES);
                    s_lastPinkTime = 0;
                    s_lastBlueTime = 0;
                } else {
                    LedController::setMode(VisualMode::PINK);
                }
            } else if (blueCode != 0 && code == blueCode) {
                Serial.printf("[IRController] %s: Blue Wand detected!\n", channel.name);
                s_lastBlueTime = now;

                if (s_lastPinkTime > 0 && (now - s_lastPinkTime <= WAND_RAPID_WINDOW_MS)) {
                    Serial.println(F("[IRController] Rapid succession detected -> Dueling Splotches!"));
                    LedController::setMode(VisualMode::SPLOTCHES);
                    s_lastPinkTime = 0;
                    s_lastBlueTime = 0;
                } else {
                    LedController::setMode(VisualMode::BLUE);
                }
            } else {
                Serial.printf("[IRController] %s: Wand 0x%08X not matched to Pink (0x%08X) or Blue (0x%08X)\n",
                              channel.name, code, pinkCode, blueCode);
            }
        }
    } else if (len >= 100) {
        // Log unrecognized full pulse burst for diagnosis
        Serial.printf("[IRController] %s: Unrecognized IR signal (%d samples). First pulses (us): ",
                      channel.name, len);
        for (uint16_t i = 1; i < len && i <= 8; i += 2) {
            Serial.printf("[M:%u S:%u] ", s_decodeBuf[i] * IR_RAW_TICK_US, s_decodeBuf[i + 1] * IR_RAW_TICK_US);
        }
        Serial.println();
    }
}

// ============================================================================
// Public Interface Implementation
// ============================================================================

void IRController::init() {
    // Configure both Left and Right shoulder IR receiver pins with internal pull-ups
    pinMode(PIN_IR_RECV_LEFT,  INPUT_PULLUP);
    pinMode(PIN_IR_RECV_RIGHT, INPUT_PULLUP);

    attachInterrupt(PIN_IR_RECV_LEFT,  isrLeft,  CHANGE);
    attachInterrupt(PIN_IR_RECV_RIGHT, isrRight, CHANGE);

    Serial.printf("[IRController] Dual IR Receivers initialized:\n");
    Serial.printf("               - Left Shoulder:  GPIO %d (D1)\n", PIN_IR_RECV_LEFT);
    Serial.printf("               - Right Shoulder: GPIO %d (D0)\n", PIN_IR_RECV_RIGHT);
}

void IRController::update() {
    uint32_t now   = millis();
    uint32_t nowUs = micros();

    // 1. Check pairing mode timeout
    PairingMode currentPairing = s_pairingMode.load(std::memory_order_relaxed);
    if (currentPairing != PairingMode::NONE) {
        uint32_t elapsed = now - s_pairingStartTime.load(std::memory_order_relaxed);
        if (elapsed >= PAIRING_TIMEOUT_MS) {
            s_pairingMode.store(PairingMode::NONE, std::memory_order_release);
            Serial.println(F("[IRController] Pairing mode timed out"));
        }
    }

    // 2. Check for inter-packet silence timeout on both channels
    s_channelLeft.checkTimeout(nowUs);
    s_channelRight.checkTimeout(nowUs);

    // 3. Process completed packets on either receiver
    if (s_channelLeft.readyBuf != 255) {
        processChannelPacket(s_channelLeft);
    }
    if (s_channelRight.readyBuf != 255) {
        processChannelPacket(s_channelRight);
    }
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

void IRController::startPairing(WandType type) {
    if (type == WandType::PINK) {
        startPairingPink();
    } else if (type == WandType::BLUE) {
        startPairingBlue();
    }
}

void IRController::cancelPairing() {
    s_pairingMode.store(PairingMode::NONE, std::memory_order_release);
    Serial.println(F("[IRController] Pairing Mode cancelled"));
}

PairingMode IRController::getPairingMode() {
    return s_pairingMode.load(std::memory_order_acquire);
}

PairingState IRController::getPairingState() {
    return getPairingMode();
}

bool IRController::isPairingActive() {
    return s_pairingMode.load(std::memory_order_acquire) != PairingMode::NONE;
}

uint32_t IRController::getLastReceivedCode() {
    return s_lastReceivedCode.load(std::memory_order_relaxed);
}
