#!/usr/bin/env python3
"""
uwreasm.py -- byte-exact disassemble -> reassemble harness for UW.EXE.

Reads work/expanded/UW.EXE, produces work/reasm/out/uw.asm (NASM source for the
*whole* 561,744-byte file: MZ header, relocation table, load module, FBOV
overlay pool), assembles it with nasm -f bin, and verifies the result is
byte-identical to the original.

Method
------
Recursive descent from verified seeds gives the code map; everything unreached
is emitted as data.  Every instruction is rendered as NASM text and then
*checked against the original bytes* using nasm's own listing output.  A line
whose emitted bytes differ walks a variant ladder (default -> byte-immediate ->
strict-word-immediate -> raw db); the db rung always matches, so byte-exactness
is guaranteed by construction and the ladder only affects how much of the file
is real mnemonics.

Branch targets are emitted $-relative (`jmp short $+2+N`), so no segment model
is needed for emission and 16-bit wraparound cannot corrupt an encoding.

Usage:  python uwreasm.py [--passes N] [--no-ghidra-seeds]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import struct
import subprocess
import sys
import textwrap
import time
from collections import deque

from capstone import Cs, CS_ARCH_X86, CS_MODE_16

PROJ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(PROJ, "work", "expanded", "UW.EXE")
OUT = os.path.join(PROJ, "work", "reasm", "out")
GHIDRA_FNS = os.path.join(PROJ, "work", "ghidra_export", "functions.txt")
NASM = r"C:\msys64\mingw64\bin\nasm.exe"

MD = Cs(CS_ARCH_X86, CS_MODE_16)          # fast path, used by the descent
MD.detail = False
MDD = Cs(CS_ARCH_X86, CS_MODE_16)         # detailed, used by the renderer
MDD.detail = True

# ---------------------------------------------------------------- container --


class Container:
    """The MZ container of UW.EXE, parsed into its five regions."""

    def __init__(self, data: bytes):
        self.data = data
        u16 = lambda o: struct.unpack_from("<H", data, o)[0]
        self.e_cblp = u16(0x02)
        self.e_cp = u16(0x04)
        self.e_crlc = u16(0x06)
        self.e_cparhdr = u16(0x08)
        self.e_minalloc = u16(0x0A)
        self.e_maxalloc = u16(0x0C)
        self.e_ss = u16(0x0E)
        self.e_sp = u16(0x10)
        self.e_csum = u16(0x12)
        self.e_ip = u16(0x14)
        self.e_cs = u16(0x16)
        self.e_lfarlc = u16(0x18)
        self.e_ovno = u16(0x1A)
        self.reserved = data[0x1C:self.e_lfarlc]

        self.hdr_size = self.e_cparhdr * 16
        self.reloc_off = self.e_lfarlc
        self.reloc_end = self.e_lfarlc + self.e_crlc * 4
        self.slack = data[self.reloc_end:self.hdr_size]
        self.image_end = (self.e_cp - 1) * 512 + self.e_cblp
        self.relocs = [struct.unpack_from("<HH", data, self.reloc_off + 4 * i)
                       for i in range(self.e_crlc)]
        self.reloc_sites = {self.hdr_size + (s << 4) + o for o, s in self.relocs}
        self.entry = self.hdr_size + (self.e_cs << 4) + self.e_ip

        sig, ovrsize, exeinfo, segnum = struct.unpack_from("<4sIII", data, self.image_end)
        self.fbov_sig = sig
        self.fbov_ovrsize = ovrsize
        self.fbov_exeinfo = exeinfo
        self.fbov_segnum = segnum
        self.pool_off = self.image_end + 16

    def check(self):
        errs = []
        if self.data[:2] != b"MZ":
            errs.append("not an MZ file")
        if self.fbov_sig != b"FBOV":
            errs.append("no FBOV overlay pool at image end")
        if self.fbov_ovrsize + 16 != len(self.data) - self.image_end:
            errs.append("FBOV ovrsize %#x != pool size %#x"
                        % (self.fbov_ovrsize, len(self.data) - self.image_end))
        if any(self.hdr_size + (s << 4) + o + 2 > self.image_end for o, s in self.relocs):
            errs.append("relocation target outside the load image")
        if len(self.reloc_sites) != self.e_crlc:
            errs.append("duplicate relocation targets")
        if any(self.slack):
            errs.append("header slack is not zero-filled")
        return errs


# ------------------------------------------------------------------ descent --

RET_OPS = {0xC3, 0xC2, 0xCB, 0xCA, 0xCF}


def s8(b):
    return b - 256 if b > 127 else b


def s16(d, o):
    v = struct.unpack_from("<H", d, o)[0]
    return v - 65536 if v > 32767 else v


class Descent:
    """Recursive descent over the flat file, tracking file offsets only.

    Near-branch targets are computed linearly.  Real-mode segment wrap would
    make that wrong; a target outside the region is dropped and counted, and
    any bad encoding is caught later by the byte-level verifier anyway.
    """

    def __init__(self, data: bytes, cont: Container, guard):
        self.d = data
        self.c = cont
        self.guard = guard
        self.insns: dict[int, int] = {}
        self.funcs: set[int] = set()
        self.stats = {"bad_decode": 0, "oob_target": 0, "guard_hits": 0,
                      "int3f_thunks": 0, "far_unrelocated": 0}

    def in_guard(self, off):
        return any(a <= off < b for a, b in self.guard)

    def run(self, seeds, lo, hi):
        d, md = self.d, MD
        q = deque()
        for s in seeds:
            if lo <= s < hi:
                q.append(s)
                self.funcs.add(s)
        while q:
            off = q.popleft()
            while True:
                if off in self.insns or not (lo <= off < hi):
                    break
                if self.in_guard(off):
                    self.stats["guard_hits"] += 1
                    break
                try:
                    ins = next(md.disasm(d[off:off + 16], off, count=1))
                except StopIteration:
                    self.stats["bad_decode"] += 1
                    break
                size = ins.size
                op = d[off]
                stop = False

                def queue(t, fn=False):
                    if lo <= t < hi and not self.in_guard(t):
                        if t not in self.insns:
                            q.append(t)
                        if fn:
                            self.funcs.add(t)
                    else:
                        self.stats["oob_target"] += 1

                if op == 0xCD and off + 1 < hi and d[off + 1] == 0x3F:
                    # Borland overlay thunk: CD 3F + dw offset + db segment.
                    size = 5
                    self.stats["int3f_thunks"] += 1
                elif op == 0xEB:
                    queue(off + 2 + s8(d[off + 1])); stop = True
                elif op == 0xE9:
                    queue(off + 3 + s16(d, off + 1)); stop = True
                elif op == 0xEA:
                    t = self.far_target(off)
                    if t is not None:
                        queue(t, fn=True)
                    stop = True
                elif 0x70 <= op <= 0x7F:
                    queue(off + 2 + s8(d[off + 1]))
                elif op == 0x0F and 0x80 <= d[off + 1] <= 0x8F:
                    queue(off + 4 + s16(d, off + 2))
                elif 0xE0 <= op <= 0xE3:
                    queue(off + 2 + s8(d[off + 1]))
                elif op == 0xE8:
                    queue(off + 3 + s16(d, off + 1), fn=True)
                elif op == 0x9A:
                    t = self.far_target(off)
                    if t is not None:
                        queue(t, fn=True)
                elif op == 0xCD and d[off + 1] == 0x20:
                    stop = True
                elif op == 0xFF and ((d[off + 1] >> 3) & 7) in (4, 5):
                    stop = True
                elif op in RET_OPS:
                    stop = True

                if off + size > hi:          # never run off the end of a region
                    self.stats["bad_decode"] += 1
                    break
                self.insns[off] = size
                if stop:
                    break
                off += size

    def far_target(self, off):
        """9A/EA ptr16:16 -> file offset, only if the segment word is relocated."""
        if off + 5 > len(self.d) or (off + 3) not in self.c.reloc_sites:
            self.stats["far_unrelocated"] += 1
            return None
        o, s = struct.unpack_from("<HH", self.d, off + 1)
        return self.c.hdr_size + (s << 4) + o


# ----------------------------------------------------------------- renderer --

PTR = re.compile(r"\b(byte|word|dword|qword|tword|fword) ptr ")
BAREPTR = re.compile(r"\bptr ")          # capstone prints `les di, ptr [bp+6]`
SEGPFX = re.compile(r"\b(cs|ds|es|ss|fs|gs):\[")
LFAR = re.compile(r"^l(call|jmp) ")      # capstone's indirect far call/jump
IMM_TAIL = re.compile(r"^([a-z0-9]+)\s+(.*),\s*(-?(?:0x)?[0-9a-fA-F]+)$")

# capstone prints string instructions with explicit operands; NASM wants them
# bare, with any segment override / rep written as a separate prefix token.
STRING_OPS = {"movsb", "movsw", "movsd", "lodsb", "lodsw", "lodsd",
              "stosb", "stosw", "stosd", "scasb", "scasw", "scasd",
              "cmpsb", "cmpsw", "cmpsd", "insb", "insw", "insd",
              "outsb", "outsw", "outsd"}
PREFIX_TOKEN = {0xF0: "lock", 0xF2: "repne", 0xF3: "rep", 0x2E: "cs", 0x36: "ss",
                0x3E: "ds", 0x26: "es", 0x64: "fs", 0x65: "gs"}
SEGNAMES = {"cs", "ds", "es", "ss", "fs", "gs"}

CC = {0x0: "jo", 0x1: "jno", 0x2: "jb", 0x3: "jae", 0x4: "je", 0x5: "jne",
      0x6: "jbe", 0x7: "ja", 0x8: "js", 0x9: "jns", 0xA: "jp", 0xB: "jnp",
      0xC: "jl", 0xD: "jge", 0xE: "jle", 0xF: "jg"}
LOOPS = {0xE0: "loopne", 0xE1: "loope", 0xE2: "loop", 0xE3: "jcxz"}


# Borland's code generator picks encodings NASM would not: the direction bit set
# on register-register ops (8B EC for `mov bp,sp`), moffs vs modrm, redundant
# prefixes.  Those bytes are pinned with `db` and the mnemonic kept in a comment.
MEMSTART = re.compile(r"\[(?:(?:cs|ds|es|ss|fs|gs):)?")
R16 = ["ax", "cx", "dx", "bx", "sp", "bp", "si", "di"]
R8 = ["al", "cl", "dl", "bl", "ah", "ch", "dh", "bh"]

# Borland emits register-to-register ALU/MOV with the direction bit set
# (reg <- r/m).  NASM always picks the equivalent d=0 form, so these are
# assembled through generated macros that pin the original ModRM byte.
D1_OPS = {0x02: "add", 0x0A: "or", 0x12: "adc", 0x1A: "sbb", 0x22: "and",
          0x2A: "sub", 0x32: "xor", 0x3A: "cmp", 0x8A: "mov"}
D1_OPS.update({k + 1: v for k, v in D1_OPS.items()})     # 16-bit twins
D1_OPS[0x86] = D1_OPS[0x87] = "xchg"      # same reg/rm ambiguity

# capstone names 0x98/0x99 with their 32-bit mnemonics even in 16-bit mode;
# without a 0x66 prefix these are CBW / CWD.
SIZE16_NAME = {0x98: "cbw", 0x99: "cwd"}

# capstone occasionally reads data as SSE / x87 / BND forms that NASM has no
# syntax for; pin those bytes instead of round-tripping through text.
BAD_TOKENS = ("xmmword", "ymmword", "zmmword", "bnd ", "fstpnce", "fcmovnu",
              "hint_", "{", "ptr ")

IMM_BYTE_OPS = {0x83, 0x6B, 0x6A}         # immediate is a sign-extended imm8
IMM_WORD_OPS = {0x81, 0x69, 0x68}         # immediate is a full imm16
DB_RUNG = 2                               # last rung of the variant ladder


def dbtext(d, off, n, comment=None):
    t = "db " + ",".join("0x%02x" % b for b in d[off:off + n])
    return t + ("        ; " + comment if comment else "")


def qual_disp(txt, qual):
    return MEMSTART.sub(lambda m: m.group(0) + qual + " ", txt, count=1)


def qual_imm(txt, qual):
    i = txt.rfind(",")
    if i >= 0:
        return "%s %s %s" % (txt[:i + 1], qual, txt[i + 1:].strip())
    mn, _, rest = txt.partition(" ")
    return "%s %s %s" % (mn, qual, rest.strip()) if rest else txt


def render(d, off, size, variant):
    """NASM text for one instruction as a list of (offset, length, text).

    Rung 0 derives the operand-size qualifiers from the *original encoding*
    (capstone's modrm/disp/imm detail), so the common Borland forms come out
    right on the first pass.  Rung 1 flips the immediate qualifier; rung 2
    pins the bytes with `db` and keeps the mnemonic as a comment.
    """
    op = d[off]
    one = lambda t: ([(off, size, t)], False)

    def bail():
        try:
            i = next(MDD.disasm(d[off:off + 16], off, count=1))
            c = "%s %s" % (i.mnemonic, i.op_str)
        except StopIteration:
            c = "(undecodable)"
        return [(off, size, dbtext(d, off, size, c))], True

    if variant >= 2:
        return bail()

    if op == 0xCD and d[off + 1] == 0x3F:                 # overlay thunk
        return ([(off, 2, "int 0x3f"),
                 (off + 2, 2, "dw 0x%04x" % struct.unpack_from("<H", d, off + 2)[0]),
                 (off + 4, 1, "db 0x%02x" % d[off + 4])], False)
    if op == 0xEB:
        return one("jmp short $+2%+d" % s8(d[off + 1]))
    if op == 0xE9:
        return one("jmp near $+3%+d" % s16(d, off + 1))
    if 0x70 <= op <= 0x7F:
        return one("%s short $+2%+d" % (CC[op & 0xF], s8(d[off + 1])))
    if op == 0x0F and 0x80 <= d[off + 1] <= 0x8F:
        return one("%s near $+4%+d" % (CC[d[off + 1] & 0xF], s16(d, off + 2)))
    if op in LOOPS:
        return one("%s $+2%+d" % (LOOPS[op], s8(d[off + 1])))
    if op == 0xE8:
        return one("call $+3%+d" % s16(d, off + 1))
    if op in (0x9A, 0xEA):
        o, s = struct.unpack_from("<HH", d, off + 1)
        return one("%s 0x%04x:0x%04x" % ("call" if op == 0x9A else "jmp", s, o))

    if size == 1 and op in SIZE16_NAME:
        return one(SIZE16_NAME[op])
    if op == 0xC8:            # capstone signs ENTER's nesting level; it is a u8
        return one("enter 0x%04x, 0x%02x"
                   % (struct.unpack_from("<H", d, off + 1)[0], d[off + 3]))

    # register-to-register with the direction bit set -> generated macro
    if size == 2 and op in D1_OPS and (d[off + 1] >> 6) == 3 and variant == 0:
        regs = R16 if op & 1 else R8
        return one("%s_rr%s %s, %s" % (D1_OPS[op], "" if op & 1 else "8",
                                       regs[(d[off + 1] >> 3) & 7],
                                       regs[d[off + 1] & 7]))

    try:
        ins = next(MDD.disasm(d[off:off + 16], off, count=1))
    except StopIteration:
        return bail()

    bare = ins.mnemonic.split()[-1]
    if bare in STRING_OPS:
        pfx = []
        for k in range(off, off + size):
            if d[k] in PREFIX_TOKEN:
                pfx.append(PREFIX_TOKEN[d[k]])
            elif d[k] not in (0x66, 0x67):
                break
        return one(" ".join(pfx + [bare]))

    txt = "%s %s" % (ins.mnemonic, ins.op_str)
    txt = SEGPFX.sub(r"[\1:", BAREPTR.sub("", PTR.sub(r"\1 ", txt))).strip()
    txt = LFAR.sub(lambda m: m.group(1) + " far ", txt)
    if any(t in txt for t in BAD_TOKENS):
        return bail()          # capstone read data as SSE/x87/BND exotica

    # capstone drops segment/rep prefixes that have no operand to attach to
    # (`3e 3f` prints as plain `aas`); put them back as explicit tokens.
    lead = []
    for k in range(off, off + size):
        if d[k] in PREFIX_TOKEN:
            lead.append(PREFIX_TOKEN[d[k]])
        elif d[k] not in (0x66, 0x67):
            break
    if lead:
        first = txt.split()[0]
        missing = [t for t in lead
                   if t not in ("lock", "rep", "repne") or first != t]
        missing = [t for t in missing if not (t in SEGNAMES and "[%s:" % t in txt)]
        if missing:
            txt = " ".join(missing) + " " + txt

    enc = ins.encoding
    opc = ins.opcode[0]

    # displacement size: NASM picks the shortest, Borland often did not
    if "[" in txt:
        mod = (ins.modrm >> 6) & 3
        if enc.disp_size == 1:
            txt = qual_disp(txt, "byte")
        elif enc.disp_size == 2 and mod == 2:
            txt = qual_disp(txt, "word")

    # immediate size: 0x83/0x6B/0x6A are sign-extended imm8 forms
    if enc.imm_size:
        want = None
        if opc in IMM_BYTE_OPS:
            want = "byte"
        elif opc in IMM_WORD_OPS and enc.imm_size == 2:
            want = "strict word"
        if variant == 1:                      # rung 1: flip the guess
            want = {"byte": "strict word", "strict word": "byte",
                    None: "byte"}[want]
        if want:
            txt = qual_imm(txt, want)
    elif variant == 1:
        return bail()
    return one(txt)


# -------------------------------------------------------------- data emitter --

PRINTABLE = set(range(0x20, 0x7F))
MIN_STR = 4
MIN_RUN = 24            # identical bytes before switching to `times`


def data_lines(d, lo, hi, reloc_sites):
    """A data region as (offset, length_or_None, text) triples."""
    out = []
    i = lo
    while i < hi:
        if i in reloc_sites and i + 2 <= hi:
            out.append((i, 2, "dw 0x%04x" % struct.unpack_from("<H", d, i)[0],
                        "RELOC"))
            i += 2
            continue

        j = i
        while j < hi and d[j] == d[i] and j not in reloc_sites:
            j += 1
        if j - i >= MIN_RUN:
            out.append((i, None, "times %d db 0x%02x" % (j - i, d[i]), None))
            i = j
            continue

        j = i
        while j < hi and d[j] in PRINTABLE and j not in reloc_sites:
            j += 1
        if j - i >= MIN_STR:
            out.extend(string_lines(d, i, j))
            i = j
            continue

        j = i
        stop = min(hi, (i | 15) + 1)          # break db runs on 16-byte lines
        while j < stop:
            if j != i and (j in reloc_sites or run_ahead(d, j, hi, reloc_sites)):
                break
            j += 1
        out.append((i, j - i, dbtext(d, i, j - i), None))
        i = j
    return out


def run_ahead(d, j, hi, reloc_sites):
    """Would a string or a long identical run start at j?"""
    k = j
    while k < hi and k - j < MIN_STR and d[k] in PRINTABLE and k not in reloc_sites:
        k += 1
    if k - j >= MIN_STR:
        return True
    k = j
    while k < hi and k - j < MIN_RUN and d[k] == d[j] and k not in reloc_sites:
        k += 1
    return k - j >= MIN_RUN


def string_lines(d, lo, hi):
    out = []
    i = lo
    while i < hi:
        j = min(hi, i + 56)
        chunk = d[i:j]
        if b"'" not in chunk:
            out.append((i, j - i, "db '%s'" % chunk.decode("latin-1"), None))
        elif b'"' not in chunk:
            out.append((i, j - i, 'db "%s"' % chunk.decode("latin-1"), None))
        else:
            out.append((i, j - i, dbtext(d, i, j - i), None))
        i = j
    return out


# ------------------------------------------------------------------- emitter --

def macro_block():
    """NASM macros for the encodings Borland picks and NASM will not.

    Emitted inline (not %included) so that nasm's listing line numbers stay in
    one-to-one correspondence with the lines this generator produced.
    """
    out = ["",
           "; ------------------------------------------------- Borland encodings --",
           "; Borland's code generator emits register-to-register ALU and MOV with",
           "; the direction bit set -- `8b ec` for `mov bp,sp`, `33 c0` for",
           "; `xor ax,ax` -- while NASM always chooses the equivalent d=0 form",
           "; (`89 e5`, `31 c0`).  Same semantics, different bytes.  These macros",
           "; pin the original ModRM byte; the _rr suffix reads \"reg <- r/m,",
           "; both operands registers\", _rr8 is the byte-wide twin.",
           ""]
    for i, r in enumerate(R8):
        out.append("%%define rn_%s %d" % (r, i))
    for i, r in enumerate(R16):
        if r not in R8:
            out.append("%%define rn_%s %d" % (r, i))
    out.append("")
    for op in sorted(D1_OPS):
        name = "%s_rr%s" % (D1_OPS[op], "" if op & 1 else "8")
        out.append("%%macro %s 2" % name)
        out.append("        db 0x%02x, 0xc0 | ((rn_ %%+ %%1) << 3) | (rn_ %%+ %%2)"
                   % op)
        out.append("%endmacro")
    out.append("")
    return out


PROLOGUE = """\
; ============================================================================
;  UW.EXE -- Ultima Underworld: The Stygian Abyss (1992), reconstructed source
;
;  Generated by work/reasm/uwreasm.py -- do not edit by hand.
;  Assembles byte-for-byte identical to work/expanded/UW.EXE ({flen} bytes):
;
;      nasm -f bin -O0 -o uw.bin uw.asm
;
;  File layout
;      0x00000 .. 0x{rloff:05x}   MZ header
;      0x{rloff:05x} .. 0x{rlend:05x}   relocation table, {ncrlc} entries
;      0x{rlend:05x} .. 0x{hdr:05x}   header slack (zero)
;      0x{hdr:05x} .. 0x{imgend:05x}   load module, DOS-loaded  (DGROUP at 0x5f2f0)
;      0x{imgend:05x} .. 0x{flen2:05x}   FBOV overlay pool, {nseg} segments
;
;  Entry point  CS:IP = 0x{ecs:04x}:0x{eip:04x}  ->  file 0x{entry:05x}  (Borland C0.ASM start)
;
;  Branch targets are $-relative: the encoding is then independent of any
;  segment model, which is what makes a flat `-f bin` rebuild exact.
; ============================================================================

        bits 16
        org 0

HDR_SIZE  equ 0x{hdr:04x}                 ; e_cparhdr * 16, a TLINK parameter

; ---------------------------------------------------------------- MZ header --
mz_header:
        dw 0x5a4d                       ; e_magic   'MZ'
        dw IMAGE_END % 512              ; e_cblp    bytes used in last page
        dw (IMAGE_END + 511) / 512      ; e_cp      pages in image
        dw NRELOC                       ; e_crlc    relocation count
        dw HDR_SIZE / 16                ; e_cparhdr header size in paragraphs
        dw 0x{minalloc:04x}                       ; e_minalloc
        dw 0x{maxalloc:04x}                       ; e_maxalloc
        dw 0x{ess:04x}                       ; e_ss      stack seg (load-relative)
        dw 0x{esp:04x}                       ; e_sp
        dw 0x{ecsum:04x}                       ; e_csum
        dw 0x{eip:04x}                       ; e_ip
        dw 0x{ecs:04x}                       ; e_cs      entry seg (load-relative)
        dw reloc_table                  ; e_lfarlc
        dw 0x{eovno:04x}                       ; e_ovno
"""


def emit(cont, insns, funcs, variants, path):
    d = cont.data
    lines = []
    linemap = {}
    dbset = set()

    def push(s):
        # line numbers must match nasm's exactly, so never push an embedded \n
        assert "\n" not in s, s
        lines.append(s)

    def code(off, n, text, note=None):
        push("        %-46s; %05x%s" % (text, off, "  " + note if note else ""))
        linemap[len(lines)] = (off, n)

    for ln in PROLOGUE.format(
            flen=len(d), flen2=len(d), rloff=cont.reloc_off, rlend=cont.reloc_end,
            hdr=cont.hdr_size, imgend=cont.image_end, ncrlc=cont.e_crlc,
            nseg=cont.fbov_segnum, ecs=cont.e_cs, eip=cont.e_ip, entry=cont.entry,
            minalloc=cont.e_minalloc, maxalloc=cont.e_maxalloc, ess=cont.e_ss,
            esp=cont.e_sp, ecsum=cont.e_csum, eovno=cont.e_ovno).rstrip("\n").split("\n"):
        if ln.endswith("MZ header --"):        # macros first, then the header
            for m in macro_block():
                push(m)
        push(ln)

    push("        ; reserved area (Borland TLINK)")
    for i in range(0, len(cont.reserved), 2):
        push("        dw 0x%04x" % struct.unpack_from("<H", cont.reserved, i)[0])

    push("")
    push("; -------------------------------------------------- relocation table --")
    push("; %d (offset, segment) pairs.  Every one targets a segment immediate" % cont.e_crlc)
    push("; inside the load module; the table is regenerated from this list, so")
    push("; e_crlc below is derived rather than copied.")
    push("reloc_table:")
    for o, s in cont.relocs:
        push("        dw 0x%04x,0x%04x                ; -> 0x%05x"
             % (o, s, cont.hdr_size + (s << 4) + o))
    push("NRELOC  equ ($ - reloc_table) / 4")
    push("")
    push("; ------------------------------------------------------ header slack --")
    push("        times HDR_SIZE - ($ - $$) db 0")
    push("")

    def body(lo, hi, title):
        push("")
        push("; " + "=" * 74)
        push("; " + title)
        push("; " + "=" * 74)
        off = lo
        while off < hi:
            if off in insns:
                n = insns[off]
                if off in funcs:
                    push("")
                    push("fn_%05x:" % off)
                trips, isdb = render(d, off, n, variants.get(off, 0))
                if isdb:
                    dbset.add(off)
                for o2, n2, text in trips:
                    code(o2, n2, text)
                off += n
            else:
                j = off
                while j < hi and j not in insns:
                    j += 1
                push("")
                for klo, _khi, why in known_data(cont):
                    if klo == off:
                        push("; %s" % ("-" * 74))
                        for w in textwrap.wrap(why, 72):
                            push("; %s" % w)
                        push("; %s" % ("-" * 74))
                push("d_%05x:%s; %d bytes of data" % (off, " " * 34, j - off))
                for o2, n2, text, note in data_lines(d, off, j, cont.reloc_sites):
                    code(o2, n2, text, note)
                off = j

    body(cont.hdr_size, cont.image_end,
         "LOAD MODULE   file 0x%05x .. 0x%05x" % (cont.hdr_size, cont.image_end))
    push("")
    push("IMAGE_END equ $ - $$")
    push("")
    push("; " + "=" * 74)
    push("; FBOV OVERLAY POOL   file 0x%05x .. 0x%05x, %d segments"
         % (cont.image_end, len(d), cont.fbov_segnum))
    push("; Borland VROOM overlay area: the code reached through the 667 INT 3Fh")
    push("; thunks in the load module.  Not loaded by DOS; swapped in on demand.")
    push("; " + "=" * 74)
    push("fbov_header:")
    push("        db 'FBOV'")
    push("        dd 0x%08x                    ; ovrsize = pool size - 16" % cont.fbov_ovrsize)
    push("        dd 0x%08x                    ; exeinfo" % cont.fbov_exeinfo)
    push("        dd %-10d                    ; segnum" % cont.fbov_segnum)
    body(cont.pool_off, len(d), "overlay segments")

    with open(path, "w", encoding="latin-1", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    return linemap, dbset


# ------------------------------------------------------------------ verifier --

# A nasm listing line is "<lineno> <offset> <bytes>[-]  <source>".  Bytes coming
# out of a macro expansion are listed against the macro *definition* line and
# marked "<1>", so they have to be re-attributed to the invoking line.
LST = re.compile(r"^\s*(\d+) ([0-9A-F]{8}) ((?:[0-9A-F]{2})+)-?\s*(.*)$")
LST_NOBYTES = re.compile(r"^\s*(\d+)\s{2,}(.*)$")
MACRO_MARK = re.compile(r"^<\d+>")      # "<rep NNh>" is a times run, not a macro


def assemble(asm, lst, binout):
    t = time.time()
    r = subprocess.run([NASM, "-f", "bin", "-O0", "-w-label-redef-late",
                        "-l", lst, "-o", binout, asm],
                       capture_output=True, text=True)
    return r, time.time() - t


def parse_listing(lst):
    out = {}
    cur = None
    with open(lst, "r", encoding="latin-1", errors="replace") as f:
        for line in f:
            m = LST.match(line)
            if m:
                if not MACRO_MARK.match(m.group(4)):
                    cur = int(m.group(1))
                if cur is not None:
                    out.setdefault(cur, bytearray()).extend(bytes.fromhex(m.group(3)))
                continue
            m = LST_NOBYTES.match(line)
            if m and not MACRO_MARK.match(m.group(2)):
                cur = int(m.group(1))
    return out


def verify(d, linemap, emitted):
    """File offsets whose emitted bytes differ from the original."""
    bad, checked = [], 0
    for lineno, (off, n) in linemap.items():
        b = emitted.get(lineno)
        if b is None:
            if n is not None:                     # instruction produced nothing
                bad.append((off, n, b"", d[off:off + n]))
            continue                              # `times` lines: not listed
        checked += 1
        b = bytes(b)
        if b != d[off:off + len(b)] or (n is not None and len(b) != n):
            bad.append((off, n, b, d[off:off + max(len(b), n or 0)]))
    return bad, checked


# ---------------------------------------------------------------------- main --

def known_data(cont):
    """Proven-data regions.  The descent must never enter these.

    cross-project.md S1: a sweep without a data guard is not measuring what its
    coverage percentage claims.  Each entry here is proven, not assumed.
    """
    return [
        (0, cont.hdr_size,
         "MZ header, relocation table and header slack"),
        (0x109DE, 0x119DE,
         "palette shading LUT, 16 levels x 256 colours; row 0 is the exact "
         "identity map, row 15 is all zero, distinct-value counts fall "
         "256,242,224,...,69,1; bounded by `cc c3` before and code after"),
        (0x5F2F0, cont.image_end,
         "DGROUP: initialised data + BSS, base = header + (0x5c0f << 4)"),
    ]


def load_ghidra_seeds():
    """Function starts from the Ghidra export, as file offsets.

    Main image: file = (seg << 4) + off - 0xCE00   (analysis/uwexe.md S8)
    CODE_TAIL : the printed address already is the file offset.
    """
    seeds = []
    if not os.path.exists(GHIDRA_FNS):
        return seeds
    for line in open(GHIDRA_FNS, encoding="latin-1"):
        a = line.split()
        if not a:
            continue
        t = a[0]
        if t.startswith("CODE_TAIL::"):
            seeds.append(int(t.split("::")[1], 16))
        elif t.startswith("int::"):
            continue          # DosSyscallAnalyzer service symbols, not code
        elif t.count(":") == 1:
            s, o = t.split(":")
            seeds.append((int(s, 16) << 4) + int(o, 16) - 0xCE00)
    return seeds


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--passes", type=int, default=8)
    ap.add_argument("--no-ghidra-seeds", action="store_true")
    args = ap.parse_args()

    os.makedirs(OUT, exist_ok=True)
    d = open(SRC, "rb").read()
    cont = Container(d)
    print("UW.EXE  %d bytes  sha256 %s" % (len(d), hashlib.sha256(d).hexdigest()))
    print("  header 0x%05x  image_end 0x%05x  relocs %d  entry file 0x%05x"
          % (cont.hdr_size, cont.image_end, cont.e_crlc, cont.entry))
    print("  FBOV segnum=%d ovrsize=0x%x exeinfo=0x%x"
          % (cont.fbov_segnum, cont.fbov_ovrsize, cont.fbov_exeinfo))
    for e in cont.check():
        print("  !! %s" % e)

    guard = [(lo, hi) for lo, hi, _ in known_data(cont)]

    seeds = [cont.entry]
    if not args.no_ghidra_seeds:
        g = load_ghidra_seeds()
        seeds += g
        print("  seeds: entry + %d Ghidra function starts" % len(g))

    dsc = Descent(d, cont, guard)
    t = time.time()
    dsc.run(seeds, cont.hdr_size, cont.image_end)
    dsc.run([cont.pool_off] + [s for s in seeds if s >= cont.pool_off],
            cont.pool_off, len(d))
    covered = sum(dsc.insns.values())
    print("  descent: %d instructions, %d bytes (%.1f%% of file) in %.1fs"
          % (len(dsc.insns), covered, 100.0 * covered / len(d), time.time() - t))
    print("           %s" % dsc.stats)

    variants = {}
    asm = os.path.join(OUT, "uw.asm")
    lst = os.path.join(OUT, "uw.lst")
    binout = os.path.join(OUT, "uw.bin")
    ok = False
    for p in range(1, args.passes + 1):
        linemap, dbset = emit(cont, dsc.insns, dsc.funcs, variants, asm)
        r, secs = assemble(asm, lst, binout)
        if r.returncode != 0:
            demoted = set()
            for m in re.finditer(r"uw\.asm:(\d+):", r.stderr):
                ent = linemap.get(int(m.group(1)))
                if ent and ent[1] is not None:
                    variants[ent[0]] = DB_RUNG
                    demoted.add(ent[0])
            print("pass %d: NASM failed, demoted %d line(s) to db" % (p, len(demoted)))
            src = open(asm, encoding="latin-1").read().split("\n")
            for m in list(re.finditer(r"uw\.asm:(\d+): error: (.*)", r.stderr))[:4]:
                ln = int(m.group(1))
                print("     %d: %-40s | %s" % (ln, src[ln - 1].strip(), m.group(2).strip()))
            if not demoted:
                print(r.stderr[:3000])
                return 1
            continue
        emitted = parse_listing(lst)
        bad, checked = verify(d, linemap, emitted)
        got = open(binout, "rb").read()
        ok = got == d
        print("pass %d: nasm %.1fs  out %d bytes  checked %d  mismatches %d  identical %s"
              % (p, secs, len(got), checked, len(bad), ok))
        if ok and not bad:
            break
        for off, n, gotb, wantb in bad[:6]:
            print("     0x%05x  got %-16s want %s" % (off, gotb.hex(), wantb.hex()))
        if not bad:
            print("  !! no per-line mismatch but binaries differ -- investigate")
            break
        for off, n, _, _ in bad:
            variants[off] = variants.get(off, 0) + 1

    got = open(binout, "rb").read()
    ok = got == d
    nins = len(dsc.insns)
    ndb = len(dbset)
    codebytes = sum(n for o, n in dsc.insns.items() if o not in dbset)
    print()
    print("RESULT: %s" % ("BYTE-IDENTICAL" if ok else "MISMATCH"))
    print("  rebuilt  sha256 %s" % hashlib.sha256(got).hexdigest())
    print("  original sha256 %s" % hashlib.sha256(d).hexdigest())
    print("  instructions as mnemonics: %d / %d (%.2f%%), %d forced to db"
          % (nins - ndb, nins, 100.0 * (nins - ndb) / max(nins, 1), ndb))
    print("  file bytes as real instructions: %d / %d (%.1f%%)"
          % (codebytes, len(d), 100.0 * codebytes / len(d)))

    with open(os.path.join(OUT, "fallbacks.txt"), "w", encoding="latin-1") as f:
        f.write("# instructions pinned with `db` because NASM re-encodes them\n")
        f.write("# offset  bytes                 capstone text\n")
        for o in sorted(dbset):
            n = dsc.insns[o]
            try:
                i = next(MDD.disasm(d[o:o + 16], o, count=1))
                t = "%s %s" % (i.mnemonic, i.op_str)
            except StopIteration:
                t = "(undecodable)"
            f.write("%06x  %-20s  %s\n" % (o, d[o:o + n].hex(), t))

    json.dump({"ok": ok, "insns": nins, "db_fallbacks": ndb,
               "code_bytes": codebytes, "file_bytes": len(d),
               "functions": len(dsc.funcs),
               "sha256": hashlib.sha256(got).hexdigest(),
               "descent": dsc.stats},
              open(os.path.join(OUT, "report.json"), "w"), indent=1)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
