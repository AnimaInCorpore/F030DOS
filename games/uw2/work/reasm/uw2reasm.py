#!/usr/bin/env python3
"""Run the shared Borland MZ reassembly harness against UW2.EXE.

The encoder/verifier is shared with the mature UW1 project.  UW2 supplies the
binary-specific paths, Ghidra skew, and data guard here so those assumptions
remain explicit and auditable.
"""

from __future__ import annotations

import importlib.util
import json
import os
import struct
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
UW1_HARNESS = ROOT.parent / "F030Underworld" / "work" / "reasm" / "uwreasm.py"

spec = importlib.util.spec_from_file_location("uw1_reasm", UW1_HARNESS)
if spec is None or spec.loader is None:
    raise RuntimeError(f"cannot load shared harness: {UW1_HARNESS}")
uw = importlib.util.module_from_spec(spec)
spec.loader.exec_module(uw)

uw.SRC = str(ROOT / "work" / "extracted" / "D3" / "UW2.EXE")
uw.OUT = str(ROOT / "work" / "reasm" / "out")
uw.GHIDRA_FNS = str(ROOT / "work" / "ghidra_export" / "functions.txt")
uw.NASM = "/opt/homebrew/bin/nasm"
uw.PROLOGUE = (uw.PROLOGUE
               .replace("UW.EXE -- Ultima Underworld: The Stygian Abyss (1992)",
                        "UW2.EXE -- Ultima Underworld II: Labyrinth of Worlds (1993)")
               .replace("work/reasm/uwreasm.py", "work/reasm/uw2reasm.py")
               .replace("work/expanded/UW.EXE", "work/extracted/D3/UW2.EXE")
               .replace("DGROUP at 0x5f2f0", "DGROUP at 0x68e80")
               .replace("the 667 INT 3Fh", "the 1,005 INT 3Fh"))


# `(code_base, table_file_offset, entry_count, label)` for the indirect near
# dispatches in the FBOV units.  The table words are offsets from that unit's
# code base; their targets are mechanically verified case-entry addresses.
OVERLAY_SWITCH_TABLES = (
    (0x072B70, 0x0731B7, 4, "raster submode"),
    (0x072B70, 0x0731BF, 4, "raster mode"),
    (0x072B70, 0x073438, 4, "terrain mode"),
    (0x072B70, 0x073CA3, 5, "polygon mode"),
    (0x0745A0, 0x075E1B, 42, "conversation opcode"),
    (0x0745A0, 0x07682A, 6, "conversation submode"),
    (0x076990, 0x076CCB, 11, "shape mode"),
    (0x07A280, 0x07B2EC, 6, "object mode"),
    (0x07A280, 0x07B833, 8, "object subtype"),
    (0x07E680, 0x07E789, 6, "input mode"),
    (0x07E680, 0x07FCAD, 4, "page mode"),
    (0x07E680, 0x07FCB5, 12, "page subtype"),
    (0x0835F0, 0x083F2D, 6, "window mode"),
    (0x0835F0, 0x084E9B, 7, "window subtype"),
    (0x0835F0, 0x0857B5, 13, "character mode"),
    (0x0835F0, 0x085A46, 4, "character submode"),
    (0x0835F0, 0x085B5E, 4, "character action"),
    (0x0835F0, 0x08682C, 5, "inventory mode"),
    (0x0835F0, 0x086AC0, 5, "inventory subtype"),
    (0x089400, 0x089587, 4, "font mode"),
    (0x08A120, 0x08A1C3, 4, "video mode"),
    (0x08BEA0, 0x08BF2D, 4, "color mode"),
    (0x08BF40, 0x08C0C0, 17, "character class"),
    (0x08D900, 0x08DFBA, 12, "animation mode"),
    (0x08EF60, 0x090154, 5, "resource mode"),
    (0x08EF60, 0x09015E, 5, "resource subtype"),
    (0x090AE0, 0x091578, 12, "terrain subtype"),
    (0x0935E0, 0x0937F8, 13, "palette mode"),
    (0x094420, 0x094DB8, 15, "object class"),
    (0x094420, 0x094DD6, 4, "object subclass"),
    (0x094420, 0x0953A6, 6, "object action"),
    (0x094420, 0x095E67, 4, "object flags"),
    (0x094420, 0x095FF0, 13, "object state"),
    (0x0970B0, 0x097611, 11, "spell mode"),
    (0x0970B0, 0x097627, 13, "spell subtype"),
    (0x097C80, 0x0989BC, 5, "save mode"),
    (0x098DC0, 0x0992F5, 5, "save subtype"),
    (0x098DC0, 0x099697, 6, "save action"),
    (0x099940, 0x09A465, 8, "level mode"),
    (0x09B100, 0x09B9FF, 6, "level subtype"),
    (0x09CE00, 0x09D121, 15, "conversation state"),
    (0x09CE00, 0x09E7B4, 8, "conversation mode"),
    (0x09CE00, 0x09EA85, 16, "conversation subtype"),
    (0x09ECB0, 0x09F818, 4, "spell state"),
    (0x09ECB0, 0x09FE36, 6, "spell subtype"),
    (0x09ECB0, 0x0A0645, 14, "spell target"),
    (0x0A1660, 0x0A193D, 8, "trap mode"),
    (0x0A1660, 0x0A318C, 25, "trap subtype"),
    (0x0A1660, 0x0A38A4, 61, "trap action"),
    (0x0A4740, 0x0A5026, 4, "file mode"),
)

# Small typed-data islands immediately adjacent to overlay code/switch tables.
# These are separate from OVERLAY_SWITCH_TABLES because they are not the table
# consumed by the nearby indirect jump; their bounds are established by the
# next real entry or by the adjacent dispatch table.
OVERLAY_EXTRA_DATA = (
    (0x076CC3, 0x076CCB, "embedded shape lookup table"),
    (0x08DFA8, 0x08DFBA, "embedded animation lookup table"),
    (0x0975F1, 0x097611, "embedded spell lookup table"),
    (0x0989C6, 0x0989D0, "embedded save lookup table"),
    (0x09E7C4, 0x09E7FF, "embedded conversation lookup table"),
)


def known_data(cont):
    """Proven non-code regions; descent is forbidden from entering them."""
    guards = [
        (0, cont.hdr_size,
         "MZ header, relocation table and header slack"),
        (0x669A0, 0x670B0,
         "Borland overlay-manager data segment"),
        (0x670E0, 0x68E80,
         "packed INT 3Fh overlay-thunk block"),
        (0x670B0, 0x670E0,
         "overlay-manager executable name and metadata"),
        (0x66B40, 0x670B0,
         "FBOV exeinfo segment table"),
        (0x25247, 0x25360,
         "zero-filled hole before the adjacent test-string data"),
        (0x251A1, 0x25247,
         "zero-filled hole after the timer helper and before test-string data"),
        (0x24154, 0x24195,
         "zero-filled hole between interrupt setup helpers"),
        (0x24D35, 0x24D40,
         "zero-filled hole before the adjacent interrupt return"),
        (0x24D41, 0x24D64,
         "zero-filled hole before the next interrupt helper"),
        (0x0D462, 0x0D470,
         "zero-filled alignment hole between VM2 helpers"),
        (0x11514, 0x11520,
         "zero-filled startup padding before the program entry"),
        (0x0E1C4, 0x0E1D0,
         "zero-filled hole between raster helpers"),
        (0x03644, 0x03650,
         "zero-filled graphics-helper padding before far stubs"),
        (0x09616, 0x09620,
         "zero-filled hole between decoder helpers"),
        (0x100DB, 0x100F0,
         "zero-filled hole before the VM2 decoder table"),
        (0x100F0, 0x10100,
         "six-entry VM2 decoder dispatch table"),
        (0x145A5, 0x145D5,
         "embedded formatter dispatch/constant table before the next routine"),
        (0x1B854, 0x1B882,
         "embedded text/constant table before the next video helper"),
        (0x13A48, 0x13A74,
         "embedded formatter constant table before the next helper"),
        (0x25364, 0x25568,
         "zero-filled hole between the test string and the next code block"),
        (0x3A03C, 0x3E460,
         "embedded lookup/palette data and zero padding before the 4b66 tables"),
        (0x3E460, 0x3EC30,
         "embedded descending lookup tables in the 4b66 data segment"),
        (0x3EC30, 0x3F750,
         "embedded ramp lookup tables and zero padding"),
        (0x3F750, 0x3FF40,
         "embedded descending lookup table, followed by zero padding"),
        (0x3FF40, 0x52B02,
         "zero-filled hole after lookup tables and before embedded geometry"),
        (0x44C3, 0x49ED,
         "embedded indexed graphics/palette data before the decoder helpers"),
        (0x4BA4, 0x5824,
         "zero-filled hole between the graphics helper and the next code block"),
        (0x52B02, 0x5519C,
         "embedded geometry metadata and padded table area before polygon records"),
        (0x5519C, 0x5B660,
         "embedded polygon/graphics-record pool; repeated 0x58/0xbc grammar"),
        (0x5B660, 0x5D679,
         "zero-filled hole after the embedded graphics-record pool"),
        (0x5D679, 0x610BD,
         "embedded graphics/config tables, path literal and FF-filled slack"),
        (0x610BD, 0x639D0,
         "zero-filled hole before the keyboard/UI/wave tables"),
        (0x639D0, 0x64620,
         "keyboard tables, UI strings and sine/wave lookup tables"),
        (0x64620, 0x669A0,
         "zero-filled gap and compact table before the overlay-manager data"),
        (0x36A1, 0x373C,
         "error string, signature word and zero-filled slack between helpers"),
        (0x3620C, 0x3621D,
         "shape/format switch pointer table plus its one-byte alignment pad"),
        (0x362FC, 0x3631C,
         "compact shape/format metadata table before the next function"),
        (0x39B69, 0x39B72,
         "EMS-manager signature/string bytes between adjacent routines"),
        (0x22CAA, 0x22CB6,
         "zero-filled interrupt-handler gap before the next real entry"),
        (0x3BD0, 0x3BD4,
         "four-byte alignment gap before the fixed-point helper"),
        (0x6CD5, 0x6CD6,
         "one-byte alignment gap before the adjacent clipping helper"),
        (0x247A5, 0x247B0,
         "interrupt-handler padding before the keyboard buffer helper"),
        (0x4211, 0x4218,
         "four-entry raster callback table and alignment bytes"),
        (0x93BD, 0x93E0,
         "zero-filled and nibble-constant table before the graphics decoder"),
        (0x242C5, 0x242C6,
         "one-byte alignment gap before the interrupt callback"),
        (0x242F3, 0x24300,
         "zero-filled interrupt-handler gap before the CPU probe"),
        (0x14EC3, 0x14EC5,
         "two-byte alignment gap after the DOS dispatch stubs"),
        (0xA169, 0xA170,
         "zero-filled gap between the divide interrupt and VM2 helpers"),
        (0x1463D, 0x1464C,
         "zero-filled alignment hole before the following DOS helper"),
        (0x21F22, 0x21F4A,
         "embedded status/terrain constant table before the next routine"),
        (0x1D1B3, 0x1D1CF,
         "embedded display-mode constant table before the next routine"),
        (0x2AFC0, 0x2AFD8,
         "embedded geometry constant table before the next routine"),
        (0x16777, 0x1678F,
         "embedded interpolation constant table before the next routine"),
        (0xF5F6, 0xF600,
         "zero-filled alignment hole between fixed-point helpers"),
        (0x15030, 0x15047,
         "runtime-overlay error string before its DOS write helper"),
        (0x2483D, 0x24844,
         "zero-filled alignment hole before the timer callback"),
        (0x24851, 0x24860,
         "zero-filled alignment hole before the next mouse helper"),
        (0x893D, 0x893E,
         "one-byte alignment hole before the final graphics thunk"),
        (0x322FB, 0x32315,
         "compact return/constant table before the next video helper"),
        (0x24871, 0x24885,
         "zero-filled alignment hole between mouse helpers"),
        (0xE878, 0xE880,
         "zero-filled alignment hole between pixel helpers"),
        (0x2477A, 0x24780,
         "alignment/data bytes before the input callback"),
        (0x247E7, 0x247F0,
         "zero-filled alignment hole before the adjacent interrupt stubs"),
        (0x79F5, 0x7A0E,
         "embedded scanline offset table before the next helper"),
        (0x2A706, 0x2A71A,
         "embedded mode constant table before the next raster routine"),
        (0x1BC80, 0x1BC8A,
         "embedded five-entry lookup table before the next routine"),
        (0x246BD, 0x246C8,
         "compact mouse/keyboard constant table between helpers"),
        (0x2783F, 0x2784B,
         "embedded mouse-mode lookup table before the next routine"),
        (0x29127, 0x2912F,
         "embedded four-entry input lookup table before the next routine"),
        (0x31309, 0x31319,
         "embedded input-mode lookup table before the next routine"),
        (0x32229, 0x32231,
         "embedded four-entry video lookup table before the next routine"),
        (0x34152, 0x34164,
         "embedded keyboard-mode lookup table before the next routine"),
        (0x34D0C, 0x34D14,
         "embedded four-entry path lookup table before the next routine"),
        (0x38E01, 0x38E09,
         "PATH string and terminator after the preceding DOS helper"),
        (0x2434B, 0x24350,
         "zero-filled alignment hole before the keyboard stubs"),
        (0x2436C, 0x24370,
         "zero-filled alignment hole before the input callback"),
        (0x24408, 0x24410,
         "zero-filled alignment hole before the interrupt stubs"),
        (0x24576, 0x24580,
         "zero-filled alignment hole before the character helper"),
        (0x35B1, 0x35B2,
         "one-byte alignment gap before the following helper"),
        (0x369F, 0x36A1,
         "adjacent return/padding bytes before the following data boundary"),
        (0x3D31, 0x3D32,
         "one-byte alignment gap before the following helper"),
        (0x3DF4, 0x3DF8,
         "zero-filled gap after the preceding far return"),
        (0x4BA0, 0x4BA4,
         "zero-filled gap before the following graphics helper"),
        (0x62E5, 0x62EA,
         "empty-return padding between VGA raster helpers"),
        (0x6836, 0x6837,
         "return padding between adjacent graphics helpers"),
        (0x6855, 0x6856,
         "one-byte alignment gap before the following helper"),
        (0x6DAB, 0x6DAC,
         "one-byte alignment gap before the following helper"),
        (0x6F03, 0x6F04,
         "one-byte alignment gap before the following helper"),
        (0x7051, 0x7052,
         "one-byte alignment NOP before the following helper"),
        (0x7A3F, 0x7A44,
         "zero-filled gap before the following helper"),
        (0x89BF, 0x89C0,
         "one-byte alignment gap before the following helper"),
        (0x8F83, 0x8F84,
         "one-byte alignment gap before the following graphics path"),
        (0x919F, 0x91A0,
         "one-byte alignment gap before the common graphics body"),
        (0x933A, 0x933C,
         "zero-filled gap before the following edge helper"),
        (0x954B, 0x954C,
         "return padding before the following graphics helper"),
        (0x99BB, 0x99C0,
         "zero-filled gap before the following VM2 helper"),
        (0xC3BB, 0xC3C0,
         "zero-filled gap before the following helper"),
        (0xC49A, 0xC49C,
         "zero-filled alignment gap between helpers"),
        (0xD04D, 0xD04E,
         "one-byte alignment gap before the following VM2 helper"),
        (0xD0AC, 0xD0B0,
         "zero-filled gap before the following VM2 handler"),
        (0xD448, 0xD44A,
         "zero-filled gap before the following VM2 helper"),
        (0xD798, 0xD799,
         "one-byte branch/alignment NOP in the renderer loop"),
        (0xD7E7, 0xD7E8,
         "one-byte branch/alignment NOP in the renderer loop"),
        (0xD85B, 0xD85C,
         "one-byte branch/alignment NOP in the renderer loop"),
        (0xD8AB, 0xD8AC,
         "one-byte branch/alignment NOP in the renderer loop"),
        (0xD91C, 0xD91D,
         "one-byte branch/alignment NOP in the renderer loop"),
        (0xD968, 0xD969,
         "one-byte branch/alignment NOP in the renderer loop"),
        (0xD9D6, 0xD9D7,
         "one-byte branch/alignment NOP in the renderer loop"),
        (0xDA23, 0xDA24,
         "one-byte branch/alignment NOP in the renderer loop"),
        (0xDAAE, 0xDAB0,
         "zero-filled gap before the following fixed-point helper"),
        (0xDEEC, 0xDEF0,
         "zero-filled gap before the following fixed-point helper"),
        (0xE2AA, 0xE2AB,
         "one-byte branch/alignment NOP in the fixed-point helper"),
        (0xE2B3, 0xE2B4,
         "one-byte branch/alignment NOP in the fixed-point helper"),
        (0xE2BE, 0xE2BF,
         "one-byte alignment gap before the following helper"),
        (0xE31A, 0xE31C,
         "zero-filled alignment gap between fixed-point helpers"),
        (0xE343, 0xE345,
         "zero-filled alignment gap between fixed-point helpers"),
        (0xE562, 0xE566,
         "zero-filled alignment gap between pixel helpers"),
        (0x1184B, 0x1184C,
         "far-return padding before the following helper"),
        (0x14BF9, 0x14C00,
         "zero-filled gap before the following DOS helper"),
        (0x228F1, 0x228F2,
         "one-byte alignment gap before the following interrupt helper"),
        (0x2412B, 0x24130,
         "zero-filled gap between interrupt helpers"),
        (0x24277, 0x24280,
         "zero-filled interrupt-handler alignment gap"),
        (0x242A0, 0x242A4,
         "zero-filled gap before the following interrupt helper"),
        (0x24B5C, 0x24B60,
         "zero-filled gap between interrupt helpers"),
        (0x24D29, 0x24D30,
         "zero-filled gap before the following interrupt helper"),
        (0x25360, 0x25364,
         "embedded test-string data before the following guarded hole"),
        (0x25568, 0x2556A,
         "compact constant/alignment bytes before the following helper"),
        (0x38F22, 0x38F23,
         "one-byte branch/alignment NOP before the following EMS helper"),
        (0x390AC, 0x390AD,
         "one-byte branch/alignment NOP in the EMS helper block"),
        (0x390C8, 0x390C9,
         "one-byte branch/alignment NOP in the EMS helper block"),
        (0x3915F, 0x39160,
         "one-byte branch/alignment NOP in the EMS helper block"),
        (0x393A3, 0x393A4,
         "one-byte branch/alignment NOP in the EMS helper block"),
        (0x39637, 0x39638,
         "one-byte branch/alignment NOP in the EMS helper block"),
        (0x39B0C, 0x39B0E,
         "return padding before the following EMS helper"),
        (0x39B91, 0x39B92,
         "one-byte branch/alignment NOP in the EMS helper block"),
        (0x39BCC, 0x39BCD,
         "one-byte branch/alignment NOP in the EMS helper block"),
        (0x39C36, 0x39C37,
         "one-byte branch/alignment NOP in the EMS helper block"),
        (0x39C42, 0x39C43,
         "one-byte branch/alignment NOP in the EMS helper block"),
        (0x39EE1, 0x39EE2,
         "one-byte branch/alignment NOP in the EMS helper block"),
        (0x39FC6, 0x39FC7,
         "one-byte branch/alignment NOP in the EMS helper block"),
        (0x39FEE, 0x39FEF,
         "one-byte branch/alignment NOP in the EMS helper block"),
        (0x10100, 0x11000,
         "15 x 256 palette-remap/shading LUT; row 0 is identity"),
        (0x11000, 0x110FE,
         "zero-filled gap between the palette LUT and the next VM2 handler"),
        (0x68E80, cont.image_end,
         "DGROUP initialised data + BSS, base = header + (0x6608 << 4)"),
    ]

    # Every FBOV unit carries a relocation/fixup tail after its code bytes;
    # paragraph padding also occurs between units.  The resident exeinfo table
    # gives the exact pool offsets and lengths, so keep these bytes typed data
    # without hard-coding a second copy of the overlay directory here.
    guards.append((cont.image_end, cont.pool_off,
                   "FBOV overlay-pool header"))
    units = []
    for i in range(cont.fbov_segnum):
        seg, _size, typ, _flags = struct.unpack_from(
            "<4H", cont.data, 0x66B40 + i * 8)
        if typ != 3:
            continue
        stub = 0x2E00 + (seg << 4)
        off = struct.unpack_from("<I", cont.data, stub + 4)[0]
        code, fix, _nent = struct.unpack_from("<HHH", cont.data, stub + 8)
        lo = cont.pool_off + off
        units.append((lo, lo + code, lo + code + fix, i))
    units.sort()
    cursor = cont.pool_off
    for lo, code_end, unit_end, row in units:
        if cursor < lo:
            guards.append((cursor, lo,
                           "paragraph padding between FBOV overlay units"))
        if code_end < unit_end:
            guards.append((code_end, unit_end,
                           "FBOV overlay-unit relocation/fixup table"))
        cursor = max(cursor, unit_end)
    if cursor < len(cont.data):
        guards.append((cursor, len(cont.data),
                       "trailing paragraph padding after the FBOV pool"))
    for _base, table, count, label in OVERLAY_SWITCH_TABLES:
        guards.append((table, table + 2 * count,
                       "FBOV indirect switch table: " + label))
    guards.extend(OVERLAY_EXTRA_DATA)
    return guards


# These unresolved islands contain an unmistakable Borland near-function
# prologue (`push bp; mov bp,sp`) at each listed offset.  Keep the addresses
# explicit so a future binary change cannot silently turn a byte-pattern scan
# into a new code claim.
EXTRA_CODE_SEEDS = (
    0x01ECA5, 0x021F4A, 0x025181, 0x02912F, 0x02BA41,
    0x034164, 0x034D14, 0x03631C, 0x038E09,
    0x072B70, 0x075E6F, 0x076836, 0x076990, 0x076CE1,
    0x077EF0, 0x07A240, 0x07BCE0, 0x07BE50, 0x07DCE0,
    0x07DFA0, 0x07E680, 0x0835B0, 0x085B66, 0x086836,
    0x086ACA, 0x088940, 0x089400, 0x08A120, 0x08A1CB,
    0x08A2F0, 0x08A7C0, 0x08ABE0, 0x08BEA0, 0x08BF40,
    0x08D900, 0x090AE0, 0x092B90, 0x092C20, 0x092C40,
    0x092C60, 0x094DDE, 0x0953B2, 0x095E6F, 0x09600A,
    0x096460, 0x096DC0, 0x098DB0, 0x098DC0, 0x0996A3,
    0x099930, 0x099940, 0x09A5A0, 0x09CDF0, 0x09D13F,
    0x0A0661, 0x0A0F10, 0x0A0F40, 0x0A391E, 0x0A4740,
    # Overlay entry points and branch arms left outside the exported Ghidra
    # starts; each was checked against its ret-delimited routine or switch
    # body before being promoted.
    0x071BD0, 0x076C39, 0x076C40, 0x076C47, 0x07B843, 0x07D49A, 0x07D696,
    0x084EA9, 0x0871CE, 0x08958F, 0x094420, 0x0970B0,
    0x097508, 0x097510, 0x097518, 0x097521, 0x09752C, 0x097718,
    0x0989D0, 0x09DC58,
    0x09F820,
    0x09F883, 0x0A1640, 0x0A1660, 0x0A2058,
    # Orphaned prologues in short residual code runs; each was checked
    # against its complete surrounding routine before being promoted.
    0x0033E5, 0x0034B5, 0x0035B2, 0x00876C, 0x00E2BF,
    0x011D3A, 0x012476, 0x012920, 0x012B27, 0x012BA3,
    0x012BBF, 0x0135C2, 0x01D1CF, 0x01F8C7, 0x021493,
    0x024DB4, 0x027AB2, 0x035EA0,
    # VGA raster bodies immediately after the segment-1344 Ghidra tail;
    # repeated hardware setup and ret-delimited bodies establish these starts.
    0x0062EA, 0x00635D, 0x006366, 0x0063D0, 0x006440, 0x006487,
    0x0064C9, 0x006565, 0x0065E3, 0x006623, 0x006688,
    # Runtime-selected VGA body and its two adjacent helper entries; the
    # selector is a DGROUP pointer written during graphics initialisation.
    0x007311, 0x007776, 0x007791,
    # Adjacent clipper/geometry bodies separated by real returns.
    0x005A8F, 0x005AEC, 0x005C1E,
    # Fixed-point renderer/math bodies after alignment padding.
    0x00DAB0, 0x00DEF0, 0x00E07A,
    # Shape/format handler following the two statically verified dispatches.
    0x036067,
    # Alternate shape/format case bodies converging on the common epilogue;
    # the pointer table between them is guarded separately above.
    0x0360B4, 0x0360F9, 0x036118, 0x03615E, 0x03616F,
    0x036184, 0x03619C, 0x0361A9, 0x0361C2, 0x0361D9,
    0x03621D, 0x036260,
    # Event/message builder continuation ending at a real far return.
    0x0310D0,
    0x03116E,
    # Status/terrain switch case bodies, all ending at the shared cleanup.
    0x01B691, 0x01B698, 0x01B69F, 0x01B6C2, 0x01B6E5,
    0x01B6EC, 0x01B708, 0x01B70F, 0x01B716, 0x01B7C8,
    0x01B838, 0x01B83E,
    # EMS/extended-memory manager helpers separated by real returns and a
    # far-jump terminator; the signature bytes are guarded above.
    0x0399B4, 0x0399E3, 0x039A07, 0x039A13, 0x039ABA,
    0x039AE9, 0x039AF6, 0x039B0E,
    # VM2 stream-consuming record builder immediately before the verified
    # 0xaaf3 handler entry; both branches converge on its existing cleanup.
    0x00AA0F,
    # Polygon edge-table callbacks and interpolation helpers selected through
    # the runtime table at 0x448a; the one-byte gap before 0x6cd6 is guarded.
    0x006C25, 0x006C4B, 0x006C55, 0x006C5D, 0x006C98,
    # UI slot-state switch arms selected by the 0x34037 table.
    0x0340A5, 0x0340C7, 0x0340DD, 0x0340DF, 0x034121,
    # UI/page-state switch arms selected by the 0x34c10 table.
    0x034C2C, 0x034C3D, 0x034C85,
    # DOS command-line/environment helper after the dispatch stubs.
    0x014EC5,
    # Timer/clock helpers and the following VM2 control entry.
    0x01232D,
    0x00A170, 0x00A17E, 0x00A192, 0x00A1D1,
    # Planar VGA blitter body following the preceding scanline helper.
    0x00404C,
    # Video/page-state switch arms selected by the 0x1b21d table.
    0x01B259, 0x01B28B, 0x01B2BD, 0x01B2C3, 0x01B2C9,
    0x01B2CF,
    # EMS page-copy helper in the overlay-manager code segment.
    0x039830,
    # Interrupt wrapper after the zero-filled gap at 0x22caa.
    0x022CB6,
    # Fixed-point setup helper after the four-byte alignment gap.
    0x003BD4,
    # Remaining display-mode switch arms from the bounded 0x1d079 table.
    0x01D0C1, 0x01D0D3, 0x01D0E5, 0x01D0FA, 0x01D104,
    # Raster setup body immediately after the prior return.
    0x00DCE5,
    # Keyboard interrupt and adjacent raster callback entries.
    0x02475E, 0x004218, 0x004242,
    # Command-line/parameter helpers and small graphics setup entries.
    0x012A71, 0x012A94, 0x006878, 0x00688A, 0x00689C, 0x0068AE,
    0x004329, 0x004B61, 0x004B7A,
    # Clipping boundary arms selected by the four-way outcode dispatch.
    0x006D6E, 0x006D73, 0x006D8C, 0x006D91,
    # Graphics decoder variant with the preceding call prefix.
    0x0093E0,
    # CPU/interrupt support callback and page-state helpers.
    0x0242C6, 0x024499, 0x02449D, 0x0244A1, 0x0244A5,
    0x038CC4, 0x038CDC,
    # Extended-memory validation and formatter helper entries.
    0x0395AA, 0x004ABF, 0x031EBD, 0x031EBF, 0x031ECF,
    0x031ED1, 0x031EDE, 0x031EE0, 0x0392AB,
    # Fixed-point/VM2 support helpers around the decoder table.
    0x0100CD, 0x0100D4,
    # Graphics and interrupt support entries separated by the guarded gaps.
    0x004329, 0x0243BC, 0x00D08B,
    # Formatter switch arms selected through the 22-entry table at 0x1369b.
    0x0136A7, 0x0136AD, 0x0136C1, 0x0136C7, 0x0136CD,
    0x0136D3, 0x0136D9, 0x0136DF, 0x0136EC, 0x0136F1,
    0x0136F6, 0x0136FB, 0x013750, 0x013756, 0x01376D,
    0x01378D, 0x0137BB, 0x0137BE, 0x013822, 0x013828,
    0x01387E, 0x0138BC,
    # Geometry/bitmap switch arms selected by bounded near-jump tables.
    0x0141DE, 0x0141E9, 0x0141F4, 0x014204, 0x01420A,
    0x014212, 0x014226, 0x014229, 0x01424A, 0x014257,
    0x014264, 0x0142A2, 0x0142A9, 0x0142B5, 0x0142B9,
    0x0142BD, 0x0142D7, 0x014353, 0x0143A3, 0x0143C3,
    0x0143FF, 0x014539,
    0x02A5D6, 0x02A604, 0x02A63B, 0x02A672, 0x02A69F,
    0x02A6B9, 0x02A6CB, 0x02A6E5,
    0x02765F, 0x027687, 0x02771B, 0x02773F,
    0x02AE7D, 0x02AE8E, 0x02AEB3, 0x02AEC8, 0x02AEF2,
    0x02AF17, 0x02AF66,
    # Raster/renderer switch arms and setup bodies.
    0x016362, 0x016370, 0x0163A7, 0x0163DE, 0x01640E,
    0x00791A, 0x029073, 0x029088, 0x029120,
    0x00A090, 0x01D10E, 0x01D17D, 0x01D191, 0x01D1A5,
    0x00366E, 0x003674, 0x003678, 0x003696,
    0x003C78, 0x00C947, 0x00C99A,
    0x03227C, 0x03229C, 0x0322B4,
    # Named graphics/decoder bodies whose starts are not in Ghidra's
    # function-start export.
    0x003D48, 0x003D79, 0x0089C2, 0x008AB7, 0x008D33,
    0x008F17, 0x0040CF, 0x008BC8, 0x008CDB, 0x008E6B,
    0x008EBD, 0x008F48, 0x0093F9, 0x009423, 0x009499,
    0x0094DC, 0x00954D, 0x012C05, 0x0255BA, 0x0927C0,
    # Branch-bound basic blocks: each start was checked as a standalone
    # decode and uses the surrounding module's real-mode call/data idioms.
    0x007875, 0x00A212, 0x00A693, 0x00B1AC, 0x00BCBA,
    0x00BEF0, 0x00D075, 0x01B65C, 0x030F51, 0x03603E,
    0x075AED, 0x076A52, 0x07B4A5, 0x091385, 0x097424,
    0x09E4C2, 0x09E83A, 0x09AC3, 0x0A0313,
    0x0A1C7A, 0x0A24A7, 0x0A33CF,
    # VM2 threaded-region continuations immediately following complete NEXT
    # sites.  These are native helper/handler bodies rather than dispatch-table
    # slots; each has the same stream-consuming code and terminates at a real
    # NEXT, with the three AF5x entries being alternate common-body entries.
    0x009B58, 0x00A56B, 0x00A876, 0x00AEB8,
    0x00AF53, 0x00AF58, 0x00AF5D, 0x00B02D,
    0x00B065, 0x00B109, 0x00B2CF, 0x00B322,
    0x00B36A, 0x00B49A, 0x00B4DA, 0x00B5D2,
    0x00BA3D, 0x00D44A, 0x0111C9,
    # Polygon clipping/edge helpers adjacent to the measured graphics
    # decoder.  0x8f96 calls the 0x91a0 common body and branches to the
    # 0x8f84/0x8f8c fast paths; 0x927e..0x92e8 are the callback entries used
    # by the two clipping passes, and 0x933c is the second edge interpolator.
    0x008F84, 0x008F96, 0x00927E, 0x0092AE, 0x0092C2,
    0x0092D6, 0x0092E0, 0x0092E8, 0x00933C,
    # Decoder helpers in the short palette/code boundary at 0x49ed; the
    # preceding indexed data ends exactly at that first executable byte.
    0x0049ED, 0x0049FB, 0x004A00, 0x004A26, 0x004A29,
    # DOS error reporting, bounded display-mode arms, and fixed-point helper
    # bodies exposed after their adjacent tables/alignment holes were bounded.
    0x01461E, 0x030E43, 0x030E50, 0x030E62,
    0x01D0C1, 0x01D0D3, 0x01D0E5, 0x01D0FA, 0x01D104,
    0x00F5E8, 0x00F5EF,
    # String/graphics helpers and their compact dispatch thunks.
    0x008868, 0x008870, 0x00887F,
    0x008913, 0x008916, 0x008919, 0x00891C, 0x00891F,
    0x008922, 0x008925, 0x008928, 0x00892B, 0x00892E,
    0x008931, 0x008937, 0x00893A,
    0x024844, 0x0247F0, 0x0247F4,
    # Graphics-table setup and mouse/input helper entries.
    0x007292, 0x007297, 0x00729C, 0x0072A1, 0x0072B6,
    0x038B86, 0x004AFA, 0x004A71, 0x00385F,
    # Short interrupt/renderer bodies and switch arms.
    0x024C94, 0x021D63, 0x021D6C,
    0x025A76, 0x025A94, 0x025ABC,
    0x025E0D, 0x025E37, 0x025E3D, 0x025E4F, 0x025E55,
    0x025E5B, 0x025E61, 0x025E67, 0x025E6D, 0x025E79,
    0x025E7F, 0x025E85, 0x025E8B, 0x025E97, 0x025EA3,
    0x025DA1, 0x025DAD,
    0x02A750, 0x02A757, 0x02A75B,
    # Short VGA/input helpers and generated switch arms in the next residual
    # batch; each is bounded by a real return or by the adjacent table guard.
    0x00671F, 0x006727, 0x0069B6, 0x006A04,
    0x007176, 0x00717E, 0x00718E, 0x007196,
    0x00D515, 0x00D5CF, 0x00D682,
    0x012FA7, 0x014B81,
    0x01BC19, 0x01BC1B, 0x01BC21, 0x01BC27,
    0x024780, 0x024350, 0x024354, 0x024370,
    0x024410, 0x024414, 0x024580,
    0x025BAC, 0x0391C0, 0x038DFE,
    # Short code islands left between the prior verified entries and their
    # surrounding padding/table guards.
    0x0041E6, 0x004A49, 0x0064E7, 0x006963,
    0x00727F,
    0x0088D1, 0x0088D4, 0x0088DA, 0x0088E0,
    0x0088FB, 0x0088FE, 0x008FA6, 0x0097CF,
    0x00A2C7, 0x00A2C8, 0x00D739,
    0x012A20, 0x012BB9, 0x012EF6, 0x012F8B,
    0x014623, 0x014A49, 0x014A59,
    0x014AF0, 0x014B11, 0x014B31, 0x014BDA, 0x014FD8,
    0x017161, 0x01719D, 0x0171E7, 0x017885,
    0x017F67, 0x017F78, 0x017F98,
    0x01BE48, 0x01BE4A, 0x023B41,
    0x024418, 0x0247D4, 0x0256CD,
    0x025D95, 0x025DA7, 0x025DD1, 0x025DDD,
    0x025E13, 0x025E2B, 0x02F55A, 0x030865,
    0x00D739,
)

# Ghidra records a thunk at the ModR/M byte of the real `imul bx` at 0x4b13
# (`eb 8a` at 0x4b14).  It is an overlapping decode, not an executable entry;
# omit only that one false seed so the surrounding renderer helper can be
# decoded linearly from 0x4afa.
GHIDRA_FALSE_SEEDS = {0x004B14}

# The threaded VM2 dispatch table at file offset 0x54FD4 contains 111 slots,
# whose values are offsets from handler-segment base 0x93C0.  The table has 94
# distinct targets; these are mechanically proven entry points even when no
# ordinary call or jump in the native-code graph reaches them.  Keep the
# resolved file offsets explicit so the reassembly remains auditable and does
# not depend on running the table locator as part of every build.
VM2_HANDLER_SEEDS = (
    0x00985C, 0x00A13F, 0x00A450, 0x00A458, 0x00A459,
    0x00A498, 0x00A784, 0x00A796, 0x00A7A0, 0x00A7AF,
    0x00A7BD, 0x00A7F2, 0x00A82E, 0x00A847, 0x00A87E,
    0x00A89D, 0x00A8C1, 0x00A8E4, 0x00A90A, 0x00AAF3,
    0x00AB2C, 0x00ACAD, 0x00ACB6, 0x00ACC7, 0x00ACDA,
    0x00ACED, 0x00AD2E, 0x00AD76, 0x00ADB3, 0x00ADF0,
    0x00AE2D, 0x00AE8D, 0x00AF0B, 0x00B04C, 0x00B0C1,
    0x00B164, 0x00B1AC, 0x00B20D, 0x00B26E, 0x00B3B2,
    0x00B3D6, 0x00B3DE, 0x00B3E4, 0x00B40A, 0x00B44D,
    0x00B476, 0x00B488, 0x00B6AB, 0x00B6B4, 0x00B6BF,
    0x00B6D7, 0x00B702, 0x00B73F, 0x00B77C, 0x00B783,
    0x00B805, 0x00B80C, 0x00B88E, 0x00B895, 0x00B917,
    0x00B92D, 0x00B946, 0x00B96F, 0x00B998, 0x00B9C1,
    0x00B9D8, 0x00B9EF, 0x00BA06, 0x00BEDA, 0x00C3C0,
    0x00D0B0, 0x00D0C5, 0x00D0DE, 0x00D0EA, 0x00D0F8,
    0x00D0FE, 0x00D106, 0x00D162, 0x00D170, 0x00D178,
    0x00D1EC, 0x00D1F4, 0x00D1FC, 0x00D26F, 0x00D27A,
    0x00D282, 0x00D35F, 0x0110FE, 0x011164, 0x0111D3,
    0x01124F, 0x0114B6, 0x0114CA, 0x0114D5,
)

def load_ghidra_seeds():
    """Convert Ghidra's segmented addresses to UW2 file offsets."""
    seeds = []
    if not os.path.exists(uw.GHIDRA_FNS):
        return seeds
    for line in open(uw.GHIDRA_FNS, encoding="latin-1"):
        a = line.split()
        if not a:
            continue
        t = a[0]
        if t.startswith("CODE_TAIL::"):
            seeds.append(int(t.split("::")[1], 16))
        elif t.startswith("int::"):
            continue
        elif t.count(":") == 1:
            s, o = t.split(":")
            seeds.append((int(s, 16) << 4) + int(o, 16) - 0xD200)
    switch_seeds = []
    data = Path(uw.SRC).read_bytes()
    for base, table, count, _label in OVERLAY_SWITCH_TABLES:
        for i in range(count):
            rel = struct.unpack_from("<H", data, table + 2 * i)[0]
            switch_seeds.append(base + rel)
    return ([q for q in seeds if q not in GHIDRA_FALSE_SEEDS]
            + list(EXTRA_CODE_SEEDS) + list(VM2_HANDLER_SEEDS)
            + switch_seeds)


uw.known_data = known_data
uw.load_ghidra_seeds = load_ghidra_seeds


# UW2 uses a few encodings that the shared 16-bit renderer intentionally leaves
# to its variant ladder.  Keep these fixes local to the UW2 wrapper: they are
# measured against this executable's bytes and do not silently change UW1's
# ratchet.
R32 = ["eax", "ecx", "edx", "ebx", "esp", "ebp", "esi", "edi"]
SHARED_MACRO_BLOCK = uw.macro_block
SHARED_RENDER = uw.render

# A handful of reachable instructions preserve redundant prefix order or a
# non-canonical group-2 encoding that NASM normalises.  They are code, not
# data: give each exact form a named macro so the generated source retains the
# decoded operation while pinning the original bytes.
EXACT_FORMS = {
    0x003C6D: (b"\xf2\x13\xeb", "adc_bp_bx_f2"),
    0x00C838: (b"\xf3\x2e\xa4", "rep_cs_movsb"),
    0x00C87F: (b"\xf3\x2e\xa4", "rep_cs_movsb"),
    0x008C26: (b"\xf3\x26\xa4", "rep_es_movsb"),
    0x008C5C: (b"\xf3\x26\xa4", "rep_es_movsb"),
    0x008C8F: (b"\xf3\x26\xa4", "rep_es_movsb"),
    0x008CC2: (b"\xf3\x26\xa4", "rep_es_movsb"),
    0x008D15: (b"\xf3\x26\xa4", "rep_es_movsb"),
    0x008EA5: (b"\xf3\x26\xa4", "rep_es_movsb"),
    0x008F09: (b"\xf3\x26\xa4", "rep_es_movsb"),
    0x006479: (b"\xf3\x26\xa4", "rep_es_movsb"),
    0x0064C4: (b"\xf3\x26\xa4", "rep_es_movsb"),
    0x006552: (b"\xf3\x26\xa4", "rep_es_movsb"),
    0x0065D0: (b"\xf3\x26\xa4", "rep_es_movsb"),
    0x00661C: (b"\xf3\x26\xa4", "rep_es_movsb"),
    0x00DBE6: (b"\x66\x2e\xa3\xb1\x48", "mov32_cs_48b1_eax"),
    0x00DBEB: (b"\x66\x2e\xa3\xd4\x48", "mov32_cs_48d4_eax"),
    0x00E4D9: (b"\x66\x26\x0f\xb7\x0e\x4c\x06", "movzx_ecx_es_064c"),
    0x00E530: (b"\x66\x67\x8d\x4a\x01", "lea_ecx_edx_1_exact"),
    0x09FB13: (b"\xc0\x75\xbb\x83", "sal_byte_di_m45_83"),
}


def macro_block_uw2():
    """Add macros for Borland's 0x66-prefixed register-direction forms."""
    out = SHARED_MACRO_BLOCK()
    out += ["",
            "; UW2 32-bit register encodings -- Borland keeps the ModRM",
            "; direction bit set under the 0x66 operand-size prefix.",
            ""]
    for i, r in enumerate(R32):
        out.append("%%define rn32_%s %d" % (r, i))
    out.append("")
    ops = sorted({op for op in uw.D1_OPS if op & 1})
    for op in ops:
        out.append("%%macro %s32_rr 2" % uw.D1_OPS[op])
        out.append("        db 0x66, 0x%02x, 0xc0 | ((rn32_ %%+ %%1) << 3) | (rn32_ %%+ %%2)"
                   % op)
        out.append("%endmacro")
    out += ["", "; UW2 exact prefix/group encodings"]
    for raw, name in dict.fromkeys(EXACT_FORMS.values()):
        out.append("%%macro %s 0" % name)
        out.append("        db " + ", ".join("0x%02x" % b for b in raw))
        out.append("%endmacro")
    out.append("")
    return out


def render_uw2(d, off, size, variant):
    """Render UW2's byte-exact fixed-count and 32-bit register forms."""
    if variant == 0 and off in EXACT_FORMS:
        raw, name = EXACT_FORMS[off]
        if d[off:off + size] == raw:
            return ([(off, size, name)], False)

    # D0/D1 shift and rotate encodings carry an implicit count of one.  NASM
    # requires that count to be written explicitly, otherwise it rejects the
    # otherwise correct mnemonic.
    if variant == 0 and size in (2, 3) and d[off] in (0xD0, 0xD1):
        trips, isdb = SHARED_RENDER(d, off, size, variant)
        if not isdb and len(trips) == 1 and "," not in trips[0][2]:
            o, n, text = trips[0]
            return ([(o, n, text + ", 1")], False)

    # Borland emits 0x66 + d=1 register-register operations for 32-bit C
    # arithmetic in an otherwise 16-bit image.  NASM emits the equivalent
    # d=0 ModRM byte, so use a tiny byte-pinning macro for the exact form.
    if variant == 0 and size == 3 and d[off] == 0x66:
        op = d[off + 1]
        modrm = d[off + 2]
        if op in uw.D1_OPS and (op & 1) and (modrm >> 6) == 3:
            name = "%s32_rr" % uw.D1_OPS[op]
            dst = R32[(modrm >> 3) & 7]
            src = R32[modrm & 7]
            return ([(off, size, "%s %s, %s" % (name, dst, src))], False)

    return SHARED_RENDER(d, off, size, variant)


uw.macro_block = macro_block_uw2
uw.render = render_uw2


def audit_whole_file():
    """Verify that every byte is decoded code or an explicit data guard."""
    data = Path(uw.SRC).read_bytes()
    cont = uw.Container(data)
    guard_ranges = [(lo, hi) for lo, hi, _ in known_data(cont)]
    seeds = [cont.entry]
    if "--no-ghidra-seeds" not in sys.argv:
        seeds += load_ghidra_seeds()

    dsc = uw.Descent(data, cont, guard_ranges)
    dsc.run(seeds, cont.hdr_size, cont.image_end)
    dsc.run([cont.pool_off] + [s for s in seeds if s >= cont.pool_off],
            cont.pool_off, len(data))

    code = bytearray(len(data))
    for off, size in dsc.insns.items():
        code[off:off + size] = b"\x01" * size
    guarded = bytearray(len(data))
    for lo, hi in guard_ranges:
        lo = max(0, lo)
        hi = min(len(data), hi)
        if hi > lo:
            guarded[lo:hi] = b"\x01" * (hi - lo)

    unknown = []
    i = 0
    while i < len(data):
        if code[i] or guarded[i]:
            i += 1
            continue
        j = i + 1
        while j < len(data) and not code[j] and not guarded[j]:
            j += 1
        unknown.append((i, j))
        i = j

    overlap = sum(1 for a, b in zip(code, guarded) if a and b)
    return {
        "ok": not unknown and not overlap,
        "file_bytes": len(data),
        "classified_bytes": len(data) - sum(b - a for a, b in unknown),
        "code_bytes_union": sum(code),
        "guard_bytes_union": sum(guarded),
        "overlap_bytes": overlap,
        "guard_ranges": len(guard_ranges),
        "unclassified_bytes": sum(b - a for a, b in unknown),
        "unclassified_runs": [
            {"start": a, "end": b, "size": b - a} for a, b in unknown
        ],
    }


def main():
    rc = uw.main()
    if rc != 0:
        return rc

    audit = audit_whole_file()
    print("  whole-file classification: %d / %d bytes classified; %d unclassified"
          % (audit["classified_bytes"], audit["file_bytes"],
             audit["unclassified_bytes"]))
    report_path = Path(uw.OUT) / "report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["whole_file"] = audit
    report_path.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    if not audit["ok"]:
        for run in audit["unclassified_runs"][:10]:
            print("  !! unclassified 0x%05x..0x%05x (%d bytes)"
                  % (run["start"], run["end"], run["size"]))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
