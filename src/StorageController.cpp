#include "StorageController.h"
#include <Preferences.h>

Preferences preferences;

void StorageController::init() {
    preferences.begin("auroradress", false);
}

void StorageController::savePinkWandCode(uint32_t code) {
    preferences.putUInt("pink_wand", code);
}

uint32_t StorageController::getPinkWandCode() {
    return preferences.getUInt("pink_wand", 0); // Default 0 if not set
}

void StorageController::saveBlueWandCode(uint32_t code) {
    preferences.putUInt("blue_wand", code);
}

uint32_t StorageController::getBlueWandCode() {
    return preferences.getUInt("blue_wand", 0); // Default 0 if not set
}
