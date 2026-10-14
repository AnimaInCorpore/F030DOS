/* WC1 Falcon 16-bit true-colour presentation contract. */
#ifndef WC1_C2P_H
#define WC1_C2P_H

#include <stdint.h>

#define WC1_SCREEN_WIDTH 320U
#define WC1_SCREEN_HEIGHT 200U
#define WC1_CHUNKY_FRAME_BYTES (WC1_SCREEN_WIDTH * WC1_SCREEN_HEIGHT)
#define WC1_TRUECOLOUR_BYTES (WC1_CHUNKY_FRAME_BYTES * 2U)
#define WC1_RGB565_PALETTE_ENTRIES 256U

/* Expand indexed source bytes to one big-endian RGB565 word per pixel. */
void wc1_indexed_to_rgb565(const uint8_t *indexed, uint8_t *rgb565,
                           const uint16_t *palette);

#endif
