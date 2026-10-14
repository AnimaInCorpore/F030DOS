#!/usr/bin/env python3
"""Payload decoders for the LFD record types (todo P2.1).

All four models below were validated over every record of that type in
game/SWTieCD/TIECD -- see analysis/LFD.md for the verification scope.

DELT (370/370) -- sparse paletted bitmap
    i16 left, top, right, bottom              # inclusive bounding box
    spans, until a u16 0x0000 terminator:
        u16 v ; i16 x ; i16 y                 # (v>>1) pixels starting at (x,y)
        v&1 == 0 : (v>>1) raw pixel bytes
        v&1 == 1 : RLE -- op&1 ? (op>>1) copies of the next byte
                                 : (op>>1) literal bytes
    Uncovered pixels are transparent (only 77 of 370 cover their whole box).

ANIM (355/355) -- u16 frame count, then per frame u32 length + a DELT payload.

PLTT (296/296) -- u8 first, u8 last, RGB[last-first+1], u8 k, k*4 trailer bytes.
    k is 0 in 293 records; the 3 records with k>0 are listed in analysis/LFD.md
    and their 4-byte entries are still TBD.

PANL (70/70) -- STRUCTURE ONLY. Byte stream, no header; the opcode set is taken
    from the blitter at 0x0004977C (analysis/LFD.md 5):
        0xFB v ?   3 bytes  -- sets a colour bias applied to later literals
        0xFC i     2 bytes  -- advances the x position via runtime tables
        0xFD w     3 bytes  -- run: u16 operand, low byte indexes a width table,
                               high byte is the colour
        0xFE       1 byte   -- end of row
        0xFF       1 byte   -- end of panel, + 0..2 bytes of 0x0A padding
        else       1 byte   -- literal: the byte is SPLIT by a mask/shift held in
                               the panel struct into (width index, colour)
    ~~"0xFD cnt val = run, 0xFE = end of row, anything else = one literal pixel"~~
    is WITHDRAWN (2026-08-22): it ignored 0xFB/0xFC and desynchronised on the
    29,070 0xFC opcodes in the tree.
    Rows per record are exactly 189 or 200 (CP320) / 456 or 480 (CP640) -- 200 and
    480 being the screen heights -- and every payload ends on 0xFF.
    PIXELS ARE NOT DECODED: literal width/colour and the 0xFC advance both need
    tables the game builds at run time. decode_panl() returns the token stream,
    not pixels.

TEXT (27/27) -- u16 block count, then per block u16 length + NUL-separated strings.

FILM (149/149) -- the scene sequencer:
    u16 version (4 in all 149), u16 frameCount, u16 blockCount
    (blockCount+1) blocks, each   {char type[4]; char name[8]; u32 length}
        NOTE: unlike the LFD container, this length INCLUDES the 16-byte header
        The last block is always type "END".
    block payload:  u16 typeCode, u16 chunkCount,
                    chunkCount x { u16 time; u16 lenBytes;
                                   u16 opcode; u16 params[(len-6)/2] },
                    u16 terminator (2 in all 2,939 non-END blocks)
    typeCode: VIEW=2 VOIC=5 PLTT=4 DELT=ANIM=CUST=3 END=1 (END has no chunks).
    A chunk of lenBytes==4 carries no opcode -- it is the block's end marker.
    CORRECTED 2026-08-22: the opcode is the THIRD word, not the first (the first
    is a time/frame stamp). 20 distinct opcodes, each with a fixed parameter
    count; see analysis/LFD.md 6b.
    Each non-END block names an LFD record of the same type -- so a FILM is the
    list of resources a scene uses, which is what tells you which PLTT belongs
    with which DELT.

SHIP (78/78 unique models) -- HEADER ONLY, decode_ship_header(); the geometry
    past 0x24 is not decoded (see analysis/LFD.md).

VOIC / BLAS (342/342) -- standard Creative Voice File v1.10, checked by
    check_voc(); GMID (179/179) + the 4 standalone .GMD files -- "MIDI" + u32be
    length + MDpg/MThd/MTrk chunks, checked by check_gmid().
"""
import struct, zlib

TRANSPARENT = -1


def decode_delt(data):
    """-> (left, top, width, height, rows) with rows[y][x] = index or TRANSPARENT."""
    left, top, right, bottom = struct.unpack_from("<4h", data)
    w, h = right - left + 1, bottom - top + 1
    px = [[TRANSPARENT] * w for _ in range(h)]
    off = 8
    while off + 2 <= len(data):
        v = struct.unpack_from("<H", data, off)[0]
        if v == 0:
            off += 2
            break
        x, y = struct.unpack_from("<2h", data, off + 2)
        off += 6
        n, rle = v >> 1, v & 1
        row, col = px[y - top], x - left
        if rle:
            got = 0
            while got < n:
                op = data[off]; off += 1
                cnt = op >> 1
                if op & 1:
                    row[col:col + cnt] = [data[off]] * cnt; off += 1
                else:
                    row[col:col + cnt] = list(data[off:off + cnt]); off += cnt
                col += cnt; got += cnt
        else:
            row[col:col + n] = list(data[off:off + n]); off += n
    if off != len(data):
        raise ValueError(f"DELT: {len(data) - off} trailing bytes")
    return left, top, w, h, px


def decode_anim(data):
    """-> list of decode_delt() tuples, one per frame."""
    count = struct.unpack_from("<H", data, 0)[0]
    frames, off = [], 2
    for _ in range(count):
        length = struct.unpack_from("<I", data, off)[0]; off += 4
        frames.append(decode_delt(data[off:off + length])); off += length
    if off != len(data):
        raise ValueError(f"ANIM: {len(data) - off} trailing bytes")
    return frames


def decode_pltt(data, palette=None):
    """Apply one PLTT range onto a 256-entry palette. -> (palette, trailer)."""
    pal = list(palette) if palette is not None else [(0, 0, 0)] * 256
    first, last = data[0], data[1]
    off = 2
    for i in range(first, last + 1):
        pal[i] = (data[off], data[off + 1], data[off + 2]); off += 3
    k = data[off]; off += 1
    trailer = [bytes(data[off + 4 * j: off + 4 * j + 4]) for j in range(k)]
    if off + 4 * k != len(data):
        raise ValueError("PLTT: length mismatch")
    return pal, trailer


PANL_OPS = {0xFB: 3, 0xFC: 2, 0xFD: 3}      # opcode -> total bytes


def decode_panl(data):
    """-> list of rows, each a list of (opcode_or_None, raw_bytes) tokens.

    Structure only -- see the module docstring. A token with opcode None is a
    literal byte, whose split into (width index, colour) is not recoverable
    statically. Raises if the payload does not end exactly on a 0xFE.
    """
    rows, row, off = [], [], 0
    while off < len(data):
        b = data[off]
        if b == 0xFF:                       # end of panel
            off += 1
            while off < len(data) and data[off] == 0x0A:    # 0-2 bytes of padding
                off += 1
            break
        if b == 0xFE:
            rows.append(row); row = []; off += 1
        elif b in PANL_OPS:
            n = PANL_OPS[b]
            row.append((b, data[off:off + n])); off += n
        else:
            row.append((None, data[off:off + 1])); off += 1
    if row:
        raise ValueError(f"PANL: {len(row)} tokens after the last 0xFE")
    if off != len(data):
        raise ValueError(f"PANL: {len(data) - off} bytes after the 0xFF terminator")
    if len(rows) not in (189, 200, 456, 480):
        raise ValueError(f"PANL: {len(rows)} rows, expected 189/200/456/480")
    return rows


def write_png(path, w, h, rows, pal):
    """8-bit RGBA PNG; TRANSPARENT pixels get alpha 0."""
    raw = bytearray()
    for row in rows:
        raw.append(0)
        for p in row:
            if p == TRANSPARENT:
                raw += b"\0\0\0\0"
            else:
                r, g, b = pal[p]
                raw += bytes((r, g, b, 255))

    def chunk(tag, payload):
        return (struct.pack(">I", len(payload)) + tag + payload
                + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF))

    with open(path, "wb") as fh:
        fh.write(b"\x89PNG\r\n\x1a\n")
        fh.write(chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)))
        fh.write(chunk(b"IDAT", zlib.compress(bytes(raw), 9)))
        fh.write(chunk(b"IEND", b""))


def decode_text(data):
    """-> list of blocks, each a list of strings."""
    count = struct.unpack_from("<H", data, 0)[0]
    blocks, off = [], 2
    for _ in range(count):
        length = struct.unpack_from("<H", data, off)[0]; off += 2
        blk = data[off:off + length]; off += length
        if len(blk) != length:
            raise ValueError("TEXT: block runs past the payload")
        strings = blk.split(b"\0")
        if strings and strings[-1] == b"":
            strings.pop()
        blocks.append([s.decode("latin1") for s in strings])
    if off != len(data):
        raise ValueError(f"TEXT: {len(data) - off} trailing bytes")
    return blocks


VOC_MAGIC = b"Creative Voice File\x1a"


def check_voc(data):
    """Walk a Creative VOC payload. -> (version, [block type codes])."""
    if not data.startswith(VOC_MAGIC):
        raise ValueError("VOC: bad magic")
    data_off, version, _checksum = struct.unpack_from("<HHH", data, 20)
    types, off = [], data_off
    while off < len(data):
        t = data[off]
        types.append(t)
        if t == 0:                                   # terminator block
            break
        length = data[off + 1] | data[off + 2] << 8 | data[off + 3] << 16
        off += 4 + length
    return version, types


def check_gmid(data):
    """Walk a GMID/.GMD payload. -> [chunk tags]."""
    if not data.startswith(b"MIDI"):
        raise ValueError("GMID: bad magic")
    total = struct.unpack_from(">I", data, 4)[0]
    if 8 + total != len(data):
        raise ValueError(f"GMID: header length {total} != payload {len(data) - 8}")
    tags, off = [], 8
    while off + 8 <= len(data):
        tag = data[off:off + 4]
        length = struct.unpack_from(">I", data, off + 4)[0]
        tags.append(tag.decode("latin1"))
        off += 8 + length
    if off != len(data):
        raise ValueError("GMID: chunk walk overran the payload")
    return tags


def decode_film(data):
    """-> (version, frame_count, [(type, name, [(time, opcode, params)])]).

    The trailing END block is included, with an empty chunk list.
    """
    version, frames, count = struct.unpack_from("<3H", data, 0)
    blocks, off = [], 6
    for _ in range(count + 1):
        type_ = data[off:off + 4].split(b"\0")[0].decode("ascii", "replace")
        name = data[off + 4:off + 12].split(b"\0")[0].decode("ascii", "replace")
        length = struct.unpack_from("<I", data, off + 12)[0]
        if length < 16 or off + length > len(data):
            raise ValueError(f"FILM: block {type_} length {length}")
        pay = data[off + 16:off + length]
        off += length
        w = struct.unpack(f"<{len(pay) // 2}H", pay)
        chunks = []
        if type_ != "END":
            i = 2
            for _ in range(w[1]):
                time, ln = w[i], w[i + 1]
                if ln < 4 or ln % 2:
                    raise ValueError(f"FILM: {type_} chunk length {ln}")
                opcode = w[i + 2] if ln >= 6 else None      # len 4 = end marker
                chunks.append((time, opcode, list(w[i + 3:i + ln // 2])))
                i += ln // 2
            if len(w) - i != 1:
                raise ValueError(f"FILM: {type_} has {len(w) - i} trailing words")
        blocks.append((type_, name, chunks))
    if off != len(data):
        raise ValueError(f"FILM: {len(data) - off} trailing bytes")
    return version, frames, blocks


def decode_ship_header(data):
    """SHIP header -- the verified part only (analysis/LFD.md).

    Every field below holds across all 78 unique SHIP records; the geometry that
    follows is NOT decoded, so this deliberately stops at 0x24.
    """
    (length, version, z4, z6,
     span_x, span_y, span_z, span_max) = struct.unpack_from("<8H", data, 0)
    unknown10 = struct.unpack_from("<I", data, 0x10)[0]
    bbox = struct.unpack_from("<6h", data, 0x14)
    if length != len(data) - 2:
        raise ValueError(f"SHIP: length {length} != record {len(data)} - 2")
    if version != 0x0100:
        raise ValueError(f"SHIP: word at 0x02 is {version:#06x}, not 0x0100")
    if (z4, z6) != (0, 0):
        raise ValueError(f"SHIP: words at 0x04/0x06 are {z4}/{z6}, not 0")
    spans = tuple((bbox[i + 3] - bbox[i]) & 0xFFFF for i in range(3))
    if (span_x, span_y, span_z) != spans:
        raise ValueError(f"SHIP: spans {(span_x, span_y, span_z)} != bbox spans {spans}")
    if span_max != max(spans):
        raise ValueError(f"SHIP: span_max {span_max} != max{spans}")
    return {
        "length": length, "version": version,
        "spans": spans, "span_max": span_max,
        "unknown_0x10": unknown10,          # u32, semantics unknown
        "bbox": bbox,                       # minX,minY,minZ,maxX,maxY,maxZ
        "count_0x20": data[0x20],           # u8, observed 1..39
        "count_0x21": data[0x21],           # u8, observed 1..5
        "word_0x22": struct.unpack_from("<H", data, 0x22)[0],   # 0 or 2
    }
