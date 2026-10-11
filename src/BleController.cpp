#include "BleController.h"
#include "Config.h"
#include "LedController.h"
#include "IRController.h"
#include "StorageController.h"

#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLE2902.h>
#include <atomic>
#include <mutex>

// ============================================================================
// Telemetry Packet Structure (15 bytes, Packed Little-Endian)
// ============================================================================
#pragma pack(push, 1)
struct DressTelemetryPacket {
    uint8_t  mode;          // 0=OFF, 1=PINK, 2=BLUE, 3=SPLOTCHES, 4=PAIRING_FEEDBACK
    uint8_t  brightness;    // 0-255
    uint8_t  pairingState;  // 0=NONE, 1=PINK, 2=BLUE
    uint32_t pinkWandId;    // 32-bit uint (0 = unassigned)
    uint32_t blueWandId;    // 32-bit uint (0 = unassigned)
    uint32_t lastWandId;    // 32-bit uint (last detected wand ID)
};
#pragma pack(pop)

// ============================================================================
// Internal BLE State & Pointers
// ============================================================================
static BLEServer*          s_pServer          = nullptr;
static BLECharacteristic*  s_pTelemetryChar   = nullptr;
static BLECharacteristic*  s_pCommandChar     = nullptr;
static BLECharacteristic*  s_pBrightnessChar  = nullptr;

static std::atomic<bool>     s_deviceConnected{false};
static std::atomic<bool>     s_restartAdvertising{false};
static std::atomic<uint32_t> s_connectedCount{0};
static std::mutex            s_bleMutex;

// State caching to automatically push notifications on any state change
static uint8_t  s_cachedMode         = 255;
static uint8_t  s_cachedBrightness   = 255;
static uint8_t  s_cachedPairing      = 255;
static uint32_t s_cachedPinkWand     = 0xFFFFFFFFUL;
static uint32_t s_cachedBlueWand     = 0xFFFFFFFFUL;
static uint32_t s_cachedLastWand     = 0xFFFFFFFFUL;

// Non-blocking timer for advertising restart after disconnect
static uint32_t s_restartTimestamp   = 0;
static bool     s_pendingRestart     = false;

// ============================================================================
// BLE Server Connection Callbacks
// ============================================================================
class ServerCallbacks : public BLEServerCallbacks {
    void onConnect(BLEServer* pServer) override {
        s_connectedCount.fetch_add(1, std::memory_order_acq_rel);
        s_deviceConnected.store(true, std::memory_order_release);
        Serial.println(F("[BleController] Client connected"));
    }

    void onDisconnect(BLEServer* pServer) override {
        uint32_t current = s_connectedCount.load(std::memory_order_acquire);
        while (current > 0 && !s_connectedCount.compare_exchange_weak(current, current - 1, std::memory_order_acq_rel, std::memory_order_acquire));
        bool stillConnected = (s_connectedCount.load(std::memory_order_acquire) > 0);
        s_deviceConnected.store(stillConnected, std::memory_order_release);
        if (!stillConnected) {
            s_restartAdvertising.store(true, std::memory_order_release);
        }
        Serial.println(F("[BleController] Client disconnected"));
    }
};

// ============================================================================
// BLE Descriptor Callbacks (CCCD Subscription Detection)
// ============================================================================
class TelemetryDescriptorCallbacks : public BLEDescriptorCallbacks {
    void onWrite(BLEDescriptor* pDescriptor) override {
        uint8_t* val = pDescriptor->getValue();
        size_t len = pDescriptor->getLength();
        if (len >= 2 && val[0] == 0x01 && val[1] == 0x00) {
            Serial.println(F("[BleController] Telemetry notifications enabled via CCCD"));
            BleController::notifyStateChanged();
        }
    }
};

// ============================================================================
// BLE Characteristic Callbacks
// ============================================================================
class TelemetryCallbacks : public BLECharacteristicCallbacks {
    void onRead(BLECharacteristic* pCharacteristic) override {
        DressTelemetryPacket pkt;
        pkt.mode         = static_cast<uint8_t>(LedController::getCurrentMode());
        pkt.brightness   = LedController::getBrightness();
        pkt.pairingState = static_cast<uint8_t>(IRController::getPairingMode());
        pkt.pinkWandId   = StorageController::getPinkWandCode();
        pkt.blueWandId   = StorageController::getBlueWandCode();
        pkt.lastWandId   = IRController::getLastReceivedCode();
        pCharacteristic->setValue(reinterpret_cast<uint8_t*>(&pkt), sizeof(pkt));
    }
};

class CommandCallbacks : public BLECharacteristicCallbacks {
    void onWrite(BLECharacteristic* pCharacteristic) override {
        std::string val = pCharacteristic->getValue();
        if (val.length() >= 1) {
            uint8_t cmd = static_cast<uint8_t>(val[0]);
            Serial.printf("[BleController] Received command opcode: 0x%02X\n", cmd);

            switch (cmd) {
                case BLE_CMD_SET_OFF:
                    LedController::setOff();
                    break;
                case BLE_CMD_SET_PINK:
                    LedController::setPink();
                    break;
                case BLE_CMD_SET_BLUE:
                    LedController::setBlue();
                    break;
                case BLE_CMD_SET_SPLOTCHES:
                    LedController::triggerSplotches();
                    break;
                case BLE_CMD_PAIR_PINK:
                    IRController::startPairingPink();
                    break;
                case BLE_CMD_PAIR_BLUE:
                    IRController::startPairingBlue();
                    break;
                case BLE_CMD_PAIR_CANCEL:
                    IRController::cancelPairing();
                    break;
                default:
                    Serial.printf("[BleController] Unknown command: 0x%02X\n", cmd);
                    break;
            }
            BleController::notifyStateChanged();
        }
    }
};

class BrightnessCallbacks : public BLECharacteristicCallbacks {
    void onRead(BLECharacteristic* pCharacteristic) override {
        uint8_t b = LedController::getBrightness();
        pCharacteristic->setValue(&b, 1);
    }

    void onWrite(BLECharacteristic* pCharacteristic) override {
        std::string val = pCharacteristic->getValue();
        if (val.length() >= 1) {
            uint8_t b = static_cast<uint8_t>(val[0]);
            Serial.printf("[BleController] Setting brightness: %u\n", b);
            LedController::setBrightness(b);
            BleController::notifyStateChanged();
        }
    }
};

// ============================================================================
// Public Interface Implementation
// ============================================================================

void BleController::init() {
    Serial.println(F("[BleController] Initializing BLE 5.0 stack..."));

    // 1. Initialize BLE Device with local name
    BLEDevice::init(BLE_DEVICE_NAME);

    // 2. Create BLE Server and register connection callbacks
    s_pServer = BLEDevice::createServer();
    s_pServer->setCallbacks(new ServerCallbacks());

    // 3. Create Aurora Dress Primary Service
    BLEService* pService = s_pServer->createService(BLE_SERVICE_UUID);

    // 4. Create Telemetry Characteristic (READ | NOTIFY)
    s_pTelemetryChar = pService->createCharacteristic(
        BLE_CHAR_TELEMETRY_UUID,
        BLECharacteristic::PROPERTY_READ | BLECharacteristic::PROPERTY_NOTIFY
    );
    s_pTelemetryChar->setCallbacks(new TelemetryCallbacks());
    BLE2902* p2902 = new BLE2902();
    p2902->setCallbacks(new TelemetryDescriptorCallbacks());
    s_pTelemetryChar->addDescriptor(p2902);

    // 5. Create Command Characteristic (WRITE | WRITE_NO_RESPONSE)
    s_pCommandChar = pService->createCharacteristic(
        BLE_CHAR_COMMAND_UUID,
        BLECharacteristic::PROPERTY_WRITE | BLECharacteristic::PROPERTY_WRITE_NR
    );
    s_pCommandChar->setCallbacks(new CommandCallbacks());

    // 6. Create Brightness Characteristic (READ | WRITE | WRITE_NO_RESPONSE)
    s_pBrightnessChar = pService->createCharacteristic(
        BLE_CHAR_BRIGHTNESS_UUID,
        BLECharacteristic::PROPERTY_READ | BLECharacteristic::PROPERTY_WRITE | BLECharacteristic::PROPERTY_WRITE_NR
    );
    s_pBrightnessChar->setCallbacks(new BrightnessCallbacks());

    // 7. Populate initial values
    notifyStateChanged();

    // 8. Start GATT Service
    pService->start();

    // 9. Configure and start BLE Advertising
    BLEAdvertising* pAdvertising = BLEDevice::getAdvertising();
    pAdvertising->addServiceUUID(BLE_SERVICE_UUID);
    pAdvertising->setScanResponse(true);
    pAdvertising->setMinPreferred(0x06); // Functions that help with iPhone / Android connections
    pAdvertising->setMaxPreferred(0x12);
    BLEDevice::startAdvertising();

    Serial.printf("[BleController] BLE GATT Server started. Advertising as \"%s\"\n", BLE_DEVICE_NAME);
    Serial.printf("               - Service UUID: %s\n", BLE_SERVICE_UUID);
}

void BleController::notifyStateChanged() {
    std::lock_guard<std::mutex> lock(s_bleMutex);

    DressTelemetryPacket pkt;
    pkt.mode         = static_cast<uint8_t>(LedController::getCurrentMode());
    pkt.brightness   = LedController::getBrightness();
    pkt.pairingState = static_cast<uint8_t>(IRController::getPairingMode());
    pkt.pinkWandId   = StorageController::getPinkWandCode();
    pkt.blueWandId   = StorageController::getBlueWandCode();
    pkt.lastWandId   = IRController::getLastReceivedCode();

    if (s_pTelemetryChar != nullptr) {
        s_pTelemetryChar->setValue(reinterpret_cast<uint8_t*>(&pkt), sizeof(pkt));
        if (s_deviceConnected.load(std::memory_order_acquire)) {
            s_pTelemetryChar->notify();
        }
    }

    if (s_pBrightnessChar != nullptr) {
        uint8_t b = pkt.brightness;
        s_pBrightnessChar->setValue(&b, 1);
    }

    // Update caches
    s_cachedMode       = pkt.mode;
    s_cachedBrightness = pkt.brightness;
    s_cachedPairing    = pkt.pairingState;
    s_cachedPinkWand   = pkt.pinkWandId;
    s_cachedBlueWand   = pkt.blueWandId;
    s_cachedLastWand   = pkt.lastWandId;
}

void BleController::update() {
    // 1. Handle non-blocking advertising restart after disconnection
    if (s_restartAdvertising.exchange(false, std::memory_order_acq_rel)) {
        s_pendingRestart = true;
        s_restartTimestamp = millis();
    }

    if (s_pendingRestart && (millis() - s_restartTimestamp >= 100)) {
        s_pendingRestart = false;
        if (s_pServer != nullptr && s_connectedCount.load(std::memory_order_acquire) == 0) {
            s_pServer->startAdvertising();
            Serial.println(F("[BleController] Advertising restarted"));
        }
    }

    // 2. Poll for dress state changes (from IR wand flick, pairing complete, timeout, etc.)
    uint8_t  currMode       = static_cast<uint8_t>(LedController::getCurrentMode());
    uint8_t  currBrightness = LedController::getBrightness();
    uint8_t  currPairing    = static_cast<uint8_t>(IRController::getPairingMode());
    uint32_t currPinkWand   = StorageController::getPinkWandCode();
    uint32_t currBlueWand   = StorageController::getBlueWandCode();
    uint32_t currLastWand   = IRController::getLastReceivedCode();

    if (currMode != s_cachedMode ||
        currBrightness != s_cachedBrightness ||
        currPairing != s_cachedPairing ||
        currPinkWand != s_cachedPinkWand ||
        currBlueWand != s_cachedBlueWand ||
        currLastWand != s_cachedLastWand) {
        notifyStateChanged();
    }
}

bool BleController::isConnected() {
    return s_connectedCount.load(std::memory_order_acquire) > 0;
}

uint32_t BleController::getConnectedDeviceCount() {
    return s_connectedCount.load(std::memory_order_acquire);
}
