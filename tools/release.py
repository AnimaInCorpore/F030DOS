#!/usr/bin/env python3
"""Pack a release: the Falcon programs of the ports that have one, and a README.TXT.  No game data is packed: each
program loads the player's own copy of the game at run time, and the README.TXT says which files go where.

    python3 tools/release.py <version> [--no-build] [--allow-embedded]
        -> release/F030DOS-<version>/ and release/F030DOS-<version>.zip

Each program is built with `make <game>` (the root Makefile supplies the toolchain) and must be a TOS executable.
Then every program is compared with the game files found locally (the directories listed per game below): a 32-byte
block of the game that also occurs in a program means the program carries game content.  That stops the release
unless --allow-embedded is given, and the README.TXT then says so.  A game whose files are not here is reported as
not checked.  These are engineering checks, not a rights review (docs/PUBLICATION.md).
"""
import argparse
import hashlib
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLOCK = 32

# key, title, files (relative to games/<key>/; the first is the program), game file directories for the embedded-
# content check, what the player has to supply, state.  Keep the states in step with games/<key>/README.md and the
# root README's table.  Ports without a Falcon program (or with only a test harness) are not listed.
GAMES = [
    ("comanche", "Comanche: Maximum Overkill (1992)",
     ["release/comanche.tos"], ["assets/extracted/comanche_hdd", "re/unpacked"],
     "Copy the files of your installed DOS game (the COMANCHE directory) next to COMANCHE.TOS. The program reads the "
     "terrain, palettes, sprites, skies, demo flights, sound banks and missions from there. COMANCHE.MNU selects the "
     "detail level as in DOS: the shipped file says MEDIUM; the development builds stage a copy set to HIGH.",
     "the attract cycle on the CPU renderer with live-flight, menu, mission-end and combat extensions; not certified "
     "against the DOS original, the DSP renderer is dormant, real-hardware speed not measured"),
    ("f29", "F29 Retaliator (1990)",
     ["release/f29.tos", "release/3d.lod"], ["assets"],
     "Keep F29.TOS and 3D.LOD (the DSP program) together.",
     "the DSP/blitter scene renderer with the flight-state core and a custom menu and HUD; the original presentation "
     "and mission behaviour are not reproduced yet"),
    ("por", "Pool of Radiance (1988)",
     ["release/por.tos"], ["work/expanded"],
     "POR.TOS reads the folder PORCACHE next to it, converted from your own copy of the game on a PC: put the "
     "archive named in games/por/README.md into games/por/assets/ and run `make -C games/por data falcon-data`.",
     "the title image, which matches the host expansion of the DOS data at 4 MB and 14 MB; no gameplay yet"),
    ("wc1", "Wing Commander (1990)",
     ["release/wc1.tos"], ["release/WC1DATA"],
     "WC1.TOS reads the folder WC1DATA next to it: the files of your three DOS disks (`make -C games/wc1 data` "
     "unpacks WC_Disk1..3.zip into it). The optional WC1CACHE folder (`make -C games/wc1 falcon-data`) speeds up "
     "mission loading.",
     "title, opening and credits, mission loading, cockpit, mobile fighters, cannon combat and damage; campaign, "
     "navigation and missiles unfinished, the flight depth merge unproven"),
]

README = """F030DOS {version}
{underline}

DOS games ported to the Atari Falcon030.  Each port re-implements the original DOS program function by function,
checked against the original running in an emulator; the game's data is read from the player's own copy.  Source
and documentation: https://github.com/AnimaInCorpore/F030DOS  (commit {commit})

This is a preview: none of the games is complete.  The states below are measured in the patched Hatari of the
F030Arcade project; speed on a real Falcon has not been measured.

Requirements: a Falcon030 with 14 MB of RAM, an RGB or VGA monitor, and your own copy of each game.  No game data
is included in this archive.

Games
-----
{games}
Files (SHA-256)
---------------
{sums}"""


def embedded(programs, dirs):
    """Bytes of game content found in the programs, or None when no game file is present here."""
    windows = set()
    for data in programs:
        windows.update(data[i:i + BLOCK] for i in range(len(data) - BLOCK + 1))
    files = [f for d in dirs if d.exists() for f in ([d] if d.is_file() else sorted(d.rglob("*"))) if f.is_file()]
    if not files:
        return None
    found, seen = {}, set()
    for f in files:
        data = f.read_bytes()
        digest = hashlib.sha256(data).digest()
        if digest in seen:  # the same file under another name (an unpacked copy, say) counts once
            continue
        seen.add(digest)
        hits = [i for i in range(0, len(data) - BLOCK + 1, BLOCK)
                if len(set(data[i:i + BLOCK])) >= 8 and data[i:i + BLOCK] in windows]
        if hits:
            found[f.name] = len(hits) * BLOCK
    return found


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("version")
    ap.add_argument("--no-build", action="store_true", help="pack the programs as they are")
    ap.add_argument("--allow-embedded", action="store_true", help="pack programs that carry game content")
    a = ap.parse_args()

    name = "F030DOS-" + a.version
    out = ROOT / "release" / name
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True,
                            text=True).stdout.strip()
    if subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"], cwd=ROOT, capture_output=True,
                      text=True).stdout.strip():
        commit += " + local changes"

    sums, texts, stop = [], [], []
    for key, title, files, data_dirs, needs, state in GAMES:
        base = ROOT / "games" / key
        if not a.no_build:
            r = subprocess.run(["make", "-C", str(ROOT), key], capture_output=True, text=True)
            if r.returncode:
                sys.stdout.write(r.stdout[-4000:] + r.stderr[-4000:])
                sys.exit("build of %s failed" % key)
        blobs = [(base / f).read_bytes() for f in files]
        if blobs[0][:2] != b"\x60\x1a":
            sys.exit("%s: not a TOS program" % files[0])
        found = embedded(blobs, [base / d for d in data_dirs])
        if found is None:
            check = "Not checked for embedded game content (no game files in this checkout)."
        elif not found:
            check = "No game content found in the program (32-byte blocks of the local game files)."
        else:
            what = ", ".join("%s %d bytes" % kv for kv in sorted(found.items()))
            check = "CARRIES GAME CONTENT: %s." % what
            if not a.allow_embedded:
                stop.append("%s: the program carries game content (%s)" % (key, what))
        for f, data in zip(files, blobs):
            dest = Path(f).name.upper()
            (out / dest).write_bytes(data)
            sums.append("%s  %s" % (hashlib.sha256(data).hexdigest(), dest))
        print("%-12s %s  %s" % (key, "  ".join("%s %d" % (Path(f).name.upper(), len(b)) for f, b in zip(files, blobs)),
                                check))
        texts.append("%s\n  %s\n  State: %s.\n  %s\n  %s\n" % (title, " + ".join(Path(f).name.upper() for f in files),
                                                           state, needs, check))
    if stop:
        shutil.rmtree(out)
        sys.exit("release stopped:\n  " + "\n  ".join(stop) + "\npass --allow-embedded only with the owner's approval")

    text = README.format(version=a.version, underline="=" * len("F030DOS " + a.version), commit=commit,
                         games="\n".join(texts), sums="\n".join(sums) + "\n")
    (out / "README.TXT").write_bytes(text.replace("\n", "\r\n").encode("ascii"))
    archive = out.parent / (name + ".zip")
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for f in sorted(out.iterdir()):
            z.write(f, "%s/%s" % (name, f.name))
    print("%s: %d bytes" % (archive.relative_to(ROOT), archive.stat().st_size))


if __name__ == "__main__":
    main()
