#include "WebController.h"
#include "Config.h"
#include "LedController.h"
#include "IRController.h"
#include "StorageController.h"

#include <WiFi.h>
#include <DNSServer.h>
#include <ESPAsyncWebServer.h>

// ============================================================================
// Network & Server Instances
// ============================================================================
static DNSServer s_dnsServer;
static AsyncWebServer s_server(HTTP_PORT);

// ============================================================================
// Mobile-Responsive HTML5 Portal Page
// ============================================================================
static const char INDEX_HTML[] PROGMEM = R"rawliteral(
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Sleeping Beauty Dress</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      background: linear-gradient(135deg, #180024 0%, #0d1127 100%);
      color: #fff;
      padding: 16px;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
    }
    .container {
      width: 100%;
      max-width: 440px;
      display: flex;
      flex-direction: column;
      gap: 16px;
    }
    h1 {
      text-align: center;
      font-size: 1.5rem;
      letter-spacing: 1px;
      background: linear-gradient(90deg, #ff1493, #a855f7, #0078ff);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      margin-bottom: 4px;
    }
    .card {
      background: rgba(255, 255, 255, 0.06);
      backdrop-filter: blur(12px);
      border: 1px solid rgba(255, 255, 255, 0.12);
      border-radius: 16px;
      padding: 16px;
      box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
    }
    .card-title {
      font-size: 0.85rem;
      text-transform: uppercase;
      letter-spacing: 1.5px;
      color: #bbb;
      margin-bottom: 12px;
    }
    .status-badge {
      display: inline-block;
      padding: 6px 14px;
      border-radius: 20px;
      font-weight: 700;
      font-size: 0.95rem;
      letter-spacing: 0.5px;
      background: #333;
    }
    .status-PINK { background: #ff1493; color: #fff; box-shadow: 0 0 12px rgba(255, 20, 147, 0.6); }
    .status-BLUE { background: #0078ff; color: #fff; box-shadow: 0 0 12px rgba(0, 120, 255, 0.6); }
    .status-SPLOTCHES {
      background: linear-gradient(90deg, #ff1493, #0078ff);
      color: #fff;
      box-shadow: 0 0 14px rgba(168, 85, 247, 0.6);
    }
    .status-OFF { background: #444; color: #aaa; }
    .wand-row {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 6px 0;
      font-size: 0.9rem;
      border-bottom: 1px solid rgba(255, 255, 255, 0.05);
    }
    .wand-code {
      font-family: monospace;
      font-weight: bold;
      background: rgba(0, 0, 0, 0.3);
      padding: 2px 8px;
      border-radius: 6px;
    }
    .btn-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 10px;
    }
    button {
      border: none;
      border-radius: 12px;
      padding: 14px 10px;
      font-size: 0.95rem;
      font-weight: 600;
      cursor: pointer;
      color: #fff;
      transition: transform 0.1s, opacity 0.2s;
    }
    button:active { transform: scale(0.97); }
    .btn-pink {
      background: linear-gradient(135deg, #ff1493, #d91b7d);
      box-shadow: 0 4px 14px rgba(255, 20, 147, 0.4);
    }
    .btn-blue {
      background: linear-gradient(135deg, #0078ff, #0056b3);
      box-shadow: 0 4px 14px rgba(0, 120, 255, 0.4);
    }
    .btn-splotches {
      grid-column: span 2;
      background: linear-gradient(135deg, #ff1493, #7c3aed, #0078ff);
      box-shadow: 0 4px 16px rgba(124, 58, 237, 0.4);
    }
    .btn-off {
      grid-column: span 2;
      background: #333;
      color: #bbb;
    }
    .btn-pair-pink {
      background: rgba(255, 20, 147, 0.2);
      border: 1px solid #ff1493;
      color: #ff69b4;
    }
    .btn-pair-blue {
      background: rgba(0, 120, 255, 0.2);
      border: 1px solid #0078ff;
      color: #60a5fa;
    }
    .btn-cancel {
      grid-column: span 2;
      background: #2a2a2a;
      border: 1px solid #555;
      color: #aaa;
    }
    .pairing-banner {
      display: none;
      padding: 10px;
      border-radius: 10px;
      text-align: center;
      font-weight: bold;
      animation: pulse 1s infinite alternate;
    }
    @keyframes pulse { from { opacity: 0.7; } to { opacity: 1; } }
    .slider-row {
      display: flex;
      align-items: center;
      gap: 12px;
      margin-top: 8px;
    }
    input[type=range] {
      flex: 1;
      accent-color: #a855f7;
    }
  </style>
</head>
<body>
  <div class="container">
    <h1>Sleeping Beauty Dress</h1>

    <!-- Status Card -->
    <div class="card">
      <div class="card-title">Dress State</div>
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
        <span>Current Color:</span>
        <span id="modeBadge" class="status-badge status-OFF">OFF</span>
      </div>
      <div id="pairingBanner" class="pairing-banner"></div>
      <div class="wand-row">
        <span>Pink Wand Code:</span>
        <span id="pinkCode" class="wand-code">--</span>
      </div>
      <div class="wand-row" style="border-bottom:none;">
        <span>Blue Wand Code:</span>
        <span id="blueCode" class="wand-code">--</span>
      </div>
    </div>

    <!-- Manual Controls -->
    <div class="card">
      <div class="card-title">Manual Overrides</div>
      <div class="btn-grid">
        <button class="btn-pink" onclick="sendAction('/setPink')">Make It Pink!</button>
        <button class="btn-blue" onclick="sendAction('/setBlue')">Make It Blue!</button>
        <button class="btn-splotches" onclick="sendAction('/setSplotches')">Dueling Splotches</button>
        <button class="btn-off" onclick="sendAction('/setOff')">Turn Off</button>
      </div>
    </div>

    <!-- Wand Pairing Controls -->
    <div class="card">
      <div class="card-title">Wand Registration</div>
      <p style="font-size:0.8rem; color:#aaa; margin-bottom:12px;">
        Tap a button, then flick the wand at the dress IR receiver within 30 seconds.
      </p>
      <div class="btn-grid">
        <button class="btn-pair-pink" onclick="sendAction('/register/pink')">Register Pink Wand</button>
        <button class="btn-pair-blue" onclick="sendAction('/register/blue')">Register Blue Wand</button>
        <button class="btn-cancel" onclick="sendAction('/register/cancel')">Cancel Pairing</button>
      </div>
    </div>

    <!-- Brightness Slider -->
    <div class="card">
      <div class="card-title">Brightness</div>
      <div class="slider-row">
        <input type="range" id="brightnessSlider" min="10" max="160" value="160" onchange="setBrightness(this.value)">
        <span id="brightnessVal" style="font-family:monospace; min-width:32px;">160</span>
      </div>
    </div>
  </div>

  <script>
    function sendAction(endpoint) {
      fetch(endpoint).then(r => r.json()).then(pollStatus).catch(console.error);
    }
    function setBrightness(val) {
      document.getElementById('brightnessVal').innerText = val;
      fetch('/setBrightness?val=' + val);
    }
    function pollStatus() {
      fetch('/api/status')
        .then(r => r.json())
        .then(d => {
          const badge = document.getElementById('modeBadge');
          badge.innerText = d.mode;
          badge.className = 'status-badge status-' + d.mode;

          document.getElementById('pinkCode').innerText = d.pinkWand;
          document.getElementById('blueCode').innerText = d.blueWand;

          const banner = document.getElementById('pairingBanner');
          if (d.pairing && d.pairing !== 'NONE') {
            banner.style.display = 'block';
            banner.innerText = 'PAIRING ACTIVE: Flick ' + d.pairing + ' Wand now!';
            banner.style.background = (d.pairing === 'PINK') ? '#ff1493' : '#0078ff';
          } else {
            banner.style.display = 'none';
          }
        })
        .catch(console.error);
    }
    setInterval(pollStatus, 1500);
    pollStatus();
  </script>
</body>
</html>
)rawliteral";

// ============================================================================
// Public Interface Implementation
// ============================================================================

void WebController::init() {
    // 1. Configure WiFi Access Point
    WiFi.mode(WIFI_AP);
    bool apStarted = WiFi.softAP(WIFI_AP_SSID, WIFI_AP_PASSWORD);
    IPAddress apIP = WiFi.softAPIP();

    if (apStarted) {
        Serial.printf("[WebController] AP '%s' started at http://%s\n", WIFI_AP_SSID, apIP.toString().c_str());
    } else {
        Serial.println(F("[WebController] ERROR: Failed to start WiFi AP"));
    }

    // 2. Start DNS Server on port 53 for captive portal
    s_dnsServer.start(DNS_PORT, "*", apIP);
    Serial.printf("[WebController] Captive portal DNS server started on port %d\n", DNS_PORT);

    // 3. Register HTTP Routes
    // Main landing portal
    s_server.on("/", HTTP_GET, [](AsyncWebServerRequest *request) {
        request->send(200, "text/html", INDEX_HTML);
    });

    // API: System Status
    s_server.on("/api/status", HTTP_GET, [](AsyncWebServerRequest *request) {
        char json[256];
        uint32_t pinkCode = StorageController::getPinkWandCode();
        uint32_t blueCode = StorageController::getBlueWandCode();
        
        const char* pairingStr = "NONE";
        PairingMode pm = IRController::getPairingMode();
        if (pm == PairingMode::PINK) pairingStr = "PINK";
        else if (pm == PairingMode::BLUE) pairingStr = "BLUE";

        char pinkBuf[16];
        char blueBuf[16];
        if (pinkCode == 0) snprintf(pinkBuf, sizeof(pinkBuf), "Not Paired");
        else snprintf(pinkBuf, sizeof(pinkBuf), "0x%08X", pinkCode);

        if (blueCode == 0) snprintf(blueBuf, sizeof(blueBuf), "Not Paired");
        else snprintf(blueBuf, sizeof(blueBuf), "0x%08X", blueCode);

        snprintf(json, sizeof(json),
            "{\"mode\":\"%s\",\"pinkWand\":\"%s\",\"blueWand\":\"%s\",\"pairing\":\"%s\",\"brightness\":%u}",
            LedController::getModeString(), pinkBuf, blueBuf, pairingStr, LedController::getBrightness()
        );
        request->send(200, "application/json", json);
    });

    // API: Manual Overrides
    s_server.on("/setPink", HTTP_GET, [](AsyncWebServerRequest *request) {
        LedController::setPink();
        request->send(200, "application/json", "{\"status\":\"ok\",\"mode\":\"PINK\"}");
    });

    s_server.on("/setBlue", HTTP_GET, [](AsyncWebServerRequest *request) {
        LedController::setBlue();
        request->send(200, "application/json", "{\"status\":\"ok\",\"mode\":\"BLUE\"}");
    });

    s_server.on("/setSplotches", HTTP_GET, [](AsyncWebServerRequest *request) {
        LedController::triggerSplotches();
        request->send(200, "application/json", "{\"status\":\"ok\",\"mode\":\"SPLOTCHES\"}");
    });

    s_server.on("/setOff", HTTP_GET, [](AsyncWebServerRequest *request) {
        LedController::setOff();
        request->send(200, "application/json", "{\"status\":\"ok\",\"mode\":\"OFF\"}");
    });

    // API: Wand Pairing
    s_server.on("/register/pink", HTTP_GET, [](AsyncWebServerRequest *request) {
        IRController::startPairingPink();
        request->send(200, "application/json", "{\"status\":\"ok\",\"pairing\":\"PINK\"}");
    });

    s_server.on("/register/blue", HTTP_GET, [](AsyncWebServerRequest *request) {
        IRController::startPairingBlue();
        request->send(200, "application/json", "{\"status\":\"ok\",\"pairing\":\"BLUE\"}");
    });

    s_server.on("/register/cancel", HTTP_GET, [](AsyncWebServerRequest *request) {
        IRController::cancelPairing();
        request->send(200, "application/json", "{\"status\":\"ok\",\"pairing\":\"NONE\"}");
    });

    // API: Brightness Control
    s_server.on("/setBrightness", HTTP_GET, [](AsyncWebServerRequest *request) {
        if (request->hasParam("val")) {
            int val = request->getParam("val")->value().toInt();
            if (val < 0) val = 0;
            if (val > 255) val = 255;
            LedController::setBrightness(static_cast<uint8_t>(val));
        }
        request->send(200, "application/json", "{\"status\":\"ok\"}");
    });

    // Captive Portal Detection Redirects (Android, iOS, Windows)
    s_server.on("/generate_204", HTTP_GET, [](AsyncWebServerRequest *request) {
        request->redirect("http://192.168.4.1/");
    });
    s_server.on("/hotspot-detect.html", HTTP_GET, [](AsyncWebServerRequest *request) {
        request->redirect("http://192.168.4.1/");
    });
    s_server.on("/canonical.html", HTTP_GET, [](AsyncWebServerRequest *request) {
        request->redirect("http://192.168.4.1/");
    });
    s_server.on("/ncsi.txt", HTTP_GET, [](AsyncWebServerRequest *request) {
        request->redirect("http://192.168.4.1/");
    });
    s_server.on("/connecttest.txt", HTTP_GET, [](AsyncWebServerRequest *request) {
        request->redirect("http://192.168.4.1/");
    });

    // Catch-all 404 handler redirecting to captive portal
    s_server.onNotFound([](AsyncWebServerRequest *request) {
        request->redirect("http://192.168.4.1/");
    });

    // Start Web Server
    s_server.begin();
    Serial.println(F("[WebController] Asynchronous HTTP Web Server started"));
}

void WebController::update() {
    // Process pending DNS captive portal queries
    s_dnsServer.processNextRequest();
}
