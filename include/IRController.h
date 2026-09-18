#ifndef IR_CONTROLLER_H
#define IR_CONTROLLER_H

#include <Arduino.h>
#include <stdint.h>

/**
 * @brief Wand pairing states for IRController
 */
enum class PairingMode : uint8_t {
    NONE = 0,
    PINK,
    BLUE
};

class IRController {
public:
    static void init();
    static void update();

    // Wand pairing triggers
    static void startPairingPink();
    static void startPairingBlue();
    static void cancelPairing();

    // State inspection
    static PairingMode getPairingMode();
    static bool isPairingActive();
    static uint32_t getLastReceivedCode();
};

#endif // IR_CONTROLLER_H
