#ifndef UW2_INDEXED_SURFACE_H
#define UW2_INDEXED_SURFACE_H

/*
 * Target-neutral UW2 presentation seam.
 *
 * pixels is a row-major, one-byte-per-pixel surface.  Each byte is an index
 * into palette6, which contains 256 RGB triples in the source PALS.DAT
 * 6-bit-DAC representation.  No video-memory address, register layout, or
 * Falcon-specific palette word belongs in this structure.
 */
#include <stdint.h>

#define UW2_INDEXED_PALETTE_ENTRIES 256u
#define UW2_INDEXED_PALETTE_BYTES (UW2_INDEXED_PALETTE_ENTRIES * 3u)

typedef struct uw2_indexed_surface {
    uint16_t width;
    uint16_t height;
    uint16_t stride;
    uint8_t *pixels;
    const uint8_t *palette6;
} uw2_indexed_surface;

#endif
