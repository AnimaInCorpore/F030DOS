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
import re
import hashlib
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLOCK = 32
DIRS = {"comanche060": "comanche"}
# Programs under GPL-3.0-or-later (the port's COPYING), and those of them that link F030OPL2: the archive then
# carries the licence and names the sources.
GPL = {"comanche", "comanche060"}
LINKS_OPL2 = {"comanche060"}
# A game's player guide (Markdown in games/<dir>/), packed once as plain text.
GUIDES = {"comanche": ("docs/PLAYING.md", "COMANCHE.TXT")}


def plain(md):
    """Markdown to the README.TXT style: no backticks, emphasis or link targets."""
    md = re.sub(r"\[([^]]+)\]\([^)]+\)", r"\1", md)
    md = re.sub(r"\*\*([^*]+)\*\*|\*([^*]+)\*", lambda m: m.group(1) or m.group(2), md)
    md = md.replace("`", "")
    md = re.sub(r"(?m)^(#+) (.*)$", lambda m: m.group(2) + "\n" + ("=" if len(m.group(1)) == 1 else "-") * len(m.group(2)), md)
    return md
OPL2 = ROOT.parent / "F030OPL2"

# key, title, files (relative to games/<dir>/; the first is the program; a (path, NAME) pair renames it in the
# archive), game file directories for the embedded-content check, what the player has to supply, state.  The key is
# the make target; DIRS maps a key to its games/ directory when the two differ.  Keep the states in step with games/<key>/README.md and the
# root README's table.  Ports without a Falcon program (or with only a test harness) are not listed.
GAMES = [
    ("comanche", "Comanche: Maximum Overkill (1992)",
     ["release/comanche.tos"], ["assets/extracted/comanche_hdd", "re/unpacked"],
     "Copy the files of your installed DOS game (the COMANCHE directory) next to COMANCHE.TOS. The program reads its "
     "tables from COMANCHE.EXE (the 1990 version, 61,154 bytes) and the terrain, palettes, sprites, skies, demo "
     "flights, sound banks and missions from the other files. COMANCHE.MNU selects the "
     "detail level as in DOS: the shipped file says MEDIUM; the development builds stage a copy set to HIGH.  "
     "COMANCHE.TXT is the guide: installation, setup and the keys.",
     "the attract cycle, menus, briefing, live flight, combat and debrief on the CPU renderer; all 20 mission starts "
     "equal the original's; this 68030 program plays the sound effects, not the music (that is COMAN060.TOS); not "
     "certified against the DOS original, the DSP renderer is dormant, never run on a real Falcon"),
    ("comanche060", "Comanche: Maximum Overkill (1992), 68060 image with music",
     [("release/68060/comanche.tos", "COMAN060.TOS"), "release/68060/OPLDATA.BIN"],
     ["assets/extracted/comanche_hdd", "re/unpacked"],
     "For a Falcon with a CT60/CT63 (68060) and TT-RAM; it does not run on a 68030.  Copy COMAN060.TOS and "
     "OPLDATA.BIN (the DSP synthesiser's tables) into the COMANCHE directory as above.  The music is played by "
     "F030OPL2's OPL2 emulation on the DSP: COMANCHE.CFG must select the AdLib (its third character 3, for example "
     "0132700000), and nothing else may use the DSP.  This program is GPL-3.0-or-later, see Licences",
     "the same game as COMANCHE.TOS, built for the 68060 (loaded into TT-RAM) with the music; in Hatari's 68060 "
     "model about 20 frames a second and the music in time, never run on a real Falcon"),
    ("f29", "F29 Retaliator (1990)",
     ["release/f29.tos", "release/3d.lod"], ["assets"],
     "Keep F29.TOS and 3D.LOD (the DSP program) together.  The scenery comes from SCENE.F29 next to them, built from "
     "your own copy with the tools in games/f29 (tools/re/unpack.py, decompress.py, then scene2f29.py; see "
     "docs/ENGINE.md); without it the program falls back to a single-model view (MODEL.O3D).",
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

Requirements: a Falcon030 with 14 MB of RAM (COMAN060.TOS: a CT60/CT63 68060 with TT-RAM), an RGB or VGA monitor,
and your own copy of each game.  No game data is included in this archive.

Installation: give each game its own folder on the Falcon's hard disk or CompactFlash card (8.3 names, for example
C:\\COMANCHE), put its program there with the files of your copy as listed below, and start the .TOS program from the
desktop.  Do not run accessories that use the DSP at the same time.  Tested in Hatari with TOS 4.02/4.04 and EmuTOS.

Games
-----
{games}
Licences
--------
{licences}
Files (SHA-256)
---------------
{sums}"""


def ramp(b):
    """A counting sequence (00 01 02 .., an identity table) is in many programs and says nothing (F030SNES: a byte
    ramp in Super Mario Kart's runtime matched the ROM)."""
    return len({(b[i + 1] - b[i]) & 0xFF for i in range(len(b) - 1)}) == 1


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
                if len(set(data[i:i + BLOCK])) >= 8 and not ramp(data[i:i + BLOCK]) and data[i:i + BLOCK] in windows]
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
    gpl_names, opl2 = [], None
    for key, title, files, data_dirs, needs, state in GAMES:
        base = ROOT / "games" / DIRS.get(key, key)
        names = [f[1] if isinstance(f, tuple) else Path(f).name.upper() for f in files]
        files = [f[0] if isinstance(f, tuple) else f for f in files]
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
        for dest, data in zip(names, blobs):
            (out / dest).write_bytes(data)
            sums.append("%s  %s" % (hashlib.sha256(data).hexdigest(), dest))
        print("%-12s %s  %s" % (key, "  ".join("%s %d" % (n, len(b)) for n, b in zip(names, blobs)), check))
        texts.append("%s\n  %s\n  State: %s.\n  %s.\n  %s\n" % (title, " + ".join(names), state, needs.rstrip("."),
                                                            check))
        if key in GUIDES:
            src, dest = GUIDES[key]
            text = plain((base / src).read_text(encoding="utf-8"))
            (out / dest).write_bytes(text.replace("\n", "\r\n").encode("ascii"))
            if key in GPL:
                gpl_names.append(dest)
            sums.append("%s  %s" % (hashlib.sha256((out / dest).read_bytes()).hexdigest(), dest))
        if key in GPL:
            gpl_names += names
            copying = (ROOT / "games" / DIRS.get(key, key) / "COPYING").read_bytes()
            (out / "COPYING.TXT").write_bytes(copying.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
        if key in LINKS_OPL2:
            opl2 = subprocess.run(["git", "describe", "--always", "--abbrev=12", "--dirty", "--exclude", "*"],
                                  cwd=OPL2, capture_output=True, text=True).stdout.strip()
            if not opl2 or opl2.endswith("-dirty"):
                sys.exit("%s: F030OPL2 at %s must be a clean checkout (%s)" % (key, OPL2, opl2 or "not found"))
    licences = []
    if gpl_names:
        licences.append(
            "%s: free software under the GNU General Public License, version 3 or (at your option)\n"
            "any later version, with no warranty; COPYING.TXT is the licence.  The source is public:\n"
            "  games/comanche of https://github.com/AnimaInCorpore/F030DOS  (commit %s)\n" % (", ".join(gpl_names), commit)
            + ("  https://github.com/AnimaInCorpore/F030OPL2  (commit %s), linked into COMAN060.TOS and the source of\n"
               "  OPLDATA.BIN; its OPL2 kernels derive from ScummVM's\n" % opl2 if opl2 else "")
            + "The licence covers the port, not Comanche itself: no NovaLogic program or data is in these files.")
    licences.append("The other programs: no licence has been chosen yet; all rights reserved.")
    if stop:
        shutil.rmtree(out)
        sys.exit("release stopped:\n  " + "\n  ".join(stop) + "\npass --allow-embedded only with the owner's approval")

    text = README.format(version=a.version, underline="=" * len("F030DOS " + a.version), commit=commit,
                         games="\n".join(texts), licences="\n\n".join(licences) + "\n", sums="\n".join(sums) + "\n")
    (out / "README.TXT").write_bytes(text.replace("\n", "\r\n").encode("ascii"))
    archive = out.parent / (name + ".zip")
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for f in sorted(out.iterdir()):
            z.write(f, "%s/%s" % (name, f.name))
    print("%s: %d bytes" % (archive.relative_to(ROOT), archive.stat().st_size))


if __name__ == "__main__":
    main()
