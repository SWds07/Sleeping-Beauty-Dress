#ifndef STORAGE_CONTROLLER_H
#define STORAGE_CONTROLLER_H

#include <Arduino.h>

class StorageController {
public:
    static void init();
    
    static void savePinkWandCode(uint32_t code);
    static uint32_t getPinkWandCode();
    
    static void saveBlueWandCode(uint32_t code);
    static uint32_t getBlueWandCode();
};

#endif // STORAGE_CONTROLLER_H
