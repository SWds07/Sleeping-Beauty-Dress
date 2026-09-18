#include <Arduino.h>
#include "Config.h"
#include "StorageController.h"
#include "LedController.h"
#include "IRController.h"
#include "WebController.h"

void setup() {
    Serial.begin(115200);
    delay(200); // Short settle time for hardware UART on cold boot

    Serial.println();
    Serial.println(F("=================================================="));
    Serial.println(F("    Princess Aurora Interactive Dress Firmware   "));
    Serial.println(F("       Seeed Studio XIAO ESP32-C3 Target         "));
    Serial.println(F("=================================================="));

    // 1. Initialize persistent NVS storage
    StorageController::init();
    Serial.println(F("[Main] StorageController initialized"));

    // 2. Initialize FastLED drivers across 3 hardware pins
    LedController::init();
    Serial.println(F("[Main] LedController initialized (150 LEDs across Skirt, Left Sleeve, Right Sleeve)"));

    // 3. Initialize 38KHz IR receiver and decoder
    IRController::init();
    Serial.println(F("[Main] IRController initialized"));

    // 4. Initialize WiFi SoftAP, captive portal DNS, and async web server
    WebController::init();
    Serial.println(F("[Main] WebController initialized"));

    Serial.println(F("=================================================="));
    Serial.println(F("         Firmware initialization complete!        "));
    Serial.println(F("=================================================="));
}

void loop() {
    // Non-blocking round-robin polling across all subsystems
    LedController::update();
    IRController::update();
    WebController::update();
}
