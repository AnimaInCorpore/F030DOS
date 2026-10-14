#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "../include/wc1_c2p.h"

static uint8_t indexed[WC1_CHUNKY_FRAME_BYTES];
static uint8_t rgb565[WC1_TRUECOLOUR_BYTES];
static uint16_t palette[WC1_RGB565_PALETTE_ENTRIES];

static int expect_pixel(uint32_t pixel, uint16_t expected)
{
    uint32_t offset;
    uint16_t got;

    offset = pixel * 2U;
    got = (uint16_t)(((uint16_t)rgb565[offset] << 8) | rgb565[offset + 1U]);
    if (got == expected)
        return 1;
    fprintf(stderr, "pixel %lu: got %04x expected %04x\n",
            (unsigned long)pixel, got, expected);
    return 0;
}

int main(void)
{
    memset(indexed, 0, sizeof(indexed));
    memset(palette, 0, sizeof(palette));
    palette[1] = 0xf800U;
    palette[2] = 0x07e0U;
    palette[3] = 0x001fU;
    palette[255] = 0xffffU;
    indexed[0] = 1U;
    indexed[1] = 2U;
    indexed[2] = 3U;
    indexed[WC1_CHUNKY_FRAME_BYTES - 1U] = 255U;

    wc1_indexed_to_rgb565(indexed, rgb565, palette);
    if (!expect_pixel(0U, 0xf800U) ||
        !expect_pixel(1U, 0x07e0U) ||
        !expect_pixel(2U, 0x001fU) ||
        !expect_pixel(WC1_CHUNKY_FRAME_BYTES - 1U, 0xffffU))
        return 1;

    printf("WC1 RGB565: %u indexed pixels, %u display bytes\n",
           WC1_CHUNKY_FRAME_BYTES, WC1_TRUECOLOUR_BYTES);
    return 0;
}
