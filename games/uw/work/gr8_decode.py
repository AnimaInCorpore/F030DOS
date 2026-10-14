#!/usr/bin/env python3
"""Decode Ultima Underworld ``.GR`` type-8 records.

Type 8 is a nibble-packed, RLE-compressed 16-colour format.  The record's
auxiliary palette index selects a 16-byte translation table in ALLPALS.DAT;
the translated values are indices into the VGA palette in PALS.DAT.

The decoder is shared by UW1 and UW2.  Its control grammar was recovered from
the 16-bit draw path and is validated against every shipped record in both
games.
"""
import struct


class Bail(Exception):
    """The encoded stream ended before the declared data was consumed."""


class Nib:
    def __init__(self, nibbles):
        self.n = nibbles
        self.i = 0

    def get(self):
        if self.i >= len(self.n):
            raise Bail("nibble stream exhausted")
        value = self.n[self.i]
        self.i += 1
        return value

    def peek_done(self):
        return self.i >= len(self.n)


def unpack4(payload):
    """Return the declared nibble count and unpacked high-first nibbles."""
    if len(payload) < 2:
        raise Bail("missing type-8 nibble count")
    count = struct.unpack_from("<H", payload, 0)[0]
    src = payload[2:]
    need = (count + 1) // 2
    if len(src) < need:
        raise Bail("source exhausted during nibble unpack")
    out = []
    for byte in src[:need]:
        out.extend((byte >> 4, byte & 0xF))
    return count, out[:count]


def _read4(stream):
    return ((stream.get() << 12) | (stream.get() << 8) |
            (stream.get() << 4) | stream.get())


def _wider(stream):
    """Read the decoder's zero-extended 8/16-bit length form."""
    value = stream.get()
    return ((value << 4) | stream.get()) if value else _read4(stream)


def rle(nibbles, xlat=None):
    """Decode the type-8 run/literal grammar."""
    if xlat is None:
        xlat = bytes(range(16))
    if len(xlat) < 16:
        raise ValueError("type-8 translation table must contain 16 entries")

    stream = Nib(nibbles)
    out = bytearray()

    def literal_count():
        value = stream.get()
        return value if value else _wider(stream)

    def emit_run(length):
        value = xlat[stream.get()]
        out.extend([value] * length)

    def run_only(control):
        if control > 2:
            emit_run(control)
        elif control == 0:
            value = stream.get()
            length = ((value << 4) | stream.get()) if value else _read4(stream)
            emit_run(length)
        # control == 1 means no run.

    while not stream.peek_done():
        control = stream.get()
        if control == 2:
            count = stream.get()
            count = count if count else _wider(stream)
            for _ in range(count):
                if stream.peek_done():
                    raise Bail("grouped run list ended early")
                run_only(stream.get())
        else:
            run_only(control)

        for _ in range(literal_count()):
            out.append(xlat[stream.get()])
    return bytes(out)


def decode_type8(record, xlat=None):
    """Decode a complete type-8 record, including its 5-byte header."""
    if len(record) < 6 or record[0] != 8:
        raise ValueError("not a type-8 record")
    _count, nibbles = unpack4(record[4:])
    return rle(nibbles, xlat)


def records(data):
    """Return ``(start, end)`` bounds for all records in a standard archive."""
    if len(data) < 7:
        raise ValueError(".GR file is too short")
    count = struct.unpack_from("<H", data, 1)[0]
    offsets = [
        data[3 + 4 * i] |
        (data[4 + 4 * i] << 8) |
        (data[5 + 4 * i] << 16)
        for i in range(count + 1)
    ]
    table_end = 3 + 4 * (count + 1)
    if offsets[0] != table_end:
        raise ValueError("non-standard .GR table start")
    if offsets[-1] != len(data):
        raise ValueError(".GR table does not end at file size")
    if any(a > b for a, b in zip(offsets, offsets[1:])):
        raise ValueError(".GR offsets are not monotonic")
    return [(offsets[i], offsets[i + 1]) for i in range(count)]


if __name__ == "__main__":
    from collections import Counter
    from pathlib import Path

    root = Path("work/expanded/DATA")
    total = decoded = bailed = 0
    lengths = Counter()
    for path in sorted(root.glob("*.GR")):
        data = path.read_bytes()
        for index, (start, end) in enumerate(records(data)):
            if end <= start or data[start] != 8:
                continue
            total += 1
            try:
                pixels = decode_type8(data[start:end])
            except Bail as exc:
                bailed += 1
                if bailed <= 3:
                    print(f"BAIL {path.name}#{index}: {exc}")
                continue
            decoded += 1
            lengths[len(pixels) - data[start + 1] * data[start + 2]] += 1
    print(f"type-8 records: {total}")
    print(f"decoded without overrun: {decoded}/{total}")
    print(f"decoder bailouts: {bailed}")
    print("output length minus w*h: " + ", ".join(
        f"{key:+d}={lengths[key]}" for key in sorted(lengths)))
    raise SystemExit(0 if total == decoded and not bailed else 1)
