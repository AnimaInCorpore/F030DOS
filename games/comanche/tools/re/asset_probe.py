#!/usr/bin/env python3
"""Report measured Comanche resource markers without decoding payloads."""

import argparse
import json
import struct
from pathlib import Path


def classify(path: Path) -> dict:
    data = path.read_bytes()
    result = {
        "name": path.name,
        "size": len(data),
        "extension": path.suffix.upper(),
        "format": "unknown",
    }

    if data.startswith(b"Kyle DTA"):
        result["format"] = "DTA"
        if len(data) >= 16:
            result["candidate_geometry_words"] = list(
                struct.unpack_from("<4H", data, 8)
            )
    elif data[:4] in (b"KRL0", b"KRL1"):
        result["format"] = data[:4].decode("ascii")
        stream = data[8:12]
        if stream.startswith(b"SG"):
            result["stream_family"] = "SG"
        elif stream.startswith(b"MS3"):
            result["stream_family"] = "MS3"
        elif stream.startswith(b"K1"):
            result["stream_family"] = "K1"
        else:
            result["stream_family"] = stream.hex()
    elif path.suffix.upper() == ".DTL" and len(data) % 4 == 0:
        result["format"] = "DTL-candidate"
        result["dword_count"] = len(data) // 4
        result["first_dword"] = struct.unpack_from("<I", data)[0]
    elif path.suffix.upper() == ".SCR" and len(data) >= 4:
        result["format"] = "SCR-candidate"
        payload_length = struct.unpack_from("<H", data)[0]
        result["payload_length"] = payload_length
        result["length_matches_file"] = payload_length == len(data) - 4
    elif path.suffix.upper() == ".MIS":
        result["format"] = "MIS-unknown"

    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="file or installed asset directory")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()

    if args.path.is_dir():
        paths = sorted(p for p in args.path.iterdir() if p.is_file())
    else:
        paths = [args.path]
    records = [classify(path) for path in paths]

    if args.as_json:
        print(json.dumps(records, indent=2))
        return

    print("name             size  format          details")
    print("---------------- ----- --------------- ------------------------------")
    for record in records:
        details = []
        for key in (
            "candidate_geometry_words",
            "stream_family",
            "dword_count",
            "first_dword",
            "payload_length",
            "length_matches_file",
        ):
            if key in record:
                details.append(f"{key}={record[key]}")
        print(
            f"{record['name']:<16} {record['size']:>5} "
            f"{record['format']:<15} {' '.join(details)}"
        )


if __name__ == "__main__":
    main()
