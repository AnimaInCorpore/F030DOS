/*
 * First browser milestone: the documented DOS attract cycle.
 *
 * This file is a JavaScript translation of the recovered data contracts, not
 * a reconstruction of the removed Falcon source tree. The screen states use
 * the authored DTA/SG pages and the terrain state consumes the authored
 * DEMO*.SCR inputs, D/C maps, HIGH.DTL, and the Q31 table extracted from the
 * DOS image. Missing or malformed data is rejected by dos-data.js before a
 * runtime is created. Source scope is selected by the QEMU-traced milestone
 * route recorded in analysis/functions/browser-attract.md.
 */
// Target artefact; record: analysis/functions/browser-attract.md#browser-host
(() => {
  "use strict";

  const DAMAGE = globalThis.ComancheDamage;
  const VIEW_W = 320;
  const VIEW_H = 240;
  const TERRAIN_COLS = 192;
  // Source column c lands at DOS page x 2*(c - 14) (00007AA0's runs), and the
  // display starts at page x 4 (00015BB7 programs [0x19CAC] = page + 1 byte),
  // so the visible window is columns 16..175. Same constants as src/dsp/proto.inc.
  const TERRAIN_VIEW_FIRST = 16;
  const TERRAIN_VIEW_LAST = 175;
  const MAP_MASK = 0x3ff;
  const PAGE_ANCHOR = 213;
  // DOS 00007580/00007860/000079F0 and src/inc/comanche.s: the two 80x44
  // multi-function displays live at page x 72 and 176, with a four-pixel
  // page margin before the browser's 320-pixel crop.
  const MFD_X = 72;
  const MFD_SURFACE_X = MFD_X - 4;
  const MFD_PANEL_STEP = 0x1a * 4;
  const MFD_Y = 174;
  const MFD_W = 80;
  const MFD_H = 44;
  const MFD_HALF_W = MFD_W >> 1;
  const MFD_ZOOM = 0x08000000;
  const MFD_VIEW_TOP_ROW = 162;
  // DOS 00015B60/00015BBC: CRTC start offsets selected by the four shake
  // phases. The browser surface is a 320x240 crop, so the target presentation
  // applies the corresponding whole-pixel row displacement after composition.
  const DOS_CRTC_ROW_STRIDE = 0x52;
  const DOS_SHAKE_CRTC_OFFSETS = [0x00000000, 0x00000051, 0x000000a4, 0x000000f5];
  const SKY_STRIPS = 512;
  const SKY_ROWS = 150;
  const SKY_TOP_BIAS = 42;
  // 00007AA0 transfers the rendered surface to the screen through a run list
  // built from the loaded console image's own transparency, walking it twice
  // through plane masks 0x302 and 0xC02. Captured out of the running original
  // at two variants (work/qemu_out/marcher-11.json and marcher-7.json):
  //
  //   consol1s, variant 1: 261 runs, shaped - row 0 is [0,1], row 84 [1,80],
  //                        row 167 [18,47]
  //   consol5s, variant 6: 168 runs, one per row, every one full width [0,82]
  //
  // and BOTH span exactly 168 rows: surface rows 46..213, screen rows 0..167.
  // Below that the original leaves its single page standing - the title art is
  // what the external cameras show under the terrain - and the terrain never
  // reaches there however the horizon is sheared.
  //
  // The per-row horizontal shape is reproduced here by the console overlay's
  // own transparency: the same picture by a different mechanism, recorded as a
  // target artefact. The ROW EXTENT is not reproducible that way, and this
  // port clipped at VIEW_H - 1 instead, drawing terrain and sky into rows
  // 168..239 where the original shows page art. That is what this bound is.
  const TERRAIN_TRANSFER_ROWS = 168;
  const TITLE_GATE_ROW = 93;
  const TITLE_PAN_LAST = 150;
  const TITLE_HELI_TOP = 0x5d;
  const TITLE_HELI_LOW = 0xf8;
  const HUD_SIGHT_GREEN = 0x47e8; // DOS COL_MENU_GREEN: 6-bit (0x10,0x3f,0x10)
  // DOS: FUN_0001959F [0001959F-00019674]; record: analysis/functions/browser-attract.md#view-select
  // View variants 1..8 use the signed 32-bit angle offsets recovered from
  // the table at 00019D94. Variant 1 is the cockpit/default view.
  const VIEW_ANGLE_OFFSETS = new Int32Array([
    0,
    0,
    -1064632320,
    -1073741824,
    1073741824,
    -2147483648,
    0,
    0,
    0,
  ]);
  // DOS: FUN_00005690 [00005690-00005AE3]; record: analysis/functions/browser-attract.md#attract-cycle
  const ZOVE_FRAMES = [3, 3, 2, 2, 1, 1];
  // DOS: FUN_00005690 [00005690-00005AE3]; record: analysis/functions/browser-attract.md#attract-cycle
  const COMA_FRAMES = Array.from({ length: 36 }, (_, index) => 9 - Math.floor(index / 4));
  // DOS: FUN_00005690 [00005690-00005AE3]; record: analysis/functions/browser-attract.md#attract-cycle
  const PAN_WOBBLE = [
    0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1, 2, 2, 2, 2, 2, 3, 3, 3, 3, 3, 3, 4, 4, 4, 4,
    3, 3, 3, 3, 3, 3, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
    1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0,
  ];
  const GAMMA = [
    0, 1, 2, 4, 5, 7, 8, 10, 12, 13, 15, 17, 19, 21, 23, 25,
    27, 29, 31, 33, 35, 37, 40, 42, 44, 46, 49, 51, 54, 56, 58, 61,
    63, 66, 68, 71, 73, 76, 78, 80, 83, 85, 87, 90, 92, 94, 96, 98,
    100, 102, 104, 106, 108, 110, 112, 114, 116, 118, 119, 121, 123, 124, 126, 127,
  ];

  const SINE_Q31 = globalThis.ComancheSineQ31;
  if (!(SINE_Q31 instanceof Int32Array) || SINE_Q31.length !== 640) {
    throw new Error("DOS attract runtime: exact 640-entry Q31 sine table is not installed");
  }

  // DOS flat 00022385/000223A5; the object bearing tables are data, not an
  // analytic atan replacement. The octant bases are the eight dwords read by
  // 00024C80 and the correction bytes are the exact ratio quantizer used by
  // 00024C8F. The original table is 2048 bytes because the quotient is scaled
  // by 1024 and the image does not clamp indices above 1024.
  const OBJECT_OCTANT_TABLE = new Uint32Array([0x0000007f, 0x00000000, 0x00000180, 0x000001ff,
    0x00000080, 0x000000ff, 0x0000017f, 0x00000100]);
  const OBJECT_BEARING_CORRECTION = globalThis.ComancheObjectBearingCorrection;
  if (!(OBJECT_BEARING_CORRECTION instanceof Uint8Array)
      || OBJECT_BEARING_CORRECTION.length !== 2048) {
    throw new Error("DOS attract runtime: exact 2048-byte bearing table is not installed");
  }

  // DOS: FUN_000227A6/00023297 [000227A6-000227BE / 00023297-0002349C]; record: analysis/functions/browser-attract.md#object-pass
  // The per-slot cells that survive from one attract pass to the next (every
  // DOS array except the active bytes 000227A6 clears).
  const OBJECT_SLOT_CELLS = ["stateAddr", "drawAddr", "fireAddr", "speed", "dosX", "dosY", "homeDosX",
    "homeDosY", "x", "y", "homeAlt", "heading", "altitude", "phase", "targetFlag", "aux", "timer",
    "steerDir", "flag", "variant", "f9", "health", "sprite", "hold", "targetSlot", "modelA", "modelB",
    "bankName", "lookupA", "lookupB", "depth", "lateral", "depthDos", "lateralDos",
    "altAcc", "vRate", "viewBearing", "designator"];

  // DOS flat 00001A70 + scancode (state) and 00001AF0 + scancode (latch): the
  // key arrays 00001900 fills (0xFF, then zero) and the keyboard ISR 00001B80
  // maintains. Only the scancodes the flight handler reads are named here.
  const KEY_SPACE = 0x39;   // [00001AA9] / latch [00001B29]
  const KEY_KP5 = 0x4c;     // [00001ABC] / latch [00001B3C]
  const KEY_TAB = 0x0f;     // latch [00001AFF]
  const KEY_RETURN = 0x1c;  // latch [00001B0C]
  const KEY_KP0 = 0x52;     // [00001AC2]
  const KEY_KPDOT = 0x53;   // [00001AC3]

  // DOS: FUN_0000D950 [0000D950-0000F317] / FUN_00018F94 [00018F94-0001959E]; record: analysis/functions/browser-attract.md#flight-integration
  const i32 = (value) => value | 0;

  // Signed high word of a 68030/386 signed 32x32 multiply. BigInt is used
  // only for the few per-ring products, so the terrain inner loop remains
  // ordinary integer arithmetic.
  // DOS: FUN_0000D950 [0000D950-0000F317] / FUN_00018F94 [00018F94-0001959E]; record: analysis/functions/browser-attract.md#terrain-renderer
  function hi32(left, right) {
    return Number((BigInt(left | 0) * BigInt(right | 0)) >> 32n) | 0;
  }

  // DOS: FUN_0002B820 [0002B820-0002B89D]; record: analysis/functions/browser-attract.md#palette-remap
  function rgb565FromDac6(palette, index) {
    const offset = index * 3;
    const red = (palette[offset] >> 1) & 0x1f;
    const green = palette[offset + 1] & 0x3f;
    const blue = (palette[offset + 2] >> 1) & 0x1f;
    return (red << 11) | (green << 5) | blue;
  }

  // DOS: FUN_0002B820 [0002B820-0002B89D]; record: analysis/functions/browser-attract.md#palette-remap
  function rgb565FromDta(palette, index) {
    return rgb565FromDac6(palette.sixBit, index);
  }

  // Target artefact; record: analysis/functions/browser-attract.md#palette-remap
  function rgb565ToRgba(word, data, offset) {
    const red = (word >> 11) & 0x1f;
    const green = (word >> 5) & 0x3f;
    const blue = word & 0x1f;
    data[offset] = (red << 3) | (red >> 2);
    data[offset + 1] = (green << 2) | (green >> 4);
    data[offset + 2] = (blue << 3) | (blue >> 2);
    data[offset + 3] = 0xff;
  }

  // Target artefact; record: analysis/functions/browser-attract.md#palette-remap
  function paletteWords(palette) {
    const words = new Uint16Array(256);
    for (let index = 0; index < 256; index += 1) words[index] = rgb565FromDta(palette, index);
    return words;
  }

  // DOS: FUN_0002B820 [0002B820-0002B89D]; record: analysis/functions/browser-attract.md#palette-remap
  function paletteKey(palette, index) {
    const offset = index * 3;
    return [
      GAMMA[palette[offset] & 0x3f],
      GAMMA[palette[offset + 1] & 0x3f],
      (palette[offset + 2] & 0x3f) * 2,
    ];
  }

  // DOS 0002B820/0002B949: candidate order, reserved indices, gamma keys,
  // weighted squared distance, and first-minimum tie behavior are preserved.
  // DOS: FUN_0002B820/0002B949 [0002B820-0002B9BA]; record: analysis/functions/browser-attract.md#palette-remap
  function nearestPaletteMap(sourcePalette, targetPalette) {
    const result = new Uint8Array(256);
    result[0] = 0;
    result[255] = 255;
    const candidates = new Array(256);
    for (let index = 1; index < 255; index += 1) candidates[index] = paletteKey(targetPalette, index);
    for (let sourceIndex = 1; sourceIndex < 255; sourceIndex += 1) {
      const source = paletteKey(sourcePalette, sourceIndex);
      let bestIndex = 1;
      let bestDistance = Number.POSITIVE_INFINITY;
      for (let candidate = 1; candidate < 255; candidate += 1) {
        const target = candidates[candidate];
        const red = 30 * Math.abs(target[0] - source[0]);
        const green = 55 * Math.abs(target[1] - source[1]);
        const blue = 15 * Math.abs(target[2] - source[2]);
        const distance = red * red + green * green + blue * blue;
        if (distance < bestDistance) {
          bestDistance = distance;
          bestIndex = candidate;
          if (distance === 0) break;
        }
      }
      result[sourceIndex] = bestIndex;
    }
    return result;
  }

  // DOS: FUN_0002A99D [0002A99D]; record: analysis/functions/browser-attract.md#palette-remap
  function missionColourPalette(evidence) {
    const source = evidence.colour.palette?.sixBit;
    if (!source) throw new Error(`${evidence.selected.colourName}: authored palette is missing`);
    const transformed = Uint8Array.from(source);
    if (Number(evidence.mission.kind.values[0]) === 1) {
      // DOS 0002A99D: the authored night-vision variant transforms Cn's
      // six-bit source palette before the common nearest-colour remap.
      for (let index = 1; index < 256; index += 1) {
        const offset = index * 3;
        const red = transformed[offset];
        const green = transformed[offset + 1];
        const blue = transformed[offset + 2];
        const brightness = ((2 * red) + (5 * green) + blue) >> 3;
        transformed[offset] = brightness >> 2;
        transformed[offset + 1] = Math.min(brightness + 10, 63);
        transformed[offset + 2] = (blue + brightness) >> 1;
      }
    }
    return transformed;
  }

  // DOS: FUN_0002B949 [0002B949-0002B9BA]; record: analysis/functions/browser-attract.md#palette-remap
  function remapColourMap(evidence, targetPalette) {
    const sourcePalette = missionColourPalette(evidence);
    const map = nearestPaletteMap(sourcePalette, targetPalette);
    const pixels = new Uint8Array(evidence.colour.pixels.length);
    for (let index = 0; index < pixels.length; index += 1) pixels[index] = map[evidence.colour.pixels[index]];
    return pixels;
  }

  // DOS: FUN_00025880 [00025880-00025DBC]; record: analysis/functions/browser-attract.md#sprite-and-console-composition
  function decodePlanarFrame(bankImage, sprite) {
    // DOS: FUN_0001644B; record: analysis/functions/browser-attract.md#resource-decoders
    // The browser expands the
    // authored planar rows into a linear lookup without changing bank bytes.
    const width = sprite.width;
    const height = sprite.height;
    const output = new Uint8Array(width * height);
    const starts = [0, 0, 0, 0];
    for (let plane = 0; plane < 4; plane += 1) {
      const count = Math.max(0, Math.ceil((width - plane) / 4));
      starts[plane] = plane === 0 ? 0 : starts[plane - 1] + Math.max(0, Math.ceil((width - (plane - 1)) / 4));
      if (starts[plane] + count > width) throw new Error("SG planar row exceeds authored sprite width");
    }
    for (let y = 0; y < height; y += 1) {
      const storedRow = height - 1 - y;
      for (let x = 0; x < width; x += 1) {
        const plane = x & 3;
        const source = sprite.pixels + (storedRow * width) + starts[plane] + (x >> 2);
        output[(y * width) + x] = bankImage[source];
      }
    }
    return output;
  }

  // DOS: FUN_00025A4D [00025A4D-00025BEA]; record: analysis/functions/browser-attract.md#sprite-and-console-composition
  function decodeColumnFrame(bankImage, sprite) {
    // DOS: FUN_00025A4D; record: analysis/functions/browser-attract.md#sprite-and-console-composition
    // The file is
    // column-major and bottom-first rather than the plane-chunked rows read by
    // 00025880; the browser normalizes authored columns once into top-down
    // pixels.
    const width = sprite.width;
    const height = sprite.height;
    const output = new Uint8Array(width * height);
    for (let y = 0; y < height; y += 1) {
      const sourceY = height - 1 - y;
      for (let x = 0; x < width; x += 1) {
        output[(y * width) + x] = bankImage[sprite.pixels + (x * height) + sourceY];
      }
    }
    return output;
  }

  // DOS: FUN_00025880 [00025880-00025DBC]; record: analysis/functions/browser-attract.md#sprite-and-console-composition
  function spriteFrame(bank, index, cache) {
    const layout = bank.payload.pixelLayout;
    const key = `${bank.name}:${index}:${layout}`;
    if (!cache.has(key)) {
      const sprite = bank.payload.sprites[index - 1];
      const pixels = layout === "column-bottom-first"
        ? decodeColumnFrame(bank.image, sprite)
        : decodePlanarFrame(bank.image, sprite);
      cache.set(key, { sprite, pixels });
    }
    return cache.get(key);
  }

  // DOS: FUN_00025880 [00025880-00025DBC]; record: analysis/functions/browser-attract.md#sprite-and-console-composition
  function drawOpaqueSprite(frame, bank, index, xReference, bottomReference, lookup, cache) {
    const decoded = spriteFrame(bank, index, cache);
    const { sprite, pixels } = decoded;
    // DOS 00025B27 computes the sprite's left pixel as xReference - xOffset.
    // The VGA plane selection uses the low two bits separately; it does not
    // round the visible sprite to a four-pixel boundary.
    const left = xReference - sprite.xOffset;
    const bottom = bottomReference + sprite.yOffset;
    const top = bottom - sprite.height + 1;
    for (let y = 0; y < sprite.height; y += 1) {
      const targetY = top + y;
      if (targetY < 0 || targetY >= VIEW_H) continue;
      for (let x = 0; x < sprite.width; x += 1) {
        const targetX = left + x;
        if (targetX < 0 || targetX >= VIEW_W) continue;
        frame[(targetY * VIEW_W) + targetX] = lookup[pixels[(y * sprite.width) + x]];
      }
    }
  }

  // DOS: FUN_0002599E [0002599E]; record: analysis/functions/browser-attract.md#sprite-and-console-composition
  function drawMaskedSprite(frame, bank, index, xReference, bottomReference, lookup, cache) {
    // DOS 0002599E: masked SG blit. Source index zero is transparent; the
    // pixel-coordinate origin and bottom-origin placement remain the same as
    // the opaque path.
    const decoded = spriteFrame(bank, index, cache);
    const { sprite, pixels } = decoded;
    // DOS 0002599E/00025B27 keeps the pixel-coordinate origin; the plane
    // mask absorbs its low two bits instead of quantizing the sprite here.
    const left = xReference - sprite.xOffset;
    const bottom = bottomReference + sprite.yOffset;
    const top = bottom - sprite.height + 1;
    for (let y = 0; y < sprite.height; y += 1) {
      const targetY = top + y;
      if (targetY < 0 || targetY >= VIEW_H) continue;
      for (let x = 0; x < sprite.width; x += 1) {
        const pixel = pixels[(y * sprite.width) + x];
        if (pixel === 0) continue;
        const targetX = left + x;
        if (targetX < 0 || targetX >= VIEW_W) continue;
        frame[(targetY * VIEW_W) + targetX] = lookup[pixel];
      }
    }
  }

  // DOS: FUN_00024CC0/0002514D [00024CC0-00024D71 / 0002514D]; record: analysis/functions/browser-attract.md#object-pass
  // SG model records are embedded at palette+770.
  // The directory's frame numbers are 1-based and the model tables contain
  // the authored azimuth/elevation frame selectors used by the object draw
  // handlers.
  function modelRecord(bank, cache) {
    const key = `${bank.name}:3D`;
    if (!cache.has(key)) {
      const paletteOffset = bank.payload.palette.offset;
      const offset = paletteOffset + 770;
      const image = bank.image;
      if (offset + 0x42 > image.length || image[offset] !== 0x33 || image[offset + 1] !== 0x44) {
        cache.set(key, null);
      } else {
        cache.set(key, {
          azimuth: image.slice(offset + 2, offset + 0x22),
          elevation: image.slice(offset + 0x22, offset + 0x42),
        });
      }
    }
    return cache.get(key);
  }

  // DOS: FUN_000253CD [000253CD]; record: analysis/functions/browser-attract.md#object-pass
  // Scaled object sprites are masked blits. This is the
  // browser surface equivalent of the DOS column scaler: the source pixels
  // remain the normalized SG image and zero remains transparent.
  function drawScaledMaskedSprite(frame, bank, index, xReference, bottomReference, lookup, cache, scale8, mirror = false) {
    const decoded = spriteFrame(bank, index, cache);
    const { sprite, pixels } = decoded;
    const width = Math.max(1, Math.floor((sprite.width * scale8) / 256));
    const height = Math.max(1, Math.floor((sprite.height * scale8) / 256));
    const offsetX = Math.trunc((sprite.xOffset * scale8) / 256);
    const offsetY = Math.trunc((sprite.yOffset * scale8) / 256);
    const left = xReference - offsetX;
    const bottom = bottomReference + offsetY;
    const top = bottom - height + 1;
    for (let y = 0; y < height; y += 1) {
      const targetY = top + y;
      if (targetY < 0 || targetY >= VIEW_H) continue;
      const sourceY = Math.min(sprite.height - 1, Math.floor((y * sprite.height) / height));
      for (let x = 0; x < width; x += 1) {
        const sourceX = Math.min(sprite.width - 1, Math.floor((x * sprite.width) / width));
        const pixel = pixels[(sourceY * sprite.width) + (mirror ? sprite.width - 1 - sourceX : sourceX)];
        if (pixel === 0) continue;
        const targetX = left + x;
        if (targetX < 0 || targetX >= VIEW_W) continue;
        frame[(targetY * VIEW_W) + targetX] = lookup[pixel];
      }
    }
  }

  // DOS: FUN_00018F94 [00018F94-0001959E]; record: analysis/functions/browser-attract.md#flight-integration
  function clamp(value, minimum, maximum) {
    return Math.max(minimum, Math.min(maximum, value));
  }

  // DOS: FUN_00018F94 [00018F94-0001959E]; record: analysis/functions/browser-attract.md#flight-integration
  function damp(value, shift) {
    if (!value) return 0;
    const positive = value > 0 ? 1 : 0;
    return i32(value - ((value >> shift) | positive));
  }

  // DOS: FUN_0000D950 [0000D950-0000F317]; record: analysis/functions/browser-attract.md#terrain-renderer
  function buildRingPageTable(detail) {
    // DOS: FUN_0000D950; record: analysis/functions/browser-attract.md#terrain-renderer
    // The authored HIGH.DTL projection tables are retained; only
    // the browser surface is linear instead of VGA planar.
    const table = new Uint8Array(250 * 256);
    const slopeSource = detail.tables[2];
    const biasSource = detail.tables[3];
    for (let ring = 0; ring < 250; ring += 1) {
      const slope = hi32(slopeSource[ring], 0x03000000);
      const bias = biasSource[ring] | 0;
      const base = ring * 256;
      for (let height = 0; height < 256; height += 1) {
        const projected = (BigInt(height - 128) * (1n << 24n) * BigInt(slope)) >> 32n;
        const fixed = projected + BigInt(bias);
        table[base + height] = fixed <= 0n ? 0 : fixed >= 0xff00n ? 0xff : Number(fixed >> 8n);
      }
    }
    return table;
  }

  // DOS: FUN_00024CC0 [00024CC0-00024D16]; record: analysis/functions/browser-attract.md#object-pass
  // HIGH.DTL table 4 is the cumulative depth table
  // used by the object projection path. Retain it as unsigned dwords because
  // the far entries intentionally cross bit 31 and the DOS compares are
  // unsigned.
  function buildRingDepthTable(detail) {
    return Uint32Array.from(detail.tables[4], (value) => value >>> 0);
  }

  // DOS: FUN_00007D25 [00007D25-0000AF4E]; record: analysis/functions/browser-attract.md#terrain-setup
  function buildBackdropDy(roll, pitch, shakePhase = 0) {
    // DOS: FUN_00007D25; record: analysis/functions/browser-attract.md#terrain-setup
    // The same 192-column horizon tilt is applied to the sky
    // and to each emitted terrain span.
    const result = new Int16Array(TERRAIN_COLS);
    // 00007D93/00007D98: `mov edx, 0x21` then `sub dl, ah` - an EIGHT-BIT
    // subtract into a register whose upper bytes stay zero. Past hi8 = 0x21
    // the limit does not go negative, it wraps to 0xFF, 0xFE, ... and the
    // clamp opens up instead of closing. This read `if (limit < 0) limit = 0`,
    // which is the same divergence src/render.s carried before it was closed
    // there.
    //
    // Unreached on this route, and recorded rather than claimed: across the
    // 800 captured DOS frames |slope| peaks at 133, and (133 * 0x40) >> 8 is
    // exactly 0x21, so the limit bottoms out at 0 without ever crossing.
    const limit = (0x21 - (((Math.abs(roll) << 6) >> 8) & 0xff)) & 0xff;
    // 00007DAD stores the CLAMPED offset, and 00007DB5 subtracts the shake
    // from it afterwards - so the shake is not itself clamped and can carry
    // the base past the limit. It is a uniform term, which is why the whole
    // horizon and the sky above it move together rather than tilting.
    const offset = clamp(pitch, -limit, limit) - (shakePhase | 0);
    const slope = i32(roll << 8);
    let accumulator = 0;
    for (let step = 0; step <= 95; step += 1) {
      accumulator = i32(accumulator + slope);
      const delta = (accumulator + 0x8000) >> 16;
      result[95 - step] = offset - delta;
    }
    result[96] = offset;
    accumulator = 0;
    for (let step = 0; step < 95; step += 1) {
      accumulator = i32(accumulator + slope);
      const delta = (accumulator + 0x8000) >> 16;
      result[97 + step] = offset + delta;
    }
    return result;
  }

  // The DOS attract tick counts are recovered; the frame cadence is not.
  // The independent shake PIT divisor is recovered (see shake-timer).
  // This scheduler is therefore a browser fixture clock, not a claim of
  // DOS cadence. It owns an explicit logical tick stream and uses RAF only to
  // present that stream. A completed presentation admits at most one logical
  // tick, matching the DOS frame-driver contract instead of catching up by
  // integrating several flight records in one displayed frame.
  const FIXTURE_TICK_HZ = 60;
  const FIXTURE_TICK_MS = 1000 / FIXTURE_TICK_HZ;

  // N/A - platform replacement; record: analysis/functions/browser-attract.md#fixture-scheduler
  class FixtureScheduler {
    // N/A - platform replacement; record: analysis/functions/browser-attract.md#fixture-scheduler
    constructor({ onTick, onPresent, onElapsed }) {
      this.onTick = onTick;
      this.onPresent = onPresent;
      this.onElapsed = onElapsed;
      this.running = false;
      this.animationHandle = 0;
      this.lastNow = null;
      this.remainder = 0;
    }

    // N/A - platform replacement; record: analysis/functions/browser-attract.md#fixture-scheduler
    start() {
      if (this.running) return;
      this.running = true;
      this.lastNow = null;
      // N/A - platform replacement; record: analysis/functions/browser-attract.md#fixture-scheduler
      const presentLoop = (now) => {
        if (!this.running) return;
        if (this.lastNow === null) this.lastNow = now;
        const elapsed = Math.max(0, now - this.lastNow);
        this.lastNow = now;
        if (this.onElapsed) this.onElapsed(elapsed);
        // Accumulate, test, THEN cap the leftover. Capping before the test
        // pins the accumulator at exactly one tick, so a frame shorter than a
        // tick throws its time away instead of carrying it, and a tick only
        // fires when the accumulator happens to land on the cap. That is
        // exact only when the display refreshes at a multiple of 60: measured
        // over ten seconds it gives 60.0 ticks/s at 60, 120 and 240 Hz, and
        // 37.5 at 75, 48.0 at 144, 50.0 at 100 and 55.0 at 165 - the fixture
        // clock running at up to two thirds speed on ordinary hardware.
        //
        // The cap stays, after the test: it is what keeps a long stall from
        // spiralling, and it preserves the contract that one presentation
        // admits at most one logical tick rather than catching up by
        // integrating several replay records into one displayed frame.
        this.remainder += elapsed;
        if (this.remainder >= FIXTURE_TICK_MS) {
          this.remainder -= FIXTURE_TICK_MS;
          this.onTick();
        }
        this.remainder = Math.min(this.remainder, FIXTURE_TICK_MS);
        this.onPresent();
        this.animationHandle = globalThis.requestAnimationFrame(presentLoop);
      };
      this.animationHandle = globalThis.requestAnimationFrame(presentLoop);
    }

    // N/A - platform replacement; record: analysis/functions/browser-attract.md#fixture-scheduler
    stop() {
      this.running = false;
      if (this.animationHandle) globalThis.cancelAnimationFrame(this.animationHandle);
      this.animationHandle = 0;
      this.lastNow = null;
      this.remainder = 0;
    }

    // Target artefact; record: analysis/functions/browser-attract.md#fixture-scheduler
    advanceTicks(count) {
      // Harness/API seam: deterministic callers can advance exact ticks without
      // involving a browser clock. This is the regression-fixture entry point.
      for (let index = 0; index < count; index += 1) this.onTick();
      this.onPresent();
    }
  }

  // DOS: FUN_00001D20 [entry 00001D20; mapped body 00001DB5-00001DE7]; record: analysis/functions/browser-attract.md#shake-timer
  function shakeTimerTick(state) {
    // 00001DBA/00001DBF: wrap after XOR/add, then 00001DC4 ROR32(3).
    const value = ((state.rng ^ 0xa50a50a0) + 0x00050a05) >>> 0;
    state.rng = ((value >>> 3) | (value << 29)) >>> 0;
    // 00001DD4 leaves phase untouched at rest; 00001DE5 forces last tick zero.
    if (state.countdown !== 0) {
      state.countdown = (state.countdown - 1) >>> 0;
      state.phase = state.countdown === 0 ? 0 : state.rng & 3;
    }
  }

  // N/A - platform replacement; record: analysis/functions/browser-attract.md#shake-timer
  function advanceShake200Hz(state, ticks) {
    if (!Number.isSafeInteger(ticks) || ticks < 0) throw new RangeError("Invalid 200 Hz tick count");
    for (let tick = 0; tick < ticks; tick += 1) {
      // DOS 00001CEB: PIT divisor 0x47B4; rational host adapter, no rounded 65 Hz.
      state.accumulator += 1193182;
      if (state.accumulator >= 200 * 0x47b4) {
        state.accumulator -= 200 * 0x47b4;
        shakeTimerTick(state);
      }
    }
  }

  // Target artefact; record: analysis/functions/browser-attract.md#fixture-scheduler
  function frameHash(frame) {
    // Harness-only FNV-1a over the canonical RGB565 words. This is a compact
    // regression key, not a source-semantic operation.
    let hash = 0x811c9dc5;
    for (let index = 0; index < frame.length; index += 1) {
      hash ^= frame[index] & 0xff;
      hash = Math.imul(hash, 0x01000193);
      hash ^= frame[index] >>> 8;
      hash = Math.imul(hash, 0x01000193);
    }
    return (hash >>> 0).toString(16).padStart(8, "0");
  }

  // DOS: FUN_0000D9E9 [0000D9E9]; record: analysis/functions/browser-attract.md#terrain-renderer
  function readMapIndex(x, y) {
    // The browser stores world positions in 16.16 after the explicit
    // 10.22-to-16.16 boundary at DEMO/object import. DOS extracts the map
    // cell from bits 22..31 of its 10.22 value; the equivalent browser
    // operation is therefore bits 16..25, not another 22-bit shift. Keeping
    // the DOS shift here silently samples a different height cell and can
    // turn the first replay tick into a false collision.
    const xCell = (x >>> 16) & MAP_MASK;
    const yCell = (y >>> 16) & MAP_MASK;
    return (yCell << 10) | xCell;
  }

  // DOS: FUN_0000D3C0 [0000D3C0-0000D8F5]; record: analysis/functions/browser-attract.md#frame-driver
  class AttractRuntime {
    // DOS: FUN_0000D3C0 [0000D3C0-0000D8F5]; record: analysis/functions/browser-attract.md#frame-driver
    constructor({ canvas, evidence, onFrame = null }) {
      this.canvas = canvas;
      this.context = canvas.getContext("2d", { alpha: false });
      this.context.imageSmoothingEnabled = false;
      this.surfaceCanvas = document.createElement("canvas");
      this.surfaceCanvas.width = VIEW_W;
      this.surfaceCanvas.height = VIEW_H;
      this.surfaceContext = this.surfaceCanvas.getContext("2d", { alpha: false });
      this.surfaceContext.imageSmoothingEnabled = false;
      this.imageData = this.surfaceContext.createImageData(VIEW_W, VIEW_H);
      this.frame = new Uint16Array(VIEW_W * VIEW_H);
      // DOS: FUN_00019681/render_reset_surface; record:
      // analysis/functions/browser-attract.md#terrain-renderer. This is the
      // logical terrain surface that survives from one replay frame to the
      // next; console/HUD pixels are never copied back into it.
      this.terrainSurface = new Uint16Array(VIEW_W * VIEW_H);
      this.passEvidence = Array.isArray(evidence?.passes) ? evidence.passes : [evidence];
      if (!this.passEvidence.length || !this.passEvidence[0]) {
        throw new Error("DOS attract runtime: no mission evidence is installed");
      }
      this.evidence = this.passEvidence[0];
      this.onFrame = onFrame;
      this.logicalTick = 0;
      this.shake = { rng: 0, phase: 0, countdown: 0, accumulator: 0 };
      this.shakePresentationUnproven = false;
      this.timerHostRemainder = 0;
      this.pass = 0;
      this.mode = "none";
      this.screen = "none";
      this.timer = 0;
      this.pan = 0;
      this.anim = 0;
      this.wobble = 0;
      this.step = 2;
      this.heli = TITLE_HELI_TOP;
      this.demoIndex = null;
      this.demo = null;
      this.demoCursor = 0;
      this.demoEnded = false;
      this.spriteCache = new Map();
      this.pendingEvents = [];
      this.trace = [];
      this.traceCount = 0;

      this.installPassEvidence(this.evidence);
      this.screenPalette = null;
      this.screenPaletteWords = null;
      this.flight = null;
      // DOS: FUN_0001959F; these are the live view-selector/camera fields
      // used by terrain and object rendering. They are explicit so replay
      // traces can prove selector transitions at a function boundary.
      this.view_variant = 1;
      this.view_angle = 0;
      this.view_sin = 0;
      this.view_cos = 0;
      this.view_slope = 0;
      this.view_offset = 0;
      this.view_camera_dos_x = 0;
      this.view_camera_dos_y = 0;
      this.view_camera_x = 0;
      this.view_camera_y = 0;
      this.view_camera_altitude = 0;
      this.view_camera_valid = false;
      // DOS 000068A5-00006947; the attract transition has already installed
      // the selected mission family when it enters DEMO<n>. Object slots are
      // therefore part of the recorded terrain frame, not a browser-only
      // enemy overlay.
      this.objects = [];
      this.objectBySlot = new Map();
      this.slotMemory = new Map();
      this.heliSlot = 0;
      this.missionTargets = 0;
      this.slotZeroWrites = 0;
      this.type4Down = 0;
      // DOS allocators scan slots 00000082..0000001F downward (100 slots).
      // [00019D10] the target latch (0 = none) and [00019D18] the candidate
      // 00024DFC leaves for the cycle; `targetSlot` below is the same latch in
      // the 31-means-none spelling the older browser code uses.
      this.targetLatch = 0;
      this.targetDefault = 0;
      // [00019D14], the locked object's depth latched by 0000D43D for RANGE.
      this.targetRange = 0;
      // [00001A70..1AEF] / [00001AF0..1B6F]: 00001900 fills the state with
      // 0xFF (released) and zeroes the latches.
      this.keyState = new Uint8Array(128).fill(0xff);
      this.keyLatch = new Uint8Array(128);
      // [000019DEC] the game-port button word: written only by 00018A06's
      // joystick path, which the keyboard device the shipped menu selects
      // never takes (000189C2-00018A06 is not carried).
      this.gamePortButtons = 0;
      // [00019D81] the sight element flag 000191B6/0001920B set and clear.
      this.weaponSightFlag = 0;
      // [00019D2C..40] the six live weapon counts (0000687D copies them from
      // the mission's [00019D44..58] loads).
      this.weaponAmmo = new Uint32Array(6);
      // Per-ring horizon archive 0000F2F7 writes ([00019E60] + ring * 256 +
      // 0x20): the page-row byte of every one of the 192 columns after each
      // ring of the flight view's march, which 00024DEA reads back.
      this.ringHorizon = new Uint8Array(250 * TERRAIN_COLS);
      // DOS 00022A00/00022AA0 move one item from each quota to its active count.
      this.effectAQuota = 0;
      this.effectBQuota = 0;
      this.effectAActive = 0;
      this.effectBActive = 0;
      // [00019D92] CHAF threat, [00019D93] threat blip, [00019D94] BULL threat.
      this.threatChaff = 0;
      this.threatBlip = 0;
      this.threatBull = 0;
      // [00019E38..3F] damage cells, [00019E40] hull, [00019E49] mission over.
      // [00019E48] the wreck's countdown, 0x64 from 000063DE; [00019DC4] how far
      // the wreck's screen has sunk (zeroed at 000056B0 and 00028761).
      this.hull = { cells: new Uint8Array(8), points: 0, down: 0, timer: 0x64 };
      this.crashDrop = 0;
      this.effectATrigger = false;
      this.effectBTrigger = false;
      this.scheduler = new FixtureScheduler({
        // N/A - platform replacement; record: analysis/functions/browser-attract.md#shake-timer
        onElapsed: (elapsed) => {
          if (this.shake.countdown !== 0 || this.shake.phase !== 0) this.shakePresentationUnproven = true;
          this.timerHostRemainder += elapsed;
          const ticks = Math.floor(this.timerHostRemainder / 5);
          this.timerHostRemainder -= ticks * 5;
          advanceShake200Hz(this.shake, ticks);
        },
        onTick: () => this.advanceAuthoritativeTick(),
        onPresent: () => this.presentAndEmit(),
      });
      this.enterNextPass();
      this.drawCurrent();
      this.recordTrace(null, this.stateSnapshot(), this.stateSnapshot());
    }

    // DOS: FUN_00019230 [00019230-000192A3]; record: analysis/functions/browser-attract.md#target-cycle
    // The older spelling of [00019D10]: slot 31 (the viewer) stands for "no
    // lock". Kept as a view of the latch so the MFD, the type-4 aim and the
    // weapon spawns read the DOS latch rather than a second selection.
    get targetSlot() {
      return this.targetLatch ? this.targetLatch : 31;
    }

    // DOS: FUN_00019230 [00019230-000192A3]; record: analysis/functions/browser-attract.md#target-cycle
    set targetSlot(slot) {
      this.targetLatch = slot === 31 ? 0 : slot;
    }

    // DOS: FUN_00028C3E/0002A320 [00028C3E,0002A320]; record: analysis/functions/browser-attract.md#mission-selection
    // Each attract pass installs its own
    // campaign-0 D/C/palette/sky family before the matching DEMO stream.
    installPassEvidence(evidence) {
      if (!evidence) throw new Error("DOS attract runtime: missing pass evidence");
      const activePalette = evidence.palette.palette?.sixBit;
      if (!activePalette) throw new Error(`${evidence.selected.paletteName}: active palette is missing`);
      this.evidence = evidence;
      this.activePalette = activePalette;
      this.terrainPalette = paletteWords(evidence.palette.palette);
      this.colourMap = remapColourMap(evidence, activePalette);
      this.ringPageTable = buildRingPageTable(evidence.detail);
      this.ringDepthTable = buildRingDepthTable(evidence.detail);
      this.skyLookup = nearestPaletteMap(evidence.sky.payload.palette.sixBit, activePalette);
      // DOS: SKY4.RLE's dominant source index 1 is the viewport fill, not a
      // near-black authored colour. The original leaves that field at the
      // active palette's entry 255 and draws only sparse non-1 marks over it.
      if (evidence.selected.skyName === "SKY4.RLE") this.skyLookup[1] = 255;
      this.skyPalette = new Uint16Array(256);
      for (let index = 0; index < 256; index += 1) this.skyPalette[index] = this.terrainPalette[this.skyLookup[index]];
      this.zoveLookup = this.buildBankLookup(evidence.banks.zove, evidence.opening.side.palette.sixBit);
      this.comaLookup = this.buildBankLookup(evidence.banks.coma, evidence.opening.title.palette.sixBit);
      this.consoleLookup = this.buildPaletteLookup(evidence.consoleImage.palette.sixBit, activePalette);
      // 000196CA calls 0002B949's remap after every console_select_variant,
      // so each image is remapped against the active palette rather than
      // borrowing variant 1's. Indexed by the variant that loads it.
      this.consoleLookups = (evidence.consoleImages || []).map(
        (image) => (image ? this.buildPaletteLookup(image.palette.sixBit, activePalette) : null));
      this.consLookup = this.buildBankLookup(evidence.banks.cons, activePalette);
      this.hudsLookup = this.buildBankLookup(evidence.banks.huds, activePalette);
      this.objectBanks = evidence.objectBanks || [];
      this.objectLookups = this.objectBanks.map((bank) => this.buildBankLookup(bank, activePalette));
      // DOS 00006494-000067A4 installs the six common transient banks at
      // 00019E74..00019E88. Keep the pointer-to-file mapping explicit so the
      // browser cannot substitute a mission bank for a weapon/effect bank.
      this.dynamicBanks = evidence.dynamicBanks || new Map();
      this.dynamicLookups = new Map();
      for (const [name, bank] of this.dynamicBanks) {
        this.dynamicLookups.set(name, this.buildBankLookup(bank, activePalette));
      }
      this.consoleWords = this.consoleLookup;
    }

    // DOS: FUN_0002B820 [0002B820-0002B89D]; record: analysis/functions/browser-attract.md#palette-remap
    buildBankLookup(bank, targetPalette) {
      // DOS: FUN_0002B820; record: analysis/functions/browser-attract.md#palette-remap
      // The browser returns RGB565 words after
      // the same source-index remap.
      return this.buildPaletteLookup(bank.payload.palette.sixBit, targetPalette);
    }

    // DOS: FUN_0002B820 [0002B820-0002B89D]; record: analysis/functions/browser-attract.md#palette-remap
    buildPaletteLookup(sourcePalette, targetPalette) {
      // DOS: FUN_0002B820; record: analysis/functions/browser-attract.md#palette-remap
      // N/A - platform replacement for the
      // VGA DAC write; index ownership and matching remain DOS-grounded.
      const map = nearestPaletteMap(sourcePalette, targetPalette);
      const words = new Uint16Array(256);
      for (let index = 0; index < 256; index += 1) words[index] = rgb565FromDac6(targetPalette, map[index]);
      return words;
    }

    // Target artefact; record: analysis/functions/browser-attract.md#fixture-scheduler
    emitFrame() {
      if (this.onFrame) this.onFrame(this.info());
    }

    // Target artefact; record: analysis/functions/browser-attract.md#fixture-scheduler
    queueEvent(name) {
      // Target artefact: event names retained by the browser fixture trace;
      // DOS event objects are outside this attract slice.
      this.pendingEvents.push(name);
    }

    // Target artefact; record: analysis/functions/browser-attract.md#fixture-scheduler
    stateSnapshot() {
      // Target artefact: canonical state copy for regression fixtures.
      return {
        pass: this.pass,
        mode: this.mode,
        screen: this.screen,
        timer: this.timer,
        shake: { ...this.shake },
        shakePresentationUnproven: this.shakePresentationUnproven,
        pan: this.pan,
        anim: this.anim,
        heli: this.heli,
        demoIndex: this.demoIndex,
        demoCursor: this.demoCursor,
        flight: this.flight
          ? {
            x: this.flight.x,
            y: this.flight.y,
            dosX: this.flight.dosX,
            dosY: this.flight.dosY,
            angle: this.flight.angle >>> 0,
            altitude: this.flight.altitude,
          }
          : null,
        view: {
          variant: this.view_variant,
          angle: this.view_angle >>> 0,
          sin: this.view_sin | 0,
          cos: this.view_cos | 0,
          slope: this.view_slope | 0,
          offset: this.view_offset | 0,
          cameraX: this.view_camera_x | 0,
          cameraY: this.view_camera_y | 0,
          cameraDosX: this.view_camera_dos_x | 0,
          cameraDosY: this.view_camera_dos_y | 0,
          cameraAltitude: this.view_camera_altitude & 0xff,
          fixedTargetDosX: this.objects.find((object) => object.slot === 31 && object.active)
            ? this.objects.find((object) => object.slot === 31 && object.active).dosX : null,
          fixedTargetDosY: this.objects.find((object) => object.slot === 31 && object.active)
            ? this.objects.find((object) => object.slot === 31 && object.active).dosY : null,
        },
        objects: this.objects.length,
      };
    }

    // Target artefact; record: analysis/functions/browser-attract.md#fixture-scheduler
    recordTrace(input, renderedState, stateAfterTick) {
      // Target artefact: bounded evidence trace; it is not game state.
      const record = {
        tick: this.logicalTick,
        input: input ? Array.from(input.raw) : null,
        events: this.pendingEvents.splice(0),
        rendered: renderedState,
        state: stateAfterTick,
        framebufferHash: frameHash(this.frame),
      };
      this.trace.push(record);
      this.traceCount += 1;
      if (this.trace.length > 256) this.trace.shift();
      this.lastTrace = record;
    }

    // Target artefact; record: analysis/functions/browser-attract.md#fixture-scheduler
    info() {
      return {
        ...this.stateSnapshot(),
        frame: this.logicalTick,
        tick: this.logicalTick,
        demoLength: this.demo?.records.length || 0,
        timing: `DOS CADENCE UNPROVEN // ${FIXTURE_TICK_HZ}Hz FIXTURE CLOCK`,
        input: "DEMO REPLAY ONLY // DOS KEYBOARD PATH UNPROVEN",
        traceCount: this.traceCount,
        traceTail: this.lastTrace || null,
      };
    }

    // N/A - platform replacement; record: analysis/functions/browser-attract.md#fixture-scheduler
    start() {
      this.scheduler.start();
    }

    // N/A - platform replacement; record: analysis/functions/browser-attract.md#fixture-scheduler
    stop() {
      this.scheduler.stop();
    }

    // N/A - platform replacement; record: analysis/functions/browser-attract.md#fixture-scheduler
    destroy() {
      // N/A - platform replacement: browser lifecycle cleanup for the
      // attract surface; the DOS counterpart is the enclosing menu loop.
      this.stop();
    }

    // DOS: FUN_00005690 [00005690-00005AE3]; record: analysis/functions/browser-attract.md#attract-cycle
    enterNextPass() {
      // DOS: FUN_00005690; record: analysis/functions/browser-attract.md#attract-cycle
      // Pass order and authored screen timers are unchanged.
      this.pass = (this.pass + 1) & 3;
      this.installPassEvidence(this.passEvidence[this.pass]);
      this.mode = "screen";
      this.pan = 0;
      this.anim = 0;
      this.wobble = 0;
      this.step = 2;
      this.heli = TITLE_HELI_TOP;
      this.demoIndex = null;
      this.demo = null;
      this.view_variant = 1;
      this.view_camera_valid = false;
      if (this.pass & 1) {
        this.screen = "fanfare";
        this.timer = 480;
        this.screenPalette = this.evidence.opening.back.palette;
      } else {
        this.screen = "side";
        this.timer = 300;
        this.screenPalette = this.evidence.opening.side.palette;
      }
      this.screenPaletteWords = paletteWords(this.screenPalette);
      this.queueEvent(`attract-pass:${this.pass}`);
    }

    // DOS: FUN_00005690 [00005690-00005AE3]; record: analysis/functions/browser-attract.md#attract-cycle
    enterTitle() {
      this.mode = "screen";
      this.screen = "title";
      this.timer = 600;
      this.pan = 0;
      this.anim = 0;
      this.wobble = 0;
      this.step = 2;
      this.heli = TITLE_HELI_TOP;
      this.screenPalette = this.evidence.opening.title.palette;
      this.screenPaletteWords = paletteWords(this.screenPalette);
      this.queueEvent("screen-enter:title");
    }

    // DOS: FUN_00018C29/00019A2D [entries 00018C29,00019A2D]; record: analysis/functions/browser-attract.md#demo-replay
    enterDemo(index) {
      // DOS: FUN_00018C29/00019A2D [entries 00018C29,00019A2D]; record: analysis/functions/browser-attract.md#demo-replay
      // The browser consumes the exact imported fixture.
      const name = `DEMO${index}.SCR`;
      if (this.evidence !== this.passEvidence[this.pass]) this.installPassEvidence(this.passEvidence[this.pass]);
      const demo = this.evidence.demos.get(name);
      if (!demo) throw new Error(`${name}: authored attract replay is missing`);
      this.mode = "demo";
      this.screen = "terrain";
      this.demoIndex = index;
      this.demo = demo;
      this.demoCursor = 0;
      this.demoEnded = false;
      // DOS DEMO headers store map positions in 10.22 coordinates. The
      // browser terrain/object surface is 16.16, so the authored world point
      // crosses the platform boundary by an arithmetic six-bit shift.
      const demoX = i32(demo.header.x >> 6);
      const demoY = i32(demo.header.y >> 6);
      // DOS: FUN_000068A5-00006947 / 00023297-0002349C. DEMO<n> is played
      // over the mission family selected for this attract pass, and the
      // authored placement records are installed before the frame loop.
      this.objects = this.spawnMissionObjects();
      this.targetSlot = 31;
      this.slotZeroWrites = 0;
      this.type4Down = 0;
      // DOS 000291CB-000291DF reads the mission's second scalar line,
      // "<chaff>,<flares>", into [00019D8D]/[00019D8E]; 0002920E-0002922F reads
      // the fourth, eight damage cells (value - 1) and the hull [00019E40].
      // [00019D8F]/[00019D90] (the counts in the air) start at 0 (0000685E).
      // Every DEMO pass starts from its own mission's values, not from state
      // carried from the previous attract replay.
      const scalarLines = this.evidence.mission.scalarLines.map((line) => line.split(",").map(Number));
      this.effectBQuota = scalarLines[0][0] & 0xff;
      this.effectAQuota = scalarLines[0][1] & 0xff;
      this.effectAActive = 0;
      this.effectBActive = 0;
      this.threatChaff = 0;
      this.threatBlip = 0;
      this.threatBull = 0;
      this.hull = {
        cells: Uint8Array.from(scalarLines[3].slice(0, 8), (value) => (value - 1) & 0xff),
        points: scalarLines[3][8] | 0,
        down: 0,
        timer: 0x64,                                             // 000063DE [00019E48]
      };
      this.crashDrop = 0;                                        // 000056B0 [00019DC4]
      this.effectATrigger = false;
      this.effectBTrigger = false;
      // DOS 0000687D-00006884 copies the mission's six weapon loads
      // [00019D44..58] (the file's second numeric line: cannon, rockets,
      // Hellfires, Stingers, bombs, wingman) to the live counts [00019D2C..40].
      this.weaponAmmo = Uint32Array.from(scalarLines[1].slice(0, 6));
      this.targetDefault = 0;
      this.targetRange = 0;
      this.weaponSightFlag = 0;
      this.flight = {
        // Keep the authoritative DOS 10.22 positions alongside the browser's
        // 16.16 render coordinates. Converting each movement term before
        // summing it drops six low bits per term and makes an otherwise exact
        // replay diverge. The renderer reads x/y; the raw pair is the replay
        // boundary and is converted only after the complete DOS update.
        dosX: demo.header.x | 0,
        dosY: demo.header.y | 0,
        x: demoX,
        y: demoY,
        angle: demo.header.angle >>> 0,
        altitude: demo.header.altitude & 0xff,
        previousAltitude: demo.header.altitude & 0xff,
        frameX: demoX,
        frameY: demoY,
        frameDosX: demo.header.x | 0,
        frameDosY: demo.header.y | 0,
        turn: 0,
        fwd: 0,
        lat: 0,
        roll: 0,
        pitch: 0,
        maxSpeed: 0x01800000,
        collective: 0,
        trigger1: 0,
        trigger2: 0,
        // DOS 000063BB initializes the weapon callback selector to 2.
        weaponMode: 2,
        axis1: 0,
        axis2: 0,
        crashes: 0,
        // [00019D60] the fuel counter, loaded from the mission's [00019D5C]
        // (the file's third numeric line) at 0000686C-00006871, and [00019D83]
        // the collective 00018D25 saves at the top of every input tick.
        fuel: i32(scalarLines[2][0]),
        collectivePrev: 0,
        // The request 00018E23 `je 0002873D` makes; nothing carries that chain.
        missionEnd: 0,
      };

      this.view_variant = 1;
      this.view_camera_valid = false;
      const initialAngleIndex = (this.flight.angle >>> 23) & 0x1ff;
      this.flight.pubSin = SINE_Q31[initialAngleIndex];
      this.flight.pubCos = SINE_Q31[initialAngleIndex + 128];
      this.buildViewBasis();
      this.screenPalette = null;
      this.screenPaletteWords = null;
      // DOS: FUN_00019681; record: analysis/functions/browser-attract.md#terrain-renderer
      // The DOS transition seeds the persistent render surface once from the
      // active ground entry before the first terrain frame.
      this.terrainSurface.fill(this.terrainPalette[255]);
      this.queueEvent(`demo-enter:DEMO${index}.SCR`);
    }

    // DOS: FUN_00023297/0002349C [00023297-0002349C]; record: analysis/functions/browser-attract.md#object-pass
    // Mission factory dispatch recovered from the ten-entry table at
    // 0002231C (file offset 0x23C1C): 00023462, 00023392, 000233DB, 00023446,
    // 00023424, 000233F7, 000233A3, 00023297, 00023413, 000233BF. Each entry
    // is 00023297's common install followed by its own state, draw and shot
    // routine stores; `fire` is the [00021FB0] pointer those leave behind
    // (00023297 itself stores 00022CA1 first).
    objectDispatch(type) {
      const dispatch = {
        0: { state: 0x23800, draw: 0x24c0a, fire: 0 },
        1: { state: 0x23f60, draw: 0x24e05, fire: 0x22ca1 },
        2: { state: 0x23cf0, draw: 0x24fed, fire: 0x22d33 },
        3: { state: 0x23a8c, draw: 0x2514d, fire: 0x22ca1 },
        4: { state: 0x23840, draw: 0x24fed, fire: 0x22ca1 },
        5: { state: 0x23cf0, draw: 0x24fed, fire: 0x22dd0 },
        6: { state: 0x23f60, draw: 0x24e05, fire: 0x22dd0 },
        7: { state: 0x23f60, draw: 0x24fed, fire: 0x22ca1 },
        8: { state: 0x23f60, draw: 0x24fed, fire: 0x22dd0 },
        9: { state: 0x23b50, draw: 0x2514d, fire: 0x22ca1 },
      };
      return dispatch[type] || dispatch[7];
    }

    // DOS: FUN_00023297/0002349C [00023297-0002349C]; record: analysis/functions/browser-attract.md#object-pass
    // The mission factories. Records are the parser's [00022248]... bytes at
    // 0002920E-00029359; the positions are `shl eax, 0x16` of the file's
    // numbers (10.22), the speed `shl eax, 0x15`. Everything 00023297 does not
    // write (timer, variant, steer, prev_*) keeps the image's zero; sprite is
    // 1 from the image. The fixed viewer slot (type 0, 00023462) writes only
    // its state, draw, aux and bank pointers.
    spawnMissionObjects() {
      const records = this.evidence.mission.objectRecords || [];
      const objects = [];
      for (const previous of this.objects) this.slotMemory.set(previous.slot, previous);
      this.objectBySlot = new Map();
      this.heliSlot = 0;                                         // 000227B4 [00022368]
      // 00029266-0002926C: one count per '*' record; 000237E6 counts them down.
      this.missionTargets = records.filter((record) => record.continuation).length;
      let standardSlot = 30;
      for (let recordIndex = 0; recordIndex < records.length; recordIndex += 1) {
        const record = records[recordIndex];
        const dispatch = this.objectDispatch(record.type);
        const bankA = this.objectBanks[record.f2] || null;
        const bankB = this.objectBanks[record.f3] || null;
        // Type 0 is the fixed slot 31 path; all other factory entries consume
        // the first-30 allocator in descending order, exactly as 00023297.
        const slot = record.type === 0 ? 31 : standardSlot--;
        const object = this.makeObjectSlot(slot);
        object.recordIndex = recordIndex;
        object.dynamic = false;
        object.type = record.type | 0;
        object.active = true;
        object.stateAddr = dispatch.state;
        object.drawAddr = dispatch.draw;
        object.fireAddr = dispatch.fire;
        object.aux = record.type === 0 ? 0 : [9, 6, 7, 8, 3][record.f1] ?? 0;   // 000232E9 / 00023484
        object.modelA = bankA;
        object.modelB = bankB;
        object.lookupA = bankA ? this.objectLookups[record.f2] : null;
        object.lookupB = bankB ? this.objectLookups[record.f3] : null;
        if (record.type !== 0) {
          object.flag = record.continuation ? 1 : 0;             // 000232B3 [00022367]
          object.hold = record.f10 | 0;                          // 000232BE [00022378]
          object.f9 = record.f9 & 0xff;                          // 000232CA [00022382]
          object.health = record.f7 & 0xff;                      // 0002331D [00022380]
          object.speed = i32((record.f8 & 0xff) << 21);          // 00023329-00023332 [00022381]
          object.dosX = i32(record.x << 22);                     // 00023339 [0002234C]
          object.dosY = i32(record.y << 22);                     // 00023345 [00022350]
          object.phase = 0;                                      // 00023351
          object.heading = record.heading & 0xff;                // 00023358 [0002237D]
          // 00023363-0002338B: ground + 0x0B, saturated.
          object.altitude = this.objectGroundByte(object, 0x0b);
          if (record.type === 4) this.heliSlot = slot;           // 0002343F [00022368]
        }
        this.syncObjectRender(object);
        objects.push(object);
        this.objectBySlot.set(slot, object);
      }
      // DOS keeps the player/fixed object in slot 31 independently of the
      // mission placement count. It is updated by 00023800 and is the target
      // consumed by 000256C8 when variant 7 aims the fixed camera. Some
      // attract mission records contain a type-0 entry that installs this
      // slot; the other connected passes still have the live slot, so supply
      // the same minimal state when their placement list does not.
      if (!this.objectBySlot.has(31)) {
        const object = this.makeObjectSlot(31);
        object.dynamic = false;
        object.type = 0;
        object.active = true;
        object.stateAddr = 0x23800;
        object.drawAddr = 0x24c0a;
        objects.push(object);
        this.objectBySlot.set(31, object);
      }
      return objects;
    }

    // ---- the per-slot object table -----------------------------------------
    // DOS keeps one array per field, indexed by slot, for the whole mission:
    // a slot that is freed (active = 0) keeps every other byte it had, and the
    // factories below write only the fields their listing writes. One JS object
    // per slot number reproduces that: claimObjectSlot() hands back the same
    // object a freed slot had, so a field a factory does not write is the stale
    // value DOS would read.

    // DOS: FUN_000227A6/00023297 [000227A6-000227BE / 00023297-0002349C]; record: analysis/functions/browser-attract.md#object-pass
    // The slot's shipped initial cells (file image, flat 0x21AA7/0x21A25/
    // 0x219A3/0x2107C/0x21284/0x20C6C/0x20E74): prev_alt and altitude 0xAA,
    // sprite 1, x = prev_x 0x40000000, y = prev_y 0xD4800000 for slots 1..130;
    // every other per-slot byte is 0 and 000227A6 clears the active bytes at
    // mission start. A field no factory writes (slot 31's prev_*, a wreck's
    // heading, a flare's prev_alt) is read from these.
    //
    // The arrays also outlive a mission: the attract cycle plays four DEMOs
    // back to back and 000227A6 clears only the active bytes, so the next
    // mission's factories find the last pass's timer, variant, steer, sprite,
    // prev_* and so on (the oracle's pass 2..4 rows start with them). The
    // per-slot cells of the previous object table are carried in slotMemory.
    makeObjectSlot(slot) {
      const fresh = this.makeObjectSlotImage(slot);
      const old = this.slotMemory.get(slot);
      if (old) {
        for (const key of OBJECT_SLOT_CELLS) fresh[key] = old[key];
      }
      return fresh;
    }

    // DOS: FUN_000227A6/00023297 [000227A6-000227BE / 00023297-0002349C]; record: analysis/functions/browser-attract.md#object-pass
    // One slot as the shipped file image has it (see makeObjectSlot).
    makeObjectSlotImage(slot) {
      return {
        slot,
        recordIndex: -1,
        active: false,
        dynamic: true,
        type: -1,
        stateAddr: 0,
        drawAddr: 0,
        fireAddr: 0,
        speed: 0,
        dosX: 0x40000000,
        dosY: i32(0xd4800000),
        homeDosX: 0x40000000,
        homeDosY: i32(0xd4800000),
        x: 0x40000000 >> 6,
        y: i32(0xd4800000) >> 6,
        homeAlt: 0xaa,
        heading: 0,
        altitude: 0xaa,
        phase: 0,
        targetFlag: 0,
        aux: 0,
        timer: 0,
        steerDir: 0,
        flag: 0,
        variant: 0,
        f9: 0,
        health: 0,
        sprite: 1,
        hold: 0,
        targetSlot: 0,
        effectCounter: null,
        modelA: null,
        modelB: null,
        bankName: null,
        lookupA: null,
        lookupB: null,
        depth: 0,
        lateral: 0,
        depthDos: 0,
        lateralDos: 0,
        // [00021694] the 8.24 altitude, [0002148C] its rate (00022890's
        // round), [00021CAF] the view bearing 00024CBA stores, [00021C2D] the
        // designator row 00024DC6 stores: image zeros, written by the routines
        // named in their own comments.
        altAcc: 0,
        vRate: 0,
        viewBearing: 0,
        designator: 0,
        projectPage: 0,
        projectClipRing: -1,
        pageValid: false,
      };
    }

    // N/A - platform replacement; record: analysis/functions/browser-attract.md#object-pass
    // The JS object that stands for DOS's slot `slot`; made on first use,
    // handed back (with its stale cells) on every later claim.
    claimObjectSlot(slot) {
      let object = this.objectBySlot.get(slot);
      if (!object) {
        object = this.makeObjectSlot(slot);
        this.objects.push(object);
        this.objectBySlot.set(slot, object);
      }
      // Target artefact: the proof's label for a countermeasure; DOS has no such
      // byte, so a slot taken by anything else must not keep it.
      object.effectCounter = null;
      return object;
    }

    // DOS: FUN_00022A00 [00022A09-00022A20]; record: analysis/functions/browser-attract.md#object-pass
    // The free-slot scan every transient factory shares (00022A09/00022AA9/
    // 00022B12/00022CA2/00022D34/00022DD1/00022E79/00022F99/000227C1): ebx walks
    // 0x82 downward and ecx = 0x64 bounds it to 100 slots (0x82..0x1F). The
    // first slot whose active byte is zero wins; none is a silent return.
    findFreeObjectSlot() {
      for (let slot = 0x82, remaining = 0x64; remaining > 0; slot -= 1, remaining -= 1) {
        const held = this.objectBySlot.get(slot);
        if (!held || !held.active) return slot;
      }
      return -1;
    }

    // DOS: FUN_000227D8 [000227FE-00022803]; record: analysis/functions/browser-attract.md#object-pass
    // `mov eax, [bank pointer]; mov [ecx*4 + 0002044C], eax`: bank A of the slot.
    bindObjectBank(object, bankName) {
      object.bankName = bankName;
      object.modelA = this.dynamicBanks.get(bankName) || null;
      object.lookupA = this.dynamicLookups.get(bankName) || null;
    }

    // DOS: FUN_00023CF0 [00023D77-00023D9D]; record: analysis/functions/browser-attract.md#object-pass
    // The map byte under a 10.22 position: `shld` twice builds
    // (y >> 22) << 10 | (x >> 22), the same 1024x1024 index the terrain walk
    // uses (readMapIndex keeps the 16.16 spelling of it).
    objectMapByte(dosX, dosY) {
      const index = (((dosY >>> 22) << 10) | (dosX >>> 22)) >>> 0;
      return this.evidence.height.pixels[index] | 0;
    }

    // DOS: FUN_00023CF0 [00023D77-00023D9F]; record: analysis/functions/browser-attract.md#object-pass
    // `shl al, 1` wraps in eight bits (its carry is overwritten by the add that
    // follows) and the add saturates: `add al, N; jae; mov al, 0xff`.
    objectGroundByte(object, add) {
      const doubled = (this.objectMapByte(object.dosX, object.dosY) << 1) & 0xff;
      return Math.min(0xff, doubled + add);
    }

    // DOS: FUN_00023CF0 [00023D77-00023D9F]; record: analysis/functions/browser-attract.md#object-pass
    // Kept under the name the weapon states (Unproven, below) already use.
    objectGroundTarget(object, clearance) {
      return this.objectGroundByte(object, clearance);
    }

    // DOS: FUN_00023D46 [00023D46-00023D70]; record: analysis/functions/browser-attract.md#object-pass
    // The Q31 step every state shares (00023514, 00023704, 00023D46, 00023F9C,
    // 00023963, 000241E8, 00024515): the high dword of speed * table[heading*8],
    // y minus the cosine term, x plus the sine term, in 10.22.
    objectMove(object) {
      const angle = (object.heading << 1) & 0x1ff;
      const sin = SINE_Q31[angle];
      const cos = SINE_Q31[angle + 128];
      object.dosY = i32(object.dosY - hi32(object.speed, cos));
      object.dosX = i32(object.dosX + hi32(object.speed, sin));
    }

    // DOS: FUN_00023CF0 [00023D03-00023D25]; record: analysis/functions/browser-attract.md#object-pass
    // The three snapshot stores every state opens with: prev_x, prev_y, prev_alt.
    objectSnapshot(object) {
      object.homeDosX = object.dosX;
      object.homeDosY = object.dosY;
      object.homeAlt = object.altitude;
    }

    // N/A - platform replacement; record: analysis/functions/browser-attract.md#object-pass
    // The render pair is the 10.22 position's arithmetic six-bit shift; the
    // renderer (view transform, aspect) reads x/y, the logic reads dosX/dosY.
    syncObjectRender(object) {
      object.x = object.dosX >> 6;
      object.y = object.dosY >> 6;
    }

    // DOS: FUN_000227BF [000227BF-0002287C]; record: analysis/functions/browser-attract.md#object-pass
    // 000227D8 does not clone the parent. It installs the BOOM wreckage handler
    // pair in the first free slot and copies the parent's position and altitude;
    // every other field of the slot keeps what its last occupant left.
    spawnWreckage(parent) {
      const slot = this.findFreeObjectSlot();                    // 000227C1-000227D7
      if (slot < 0) return null;
      const object = this.claimObjectSlot(slot);
      object.dynamic = true;
      object.aux = 0;                                            // 000227DA
      object.active = true;                                      // 000227E1
      object.stateAddr = 0x237b0;                                // 000227E8
      object.drawAddr = 0x2519d;                                 // 000227F3
      this.bindObjectBank(object, "BOOM.RLE");                   // 000227FE [00019E88]
      object.sprite = 1;                                         // 0002280A
      object.dosX = parent.dosX;                                 // 00022811
      object.dosY = parent.dosY;                                 // 0002281F
      object.altitude = parent.altitude;                         // 0002282D
      this.syncObjectRender(object);
      // 00022839-00022871: the distance-scaled explosion sound through 00004E8E.
      // Sound is outside the first playable scope (AGENTS.md).
      return object;
    }

    // DOS: FUN_00024997 [00024997-00024A32]; record: analysis/functions/browser-attract.md#object-pass
    // The destruction tail: the slot itself becomes the BOOM handler pair at
    // its previous position and altitude. phase, timer and the rest are left.
    convertObjectToExplosion(object) {
      object.stateAddr = 0x237b0;                                // 00024997
      object.drawAddr = 0x2519d;                                 // 000249A2
      object.aux = 0;                                            // 000249AD
      this.bindObjectBank(object, "BOOM.RLE");                   // 000249B4 [00019E88]
      object.sprite = 1;                                         // 000249C0
      object.dosX = object.homeDosX;                             // 000249C7
      object.dosY = object.homeDosY;                             // 000249D5
      object.altitude = object.homeAlt;                          // 000249E3
      this.syncObjectRender(object);
      // 000249EF-00024A31: the distance-scaled explosion sound (00004E8E).
    }

    // DOS: FUN_00022CA1/00022D33/00022DD0 [00022CA1-00022E69]; record: analysis/functions/browser-attract.md#object-pass
    // The three per-object shot routines [00021FB0] points at. Each one takes
    // the first free slot and installs a shell at the shooter's position,
    // heading and altitude (the caller has already added the turret and +6):
    //   00022CA1: state 000234E0, bank [00019E7C] (ROCK)
    //   00022D33: state 000236D0, bank [00019E84] (STGR)
    //   00022DD0: state 00024860, bank [00019E80] (HELL), target [00021D31] = 0x1F
    // All three write timer = 0 and aux = 8, active, draw 0002514D and speed
    // 0x04000000; none writes phase, sprite or the other bytes.
    objectFire(shooter) {
      let state;
      let bankName;
      let missile = false;
      if (shooter.fireAddr === 0x22ca1) {
        state = 0x234e0;
        bankName = "ROCK.RLE";
      } else if (shooter.fireAddr === 0x22d33) {
        state = 0x236d0;
        bankName = "STGR.RLE";
      } else if (shooter.fireAddr === 0x22dd0) {
        state = 0x24860;
        bankName = "HELL.RLE";
        missile = true;
      } else {
        return null;
      }
      const slot = this.findFreeObjectSlot();                    // 00022CA2-00022CB9
      if (slot < 0) return null;
      const object = this.claimObjectSlot(slot);
      object.dynamic = true;
      object.timer = 0;                                          // 00022CBB
      object.aux = 8;                                            // 00022CC2
      if (missile) object.targetSlot = 0x1f;                     // 00022DF8-00022DFA
      object.active = true;                                      // 00022CC9
      object.stateAddr = state;                                  // 00022CD0
      object.drawAddr = 0x2514d;                                 // 00022CDB
      this.bindObjectBank(object, bankName);                     // 00022CE6
      object.speed = 0x04000000;                                 // 00022CF2
      object.dosX = shooter.dosX;                                // 00022CFE
      object.dosY = shooter.dosY;                                // 00022D0C
      object.heading = shooter.heading;                          // 00022D1A
      object.altitude = shooter.altitude;                        // 00022D26
      this.syncObjectRender(object);
      return object;
    }

    // DOS: FUN_00022E70/00022F90 [00022E70-000230AD]; record: analysis/functions/browser-attract.md#weapon-fire.
    // Unproven: NOT a port of the DOS launchers (no rail, no ammunition, flight
    // angle instead of [00019CB8]/[00019CBC]); src/object.s weapon_fire_* is,
    // checked 35/35 by tools/check-weapon-launch.py. Weapon factories
    // place the transient model beside the frame-start viewer before the
    // next 000234A4 pass. Positions are 10.22 like every object's.
    spawnWeaponObject(stateAddr, bankName, targetSlot = this.targetSlot) {
      const angleIndex = (this.flight.angle >>> 23) & 0x1ff;
      const sin = SINE_Q31[angleIndex];
      const cos = SINE_Q31[angleIndex + 128];
      const lateral = hi32(0x03000000, cos);
      const forward = hi32(0x03000000, sin);
      const slot = this.findFreeObjectSlot();
      if (slot < 0) return null;
      const object = this.claimObjectSlot(slot);
      object.dynamic = true;
      object.active = true;
      object.stateAddr = stateAddr;
      object.drawAddr = 0x2514d;
      this.bindObjectBank(object, bankName);
      object.targetSlot = targetSlot;
      object.dosX = i32(this.flight.frameDosX + lateral + forward);
      object.dosY = i32(this.flight.frameDosY + hi32(0x03000000, sin) - hi32(0x03000000, cos));
      object.altitude = this.flight.altitude;
      object.heading = (this.flight.angle >>> 24) & 0xff;
      object.speed = 0x04000000;
      object.timer = 0;
      object.phase = 0;
      object.hold = 0;
      this.syncObjectRender(object);
      return object;
    }

    // DOS: FUN_00022A00 [00022A00-00022A97]; record: analysis/functions/browser-attract.md#object-pass.
    // BULL: the launcher tests only its quota [00019D8E] (the "no flare in the
    // air" test lives in the decision at 00019581, the key path 000195A3 jumps
    // here without it), takes the first free slot, moves one count from the
    // quota to [00019D90] and installs 00024480 with timer 0x14 and bank [00019E74].
    spawnEffectA() {
      if (this.effectAQuota === 0) return null;                  // 00022A00-00022A07
      const slot = this.findFreeObjectSlot();                    // 00022A09-00022A1F
      if (slot < 0) return null;
      const object = this.claimObjectSlot(slot);
      this.effectAQuota = (this.effectAQuota - 1) & 0xff;        // 00022A23
      this.effectAActive = (this.effectAActive + 1) & 0xff;      // 00022A29
      object.timer = 0x14;                                       // 00022A2F
      object.stateAddr = 0x24480;                                // 00022A36
      object.sprite = 1;                                         // 00022A41
      this.bindObjectBank(object, "BULL.RLE");                   // 00022A48 [00019E74]
      object.effectCounter = "A";
      this.installCountermeasure(object);
      return object;
    }

    // DOS: FUN_00022AA0 [00022AA0-00022AF4]; record: analysis/functions/browser-attract.md#object-pass.
    // CHAF: the same factory with quota [00019D8D], active count [00019D8F],
    // timer 0x1E, state 000244A0 and bank [00019E78].
    spawnEffectB() {
      if (this.effectBQuota === 0) return null;                  // 00022AA0-00022AA7
      const slot = this.findFreeObjectSlot();                    // 00022AA9-00022ABF
      if (slot < 0) return null;
      const object = this.claimObjectSlot(slot);
      this.effectBQuota = (this.effectBQuota - 1) & 0xff;        // 00022AC3
      this.effectBActive = (this.effectBActive + 1) & 0xff;      // 00022AC9
      object.timer = 0x1e;                                       // 00022ACF
      object.stateAddr = 0x244a0;                                // 00022AD6
      object.sprite = 1;                                         // 00022AE1
      this.bindObjectBank(object, "CHAF.RLE");                   // 00022AE8 [00019E78]
      object.effectCounter = "B";
      this.installCountermeasure(object);
      return object;
    }

    // DOS: FUN_00022A00 [00022A54-00022A97]; record: analysis/functions/browser-attract.md#object-pass.
    // The common tail both launchers jump to: aux 0, active, draw 0002519D and
    // the player's LIVE position ([00019CD4]/[00019CD8], after this frame's
    // integration) and altitude [00019DFC]. 000074C0 then redraws the counter.
    installCountermeasure(object) {
      object.dynamic = true;
      object.aux = 0;                                            // 00022A5B
      object.active = true;                                      // 00022A62
      object.drawAddr = 0x2519d;                                 // 00022A69
      object.dosX = this.flight.dosX;                            // 00022A74
      object.dosY = this.flight.dosY;                            // 00022A80
      object.altitude = this.flight.altitude & 0xff;             // 00022A8C
      this.syncObjectRender(object);
    }

    // DOS: FUN_00022890 [00022890-000229F0]; record: analysis/functions/browser-attract.md#weapon-fire
    // The cannon launcher, console page 0, dispatched from 000191B6-0001922E
    // through [00019D68]. It takes the shared slot scan (000228A2-000228B8:
    // slots 0x82 down, 0x64 of them), spends two rounds, and installs a round
    // at the flight position (the LIVE [00019CD4]/[00019CD8], before this
    // tick's move) with the flight heading [00019D04] >> 24, the altitude
    // byte [00019DFC] and its 8.24 spelling, and a vertical rate of
    // -pitch << 22. With a lock it re-aims: heading = the target's view
    // bearing [00021CAF], and the rate becomes
    // ((alt_target - alt) << 23) / n + 0xC00000, n = ((|lateral| >> 1 +
    // depth) << 2) / speed, from the lateral/depth 00024B17 stored this frame.
    //
    // Not carried: 000228C3-000228CA / 000228E6-000228ED set [00019D89] and
    // call 000073D0 (the console's count redraw; this reference redraws the
    // console every frame) and 000228F2-000228FD play the firing sound.
    fireCannon() {
      const flight = this.flight;
      // 00022890-000228A0: no rounds, or the gun's damage cell [00019E3D]
      // (hull.cells[5]) negative, empties the count and leaves.
      if (this.weaponAmmo[0] === 0 || (this.hull.cells[5] & 0x80) !== 0) {
        this.weaponAmmo[0] = 0;                                  // 000228B9
        return null;
      }
      const slot = this.findFreeObjectSlot();                    // 000228A2-000228B8
      if (slot < 0) return null;
      this.weaponAmmo[0] = this.weaponAmmo[0] >= 2 ? this.weaponAmmo[0] - 2 : 0;   // 000228D2-000228E5
      const object = this.claimObjectSlot(slot);
      object.dynamic = true;
      object.aux = 0;                                            // 00022903 [00021DB3]
      object.active = true;                                      // 0002290A [00021921]
      object.stateAddr = 0x244e0;                                // 00022911 [00020244]
      object.drawAddr = 0x2519d;                                 // 0002291C [0002003C]
      this.bindObjectBank(object, "BULL.RLE");                   // 00022927 [0002044C] = [00019E74]
      object.sprite = 1;                                         // 00022933 [000219A3]
      object.speed = 0x8000000;                                  // 0002293A [0001FE34]
      object.dosX = flight.dosX;                                 // 00022946 [00019CD4]
      object.dosY = flight.dosY;                                 // 00022952 [00019CD8]
      object.altitude = flight.altitude & 0xff;                  // 0002295E-00022963 [00019DFC]
      object.altAcc = (object.altitude << 24) >>> 0;             // 00022969-0002296C [00021694]
      object.vRate = i32((-flight.pitch) << 22);                 // 00022973-0002297D [0002148C], pitch [00019CF4]
      object.heading = (flight.angle >>> 24) & 0xff;             // 00022984-0002298C [00019D04]
      const latch = this.targetLatch & 0xff;                     // 00022992 movzx ebx, byte [00019D10]
      if (latch !== 0) {                                         // 00022999-0002299B
        const target = this.objectBySlot.get(latch) || this.makeObjectSlotImage(latch);
        object.heading = target.viewBearing & 0xff;              // 0002299D-000229A3
        let eax = target.lateralDos | 0;                         // 000229A9 [ebx*4 + 0002085C]
        eax ^= eax >> 31;                                        // 000229B0-000229B1 cdq / xor: one's complement
        eax = (eax >>> 1) | 0;                                   // 000229B3
        eax = (eax + (target.depthDos | 0)) | 0;                 // 000229B5 [ebx*4 + 00020A64]
        eax = (eax << 2) >>> 0;                                  // 000229BC
        const n = Math.floor(eax / (object.speed >>> 0));        // 000229BF-000229C1 xor edx / div [speed]
        if (n === 0) return object;                              // 000229C8-000229CA
        const delta = (target.altitude & 0xff) - (flight.altitude & 0xff);   // 000229CE-000229DC
        object.vRate = i32(Math.trunc(((delta << 23) | 0) / n) + 0xc00000);  // 000229DE-000229E9 idiv ebp
      }
      return object;
    }

    // DOS: FUN_000244E0 [000244E0-00024677]; record: analysis/functions/browser-attract.md#weapon-fire
    // The cannon round. Sprite frame 1 is flight; any higher frame is the
    // burst (00024659: count up, free the slot after frame 7). In flight it
    // latches X, Y and altitude, moves along its heading (the 00024515
    // mover), drops the vertical rate by 0x100000 and adds it to the 8.24
    // altitude: a carry out of a non-negative rate frees the slot, no carry
    // on a negative rate bursts at the latched position. The altitude byte
    // is the 8.24 value's top byte; at or below the terrain byte
    // (2h & 0xFF) + 1 the round is a burst already at frame 3 (00024650).
    // Otherwise the first of slots 30..1 that is active, within 0x14 half
    // steps of altitude and 0x1C00000 on both axes loses a health point (its
    // borrow sets bit 0 of its phase) and the round bursts.
    objectStateBullet(object) {
      if (object.sprite > 1) {                                   // 000244E0-000244E7
        object.sprite = (object.sprite + 1) & 0xff;              // 00024659
        if (object.sprite > 7) object.active = false;            // 0002465F-00024668
        return;
      }
      object.homeDosX = object.dosX;                             // 000244ED-000244F4 [0002107C]
      object.homeDosY = object.dosY;                             // 000244FB-00024502 [00021284]
      object.homeAlt = object.altitude;                          // 00024509-0002450F [00021AA7]
      this.objectMove(object);                                   // 00024515-0002453F
      object.vRate = i32(object.vRate - 0x100000);               // 00024546
      const rate = object.vRate;                                 // 00024551-00024558
      const sum = (object.altAcc >>> 0) + (rate >>> 0);          // 0002455C / 0002456B
      const carry = sum > 0xffffffff;
      object.altAcc = sum >>> 0;
      if (rate >= 0) {                                           // 0002455A js 0002456B
        if (carry) {                                             // 00024563 jb 00024668
          object.active = false;
          return;
        }
      } else if (!carry) {                                       // 00024572 jae 00024621
        this.objectBulletBurst(object);
        return;
      }
      object.altitude = (object.altAcc >>> 24) & 0xff;           // 00024578-0002457F
      // 00024585-000245A9: the map byte under the round, doubled in eight
      // bits plus one; `jbe` bursts when the altitude is at or below it.
      const ground = (((this.objectMapByte(object.dosX, object.dosY) << 1) & 0xff) + 1) & 0xff;
      if (object.altitude <= ground) {
        object.sprite = 3;                                       // 00024650
        this.objectBulletBurst(object);                          // 00024657
        return;
      }
      for (let slot = 0x1e; slot >= 1; slot -= 1) {              // 000245B5, 00024670-00024671
        const other = this.objectBySlot.get(slot);
        if (!other || !other.active) continue;                   // 000245BA-000245C1
        if (this.altitudeSpread(object.altitude, other.altitude) > 0x14) continue;   // 000245C7-000245DB
        if (this.positionSpread(object.dosX, other.dosX) > 0x1c00000) continue;     // 000245E1-000245F7
        if (this.positionSpread(object.dosY, other.dosY) > 0x1c00000) continue;     // 000245F9-0002460F
        if (other.health === 0) other.phase = (other.phase | 1) & 0xff;             // 00024611-0002461A borrow
        other.health = (other.health - 1) & 0xff;                // 00024611 sub byte [ebx + 00021F93], 1
        this.objectBulletBurst(object);                          // 00024621
        return;
      }
    }

    // DOS: FUN_000244E0 [00024621-0002464F]; record: analysis/functions/browser-attract.md#weapon-fire
    // The burst: the frame counter steps and X, Y and altitude go back to the
    // values latched at 000244ED-0002450F.
    objectBulletBurst(object) {
      object.sprite = (object.sprite + 1) & 0xff;                // 00024621
      object.dosX = object.homeDosX;                             // 00024627-0002462E
      object.dosY = object.homeDosY;                             // 00024635-0002463C
      object.altitude = object.homeAlt;                          // 00024643-00024649
    }

    // DOS: FUN_00019230 [00019230-000192A3]; record: analysis/functions/browser-attract.md#target-cycle
    // The target latch [00019D10] and its cycle. Two things feed it: a make
    // latch of Tab or Return ([00001AFF]/[00001B0C]) and a pending replay
    // count [00019DF3] consumed one per tick. A damaged targeting cell
    // [00019E3A] (hull.cells[2]) or a console variant past 5 gates it; the
    // latches survive a gated tick. An empty latch seeds from the candidate
    // [00019D18] 00024DFC leaves; otherwise the walk takes the next object
    // 1..0x1E (wrapping to 1) whose targetability byte [00021BAB] is set, or
    // the object it started from.
    targetCycle() {
      const flight = this.flight;
      const pressed = this.keyLatch[KEY_TAB] | this.keyLatch[KEY_RETURN];   // 00019230-0001923B
      if (pressed === 0) {
        if (flight.trigger2 === 0) return;                       // 0001923D-00019244
        flight.trigger2 = (flight.trigger2 - 1) & 0xff;          // 00019246
      }
      if ((this.hull.cells[2] & 0x80) !== 0) return;             // 0001924C-00019253
      if (this.view_variant > 5) return;                         // 00019255-0001925C
      this.keyLatch[KEY_TAB] = 0;                                // 0001925E
      this.keyLatch[KEY_RETURN] = 0;                             // 00019265
      if (this.targetLatch === 0) {                              // 0001926C-00019273
        this.targetLatch = this.targetDefault;                   // 00019275-0001927A
        return;                                                  // 0001927F
      }
      let slot = this.targetLatch;                               // 00019281
      for (;;) {
        slot += 1;                                               // 00019287
        if (slot > 0x1e) slot = 1;                               // 00019288-0001928D
        const candidate = this.objectBySlot.get(slot);
        if (candidate && candidate.targetFlag !== 0) break;      // 00019292-00019299
        if (slot === this.targetLatch) break;                    // 0001929B-000192A1
      }
      this.targetLatch = slot;                                   // 000192A3
    }

    // DOS: FUN_000234E0 [0002357B-0002358F]; record: analysis/functions/browser-attract.md#object-pass
    // `mov al, a; sub al, b; rcr al, 1; cbw; xor al, ah`: the borrow of the
    // subtraction rotates into bit 7, so al is the signed nine-bit difference
    // halved, and the xor with its sign makes that a ONE'S-complement
    // magnitude. Every "close enough in altitude" test (cmp al, 0xF / 0x14) is
    // on this byte.
    altitudeSpread(altitude, reference) {
      const difference = (altitude & 0xff) - (reference & 0xff);
      const carry = difference < 0 ? 1 : 0;
      const al = (((difference & 0xff) >>> 1) | (carry << 7)) & 0xff;
      return al ^ ((al & 0x80) ? 0xff : 0);
    }

    // DOS: FUN_000234E0 [00023595-000235C5]; record: analysis/functions/browser-attract.md#object-pass
    // `sub eax, [..]; cdq; xor eax, edx; cmp eax, 0x1400000; ja`: a 32-bit
    // ONE'S-complement magnitude, compared unsigned.
    positionSpread(a, b) {
      const difference = i32(a - b);
      return (difference ^ (difference >> 31)) >>> 0;
    }

    // DOS: FUN_000234E0 [000234E0-0002357A]; record: analysis/functions/browser-attract.md#object-pass
    // The enemy shell installed by 00022CA1: step, climb check, fall by one.
    objectStateShell(object) {
      this.objectSnapshot(object);                               // 000234E0-00023502
      object.timer = (object.timer + 1) & 0xff;                  // 00023508
      if (object.timer & 0x80) {                                 // 0002350E js 00024997
        this.convertObjectToExplosion(object);
        return;
      }
      this.objectMove(object);                                   // 00023514-0002353E
      // 00023545-0002356F: ground = (map << 1) + 1 in eight bits (`inc al`
      // wraps 0xFF to 0, it does not saturate); at or below it the shell bursts.
      const ground = (((this.objectMapByte(object.dosX, object.dosY) << 1) & 0xff) + 1) & 0xff;
      if (object.altitude <= ground) {
        this.convertObjectToExplosion(object);
        return;
      }
      object.altitude = (object.altitude - 1) & 0xff;            // 00023575
      this.objectShellProximity(object);                         // 0002357B
    }

    // DOS: FUN_000236D0 [000236D0-000237A1]; record: analysis/functions/browser-attract.md#object-pass
    // The lobbed shell installed by 00022D33: it homes its altitude on the
    // player's [00019DFC] (down by 5, up by 0x12) before the same ground and
    // proximity tests.
    objectStateShellLob(object) {
      this.objectSnapshot(object);                               // 000236D0-000236F2
      object.timer = (object.timer + 1) & 0xff;                  // 000236F8
      if (object.timer & 0x80) {                                 // 000236FE js 00024997
        this.convertObjectToExplosion(object);
        return;
      }
      this.objectMove(object);                                   // 00023704-0002372E
      const player = this.view_camera_altitude & 0xff;           // [00019DFC], see objectMobileAim
      if (object.altitude !== player) {                          // 00023735-00023741
        if (object.altitude < player) {                          // 00023743 jb 00023754
          const climbed = object.altitude + 0x12;                // 00023754
          if (climbed > 0xff) {                                  // 0002375B jae not taken
            object.altitude = 0xfe;                              // 0002375D
            object.timer = (object.timer + 0x0a) & 0xff;         // 00023764
            if (object.timer & 0x80) {                           // 0002376B js 00024997
              this.convertObjectToExplosion(object);
              return;
            }
          } else {
            object.altitude = climbed;
          }
        } else {
          if (object.altitude - 5 < 0) {                         // 00023745/0002374C jb 00024997
            object.altitude = (object.altitude - 5) & 0xff;
            this.convertObjectToExplosion(object);
            return;
          }
          object.altitude -= 5;
        }
      }
      const ground = (((this.objectMapByte(object.dosX, object.dosY) << 1) & 0xff) + 1) & 0xff;   // 00023771-00023793
      if (object.altitude <= ground) {                           // 00023795/0002379B jbe 00024997
        this.convertObjectToExplosion(object);
        return;
      }
      this.objectShellProximity(object);                         // 000237A1 jmp 0002357B
    }

    // DOS: FUN_000234E0 [0002357B-000236C1]; record: analysis/functions/browser-attract.md#object-pass
    // The proximity tail both shells share. 0002357B-000235C5: is the shell
    // inside the player's box (altitude spread <= 0xF, |dx| and |dy| <= 0x1400000
    // against the frame-start viewer [00019DF6]/[00019CDC]/[00019CE0]); if so
    // 000235CB-0002365B deals the hit, otherwise 00023660 tests the helicopter.
    objectShellProximity(object) {
      const flight = this.flight;
      if (this.altitudeSpread(object.altitude, flight.previousAltitude) <= 0x0f
          && this.positionSpread(object.dosX, flight.frameDosX) <= 0x1400000
          && this.positionSpread(object.dosY, flight.frameDosY) <= 0x1400000) {
        this.objectShellHitsPlayer(object);
        return;
      }
      this.objectShellHitsHelicopter(object);                    // 00023660
    }

    // DOS: FUN_000234E0 [000235CB-0002365B]; record: analysis/functions/browser-attract.md#object-pass
    // 000235CB-000235E4: while a flare is in the air and the wall-clock gate
    // [00019DB8] & 0xC is open the shell loses its target and passes on to the
    // helicopter test. Otherwise (and with the mission still running, [00019E49]
    // = 0) the hit: BULL threat flag, shake countdown, the two damage cells the
    // PRNG picks, the hull, and the shell bursts through 00024997.
    objectShellHitsPlayer(object) {
      const hull = this.hull;
      if ((this.shake.rng & 0x0c) !== 0 && this.effectAActive !== 0) {   // 000235CB-000235D4
        object.targetSlot = 0;                                   // 000235DD [00021D31]
        this.objectShellHitsHelicopter(object);                  // 000235E4 jmp 00023660
        return;
      }
      if (hull.down !== 0) {                                     // 000235E6-000235ED
        this.objectShellHitsHelicopter(object);
        return;
      }
      this.threatBull = 1;                                       // 000235EF
      this.shake.countdown = 10;                                 // 000235F6 [00019DC0]
      // 00023600-0002360C: sound 5 (00004E8E).
      this.shake.rng = ((this.shake.rng + this.view_camera_dos_x) >>> 0);   // 00023612-00023617 add [19DB8], [19CD4] (the view camera's)
      const byte = this.shake.rng & 0xff;                        // 0002361D
      hull.cells[byte & 7] = (hull.cells[byte & 7] - 1) & 0xff;  // 00023626-00023628
      hull.cells[byte >>> 5] = (hull.cells[byte >>> 5] - 1) & 0xff;      // 0002362E-00023631
      this.shake.rng = (((this.shake.rng >>> 8) | (this.shake.rng << 24)) >>> 0);   // 00023637 ror 8
      hull.points = i32(hull.points - (((this.shake.rng & 3) + 2)));     // 0002363E-00023648
      if (hull.points < 0) hull.down = 1;                        // 0002364E-00023654
      this.convertObjectToExplosion(object);                     // 0002365B / 0002364E jns
    }

    // DOS: FUN_000234E0 [00023660-000236C1]; record: analysis/functions/browser-attract.md#object-pass
    // Is the shell inside the box of the type-4 helicopter [00022368]? Inside:
    // its health loses 6 (a borrow sets bit 0 of its destruction byte) and the
    // shell bursts. DOS reads slot [00022368] even when it is 0; slot 0's cells
    // are other arrays' cells (altitude[0] is sprite[130], x[0] is depth[130],
    // y[0] is x[130]) and are read here exactly so.
    objectShellHitsHelicopter(object) {
      const slot = this.heliSlot;
      const heli = slot ? this.objectBySlot.get(slot) : null;
      const reference = heli
        ? { altitude: heli.altitude, dosX: heli.dosX, dosY: heli.dosY }
        : this.slotZeroCells();
      if (this.altitudeSpread(object.altitude, reference.altitude) > 0x0f) return;       // 00023666-0002367A
      if (this.positionSpread(object.dosX, reference.dosX) > 0x1400000) return;          // 0002367C-00023692
      if (this.positionSpread(object.dosY, reference.dosY) > 0x1400000) return;          // 00023694-000236AA
      if (heli) {
        const remaining = heli.health - 6;                       // 000236AC
        heli.health = remaining & 0xff;
        if (remaining < 0) heli.phase |= 1;                      // 000236B3-000236B5
      } else {
        // The write lands in slot 0's health[0] / phase[0] cells (f9[30] and
        // prev_alt[130]); neither is modelled. Counted so a run can say so.
        this.slotZeroWrites += 1;
      }
      this.convertObjectToExplosion(object);                     // 000236BC
    }

    // DOS: FUN_000234E0 [00023660-000236AA]; record: analysis/functions/browser-attract.md#object-pass
    // Slot 0 is no object, but arrays run on: altitude[0] = [00021A25] is the
    // sprite byte of slot 130, x[0] = [00020C6C] is depth[130] (24B70 stores the
    // slot's DOS-unit depth there) and y[0] = [00020E74] is x[130].
    slotZeroCells() {
      const last = this.objectBySlot.get(130);
      return {
        altitude: last ? last.sprite : 1,
        dosX: last ? last.depthDos : 0,
        dosY: last ? last.dosX : 0,
      };
    }

    // DOS: FUN_000237B0 [000237B0-000237FD]; record: analysis/functions/browser-attract.md#object-pass
    // BOOM wreckage: the sprite byte is the frame; at 0x14 the slot is freed.
    // A mission object (slot <= 0x1E, '*' record) that ends here counts down
    // [0002824B]; the last one raises the mission-complete flag [00019E49].
    objectStateExplosion(object) {
      object.sprite = (object.sprite + 1) & 0xff;                // 000237B0
      if (object.sprite < 0x14) return;                          // 000237B6/000237BD
      object.active = false;                                     // 000237BF
      if (object.slot > 0x1e) return;                            // 000237C6/000237C9
      if (!object.flag) return;                                  // 000237CC-000237D3
      if (this.missionTargets === 0) return;                     // 000237D5-000237DC
      this.missionTargets -= 1;                                  // 000237DE
      if (this.missionTargets !== 0) return;                     // 000237E4
      if (this.hull.down !== 0) return;                          // 000237E6-000237ED
      this.hull.down = 1;                                        // 000237EF (sound 7 follows)
    }

    // DOS: FUN_00023800 [00023800-0002383E]; record: analysis/functions/browser-attract.md#object-pass
    // The fixed slot 31: it follows the frame-start viewer snapshot.
    objectStateViewer(object) {
      object.variant = (object.variant - 0x10) & 0xff;           // 00023800
      object.dosX = this.flight.frameDosX;                       // 00023807 [00019CDC]
      object.dosY = this.flight.frameDosY;                       // 00023813 [00019CE0]
      object.altitude = Math.min(0xff, (this.flight.previousAltitude & 0xff) + 1);   // 0002381F-0002382A [00019DF6]
      object.heading = (this.flight.angle >>> 24) & 0xff;        // 00023830 [00019D04]
    }

    // DOS: FUN_00023F60 [0002414C-000241B9]; record: analysis/functions/browser-attract.md#object-pass
    // The wreck-and-fall tail the default ground state (00024162-000241B9) and
    // the type-4 helicopter (00023A2F-00023A86) each carry as their own copy of
    // the same instructions: the wreck turns (+0x10) and sinks (-4) every tick;
    // under the ground byte it bursts through 00024997, and on the way down
    // (once, while the destruction byte is <= 2 and within 0xF of the ground)
    // it spawns its BOOM child.
    objectWreckFall(object) {
      object.heading = (object.heading + 0x10) & 0xff;
      const sunk = object.altitude - 4;                          // 00024169/00023A36
      object.altitude = sunk & 0xff;
      if (sunk < 0) {                                            // jb 00024997 / 00023A86
        this.convertObjectToExplosion(object);
        return;
      }
      // 00024172-00024192: the ground byte is `shl al, 1` alone, no clearance.
      const ground = (this.objectMapByte(object.dosX, object.dosY) << 1) & 0xff;
      if (ground >= object.altitude) {                           // 00024194-0002419C jae 00024997
        this.convertObjectToExplosion(object);
        return;
      }
      if (object.phase > 2) return;                              // 0002419E-000241A5
      if (((ground + 0x0f) & 0xff) < object.altitude) return;   // 000241A7-000241AB
      object.phase = (object.phase + 1) & 0xff;                  // 000241AE
      this.spawnWreckage(object);                                // 000241B4 jmp 000227BF
    }

    // DOS: FUN_00023A8C [00023A8C-00023AC7]; record: analysis/functions/browser-attract.md#object-pass
    // Idle objects (type 3, the oil tanks): nothing until destroyed, then
    // one wreck child and five more ticks before the slot bursts.
    objectStateIdle(object) {
      if (object.phase === 0) return;                            // 00023A8C-00023A95
      if (object.phase <= 1) {                                   // 00023A96-00023A9D
        object.phase = (object.phase + 1) & 0xff;                // 00023A9F
        this.spawnWreckage(object);                              // 00023AA6 (sound 1 follows)
        return;
      }
      object.phase = (object.phase + 1) & 0xff;                  // 00023AB4
      if (object.phase === 5) this.convertObjectToExplosion(object);   // 00023ABA-00023AC1
    }

    // DOS: FUN_00023CF0 [00023F24-00023F55]; record: analysis/functions/browser-attract.md#object-pass
    // The mobile unit's destruction tail: the first tick spawns the wreck child,
    // the 0x0F-th converts the slot itself.
    objectMobileDamage(object) {
      if (object.phase <= 1) {                                   // 00023F24-00023F2B
        object.phase = (object.phase + 1) & 0xff;                // 00023F2D
        this.spawnWreckage(object);                              // 00023F34 (sound 1 follows)
        return;
      }
      object.phase = (object.phase + 1) & 0xff;                  // 00023F42
      if (object.phase === 0x0f) this.convertObjectToExplosion(object);   // 00023F48-00023F4F
    }

    // DOS: FUN_00023AD0 [00023AD0-00023B4B]; record: analysis/functions/browser-attract.md#object-pass
    // The steering probe: from the previous position, one step along the
    // CURRENT heading; equal to the ground byte (+0x0B) means that way is level.
    objectTerrainProbe(object) {
      object.dosX = object.homeDosX;                             // 00023AD0
      object.dosY = object.homeDosY;                             // 00023ADE
      this.objectMove(object);                                   // 00023AEC-00023B16
      return object.altitude === this.objectGroundByte(object, 0x0b);   // 00023B1D-00023B45
    }

    // DOS: FUN_00023CF0 [00023CF0-00023F55]; record: analysis/functions/browser-attract.md#object-pass
    // The mobile ground unit (type 2 and 5 records). Order of the listing:
    // destruction tail, timer, snapshot, then - health above 6 only - hold or
    // move and steer, and ALWAYS the aim at 00023E55 (health <= 6, a hold in
    // progress and a finished steer all fall into it).
    objectStateMobile(object) {
      if (object.phase !== 0) {                                  // 00023CF0-00023CF7
        this.objectMobileDamage(object);
        return;
      }
      object.timer = (object.timer + 1) & 0xff;                  // 00023CFD
      this.objectSnapshot(object);                               // 00023D03-00023D25
      if (object.health > 6) {                                   // 00023D2B/00023D32 jbe 00023E55
        if (object.hold !== 0) {                                 // 00023D38/00023D40
          object.hold = (object.hold - 1) | 0;                   // 00023E4E
        } else {
          this.objectMobileSteer(object);                        // 00023D46-00023E4C
        }
      }
      this.objectMobileAim(object);                              // 00023E55-00023F23
    }

    // DOS: FUN_00023CF0 [00023D46-00023E4C]; record: analysis/functions/browser-attract.md#object-pass
    // Move one step; if the ground byte (+0x0B) is not the altitude, turn
    // toward the side whose probe is level (the latched steer byte decides
    // first, 0 = undecided probes +0x20, -0x20, +0x40 of the heading),
    // turn by (speed >> 21) + 1 and go back to the snapshot position.
    objectMobileSteer(object, bias = 1) {
      this.objectMove(object);                                   // 00023D46-00023D70
      if (object.altitude === this.objectGroundByte(object, 0x0b)) {   // 00023D77-00023DA5
        object.steerDir = 0;                                     // 00023E45
        return;
      }
      const saved = object.heading;                              // 00023DAB push eax
      let right;
      if (object.steerDir < 0) {                                 // 00023DB2/00023DB9 js 00023DE7
        right = false;
      } else if (object.steerDir > 0) {                          // 00023DBB jne 00023E08
        right = true;
      } else {
        object.heading = (saved + 0x20) & 0xff;                  // 00023DBD
        if (this.objectTerrainProbe(object)) {                   // 00023DC4/00023DC9 je 00023E08
          right = true;
        } else {
          object.heading = (object.heading - 0x40) & 0xff;       // 00023DCB
          if (this.objectTerrainProbe(object)) {                 // 00023DD2/00023DD7 je 00023DE7
            right = false;
          } else {
            object.heading = (object.heading + 0x60) & 0xff;     // 00023DD9
            right = this.objectTerrainProbe(object);             // 00023DE0/00023DE5 je 00023E08, else 00023DE7
          }
        }
      }
      const turn = ((object.speed >>> 21) + bias) & 0xff;        // 00023DEE-00023DF8 / 00023E0F-00023E19 (bias 1; 0 at 00023C4E-00023C58)
      if (right) {
        object.heading = (saved + turn) & 0xff;                  // 00023E1A
        object.steerDir = 1;                                     // 00023E20
      } else {
        object.heading = (saved - turn) & 0xff;                  // 00023DF9
        object.steerDir = -1;                                    // 00023DFF
      }
      object.dosX = object.homeDosX;                             // 00023E27-00023E3C
      object.dosY = object.homeDosY;
    }

    // DOS: FUN_00023B50 [00023B50-00023CB2]; record: analysis/functions/browser-attract.md#object-pass
    // Type 9: the mobile unit without the aim, retreating at health <= 2 instead
    // of 6, and turning by (speed >> 21) with no +1 (00023C4E-00023C58,
    // 00023C6E-00023C78). Its destruction tail 00023CB3-00023CE4 is the mobile
    // unit's. No captured pass places a type-9 record, so this is ported from
    // the listing only.
    objectStateType9(object) {
      if (object.phase !== 0) {                                  // 00023B50-00023B57
        this.objectMobileDamage(object);
        return;
      }
      object.timer = (object.timer + 1) & 0xff;                  // 00023B5D
      this.objectSnapshot(object);                               // 00023B63-00023B85
      if (object.health <= 2) return;                            // 00023B8B-00023B92 jbe 00023CAA
      if (object.hold !== 0) {                                   // 00023B98-00023BA0
        object.hold = (object.hold - 1) | 0;                     // 00023CAB
        return;
      }
      this.objectMobileSteer(object, 0);                         // 00023BA6-00023CA1
    }

    // DOS: FUN_00023CF0 [00023E55-00023F23]; record: analysis/functions/browser-attract.md#object-pass
    // The aim. Bearing and distance estimate to the frame-start viewer through
    // 000256C8; out of range ((altitude << 20) + 0x1E000000, +0x87 for a
    // targetable slot) nothing happens; with the PRNG gate [00019DB8] & 0xC
    // open and chaff in the air nothing happens; otherwise the threat flag
    // [00019D92] is raised and either the turret is within 0x10 of the bearing
    // and the shot timer mask lets it fire, or the turret walks by 3 toward it.
    objectMobileAim(object) {
      const flight = this.flight;
      const aim = this.objectBearingTo(object, flight.frameDosX, flight.frameDosY);   // 00023E55-00023E69
      // [00019DFC] during 000234A4 is the VIEW hook's altitude: 0000D3EA pushes
      // the player's, 0000D3F0 calls [00019C94] (the camera handlers of
      // 00007BF0-00007D24 store the camera's altitude and position into
      // [00019DFC]/[00019CD4]/[00019CD8]), 0000D3FD pops it after the pass.
      let range = (this.view_camera_altitude & 0xff) * 0x100000; // 00023E6E-00023E75
      if (object.targetFlag !== 0) range += 0x87;                // 00023E78-00023E81
      range += 0x1e000000;                                       // 00023E87
      if ((aim.distance >>> 0) >= range) return;                 // 00023E8D jae 00023F23
      if ((this.shake.rng & 0x0c) !== 0 && this.effectBActive !== 0) return;   // 00023E95-00023EA5
      this.threatChaff = 1;                                      // 00023EA7
      const turret = object.variant & 0xff;
      const al = ((aim.bearing - object.heading) - turret) & 0xff;   // 00023EAE-00023EBA
      const negative = (al & 0x80) !== 0;                        // 00023EBC sets bl
      const exact = al === 0;                                    // 00023EBF sete bh
      const spread = al ^ (negative ? 0xff : 0);                 // 00023EC2-00023EC4 cbw; xor
      if (spread >= 0x10) {                                      // 00023EC6/00023EC8 jae 00023F0B
        if (exact) return;                                       // 00023F0B-00023F0D
        object.variant = (object.variant + (negative ? -3 : 3)) & 0xff;   // 00023F0F-00023F1C
        return;
      }
      if ((object.timer & object.f9) !== 0) return;              // 00023ECA-00023ED6
      object.heading = (object.heading + turret) & 0xff;         // 00023ED9-00023EDF
      object.altitude = (object.altitude + 6) & 0xff;            // 00023EE5
      this.objectFire(object);                                   // 00023EEC-00023EF3
      object.heading = (object.heading - (object.variant & 0xff)) & 0xff;   // 00023EF6-00023EFC
      object.altitude = (object.altitude - 6) & 0xff;            // 00023F02
    }

    // DOS: FUN_00023F60 [00023F60-0002414C]; record: analysis/functions/browser-attract.md#object-pass
    // The ordinary mover (types 1, 6, 7 and 8). It moves BEFORE it looks at
    // the destruction byte, follows the ground at +0x2C, and its aim section
    // 00024076-00024148 jitters the heading or turns it toward the player.
    objectStateDefault(object) {
      object.variant = (object.variant - 0x10) & 0xff;           // 00023F60
      this.objectSnapshot(object);                               // 00023F67-00023F89
      object.timer = (object.timer + 1) & 0xff;                  // 00023F8F
      this.objectMove(object);                                   // 00023F95-00023FBF
      if (object.phase !== 0) {                                  // 00023FC6/00023FCD jne 0002414C
        this.objectDefaultDamage(object);
        return;
      }
      if (object.hold !== 0) {                                   // 00023FD3-00023FDB
        object.hold = (object.hold - 1) | 0;                     // 00023FDD
        object.dosX = object.homeDosX;                           // 00023FE4-00023FF9
        object.dosY = object.homeDosY;
        return;
      }
      // 00024001-00024029: ground + 0x2C, saturated; al = ground - altitude.
      const ground = this.objectGroundByte(object, 0x2c);
      const difference = ground - object.altitude;
      if (difference > 0) {                                      // 00024031 jb not taken
        if (difference > 0x14) {                                 // 00024033-00024035
          object.dosX = object.homeDosX;                         // 00024037-0002404C
          object.dosY = object.homeDosY;
        }
        if (difference > 4) {                                    // 00024053-00024055
          object.altitude = Math.min(0xff, object.altitude + 8); // 00024057-00024060
        }
      } else if (difference < 0 && -difference > 4) {            // 00024069-0002406D
        object.altitude = (object.altitude - 8) & 0xff;          // 0002406F
      }
      this.objectDefaultAim(object);                             // 00024076-0002414B
    }

    // DOS: FUN_00023F60 [00024076-0002414B]; record: analysis/functions/browser-attract.md#object-pass
    // Bearing and distance to the frame-start viewer, then by distance: inside
    // the fire radius ((([0002A37F] ^ 1) << 6) + 0x96) << 22 and within 0xC of
    // the bearing it fires on the [00021F75] timer mask and holds station
    // above the player's altitude; closer than 0x7800000 it jitters
    // the heading by 4 + (rng & 7); at long range or a far-off bearing it jitters by
    // (rng & 3) - 2; otherwise it turns toward the bearing by 0xC.
    objectDefaultAim(object) {
      const flight = this.flight;
      const aim = this.objectBearingTo(object, flight.frameDosX, flight.frameDosY);   // 00024076-0002408A
      const night = Number(this.evidence.mission.kind.values[0]) & 0xff;   // 0002408F [0002A37F]
      const radius = ((((night ^ 1) << 6) + 0x96) << 22) >>> 0;  // 00024096-000240A2
      const distance = aim.distance >>> 0;
      if (distance >= radius) {                                  // 000240A5/000240A7 jae 00024100
        this.objectJitter(object, 3, -2);
        return;
      }
      const al = (aim.bearing - object.heading) & 0xff;          // 000240A9
      const negative = (al & 0x80) !== 0;                        // 000240AF sets bl
      const exact = al === 0;                                    // 000240B2 sete bh
      const spread = al ^ (negative ? 0xff : 0);                 // 000240B5-000240B7
      if (spread >= 0x0c) {                                      // 000240B9/000240BB jae 00024120
        if (distance <= 0x7800000) {                             // 00024120/00024126 jbe 00024110
          object.heading = (object.heading + (this.shake.rng & 7) + 4) & 0xff;   // 00024110-0002411F
          return;
        }
        if (distance >= 0x19000000 || spread >= 0x46) {          // 00024128-00024132 -> 00024100
          this.objectJitter(object, 3, -2);
          return;
        }
        if (exact) return;                                       // 00024134-00024136
        object.heading = (object.heading + (negative ? -0x0c : 0x0c)) & 0xff;   // 00024138-0002414B
        return;
      }
      if ((object.timer & object.f9) === 0) this.objectFire(object);     // 000240BD-000240D2
      // 000240D4-000240F8: hover at the player's altitude + 0xB, climbing 0x10
      // at a time and never above 0xFE.
      const hover = Math.min(0xff, (flight.previousAltitude & 0xff) + 0x0b);   // 000240D4-000240DD
      if (object.altitude > hover) return;                       // 000240DF/000240E5 ja
      if (object.altitude > 0xef) {                              // 000240E7/000240EE
        object.altitude = 0xfe;                                  // 000240F8
        return;
      }
      object.altitude = (object.altitude + 0x10) & 0xff;         // 000240F0
    }

    // DOS: FUN_00023F60 [00024100-0002410F]; record: analysis/functions/browser-attract.md#object-pass
    // `mov al, [00019DB8]; and al, mask; sub al, 2; add [heading], al`.
    objectJitter(object, mask, bias) {
      object.heading = (object.heading + ((this.shake.rng & mask) + bias)) & 0xff;
    }

    // DOS: FUN_00023F60 [0002414C-000241B9]; record: analysis/functions/browser-attract.md#object-pass
    // The default state's destruction tail: tick 1 only advances the byte (sound);
    // the wreck child comes from the fall at 000241AE.
    objectDefaultDamage(object) {
      if (object.phase === 1) {                                  // 0002414C-00024153
        object.phase = 2;                                        // 00024155 (sound 1 follows)
      }
      this.objectWreckFall(object);                              // 00024162-000241B9
    }

    // DOS: FUN_00023840 [00023840-00023A86]; record: analysis/functions/browser-attract.md#object-pass
    // Type 4, the helicopter. It aims at a point 0x11800000 to the side of the
    // player (or at the selected target in weapon mode 5), turns by 8 toward it,
    // closes while farther than 0x19000000, and follows the ground at +0x22.
    objectStateType4(object) {
      object.variant = (object.variant - 0x10) & 0xff;           // 00023840
      this.objectSnapshot(object);                               // 00023847-00023869
      if (object.phase !== 0) {                                  // 0002386F/00023876 jne 00023A08
        this.objectType4Damage(object);
        return;
      }
      const flight = this.flight;
      let targetX = flight.frameDosX;                            // 0002387C [2234C]
      let targetY = flight.frameDosY;                            // 00023886 [22350]
      const selected = this.targetSlot === 31 ? 0 : this.targetSlot;   // [00019D10]; Unproven (see below)
      if (flight.weaponMode === 5 && selected !== 0) {           // 00023890-000238A2
        const chosen = this.objectBySlot.get(selected);
        if (chosen) {
          targetX = chosen.dosX;                                 // 000238A4
          targetY = chosen.dosY;                                 // 000238B0
        }
        const raised = object.altitude + 9;                      // 000238BC
        object.altitude = raised > 0xff ? 0xff : raised;         // 000238C3-000238C5
      }
      // 000238CC-000238E8: the offset is -0x11800000 times the published
      // (cosine, sine) pair [00019CBC]/[00019CB8] - x takes the cosine.
      targetX = i32(targetX + hi32(0xee800000, flight.pubCos));
      targetY = i32(targetY + hi32(0xee800000, flight.pubSin));
      const aim = this.objectBearingTo(object, targetX, targetY);   // 000238EE
      const al = (aim.bearing - object.heading) & 0xff;          // 000238F3-000238F9
      if (al !== 0 && al < 0x80) {                               // 000238FB je / js
        if (al > 4) {                                            // 000238FF/00023901 jbe 00023927
          object.heading = (object.heading + 8) & 0xff;          // 00023903
          object.timer = 0x0f;                                   // 0002390A
        } else {
          this.objectType4Settle(object);
        }
      } else if (al >= 0x80) {
        if (al >= 0xfc) {                                        // 00023913/00023915 jge 00023927 (signed >= -4)
          this.objectType4Settle(object);
        } else {
          object.heading = (object.heading - 8) & 0xff;          // 00023917
          object.timer = 0x0f;                                   // 0002391E
        }
      } else {
        this.objectType4Settle(object);                          // 000238FB je 00023927
      }
      if ((aim.distance >>> 0) > 0x19000000) this.objectMove(object);   // 0002395B-0002398D
      // 00023994-00023A07: ground + 0x22 (saturated); al = ground - altitude.
      const ground = this.objectGroundByte(object, 0x22);
      const difference = ground - object.altitude;
      if (difference > 0) {                                      // 000239C4 jb not taken
        if (difference > 0x0f) {                                 // 000239C6/000239C8 jbe 000239E6
          object.dosX = object.homeDosX;                         // 000239CA-000239DF
          object.dosY = object.homeDosY;
        }
        if (difference > 4) {                                    // 000239E6/000239E8
          object.altitude = Math.min(0xff, object.altitude + 8); // 000239EA-000239F3
        }
      } else if (difference < 0 && -difference > 4) {           // 000239FC-00023A00
        object.altitude = (object.altitude - 8) & 0xff;          // 00023A00
      }
    }

    // DOS: FUN_00023840 [00023927-0002395A]; record: analysis/functions/browser-attract.md#object-pass
    // On course: count the timer down; at zero the speech cue is chosen from
    // [00019D10] (sound only, nothing is stored).
    objectType4Settle(object) {
      object.timer = (object.timer - 1) & 0xff;                  // 00023927
    }

    // DOS: FUN_00023840 [00023A08-00023A86]; record: analysis/functions/browser-attract.md#object-pass
    // The helicopter's destruction: tick 1 sets [00022384] and silences the
    // weapon-5 count [00019D40] (neither is modelled: no ammunition in the JS),
    // then it turns, sinks and spawns its wreck at the ground.
    objectType4Damage(object) {
      if (object.phase === 1) {                                  // 00023A08-00023A0F
        object.phase = 2;                                        // 00023A11
        this.type4Down = 1;                                      // 00023A17 [00022384]
      }
      this.objectWreckFall(object);                              // 00023A2F-00023A86
    }

    // DOS: FUN_00024480 [00024480-0002449E]; record: analysis/functions/browser-attract.md#object-pass.
    // BULL cloud: altitude and timer count down; at zero either ends it and
    // [00019D90] is decremented unconditionally.
    objectStateEffectA(object) {
      object.altitude = (object.altitude - 1) & 0xff;            // 00024480
      if (object.altitude !== 0) {                               // 00024486 je 00024491
        object.timer = (object.timer - 1) & 0xff;                // 00024488
        if (object.timer !== 0) return;                          // 0002448E je 00024491
      }
      this.effectAActive = (this.effectAActive - 1) & 0xff;      // 00024491
      object.active = false;                                     // 00024497
    }

    // DOS: FUN_000244A0 [000244A0-000244D5]; record: analysis/functions/browser-attract.md#object-pass.
    // CHAF cloud: the same countdown plus the sprite byte cycling 1..8; the
    // end decrements [00019D8F] unconditionally.
    objectStateEffectB(object) {
      object.altitude = (object.altitude - 1) & 0xff;            // 000244A0
      let ended = object.altitude === 0;                         // 000244A6 je 000244C8
      if (!ended) {
        object.timer = (object.timer - 1) & 0xff;                // 000244A8
        ended = object.timer === 0;                              // 000244AE je 000244C8
      }
      if (!ended) {
        object.sprite = (object.sprite + 1) & 0xff;              // 000244B0
        if (object.sprite > 8) object.sprite = 1;                // 000244B6-000244C7
        return;
      }
      this.effectBActive = (this.effectBActive - 1) & 0xff;      // 000244C8
      object.active = false;                                     // 000244CE
    }

    // DOS: FUN_000241C0 [000241C0-0002430D]; record: analysis/functions/browser-attract.md#weapon-fire.
    // Unproven: NOT a port of 000241C0 (no 8.24 gravity, invented altitude
    // steps); see src/object.s object_state_rocket. This state is the
    // timed ROCK projectile path and shares the DOS ground/collision gate.
    objectStateTimedProjectile(object) {
      this.objectSnapshot(object);
      object.phase = (object.phase + 1) & 0xff;
      object.timer = (object.timer + 1) & 0xff;
      this.objectMove(object);
      if (this.dynamicCollision(object, 6)) return;
      const target = this.objectGroundTarget(object, 1);
      const difference = ((target - object.altitude + 128) & 0xff) - 128;
      if (difference > 4) object.altitude = Math.min(0xff, object.altitude + Math.min(8, difference));
      else if (difference < -4) object.altitude = Math.max(0, object.altitude - Math.min(8, -difference));
      if (object.timer >= 0x78) this.convertObjectToExplosion(object);
    }

    // DOS: FUN_00024680/00024860 [00024680-00024996]; record: analysis/functions/browser-attract.md#weapon-fire.
    // Unproven: NOT a port of 00024680 (no timer exit, invented climb/dive);
    // see src/object.s object_state_hellfire. Guided states use
    // the recovered table-driven bearing routine and terrain clearance rather
    // than a browser straight-line projectile.
    objectStateGuided(object) {
      this.objectSnapshot(object);
      object.phase = (object.phase + 1) & 0xff;
      const target = object.targetSlot === 31
        ? { dosX: this.flight.frameDosX, dosY: this.flight.frameDosY, altitude: this.flight.altitude }
        : this.objects.find((candidate) => candidate.slot === object.targetSlot && candidate.active);
      if (target) {
        const aim = this.objectBearingTo(object, target.dosX, target.dosY);
        let delta = (aim.bearing - object.heading) & 0xff;
        if (delta > 0x80) delta -= 0x100;
        const limit = object.stateAddr === 0x24860 ? 0x19 : 0x14;
        object.heading = (object.heading + clamp(delta, -limit, limit)) & 0xff;
        const altitudeDelta = target.altitude - object.altitude;
        if (altitudeDelta > 3) object.altitude = Math.min(0xff, object.altitude + 3);
        else if (altitudeDelta < -3) object.altitude = Math.max(0, object.altitude - 3);
      }
      this.objectMove(object);
      if (object.phase > 5 && this.dynamicCollision(object, 0x50)) return;
      const ground = this.objectGroundTarget(object, 0x14);
      const difference = ((ground - object.altitude + 128) & 0xff) - 128;
      if (difference > 0x14) {
        object.dosX = object.homeDosX;
        object.dosY = object.homeDosY;
      } else if (difference > 4) {
        object.altitude = Math.min(0xff, object.altitude + 8);
      } else if (difference < -4) {
        object.altitude = Math.max(0, object.altitude - 8);
      }
      if (object.phase >= 0x78) this.convertObjectToExplosion(object);
    }

    // DOS: FUN_00023D46/00023F9C [00023D46-00023FBF]; record: analysis/functions/browser-attract.md#weapon-fire.
    // Unproven (the player's weapons, see above): the 0x01400000 box test of
    // 00024A33-00024B0F kept as the browser had it, now in 10.22 units and
    // without the object-pass flag hack the previous version raised.
    dynamicCollision(object, damage) {
      const radius = 0x01400000;
      for (const target of this.objects) {
        if (!target.active || target.dynamic || target === object || target.slot < 1 || target.slot > 30) continue;
        const dx = Math.abs(i32(target.dosX - object.dosX));
        const dy = Math.abs(i32(target.dosY - object.dosY));
        const altitude = ((target.altitude - object.altitude + 128) & 0xff) - 128;
        if (dx <= radius && dy <= radius && Math.abs(altitude) <= 0x0f) {
          const remaining = (target.health || 0) - damage;
          target.health = Math.max(0, remaining);
          if (remaining < 0) target.phase |= 1;
          this.convertObjectToExplosion(object);
          return true;
        }
      }
      return false;
    }

    // DOS: FUN_000256C8 [000256C8-00025726]; record: analysis/functions/browser-attract.md#object-pass
    // The single routine DOS has here: 00007CF2's fixed camera and the five
    // object states at 000238EE/00023E69/0002408A/000246DB/000248B7 all call
    // it. Keep the DOS octant/correction arithmetic instead of substituting
    // Math.atan2, whose tie and quantization rules do not match the image.
    //
    // Transcribed instruction by instruction from the listing. The previous
    // reading of this routine agreed with 0 of the 153 captured DOS variant-7
    // frames; this one reproduces 153/153. Its errors are named at the
    // instruction each one dropped, below. Positions are 10.22 (dosX/dosY):
    // the origin is the object, the target the stored [0002234C]/[00022350].
    objectBearingTo(origin, targetX, targetY) {
      const dy = i32(origin.dosY - targetY);             // 000256CA/000256D1
      const dx = i32(origin.dosX - targetX);             // 000256DF/000256E6
      // 000256D7 `sets bl` takes the Y sign; 000256F1 `shld ebx, edx, 1`
      // shifts the X sign in beside it, and 000256F5 `shl bl, 1` doubles the
      // pair. The index therefore steps in twos, not ones.
      let index = (((dy < 0 ? 1 : 0) << 1) | (dx < 0 ? 1 : 0)) << 1;
      // 000256DA/DB and 000256EC/ED. `cdq`/`xor` is a ONE'S-complement
      // magnitude - |v| - 1 for negatives - not an absolute value.
      let edi = dy < 0 ? i32(~dy) : dy;             // 000256DD
      let ebp = dx < 0 ? i32(~dx) : dx;             // 000256EF
      // 000256F7/F9 `cmp ebp, edi` / `ja`: the increment and the exchange run
      // when |dx| is NOT above |dy|, which is the opposite of the condition
      // this port previously used. Either way ebp ends up the major.
      if (!((ebp >>> 0) > (edi >>> 0))) {
        index += 1;                                 // 000256FB
        const swap = edi; edi = ebp; ebp = swap;    // 000256FD
      }
      // 000256FF-00025703: `(minor >> 1) + major`, in that order.
      const distance = i32((edi >>> 1) + ebp);
      let bearing = OBJECT_OCTANT_TABLE[index] >>> 0;   // 00025705
      const divisor = ebp >>> 10;                       // 0002570C
      if (divisor) {                                    // 0002570F
        // 00025715 `div ebp` is unclamped: the quotient indexes the whole
        // 2048-byte table. 00025717 `xor bl` touches the low byte only, and
        // the bits above it still matter to the shift that follows.
        const ratio = ((edi >>> 0) / divisor) | 0;
        bearing = ((bearing & ~0xff)
          | ((bearing ^ OBJECT_BEARING_CORRECTION[ratio]) & 0xff)) >>> 0;
      }
      // 0002571D/0002571E run on the whole word; 00025722/00025724 then take
      // bl and complement it.
      bearing = ((bearing + 1) >>> 1) >>> 0;
      return { bearing: (~bearing) & 0xff, distance };
    }

    // DOS: FUN_000234A4 [000234A4-000234D3]; record: analysis/functions/browser-attract.md#object-pass
    // The state dispatch: `call [ecx*4 + 00020244]` for every active slot.
    updateObjectState(object) {
      if (!object.active) return;
      if (object.stateAddr === 0x234e0) this.objectStateShell(object);
      else if (object.stateAddr === 0x236d0) this.objectStateShellLob(object);
      else if (object.stateAddr === 0x237b0) this.objectStateExplosion(object);
      else if (object.stateAddr === 0x23800) this.objectStateViewer(object);
      else if (object.stateAddr === 0x23840) this.objectStateType4(object);
      else if (object.stateAddr === 0x23cf0) this.objectStateMobile(object);
      else if (object.stateAddr === 0x23a8c) this.objectStateIdle(object);
      else if (object.stateAddr === 0x23b50) this.objectStateType9(object);
      else if (object.stateAddr === 0x23f60) this.objectStateDefault(object);
      else if (object.stateAddr === 0x241c0) this.objectStateTimedProjectile(object);
      else if (object.stateAddr === 0x24480) this.objectStateEffectA(object);
      else if (object.stateAddr === 0x244a0) this.objectStateEffectB(object);
      else if (object.stateAddr === 0x244e0) this.objectStateBullet(object);
      else if (object.stateAddr === 0x24680 || object.stateAddr === 0x24860) this.objectStateGuided(object);
      this.syncObjectRender(object);
    }

    // DOS: FUN_0000D3C0 [0000D3C0-0000D8F5]; record: analysis/functions/browser-attract.md#frame-driver
    advanceAuthoritativeTick() {
      // DOS: FUN_0000D3C0; record: analysis/functions/browser-attract.md#frame-driver
      // The browser keeps the
      // recovered draw-then-tick sequence; publication is outside this seam.
      let renderedState;
      let input = null;
      if (this.mode === "demo") {
        this.prepareFlightFrame();
        // DOS 0000D3C0 draws terrain and the active object pass against the
        // frame-start viewer snapshot. 00018D20 then consumes one replay
        // record and integrates flight state before 0000D703 composes HUD.
        this.drawTerrainStage();
        renderedState = this.stateSnapshot();
        input = this.advanceDemoInput();
        if (this.mode === "demo") this.drawCockpitStage();
      } else {
        this.drawScreen();
        renderedState = this.stateSnapshot();
        this.advanceScreen();
      }
      this.logicalTick += 1;
      this.recordTrace(input, renderedState, this.stateSnapshot());
    }

    // Target artefact; record: analysis/functions/browser-attract.md#fixture-scheduler
    advanceTicks(count) {
      // Target artefact: exact fixture seam for deterministic regression runs.
      this.scheduler.advanceTicks(count);
    }

    // N/A - platform replacement; record: analysis/functions/browser-attract.md#fixture-scheduler
    presentAndEmit() {
      // Target artefact: Canvas presentation and UI publication.
      this.present();
      this.emitFrame();
    }

    // DOS: FUN_0000D3C0 [0000D3C0-0000D8F5]; record: analysis/functions/browser-attract.md#frame-driver
    prepareFlightFrame() {
      this.flight.previousAltitude = this.flight.altitude;
      this.flight.frameX = this.flight.x;
      this.flight.frameY = this.flight.y;
      this.flight.frameDosX = this.flight.dosX;
      this.flight.frameDosY = this.flight.dosY;
    }

    // DOS: FUN_000195B1/00019674 [000195B1-00019674]; record: analysis/functions/browser-attract.md#demo-replay. Replay keys 1A/1B
    // select the six callback entries at 00019D68; the browser keeps the
    // selector in the flight seam instead of a hidden global byte.
    // DOS: FUN_0001959F [0001959F-00019907]; record: analysis/functions/browser-attract.md#view-select
    // View keys are handled separately because the original re-enters the
    // frame tail after selecting one. The browser preserves the state change
    // at this replay boundary and renders the selected basis on the next
    // normal frame, keeping the fixture tick count stable.
    applyReplayKey(key) {
      if (key === 0x1a) this.flight.weaponMode = (this.flight.weaponMode + 5) % 6;
      else if (key === 0x1b) this.flight.weaponMode = (this.flight.weaponMode + 1) % 6;
      else if (key === 0x28) this.effectATrigger = true;
      else if (key === 0x27) this.effectBTrigger = true;
      else if (key >= 0x02 && key <= 0x09) this.applyViewKey(key);
    }

    // DOS: FUN_000256C8 [000256C8-00025726]; record: analysis/functions/browser-attract.md#view-select
    // The fixed camera uses a second copy of the DOS table-driven bearing
    // routine. Keep the sign, octant, ratio quantizer, XOR correction, round,
    // and final one's complement; Math.atan2 is not equivalent here.
    viewBearingToPoint(originX, originY, targetX, targetY) {
      const dy = i32(targetY - originY);
      const dx = i32(targetX - originX);
      const yNegative = dy < 0 ? 1 : 0;
      const xNegative = dx < 0 ? 1 : 0;
      let yMagnitude = dy < 0 ? i32(~dy) : dy;
      let xMagnitude = dx < 0 ? i32(~dx) : dx;
      let octant = (yNegative << 2) | (xNegative << 1);
      let major = yMagnitude;
      let minor = xMagnitude;
      if (xMagnitude <= yMagnitude) {
        octant += 1;
        major = yMagnitude;
        minor = xMagnitude;
      } else {
        major = xMagnitude;
        minor = yMagnitude;
      }
      let bearing = OBJECT_OCTANT_TABLE[octant] >>> 0;
      const divisor = major >>> 10;
      if (divisor !== 0) {
        const ratio = Math.floor((minor >>> 0) / divisor);
        bearing ^= OBJECT_BEARING_CORRECTION[ratio] || 0;
      }
      return (~((bearing + 1) >>> 1)) & 0xff;
    }

    // DOS: FUN_0001959F [0001959F-000198B6]; record: analysis/functions/browser-attract.md#view-select
    // Place the variant-7 camera in the flight's raw 10.22 coordinate space,
    // using the published flight basis rather than the selected view basis.
    placeFixedCamera() {
      const flight = this.flight;
      const mapIndex = readMapIndex(flight.x, flight.y);
      const height = this.evidence.height.pixels[mapIndex] | 0;
      // 00019879-0001987D: byte shift wraps; only the following add saturates.
      const altitude = Math.min(0xff, ((height << 1) & 0xff) + 10);
      const sin = flight.pubSin ?? SINE_Q31[(flight.angle >>> 23) & 0x1ff];
      const cos = flight.pubCos ?? SINE_Q31[((flight.angle >>> 23) & 0x1ff) + 128];
      this.view_camera_dos_x = i32(flight.dosX - hi32(0x02800000, sin));
      this.view_camera_dos_y = i32(flight.dosY + hi32(0x02800000, cos));
      this.view_camera_altitude = altitude;
      this.view_camera_valid = true;
    }

    // DOS: FUN_00007D25 [00007D25-00007D7F] and handlers 00007BF0-00007D24; record:
    // analysis/functions/browser-attract.md#view-select
    // Publish the basis and live camera consumed by terrain/object drawing.
    buildViewBasis() {
      const flight = this.flight;
      if (!flight) return;
      let variant = this.view_variant | 0;
      if (variant < 1 || variant > 7) variant = 1;
      this.view_variant = variant;

      let angle = i32(flight.angle + VIEW_ANGLE_OFFSETS[variant]);
      let angleIndex = (angle >>> 23) & 0x1ff;
      let sin = SINE_Q31[angleIndex];
      let cos = SINE_Q31[angleIndex + 128];
      let cameraDosX = flight.dosX | 0;
      let cameraDosY = flight.dosY | 0;
      let cameraAltitude = flight.altitude & 0xff;
      let slope = flight.roll | 0;
      let offset = flight.pitch | 0;

      if (variant === 2) {
        slope = i32(flight.pitch << 2);
        offset = i32((-flight.roll) >> 2);
      } else if (variant === 3) {
        slope = i32(-(flight.pitch << 2));
        offset = i32(flight.roll >> 2);
      } else if (variant === 4) {
        slope = i32(-flight.roll);
        offset = i32(-flight.pitch);
      } else if (variant === 6) {
        angle = i32(angle - (flight.turn << 2));
        angleIndex = (angle >>> 23) & 0x1ff;
        sin = SINE_Q31[angleIndex];
        cos = SINE_Q31[angleIndex + 128];
        cameraDosX = i32(flight.dosX - hi32(0x0f000000, sin));
        cameraDosY = i32(flight.dosY + hi32(0x0f000000, cos));
        const mapIndex = readMapIndex(i32(cameraDosX >> 6), i32(cameraDosY >> 6));
        // 00007CAB-00007CB1: discard shift carry, saturate the add carry.
        const targetAltitude = Math.min(0xff, (((this.evidence.height.pixels[mapIndex] | 0) << 1) & 0xff) + 12);
        if (targetAltitude > cameraAltitude) cameraAltitude = targetAltitude;
        offset = 0;
      } else if (variant === 7) {
        if (this.view_camera_valid) {
          cameraDosX = this.view_camera_dos_x | 0;
          cameraDosY = this.view_camera_dos_y | 0;
          cameraAltitude = this.view_camera_altitude & 0xff;
        }
        const target = this.objects.find((object) => object.slot === 31 && object.active);
        if (target) {
          const targetX = target.dosX;
          const targetY = target.dosY;
          const bearing = this.viewBearingToPoint(cameraDosX, cameraDosY, targetX, targetY);
          angle = i32((((bearing + 128) & 0xff) << 24));
          angleIndex = (angle >>> 23) & 0x1ff;
          sin = SINE_Q31[angleIndex];
          cos = SINE_Q31[angleIndex + 128];
        }
        slope = 0;
        offset = 0;
      }

      this.view_angle = angle | 0;
      this.view_sin = sin | 0;
      this.view_cos = cos | 0;
      this.view_slope = slope | 0;
      this.view_offset = offset | 0;
      this.view_camera_dos_x = cameraDosX | 0;
      this.view_camera_dos_y = cameraDosY | 0;
      this.view_camera_x = i32(cameraDosX >> 6);
      this.view_camera_y = i32(cameraDosY >> 6);
      this.view_camera_altitude = cameraAltitude & 0xff;
    }

    // DOS: FUN_0001959F [0001959F-00019907]; record: analysis/functions/browser-attract.md#view-select
    // 0x02..0x08 select variants 1..7. 0x09 is the original quirk: it
    // re-selects variant 7 without placing the fixed camera again.
    applyViewKey(key) {
      if (key < 0x02 || key > 0x09) return;
      const variant = key === 0x09 ? 7 : key - 1;
      if (key !== 0x08 && key !== 0x09 && variant === this.view_variant) return;
      // 000196B4-000196CF: all seven select cases (00019787, 000197B7, 000197E7,
      // 00019817, 00019847, 000198D3, 00019903) jump here. It clears the target
      // [00019D10] and the threat blip [00019D93], and 0001687D, called at
      // 000196CF, zeroes the wreck's screen drop [00019DC4] (the chase view
      // the death block selects therefore starts with the drop back at 0).
      this.targetLatch = 0;                                      // 000196B4
      this.threatBlip = 0;                                       // 000196BE
      this.crashDrop = 0;                                        // 0001687D [00019DC4] = 0
      // Keep slot 31 at the frame-start viewer snapshot. DOS updates the
      // fixed object during the draw pass before this post-frame selector
      // runs; using the live post-flight position here shifts the bearing by
      // one replay record at the external-camera transition.
      if (key === 0x08) this.placeFixedCamera();
      this.view_variant = variant;
      if (variant !== 7) this.view_camera_valid = false;
      this.buildViewBasis();
      this.queueEvent(`view-select:${variant}`);
    }

    // DOS: FUN_00001B80 [00001B91-00001BA0]; record: analysis/functions/browser-attract.md#weapon-fire
    // The keyboard ISR's two array stores for one scancode byte (00001B81 `in
    // al, 0x60`): the state array [00001A70 + code & 0x7F] takes the byte
    // itself (0001B96; bit 7 is the break flag, so a held key reads
    // non-negative), and a make (non-negative byte) also stamps the latch
    // array [00001AF0 + code & 0x7F] (00001B9C-00001BA0) that the dispatch and
    // the target cycle clear when they consume it. The ISR's other work - the
    // collective notch [00019D85] for the +/-/ keys at 00001BA6-00001BE6, the
    // key history [00001B70], the Alt/A/KP. abort test at 00001C00-00001C18 -
    // is not carried. The browser page attaches no keyboard; this is the seam
    // a host adapter would call.
    keyEvent(code) {
      const index = code & 0x7f;                                 // 00001B93
      this.keyState[index] = code & 0xff;                        // 00001B96
      if ((code & 0x80) === 0) this.keyLatch[index] = code & 0xff;   // 00001B9C-00001BA0
    }

    // DOS: FUN_00018F94 [000191B6-0001922E]; record: analysis/functions/browser-attract.md#weapon-fire
    // The weapon dispatch inside the flight handler, after the control inputs
    // and before the terrain follow and movement core, so a weapon leaves from
    // the position, heading and pitch as they stood before this tick's move.
    //   000191B6  [00019D81] = 0, the sight element flag
    //   000191BD  console page [00019D88] == 0: the pending count [00019DF2]
    //             is discarded and the LIVE keys decide - Space [00001AA9] or
    //             KP5 [00001ABC] held (state byte non-negative), or the
    //             game-port button word [00019DEC] bit 0
    //   000191EA  any other page: a make latch of Space [00001B29] or KP5
    //             [00001B3C], or else a pending count, which is decremented
    //   0001920B  [00019D81] = 1, both make latches cleared, and the page's
    //             launcher called through [00019D68]: 00022890, 00022B00,
    //             00022F90, 00022E70, 000231B2, 000230B0
    // Pages 1-5 still call the earlier browser launch models (spawnWeaponObject
    // below), which are NOT ports of those launchers - only the cannon is.
    weaponDispatch() {
      const flight = this.flight;
      this.weaponSightFlag = 0;                                  // 000191B6
      let fire = false;
      if (flight.weaponMode === 0) {                             // 000191BD-000191C4
        flight.trigger1 = 0;                                     // 000191C6
        fire = (this.keyState[KEY_SPACE] & 0x80) === 0           // 000191CD-000191D4 jns
          || (this.keyState[KEY_KP5] & 0x80) === 0               // 000191D6-000191DD jns
          || (this.gamePortButtons & 1) !== 0;                   // 000191DF-000191E6
      } else if (this.keyLatch[KEY_SPACE] !== 0                  // 000191EA-000191F1
        || this.keyLatch[KEY_KP5] !== 0) {                       // 000191F3-000191FA
        fire = true;
      } else if (flight.trigger1 !== 0) {                        // 000191FC-00019203
        flight.trigger1 = (flight.trigger1 - 1) & 0xff;          // 00019205
        fire = true;
      }
      if (!fire) return;                                         // 000191E8 / 00019203 -> 00019230
      this.weaponSightFlag = 1;                                  // 0001920B
      this.keyLatch[KEY_SPACE] = 0;                              // 00019212
      this.keyLatch[KEY_KP5] = 0;                                // 00019219
      const mode = flight.weaponMode;                            // 00019220
      if (mode === 0) this.fireCannon();                         // 00019227-0001922E [00019D68]
      else if (mode === 1) this.spawnWeaponObject(0x241c0, "ROCK.RLE");
      else if (mode === 2) this.spawnWeaponObject(0x24680, "HELL.RLE");
      else if (mode === 3) this.spawnWeaponObject(0x24860, "STGR.RLE");
      else if (mode === 4) this.spawnWeaponObject(0x24680, "HELL.RLE", this.targetSlot);
      else if (mode === 5) this.spawnWeaponObject(0x24680, "HELL.RLE", this.targetSlot);
    }

    // DOS: FUN_00018F94 [000192A9-000192EE]; record: analysis/functions/browser-attract.md#target-cycle
    // The two rudder keys, KP0 [00001AC2] and KP. [00001AC3], step the turn
    // rate [00019D08] by 0x400000 a tick while held (state byte
    // non-negative), after the clamp at 000190BE-000190EA and without a new
    // one. Then a damaged targeting cell [00019E3C] (hull.cells[4], negative)
    // drops the lock whenever the shake PRNG [00019DB8] & 0x1C is zero.
    rudderAndLockLoss() {
      const flight = this.flight;
      if ((this.keyState[KEY_KP0] & 0x80) === 0) flight.turn = i32(flight.turn - 0x400000);     // 000192A9-000192B2
      if ((this.keyState[KEY_KPDOT] & 0x80) === 0) flight.turn = i32(flight.turn + 0x400000);   // 000192BC-000192C5
      if ((this.hull.cells[4] & 0x80) !== 0 && (this.shake.rng & 0x1c) === 0) {                 // 000192CF-000192E2
        this.targetLatch = 0;                                    // 000192E4
      }
    }

    // DOS: FUN_00018D20 [00018E10-00018E49]; record: analysis/functions/browser-attract.md#fuel-exhausted
    // The fuel tank [00019D60] below zero takes the collective away from the
    // pilot: at exactly -0x10E the flight ends (00018E19-00018E23 je
    // 0002873D, the mission-abort chain, which is not carried: the request is
    // recorded and the tick stops); before that the collective is last tick's
    // [00019D83], less one while non-zero (00018E29-00018E3C). The call at
    // 00018E44 as it reaches zero is 0001899A, the engine-out voice - a
    // sound request, with the rest of the audio. Every tick that gets past
    // the branch spends one unit (00018E49). Returns true when the tick ends.
    applyFuelState() {
      const flight = this.flight;
      if (flight.fuel < 0) {                                     // 00018E10-00018E17 jns
        if (flight.fuel === -0x10e) {                            // 00018E19-00018E23
          flight.missionEnd = 1;
          return true;
        }
        flight.collective = flight.collectivePrev;               // 00018E29-00018E2E
        if (flight.collective !== 0) {                           // 00018E33-00018E3A
          flight.collective = (flight.collective - 1) & 0xff;    // 00018E3C-00018E42
        }
      }
      flight.fuel = i32(flight.fuel - 1);                        // 00018E49
      return false;
    }

    // DOS: FUN_0000D3C0 [0000D418-0000D47F]; record: analysis/functions/browser-attract.md#target-cycle
    // After the input and flight tick the frame driver reads the locked
    // object's targetability byte [00021BAB] (rebuilt by this frame's object
    // pass): the object's depth is latched for the RANGE readout first
    // ([00019D14], 0000D43D-0000D444), and a zero byte clears the lock
    // (0000D449-0000D454). Skipped in the console variants past 5. The
    // designator stores at 0000D421-0000D428 and 0000D460-0000D478 feed the
    // HUD marker box this reference does not draw.
    validateTargetLatch() {
      if (this.view_variant > 5) return;                         // 0000D418-0000D41F
      const latch = this.targetLatch;                            // 0000D433-0000D43B
      if (latch === 0) return;
      const target = this.objectBySlot.get(latch) || this.makeObjectSlotImage(latch);
      this.targetRange = target.depthDos | 0;                    // 0000D43D-0000D444
      if ((target.targetFlag & 0xff) === 0) this.targetLatch = 0;   // 0000D449-0000D454 shl eax,1 / jne
    }

    // DOS: FUN_00019555 [00019555-0001959E]; record: analysis/functions/browser-attract.md#flight-integration.
    // The countermeasure decision that ends every flight tick, plus the two
    // direct replay-key paths of 0001959F (key 0x28 jumps to the BULL launcher
    // 00022A00, key 0x27 to the CHAF launcher 00022AA0, neither with an
    // altitude or in-the-air test; the launchers test their quota and a free
    // slot themselves).
    //
    // 00019555-0001956E: the threat blip [00019D93] (the MFD display of the
    // previous frame) and the shell-hit flag [00019D94] ask for a BULL flare,
    // the tank-aim flag [00019D92] for CHAF, the blip taking precedence over
    // the aim flag. 00019571: BULL needs altitude > 0x0A and none in the air
    // ([00019D90] = 0); 00019588: CHAF altitude > 0x14 and none in the air
    // ([00019D8F] = 0).
    dispatchFlightEffects() {
      if (this.effectATrigger) this.spawnEffectA();              // 000195A3 jmp 00022A00
      if (this.effectBTrigger) this.spawnEffectB();              // 000195AC jmp 00022AA0
      this.effectATrigger = false;
      this.effectBTrigger = false;
      const altitude = this.flight.altitude & 0xff;              // [00019DFC]
      let bull;
      if (this.threatBlip !== 0) bull = true;                    // 00019555-0001955C
      else if (this.threatChaff !== 0) bull = false;             // 0001955E-00019565
      else if (this.threatBull !== 0) bull = true;               // 00019567-0001956E
      else return;                                               // 00019570
      if (bull) {
        if (altitude <= 0x0a) return;                            // 00019571-00019578
        if (this.effectAActive === 0) this.spawnEffectA();       // 0001957A-00019581
      } else {
        if (altitude <= 0x14) return;                            // 00019588-0001958F
        if (this.effectBActive === 0) this.spawnEffectB();       // 00019591-00019598
      }
    }

    // DOS: FUN_000077A0 [000077A0-0000785C]; record: analysis/functions/browser-attract.md#cockpit-hud
    // The MFD threat display, in the cockpit view only (it sits in the
    // [00019D86] = 1 branch of 0000D3C0, after the flight tick). Walking slots
    // 0x82..0x1F it sets [00019D93] for any active slot with a non-zero aux
    // byte whose DOS-unit lateral is inside +-0x14 << 24 and whose depth is
    // inside +-0xF << 24 (this frame's 00024B17 transform). The blip draw
    // through 00025B27 is not ported; the flag is what the flight tick of the
    // NEXT frame reads (00019555).
    updateThreatDisplay() {
      this.threatBlip = 0;                                       // 000077BD-000077C7
      for (let slot = 0x82; slot !== 0x1e; slot -= 1) {         // 000077D0-00007841
        const object = this.objectBySlot.get(slot);
        if (!object || !object.active || object.aux === 0) continue;   // 000077D5-000077E6
        const lateral = object.lateralDos >> 24;                 // 000077ED-000077F4
        if (lateral <= -0x14 || lateral >= 0x14) continue;       // 000077F6-000077FE
        const depth = i32(-object.depthDos) >> 24;               // 00007800-00007809
        if (depth <= -0x0f || depth >= 0x0f) continue;           // 0000780B-00007813
        this.threatBlip = 1;                                     // 00007836
      }
    }

    // DOS: FUN_000059ED [000059ED-00005AD6]; record: analysis/functions/browser-attract.md#attract-cycle
    advanceScreen() {
      // DOS: FUN_00005690; record: analysis/functions/browser-attract.md#attract-cycle
      // Draw happens before this state/timer tick.
      if (this.screen === "side") {
        this.anim = (this.anim + 1) % ZOVE_FRAMES.length;
      } else if (this.screen === "title") {
        this.anim = (this.anim + 1) % COMA_FRAMES.length;
        if (this.pan >= TITLE_GATE_ROW) {
          let helicopter = this.heli + this.step;
          if (helicopter < TITLE_HELI_TOP) helicopter = TITLE_HELI_TOP;
          if (helicopter > TITLE_HELI_LOW) {
            helicopter = TITLE_HELI_LOW;
            this.wobble += 1;
            helicopter += PAN_WOBBLE[(this.wobble >> 1) & 63];
          }
          this.heli = helicopter;
        }
        this.pan += 1;
        if (this.pan > TITLE_PAN_LAST) {
          this.pan = TITLE_PAN_LAST;
          this.heli -= 1;
        }
        if (this.timer < 45) this.step = -1;
        if (this.timer < 40) this.step = -2;
      }
      this.timer -= 1;
      if (this.timer > 0) return;
      if (this.screen === "fanfare") {
        this.enterTitle();
      } else if (this.screen === "side") {
        this.enterDemo(this.pass === 2 ? 2 : 0);
      } else if (this.screen === "title") {
        this.enterDemo(this.pass === 1 ? 1 : 3);
      }
    }

    // DOS: FUN_00018C29/00019A2D [entries 00018C29,00019A2D]; record: analysis/functions/browser-attract.md#demo-replay
    advanceDemoInput() {
      // DOS: FUN_00018C29/00019A2D; record: analysis/functions/browser-attract.md#demo-replay
      // Input is fed only after the current frame is drawn.
      if (this.demoCursor >= this.demo.records.length) {
        this.demoEnded = true;
        this.queueEvent(`demo-end:DEMO${this.demoIndex}.SCR`);
        this.enterNextPass();
        return null;
      }
      // The fuel branch ended the flight (00018E23 -> 0002873D); that chain
      // is not carried, so the tick stays stopped.
      if (this.flight.missionEnd) return null;
      const record = this.demo.records[this.demoCursor];
      this.demoCursor += 1;
      this.flight.collectivePrev = this.flight.collective;     // 00018D20-00018D25 [00019D83]
      this.applyReplayKey(record.key & 0xff);
      this.flight.collective = record.collective & 0xff;
      this.flight.trigger1 |= record.trigger1 & 0xff;
      this.flight.trigger2 |= record.trigger2 & 0xff;
      this.flight.axis1 = record.axis1 | 0;
      this.flight.axis2 = record.axis2 | 0;
      if (this.applyFuelState()) {                              // 00018E10-00018E49
        this.queueEvent(`mission-end:fuel`);
        return record;
      }
      this.flightTick();
      this.applyViewKey(record.key & 0xff);
      this.dispatchFlightEffects();
      this.validateTargetLatch();                               // 0000D418-0000D47F
      this.queueEvent(`demo-record:${record.index}`);
      return record;
    }

    // DOS: FUN_00005690 [00005690-00005AE3]; record: analysis/functions/browser-attract.md#attract-cycle
    drawCurrent() {
      // Target artefact: initial/fixture redraw dispatches the same recovered
      // screen or flight composition without advancing its state.
      if (this.mode === "demo") this.drawDemo();
      else this.drawScreen();
    }

    // DOS: FUN_00005690 [00005690-00005AE3] / FUN_00025880 [00025880-00025DBC]; record: analysis/functions/browser-attract.md#attract-cycle
    drawScreen() {
      const image = this.screen === "fanfare"
        ? this.evidence.opening.back
        : this.screen === "side" ? this.evidence.opening.side : this.evidence.opening.title;
      const pixels = image.pixels;
      const width = image.header.widthMax + 1;
      const height = image.header.heightMax + 1;
      this.frame.fill(0);
      for (let y = 0; y < VIEW_H; y += 1) {
        const sourceY = this.pan + y;
        if (sourceY < 0 || sourceY >= height) continue;
        for (let x = 0; x < VIEW_W; x += 1) {
          this.frame[(y * VIEW_W) + x] = this.screenPaletteWords[pixels[(sourceY * width) + x]];
        }
      }
      if (this.screen === "side") {
        const frame = ZOVE_FRAMES[this.anim];
        drawOpaqueSprite(this.frame, this.evidence.banks.zove, frame, 0xaf, 0x4b, this.zoveLookup, this.spriteCache);
      } else if (this.screen === "title" && this.pan >= TITLE_GATE_ROW) {
        const frame = COMA_FRAMES[this.anim];
        drawOpaqueSprite(this.frame, this.evidence.banks.coma, frame, 0xa0, this.heli - this.pan, this.comaLookup, this.spriteCache);
      }
    }

    // DOS: FUN_00007D25 [00007D25-0000AF4E]; record: analysis/functions/browser-attract.md#terrain-setup
    renderClear() {
      // DOS: FUN_00007D25; record: analysis/functions/browser-attract.md#terrain-setup
      // RGB565 replaces the DOS DAC/planar presentation only.
      // DOS: FUN_00019681/render_reset_surface; record:
      // analysis/functions/browser-attract.md#terrain-renderer. The surface
      // is persistent. Only the authored sky spans are repainted here.
      this.frame.set(this.terrainSurface);
      const sky = this.evidence.sky.payload;
      const dy = buildBackdropDy(this.view_slope, this.view_offset, this.shake.phase);
      const origin = (((~this.view_angle) - 0x30000000) >>> 23) & 0x1ff;
      for (let column = 0; column < TERRAIN_COLS; column += 1) {
        if (column < TERRAIN_VIEW_FIRST || column > TERRAIN_VIEW_LAST) continue;
        const x = (column - TERRAIN_VIEW_FIRST) * 2;
        const h = dy[column];
        const start = -h - SKY_TOP_BIAS;
        const strip = (origin + TERRAIN_COLS - 1 - column) & (SKY_STRIPS - 1);
        let sourceRow = start < 0 ? -start : 0;
        let targetRow = start < 0 ? 0 : start;
        let count = SKY_ROWS - sourceRow;
        if (targetRow < TERRAIN_TRANSFER_ROWS && count > 0) {
          count = Math.min(count, TERRAIN_TRANSFER_ROWS - targetRow);
          for (let row = 0; row < count; row += 1) {
            const pixel = sky.pixels[(strip * SKY_ROWS) + sourceRow + row];
            const word = this.skyPalette[pixel];
            const offset = ((targetRow + row) * VIEW_W) + x;
            this.frame[offset] = word;
            this.frame[offset + 1] = word;
          }
        }
        if (h > 0) {
          let wrappedSource = 0;
          let wrappedTarget = (PAGE_ANCHOR + 1) - h;
          let wrappedCount = Math.min(h, SKY_ROWS);
          if (wrappedTarget < 0) {
            wrappedSource = -wrappedTarget;
            wrappedTarget = 0;
            wrappedCount -= wrappedSource;
          }
          if (wrappedTarget < TERRAIN_TRANSFER_ROWS && wrappedCount > 0) {
            wrappedCount = Math.min(wrappedCount, TERRAIN_TRANSFER_ROWS - wrappedTarget);
            for (let row = 0; row < wrappedCount; row += 1) {
              const pixel = sky.pixels[(strip * SKY_ROWS) + wrappedSource + row];
              const word = this.skyPalette[pixel];
              const offset = ((wrappedTarget + row) * VIEW_W) + x;
              this.frame[offset] = word;
              this.frame[offset + 1] = word;
            }
          }
        }
      }
    }

    // DOS: FUN_00006FEF [00006FEF-00007BCD]; record: analysis/functions/browser-attract.md#terrain-renderer
    drawTerrainSpan(column, top, bottom, word) {
      // DOS: FUN_00006BF0 [00006BF0-00006FEC]; record: analysis/functions/browser-attract.md#terrain-renderer
      // The DOS span writer increments CH through the 256-row surface. The
      // browser keeps the same inclusive span and applies only a target-side
      // surface-boundary clip instead of allowing a VGA page wrap.
      let first = Math.max(0, top);
      const last = Math.min(TERRAIN_TRANSFER_ROWS - 1, bottom);
      if (first > last || column < TERRAIN_VIEW_FIRST || column > TERRAIN_VIEW_LAST) return;
      const x = (column - TERRAIN_VIEW_FIRST) * 2;
      for (; first <= last; first += 1) {
        const offset = (first * VIEW_W) + x;
        this.frame[offset] = word;
        this.frame[offset + 1] = word;
      }
    }

    // DOS: FUN_0000D950 [0000D950-0000F317]; record: analysis/functions/browser-attract.md#terrain-renderer
    drawTerrain() {
      // DOS: FUN_0000D950; record: analysis/functions/browser-attract.md#terrain-renderer
      // Ring order, map addressing, projection pages and strict
      // occlusion are preserved.
      const heightMap = this.evidence.height.pixels;
      const colourMap = this.colourMap;
      const tables = this.evidence.detail.tables;
      const forwardX = this.view_sin;
      const forwardY = this.view_cos;
      const cameraHeight = (127 - (this.view_camera_altitude >> 1)) & 0xff;
      const backdropDy = buildBackdropDy(this.view_slope, this.view_offset, this.shake.phase);
      const occlusion = new Int16Array(TERRAIN_COLS);
      occlusion.fill(PAGE_ANCHOR);
      // 0000D974/0000D97A: EDI/EBX load the raw 10.22 camera.
      // DTL steps and every accumulated sample retain that scale; converting
      // each step to 16.16 would discard carries before the map lookup.
      let centreX = this.view_camera_dos_x | 0;
      let centreY = this.view_camera_dos_y | 0;

      for (let ring = 0; ring < 250; ring += 1) {
        const forwardStep = tables[1][ring] | 0;
        const lateralStep = tables[0][ring] | 0;
        centreX = i32(centreX + hi32(forwardStep, forwardX));
        // 0000D9B1/0000D9B7: subtract the signed high product, after IMUL.
        centreY = i32(centreY - hi32(forwardStep, forwardY));
        const lateralX = hi32(lateralStep, forwardY);
        const lateralY = hi32(lateralStep, forwardX);
        const pageBase = ring * 256;
        let x = centreX;
        let y = centreY;
        for (let column = 95; column >= 0; column -= 1) {
          this.drawTerrainSample(column, x, y, cameraHeight, pageBase, occlusion, heightMap, colourMap, backdropDy);
          x = i32(x - lateralX);
          y = i32(y - lateralY);
        }
        x = i32(centreX + lateralX);
        y = i32(centreY + lateralY);
        for (let column = 96; column < TERRAIN_COLS; column += 1) {
          this.drawTerrainSample(column, x, y, cameraHeight, pageBase, occlusion, heightMap, colourMap, backdropDy);
          x = i32(x + lateralX);
          y = i32(y + lateralY);
        }
        // 0000F2DE-0000F2FF: the ring's 192 horizon bytes (page rows; the
        // surface rows above are PAGE_ANCHOR minus them) are archived at
        // [00019E60] + ring * 256 + 0x20.
        const archive = ring * TERRAIN_COLS;
        for (let column = 0; column < TERRAIN_COLS; column += 1) {
          this.ringHorizon[archive + column] = (PAGE_ANCHOR - occlusion[column]) & 0xff;
        }
      }
    }

    // DOS: FUN_0000D9E9 [0000D9E9]; record: analysis/functions/browser-attract.md#terrain-renderer
    drawTerrainSample(column, x, y, cameraHeight, pageBase, occlusion, heightMap, colourMap, backdropDy) {
      // 0000D9EE/0000D9F2: SHLD packs the top ten bits of each raw
      // 10.22 coordinate. Keep readMapIndex's 16.16 contract for its other
      // consumers; terrain does not cross that boundary.
      const mapIndex = ((y >>> 22) << 10) | (x >>> 22);
      const pageRow = this.ringPageTable[pageBase + ((cameraHeight + heightMap[mapIndex]) & 0xff)];
      const screenRow = PAGE_ANCHOR - pageRow;
      const oldHorizon = occlusion[column];
      if (screenRow >= oldHorizon) return;
      const word = this.terrainPalette[colourMap[mapIndex]];
      occlusion[column] = screenRow;
      const tilt = backdropDy[column];
      this.drawTerrainSpan(column, screenRow + 1 - tilt, oldHorizon - tilt, word);
    }

    // DOS: FUN_00006FEF [00006FEF-00007BCD] / FUN_00025880 [00025880-00025DBC]; record: analysis/functions/browser-attract.md#sprite-and-console-composition
    drawConsole() {
      // DOS: FUN_00006FEF/00025880; CONSOL1S is a 328-byte
      // pitch image; the visible Falcon/browser crop is its first 320 columns,
      // and source row zero is the screen's row zero. Index 255 is the
      // authored clear/opening value. Index 0 is ordinary console ink.
      // 00019689's cases select the image and 0002543A draws whatever is
      // loaded: consol1s..consol4s for variants 1..4, consol5s for 5, 6 and 7.
      // The external images are 245 rows to the cockpit's 290, and both are
      // read row-for-row against the screen, so the first 240 rows of either
      // land the same way.
      const digit = Math.min(this.view_variant & 0xff, 5);
      const image = this.evidence.consoleImages?.[digit] || this.evidence.consoleImage;
      const words = this.consoleLookups?.[digit] || this.consoleWords;
      const sourceWidth = image.header.widthMax + 1;
      for (let y = 0; y < VIEW_H; y += 1) {
        const sourceRow = y * sourceWidth;
        const targetRow = y * VIEW_W;
        for (let x = 0; x < VIEW_W; x += 1) {
          const pixel = image.pixels[sourceRow + x];
          if (pixel === 0xff) continue;
          this.frame[targetRow + x] = words[pixel];
        }
      }
    }

    // DOS: FUN_00007403/00007443/000077BE [entries 00007403,00007443,000077BE]; record: analysis/functions/browser-attract.md#sprite-and-console-composition
    drawFixedInstruments() {
      // DOS: FUN_00007403/00007443/000077BE. These are opaque CONS elements
      // at the exact bottom-origin coordinates recovered from the call sites.
      const bank = this.evidence.banks.cons;
      drawOpaqueSprite(this.frame, bank, 0x09, 0x10, 0xea, this.consLookup, this.spriteCache);
      drawOpaqueSprite(this.frame, bank, 0x25, 0x0c, 0xc9, this.consLookup, this.spriteCache);
      drawOpaqueSprite(this.frame, bank, 0x39, 0x110, 0xcb, this.consLookup, this.spriteCache);
    }

    // DOS: FUN_00007580 [00007580-000075AD]; record: analysis/functions/browser-attract.md#mfd-map
    drawMfdMap(panelOffset = 0) {
      // DOS 00015855/0001591A: the left MFD is an 80x44 top-down map. The
      // browser writes the same raw 10.22 samples directly into its chunky
      // crop; the four DOS plane passes collapse to one linear pass.
      const angleIndex = (this.flight.angle >>> 23) & 0x1ff;
      const sin = SINE_Q31[angleIndex];
      const cos = SINE_Q31[angleIndex + 128];
      const basisX = hi32(MFD_ZOOM, sin);
      const basisY = hi32(MFD_ZOOM, cos);
      const pixelX = basisY >> 2;
      const pixelY = basisX >> 2;
      let rowX = i32(this.flight.dosX + (basisX << 3));
      let rowY = i32(this.flight.dosY - (basisY << 3));
      rowX = i32(rowX - (pixelX * MFD_HALF_W));
      rowY = i32(rowY - (pixelY * MFD_HALF_W));

      for (let row = 0; row < MFD_H; row += 1) {
        let x = rowX;
        let y = rowY;
        const targetRow = (MFD_Y + row) * VIEW_W;
        for (let column = 0; column < MFD_W; column += 1) {
          const mapIndex = ((y >>> 22) << 10) | (x >>> 22);
          this.frame[targetRow + MFD_SURFACE_X + panelOffset + column] = this.terrainPalette[this.colourMap[mapIndex]];
          x = i32(x + pixelX);
          y = i32(y + pixelY);
        }
        rowX = i32(rowX - pixelY);
        rowY = i32(rowY + pixelX);
      }
    }

    // DOS: FUN_0001C920 [0001C920-0001CAC0]; record: analysis/functions/browser-attract.md#mfd-target-view
    // The target view's sourced sky, installed in [00019C9C] by 000261AF-000261E0
    // when the sky option [00025DD8] is on (it is, in the shipped settings;
    // 0001CAD0's flat viewport fill is the option-off member). Forty
    // iterations, one per column pair from the right (dl = 0x53 down to 0x2C):
    // each takes the next-but-one of the sky bank's 512 column strips of 150
    // bytes, starting at ((~[00019D00] - 0x14000000) >> 23) (0001C941-0001C957;
    // [00019D00] is the substituted view angle, bearing << 24), skips the
    // strip's first 90 bytes (0001C96B `add esi, 0x5A`) and stores the
    // remaining 60 downward from page row 0xA5 (0001C963-0001C9BC, with the
    // horizon bytes 0001B295 has just zeroed). The strip pointer wraps to
    // strip 0 whenever it reaches the end of the bank (0001CA9A-0001CAB7),
    // which is modulo 512 strips. 000079F0 then reads page row 162 - 2r for
    // panel row r (its edx starts at +0xA22C and drops 0x200 a row), so panel
    // row r takes strip byte 255 - (162 - 2r) = 93 + 2r, rows 0..28; the
    // pair's second pixel is the same value (the pair stores of
    // 0001C1B0-0001C1B4, and the captured DOS panels, are pairwise equal).
    // Returns the number of pixels written.
    drawMfdTargetSky(angle) {
      const sky = this.evidence.sky.payload;
      const first = (((~angle) - 0x14000000) >>> 23) & (SKY_STRIPS - 1);
      let painted = 0;
      for (let iteration = 0; iteration < 40; iteration += 1) {         // 0001C92F ecx = 0x28
        const pair = 39 - iteration;                                      // dl = 0x2C + pair
        const strip = (first + (2 * iteration)) & (SKY_STRIPS - 1);       // 0001CA9A-0001CAB7
        for (let row = 0; row < 29; row += 1) {
          const pixel = sky.pixels[(strip * SKY_ROWS) + 93 + (2 * row)];
          const word = this.skyPalette[pixel];
          const offset = ((MFD_Y + row) * VIEW_W) + MFD_SURFACE_X + MFD_PANEL_STEP + (2 * pair);
          this.frame[offset] = word;
          this.frame[offset + 1] = word;
          painted += 2;
        }
      }
      return painted;
    }

    // DOS: FUN_0001B26C [0001B26C-0001B34F]; record: analysis/functions/browser-attract.md#mfd-target-view
    drawMfdTargetTerrain(cameraDosX, cameraDosY, cameraAltitude, angle) {
      // DOS 0001B26C: march the target view with the original three-ring
      // cursor advance, paired columns, strict horizon test and 162-to-44-row
      // window. The target view has its own occlusion array; it must not reuse
      // the flight view's terrain surface or horizon state.
      const tables = this.evidence.detail.tables;
      const forwardTable = tables[1];
      const lateralTable = tables[0];
      const ringSteps = Math.min(forwardTable.length, lateralTable.length, this.ringPageTable.length / 256);
      const ringCount = Math.floor(ringSteps / 3);
      if (ringCount <= 0) return;

      const angleIndex = (angle >>> 23) & 0x1ff;
      const sin = SINE_Q31[angleIndex];
      const cos = SINE_Q31[angleIndex + 128];
      const cameraHeight = (127 - (cameraAltitude >> 1)) & 0xff;
      const occlusion = new Uint8Array(MFD_W);
      // 0001B29C `call [00019C9C]`: the sourced sky fill runs before the first
      // ring, so the terrain below overpaints it.
      let painted = this.drawMfdTargetSky(angle);
      let centreX = cameraDosX | 0;
      let centreY = cameraDosY | 0;

      for (let ring = 0, ringIndex = 0; ring < ringCount; ring += 1, ringIndex += 3) {
        // DOS 0001B2DF/0001B2E6 use A[i] + A[i+1], then 0001B883 advances
        // the shared cursor by three entries. B[i] is doubled before its two
        // Q31 products, exactly as 0001B301/0001B312 do.
        const forwardStep = i32((forwardTable[ringIndex] | 0) + (forwardTable[ringIndex + 1] | 0));
        centreX = i32(centreX + hi32(forwardStep, sin));
        centreY = i32(centreY - hi32(forwardStep, cos));
        const lateralStep = i32((lateralTable[ringIndex] | 0) * 2);
        const lateralX = hi32(lateralStep, cos);
        const lateralY = hi32(lateralStep, sin);
        const pageBase = ringIndex * 256;

        for (let half = 0; half < 2; half += 1) {
          let x = half === 0 ? centreX : i32(centreX + lateralX);
          let y = half === 0 ? centreY : i32(centreY + lateralY);
          let column = half === 0 ? 38 : 40;
          const columnStep = half === 0 ? -2 : 2;
          const stepX = half === 0 ? -lateralX : lateralX;
          const stepY = half === 0 ? -lateralY : lateralY;
          for (let sample = 0; sample < MFD_W / 4; sample += 1) {
            const mapIndex = ((y >>> 22) << 10) | (x >>> 22);
            const height = this.evidence.height.pixels[mapIndex] | 0;
            const page = this.ringPageTable[pageBase + ((cameraHeight + height) & 0xff)] | 0;
            const oldPage = occlusion[column] | 0;
            if (page > oldPage) {
              const word = this.terrainPalette[this.colourMap[mapIndex]];
              let top = MFD_VIEW_TOP_ROW - page;
              top = top < 0 ? 0 : top >> 1;
              if (top < MFD_H) {
                let bottom = MFD_VIEW_TOP_ROW - oldPage;
                bottom = bottom < 0 ? 0 : bottom >> 1;
                bottom = Math.min(MFD_H, bottom);
                for (let panelRow = top; panelRow < bottom; panelRow += 1) {
                  const rowOffset = ((MFD_Y + panelRow) * VIEW_W) + MFD_SURFACE_X + MFD_PANEL_STEP + column;
                  this.frame[rowOffset] = word;
                  this.frame[rowOffset + 1] = word;
                  painted += 2;
                }
              }
              occlusion[column] = page;
              occlusion[column + 1] = page;
            }
            x = i32(x + stepX);
            y = i32(y + stepY);
            column += columnStep;
          }
        }
      }
      return painted;
    }

    // DOS: FUN_00007860 [00007860-000079E3]; record: analysis/functions/browser-attract.md#mfd-target-view
    drawMfdTargetView() {
      // DOS 00007860 substitutes the locked target's camera before calling
      // 0001B26C. The browser's replay selector is the recovered target latch
      // for this connected slice; before the first target-selection record,
      // the original page is legitimately left as console black.
      let target = this.objects.find((object) => object.active && !object.dynamic
        && object.slot === this.targetSlot && object.slot >= 1 && object.slot <= 30);
      if (!target) {
        // Target artefact: the browser keeps the connected MFD useful during
        // the short interval before DEMO's target-cycle byte selects a live
        // slot. Once the replay has selected a target, the exact slot above
        // owns the view; this fallback prevents a newly entered mission from
        // presenting two empty screens while its first records are consumed.
        target = this.objects
          .filter((object) => object.active && !object.dynamic && object.slot >= 1 && object.slot <= 30)
          .sort((left, right) => left.slot - right.slot)[0] || null;
      }
      if (!target) {
        // Target artefact: keep the panel populated even on a mission family
        // whose replay has not installed a targetable object yet.
        this.drawMfdMap(MFD_PANEL_STEP);
        return;
      }

      const bearing = this.viewBearingToPoint(target.dosX, target.dosY, this.flight.frameDosX, this.flight.frameDosY);
      const bearingIndex = (bearing << 1) & 0x1ff;
      const sin = SINE_Q31[bearingIndex];
      const cos = SINE_Q31[bearingIndex + 128];
      const targetDosX = target.dosX;
      const targetDosY = target.dosY;
      const cameraDosX = i32(targetDosX - hi32(0x10000000, sin));
      const cameraDosY = i32(targetDosY + hi32(0x10000000, cos));
      const angle = i32(bearing << 24);
      const painted = this.drawMfdTargetTerrain(cameraDosX, cameraDosY, target.altitude, angle);
      if (!painted) {
        // Target artefact: a target can be selected before its substituted
        // view has a visible terrain span. Keep the connected cockpit useful
        // by showing the same authored moving-map body until that next span.
        this.drawMfdMap(MFD_PANEL_STEP);
      }

      // DOS 000079AF-000079E3: RANGE is the target's current forward depth,
      // drawn through HUDS at the right panel's page-relative anchor.
      const range = Math.max(0, target.depth >> 16);
      const rangeX = 0x75 + MFD_PANEL_STEP - 4;
      drawMaskedSprite(this.frame, this.evidence.banks.huds, 0x20, rangeX, 0xd7,
        this.hudsLookup, this.spriteCache);
      this.drawHudValue(range, rangeX, 0xd7);
    }

    // DOS: FUN_000075B0 [000075B0-00007666]; record: analysis/functions/browser-attract.md#mfd-map
    drawMfdMarkers() {
      // DOS 000075C9/0000763A: map markers use the current flight-view
      // lateral/depth transform and the HUDS palette. The browser keeps the
      // original target blink cadence while bounding sprite writes to the
      // 320x240 surface.
      const zoom = MFD_ZOOM >>> 5;
      if (!zoom) return;
      const scale = Math.floor(0xffffffff / zoom);
      for (const object of this.objects) {
        if (!object.active || !object.aux) continue;
        const mapX = Number((BigInt(object.lateral | 0) * BigInt(scale)) >> 26n);
        const mapY = Number((BigInt(-(object.depth | 0)) * BigInt(scale)) >> 26n);
        if (mapX <= -0x26 || mapX >= 0x26) continue;
        const x = 0x6f + mapX - 4;
        const y = 0xce + mapY;
        if (mapY <= -0x15 || mapY >= 0x0b) continue;
        drawMaskedSprite(this.frame, this.evidence.banks.huds, object.aux, x, y,
          this.hudsLookup, this.spriteCache);
        if ((this.logicalTick & 3) === 0 && object.flag) {
          drawMaskedSprite(this.frame, this.evidence.banks.huds, 0x14, x, y,
            this.hudsLookup, this.spriteCache);
        }
      }

      // DOS 000075A1/0002599E: the own-ship cross is an instrument-bank
      // overlay on the map, not a HUD glyph.
      drawMaskedSprite(this.frame, this.evidence.banks.cons, 3, 0x70 - 4, 0xce,
        this.consLookup, this.spriteCache);
    }

    // DOS: FUN_000073D0 [000073D0-000079E3]; record: analysis/functions/browser-attract.md#cockpit-hud
    drawMfdStage() {
      // DOS dispatches both MFD bodies after the console and before the fixed
      // instruments. Keep that order so the bezel and F-key labels remain on
      // top of the live panel pixels.
      this.drawMfdMap();
      this.drawMfdTargetView();
      this.drawMfdMarkers();
    }

    // DOS: FUN_00025A4D [00025A4D-00025BEA]; record: analysis/functions/browser-attract.md#sprite-and-console-composition
    drawHeadingWindow() {
      // DOS: FUN_00025A4D. HUDS element 1 is a 192x5 column ribbon;
      // the heading selects a 64-column window beginning at (angle >> 25).
      const decoded = spriteFrame(this.evidence.banks.huds, 1, this.spriteCache);
      const sourceColumn = (this.flight.angle >>> 25) & 0x7f;
      for (let column = 0; column < 64; column += 1) {
        const targetX = 136 + column;
        if (targetX < 0 || targetX >= VIEW_W) continue;
        for (let row = 0; row < 5; row += 1) {
          const pixel = decoded.pixels[(row * decoded.sprite.width) + sourceColumn + column];
          if (pixel === 0) continue;
          const targetY = 5 + row;
          if (targetY < 0 || targetY >= VIEW_H) continue;
          this.frame[(targetY * VIEW_W) + targetX] = this.hudsLookup[pixel];
        }
      }
    }

    // DOS: FUN_0000D8F5 [0000D8F5-0000D950]; record: analysis/functions/browser-attract.md#cockpit-hud
    drawHudValue(value, xAnchor, bottom) {
      // DOS: FUN_0000D8F5. Units, tens, then an optional hundreds digit
      // are emitted from HUDS records 0x16..0x1F, right-aligned at x+8.
      let remaining = value | 0;
      let x = xAnchor + 8;
      const units = remaining % 10;
      drawMaskedSprite(this.frame, this.evidence.banks.huds, 0x16 + units, x, bottom, this.hudsLookup, this.spriteCache);
      remaining = Math.floor(remaining / 10);
      x -= 4;
      const tens = remaining % 10;
      drawMaskedSprite(this.frame, this.evidence.banks.huds, 0x16 + tens, x, bottom, this.hudsLookup, this.spriteCache);
      remaining = Math.floor(remaining / 10);
      if (remaining <= 9) {
        x -= 4;
        drawMaskedSprite(this.frame, this.evidence.banks.huds, 0x16 + remaining, x, bottom, this.hudsLookup, this.spriteCache);
      }
    }

    // DOS: FUN_00019352 [00019352-00019391]; record: analysis/functions/browser-attract.md#cockpit-hud
    hudClearance() {
      // DOS: FUN_00019352. This is the positive
      // above-ground difference in the authored terrain byte units.
      const mapIndex = readMapIndex(this.flight.x, this.flight.y);
      const terrainByte = ((2 * this.evidence.height.pixels[mapIndex]) + 1) & 0xff;
      const altitude = this.flight.altitude & 0xff;
      return terrainByte < altitude ? Math.min(0xff, altitude - terrainByte) : 0;
    }

    // DOS: FUN_0000D703 [0000D703-0000D887]; record: analysis/functions/browser-attract.md#cockpit-hud
    drawHudAuthored() {
      // DOS: FUN_0000D703. The shipped executable's HUD option strings
      // at 000267C1 and 000267D2 begin with '}', so both authored families are
      // enabled for this attract milestone.
      drawMaskedSprite(this.frame, this.evidence.banks.huds, 2, 0xa4, 5, this.hudsLookup, this.spriteCache);
      this.drawHeadingWindow();

      const clearance = this.hudClearance();
      drawMaskedSprite(this.frame, this.evidence.banks.huds, 0x15, 0x42, 0x88, this.hudsLookup, this.spriteCache);

      const forward = Math.abs(this.flight.fwd | 0);
      const lateral = Math.abs(this.flight.lat | 0);
      const speed = Math.floor(Math.max(forward, lateral) / 0x20000);
      this.drawHudValue(speed, 0x42, 0x88);

      drawMaskedSprite(this.frame, this.evidence.banks.huds, 4, 0x120, 0x78, this.hudsLookup, this.spriteCache);
      const ladderCount = (clearance >> 2) + 1;
      for (let step = 0; step < ladderCount; step += 1) {
        const targetY = 0x78 - step;
        if (targetY < 0 || targetY >= VIEW_H || 0x120 < 0 || 0x120 >= VIEW_W) continue;
        this.frame[(targetY * VIEW_W) + 0x120] = HUD_SIGHT_GREEN;
      }

      const clearanceValue = Math.max((2 * clearance) - 10, 0);
      this.drawHudValue(clearanceValue, 0x110, 0x7b - ladderCount);
    }

    // DOS: FUN_00025CA2 [00025CA2-00025D31]; record: analysis/functions/browser-attract.md#sight-line
    drawSightLine(targetX, targetY) {
      // DOS: FUN_00025CA2. This preserves the shallow/steep split,
      // denominator (+1), eight-bit fractional accumulator seeded at 0x80,
      // +0x100 quotient bias, and inclusive endpoints. The DOS routine does
      // not accumulate a full 16-bit quotient: it takes AH after the bias and
      // adds that byte to BH, so the browser keeps that exact quantization.
      // Only the framebuffer write is bounded for the browser surface.
      const centerX = 0xa5;
      const centerY = 0x5a;
      let dx = Math.abs(targetX - centerX);
      let dy = Math.abs(targetY - centerY);
      const sx = targetX < centerX ? -1 : 1;
      const sy = targetY < centerY ? -1 : 1;
      let x = centerX;
      let y = centerY;

      if (dx === 0 && dy === 0) {
        this.plotSightPixel(x, y);
        return;
      }
      if (dx >= dy) {
        // DOS: EAX = (dy << 16) / (dx + 1); add 0x100; BL = AH;
        // BH starts at 0x80 and is advanced by BL for each plotted pixel.
        const slopeByte = ((Math.trunc((dy * 0x10000) / (dx + 1)) + 0x100) >>> 8) & 0xff;
        let fraction = 0x80;
        for (let step = 0; step <= dx; step += 1) {
          this.plotSightPixel(x, y);
          x += sx;
          const sum = fraction + slopeByte;
          fraction = sum & 0xff;
          if (sum > 0xff) {
            y += sy;
          }
        }
        return;
      }

      const slopeByte = ((Math.trunc((dx * 0x10000) / (dy + 1)) + 0x100) >>> 8) & 0xff;
      let fraction = 0x80;
      for (let step = 0; step <= dy; step += 1) {
        this.plotSightPixel(x, y);
        y += sy;
        const sum = fraction + slopeByte;
        fraction = sum & 0xff;
        if (sum > 0xff) {
          x += sx;
        }
      }
    }

    // DOS: FUN_00025CA2 [00025CA2-00025D31]; record: analysis/functions/browser-attract.md#sight-line
    plotSightPixel(x, y) {
      // DOS: FUN_00025CA2; record: analysis/functions/browser-attract.md#sight-line
      // Bounds checking replaces
      // DOS page wrapping at the browser surface edge.
      if (x < 0 || x >= VIEW_W || y < 0 || y >= VIEW_H) return;
      this.frame[(y * VIEW_W) + x] = HUD_SIGHT_GREEN;
    }

    // DOS: FUN_0000D857 [0000D857-0000D887]; record: analysis/functions/browser-attract.md#cockpit-hud
    drawDynamicHud() {
      // DOS: FUN_0000D857/00025CA2; record: analysis/functions/browser-attract.md#cockpit-hud
      // Arithmetic shifts are
      // deliberately kept signed before the fixed sight-line offsets.
      const targetX = 0xa5 + (this.flight.lat >> 19);
      const targetY = 0x5a + ((-this.flight.fwd) >> 19);
      drawMaskedSprite(this.frame, this.evidence.banks.huds, 0x21, targetX, targetY, this.hudsLookup, this.spriteCache);
      this.drawSightLine(targetX, targetY);
    }

    // DOS: FUN_00024B17 [00024B17-00024B70]; record: analysis/functions/browser-attract.md#object-pass
    // lateral/depth in two spellings: lateralDos/depthDos are 00024B27-00024B70
    // exactly (each 10.22 delta to the live camera halved BEFORE the Q31 product,
    // [0002085C]/[00020A64]) and are what the threat display and the helicopter
    // test read; lateral/depth are the same transform of the 16.16 render pair
    // the renderer's page search and fan column were written against.
    objectTransform() {
      const sin = this.view_sin;
      const cos = this.view_cos;
      const viewerX = this.view_camera_x;
      const viewerY = this.view_camera_y;
      for (const object of this.objects) {
        if (!object.active) continue;
        const dx = i32(object.x - viewerX);
        const dy = i32(object.y - viewerY);
        // DOS 00024B27/00024B57 halves each 10.22 delta before the Q31
        // multiply. Object positions cross into the renderer as 16.16, so
        // the equivalent conversion there is the post-product arithmetic shift.
        object.lateral = i32((hi32(dx, cos) >> 1) + (hi32(dy, sin) >> 1));
        object.depth = i32((hi32(dx, sin) >> 1) - (hi32(dy, cos) >> 1));
        const halfX = i32(object.dosX - this.view_camera_dos_x) >> 1;     // 00024B27-00024B34
        const halfY = i32(object.dosY - this.view_camera_dos_y) >> 1;     // 00024B36-00024B43
        object.lateralDos = i32(hi32(cos, halfX) + hi32(sin, halfY));     // 00024B45-00024B55, 00024B69
        object.depthDos = i32(hi32(sin, halfX) - hi32(cos, halfY));       // 00024B57-00024B67, 00024B70
      }
    }

    // DOS: FUN_00024B17 [00024B81-00024C09]; record: analysis/functions/browser-attract.md#target-cycle
    // The draw walk's bookkeeping, separated from its pixels. 00024BD0 clears
    // the candidate [00019D18]; for every slot 0x82..1 in the far-to-near
    // order 00024B81-00024BC9 sorts ([00020A64], a selection sort whose ties
    // go to the lower slot) 00024BE1 clears the targetability byte
    // [00021BAB], and an active slot whose depth is not negative calls its
    // draw handler. The handlers that reach 00024C45 (00024E05, 00024FED,
    // 0002514D, and 00024C0A in the external views) store the view bearing
    // [00021CAF] and the targetability tail 00024DA4 may set [00021BAB] and
    // the candidate - the last object in this order to do so wins.
    objectProjectionPass() {
      this.targetDefault = 0;                                    // 00024BD0
      for (const object of this.objectBySlot.values()) object.targetFlag = 0;   // 00024BE1
      const backdrop = buildBackdropDy(this.view_slope, this.view_offset, this.shake.phase);
      const order = this.objects.filter((object) => object.active)
        .sort((left, right) => (right.depthDos - left.depthDos) || (left.slot - right.slot));
      for (const object of order) {
        if (object.depthDos < 0) continue;                       // 00024BF1-00024BF9
        const addr = object.drawAddr;
        const projects = addr === 0x24e05 || addr === 0x24fed || addr === 0x2514d
          || (addr === 0x24c0a && this.view_variant > 5);        // 00024C0A-00024C20
        if (projects) this.objectProjectionEffects(object, backdrop);
      }
    }

    // DOS: FUN_00024C45 [00024C45-00024D9F]; record: analysis/functions/browser-attract.md#target-cycle
    // What 00024C45 leaves behind for the target machinery: past the depth
    // gate (> 0x1FFFFFFF, signed, 00024C45-00024C50) the bearing
    // `~((minor >> 1 ... ) + 1) >> 1` of the aspect block is stored per slot
    // at [00021CAF] (00024CB8-00024CBA) - 000256C8's routine with the live
    // viewpoint minus the object - and then the ring search, the projection
    // page, its 0x01..0xFE gate (00024D78-00024D82) and the fan column
    // (00024D84-00024D9F) decide whether 00024DA4 runs at all.
    objectProjectionEffects(object, backdrop) {
      if (object.depthDos > 0x1fffffff) return;                  // 00024C45-00024C50
      object.viewBearing = this.objectBearingTo({ dosX: this.view_camera_dos_x, dosY: this.view_camera_dos_y },
        object.dosX, object.dosY).bearing;                       // 00024C56-00024CBA
      const page = this.objectFindPage(object);                  // 00024CC0-00024D71
      if (page < 0) return;
      if ((page & 0xff) < 1 || (page & 0xff) > 0xfe) return;     // 00024D78-00024D82
      const fan = this.objectFanColumn(object);                  // 00024D84-00024D9F
      if (!fan) return;
      this.objectMarkTargetable(object, fan.x, backdrop);
    }

    // DOS: FUN_00024C45 [00024DA4-00024E02]; record: analysis/functions/browser-attract.md#target-cycle
    // The targetability test, the tail of the same routine. Only slots up to
    // 0x1E take part (00024DA4-00024DA7). The designator row is
    // ~(backdrop[v - 0x20] + page) - 0x29 and must be in [0, 0xC8)
    // (00024DA9-00024DC4, stored at [00021C2D]); v - 0x2E must be in (3, 0xA0]
    // (00024DCC-00024DDB); and the page row must not be below the horizon the
    // flight view's march archived for the CLIP ring at that column
    // (00024DDD-00024DF4). Then [00021BAB] = v - 0x2E and the candidate
    // [00019D18] is this slot (00024DF6-00024DFC).
    //
    // 00024DB0 reads [v + 0003CB20], the backdrop array biased by 0x20; for v
    // outside 0x20..0xDF that is a neighbouring BSS byte this reference does
    // not carry. It cannot matter: acceptance needs v - 0x2E in (3, 0xA0],
    // i.e. v in 0x32..0xCE, so a v outside the array is rejected here without
    // reading it (the only difference is the unobservable [00021C2D] store).
    objectMarkTargetable(object, v, backdrop) {
      if (object.slot > 0x1e) return;                            // 00024DA4-00024DA7
      const page = object.projectPage & 0xff;                    // [00022366]
      const column = v - 0x20;
      if (column < 0 || column >= TERRAIN_COLS) return;
      let row = (backdrop[column] + page) & 0xff;                // 00024DA9-00024DB6
      row = (~row & 0xff) - 0x29;                                // 00024DBC-00024DBE
      if (row < 0 || row >= 0xc8) return;                        // 00024DC0-00024DC4
      object.designator = row;                                   // 00024DC6
      const target = v - 0x2e;                                   // 00024DCC-00024DD1
      if (target < 0 || target > 0xa0 || target <= 3) return;    // 00024DD3-00024DDB
      const clip = object.projectClipRing;                       // [00022358] = clip ring * 256
      if (clip < 0) return;
      if (page < this.ringHorizon[clip * TERRAIN_COLS + column]) return;   // 00024DDD-00024DF4
      object.targetFlag = target;                                // 00024DF6
      this.targetDefault = object.slot;                          // 00024DFC
    }

    // DOS: FUN_00024C45 [00024C45-00024D73]; record: analysis/functions/browser-attract.md#object-pass
    objectFindPage(object) {
      // 00024C45-00024C50: `cmp [ecx*4 + 00020A64], 0x1FFFFFFF; jg 00024E03`,
      // on the transform's own [00020A64] (12.20, 512 map units); 00024BF1
      // has already skipped a negative one. The ring-search key is that same
      // dword shifted left by three (00024CC0-00024CC7 `shl edi, 3`), which
      // cannot wrap below the gate. This used the render pair's depth (a
      // sixty-fourth of it) with the gate applied AFTER the shift, which
      // dropped every object past 64 map units; the DOS draws them to 512.
      if (object.depthDos < 0 || object.depthDos > 0x1fffffff) {
        object.pageValid = false;
        return -1;
      }
      const depthKey = (object.depthDos << 3) >>> 0;             // 00024CC7
      let clipKey = depthKey;
      if (clipKey >= 0x01800000) clipKey = (clipKey - 0x01800000) >>> 0;
      let ring = -1;
      for (let index = 0; index < this.ringDepthTable.length; index += 1) {
        if ((this.ringDepthTable[index] >>> 0) >= clipKey) {
          ring = index;
          break;
        }
      }
      if (ring < 0) {
        object.pageValid = false;
        return -1;
      }
      // 00024CFB-00024D06: the CLIP ring (the first one at or past the biased
      // key) is stored as [00022358] = ring * 256; 00024DEA indexes the
      // horizon archive with it.
      object.projectClipRing = ring;
      while (ring < this.ringDepthTable.length && (this.ringDepthTable[ring] >>> 0) < depthKey) ring += 1;
      if (ring >= this.ringDepthTable.length) {
        object.pageValid = false;
        return -1;
      }

      // DOS 00024D58 masks the player altitude, adds the object's altitude,
      // and rotates the add carry into the high bit before indexing the 256
      // byte projection page.
      const base = (~(this.view_camera_altitude & 0xfe)) & 0xff;
      const sum = base + (object.altitude & 0xff);
      const altitudeIndex = (((sum > 0xff ? 1 : 0) << 7) | ((sum & 0xff) >>> 1)) & 0xff;
      const page = this.ringPageTable[(ring * 256) + altitudeIndex] | 0;
      object.projectPage = page;
      // 00024D1B leaves `ebx` as the ring's byte offset and 00024D28 reads
      // [ebx + 00019EE4] with it - the B table, one lateral increment per
      // ring. HIGH.DTL's five 250-entry tables load consecutively and the
      // ring depth table the search walks is 0001AE84, so
      // 0001AE84 - 4 * 0x3E8 = 00019EE4 is table 0. Both the sprite scale and
      // the fan column divide by B[ring], not by the object's own depth.
      object.projectRing = ring;
      object.pageValid = true;
      return page;
    }

    // DOS: FUN_00024C45/0002514D [00024C45-00024D71 / 0002514D-000253CD]; record: analysis/functions/browser-attract.md#object-pass
    objectAspect(object, bank, page, bias) {
      const model = modelRecord(bank, this.spriteCache);
      if (!model) return null;
      let dy = i32(this.view_camera_y - object.y);
      let ySign = 0;
      let yMagnitude = dy;
      if (dy < 0) {
        yMagnitude = (~dy) | 0;
        ySign = 1;
      }
      let dx = i32(this.view_camera_x - object.x);
      let xSign = 0;
      let xMagnitude = dx;
      if (dx < 0) {
        xMagnitude = (~dx) | 0;
        xSign = 1;
      }
      // 00024C7D-00024CA4. This is instruction-for-instruction the block
      // 000256C8 runs - see objectBearingTo, which is certified against 153
      // captured DOS frames - with the other origin and the other direction:
      // 00024C58/00024C71 take the LIVE viewpoint minus the object, where
      // 000256C8 takes the object minus a stored origin.
      //
      // It carried the same four errors as that routine did. 00024C7D's
      // `shld` builds (ysign << 1) | xsign and 00024C81's `shl bl, 1` doubles
      // it, so the index steps in twos; 00024C85's `ja` skips the increment
      // when |dx| IS greater, which is the opposite of the condition used
      // here; 00024C9D XORs into bl alone, and the bits above it still reach
      // 00024CA4's shift; and 00024C9B's quotient is unclamped, indexing the
      // whole 2048-byte correction table.
      let index = ((ySign << 1) | xSign) << 1;
      let edi = yMagnitude;                             // 00024C6A
      let ebp = xMagnitude;                             // 00024C7B
      if (!(ebp > edi)) {                               // 00024C83/00024C85
        index += 1;                                     // 00024C87
        const swap = edi; edi = ebp; ebp = swap;        // 00024C89
      }
      let bearingBase = OBJECT_OCTANT_TABLE[index] >>> 0;   // 00024C8B
      const ratioDenominator = ebp >>> 10;                  // 00024C92
      if (ratioDenominator !== 0) {                         // 00024C95
        const ratio = ((edi >>> 0) / ratioDenominator) | 0; // 00024C9B
        bearingBase = ((bearingBase & ~0xff)
          | ((bearingBase ^ OBJECT_BEARING_CORRECTION[ratio]) & 0xff)) >>> 0;
      }
      // 00024CA3/00024CA4 on the whole word; 00024CA6 then takes bl. The
      // original also keeps ~bl at [ecx + 00021CAF] for the target panel,
      // which this milestone does not carry.
      const bearing = ((bearingBase + 1) >>> 1) & 0xff;
      const step = (((bearing + (object.heading & 0xff) + 4) & 0xff) >>> 3) + (bias | 0);
      const azimuth = model.azimuth[step & 0x1f] | 0;
      const rawFrame = azimuth + (model.elevation[(page >>> 4) & 0x1f] | 0);
      return {
        index: rawFrame & 0x7f,
        mirror: (rawFrame & 0x80) !== 0,
      };
    }

    // 00024D21-00024D9F. The sprite's 8.8 scale and its fan column, both
    // divided by the RING's lateral increment `B[ring]` rather than by the
    // object's own depth. Returns null where the original jumps to 00024E03,
    // which pops its caller's return address: an off-screen fan column is a
    // cull of the whole draw, not a skipped step.
    // DOS: FUN_00024C45 [00024D21-00024D9F]; record: analysis/functions/browser-attract.md#object-pass
    objectFanColumn(object) {
      const ring = object.projectRing | 0;
      const bTable = this.evidence.detail.tables[0];
      if (ring < 0 || ring >= bTable.length) return null;
      const b = bTable[ring] | 0;
      if (b === 0) return null;

      // 00024D21-00024D37: 2^27 / B, saturated at 127. The ramp at
      // 0x1D7EC/0x1DBEC is built at startup and entry 127-index is index+1
      // bytes summing to 64, which (index + 1) * 4 reproduces in 8.8.
      let scaleIndex = Math.floor(0x8000000 / (b >>> 0));
      if (scaleIndex > 127) scaleIndex = 127;
      const scale8 = (scaleIndex + 1) * 4;

      // 00024D87/00024D8A: the divisor is B >> 3, and a zero is a cull.
      const divisor = b >> 3;
      if (divisor === 0) return null;
      // 00024D84's dividend is `esi`, reloaded from [0002085C] at 00024D46 -
      // the lateral AS STORED, 12.20 (object.lateralDos, 00024B69). 00024CC7's
      // `shl edi,3` belongs to the ring search's key alone and must not be
      // applied here as well. The render pair's `lateral` is a sixty-fourth of
      // it, and `lateral * 16` - what stood here - is a quarter of it: on the
      // captured frame of slot 26 (lateral 3291747, B = 5825923) it gave
      // column 129 where the original's targetability byte 86 says 132.
      const v = Math.trunc(object.lateralDos / divisor) + 0x80;
      // 00024D93/00024D9A: outside [5, 0xF5) is not on screen.
      if (v >= 0xf5 || v < 5) return null;
      // 00024D9F stores v at [00022365] and 0002543A adds that byte to the
      // blit's destination x, so v is where the sprite stands.
      return { scale8, x: v };
    }

    // DOS: FUN_0002519D/00025880 [0002519D-00025DBC]; record: analysis/functions/browser-attract.md#object-pass. The 0002519D path
    // draws the non-3D BULL/CHAF/BOOM banks with the same projected origin as
    // the model blitter, but selects its authored animation frame directly.
    drawDynamicBank(object, page) {
      const bank = object.modelA;
      const lookup = object.lookupA;
      if (!bank || !lookup || !object.pageValid || page < 0) return;
      if (modelRecord(bank, this.spriteCache)) {
        this.drawObjectModel(object, bank, lookup, page, 0);
        return;
      }
      // 000251AE-000251B4: the frame is the slot's sprite byte [000219A3],
      // 1-based (BULL keeps 1, CHAF cycles 1..8, BOOM counts 1..0x13).
      const index = object.sprite;
      if (index < 1 || index > bank.payload.count) return;
      const fan = this.objectFanColumn(object);
      if (!fan) return;
      const bottom = PAGE_ANCHOR - page;
      drawScaledMaskedSprite(this.frame, bank, index, fan.x, bottom, lookup, this.spriteCache, fan.scale8, false);
    }

    // DOS: FUN_0002514D/000253CD [0002514D-000253CD]; record: analysis/functions/browser-attract.md#object-pass
    drawObjectModel(object, bank, lookup, page, bias = 0) {
      if (!bank || !lookup || !object.pageValid || page < 0) return;
      const aspect = this.objectAspect(object, bank, page, bias);
      if (!aspect || aspect.index < 1 || aspect.index > bank.payload.count) return;
      const fan = this.objectFanColumn(object);
      if (!fan) return;
      const bottom = PAGE_ANCHOR - page;
      drawScaledMaskedSprite(this.frame, bank, aspect.index, fan.x, bottom, lookup, this.spriteCache, fan.scale8, aspect.mirror);
    }

    // DOS: FUN_0002514D [0002514D-000253CD]; record: analysis/functions/browser-attract.md#object-pass
    drawObjectSingle(object, page) {
      this.drawObjectModel(object, object.modelA, object.lookupA, page, 0);
    }

    // DOS: FUN_00024E05/00024FED [00024E05-0002503A / 00024FED-0002514C]; record: analysis/functions/browser-attract.md#object-pass
    drawObjectPair(object, page) {
      if (!object.modelA && !object.modelB) return;
      if (page <= 0x82) {
        this.drawObjectModel(object, object.modelA, object.lookupA, page, 0);
        const bias = (((-object.variant + 4) & 0xff) >>> 3);
        this.drawObjectModel(object, object.modelB, object.lookupB, page, bias);
      } else {
        const bias = (((object.variant + 4) & 0xff) >>> 3);
        this.drawObjectModel(object, object.modelB, object.lookupB, page, bias);
        this.drawObjectModel(object, object.modelA, object.lookupA, page, 0);
      }
    }

    // DOS: FUN_00024BDA/00024C45 [00024BDA-00024C09]; record: analysis/functions/browser-attract.md#object-pass
    objectDraw(object) {
      const page = this.objectFindPage(object);
      if (page < 0) return;
      if (object.drawAddr === 0x2519d) {
        this.drawDynamicBank(object, page);
      } else if (object.drawAddr === 0x2514d) {
        this.drawObjectSingle(object, page);
      } else if (object.drawAddr === 0x24c0a) {
        // DOS 00024C0A is gated by the external-view phase. The fallback
        // slot-31 object has no model when its mission has no type-0 record,
        // but the gate remains semantically live for authored type-0 data.
        if (this.view_variant > 5) this.drawObjectPair(object, page);
      } else {
        this.drawObjectPair(object, page);
      }
    }

    // DOS: FUN_000234A4 [000234A4-000234D3]; record: analysis/functions/browser-attract.md#frame-driver
    updateObjectPass() {
      // DOS 000234A4 updates slots 130..1, then 00024B17 transforms all
      // active slots, selection-sorts depth, and draws slot 130..1 far-to-near.
      // The two object-pass flags are frame-local in DOS (000234A4/000234AB
      // clear them); the flight tail consumes the values after this pass.
      // The walk looks the slot up when it reaches it, as the loop does: a
      // slot a handler has just filled below the current one runs this pass.
      this.threatChaff = 0;
      this.threatBull = 0;
      for (let slot = 0x82; slot >= 1; slot -= 1) {
        const object = this.objectBySlot.get(slot);
        if (object) this.updateObjectState(object);
      }
      this.objectTransform();
      this.objectProjectionPass();
      const order = this.objects.filter((object) => object.active).slice();
      const sorted = [];
      while (order.length) {
        let best = 0;
        for (let index = 1; index < order.length; index += 1) {
          if (order[index].depth > order[best].depth) best = index;
        }
        sorted.push(order.splice(best, 1)[0]);
      }
      for (const object of sorted) {
        // 00024B17's walk tests two things: the slot is active, and the depth
        // is not behind the viewer. The 992-unit range cull that stood here
        // was invented. The original's range cull is 00024C45's 0x1FFFFFFF -
        // 512 units - which objectFindPage already applies, and it is
        // structural rather than chosen: `depth << 3` wraps at exactly 512,
        // so past it the table-4 search returns a near ring for a far object.
        if (object.depth < 0) continue;
        this.objectDraw(object);
      }
    }

    // DOS: FUN_0000D3C0 [0000D3C0-0000D8F5]; record: analysis/functions/browser-attract.md#frame-driver
    drawTerrainStage() {
      this.buildViewBasis();
      this.renderClear();
      this.drawTerrain();
      this.updateObjectPass();

      // DOS: FUN_00019681; record: analysis/functions/browser-attract.md#terrain-renderer
      // Keep only the pre-console/HUD render surface for the next frame.
      this.terrainSurface.set(this.frame);
    }

    // DOS: FUN_00025880/0000D703/0000D857 [00025880-00025DBC / 0000D703-0000D887]; record: analysis/functions/browser-attract.md#frame-driver
    // Cockpit composition is
    // after the replay/flight phase in the traced frame driver.
    drawCockpitStage() {
      this.drawConsole();
      if (this.view_variant !== 1) return;
      this.updateThreatDisplay();
      this.drawMfdStage();
      this.drawFixedInstruments();
      this.drawHudAuthored();
      this.drawDynamicHud();
    }

    // N/A - platform replacement; record: analysis/functions/browser-attract.md#frame-driver. Initial browser presentation seam. It renders the same two DOS
    // phases without consuming a replay record.
    drawDemo() {
      this.prepareFlightFrame();
      this.drawTerrainStage();
      this.drawCockpitStage();
    }

    // DOS: FUN_00018F94 [00018EE3-0001959E]; record: analysis/functions/browser-attract.md#player-damage-chain
    // The explicit state object the damage functions of dos-damage.js work on,
    // as live views of this runtime's fields (DOS address in each comment).
    // Created once; the fields are read and written where they live, so the
    // pure functions see exactly the tick's state.
    damageView() {
      if (this.damageStateView) return this.damageStateView;
      const runtime = this;
      this.damageStateView = {
        get cells() { return runtime.hull.cells; },                                   // [00019E38..3F]
        get hullPoints() { return runtime.hull.points; },                             // [00019E40]
        set hullPoints(value) { runtime.hull.points = i32(value); },
        get deathCue() { return runtime.hull.down; },                                 // [00019E49]
        set deathCue(value) { runtime.hull.down = value & 0xff; },
        get deathTimer() { return runtime.hull.timer; },                              // [00019E48]
        set deathTimer(value) { runtime.hull.timer = value & 0xff; },
        get axis1() { return runtime.flight.axis1; },                                 // [00019DC8]
        set axis1(value) { runtime.flight.axis1 = i32(value); },
        get axis2() { return runtime.flight.axis2; },                                 // [00019DCC]
        set axis2(value) { runtime.flight.axis2 = i32(value); },
        get collective() { return runtime.flight.collective; },                       // [00019D82]
        set collective(value) { runtime.flight.collective = value & 0xff; },
        get altitude() { return runtime.flight.altitude; },                           // [00019DFC]
        set altitude(value) { runtime.flight.altitude = value & 0xff; },
        get previousAltitude() { return runtime.flight.previousAltitude; },           // [00019DF6]
        get maxSpeed() { return runtime.flight.maxSpeed; },                           // [00019CCC]
        set maxSpeed(value) { runtime.flight.maxSpeed = i32(value); },
        get shakeCountdown() { return runtime.shake.countdown; },                     // [00019DC0]
        set shakeCountdown(value) { runtime.shake.countdown = value >>> 0; },
        get viewVariant() { return runtime.view_variant; },                           // [00019D86]
        get crashDrop() { return runtime.crashDrop; },                                // [00019DC4]
        set crashDrop(value) { runtime.crashDrop = value >>> 0; },
        get rng() { return runtime.shake.rng; },                                      // [00019DB8]
        set rng(value) { runtime.shake.rng = value >>> 0; },
        get x() { return runtime.flight.dosX; },                                      // [00019CD4]
        set x(value) { runtime.flight.dosX = i32(value); runtime.flight.x = i32(value >> 6); },
        get y() { return runtime.flight.dosY; },                                      // [00019CD8]
        set y(value) { runtime.flight.dosY = i32(value); runtime.flight.y = i32(value >> 6); },
        get frameX() { return runtime.flight.frameDosX; },                            // [00019CDC]
        get frameY() { return runtime.flight.frameDosY; },                            // [00019CE0]
        get fwd() { return runtime.flight.fwd; },                                     // [00019CC8]
        set fwd(value) { runtime.flight.fwd = i32(value); },
        get lat() { return runtime.flight.lat; },                                     // [00019CD0]
        set lat(value) { runtime.flight.lat = i32(value); },
        get torque() { return runtime.flight.torque; },                               // [00019D84]
        set torque(value) { runtime.flight.torque = value & 0xff; },
      };
      return this.damageStateView;
    }

    // DOS: FUN_00018F94 [00018EE3-00018F93]; record: analysis/functions/browser-attract.md#player-damage-chain
    // Carry out what the death block asked of the rest of the game: the end of
    // the flight (00018EF6 je 0002873D: the request is recorded and the tick
    // stops, as for the fuel branch), the chase view (00018F72 -> 00019820,
    // the key-7 case) and the wreck puff from the fixed object (00018F8F ->
    // 000227BF with ecx = 0x1F). Sound requests are not carried.
    applyDamageRequests(requests) {
      if (requests.missionEnd) {
        this.flight.missionEnd = 1;
        this.queueEvent("mission-end:death");
        return true;
      }
      if (requests.chaseView) this.applyViewKey(0x07);
      if (requests.wreckFromSlot) {
        const parent = this.objectBySlot.get(requests.wreckFromSlot);
        if (parent) this.spawnWreckage(parent);
      }
      return false;
    }

    // DOS: FUN_00018F94 [00018F94-0001959E]; record: analysis/functions/browser-attract.md#flight-integration
    flightTick() {
      // DOS: FUN_00018F94; record: analysis/functions/browser-attract.md#flight-integration
      // The attract path uses authored replay axes only.
      const flight = this.flight;
      const damage = this.damageView();
      // 00018EE3-00018F93: a wreck is flown by nobody; 00018F94-00018FE2: a
      // damaged engine sinks and the T gauge is computed. The tick ends at once
      // when the wreck's countdown reaches zero (00018EF6 je 0002873D).
      if (this.applyDamageRequests(DAMAGE.deathBlock(damage))) return;
      DAMAGE.engineDamage(damage);
      DAMAGE.torqueGauge(damage);
      let shift = flight.collective > 0x10 ? 5 : 3;
      flight.fwd = damp(flight.fwd, shift);
      flight.lat = damp(flight.lat, shift);
      shift -= 1;
      flight.turn = damp(flight.turn, shift);
      flight.roll = damp(flight.roll, shift);
      shift -= 1;
      flight.pitch = damp(flight.pitch, shift);

      // 000190AB-000190B4: a damaged tail rotor adds a constant yaw before the clamp.
      flight.turn = clamp(i32(flight.turn + (flight.axis1 << 14) + DAMAGE.tailRotorYaw(damage)), -0x04000000, 0x04000000) | 0;
      flight.roll = clamp(i32(flight.roll + ((flight.axis1 + 8) >> 4)), -133, 133) | 0;
      flight.lat = clamp(i32(flight.lat + (flight.axis1 << 12)), -0x00800000, 0x00800000) | 0;
      flight.pitch = clamp(i32(flight.pitch + ((16 - flight.axis2) >> 5)), -33, 33) | 0;
      flight.fwd = clamp(i32(flight.fwd - (flight.axis2 << 11)), -(flight.maxSpeed >> 1), flight.maxSpeed) | 0;

      // 000191B6-000192EE sit between the control inputs above and the
      // terrain follow below: the weapon dispatch, the target cycle, the
      // rudder keys and the lock loss all see the position, heading and pitch
      // of the previous tick.
      this.weaponDispatch();
      this.targetCycle();
      this.rudderAndLockLoss();

      // 000192EE-0001934F, the collision test against the thirty mission
      // objects (ComancheDamage.objectCollision), is NOT entered here: it is
      // transcribed and proved in dos-damage.js, but this reference's mobile
      // objects (state 00023F60 and 00023CF0) are not DOS-exact in position -
      // they take the wall-clock RNG - and with the test wired DEMO2 crashes
      // into the browser's slot-27 Hokum at tick 280, where the captured DOS
      // flight (work/replay_dos/flight-dos.json) flies on uninterrupted. The
      // path stays dormant until the object model is exact
      // (analysis/functions/browser-attract.md#player-damage-chain).
      const mapIndex = readMapIndex(flight.x, flight.y);
      const terrainByte = ((2 * this.evidence.height.pixels[mapIndex]) + 1) & 0xff;
      const altitude = flight.altitude & 0xff;
      const difference = (terrainByte - altitude) & 0xff;
      if (terrainByte >= altitude) {
        if (difference > 2) {
          flight.crashes += 1;
          DAMAGE.crashResponse(damage);                        // 0001937E ja 00019424
        } else {
          flight.altitude = (flight.altitude + difference) & 0xff;
        }
      } else {
        const clearance = (-difference) & 0xff;
        if (clearance <= 6 && flight.collective <= 6) {
          flight.turn = 0;
          flight.fwd = 0;
          flight.lat = 0;
          flight.roll = 0;
          flight.pitch = 0;
        } else {
          const gap = (clearance - flight.collective) & 0xff;
          if (gap === 0) {
            // The original leaves the altitude unchanged at the target.
          } else if (clearance >= flight.collective) {
            const sink = (gap >> 4) + 4;
            flight.altitude = Math.max(0, flight.altitude - sink);
          } else {
            const climb = (((-gap) & 0xff) >> 4) + 3;
            flight.altitude = Math.min(0xff, flight.altitude + climb);
          }
        }
      }

      const sum = flight.altitude + flight.previousAltitude;
      flight.altitude = ((sum >> 1) | ((sum & 0x100) ? 0x80 : 0)) & 0xff;
      flight.angle = (flight.angle + flight.turn) >>> 0;
      const angleIndex = (flight.angle >>> 23) & 0x1ff;
      const sin = SINE_Q31[angleIndex];
      const cos = SINE_Q31[angleIndex + 128];
      flight.pubSin = sin;
      flight.pubCos = cos;
      // DOS flight velocities and high-dword products remain 10.22. Convert
      // each authored displacement to the browser's 16.16 map surface only
      // at the final position store.
      // Preserve the DOS 10.22 accumulator through all four terms. Only the
      // final position crosses to the browser's 16.16 surface coordinate.
      flight.dosY = i32(flight.dosY - hi32(flight.fwd, cos));
      flight.dosX = i32(flight.dosX + hi32(flight.fwd, sin));
      flight.dosX = i32(flight.dosX + hi32(flight.lat, cos));
      flight.dosY = i32(flight.dosY + hi32(flight.lat, sin));
      flight.x = i32(flight.dosX >> 6);
      flight.y = i32(flight.dosY >> 6);
    }

    // N/A - platform replacement; record: analysis/functions/browser-attract.md#frame-driver
    present() {
      // DOS 00001DF1-00001DFF applies fine pixel panning and 00015BBC-00015BC2
      // applies the phase-specific CRTC start offset. The browser's target
      // surface has no DOS page margins, so the recovered displacement is
      // applied to the composed RGB565 crop and the newly exposed edge is
      // cleared. This is a target presentation adaptation; it keeps the
      // recovered replay and timer state running without claiming full VGA
      // page parity.
      const data = this.imageData.data;
      for (let index = 0; index < this.frame.length; index += 1) rgb565ToRgba(this.frame[index], data, index * 4);
      this.surfaceContext.putImageData(this.imageData, 0, 0);
      this.context.fillStyle = "#000";
      this.context.fillRect(0, 0, this.canvas.width, this.canvas.height);
      this.context.imageSmoothingEnabled = false;
      const phase = this.shake.phase & 3;
      const pixelPan = phase * 2;
      const crtcOffset = DOS_SHAKE_CRTC_OFFSETS[phase];
      const rowPan = Math.round(crtcOffset / DOS_CRTC_ROW_STRIDE);
      this.context.drawImage(this.surfaceCanvas, -pixelPan, -rowPan,
        this.canvas.width, this.canvas.height);
    }

    // DOS: FUN_00018C29/00019A2D [entries 00018C29,00019A2D]; record: analysis/functions/browser-attract.md#demo-replay
    currentRecord() {
      return this.demo && this.demoCursor < this.demo.records.length ? this.demo.records[this.demoCursor] : null;
    }
  }

  globalThis.ComancheRuntime = {
    shakeTimerTick,
    advanceShake200Hz,
    buildBackdropDy,
    VIEW_W,
    VIEW_H,
    DOS_SCALE: 4,
    // Target artefact; record: analysis/functions/browser-attract.md#browser-host
    create(options) {
      return new AttractRuntime(options);
    },
  };
})();
