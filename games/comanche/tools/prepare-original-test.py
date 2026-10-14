#!/usr/bin/env python3
"""Prepare the selected terrain maps for the Falcon build.

The authoritative pair is the original Comanche D1/C1 Kyle DTA family, because
that is what src/resources.s opens at runtime. Everything this script emits -
the colour palette above all - is interpreted against the map the Falcon
actually loads, so the generator and the runtime loader must agree on the
source and on the colour index space.
"""

from __future__ import annotations

import re
import os
import struct
import sys
from pathlib import Path


MAP_SOURCE_SIZE = 1024
MAP_BYTES = MAP_SOURCE_SIZE * MAP_SOURCE_SIZE
MAGIC = b"Kyle DTA"
# Recorded in the generated output so a build always states which asset family
# its palette and maps describe.
SOURCE_ORIGINAL = 1


def decode_dta(path: Path) -> bytes:
    data = path.read_bytes()
    if data[:8] != MAGIC:
        raise ValueError(f"{path}: missing Kyle DTA signature")

    x_max, y_max, screen_width, screen_height = struct.unpack_from("<4H", data, 8)
    if (x_max, y_max) != (1023, 1023):
        raise ValueError(
            f"{path}: expected a 1024x1024 map, got {x_max + 1}x{y_max + 1}"
        )
    if (screen_width, screen_height) != (1024, 768):
        raise ValueError(
            f"{path}: unexpected display fields {screen_width}x{screen_height}"
        )

    decoded = bytearray()
    # The Kyle header is 128 bytes in the original resource reader. Starting
    # at 16 consumes the reserved header as terrain and creates a plausible
    # but shifted map, which is not the DOS map.
    pos = 128
    while pos < len(data) and len(decoded) < MAP_BYTES:
        token = data[pos]
        pos += 1
        if token & 0xC0 == 0xC0:
            count = token & 0x3F
            if count == 0 or pos >= len(data):
                raise ValueError(f"{path}: invalid PCX RLE token at 0x{pos - 1:x}")
            decoded.extend([data[pos]] * count)
            pos += 1
        else:
            decoded.append(token)

    if len(decoded) < MAP_BYTES:
        raise ValueError(
            f"{path}: decoded only {len(decoded)} bytes, expected {MAP_BYTES}"
        )
    return bytes(decoded[:MAP_BYTES])


# Renderer tables. They live here because they are build-time data derived
# from the same constants as the maps, and keeping them beside the map keeps
# one generator authoritative for everything the terrain pass reads.
SIN_ENTRIES = 256
SIN_EXTRA = 64          # so cos(a) is sin_table[a + 64] with no wrap test
SIN_ONE = 256           # 8.8 fixed point
ORIGINAL_FLAT = (Path(__file__).resolve().parent.parent
                 / "re/unpacked/comanche-flat32.bin")
OBJECT_OCTANT_BASE = 0x22385
OBJECT_CORRECTION_BASE = 0x223A5
# 00007D31's `add eax, [ebx*4 + 00019D94]`: the per-variant view-angle offset
# 00007D25 adds to the flight angle. Nine dwords, one per view variant, and
# they are the look directions - 0, -90, +90 and 180 degrees for variants
# 1..4, zero for the rest. Read out of the RUNNING game at variants 1, 6 and 7
# on 2026-09-01 and identical to these image bytes, so the shipped values are
# the runtime values here.
VIEW_ANGLE_OFFSET_BASE = 0x19D94
SPRITE_RAMP_OFFSETS_BASE = 0x1D7EC     # 128 dwords, read at 000253D2
SPRITE_RAMP_POOL_BASE = 0x1DBEC        # 000253D9; ramp r is 128 - r bytes
SPRITE_RAMP_POOL_BYTES = 8256 + 512    # 128*129/2, plus what a tall sprite reads past it
VIEW_VARIANT_COUNT = 9
SINE_Q31_BASE = 0x32120


def load_original_flat() -> bytes:
    """Return the unpacked DOS flat image or stop the build.

    These tables are executable behaviour, not optional artwork. A generated
    sine approximation, zero-width font, or empty menu changes the program
    while still producing a plausible binary, so the original image is a hard
    build input for the original path.
    """
    if not ORIGINAL_FLAT.is_file():
        raise SystemExit(
            f"missing {ORIGINAL_FLAT}: unpacked COMANCHE flat image is "
            "required to generate DOS tables"
        )
    return ORIGINAL_FLAT.read_bytes()
# The DSP kernel's schedule, read from src/dsp/proto.inc rather than
# duplicated: objects are placed through these tables while either path
# renders the terrain, so the schedule must be the kernel's or objects
# detach from the ground - and a hardcoded copy here is exactly how the two
# would drift. Three tiers out to the original's range.
def _proto_const(name: str) -> int:
    text = (Path(__file__).resolve().parent.parent
            / "src/dsp/proto.inc").read_text()
    m = re.search(rf"^{name}\s+EQU\s+(\S+)", text, re.M)
    if not m:
        raise SystemExit(f"{name} not found in src/dsp/proto.inc")
    return int(m.group(1))


DEPTH_NEAR_SAMPLES = _proto_const("MARCH_NEAR_STEPS")
DEPTH_FAR_SAMPLES = _proto_const("MARCH_FAR_STEPS")
DEPTH_FAR2_SAMPLES = _proto_const("MARCH_FAR2_STEPS")
DEPTH_SAMPLES = DEPTH_NEAR_SAMPLES + DEPTH_FAR_SAMPLES + DEPTH_FAR2_SAMPLES
DEPTH_NEAR_STEP = 1
DEPTH_FAR_STEP = 1 << _proto_const("TILE_FAR_SHIFT")
DEPTH_FAR2_STEP = 1 << _proto_const("TILE_FAR2_SHIFT")
# Projection scale. Read from src/inc/comanche.s rather than duplicated here:
# invz_table and src/object.s's object placement are the same projection, and a
# second copy of the number would let the terrain and the objects standing on it
# drift apart silently.
def _header_const(name: str) -> int:
    header = Path(__file__).resolve().parent.parent / "src" / "inc" / "comanche.s"
    for line in header.read_text().splitlines():
        m = re.match(rf"\s*{name}\s*=\s*(\d+)", line)
        if m:
            return int(m.group(1))
    raise SystemExit(f"{name} not found in src/inc/comanche.s")


def _proj_scale() -> int:
    return _header_const("PROJ_SCALE")


PROJ_SCALE = _proj_scale()
SCREEN_HORIZON = _header_const("SCREEN_HORIZON")
SCREEN_HEIGHT = _header_const("SCREEN_HEIGHT")

# The original's projection is not a constant, it is two tables in the .DTL
# file, and this reads them. build_projection_tables at DOS 00015AD9 builds one
# 256-byte page per depth step with
#
#     row = clamp((k - 128) * slope_i + bias_i, 0, 255)   in 8.8
#     slope_i = high32(dtl2[i] * [00019CEC])
#     bias_i  = dtl3[i]
#
# and the renderers step through the pages with `inc word ptr [00019EDD]`.
#
# Two relations hold across all 250 steps of HIGH.DTL (to within per-entry
# rounding) and are what make the tables usable at this port's own depth
# schedule rather than the original's: dtl4 is the cumulative depth,
# dtl0[i]/z_i is 1/100 - the sideways step per column - and
# dtl2[i] * z_i / 2**32 is 819200.
#
# The page rows land on the screen 1:1 and upside down, and the transfer says
# by how much. sub_00006FEF walks the 256x256 surface and the VGA page in one
# loop: source [00019E70] + 0x2011 stepping `inc dh`, destination [000014C4] +
# 0x39FA stepping `sub 0x52`, 0xB6 times. That is surface row 32 to VGA row
# 0x39FA/82 = 181, 182 rows, the source row rising as the destination row
# falls, so
#
#     screen row = 213 - page row
#
# and the terrain viewport is VGA rows 0..181 of the 328x240 mode. The resting
# CRTC start is zero - entry 0 of the shake table at 00015B60 - so page row 0
# is screen row 0 and the mapping is absolute, not relative to a scrolled page.
#
# This replaces an anchor of 198 taken from the 199-entry scanline table at
# 0002D7F0, which describes a 192-pitch surface nothing in the listing reads
# and is not the surface the emitter writes (its `inc ch` is a 256 stride).
# The 15 rows between them are why the horizon sat high: 198 was cross-checked
# against the nearest ring's bias landing on CONSOL1S's windshield bottom, but
# that is a coincidence with no mechanism behind it - the near rows are simply
# behind the panel, which is what a cockpit does.
# high.dtl's declared ring count. The shipped install runs MEDIUM - 00026240
# loads medium.dtl when the detail byte [00025DD4] is '1', and two QMP captures
# of the attract flight read the resulting count [0x19EE0] = 180 - but this
# port is built for high detail by project decision, so it generates from
# high.dtl and src/dtl.s caches '0'. High is the original's own setting, not an
# invention: 0002622C selects it from the same byte.
#
# The consequence is that an oracle still set to medium is NOT comparable. Its
# ring schedule, projection pages and per-ring B all differ, so certify-marcher
# and certify-replay-flight measure a configuration difference rather than a
# port fault. Set the install's detail byte to '0' before capturing.
DTL_STEPS = 250
# HIGH.DTL's count, and what every generated ring array is SIZED for.
# The Detail menu selects a file at runtime (src/dtl.s), so the arrays
# have to hold the largest of the three even when the build generates
# the medium one into them. The live count is the word `ring_steps`,
# not RING_STEPS - that constant is now the bound, not the schedule.
DTL_MAX_STEPS = 250
DTL_ANCHOR = 213                # screen row of page row 0, the viewport bottom
DTL_FIXED = 1 << 22             # its positions are 10.22


def load_dtl():
    """Return (z in map units, bias) for every original depth step."""
    path = (Path(__file__).resolve().parent.parent
            / "assets/extracted/comanche_hdd/HIGH.DTL")
    if not path.is_file():
        raise SystemExit(f"missing original depth table: {path}")
    raw = path.read_bytes()
    if len(raw) < 4004 + DTL_STEPS * 4:
        raise SystemExit(f"{path}: truncated original depth table")
    count = struct.unpack_from("<I", raw, 0)[0]
    if count != DTL_STEPS:
        raise SystemExit(f"{path}: expected {DTL_STEPS} depth records, got {count}")
    # The original's own fixed offsets, not the file's table boundaries -
    # 0x19EE4, 0x1A2CC, 0x1A6B4, 0x1AA9C and 0x1AE84 against a file loaded at
    # 0x19EE0. They coincide with the boundaries only for a 250-entry file.
    table = [list(struct.unpack_from(f"<{DTL_STEPS}I", raw, off))
             for off in (4, 1004, 2004, 3004, 4004)]
    z, bias = [], table[3]
    for i in range(min(count, DTL_STEPS)):
        # Table 4 is the file's running total of the raw table-1 A words, and
        # the marcher's per-ring step is high32(A * sinQ31) - A/2 map units -
        # so a raw total counts world distance at 2^23 per unit, not the
        # 10.22 the increments are written in. Reading it as 10.22 halved
        # every world depth and placed objects against rings the terrain
        # draws twice as far away.
        z.append(table[4][i] / (1 << 23))
    return list(zip(z, bias))


def depth_step(i: int) -> int:
    if i < DEPTH_NEAR_SAMPLES:
        return DEPTH_NEAR_STEP
    if i < DEPTH_NEAR_SAMPLES + DEPTH_FAR_SAMPLES:
        return DEPTH_FAR_STEP
    return DEPTH_FAR2_STEP


def dtl_horizon(dtl, sample: int) -> int:
    """The horizon row for this port's depth sample, at the original's 1:1
    rows: screen row = DTL_ANCHOR - floor(bias/256), the floor because the DOS
    page build takes the high byte of the clamped sum."""
    z = 0
    for i in range(sample + 1):
        z += depth_step(i)
    bias = dtl[-1][1]
    for zi, bi in dtl:
        if zi >= z:
            bias = bi
            break
    return DTL_ANCHOR - (bias >> 8)



def emit_sine_q31(lines: list[str]) -> None:
    """The DOS Q31 sine table, 640 dwords: one revolution in 512 steps plus a
    128-entry quarter-wave overhang so the cosine index never wraps. Extracted
    verbatim from the unpacked image at 00032120 when it is present - the
    flight integration's hi32 multiplies must see the original's exact words
    or a replayed demo drifts."""
    raw = load_original_flat()
    end = SINE_Q31_BASE + 640 * 4
    if len(raw) < end:
        raise SystemExit(
            f"{ORIGINAL_FLAT}: DOS sine table at 00032120 is truncated"
        )
    vals = list(struct.unpack_from("<640i", raw, SINE_Q31_BASE))
    source = "verbatim from the image at 00032120"
    lines.append("")
    lines.append("; Q31 sine, 512 steps per revolution, cosine at +128 entries,")
    lines.append(f"; {source}.")
    lines.append("        even")
    lines.append("        global  sine_q31")
    lines.append("sine_q31")
    for pos in range(0, 640, 4):
        chunk = ",".join(str(v) for v in vals[pos:pos + 4])
        lines.append("        dc.l    " + chunk)


MENU_FONT_BASE = 0x27276


def emit_menu_font(lines: list[str]) -> None:
    """The `KF4b` proportional font at 00027276, the one the menu and briefing
    text engine at 00027034 draws from.

    Self-describing: `"KF4b"`, height 10 at +4, a 128-byte width table at +8,
    a 128-word offset table at +0x88 whose entries are relative to the block
    base, and glyph data from +0x188 at four bytes per column. Each column is
    one 32-bit mask read from bit 0 upward, two bits per row - the low bit of
    the pair paints the ink colour and the high bit the shadow, which is what
    gives every glyph its one-pixel drop shadow.

    Emitted rather than committed: the block is 2,844 bytes of the original
    executable, so it is generated the same way the Q31 sine table is. Without
    the unpacked image the port simply has no menu font, and menu_status says
    so instead of drawing something invented."""
    raw = load_original_flat()
    widths = [0] * 128
    blob: list[int] = []
    starts = [0] * 128
    ok = False
    b = MENU_FONT_BASE
    if len(raw) < b + 0x188 or raw[b:b + 4] != b"KF4b":
        raise SystemExit(
            f"{ORIGINAL_FLAT}: KF4b menu font is missing at 00027276"
        )
    widths = list(raw[b + 8:b + 8 + 128])
    offs = list(struct.unpack_from("<128H", raw, b + 0x88))
    for c in range(128):
        if not widths[c]:
            continue
        starts[c] = len(blob)
        o = b + offs[c]
        blob.extend(struct.unpack_from(f"<{widths[c]}I", raw, o))
    ok = True

    lines.append("")
    if ok:
        lines.append("; The KF4b menu font, verbatim from the image at 00027276:")
        lines.append(f"; {sum(1 for w in widths if w)} glyphs, {len(blob)} columns.")
    else:
        raise AssertionError("the original menu font was validated above")
    lines.append("        even")
    lines.append("        global  menu_font_ok")
    lines.append("menu_font_ok")
    lines.append(f"        dc.w    {1 if ok else 0}")
    lines.append("        global  menu_font_width")
    lines.append("menu_font_width")
    for pos in range(0, 128, 16):
        lines.append("        dc.b    " + ",".join(str(v) for v in widths[pos:pos + 16]))
    lines.append("        even")
    lines.append("; Byte offset of each glyph's columns inside menu_font_glyphs.")
    lines.append("        global  menu_font_start")
    lines.append("menu_font_start")
    for pos in range(0, 128, 8):
        lines.append("        dc.l    " + ",".join(str(v * 4) for v in starts[pos:pos + 8]))
    lines.append("        global  menu_font_glyphs")
    lines.append("menu_font_glyphs")
    if not blob:
        lines.append("        dc.l    0")
    for pos in range(0, len(blob), 6):
        lines.append("        dc.l    " + ",".join(f"${v:08X}" for v in blob[pos:pos + 6]))


MENU_BAR_STRING = 0x265C0
MENU_GROUPS_FROM = 0x26607
MENU_GROUPS_TO = 0x267F2     # through the Cheat group's 0xFF: "Fix Damage", "Reload"
MENU_REPAIRED_TEXT = 0x26A6C
MENU_RELOADED_TEXT = 0x26A47
MENU_LOCK_TEXT = 0x269D5
MENU_ABOUT_TEXT = 0x2691C
MENU_SAVED_TEXT = 0x269BC
MENU_FILE_DEFAULTS = 0x25DBC
MENU_STATS_TEXT = 0x28AB5

# The screen text the list-menu driver at 00027DB4 walks, seven 0xFF-separated
# screens. Its layout is proved in re/annotations.txt: NUL ends a line, 0xFF
# ends a screen, 0x7C plus a letter is the same colour markup the bar uses, and
# 0xFC is the fill name_entry_loop writes into the pilot field.
MENU_SCREENS_FROM = 0x29B2C
MENU_SCREENS_LEN = 0x3C4

# The pilot screen's own header. 00028231 points the driver at 00029570, which
# is 18 bytes before the COMANCHE.NAM load target at 00029582 - a blank line,
# "|rSelect Pilot:" and another blank - so the header and the roster records
# have to sit contiguously for the driver to walk from one into the other.
MENU_PILOT_HEADER_FROM = 0x29570
MENU_PILOT_HEADER_LEN = 0x12

# The mission-end result block: seven 0x2F-byte message lines from 000284B1 and
# the 0xFF-terminated score screen at 000285FA that 00028261 patches in place -
# the score digits at 0002860B, the five percentages at 00028619/00028633/
# 00028653/0002866D/00028687 and the chosen message at 000286A1.
DEBRIEF_FROM = 0x284B1
DEBRIEF_SCREEN = 0x285FA


def emit_menu_strings(lines: list[str]) -> None:
    """The options menu's own text: the bar at 000265C0 and the four
    drop-down groups running consecutively from 00026607.

    Generated rather than transcribed, for the same reason the font is - it
    is the original's content - and because the port computes the same things
    from it the original does at 000268C5: a group's row count is its strings
    up to the 0xFF terminator, and a panel's width follows from the widest of
    them. Nothing here is a table lifted out of the image; the bytes at
    000265F7 that look like row counts are dead initialisers."""
    raw = load_original_flat()
    if len(raw) < MENU_GROUPS_TO:
        raise SystemExit(f"{ORIGINAL_FLAT}: menu strings are truncated")
    try:
        # The bar's first 0xFF is the Cheat column's hidden 'C' (00026012-0002603F
        # write 0x43 over it); the string ends at the second.
        end = raw.index(b"\xff", MENU_BAR_STRING + 0x2E) + 1
    except ValueError as exc:
        raise SystemExit(
            f"{ORIGINAL_FLAT}: menu bar has no 0xFF terminator"
        ) from exc
    bar = raw[MENU_BAR_STRING:end]
    groups = raw[MENU_GROUPS_FROM:MENU_GROUPS_TO]
    screens = raw[MENU_SCREENS_FROM:MENU_SCREENS_FROM + MENU_SCREENS_LEN]

    # The driver's whole loop structure depends on these two markers, and a
    # silently short or mis-based extraction would still assemble and still
    # draw something. Check the shape here, where it is cheap to say why.
    if screens.count(b"\xff") != 6:
        raise SystemExit(
            f"{ORIGINAL_FLAT}: menu screen block has {screens.count(bytes([0xFF]))}"
            " 0xFF screen terminators, expected 6 - wrong base or truncated")
    if b"Begin Mission" not in screens:
        raise SystemExit(
            f"{ORIGINAL_FLAT}: menu screen block does not contain the main "
            "operations menu - wrong base")

    def blob(label: str, data: bytes) -> None:
        lines.append(f"        global  {label}")
        lines.append(label)
        if not data:
            raise AssertionError(f"{label} unexpectedly empty")
        for pos in range(0, len(data), 16):
            chunk = ",".join(f"${b:02X}" for b in data[pos:pos + 16])
            lines.append("        dc.b    " + chunk)

    lines.append("")
    if bar:
        lines.append(f"; The options bar at 000265C0, {len(bar)} bytes, and the four")
        lines.append(f"; drop-down groups at 00026607, {len(groups)} bytes.")
    else:
        lines.append("; No menu strings: re/unpacked was absent.")
    lines.append("        even")
    lines.append("        global  menu_text_ok")
    lines.append("menu_text_ok")
    lines.append(f"        dc.w    {1 if bar else 0}")
    blob("menu_bar_text", bar)
    lines.append("        even")
    blob("menu_group_text", groups)
    lines.append("        even")
    lines.append(f"; The list-menu screens at {MENU_SCREENS_FROM:08X}, "
                 f"{len(screens)} bytes, seven 0xFF-separated.")
    blob("menu_screen_text", screens)
    lines.append("        even")

    # 00026E90's message line for the locked missions, 000269D5: "You must
    # finish GREEN missions." up to its 0xFF. The caller passes the address in
    # esi at 00029024.
    lock = raw[MENU_LOCK_TEXT:raw.index(b"\xff", MENU_LOCK_TEXT) + 1]
    if b"GREEN" not in lock:
        raise SystemExit(
            f"{ORIGINAL_FLAT}: {MENU_LOCK_TEXT:08X} is not the locked-mission "
            "message - wrong base")
    lines.append(f"; The locked-mission message at {MENU_LOCK_TEXT:08X}, {len(lock)} bytes.")
    blob("menu_lock_text", lock)
    lines.append("        even")

    # The two boxes the options menu's Game column raises: About Comanche
    # (0002691C, 00026E1C's case 0) and "Menu Settings Saved" (000269BC,
    # 00026D8B's case 2), each to its 0xFF - and the 35 bytes the image holds
    # at 00025DBC, which the original writes back as COMANCHE.MNU and which
    # stand in for it when the file is absent.
    for label, addr, needle in (("menu_about_text", MENU_ABOUT_TEXT, b"NovaLogic"),
                                ("menu_saved_text", MENU_SAVED_TEXT, b"Saved"),
                                ("menu_repaired_text", MENU_REPAIRED_TEXT, b"Repaired"),
                                ("menu_reloaded_text", MENU_RELOADED_TEXT, b"Reloaded")):
        text = raw[addr:raw.index(b"\xff", addr) + 1]
        if needle not in text:
            raise SystemExit(f"{ORIGINAL_FLAT}: {addr:08X} is not the expected "
                             f"menu message - wrong base")
        lines.append(f"; {label} at {addr:08X}, {len(text)} bytes.")
        blob(label, text)
        lines.append("        even")
    stats = raw[MENU_STATS_TEXT:raw.index(b"\xff", MENU_STATS_TEXT) + 1]
    if b"Victorious" not in stats:
        raise SystemExit(f"{ORIGINAL_FLAT}: {MENU_STATS_TEXT:08X} is not the "
                         "pilot statistics screen - wrong base")
    lines.append(f"; The Your Stats screen at {MENU_STATS_TEXT:08X}, {len(stats)} bytes.")
    blob("menu_stats_text", stats)
    lines.append("        even")
    # The new-pilot name entry, 0002800C: the record's head and tail
    # (00027FC0, 00027FC9), the prompt line with its name buffer (00027FD5 to
    # the 0xFF) and the two scancode-to-character tables it reads
    # (000019E9 plain, 00001969 shifted).
    for label, addr, length in (("name_head_text", 0x27FC0, 9),
                                ("name_tail_text", 0x27FC9, 12),
                                ("name_plain_keys", 0x19E9, 128),
                                ("name_shift_keys", 0x1969, 128)):
        lines.append(f"; {label} at {addr:08X}, {length} bytes.")
        blob(label, raw[addr:addr + length])
        lines.append("        even")
    prompt = raw[0x27FD5:raw.index(b"\xff", 0x27FD5) + 1]
    if b"Enter Your Name" not in prompt:
        raise SystemExit(f"{ORIGINAL_FLAT}: 00027FD5 is not the name prompt")
    lines.append(f"; The name prompt at 00027FD5, {len(prompt)} bytes.")
    blob("name_prompt_text", prompt)
    lines.append("        even")
    lines.append("; The roster the image ships at 00029582, 1450 bytes (the file overwrites it).")
    blob("roster_defaults", raw[0x29582:0x29582 + 1450])
    lines.append("        even")
    lines.append(f"; The settings file's image defaults, {MENU_FILE_DEFAULTS:08X}, 35 bytes.")
    blob("menu_file_defaults", raw[MENU_FILE_DEFAULTS:MENU_FILE_DEFAULTS + 35])
    lines.append("        even")

    debrief_end = raw.index(b"\xff", DEBRIEF_SCREEN) + 1
    debrief = raw[DEBRIEF_FROM:debrief_end]
    if b"Mission Score:" not in debrief or b"Congratulations" not in debrief:
        raise SystemExit(
            f"{ORIGINAL_FLAT}: {DEBRIEF_FROM:08X} is not the mission-end text - "
            "wrong base")
    lines.append(f"; The mission-end messages and score screen at {DEBRIEF_FROM:08X}, "
                 f"{len(debrief)} bytes.")
    blob("debrief_text", debrief)
    lines.append("        even")

    pilot_header = raw[MENU_PILOT_HEADER_FROM:
                      MENU_PILOT_HEADER_FROM + MENU_PILOT_HEADER_LEN]
    if b"Select Pilot" not in pilot_header:
        raise SystemExit(
            f"{ORIGINAL_FLAT}: {MENU_PILOT_HEADER_FROM:08X} is not the pilot "
            "screen header - wrong base")
    lines.append(f"; The pilot screen's header at {MENU_PILOT_HEADER_FROM:08X}, "
                 f"{len(pilot_header)} bytes, copied in front of the roster.")
    blob("menu_pilot_header", pilot_header)
    lines.append("        even")


def emit_tables(lines: list[str]) -> None:
    raw = load_original_flat()
    q31_end = SINE_Q31_BASE + 640 * 4
    if len(raw) < q31_end:
        raise SystemExit(
            f"{ORIGINAL_FLAT}: DOS sine table at 00032120 is truncated"
        )
    q31 = struct.unpack_from("<640i", raw, SINE_Q31_BASE)

    lines.append("")
    lines.append("; sin(a) in 8.8 for a in 1/256 turn units, with 64 extra")
    lines.append("; entries so that cos(a) is simply sin_table[a + 64].")
    lines.append("        even")
    lines.append("sin_table")
    # The renderer's 256-entry 8.8 view table is the DOS 512-step Q31 table
    # sampled at every second entry and truncated by the same shift as the
    # original fixed-point consumers. In particular cos(0) is 255, not the
    # analytic 256 that the old stand-in emitted.
    values = [q31[i * 2] >> 23 for i in range(SIN_ENTRIES + SIN_EXTRA)]
    for pos in range(0, len(values), 8):
        chunk = values[pos : pos + 8]
        lines.append("        dc.w    " + ",".join(str(v) for v in chunk))

    octant_end = OBJECT_OCTANT_BASE + 8 * 4
    # 00024C9B divides the SMALLER magnitude by the larger one shifted right
    # ten, so 00024C9D's index is the ratio scaled by 1024, not by 256. The
    # table itself is the arctan ramp 0..63 over indices 0..1024 - 1025 bytes,
    # ending where 000227A6's bytes stop being monotone. It is transcribed
    # with the 1023 bytes after it because the index is not bounded by 1024:
    # 00024C95's `je` only rules out max < 1024, and for max in [1024, 2047]
    # the divisor is 1 and the index runs to 2047. The original reads those
    # bytes; reproducing the image is faithful where a clamp would be a second
    # behaviour. Transcribing 256 was the bug - a bearing at ratio 380 read
    # past the end of the table.
    correction_end = OBJECT_CORRECTION_BASE + 2048
    if len(raw) < correction_end:
        raise SystemExit(
            f"{ORIGINAL_FLAT}: object bearing tables at 00022385/000223A5 "
            "are truncated"
        )
    offsets = struct.unpack_from(f"<{VIEW_VARIANT_COUNT}i", raw,
                                 VIEW_ANGLE_OFFSET_BASE)
    lines.append("")
    lines.append("; DOS view-angle offsets, verbatim from 00019D94. Indexed by")
    lines.append("; the view variant [00019D86]; see view_basis_build.")
    lines.append("        even")
    lines.append("        global  view_angle_offsets")
    lines.append("view_angle_offsets")
    for pos in range(0, len(offsets), 3):
        lines.append("        dc.l    "
                     + ",".join(str(v) for v in offsets[pos:pos + 3]))
    octants = struct.unpack_from("<8I", raw, OBJECT_OCTANT_BASE)
    correction = raw[OBJECT_CORRECTION_BASE:correction_end]
    lines.append("")
    lines.append("; DOS object bearing octants, verbatim from 00022385.")
    lines.append("        even")
    lines.append("object_octant_table")
    for pos in range(0, len(octants), 4):
        lines.append("        dc.l    " + ",".join(str(v) for v in octants[pos:pos + 4]))
    lines.append("")
    lines.append("; DOS object bearing ratio correction, verbatim from 000223A5.")
    lines.append("; 0..1024 is the arctan ramp 00024C9D indexes with the")
    lines.append("; 1024-scaled ratio; the rest is what the original reads past")
    lines.append("; it when the two magnitudes are under a map unit apart.")
    lines.append("        even")
    lines.append("object_bearing_correction")
    for pos in range(0, len(correction), 16):
        lines.append("        dc.b    " + ",".join(str(v) for v in correction[pos:pos + 16]))
    lines.append("        even")

    ramp_offsets = struct.unpack_from("<128I", raw, SPRITE_RAMP_OFFSETS_BASE)
    ramp_pool = raw[SPRITE_RAMP_POOL_BASE:SPRITE_RAMP_POOL_BASE + SPRITE_RAMP_POOL_BYTES]
    lines.append("")
    lines.append("; DOS sprite scale ramps, verbatim from 0001D7EC (128 offsets) and")
    lines.append("; 0001DBEC (the pool). 000253CD's scale index [00022354] selects ramp r,")
    lines.append("; 128 - r bytes summing to 64 (ramp 0 is 1,0,1,0 ...): each byte is how")
    lines.append("; many source columns, and separately rows, one destination column or")
    lines.append("; row consumes. A sprite larger than 64 reads on into the next ramps; the")
    lines.append("; 512 bytes after the pool are what it reads past the last one.")
    lines.append("        even")
    lines.append("        global  sprite_ramp_offsets, sprite_ramp_pool")
    lines.append("sprite_ramp_offsets")
    for pos in range(0, 128, 8):
        lines.append("        dc.l    " + ",".join(str(v) for v in ramp_offsets[pos:pos + 8]))
    lines.append("sprite_ramp_pool")
    for pos in range(0, len(ramp_pool), 16):
        lines.append("        dc.b    " + ",".join(str(v) for v in ramp_pool[pos:pos + 16]))
    lines.append("        even")

    dtl = load_dtl()

    lines.append("")
    lines.append("; Reciprocal depth, one entry per depth sample. The first 64")
    lines.append("; samples are unit steps; the rest use four-unit steps.")
    lines.append("; The 1/z relation is the original's, recovered from")
    lines.append("; HIGH.DTL: its table 2 holds 819200 * 2**32 / z at every")
    lines.append("; one of its 250 depth steps, exact to the last entry, so")
    lines.append("; the shape here is not a model of the original - it is")
    lines.append("; the original's own, evaluated at this port's depths.")
    lines.append("        even")
    lines.append("invz_table")
    inv = []
    z = 0
    for i in range(DEPTH_SAMPLES):
        z += depth_step(i)
        inv.append(min(32767, (PROJ_SCALE * 256) // z))
    for pos in range(0, len(inv), 4):
        if pos == DEPTH_NEAR_SAMPLES:
            lines.append("invz_far_start")
        if pos == DEPTH_NEAR_SAMPLES + DEPTH_FAR_SAMPLES:
            lines.append("invz_far2_start")
        chunk = inv[pos : pos + 4]
        lines.append("        dc.w    " + ",".join(str(v) for v in chunk))
    lines.append("invz_end")

    lines.append("")
    lines.append("; Horizon row per depth sample, from HIGH.DTL table 3 -")
    lines.append("; the bias build_projection_tables adds before taking the")
    lines.append("; high byte, so bias/256 is the page row a point on the")
    lines.append("; camera's level plane lands on. Page rows map to screen")
    lines.append("; rows 1:1 and inverted - sub_00006FEF walks surface")
    lines.append("; row 32 to VGA row 181 over 182 rows, so page row k is")
    lines.append(f"; screen row {DTL_ANCHOR}-k - these are {DTL_ANCHOR} - (bias >> 8).")
    lines.append("; It is a curve, not a constant: page 137 at the far end")
    lines.append("; and 60 at the nearest step, which is why a single")
    lines.append("; SCREEN_HORIZON could only ever be right at one depth.")
    lines.append("        even")
    lines.append("horizon_table")
    lines.append("; render.s walks invz_table and this one in lockstep, so it")
    lines.append("; reaches the horizon through this delta rather than a second")
    lines.append("; pointer. Emitted here so the two cannot drift apart.")
    hor = []
    for i in range(DEPTH_SAMPLES):
        hor.append(dtl_horizon(dtl, i))
    for pos in range(0, len(hor), 8):
        chunk = hor[pos : pos + 8]
        lines.append("        dc.w    " + ",".join(str(v) for v in chunk))
    lines.append("HORIZON_DELTA = horizon_table-invz_table")

    # ------------------------------------------------------------------
    # The ring-major schedule: the original's own, straight out of the .DTL.
    #
    # The three tables above describe this port's column-major march, whose
    # depth steps are powers of two because a column-major marcher pays a
    # multiply per sample PER COLUMN for anything else. The original is
    # ring-major - outer loop over the 250 depth rings, inner over the columns
    # of one ring - so its step is spent once across a whole ring and can be
    # any curve the file likes. These are that curve, for render.s's
    # ring-major marcher.
    #
    # HIGH.DTL table 1 holds the per-ring forward increment and table 0 the
    # per-ring lateral increment, both raw 10.22 words. Table 4 is the
    # original running total of the raw A words; because the marcher's step
    # is high32(A * sinQ31) = A/2 map units, that total counts world depth
    # at 2^23 per unit, and it must be read unsigned because its raw value
    # passes 2^31 (512 world units) before ring 250.
    lines.append("")
    # WHICH file, and at WHAT offsets. Both were wrong here, and a QMP dump
    # of the running original is what showed it.
    #
    # 00026211-0002626E selects the file from the detail byte [00025DD4]:
    # '0' loads high.dtl, '1' medium.dtl, anything else low.dtl, each through
    # 00015DD0 with eax = 0x00019EE0 - so the file lands AT 0x19EE0 and its
    # own first dword becomes the ring count [0x19EE0].
    #
    # Every consumer then reads the tables at FIXED absolute addresses:
    # 0000D9BB takes the lateral increment from 0x19EE4 (file + 4),
    # 0000D99B the forward increment from 0x1A2CC (file + 1004), and
    # 00015ADA/00015B0A the projection slope and bias from 0x1A6B4 and
    # 0x1AA9C (file + 2004 and + 3004). Those offsets are the table
    # boundaries only for a 250-entry file. For any other .DTL they land
    # partway into a neighbouring table, and the original does that anyway.
    #
    # The shipped install runs MEDIUM: two independent QMP captures of the
    # attract flight read [0x19EE0] = 180, which is medium.dtl's declared
    # count, and their slope/bias arrays are byte-identical to medium.dtl at
    # offsets 2004 and 3004. Generating from high.dtl against a medium oracle -
    # what this did before - produced 250 pages that matched none of the
    # original's 180. See docs/PORTING-PLAN.md.
    #
    # That was a mismatch between the build and the capture, not a fault in
    # either file, and it is the trap to remember here: the detail level is a
    # setting the original exposes at 00026211, and BOTH sides have to be on
    # the same one before any table is compared. This port is built for high
    # detail, so the oracle has to be set to '0' too - otherwise the 250 pages
    # generated here will again match none of the 180 captured.
    #
    # The offsets below are the original's fixed absolute ones, not the file
    # format's; for a 250-entry file they coincide.
    raw = (Path(__file__).resolve().parent.parent
           / "assets/extracted/comanche_hdd/HIGH.DTL").read_bytes()
    nring = struct.unpack_from("<I", raw, 0)[0]
    dtl_b = list(struct.unpack_from(f"<{nring}I", raw, 4))         # 0x19EE4
    dtl_a = list(struct.unpack_from(f"<{nring}I", raw, 1004))      # 0x1A2CC
    dt2 = list(struct.unpack_from(f"<{nring}I", raw, 2004))        # 0x1A6B4
    dt3 = list(struct.unpack_from(f"<{nring}I", raw, 3004))        # 0x1AA9C
    dtl_z = list(struct.unpack_from(f"<{nring}I", raw, 4004))

    def pad(values, fill=0):
        """Grow a per-ring column to DTL_MAX_STEPS.

        The tail is never walked - every ring loop bounds itself by the live
        ring_steps - but the storage has to exist so a HIGH.DTL loaded at
        runtime has somewhere to land."""
        return values + [fill] * (DTL_MAX_STEPS - len(values))

    dtl_a = pad(dtl_a)
    dtl_b = pad(dtl_b)
    dtl_z = pad(dtl_z)
    dt2 = pad(dt2)
    dt3 = pad(dt3)

    lines.append("; Original per-ring forward increment A, 10.22 raw words.")
    lines.append("        even")
    lines.append("ring_a_table")
    for pos in range(0, DTL_MAX_STEPS, 4):
        lines.append("        dc.l    " + ",".join(str(v) for v in dtl_a[pos:pos + 4]))
    lines.append("")
    lines.append("; Original per-ring lateral increment B, 10.22 raw words.")
    lines.append("        even")
    lines.append("ring_b_table")
    for pos in range(0, DTL_MAX_STEPS, 4):
        lines.append("        dc.l    " + ",".join(str(v) for v in dtl_b[pos:pos + 4]))
    lines.append("")

    lines.append("; Ring-major depth schedule from HIGH.DTL: table 4 verbatim,")
    lines.append("; the running total of the raw A words. One unit of world")
    lines.append("; depth is 2^23 here - the marcher's step is high32(A*sin),")
    lines.append("; A/2 map units - and 00024CC0 compares the object depth")
    lines.append("; (world<<20) shifted left 3 against these words UNSIGNED.")
    lines.append("        even")
    lines.append("ring_z_table")
    for pos in range(0, DTL_MAX_STEPS, 4):
        chunk = dtl_z[pos : pos + 4]
        lines.append("        dc.l    "
                     + ",".join(str(z if z < (1 << 31) else z - (1 << 32))
                                for z in chunk))
    lines.append("")
    lines.append("; 1/z per ring, same PROJ_SCALE*256 numerator as")
    lines.append("; invz_table so the two projections are one projection.")
    lines.append("        even")
    lines.append("ring_invz_table")
    inv = [min(32767, int((PROJ_SCALE * 256) // z)) if z > 0 else 32767
           for z, _ in dtl]
    inv = pad(inv, 32767)
    for pos in range(0, len(inv), 8):
        lines.append("        dc.w    "
                     + ",".join(str(v) for v in inv[pos : pos + 8]))
    lines.append("")
    lines.append(f"; Horizon row per ring, {DTL_ANCHOR} - (bias >> 8), indexed")
    lines.append("; directly instead of searched for by depth.")
    lines.append("        even")
    lines.append("ring_horizon_table")
    rows = pad([DTL_ANCHOR - (b >> 8) for _, b in dtl], DTL_ANCHOR)
    for pos in range(0, len(rows), 8):
        lines.append("        dc.w    "
                     + ",".join(str(v) for v in rows[pos : pos + 8]))
    lines.append("")
    lines.append("; RING_STEPS is the STORAGE bound - HIGH.DTL's count, the")
    lines.append("; largest the Detail menu can select at runtime. The live")
    lines.append("; count is the word below, which src/dtl.s rewrites when it")
    lines.append("; loads a different file. Every ring loop reads that word;")
    lines.append("; only array sizes use the constant.")
    lines.append(f"RING_STEPS = {DTL_MAX_STEPS}")
    lines.append(f"RING_STEPS_INIT = {len(dtl)}")
    lines.append("")
    lines.append("; In TEXT with the tables it counts, not BSS: a dc.w in a bss")
    lines.append("; section is zero-filled at load, which would make every ring")
    lines.append("; walk terminate immediately. render_page_anchor carries the")
    lines.append("; same warning for the same reason.")
    lines.append("        even")
    lines.append("        global  ring_steps")
    lines.append("ring_steps")
    lines.append("        dc.w    RING_STEPS_INIT")

    # The projection pages, exactly as build_projection_tables makes them
    # at 00015B24:
    #
    #   page[k] = clamp(high32(((k-128)<<24) * slope_i) + bias_i,
    #                   0, 0xFF00) >> 8
    #
    # with slope_i = high32(dtl2[i] * [00019CEC]) and bias_i = dtl3[i].
    # It is EDX that receives the bias in both multiplies, so both keep
    # the HIGH half of a 64-bit product - reading either as a shift makes
    # every row saturate.
    #
    # The marcher indexes one of these with (127 - alt/2 + height) & 0xFF
    # and takes the row straight out, which is what 0000D9F6/0000D9F9 do.
    # That replaces a per-sample multiply with a byte read, and carries
    # the original's clamps at page rows 0 and 255 - neither of which the
    # computed form had.
    MUL = 0x03000000
    lines.append("")
    lines.append(f"; {nring} projection pages of 256 rows, from .DTL")
    lines.append("; tables 2 and 3 - the lookup 0000D9F9 reads.")
    lines.append("        even")
    lines.append("ring_page_table")
    page128 = []
    for i in range(DTL_MAX_STEPS):
        slope = (dt2[i] * MUL) >> 32
        bias = dt3[i]
        page = []
        for k in range(256):
            v = ((((k - 128) << 24) * slope) >> 32) + bias
            v = 0 if v < 0 else (0xFF00 if v > 0xFF00 else v)
            page.append((v >> 8) & 0xFF)
        page128.append(page[128])
        for q in range(0, 256, 16):
            lines.append("        dc.b    "
                         + ",".join(str(v) for v in page[q:q + 16]))
    lines.append("        even")
    lines.append(f"RING_PAGE_ANCHOR = {DTL_ANCHOR}")

    # The terrain and the objects standing on it reach the horizon by two
    # different routes, and nothing used to check that they agree. The
    # terrain draws through ring_page_table indexed by the .DTL's own
    # rings; an object places itself through horizon_table indexed by this
    # port's depth schedule. Both descend from bias_i, but through
    # different index arithmetic, and a divergence does not look like a
    # broken table - it looks like sprites floating over the ground.
    #
    # At k = 128 the page's (k-128) term vanishes, so page[128] IS the
    # level plane's row and must be bias_i >> 8 exactly. Check that, then
    # check that the horizon every depth sample will be placed against is
    # the anchor minus the page row of the ring the terrain would draw at
    # the same distance. A build that cannot satisfy both has a projection
    # bug, and shipping it costs far more than failing here.
    for i in range(nring):
        if page128[i] != (dt3[i] >> 8) & 0xFF:
            raise SystemExit(
                f"projection: ring {i} page[128] is {page128[i]}, "
                f"bias>>8 is {(dt3[i] >> 8) & 0xFF}")
    for sample in range(DEPTH_SAMPLES):
        z = sum(depth_step(j) for j in range(sample + 1))
        ring = next((j for j, (zj, _) in enumerate(dtl) if zj >= z),
                    len(dtl) - 1)
        want = DTL_ANCHOR - page128[ring]
        got = dtl_horizon(dtl, sample)
        if want != got:
            raise SystemExit(
                f"projection: depth sample {sample} places objects at "
                f"row {got} but the terrain draws ring {ring} at {want}")


# The Comanche palette is carried by C1.DTA after the decoded map stream. The
# resource reader reaches it through the same 0x0C marker and 768 raw bytes;
# this build-time copy keeps the generated RGB565 table byte-for-byte tied to
# the runtime resource contract.
#
# res_open_e at 00016381 reads a 128-byte header, takes the words at +8 and +10
# as width-1 and height-1, forms (w+1)*(h+1) and falls straight into the decoder
# at 0001644B. When that has produced exactly that many bytes, 000164B7 reads
# the next stream byte and, if it is 0x0C, copies 768 more into the palette
# buffer at 00015F84 - `shr al,2` on the way, so the file holds 8-bit
# components and the DAC gets six. 0002A9E7 then uploads that buffer unaltered.
#
# So the terrain's palette is inside C1.DTA. The P-series files are the same
# mechanism used for nothing else: a 16x22 dummy image followed by a palette,
# which is why a mission's resource list names p12.dta first.
#
# This replaces LH66.RLE's palette, which was picked by rendering when the
# mechanism was not yet understood. LH66's is a real palette but the wrong one -
# it renders C1 muted and noisy where its own resolves into green vegetation,
# brown rock and cyan rivers.
#
# Eight bits to RGB565: red and blue keep five, green six.
def comanche_palette(colour_path: Path) -> list[int] | None:
    data = colour_path.read_bytes()
    if data[:8] != b"Kyle DTA":
        return None
    width = int.from_bytes(data[8:10], "little") + 1
    height = int.from_bytes(data[10:12], "little") + 1
    want = width * height
    produced = 0
    i = 128
    while produced < want and i < len(data):
        b = data[i]
        i += 1
        if b >= 0xC0:
            if i >= len(data):
                return None
            produced += b & 0x3F
            i += 1
        else:
            produced += 1
    if i >= len(data) or data[i] != 0x0C or i + 769 > len(data):
        return None
    pal = data[i + 1 : i + 769]
    return [
        ((pal[k * 3] >> 3) << 11) | ((pal[k * 3 + 1] >> 2) << 5) | (pal[k * 3 + 2] >> 3)
        for k in range(256)
    ]


def write_palette(output: Path, palette: list[int], source_label: str) -> None:
    lines = [
        f"; Generated RGB565 palette from {source_label}.",
        "; Do not edit: tools/prepare-original-test.py regenerates this file.",
        "        even",
        "colour_palette",
    ]
    for pos in range(0, len(palette), 8):
        chunk = palette[pos : pos + 8]
        lines.append("        dc.w    " + ",".join(f"${value:04X}" for value in chunk))
    lines.append("colour_palette_end")
    output.write_text(chr(10).join(lines) + chr(10), encoding="ascii")


def write_maps(
    output: Path,
    height: bytes,
    colour: bytes,
    palette: list[int],
    source_id: int,
    source_label: str,
) -> None:
    """Emit the full-resolution maps as binaries plus an assembly stub.

    1024x1024 is 1 MiB per map. Emitting that as `dc.b` would be two million
    assembler lines; `incbin` keeps the build a file copy instead. The binaries
    live beside the stub in ignored build output - no original asset enters the
    repository or the release tree.
    """
    height_path = output.parent / "map_height.bin"
    colour_path = output.parent / "map_colour.bin"
    palette_path = output.parent / "colour_palette.s"
    height_path.write_bytes(height)
    colour_path.write_bytes(colour)
    write_palette(palette_path, palette, source_label)

    lines = [
        f"; Generated from {source_label}.",
        "; Do not edit: tools/prepare-original-test.py regenerates this file.",
        "ORIGINAL_ASSET_READY = 1",
        "; 1 = original D1/C1",
        f"ORIGINAL_ASSET_SOURCE = {source_id}",
        "ORIGINAL_MAP_SIZE = 1024",
        "ORIGINAL_MAP_MASK = $03ff",
        "ORIGINAL_MAP_SHIFT = 10",
        f"DEPTH_SAMPLES = {DEPTH_SAMPLES}",
        f"DEPTH_NEAR_SAMPLES = {DEPTH_NEAR_SAMPLES}",
        f"DEPTH_NEAR_STEP = {DEPTH_NEAR_STEP}",
        f"DEPTH_FAR_STEP = {DEPTH_FAR_STEP}",
        "",
        "; The map buffers live in Falcon BSS and are filled by resources.s.",
        "; map_height.bin and map_colour.bin remain ignored build outputs for",
        "; native reference renders and asset inspection, not executable data.",
    ]
    emit_sine_q31(lines)
    emit_menu_font(lines)
    emit_menu_strings(lines)
    emit_tables(lines)
    output.write_text(chr(10).join(lines) + chr(10), encoding="ascii")


def make_output(output: Path, root: Path, source: str) -> str:
    source_root = root / "assets" / "extracted" / "comanche_hdd"
    height_path = source_root / "D1.DTA"
    colour_path = source_root / "C1.DTA"
    have_original = height_path.exists() and colour_path.exists()

    if source == "auto":
        source = "original"

    if source != "original":
        raise ValueError(f"unknown --source {source!r}")
    if not have_original:
        raise ValueError(
            f"--source original needs {height_path} and {colour_path}"
        )

    height = decode_dta(height_path)
    # Raw C1 index bytes, deliberately not reduced. resources.s writes the same
    # raw bytes into original_colour_map at runtime, so the build-time map and
    # the runtime map now share one index space and one palette covers both.
    colour = decode_dta(colour_path)
    palette = comanche_palette(colour_path)
    if palette is None:
        raise ValueError(f"{colour_path}: missing original Kyle palette")
    label = "original Comanche D1.DTA/C1.DTA pair"
    note = "C1.DTA palette"
    write_maps(output, height, colour, palette, SOURCE_ORIGINAL, f"{label}, {note}")
    return f"D1.DTA/C1.DTA -> {MAP_SOURCE_SIZE}x{MAP_SOURCE_SIZE} full-resolution maps, {note}"


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = [a for a in sys.argv[1:] if a.startswith("--")]
    source = "auto"
    for flag in flags:
        if flag.startswith("--source="):
            source = flag.split("=", 1)[1]
        else:
            print(f"usage: {Path(sys.argv[0]).name} [--source=NAME] OUTPUT", file=sys.stderr)
            return 2
    if len(args) != 1:
        print(
            f"usage: {Path(sys.argv[0]).name} [--source=auto|original] OUTPUT",
            file=sys.stderr,
        )
        return 2

    output = Path(args[0])
    root = Path(__file__).resolve().parent.parent
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        description = make_output(output, root, source)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"prepared original terrain test: {description}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
