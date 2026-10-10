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

// Aliases matching PROJECT.md interface contracts
using PairingState = PairingMode;

/**
 * @brief Wand selection enum for pairing
 */
enum class WandType : uint8_t {
    PINK = 1,
    BLUE = 2
};

class IRController {
public:
    static void init();
    static void update();

    // Wand pairing triggers
    static void startPairingPink();
    static void startPairingBlue();
    static void startPairing(WandType type);
    static void cancelPairing();

    // State inspection
    static PairingMode getPairingMode();
    static PairingState getPairingState();
    static bool isPairingActive();
    static uint32_t getLastReceivedCode();
};

#endif // IR_CONTROLLER_H
