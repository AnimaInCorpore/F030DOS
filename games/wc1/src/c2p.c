/*
 * Host/reference half of the Falcon 16-bit true-colour presentation path.
 *
 * WC1's DOS resources and software renderer naturally remain indexed. The
 * Falcon display page is RGB565, so this bounded reference converter expands
 * one frame through the palette loaded by resources.c. The target build uses
 * the adjacent 68030 implementation in c2p_fast.s; keeping this version
 * architecture-neutral makes the golden-pixel smoke test independent of the
 * host byte order.
 */
#include "../include/wc1_c2p.h"

/*
 * Target artefact: c2p_present_rgb565; record:
 * analysis/functions/c2p-present.md. N/A - platform replacement; the DOS
 * program presents indexed VGA data, while Falcon Videl needs RGB565 words.
 */
static void write_be16(uint8_t *destination, uint16_t value)
{
    destination[0] = (uint8_t)(value >> 8);
    destination[1] = (uint8_t)value;
}

/*
 * Target artefact: c2p_present_rgb565; record:
 * analysis/functions/c2p-present.md. N/A - platform replacement; this is the
 * host/reference implementation of the Falcon presentation seam.
 */
void wc1_indexed_to_rgb565(const uint8_t *indexed, uint8_t *rgb565,
                           const uint16_t *palette)
{
    uint32_t pixel;

    if (indexed == 0 || rgb565 == 0 || palette == 0)
        return;
    for (pixel = 0; pixel < WC1_CHUNKY_FRAME_BYTES; pixel++) {
        write_be16(rgb565 + pixel * 2U, palette[indexed[pixel]]);
    }
}
