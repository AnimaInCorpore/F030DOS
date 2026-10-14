#!/usr/bin/env python3
"""Copy-protection challenge tables, read out of the authority executable.

Everything here is recovered from `game/installed/INDYCAR.EXE` itself; nothing
is invented and nothing is patched.  See `analysis/copy-protection.md` for the
disassembly this encodes.

The gate has three parts:

  * a 169-entry table of packed page/line words (file 0xB29C8), one per
    challenge;
  * a 169-entry table of 32-bit hashes (file 0xAC584), the expected answer for
    the challenge with the same index;
  * a hash over the **first three characters** of the typed word, lowercased
    (routine at runtime 0x1BF320).

Because the hash keeps only three characters and is lossy, an accepted answer
is not necessarily the word printed in the manual: most entries have several
three-letter preimages.  `answer_for()` returns *an accepted string*, which is
what the DOS oracle needs, and the distinction is deliberate -- do not record a
recovered preimage as "the manual word".

    python tools/re/protection.py --list
    python tools/re/protection.py --answer 92 3
    python tools/re/protection.py --index 57
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import string
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXE = ROOT / 'game' / 'installed' / 'INDYCAR.EXE'
EXE_SHA256 = ('5B8BD9AA115C0E8CCD012617B161B44C'
              'E02124AA5875F2182EFA132ECA5B8B5A')

# File offsets.  The runtime addresses they correspond to are data-segment
# addresses; the data delta measured at the prompt is +0x13FEDC
# (analysis/executable.md).  Both tables are identical in the file and in a
# RAM dump, i.e. they carry no load-time fixups.
PAGELINE_OFF = 0xB29C8          # runtime 0x1F28A4, 169 x int16
HASH_OFF = 0xAC584              # runtime 0x1EC460, 169 x uint32
COUNT = 0xA9                    # 169; the divisor in `div ebx` at 0x1BF61B

# The answer is lowercased character by character before hashing (0x1DC837 is
# a plain A-Z tolower), so the search space is lowercase.  Digits and the two
# punctuation marks are included because a manual word may contain them; every
# entry already resolves with letters alone.
CHARSET = string.ascii_lowercase + string.digits + "'-"


def read_exe() -> bytes:
    data = EXE.read_bytes()
    got = hashlib.sha256(data).hexdigest().upper()
    if got != EXE_SHA256:
        raise SystemExit(f'{EXE} is not the recorded authority build\n'
                         f'  expected {EXE_SHA256}\n  got      {got}')
    return data


def word_hash(word: str) -> int:
    """Runtime 0x1BF320, transcribed.

        ecx = 1
        for each of at most 3 characters b:
            ecx = (ecx + ecx) - 1
            ecx ^= b | (b << 7)

    The loop stops at the NUL or after three characters, whichever comes
    first, so a one- or two-character answer hashes differently from the same
    prefix of a longer one.
    """
    ecx = 1
    for ch in word.lower()[:3]:
        b = ord(ch)
        ecx = (ecx + ecx - 1) & 0xFFFFFFFF
        ecx = (ecx ^ (b | (b << 7))) & 0xFFFFFFFF
    return ecx


def page_line(packed: int) -> tuple[int, int]:
    """Runtime 0x1BF629..0x1BF647: the entry is loaded as the high half of a
    dword read at a 2-byte stride and sign-extended (`sar eax, 0x10`), then

        page = 0xFF - ((v >> 4) & 0xFF)
        line = 7 - (v >> 12)

    with both shifts arithmetic.
    """
    return 0xFF - ((packed >> 4) & 0xFF), 7 - (packed >> 12)


def tables(data: bytes | None = None):
    """[(index, page, line, hash)] for all 169 challenges."""
    data = data if data is not None else read_exe()
    out = []
    for i in range(COUNT):
        packed = struct.unpack_from('<h', data, PAGELINE_OFF + 2 * i)[0]
        h = struct.unpack_from('<I', data, HASH_OFF + 4 * i)[0]
        page, line = page_line(packed)
        out.append((i, page, line, h))
    return out


def preimages(target: int, max_len: int = 3) -> list[str]:
    """Every string of up to `max_len` CHARSET characters that hashes to
    `target`, letters-only candidates first (they are typeable as plain QMP
    sendkey names)."""
    found = []
    for n in range(max_len, 0, -1):
        for t in itertools.product(CHARSET, repeat=n):
            s = ''.join(t)
            if word_hash(s) == target:
                found.append(s)
    found.sort(key=lambda s: (not s.isalpha(), len(s), s))
    return found


def answer_for_index(index: int, data: bytes | None = None) -> str:
    _, _, _, h = tables(data)[index]
    cands = preimages(h)
    if not cands:
        raise SystemExit(f'no preimage for challenge {index} (hash {h:#x})')
    return cands[0]


def answer_for(page: int, line: int, data: bytes | None = None) -> tuple[int, str]:
    for i, p, l, _ in tables(data):
        if (p, l) == (page, line):
            return i, answer_for_index(i, data)
    raise SystemExit(f'page {page}, line {line} is not one of the 169 challenges')


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--list', action='store_true',
                    help='all 169 challenges with an accepted answer')
    ap.add_argument('--answer', nargs=2, type=int, metavar=('PAGE', 'LINE'))
    ap.add_argument('--index', type=int, help='challenge index as the game '
                                              'stores it at 0x1EBDA8')
    args = ap.parse_args()
    data = read_exe()
    if args.list:
        for i, p, l, h in tables(data):
            c = preimages(h)
            print(f'{i:3d}  page {p:3d}, line {l}  hash {h:#010x}  '
                  f'accepted: {c[0]}  ({len(c)} preimages)')
    elif args.answer:
        i, a = answer_for(args.answer[0], args.answer[1], data)
        print(f'challenge index {i}: type "{a}"')
    elif args.index is not None:
        i, p, l, h = tables(data)[args.index]
        print(f'challenge index {i}: page {p}, line {l}, hash {h:#010x}, '
              f'type "{answer_for_index(i, data)}"')
    else:
        ap.print_help()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
