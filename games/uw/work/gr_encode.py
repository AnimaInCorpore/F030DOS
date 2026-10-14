#!/usr/bin/env python3
"""Re-emit standard UW1 ``.GR`` archives from decoded records."""
import struct

from gr8_encode import encode_type8_record


def _encode_type10(record):
    width, height = record[1], record[2]
    count = width * height
    payload = record[5:]
    packed_len = (count + 1) // 2
    if len(payload) < packed_len:
        raise ValueError("type-0a payload is shorter than width*height")
    nibbles = []
    for byte in payload[:packed_len]:
        nibbles.extend((byte >> 4, byte & 0xF))
    trailing = payload[packed_len - 1] & 0xF if count & 1 else 0
    rebuilt = bytearray()
    for i in range(0, count, 2):
        high = nibbles[i]
        low = nibbles[i + 1] if i + 1 < count else trailing
        rebuilt.append((high << 4) | low)
    # The byte following the packed pixels is format slack; preserve it.
    return record[:5] + bytes(rebuilt) + payload[packed_len:]


def encode_record(record, allpals):
    if not record:
        return record
    rtype = record[0]
    if rtype == 8:
        return encode_type8_record(record, allpals)
    if rtype == 4:
        width, height = record[1], record[2]
        if len(record) != 5 + width * height:
            raise ValueError("type-4 payload length does not equal width*height")
        return record
    if rtype == 10:
        return _encode_type10(record)
    raise ValueError(f"unsupported standard .GR record type: {rtype:#x}")


def rebuild_archive(data, allpals):
    """Rebuild a standard container, including a fresh offset table."""
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
    if offsets[0] != table_end or offsets[-1] != len(data):
        raise ValueError("non-standard .GR offset table")

    out = bytearray(data[:3])
    table_at = len(out)
    out += b"\0" * (4 * (count + 1))
    new_offsets = []
    for i in range(count):
        start, end = offsets[i], offsets[i + 1]
        if end < start or end > len(data):
            raise ValueError(f"bad .GR record bounds at index {i}")
        new_offsets.append(len(out))
        out += encode_record(data[start:end], allpals)
    new_offsets.append(len(out))

    for i, offset in enumerate(new_offsets):
        out[table_at + 4 * i:table_at + 4 * i + 3] = bytes((
            offset & 0xFF, (offset >> 8) & 0xFF, (offset >> 16) & 0xFF))
    return bytes(out)
