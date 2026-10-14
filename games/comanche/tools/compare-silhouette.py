#!/usr/bin/env python3
"""Reject the retired pinned-camera silhouette comparison."""

import sys


def main() -> int:
    print(
        "compare-silhouette.py is obsolete: it depended on the removed "
        "pinned-camera build. Use tools/compare-terrain.py on an actual "
        "attract-demo capture.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
