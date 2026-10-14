#!/usr/bin/env python3
"""Reconstruct the two-volume INDYCAR code archive without touching media.

The installer configuration calls the two files a ``MergeSet INDYCAR``.  The
first volume contains a 40-byte distribution prefix followed by an LHA stream;
the second volume is its byte-for-byte continuation.  The merged output is a
work artifact and is deliberately kept separate from the shipped files.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", type=Path,
                        default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    project = args.project.resolve()
    first = project / "game" / "disks" / "disk1" / "INDYCAR.001"
    second = project / "game" / "disks" / "disk2" / "INDYCAR.002"
    if not first.is_file() or not second.is_file():
        raise SystemExit("run extract_media.py before merge_indycar.py")
    first_bytes = first.read_bytes()
    second_bytes = second.read_bytes()
    if len(first_bytes) < 40 or first_bytes[8:15] != b"INDYCAR":
        raise SystemExit("INDYCAR.001 does not have the expected merge prefix")
    if first_bytes[40:45] != b"$\xee-lh":
        # The first LHA header is level-0: 0x24, checksum 0xee, then -lh5-.
        raise SystemExit("INDYCAR.001 does not have the expected LHA stream")
    merged = first_bytes + second_bytes
    output = project / "work" / "INDYCAR.MERGED"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(merged)
    print(f"INDYCAR.001: {len(first_bytes)} bytes {digest(first_bytes)}")
    print(f"INDYCAR.002: {len(second_bytes)} bytes {digest(second_bytes)}")
    print(f"merged:       {len(merged)} bytes {digest(merged)}")
    print(f"archive stream begins at byte 40: {digest(merged[40:])}")
    print(f"wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
