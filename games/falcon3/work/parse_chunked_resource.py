#!/usr/bin/env python3
"""Parse the verified indexed chunks used by Falcon's COCKPIT loader.

This is intentionally a structural parser, not a decoder.  The loader reads
the first six little-endian offsets, seeks to each offset, reads a 16-bit
payload length, and streams that payload.  The final bytes after the sixth
payload are retained as an unresolved tail.
"""

from __future__ import annotations

import hashlib
import json
import struct
import sys
from pathlib import Path


def parse(path: Path) -> dict:
    data = path.read_bytes()
    if len(data) < 12:
        raise ValueError(f"{path} is too short for a six-entry index")

    offsets = list(struct.unpack_from("<6H", data, 0))
    if offsets[0] != 12 or any(a >= b for a, b in zip(offsets, offsets[1:])):
        raise ValueError(f"unexpected offset index: {offsets!r}")

    chunks = []
    for index, start in enumerate(offsets):
        if start + 2 > len(data):
            raise ValueError(f"chunk {index} length word is outside the file")
        length = struct.unpack_from("<H", data, start)[0]
        payload_start = start + 2
        payload_end = payload_start + length
        expected_end = offsets[index + 1] if index + 1 < len(offsets) else None
        chunks.append({
            "index": index,
            "offset": start,
            "length_word": length,
            "payload_start": payload_start,
            "payload_end": payload_end,
            "next_index_offset": expected_end,
            "reaches_next_index": expected_end is None or payload_end == expected_end,
            "sha256": hashlib.sha256(data[payload_start:payload_end]).hexdigest(),
        })

    last_end = chunks[-1]["payload_end"]
    return {
        "file": str(path),
        "size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "index_offsets": offsets,
        "chunks": chunks,
        "tail": {
            "offset": last_end,
            "length": len(data) - last_end,
            "sha256": hashlib.sha256(data[last_end:]).hexdigest(),
        },
    }


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else root / "game" / "FALCON3" / "COCKPIT"
    result = parse(path)
    output = root / "work" / "qemu_out" / "cockpit_chunk_index.json"
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    print(f"saved {output}")


if __name__ == "__main__":
    main()
