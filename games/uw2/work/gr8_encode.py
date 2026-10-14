#!/usr/bin/env python3
"""Byte-exact encoder for UW2 `.GR` type-8 records.

The encoder is the inverse of ``gr8_decode.py``'s format-8 path.  It consumes
the pixels after the auxiliary palette translation, inverts that 16-entry
translation back to nibble values, then emits the original greedy run/literal
grammar.  All 736 shipped type-8 records round-trip byte-for-byte.
"""
import struct

from gr8_decode import decode_type8


def _literal_length(n):
    """Encode a literal-group length (direct, 8-bit escape, or 16-bit)."""
    if n < 16:
        return [n]
    if n < 256:
        return [0, n >> 4, n & 0xF]
    return [0, 0, (n >> 12) & 0xF, (n >> 8) & 0xF,
            (n >> 4) & 0xF, n & 0xF]


def _run_length_body(n):
    """Encode the body following a run control of zero.

    Unlike literal lengths, the control zero has already been consumed, so an
    8-bit run length is only two nibbles; a 16-bit length begins with zero.
    """
    if n < 256:
        return [n >> 4, n & 0xF]
    return [0, (n >> 12) & 0xF, (n >> 8) & 0xF,
            (n >> 4) & 0xF, n & 0xF]


def _run_token(n, value):
    """Encode one run inside a normal or grouped run control."""
    if 3 <= n <= 15:
        return [n, value]
    return [0, *_run_length_body(n), value]


def encode_rle(source, content_length):
    """Encode pre-palette nibble values into the type-8 RLE stream.

    The original encoder scans maximal runs of at least three values.  A final
    two-pixel decoder overrun is reproduced by allowing the first padding pixel
    into the run scan; the second remains a literal.  This is the measured
    rule behind the 119/452/165 output-length distribution.
    """
    pixels = list(source)
    if any(not 0 <= p <= 0xF for p in pixels):
        raise ValueError("type-8 source values must be nibbles")
    padding = len(pixels) - content_length
    if padding not in (0, 1, 2):
        raise ValueError(f"unexpected type-8 padding: {padding}")

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

    out = []
    if not runs:
        return [1, *_literal_length(len(pixels)), *pixels]

    if runs[0][0]:
        n = runs[0][0]
        out += [1, *_literal_length(n), *pixels[:n]]

    ri = 0
    while ri < len(runs):
        start = ri
        ri += 1
        while (ri < len(runs)
               and runs[ri][0] == runs[ri - 1][0] + runs[ri - 1][1]):
            ri += 1
        group = runs[start:ri]

        if len(group) == 1:
            _, n, value = group[0]
            out += _run_token(n, value)
        else:
            out += [2, *_literal_length(len(group))]
            for _, n, value in group:
                out += _run_token(n, value)

        end = group[-1][0] + group[-1][1]
        next_start = runs[ri][0] if ri < len(runs) else len(pixels)
        out += _literal_length(next_start - end)
        out += pixels[end:next_start]

    return out


def _pack(nibbles, trailing_nibble=0):
    out = bytearray(struct.pack("<H", len(nibbles)))
    for i in range(0, len(nibbles), 2):
        hi = nibbles[i]
        lo = (nibbles[i + 1] if i + 1 < len(nibbles)
              else trailing_nibble)
        out.append((hi << 4) | lo)
    return bytes(out)


def _inverse_palette(table, pixels):
    reverse = {}
    for nibble, value in enumerate(table):
        # Duplicate palette entries exist, but the shipped records use the
        # first source nibble for those values.  Keeping first occurrence is
        # the only deterministic inverse and is verified by the full census.
        reverse.setdefault(value, nibble)
    try:
        return [reverse[p] for p in pixels]
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
    # The low half of an odd final packed byte is not consumed by the game,
    # but shipped files preserve arbitrary values there.  Carry that
    # unreferenced nibble exactly, like the trailing Huffman slack in STRINGS.
    trailing = record[-1] & 0xF if len(nibbles) & 1 else 0
    payload = _pack(nibbles, trailing)
    return record[:4] + payload
