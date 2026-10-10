#ifndef ANIM_MATH_H
#define ANIM_MATH_H

#include <Arduino.h>
#include <NeoPixelBus.h>
#include <stdint.h>

// ============================================================================
// Princess Aurora & Merryweather Animation Math (Pure C++, Zero FastLED)
// ============================================================================

namespace AnimMath {

// 256-entry precomputed sine table [0..255]
static const uint8_t s_sinTable[256] = {
    128,131,134,137,140,143,146,149,152,155,158,162,165,167,170,173,
    176,179,182,185,188,190,193,196,198,201,203,206,208,211,213,215,
    218,220,222,224,226,228,230,232,234,235,237,238,240,241,243,244,
    245,246,248,249,250,250,251,252,253,253,254,254,254,255,255,255,
    255,255,255,255,254,254,254,253,253,252,251,250,250,249,248,246,
    245,244,243,241,240,238,237,235,234,232,230,228,226,224,222,220,
    218,215,213,211,208,206,203,201,198,196,193,190,188,185,182,179,
    176,173,170,167,165,162,158,155,152,149,146,143,140,137,134,131,
    128,124,121,118,115,112,109,106,103,100,97,93,90,88,85,82,
    79,76,73,70,67,65,62,59,57,54,52,49,47,44,42,40,
    37,35,33,31,29,27,25,23,21,20,18,17,15,14,12,11,
    10,9,7,6,5,5,4,3,2,2,1,1,1,0,0,0,
    0,0,0,0,1,1,1,2,2,3,4,5,5,6,7,9,
    10,11,12,14,15,17,18,20,21,23,25,27,29,31,33,35,
    37,40,42,44,47,49,52,54,57,59,62,65,67,70,73,76,
    79,82,85,88,90,93,97,100,103,106,109,112,115,118,121,124
};

// Perlin noise permutation table doubled to 512 entries
static const uint8_t s_perlinP[512] = {
    151,160,137,91,90,15,131,13,201,95,96,53,194,233,7,225,140,36,103,30,69,142,
    8,99,37,240,21,10,23,190,6,148,247,120,234,75,0,26,197,62,94,252,219,203,117,
    35,11,32,57,177,33,88,237,149,56,87,174,20,125,136,171,168,68,175,74,165,71,
    134,139,48,27,166,77,146,158,231,83,111,229,122,60,211,133,230,220,105,92,41,
    55,46,245,40,244,102,143,54,65,25,63,161,1,216,80,73,209,76,132,187,208,89,
    18,169,200,196,135,130,116,188,159,86,164,100,109,198,173,186,3,64,52,217,226,
    250,124,123,5,202,38,147,118,126,255,82,85,212,207,206,59,227,47,16,58,17,182,
    189,28,42,223,183,170,213,119,248,152,2,44,154,163,70,221,153,101,155,167,43,
    172,9,129,22,39,253,19,98,108,110,79,113,224,232,178,185,112,104,218,246,97,
    228,251,34,242,193,238,210,144,12,191,179,162,241,81,51,145,235,249,14,239,
    107,49,192,214,31,181,199,106,157,184,84,204,176,115,121,50,45,127,4,150,254,
    138,236,205,93,222,114,67,29,24,72,243,141,128,195,78,66,215,61,156,180,
    151,160,137,91,90,15,131,13,201,95,96,53,194,233,7,225,140,36,103,30,69,142,
    8,99,37,240,21,10,23,190,6,148,247,120,234,75,0,26,197,62,94,252,219,203,117,
    35,11,32,57,177,33,88,237,149,56,87,174,20,125,136,171,168,68,175,74,165,71,
    134,139,48,27,166,77,146,158,231,83,111,229,122,60,211,133,230,220,105,92,41,
    55,46,245,40,244,102,143,54,65,25,63,161,1,216,80,73,209,76,132,187,208,89,
    18,169,200,196,135,130,116,188,159,86,164,100,109,198,173,186,3,64,52,217,226,
    250,124,123,5,202,38,147,118,126,255,82,85,212,207,206,59,227,47,16,58,17,182,
    189,28,42,223,183,170,213,119,248,152,2,44,154,163,70,221,153,101,155,167,43,
    172,9,129,22,39,253,19,98,108,110,79,113,224,232,178,185,112,104,218,246,97,
    228,251,34,242,193,238,210,144,12,191,179,162,241,81,51,145,235,249,14,239,
    107,49,192,214,31,181,199,106,157,184,84,204,176,115,121,50,45,127,4,150,254,
    138,236,205,93,222,114,67,29,24,72,243,141,128,195,78,66,215,61,156,180
};

/**
 * @brief Fast 8-bit sine function mapping [0..255] to [0..255]
 */
static inline uint8_t sin8(uint8_t theta) {
    return s_sinTable[theta];
}

/**
 * @brief Fast 8-bit cosine function mapping [0..255] to [0..255]
 */
static inline uint8_t cos8(uint8_t theta) {
    return s_sinTable[(uint8_t)(theta + 64)];
}

/**
 * @brief Smooth sinusoidal oscillator between lowest and highest bounds at given BPM
 */
static inline uint8_t beatsin8(uint16_t bpm, uint8_t lowest = 0, uint8_t highest = 255, uint32_t timebase = 0, uint8_t phase_offset = 0) {
    uint32_t now = millis();
    uint32_t beat_ms = 60000 / (bpm > 0 ? bpm : 1);
    uint32_t elapsed = (now - timebase) % beat_ms;
    uint8_t beat_phase = (uint8_t)((elapsed * 256) / beat_ms) + phase_offset;
    uint8_t sin_val = sin8(beat_phase);
    return lowest + (uint8_t)(((uint16_t)(highest - lowest) * sin_val) / 255);
}

/**
 * @brief Saturating 8-bit integer addition
 */
static inline uint8_t qadd8(uint8_t i, uint8_t j) {
    uint16_t t = (uint16_t)i + (uint16_t)j;
    return (t > 255) ? 255 : (uint8_t)t;
}

/**
 * @brief Saturating 8-bit integer subtraction
 */
static inline uint8_t qsub8(uint8_t i, uint8_t j) {
    int16_t t = (int16_t)i - (int16_t)j;
    return (t < 0) ? 0 : (uint8_t)t;
}

/**
 * @brief Linear interpolation between two 8-bit values
 */
static inline uint8_t blend8(uint8_t a, uint8_t b, uint8_t amountOfB) {
    return (uint8_t)((((uint16_t)a * (255 - amountOfB)) + ((uint16_t)b * amountOfB)) / 255);
}

/**
 * @brief Blends two RgbColor objects according to amountOfC2 (0 = pure c1, 255 = pure c2)
 */
static inline RgbColor blend(const RgbColor& c1, const RgbColor& c2, uint8_t amountOfC2) {
    uint8_t r = blend8(c1.R, c2.R, amountOfC2);
    uint8_t g = blend8(c1.G, c2.G, amountOfC2);
    uint8_t b = blend8(c1.B, c2.B, amountOfC2);
    return RgbColor(r, g, b);
}

/**
 * @brief Fast 32-bit Xorshift PRNG returning 8-bit pseudo-random value
 */
static inline uint8_t random8() {
    static uint32_t s_prngState = 0x5A17C309;
    s_prngState ^= (s_prngState << 13);
    s_prngState ^= (s_prngState >> 17);
    s_prngState ^= (s_prngState << 5);
    return (uint8_t)(s_prngState & 0xFF);
}

static inline uint8_t random8(uint8_t max_val) {
    if (max_val == 0) return 0;
    return random8() % max_val;
}

static inline uint8_t random8(uint8_t min_val, uint8_t max_val) {
    if (max_val <= min_val) return min_val;
    return min_val + (random8() % (max_val - min_val));
}

// Internal Perlin fade curve: 6t^5 - 15t^4 + 10t^3 approximated via cubic smoothstep
static inline int32_t perlinFade(int32_t t) {
    return (t * t * (765 - 2 * t)) >> 16;
}

static inline int32_t perlinGrad(uint8_t hash, int32_t x, int32_t y, int32_t z) {
    uint8_t h = hash & 15;
    int32_t u = (h < 8) ? x : y;
    int32_t v = (h < 4) ? y : ((h == 12 || h == 14) ? x : z);
    return (((h & 1) == 0) ? u : -u) + (((h & 2) == 0) ? v : -v);
}

static inline int32_t perlinLerp(int32_t a, int32_t b, int32_t t) {
    return a + ((b - a) * t >> 8);
}

/**
 * @brief 3D integer Perlin noise returning [0..255]
 * Coordinates x, y, z have 8-bit integer grid index in high byte, 8-bit fraction in low byte
 */
static inline uint8_t inoise8(uint16_t x, uint16_t y, uint16_t z) {
    uint8_t X = (x >> 8) & 255;
    uint8_t Y = (y >> 8) & 255;
    uint8_t Z = (z >> 8) & 255;

    int32_t xf = x & 255;
    int32_t yf = y & 255;
    int32_t zf = z & 255;

    int32_t u = perlinFade(xf);
    int32_t v = perlinFade(yf);
    int32_t w = perlinFade(zf);

    uint8_t A = s_perlinP[X] + Y;
    uint8_t AA = s_perlinP[A] + Z;
    uint8_t AB = s_perlinP[A + 1] + Z;
    uint8_t B = s_perlinP[X + 1] + Y;
    uint8_t BA = s_perlinP[B] + Z;
    uint8_t BB = s_perlinP[B + 1] + Z;

    int32_t g000 = perlinGrad(s_perlinP[AA], xf, yf, zf);
    int32_t g100 = perlinGrad(s_perlinP[BA], xf - 256, yf, zf);
    int32_t g010 = perlinGrad(s_perlinP[AB], xf, yf - 256, zf);
    int32_t g110 = perlinGrad(s_perlinP[BB], xf - 256, yf - 256, zf);
    int32_t g001 = perlinGrad(s_perlinP[AA + 1], xf, yf, zf - 256);
    int32_t g101 = perlinGrad(s_perlinP[BA + 1], xf - 256, yf, zf - 256);
    int32_t g011 = perlinGrad(s_perlinP[AB + 1], xf, yf - 256, zf - 256);
    int32_t g111 = perlinGrad(s_perlinP[BB + 1], xf - 256, yf - 256, zf - 256);

    int32_t x1 = perlinLerp(g000, g100, u);
    int32_t x2 = perlinLerp(g010, g110, u);
    int32_t y1 = perlinLerp(x1, x2, v);

    int32_t x3 = perlinLerp(g001, g101, u);
    int32_t x4 = perlinLerp(g011, g111, u);
    int32_t y2 = perlinLerp(x3, x4, v);

    int32_t val = perlinLerp(y1, y2, w);
    int32_t scaled = 128 + (val >> 1);
    if (scaled < 0) return 0;
    if (scaled > 255) return 255;
    return (uint8_t)scaled;
}

static inline uint8_t inoise8(uint16_t x, uint16_t y) {
    return inoise8(x, y, 0);
}

static inline uint8_t inoise8(uint16_t x) {
    return inoise8(x, 0, 0);
}

} // namespace AnimMath

// Expose common functions into global scope for natural expressive syntax
using AnimMath::sin8;
using AnimMath::cos8;
using AnimMath::beatsin8;
using AnimMath::qadd8;
using AnimMath::qsub8;
using AnimMath::blend8;
using AnimMath::blend;
using AnimMath::random8;
using AnimMath::inoise8;

#endif // ANIM_MATH_H
