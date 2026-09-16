#include <Arduino.h>
#include "Config.h"
#include "LedController.h"
#include "IRController.h"
#include "WebController.h"
#include "StorageController.h"

void setup() {
    Serial.begin(115200);
    
    // Initialize components
    // StorageController::init();
    // LedController::init();
    // IRController::init();
    // WebController::init();
}

void loop() {
    // LedController::update();
    // IRController::update();
    // WebController::update();
}
