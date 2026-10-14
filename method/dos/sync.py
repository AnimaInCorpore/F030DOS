#!/usr/bin/env python3
"""Sync the shared DOS-oracle harness from this master copy into the projects.

Master:  F030Method/dos/{dosimg.py, run_qemu.py, mbr.asm, gdbstub_probe.py}
Targets: every sibling project directory that carries a copy of dosimg.py in
         work/ or tools/dos/. Directories ending in "-test" are skipped (git
         worktrees used for adversarial merge passes).

    python dos/sync.py                     # check: report ok/DRIFT per copy
    python dos/sync.py --push              # overwrite project copies
    python dos/sync.py --init F030NewGame  # seed a new project (into work/)

Per-game files (build_dos_hdd.py, set_boot_mode.py) are never touched.
Exit status: 0 = all copies identical; 1 = drift found in check mode.
Line endings are normalised before comparing, so a CRLF checkout is not
drift; content is compared exactly.

Discovery is by presence, which means a project that never seeded the harness
has no copy to drift and would otherwise pass by having nothing -- that is how
F030Comanche's missing oracle stayed invisible while METHOD.md was citing its
open terrain question as the case only an oracle can close. Every *registered*
family member without a copy is therefore printed as `absent` after the report.
It is not drift and does not fail the check: a member may legitimately not need
a DOS oracle. It just has to be visible rather than inferred from a gap.

The register is gen_cross_project.py's TARGETS, so the family has one manifest
rather than two that can disagree. Sibling directories that are not in it (the
non-method F030* repos) are neither synced nor reported.
"""
import sys
from pathlib import Path

SHARED = ['dosimg.py', 'run_qemu.py', 'mbr.asm', 'gdbstub_probe.py']
HERE = Path(__file__).resolve().parent        # .../F030Method/dos
ROOT = HERE.parent.parent                     # the workspace holding every repo

sys.path.insert(0, str(HERE.parent))
import gen_cross_project                      # guarded: importing writes nothing

# The registered family, in TARGETS order, minus F030Method's own copy.
FAMILY = [t[1].relative_to(ROOT).parts[0] for t in gen_cross_project.TARGETS
          if ROOT in t[1].parents and t[1].relative_to(ROOT).parts[0]
          != HERE.parent.name]


def content(p):
    """File bytes with line endings normalised to LF.

    A project may check the harness out with CRLF -- TIE sets `*.py text
    eol=crlf` -- so the raw bytes differ from the LF masters even when nobody
    edited anything. Only a real content difference is drift; --push still
    writes the master's exact bytes. Same stance as gen_cross_project.py.
    """
    return p.read_bytes().replace(b'\r\n', b'\n')


# The per-game half.  Never synced -- sync.py writes it once at --init and then
# leaves it alone, because everything in the marked block is a statement about
# one game.  Modelled on F030Underworld2/work/build_dos_hdd.py, the cleanest of
# the five that already exist; read a sibling's before changing the shape.
BUILD_TEMPLATE = '''#!/usr/bin/env python3
r"""Build img/%(stem)s.hdd -- bootable MS-DOS 6.22 disk running the game.

    python %(rel)s/build_dos_hdd.py            # build + bootstrap boot
    python %(rel)s/build_dos_hdd.py --no-boot  # build only

Seeded by F030Method/dos/sync.py --init %(proj)s.  The shared half (dosimg.py,
run_qemu.py, mbr.asm, gdbstub_probe.py) is synced from that master and must not
be edited here; this file is the per-game half and is yours.

Layout rules, boot-record invariants and the five things that make the image
actually boot: dosimg.py's module docstring.  Procedure and gotchas: write them
up in this project's own qemu-boot.md / DOS-ORACLE.md as you hit them.
"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dosimg

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = dosimg.find_project_root(__file__)
WORK = os.path.join(ROOT, 'work', 'img_build')
OUT = os.path.join(ROOT, 'img', '%(stem)s.hdd')

dosimg._verify_mbr(os.path.join(HERE, 'mbr.asm'), os.path.join(WORK, 'mbr.bin'))

# --- per-game block: everything below here is a claim about THIS game --------
#
# GAME_TREE   the extracted, pristine game directory to stage onto the image.
# GUEST_DIR   where it lands in the guest; the game's own .BAT/.CFG may care.
# SIZE_MB     big enough for DOS + the tree, with room for logs written back.
# CONFIG.SYS  what the game needs resident.  Check the binary for `EMMXXXX0`
#             (EMS) and `XMSXXXX0` (XMS) before deciding -- guessing here costs
#             a boot cycle each time.  HIMEM/EMM386 are expanded in-guest by
#             dosimg bootstrap, so they are available.
# AUTOEXEC    expand_autoexec() ends with C:\\QUIT.COM so the guest terminates
#             the run itself (QEMU exit 21).  Put the game's own launcher line
#             in `then=` once booting is proven, not before.
#
GAME_TREE = os.path.join(ROOT, 'assets', 'extracted')   # <-- point at the game
GUEST_DIR = '/GAME'
SIZE_MB = 32

img = dosimg.DosImage(OUT, size_mb=SIZE_MB, work_dir=WORK,
                      label='%(stem)s')
print('game files: %%d' %% img.add_tree(GUEST_DIR, GAME_TREE))
img.add_bytes(b'FILES=30\\r\\nBUFFERS=20\\r\\n', '/CONFIG.SYS')
img.add_bytes(dosimg.expand_autoexec(), '/AUTOEXEC.BAT')
# --- end per-game block ------------------------------------------------------

img.write()

if '--no-boot' not in sys.argv:
    print('\\n--- bootstrap boot (in-guest EXPAND) ---')
    rc = subprocess.call([sys.executable, os.path.join(HERE, 'run_qemu.py'),
                          '--timeout', '120', '--cat', '::/BOOT.LOG'])
    if rc != 0:
        sys.exit('bootstrap boot failed -- see output above')
'''


def siblings():
    """Registered family project directories that exist, in manifest order.

    Directories ending in "-test" are skipped (git worktrees used for
    adversarial merge passes)."""
    return [ROOT / n for n in FAMILY
            if (ROOT / n).is_dir() and not n.endswith('-test')]


def harness_dir(proj):
    """Where this project keeps the shared harness, or None if it has none."""
    for sub in ('work', 'tools/dos'):
        d = proj.joinpath(*sub.split('/'))
        if (d / 'dosimg.py').is_file():
            return d
    return None


def targets():
    return [d for d in map(harness_dir, siblings()) if d is not None]


def main(argv):
    if argv and argv[0] == '--init':
        if len(argv) != 2:
            sys.exit('usage: sync.py --init <Project>[/work|/tools/dos]')
        dest = ROOT / argv[1].replace('\\', '/')
        if dest.name not in ('work', 'dos'):
            dest = dest / 'work'
        dest.mkdir(parents=True, exist_ok=True)
        for f in SHARED:
            (dest / f).write_bytes((HERE / f).read_bytes())
            print('seeded  %s' % (dest / f))
        # --init used to stop here and leave a note telling the newcomer to
        # copy a sibling's per-game half by hand.  That handoff is where
        # seeding stalled, so write a working skeleton instead.
        build = dest / 'build_dos_hdd.py'
        if build.exists():
            print('kept    %s (already written)' % build)
        else:
            stem = dest.parent.name.replace('F030', '').lower() or 'game'
            build.write_text(BUILD_TEMPLATE % {
                'proj': dest.parent.name,
                'rel': '%s/%s' % (dest.parent.name, dest.name),
                'stem': stem,
            }, encoding='utf-8')
            print('seeded  %s  <-- per-game half: edit the marked block'
                  % build)
        (dest.parent / 'img').mkdir(exist_ok=True)
        print('next: point GAME_TREE at the extracted game, then run it.')
        return 0

    push = '--push' in argv
    drift = 0
    for d in targets():
        for f in SHARED:
            t, m = d / f, HERE / f
            if t.is_file() and content(t) == content(m):
                print('  ok     %s' % t)
            elif push:
                t.write_bytes(m.read_bytes())
                print('  PUSHED %s' % t)
            else:
                drift += 1
                print('  DRIFT  %s' % t)
    # Projects with no harness at all: reported, never counted as drift.
    for proj in siblings():
        if harness_dir(proj) is None:
            print('  absent %s  (no harness seeded; --init %s to add one)'
                  % (proj, proj.name))

    if drift:
        print('%d cop%s differ from the master. Diff before acting: a project-'
              'local fix belongs in the master first; then --push.'
              % (drift, 'y' if drift == 1 else 'ies'))
        return 1
    print('all seeded copies identical to the master')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
