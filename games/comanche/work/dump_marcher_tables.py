#!/usr/bin/env python3
"""Dump the surface-transfer run list and the sky horizon array out of the
running original, so the CPU marcher can be checked against data instead of
fitted to a picture.

Why this exists
---------------
`docs/PORTING-PLAN.md` recorded the terrain silhouette gap as needing "more
disassembly". It does not. The 207,648-byte flat content region ends at
exactly 0x32B20, and every table `00007AA0` reads starts at or after that
address, so all of them are BSS built at runtime and cannot be read out of the
image at all.

What 00007AA0 actually consumes, read off the listing rather than assumed:

    ecx = word  [ebp*4 + 0x38B20]     run length in bytes
    bx  = word  [ebp*4 + 0x38B22]     bl = leading odd byte, bh = trailing
    esi = dword [ebp*4 + 0x32B20]     source offset
    eax = dword [ebp*4 + 0x3AB20]     pointer to the source base
    esi += [eax]
    edi = dword [edx*4 + 0x34B20]     destination offset, edx = ebp (+0x800
                                      when [0x19D87] is set)
    ... movsb / rep movsw of ecx bytes, with the two odd bytes written
        through their own plane masks ...
    loop while ebp != [0x19E4C]

So it is a run list of [0x19E4C] entries, not four "per-column tables" - that
earlier reading is superseded here. 0x3CB40 is separate: the 192-byte per
column horizon the sky fill at 00017275 walks.

Usage
-----
    python3 work/dump_marcher_tables.py --at 60 --at 75 --at 90

Each sample that finds a non-zero entry count is written to
work/qemu_out/marcher-<seconds>.json, with the camera state beside it so the
dump is anchored to a known viewpoint. Run it under the pinned camera build
for a still one; see tools/oracle-capture.sh's PIN_CAMERA notes.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dosimg
from inspect_qemu_state import Qmp, default_hdd, xp_bytes, u32_table
from rsp import Rsp

QEMU = dosimg.host_tool("qemu-system-i386")
ROOT = dosimg.find_project_root(__file__)

# The flat selector base in QEMU physical memory, the same constant
# inspect_qemu_state.print_objects uses.
FLAT = 0x6040

RUN_LEN_AND_FLAGS = 0x38B20
RUN_SOURCE        = 0x32B20
RUN_SOURCE_BASE   = 0x3AB20
RUN_DEST          = 0x34B20
HORIZON           = 0x3CB40
HORIZON_BYTES     = 192

# The 256x256 chunky surface the marcher draws into and 00007AA0 copies out of.
# 00006FEF starts its source at [0x19E70] + 0x2011 - surface row 32, column 17
# - and its destination at [0x000014C4] + 0x39FA, which is VGA row 181 exactly
# (0x39FA / 0x52 = 181). It walks 0xB6 = 182 rows, source row increasing
# (`inc dh`) while the destination decreases by 0x52, so
#
#     screen row = 181 - (surface row - 32) = 213 - surface row
#
# which is where RING_PAGE_ANCHOR's 213 comes from, confirmed here by the
# producer rather than inferred.
SURFACE_BYTES     = 0x10000
SURFACE_SRC_ROW   = 32
SURFACE_SRC_COL   = 17
SURFACE_ROWS      = 0xB6
SCREEN_ANCHOR     = 213

# Scalars worth having next to the tables: without the camera a dump cannot be
# matched to anything the port renders.
SCALARS = {
    "run_count_0x19E4C":   (0x19E4C, 4),
    "dest_half_0x19D87":   (0x19D87, 1),
    "camera_x_0x19CD4":    (0x19CD4, 4),
    "camera_y_0x19CD8":    (0x19CD8, 4),
    # The frame driver latches the camera into these at 0000D3CA/0000D3D4
    # BEFORE calling the renderer, and the flight integration that advances
    # [00019CD4] runs after it - inside the same driver call, at 0000D413.
    # So a sample taken anywhere after the marcher finds [00019CD4] already
    # advanced to the next frame while the silhouettes are still this one's.
    # The latched pair is the camera the marcher actually used.
    "frame_x_0x19CDC":     (0x19CDC, 4),
    "frame_y_0x19CE0":     (0x19CE0, 4),
    "view_angle_0x19D04":  (0x19D04, 4),
    # 00007D25 publishes the VIEW angle at [0x19D00] and the variant it
    # built it for at [0x19D86]. tools/gen-marcher-oracle.py needs both:
    # it pins flt_angle to reproduce the marcher's basis, which only
    # holds while variant 1's identity handler leaves [0x19D00] equal
    # to [0x19D04]. In any external view they differ and the pinned
    # camera would march a heading the original never used.
    "view_angle_0x19D00":  (0x19D00, 4),
    "view_variant_0x19D86": (0x19D86, 1),
    "altitude_0x19DFC":    (0x19DFC, 1),
    "sin_0x19CB0":         (0x19CB0, 4),
    "cos_0x19CB4":         (0x19CB4, 4),
    "surface_0x19E70":     (0x19E70, 4),
    "page_base_0x19CAC":   (0x19CAC, 4),
    "pan_0x19DC4":         (0x19DC4, 4),
    "roll_0x19CF8":        (0x19CF8, 4),
    "pitch_0x19CFC":       (0x19CFC, 4),
    # The impact shake. 00001DB5-00001DE7 runs the PRNG at 0x19DB8 every
    # timer tick and stores the 0..3 phase to 0x19DBC while the countdown at
    # 0x19DC0 lasts; 00007DB5 subtracts that phase from the backdrop's base,
    # so a horizon comparison that ignores it is off by a constant whenever
    # the captured frame happened to be shaking.
    "shake_rng_0x19DB8":   (0x19DB8, 4),
    "shake_phase_0x19DBC": (0x19DBC, 4),
    "shake_timer_0x19DC0": (0x19DC0, 4),
    # 1 while a DEMO<n>.SCR replay is playing: 00019A4E sets it when the
    # reader loads the file, 00018C87 and 00019AF4 clear it, and 000199B5
    # uses 0xFFFFFFFF for recording. This is the only reliable "we are in a
    # terrain flight" test - fraction-of-surface-painted cannot tell a flight
    # frame from a full-screen briefing image, because both fill the window.
    "replay_mode_0x19ED0": (0x19ED0, 4),
    "attract_on_0x19ED4":  (0x19ED4, 1),
    # 00015AD9's inputs: the ring count, the 0x03000000 scalar, and the
    # destination the 256-byte projection pages are built into.
    "ring_count_0x19EE0":  (0x19EE0, 4),
    "proj_scalar_0x19CEC": (0x19CEC, 4),
    "page_buffer_0x19E5C": (0x19E5C, 4),
    # 00019366's `add ebx, [0x19E6C]` - the flat base of the 1024x1024 height
    # map the marcher samples through gs at 0000D9F6.
    "height_map_0x19E6C":  (0x19E6C, 4),
    # 00015922: the map sub_0001591A samples for the MFD moving map, and
    # 00015C90's zoom that scales its grid.
    "mfd_map_0x19E64":     (0x19E64, 4),
    "mfd_zoom_0x19C90":    (0x19C90, 4),
    # 0000F2F1's base: the marcher copies its finished 192-byte per-column
    # occlusion out to [0x19E60] + ring*256 + 0x20 at the end of every ring,
    # so this is the terrain silhouette itself - no sky/terrain ambiguity,
    # unlike reading it back off the drawn surface.
    "silhouette_0x19E60":  (0x19E60, 4),
    # 00026211 reads the detail character from here; the three bytes after it
    # are the rest of the shipped settings block. The image ships '2','1','1',
    # '4' but COMANCHE.CFG is loaded over it, so only a capture says what the
    # game actually runs with.
    "settings_0x25DD4":    (0x25DD4, 4),
    "detail_cache_0x25DAB": (0x25DAB, 1),
    # 000261FE: '}' (0x7D) keeps the renderer at 0x0000D950, anything else
    # switches [0x19C94] to 0x000137F0 - a different marcher entirely.
    "renderer_sel_0x25DD9": (0x25DD9, 1),
    "renderer_ptr_0x19C94": (0x19C94, 4),
    # 000072EB's four label blits read these: left page, right page, and the
    # previous value of each. The image ships 0,1,0,0 - so anything else is
    # the running game having selected a page, and the only writers are the
    # function-key cases at 000195B1-00019643.
    "mfd_page_left_0x72E6":  (0x72E6, 1),
    "mfd_page_right_0x72E7": (0x72E7, 1),
    "mfd_page_lprev_0x72E8": (0x72E8, 1),
    "mfd_page_rprev_0x72E9": (0x72E9, 1),
    "mfd_page_dirty_0x72EA": (0x72EA, 1),
    # 0x1B70 is where 00018CDB parks the demo record's key byte.
    "demo_key_0x1B70":       (0x1B70, 1),
    # 00007403 draws console element [0x19D88] + 7, and 00019649/0001965E
    # step it with '[' and ']' from the demo stream.
    "console_page_0x19D88":  (0x19D88, 1),
    "weapon_0x19D81":        (0x19D81, 1),
    # 0000D69A/0000D6D7 call through this six-entry table, one handler per
    # MFD page. 0x19E10 is inside the static content region, but the frame
    # driver's two override tests (0x1AA5, 0x19E3E/0x19E3F) can replace the
    # choice, so capture the inputs as well as the table.
    "mfd_override_0x1AA5":   (0x1AA5, 1),
    "mfd_left_ovr_0x19E3E":  (0x19E3E, 1),
    "mfd_right_ovr_0x19E3F": (0x19E3F, 1),
    "mfd_origin_0x19CA8":    (0x19CA8, 4),
    # 00025C55 takes its colour in cl, and every caller loads it from here.
    "hud_column_col_0x2A37A": (0x2A37A, 1),
    # The rest of the named colour slots 0002AAB3-0002AB3F resolves, so the
    # colour matcher can be checked at more than one point.
    "colour_0x2A375":        (0x2A375, 1),
    "colour_0x2A376":        (0x2A376, 1),
    "colour_0x2A377":        (0x2A377, 1),
    "colour_0x2A378":        (0x2A378, 1),
    # The three authored HUD option bytes: Artificial Horizon, HID
    # Indicators, HID Compass. '{' is off, '}' is on. The image ships
    # '{','}','}' but the menu/CFG can rewrite them.
    "settings_block_0x25DD4": (0x25DD4, 12),
    # 00007860's gate: the locked target index. Zero means the target view
    # skips its march entirely and only re-transfers the viewport.
    "target_index_0x19D10":  (0x19D10, 4),
    # 00024DFC's "most recently targetable object", which 00019275 seeds the
    # latch from when it is zero.
    "target_default_0x19D18": (0x19D18, 4),
    "opt_horizon_0x267AC":   (0x267AC, 1),
    "opt_indicators_0x267C1": (0x267C1, 1),
    "opt_compass_0x267D2":   (0x267D2, 1),
}

# 00015AD9 builds one 256-byte projection page per depth ring:
#
#   slope_hi = high32(dtl_slope[i] * [0x19CEC])
#   page[k]  = clamp((k - 128) << 24 * slope_hi + bias[i], 0, 0xFF00) >> 8
#
# with the slopes at 0x1A6B4 and the biases at 0x1AA9C, 250 dwords each and
# adjacent (0x1AA9C - 0x1A6B4 = 0x3E8 = 250*4). Both read as all-ones in the
# image: they are placeholders filled from HIGH.DTL at load, so they have to
# be captured. This is the projection itself - if the port's ring_page_table
# matches these, the depth/row mapping is right and the silhouette gap is
# somewhere else.
# The five tables, at the absolute addresses their consumers use against a
# file loaded at 0x19EE0. 0000D9BB reads the lateral increment from 0x19EE4,
# 0000D99B the forward increment from 0x1A2CC, 00015ADA/00015B0A the
# projection slope and bias from 0x1A6B4/0x1AA9C, and 000251CA/00024D1B the
# cumulative depth from 0x1AE84.
DTL_TABLES = {
    "dtl_lateral_0x19EE4": 0x19EE4,   # file + 4
    "dtl_forward_0x1A2CC": 0x1A2CC,   # file + 1004
    "dtl_slopes_0x1A6B4":  0x1A6B4,   # file + 2004
    "dtl_biases_0x1AA9C":  0x1AA9C,   # file + 3004
    "dtl_depth_0x1AE84":   0x1AE84,   # file + 4004
}
DTL_SLOPES = 0x1A6B4
DTL_BIASES = 0x1AA9C
PAGE_BYTES = 256

# 0002913C fills the active mission's resource names through a table of 21
# pointers at 0x2A320, each name up to 0xC bytes. Dereferencing them says
# which D<n>/C<n> pair and which palette the captured flight is actually
# using - and that is not guessable: the attract passes fly the FIRST
# catalog's missions in order, and 0.MIS names d1, d4, d3, d2 for the first
# four, so "the demo flies D1" is wrong for every pass but the first.
RESOURCE_NAME_TABLE = 0x2A320
RESOURCE_NAME_COUNT = 0x15
RESOURCE_NAME_BYTES = 0xC

REPLAY_PLAYING = 1

# The marcher's own `ret`. 0000D950 is entered once per frame and finishes by
# copying its last per-column silhouette out to [0x19E60]; 00007AA0 and the
# rear-view pass run after it. Stopping *here* is the difference between a
# capture that is merely frozen and one that is phase-coherent: `stop` at an
# arbitrary instant lands anywhere in the frame, including between the camera
# latch and the silhouette write, and pairs one frame's viewpoint with
# another frame's columns. That is invisible in the shape of the data and
# shows up only as a model that is right in form and wrong in numbers.
MARCHER_RET = 0x0000F317

# QEMU's gdbstub takes linear addresses. Paging is off under the extender
# here - the exec trace's linear PC and the physical address `xp` reads agree
# - so linear = physical = FLAT + flat_address.
def linear(flat_addr):
    return FLAT + flat_addr


def read_resource_names(qmp):
    """The active mission's resource names, straight out of the game."""
    table = u32_table(qmp, FLAT + RESOURCE_NAME_TABLE, RESOURCE_NAME_COUNT)
    names = []
    for ptr in table:
        if not 0 < ptr < 0x80000:
            names.append(None)
            continue
        raw = xp_bytes(qmp, FLAT + ptr, RESOURCE_NAME_BYTES) or b""
        names.append(raw.split(b"\0")[0].decode("latin-1"))
    return names


def read_scalars(qmp):
    out = {}
    for name, (addr, size) in SCALARS.items():
        raw = xp_bytes(qmp, FLAT + addr, size)
        out[name] = int.from_bytes(raw, "little") if raw else None
    return out


# A signature that proves the game's flat image is actually resident. Until it
# is, every read below is uninitialised memory that happens to decode as
# something - the first run of the replay gate matched [0x19ED0] == 1 at 3.5
# seconds, before DOS had finished booting, and captured a frame that was not
# a frame. Check the program is there before believing anything it says.
SIGNATURE_AT = 0x25880
SIGNATURE_LEN = 16


def program_signature():
    path = os.path.join(ROOT, "re", "unpacked", "comanche-flat32.bin")
    with open(path, "rb") as f:
        f.seek(SIGNATURE_AT)
        return f.read(SIGNATURE_LEN)


def wait_for_program(qmp, process, timeout, poll=1.0):
    """Block until the flat image is resident at the expected base."""
    want = program_signature()
    deadline = time.time() + timeout
    while time.time() < deadline:
        if process.poll() is not None:
            print("  qemu exited before the program loaded")
            return False
        if xp_bytes(qmp, FLAT + SIGNATURE_AT, SIGNATURE_LEN) == want:
            print(f"  program resident ({SIGNATURE_AT:#07x} matches the image)")
            return True
        time.sleep(poll)
    print(f"  program never became resident within {timeout:.0f}s")
    return False


def wait_for_flight(qmp, process, timeout, poll=0.5):
    """Block until [0x19ED0] says a replay is playing.

    Without this the samples land wherever the attract cycle happens to be -
    blank between screens, or a full-screen image that looks "painted" and is
    not terrain.
    """
    deadline = time.time() + timeout
    seen = None
    while time.time() < deadline:
        if process.poll() is not None:
            print("  qemu exited while waiting for the flight")
            return False
        raw = xp_bytes(qmp, FLAT + 0x19ED0, 4)
        mode = int.from_bytes(raw, "little") if raw else None
        if mode != seen:
            print(f"  [0x19ED0] = {mode}")
            seen = mode
        if mode == REPLAY_PLAYING:
            return True
        time.sleep(poll)
    print(f"  no replay started within {timeout:.0f}s")
    return False


def sample_frozen(qmp, when):
    # The caller has already stopped the machine. Every read below is a separate QMP round trip
    # and the game runs at tens of frames a second, so an unfrozen capture
    # mixes the camera of one frame with the silhouettes of another - which
    # is structurally invisible and shows up only as a model that is right in
    # shape and wrong in numbers, with the error growing along the march
    # because a slightly different bearing diverges with distance.
    state = read_scalars(qmp)
    state["replay_cursor_0x19ECC"] = (
        int.from_bytes(xp_bytes(qmp, FLAT + 0x19ECC, 4) or b"\0", "little"))
    count = state["run_count_0x19E4C"] or 0
    if not 0 < count <= 4096:
        print(f"  {when:5.1f}s: run count {count} - the transfer has not run yet")
        return None
    if state["replay_mode_0x19ED0"] != REPLAY_PLAYING:
        print(f"  {when:5.1f}s: [0x19ED0] = {state['replay_mode_0x19ED0']} - "
              "not inside a replay flight")
    print(f"  {when:5.1f}s: {count} runs, camera "
          f"x={state['camera_x_0x19CD4']:#010x} y={state['camera_y_0x19CD8']:#010x} "
          f"angle={state['view_angle_0x19D04']:#010x} alt={state['altitude_0x19DFC']}")

    lengths_flags = u32_table(qmp, FLAT + RUN_LEN_AND_FLAGS, count)
    dump = {
        "seconds": when,
        "state": state,
        # Top level as well as in state: gen-marcher-oracle.py reads them off
        # the dump itself to decide whether this frame can pin flt_angle.
        "view_variant_0x19D86": state.get("view_variant_0x19D86"),
        "view_angle_0x19D00": state.get("view_angle_0x19D00"),
        "runs": [{
            "length": value & 0xFFFF,
            "lead_odd": (value >> 16) & 0xFF,
            "trail_odd": (value >> 24) & 0xFF,
        } for value in lengths_flags],
        "source_offset": u32_table(qmp, FLAT + RUN_SOURCE, count),
        "source_base_ptr": u32_table(qmp, FLAT + RUN_SOURCE_BASE, count),
        # Both halves: 00007AB7 adds 0x800 entries when [0x19D87] is set.
        "dest_low": u32_table(qmp, FLAT + RUN_DEST, count),
        "dest_high": u32_table(qmp, FLAT + RUN_DEST + 0x800 * 4, count),
        "horizon_0x3CB40": list(xp_bytes(qmp, FLAT + HORIZON, HORIZON_BYTES)),
        "resource_names_0x2A320": read_resource_names(qmp),
        "mfd_handlers_0x19E10": u32_table(qmp, FLAT + 0x19E10, 6),
        # The target view's own camera source, indexed by [0x19D10]:
        # 0x20C6C x, 0x20E74 y, 0x21A25 altitude, 0x21CAF bearing.
        # 0x1E slots, not 16: 00024DA4 makes 1..0x1E targetable and the
        # locked slot is routinely above 16, so a 16-entry capture cannot
        # check the bearing of the object the target view is actually looking
        # at. The bearing/targetability arrays below are already 32.
        "target_x_0x20C6C": u32_table(qmp, FLAT + 0x20C6C, 32),
        "target_y_0x20E74": u32_table(qmp, FLAT + 0x20E74, 32),
        "target_alt_0x21A25": list(xp_bytes(qmp, FLAT + 0x21A25, 32)),
        "target_bear_0x21CAF": list(xp_bytes(qmp, FLAT + 0x21CAF, 32)),
        # 00024DF6 stores the object's on-screen X offset here when it passes
        # the targetability test, and 00019292 skips zero entries when
        # cycling. 0x21C2D is the designator row 00024DC6 stores beside it.
        #
        # These are TRANSIENT per-frame state: 00024BE1 clears the byte and
        # the object pass re-sets it for whatever is on screen this frame. A
        # capture can therefore legitimately read all zeros - one here did,
        # while an earlier one read a latch of 30 - so a run that needs them
        # populated has to keep breaking until [0x19D18] is non-zero rather
        # than conclude the field is dead.
        "target_ok_0x21BAB": list(xp_bytes(qmp, FLAT + 0x21BAB, 32)),
        "target_desig_0x21C2D": list(xp_bytes(qmp, FLAT + 0x21C2D, 32)),
        # 00024D46's lateral and 00024D87's depth, the two the projection
        # v = 128 + lateral / (depth >> 3) divides. Dword arrays are 130*4
        # apart: 0x2085C, 0x20A64, 0x20C6C, 0x20E74 are fields 4,5,6,7 - so
        # these are OBJ_LATERAL and OBJ_DEPTH, and 0x20A64 is also the range
        # 0000D43D latches into [0x19D14].
        "obj_lateral_0x2085C": u32_table(qmp, FLAT + 0x2085C, 32),
        "obj_depth_0x20A64": u32_table(qmp, FLAT + 0x20A64, 32),
        "obj_screen_x_0x22365": list(xp_bytes(qmp, FLAT + 0x22365, 2)),
        # 0002B820 searches this 256-entry, 3-bytes-per-entry palette. It is
        # zero in the image - the mission palette is loaded over it - so the
        # colour matcher cannot be checked without capturing it.
        "match_palette_0x2A680": list(xp_bytes(qmp, FLAT + 0x2A680, 768)),
        "match_range_0x2B810": u32_table(qmp, FLAT + 0x2B810, 2),
    }
    loaded = [n for n in dump["resource_names_0x2A320"] if n]
    if loaded:
        print(f"   resources: {' '.join(loaded[:6])}")
    sil = state.get("silhouette_0x19E60")
    rings_now = state["ring_count_0x19EE0"] or 0
    if sil and 0 < rings_now <= 512:
        dump["ring_silhouettes"] = {
            str(r): list(xp_bytes(qmp, FLAT + sil + r * 256 + 0x20, 192))
            for r in (0, rings_now // 2, rings_now - 1)
        }
    rings = state["ring_count_0x19EE0"] or 0
    if 0 < rings <= 512:
        for name, addr in DTL_TABLES.items():
            dump[name] = u32_table(qmp, FLAT + addr, rings)
        # kept under their old names too, so earlier dumps stay comparable
        dump["dtl_slopes"] = dump["dtl_slopes_0x1A6B4"]
        dump["dtl_biases"] = dump["dtl_biases_0x1AA9C"]
        print(f"   {rings} rings: all five DTL tables captured")
    # Dereference the source bases once - they are pointers, and the offsets
    # above are meaningless without them.
    bases = sorted({p for p in dump["source_base_ptr"] if 0 < p < 0x80000})
    dump["source_base_values"] = {
        f"{p:#07x}": int.from_bytes(xp_bytes(qmp, FLAT + p, 4), "little")
        for p in bases[:16]
    }
    return dump


def save_surface(qmp, base, path):
    """Write the original's 256x256 terrain surface to a file.

    Uses pmemsave rather than xp: the surface is 64 KB and pulling that
    through the monitor's hex text costs megabytes of parsing.

    000055DE fixes the surface at (0x0004CC20 & 0xFFFF0000) = 0x00040000 once
    at startup and never moves it, so the address is not the thing to doubt.
    What varies is whether anything has been DRAWN there: 0xFF is the
    not-painted marker - 00006FEF scans for spans that are not 0xFFFFFFFF and
    only those are transferred - so a sample taken between screens finds the
    visible window blank. Report that rather than writing a file that looks
    like a capture and is not one.
    """
    out = qmp.hmp(f'pmemsave {FLAT + base:#x} {SURFACE_BYTES:#x} '
                  f'"{path.replace(chr(92), "/")}"').strip()
    if out:
        print("   pmemsave:", out)
    if not (os.path.exists(path) and os.path.getsize(path) == SURFACE_BYTES):
        return False
    raw = open(path, "rb").read()
    window = bytearray()
    for row in range(SURFACE_SRC_ROW, SURFACE_SRC_ROW + SURFACE_ROWS):
        window += raw[row * 256:(row + 1) * 256]
    # 0xFF is the only not-painted marker - 00006FEF scans for spans that are
    # not 0xFFFFFFFF. 0x00 is counted out with it only because a cleared
    # surface reads zero; it is not a sky marker. A good terrain frame is
    # ~90% painted, because the sky is drawn into this surface too and only
    # the parts no span reached stay 0xFF. Do not read a high figure as
    # "this is not terrain": that misreading cost a round trip here.
    painted = sum(1 for b in window if b not in (0x00, 0xFF))
    share = painted / len(window)
    print(f"   visible window rows {SURFACE_SRC_ROW}"
          f"..{SURFACE_SRC_ROW + SURFACE_ROWS - 1}: "
          f"{painted}/{len(window)} painted ({share:.1%})")
    if share < 0.05:
        print("   -> blank: this sample is between screens, not a terrain frame")
        os.remove(path)
        return False
    return True


def run_to_breakpoint(gdb_port, flat_addr, timeout=60, qmp=None,
                      want=None, rounds=1):
    """Stop the guest at `flat_addr`, leaving the VM halted for the caller.

    Returns the connected Rsp so the caller can resume; None if the address
    was never reached. Connecting to QEMU's gdbstub pauses the machine by
    itself, so the breakpoint is armed against a stopped guest and there is
    no window where it could be missed.

    `want` is an optional predicate on the stopped machine. Some of what a
    capture wants is per-frame and often absent - the targeting bytes are
    cleared and rebuilt every frame, so a given frame legitimately has none -
    and for those the breakpoint has to be taken repeatedly until the frame
    is the interesting one. That is why the breakpoint stays armed across
    `rounds` stops rather than being cleared after the first.
    """
    addr = linear(flat_addr)
    try:
        gdb = Rsp(gdb_port, timeout=timeout)
    except OSError as exc:
        print(f"  gdbstub connect failed: {exc}")
        return None
    reply = gdb.set_break(addr)
    if reply != "OK":
        print(f"  breakpoint at {addr:#x} refused: {reply!r}")
        gdb.close()
        return None
    print(f"  breakpoint armed at {flat_addr:#07x} (linear {addr:#x}), running")
    for attempt in range(max(1, rounds)):
        # cont_from_break, not cont_until_stop, for every stop after the
        # first. QEMU re-tests a breakpoint at the PC it is resuming from, so
        # a plain continue stops again on the same instruction without the
        # guest advancing a single frame: the predicate below then re-reads
        # one frozen frame `rounds` times and reports that the condition never
        # held. rsp.cont_from_break lifts the breakpoint, steps one
        # instruction, re-arms and continues. work/trace_replay_flight.py
        # already does this; this loop did not, which is why every gate here
        # could only ever succeed if the very first stop happened to satisfy
        # it.
        stop = gdb.cont_until_stop() if attempt == 0 else gdb.cont_from_break(addr)
        if stop is None:
            print(f"  {flat_addr:#07x} not reached within {timeout:.0f}s")
            gdb.clear_break(addr)
            gdb.close()
            return None
        if want is None or want(qmp):
            print(f"  stopped: {stop.split(';')[0]}"
                  + (f" (after {attempt + 1} frames)" if attempt else ""))
            gdb.clear_break(addr)
            return gdb
    print(f"  condition never held in {rounds} frames at {flat_addr:#07x}")
    gdb.clear_break(addr)
    gdb.close()
    return None


def confirm_stopped_at(qmp, flat_addr):
    """Read EIP back through the monitor and check it against the request.

    The gdbstub already said it stopped, but it reports the stop, not the
    address, and a wrong-address stop would silently produce a capture that
    looks phase-coherent and is not. Cross-check through the other channel.
    """
    regs = qmp.hmp("info registers") or ""
    match = re.search(r"EIP=([0-9a-fA-F]{8})", regs)
    if not match:
        print("  could not read EIP back - capturing anyway")
        return True
    eip = int(match.group(1), 16)
    if eip == flat_addr:
        print(f"  EIP={eip:#010x} - at the requested address")
        return True
    print(f"  EIP={eip:#010x}, expected {flat_addr:#010x} - not the breakpoint")
    return False


def cursor_record(qmp):
    raw = xp_bytes(qmp, FLAT + 0x19ECC, 4)
    return int.from_bytes(raw, "little") // 8 if raw else None


def in_cockpit(qmp):
    """True when [0x19D86] is variant 1, the cockpit.

    The attract spends 41% of DEMO1 in the chase and fixed cameras, so an
    ungated marcher capture usually lands in one of them and the oracle
    generator rejects it.
    """
    raw = xp_bytes(qmp, FLAT + 0x19D86, 1)
    return bool(raw) and raw[0] == 1


def has_target(qmp):
    """True when this frame has something targetable.

    00024DFC sets [0x19D18] to the last object that passed the targetability
    test, and 00024BE1 clears the per-object byte every frame, so this is the
    cheapest test for "the object pass found something this frame".
    """
    raw = xp_bytes(qmp, FLAT + 0x19D18, 4)
    return bool(raw) and int.from_bytes(raw, "little") != 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hdd", default=default_hdd())
    parser.add_argument("--at", action="append", type=float, default=[],
                        help="seconds after boot to sample; repeatable")
    parser.add_argument("--seconds", type=float, default=0,
                        help="extra run time after the last sample")
    parser.add_argument("--wait-flight", type=float, default=0, metavar="SECONDS",
                        help="poll [0x19ED0] and sample as soon as a replay "
                             "is playing, giving up after SECONDS")
    parser.add_argument("--settle", type=float, default=2.0,
                        help="seconds to let the flight run before sampling")
    parser.add_argument("--silhouette", action="store_true",
                        help="pmemsave the whole per-ring silhouette region")
    parser.add_argument("--heightmap", action="store_true",
                        help="also pmemsave the 1024x1024 height map")
    parser.add_argument("--shot", action="store_true",
                        help="also screendump the display at the sample")
    parser.add_argument("--surface", action="store_true",
                        help="also pmemsave the 256x256 terrain surface")
    parser.add_argument("--break-at", metavar="FLATADDR", default=None,
                        help="stop the guest at this flat address before "
                             f"sampling (default {MARCHER_RET:#07x} with "
                             "--at-marcher)")
    parser.add_argument("--want-cursor", type=int, default=None,
                        metavar="RECORD",
                        help="take the breakpoint repeatedly until the replay "
                             "cursor [0x19ECC] reaches this RECORD index. "
                             "Records are the replay's own clock - one per "
                             "frame at 00018D15 - so two machines can be "
                             "compared at the same record however differently "
                             "they are paced")
    parser.add_argument("--cockpit", action="store_true",
                        help="keep taking the breakpoint until the view "
                             "variant [0x19D86] is 1, so the capture is a "
                             "cockpit frame gen-marcher-oracle.py accepts")
    parser.add_argument("--with-target", action="store_true",
                        help="keep taking the breakpoint until [0x19D18] is "
                             "non-zero, i.e. this frame found something "
                             "targetable")
    parser.add_argument("--rounds", type=int, default=400,
                        help="how many frames to allow when a gate is set")
    parser.add_argument("--at-marcher", action="store_true",
                        help=f"sample at the marcher's ret ({MARCHER_RET:#07x}), "
                             "so the camera and the silhouettes are the same "
                             "frame's")
    parser.add_argument("--outdir",
                        default=os.path.join(ROOT, "work", "qemu_out"))
    args = parser.parse_args()
    times = sorted(args.at) or [60.0, 75.0, 90.0]
    break_at = None
    if args.break_at is not None:
        break_at = int(args.break_at, 0)
    elif args.at_marcher:
        break_at = MARCHER_RET

    with open(args.hdd + ".geom.json", encoding="utf-8") as f:
        g = json.load(f)
    # Hardcoded ports collide when two captures run at once - the failure is
    # "QMP never came up", which reads like a QEMU fault rather than a busy
    # socket. Overridable, same defaults.
    port = int(os.environ.get("QMP_PORT", 4613))
    gdb_port = int(os.environ.get("GDB_PORT", 4614))
    command = [QEMU, "-M", "pc", "-cpu", "486", "-m", "16",
               "-drive", f"file={args.hdd.replace(chr(92), '/')},format=raw,"
                         "if=none,id=hd0,cache=writeback",
               "-device", f"ide-hd,drive=hd0,bus=ide.0,unit=0,cyls={g['cyls']},"
                          f"heads={g['heads']},secs={g['secs']}",
               "-boot", "c", "-display", "none", "-vga", "std", "-no-reboot",
               "-qmp", f"tcp:127.0.0.1:{port},server=on,wait=off"]
    if break_at is not None:
        command += ["-gdb", f"tcp:127.0.0.1:{gdb_port}"]
    print("$", " ".join(command))
    process = subprocess.Popen(command, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, text=True)
    os.makedirs(args.outdir, exist_ok=True)
    written = []
    try:
        qmp = Qmp(port)
        start = time.time()
        if args.wait_flight:
            print(f"waiting up to {args.wait_flight:.0f}s for a replay flight")
            if not wait_for_program(qmp, process, args.wait_flight):
                return 1
            remaining = args.wait_flight - (time.time() - start)
            if not wait_for_flight(qmp, process, max(remaining, 1.0)):
                return 1
            # A few frames in, so the surface holds a marched frame rather
            # than whatever the transition left.
            time.sleep(args.settle)
            times = [round(time.time() - start, 1)]
        for when in times:
            wait = when - (time.time() - start)
            if wait > 0:
                time.sleep(wait)
            if process.poll() is not None:
                print("qemu exited early")
                break
            # Freeze for the whole capture. Every read is a separate QMP
            # round trip and the game runs at tens of frames a second, so an
            # unfrozen capture mixes one frame's camera with another frame's
            # silhouettes. That is invisible in the structure and shows up
            # only as a model that is right in shape and wrong in numbers,
            # with the error growing along the march - a slightly different
            # bearing diverges with distance.
            gdb = None
            if break_at is not None:
                want = None
                rounds = 1
                if args.want_cursor is not None:
                    target = args.want_cursor

                    def want(q, _t=target):
                        got = cursor_record(q)
                        return got is not None and got >= _t
                    rounds = args.rounds
                elif args.cockpit:
                    want = in_cockpit
                    rounds = args.rounds
                elif args.with_target:
                    want = has_target
                    rounds = args.rounds
                gdb = run_to_breakpoint(gdb_port, break_at, qmp=qmp,
                                        want=want, rounds=rounds)
                if gdb is None:
                    continue
                if not confirm_stopped_at(qmp, break_at):
                    gdb.cmd("D")
                    gdb.close()
                    qmp.hmp("cont")
                    continue
            else:
                qmp.hmp("stop")
            try:
                dump = sample_frozen(qmp, when)
                if dump is None:
                    continue
                surface = dump["state"]["surface_0x19E70"]
                if args.surface and surface:
                    raw = os.path.join(args.outdir, f"surface-{int(when)}.bin")
                    if save_surface(qmp, surface, raw):
                        dump["surface_file"] = os.path.basename(raw)
                        dump["surface_geometry"] = {
                            "bytes": SURFACE_BYTES, "pitch": 256,
                            "src_row": SURFACE_SRC_ROW,
                            "src_col": SURFACE_SRC_COL,
                            "rows": SURFACE_ROWS,
                            "screen_anchor": SCREEN_ANCHOR,
                        }
                        print("   ->", raw)
                pages = dump["state"]["page_buffer_0x19E5C"]
                rings = dump["state"]["ring_count_0x19EE0"] or 0
                if args.surface and pages and 0 < rings <= 512:
                    raw = os.path.join(args.outdir, f"pages-{int(when)}.bin")
                    size = rings * PAGE_BYTES
                    qmp.hmp(f'pmemsave {FLAT + pages:#x} {size:#x} '
                            f'"{raw.replace(chr(92), "/")}"')
                    if os.path.exists(raw) and os.path.getsize(raw) == size:
                        dump["pages_file"] = os.path.basename(raw)
                        dump["pages_geometry"] = {"rings": rings,
                                                  "page_bytes": PAGE_BYTES}
                        print("   ->", raw)
                sil = dump["state"].get("silhouette_0x19E60")
                if args.silhouette and sil and 0 < rings <= 512:
                    raw = os.path.join(args.outdir,
                                       f"silhouettes-{int(when)}.bin")
                    size = (rings + 1) * 256
                    qmp.hmp(f'pmemsave {FLAT + sil:#x} {size:#x} '
                            f'"{raw.replace(chr(92), "/")}"')
                    if os.path.exists(raw) and os.path.getsize(raw) == size:
                        dump["silhouettes_file"] = os.path.basename(raw)
                        print("   ->", raw)
                hmap = dump["state"]["height_map_0x19E6C"]
                if args.heightmap and hmap:
                    raw = os.path.join(args.outdir,
                                       f"heightmap-{int(when)}.bin")
                    qmp.hmp(f'pmemsave {FLAT + hmap:#x} {1 << 20:#x} '
                            f'"{raw.replace(chr(92), "/")}"')
                    if os.path.exists(raw) and os.path.getsize(raw) == 1 << 20:
                        dump["heightmap_file"] = os.path.basename(raw)
                        print("   ->", raw)
                if args.shot:
                    shot = os.path.join(args.outdir, f"screen-{int(when)}.ppm")
                    qmp.hmp(f'screendump "{shot.replace(chr(92), "/")}"')
                    dump["screen_file"] = os.path.basename(shot)
                    print("   ->", shot)
                path = os.path.join(args.outdir, f"marcher-{int(when)}.json")
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(dump, f, indent=1)
                written.append(path)
                print("   ->", path)
            finally:
                if gdb is not None:
                    # Detach rather than just closing: on detach QEMU resumes
                    # the guest, and the `cont` after it is the belt to that
                    # brace - harmless if the machine is already running.
                    gdb.cmd("D")
                    gdb.close()
                qmp.hmp("cont")
        if args.seconds > 0:
            time.sleep(args.seconds)
        qmp.hmp("quit")
    finally:
        if process.poll() is None:
            process.kill()
    if not written:
        print("no sample found a built run list - try later --at values")
        return 1
    print(f"\nwrote {len(written)} dump(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
