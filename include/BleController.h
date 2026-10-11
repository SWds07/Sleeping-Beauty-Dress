#ifndef BLE_CONTROLLER_H
#define BLE_CONTROLLER_H

#include <Arduino.h>
#include <stdint.h>

/**
 * @brief Bluetooth Low Energy (BLE 5.0) GATT Server Controller
 * 
 * Exposes the Princess Aurora dress state, controls, and wand pairing
 * triggers over BLE to the companion Android application.
 */
class BleController {
public:
    /**
     * @brief Initialize BLE stack, GATT server, services, and advertising.
     */
    static void init();

    /**
     * @brief Non-blocking loop update. Handles disconnection restarts and pending notifications.
     */
    static void update();

    /**
     * @brief Broadcast current dress telemetry to connected client(s).
     */
    static void notifyStateChanged();

    /**
     * @brief Returns true if an Android client is currently connected.
     */
    static bool isConnected();

    /**
     * @brief Returns the count of connected BLE clients.
     */
    static uint32_t getConnectedDeviceCount();
};

#endif // BLE_CONTROLLER_H
