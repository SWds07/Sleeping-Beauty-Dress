#include <Arduino.h>
#include "Config.h"
#include "LedController.h"
#include "IRController.h"
#include "WebController.h"

void setup() {
    Serial.begin(115200);
    
    // Initialize components
    // LedController::init();
    // IRController::init();
    // WebController::init();
}

void loop() {
    // LedController::update();
    // IRController::update();
    // WebController::update();
}
