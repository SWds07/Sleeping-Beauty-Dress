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

    // PROJECT.md contract aliases
    static inline void savePinkWandId(uint32_t id) { savePinkWandCode(id); }
    static inline uint32_t getPinkWandId() { return getPinkWandCode(); }
    
    static inline void saveBlueWandId(uint32_t id) { saveBlueWandCode(id); }
    static inline uint32_t getBlueWandId() { return getBlueWandCode(); }
};

#endif // STORAGE_CONTROLLER_H
