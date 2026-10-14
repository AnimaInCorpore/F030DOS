#!/usr/bin/env python3
"""Byte-exact encoder for UW1 ``.GR`` type-8 records."""
import struct

from gr8_decode import decode_type8


def _literal_length(length):
    if length < 16:
        return [length]
    if length < 256:
        return [0, length >> 4, length & 0xF]
    return [0, 0, (length >> 12) & 0xF, (length >> 8) & 0xF,
            (length >> 4) & 0xF, length & 0xF]


def _run_length_body(length):
    if length < 256:
        return [length >> 4, length & 0xF]
    return [0, (length >> 12) & 0xF, (length >> 8) & 0xF,
            (length >> 4) & 0xF, length & 0xF]


def _run_token(length, value):
    if 3 <= length <= 15:
        return [length, value]
    return [0, *_run_length_body(length), value]


def encode_rle(source, content_length):
    """Encode the original greedy run/literal grammar."""
    pixels = list(source)
    if any(not 0 <= value <= 0xF for value in pixels):
        raise ValueError("type-8 source values must be nibbles")
    padding = len(pixels) - content_length
    if padding not in (0, 1, 2):
        raise ValueError(f"unexpected type-8 padding: {padding}")

    # The original decoder may emit one or two final padding pixels.  When
    # there are two, the first participates in the encoder's run scan.
    scan_end = content_length + (padding == 2)
    runs = []
    i = 0
    while i < scan_end:
        j = i + 1
        while j < scan_end and pixels[j] == pixels[i]:
            j += 1
        if j - i >= 3:
            runs.append((i, j - i, pixels[i]))
        i = j

    if not runs:
        return [1, *_literal_length(len(pixels)), *pixels]

    out = []
    if runs[0][0]:
        first = runs[0][0]
        out += [1, *_literal_length(first), *pixels[:first]]

    run_index = 0
    while run_index < len(runs):
        group_start = run_index
        run_index += 1
        while (run_index < len(runs) and
               runs[run_index][0] ==
               runs[run_index - 1][0] + runs[run_index - 1][1]):
            run_index += 1
        group = runs[group_start:run_index]

        if len(group) == 1:
            _, length, value = group[0]
            out += _run_token(length, value)
        else:
            out += [2, *_literal_length(len(group))]
            for _, length, value in group:
                out += _run_token(length, value)

        end = group[-1][0] + group[-1][1]
        next_start = runs[run_index][0] if run_index < len(runs) else len(pixels)
        out += _literal_length(next_start - end)
        out += pixels[end:next_start]
    return out


def _pack(nibbles, trailing=0):
    out = bytearray(struct.pack("<H", len(nibbles)))
    for i in range(0, len(nibbles), 2):
        high = nibbles[i]
        low = nibbles[i + 1] if i + 1 < len(nibbles) else trailing
        out.append((high << 4) | low)
    return bytes(out)


def _inverse_palette(table, pixels):
    reverse = {}
    for nibble, value in enumerate(table):
        # Duplicate entries occur in auxiliary palettes.  Shipped records use
        # the first source nibble for those values; the full census verifies
        # that this deterministic inverse reproduces the source bytes.
        reverse.setdefault(value, nibble)
    try:
        return [reverse[pixel] for pixel in pixels]
    except KeyError as exc:
        raise ValueError(f"pixel {exc.args[0]:#x} is absent from aux palette") from exc


def encode_type8_record(record, allpals):
    """Decode and re-encode one complete type-8 record."""
    if len(record) < 6 or record[0] != 8:
        raise ValueError("not a type-8 record")
    width, height, aux_index = record[1], record[2], record[3]
    table = allpals[aux_index * 16:aux_index * 16 + 16]
    if len(table) != 16:
        raise ValueError(f"missing auxiliary palette {aux_index}")
    pixels = decode_type8(record, table)
    source = _inverse_palette(table, pixels)
    nibbles = encode_rle(source, width * height)
    trailing = record[-1] & 0xF if len(nibbles) & 1 else 0
    return record[:4] + _pack(nibbles, trailing)
