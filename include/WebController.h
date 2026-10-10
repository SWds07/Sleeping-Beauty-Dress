#ifndef WEB_CONTROLLER_H
#define WEB_CONTROLLER_H

/**
 * @brief Zero-configuration Captive Portal & Web Management Controller.
 * Broadcasts open SoftAP "Sleeping-Beauty-Dress" at 192.168.4.1, runs a DNS
 * captive portal wildcard responder on UDP port 53, and provides an asynchronous
 * single-page web management UI and REST API.
 */
class WebController {
public:
    /**
     * @brief Configures WiFi SoftAP, starts DNS wildcard responder on port 53,
     * and binds all HTTP REST endpoints and captive portal probe redirects.
     */
    static void init();

    /**
     * @brief Cooperative loop update callback to process pending DNS queries.
     * Must be called periodically from loop() with zero delay.
     */
    static void update();
};

#endif // WEB_CONTROLLER_H
