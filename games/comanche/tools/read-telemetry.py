#!/usr/bin/env python3
"""Fail clearly because synthetic telemetry pixels are no longer rendered."""

import sys


def main() -> int:
    print(
        "read-telemetry.py is obsolete: the renderer no longer paints "
        "non-game telemetry pixels. Use emulator VBL timing and a real frame "
        "capture for verification.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
