#ifndef LED_CONTROLLER_H
#define LED_CONTROLLER_H

class LedController {
public:
    static void init();
    static void update();
    
    // Animation triggers
    static void setPink();
    static void setBlue();
    static void triggerSplotches();
};

#endif // LED_CONTROLLER_H
