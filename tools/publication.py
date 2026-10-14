#!/usr/bin/env python3
"""Import, sync and check the publication copy of the F030 DOS ports.

The development homes are the sibling repositories (../F030Comanche, ../F030POR, ...); this repository holds a
screened copy of their committed sources under games/<game>/ (and F030Method's shared layer under method/).  Only
committed content is read, never a private working tree.  docs/publication-inventory.json records a decision for
every path of every imported commit:

    candidate    copied here; source, tool or documentation whose ownership and license review is pending
    local-only   game input, capture, generated output or binary; stays in the private repository
    exclude      text that looks like the game itself (disassembly, decompiler output, data tables) or vendor content

    python3 tools/publication.py init <game>|--all          first import of a source's HEAD
    python3 tools/publication.py sync <game>|--all [--apply] [--accept PATH] [--to REV]
    python3 tools/publication.py stage                      index exactly the candidates and the owned files
    python3 tools/publication.py status                     imported commit vs. each source's HEAD
    python3 tools/publication.py check [--history] [--ready]
    python3 tools/publication.py import-local <game>        restore local-only files from the private checkout

The checks are engineering controls, not a determination of distribution rights.  Standard library and Git only.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "docs/publication-inventory.json"

# key -> (sibling repository, publication directory).  The order is the order of the README's game table.
SOURCES = {
    "comanche": ("F030Comanche", "games/comanche"),
    "f29": ("F030F29", "games/f29"),
    "por": ("F030POR", "games/por"),
    "uw2": ("F030Underworld2", "games/uw2"),
    "pg": ("F030PanzerGeneral", "games/pg"),
    "uw": ("F030Underworld", "games/uw"),
    "tie": ("F030TieFighter", "games/tie"),
    "falcon3": ("F030Falcon3", "games/falcon3"),
    "links386": ("F030Links386", "games/links386"),
    "lol": ("F030LOL", "games/lol"),
    "magiccarpet": ("F030MagicCarpet", "games/magiccarpet"),
    "icr": ("F030ICR", "games/icr"),
    "method": ("F030Method", "method"),
}

TEXT_EXTENSIONS = {
    ".md", ".txt", ".s", ".i", ".inc", ".asm", ".a56", ".c", ".h", ".cpp", ".hpp", ".py", ".js", ".mjs", ".cjs", ".ts",
    ".html", ".css", ".json", ".sh", ".ps1", ".bat", ".cmd", ".mk", ".ld", ".patch", ".yml", ".yaml", ".toml", ".cfg",
    ".conf", ".csv",
}
TEXT_NAMES = {"Makefile", ".gitignore", ".gitattributes", ".gitkeep", "LICENSE", "NOTICE"}

# Directory names (anywhere in a source path) whose content is the game, a capture of it or generated from it.
LOCAL_PARTS = {
    "game": "game media or its extraction",
    "assets": "supplied game media",
    "img": "disk images and DOS installation media",
    "captures": "recorded capture of the original",
    "fixtures": "fixture recorded from the original",
    "ghidra": "Ghidra project database",
    "ghidra_export": "decompiler/disassembler export of the game program",
    "out": "generated reassembly output",
    "expanded": "extracted game data",
    "extracted": "extracted game data",
    "unpacked": "extracted game data",
    "listings": "generated listings of the game program",
    "resources": "extracted game resources",
    "toolchain": "vendor binaries",
    "build": "build output",
    "release": "build output",
    "obj": "build output",
    ".pi": "agent tool scratch",
    ".vscode": "editor settings",
    ".claude": "agent settings",
}
# Top-level directories (first path part only) that stay local.
LOCAL_TOP = {"reference": "copy of another repository's files"}
# Vendored third-party trees: their own licenses, not ours to relicense; recorded as excluded.
VENDOR_PARTS = {"dos32a": "vendored DOS/32A extender source (own license)",
                "zrdx": "vendored ZRDX extender source (own license)"}
# File-name patterns (matched against the base name) for content recovered from or recorded off the original.
NAME_RULES = [
    (re.compile(r"(?i)strings?(?:_decoded)?\.txt$"), "exclude", "string dump extracted from the game program"),
    (re.compile(r"(?i)trace[\w-]*\.json$"), "local-only", "recorded trace of the original"),
]
# Files the publication copy owns itself (not imported from a source).
OWNED_TOP = {"README.md", "AGENTS.md", "Makefile", ".gitignore", ".gitattributes", "LICENSE", "NOTICE", "tools", "docs"}

X86_REG = r"\b(?:e?[abcd]x|[abcd][lh]|e?[sd]i|e?[sb]p|[cdefgs]s)\b"
X86_LINE = re.compile(r"(?im)^[^\n;#]*?\b(?:mov|movzx|movsx|push|pop|call|jmp|j[a-z]{1,3}|cmp|test|lea|xor|or|and|add|adc|sub|"
                      r"sbb|inc|dec|shl|shr|sar|imul|mul|idiv|div|les|lds|xchg|neg|not|rcl|rcr|rol|ror)\s+[^\n]*" + X86_REG)
DECOMPILED = re.compile(r"\b(?:FUN_[0-9a-fA-F]{4,}|DAT_[0-9a-fA-F]{4,}|undefined[1248]?|LAB_[0-9a-fA-F]{4,})\b")
DATA_LINE = re.compile(r"(?im)^\s*(?:[\w.$]+:?\s+)?(?:d[bwd]|dc\.[bwl])\s+(?:\$|0x)?[0-9a-f]+h?(?:\s*,\s*(?:\$|0x)?[0-9a-f]+h?){7,}")
NUMERIC_RUN = re.compile(r"(?:-?(?:0x[0-9a-fA-F]+|\d+)\s*,\s*){512,}")
MAX_TEXT = 4 << 20


def git(*args, cwd=ROOT, **kw):
    return subprocess.check_output(["git", *args], cwd=cwd, **kw)


def source_dir(key):
    return ROOT.parent / SOURCES[key][0]


def inventory():
    if INVENTORY.exists():
        return json.loads(INVENTORY.read_text(encoding="utf-8"))
    return {"license": "undecided", "status": "private-review-candidate", "sources": {}, "files": []}


def write_inventory(manifest):
    manifest["files"].sort(key=lambda r: r["path"])
    INVENTORY.write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def content_errors(path, data):
    """Reasons a text blob may not be published, or [] (mechanical screening only)."""
    if b"\0" in data:
        return ["binary content"]
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = data.decode("latin-1")
        except UnicodeDecodeError:
            return ["undecodable content"]
        if sum(c < 9 or 13 < c < 32 for c in data) > 16:
            return ["binary content"]
    errors = []
    if len(data) > MAX_TEXT:
        errors.append("oversized text (%d bytes), generated output needs review" % len(data))
    if text.startswith("version https://git-lfs.github.com/spec/v1"):
        errors.append("LFS pointer; payload was not audited")
    if PurePosixPath(path).suffix.lower() == ".txt" and re.search(r"(?m)^[0-9a-fA-F]{4,8}: (?:[0-9a-fA-F]{2} ){8,}", text):
        errors.append("raw hexadecimal dump")
    if len(X86_LINE.findall(text)) > 400:
        errors.append("x86 disassembly of the game program")
    if len(DECOMPILED.findall(text)) > 200:
        errors.append("decompiler output of the game program")
    if len(DATA_LINE.findall(text)) > 64:
        errors.append("long literal data table needs review")
    if NUMERIC_RUN.search(text):
        errors.append("long numeric array (possibly captured game data)")
    if re.search(r"(?:[0-9a-fA-F]{2}){128,}", text):
        errors.append("long hexadecimal payload needs review")
    if re.search(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|gh[pousr]_[A-Za-z0-9]{30,}|AKIA[0-9A-Z]{16}", text):
        errors.append("potential credential")
    return errors


def location_reason(path):
    """Why a source path (relative to its repository) stays local regardless of content, or None."""
    p = PurePosixPath(path)
    if len(p.parts) > 1 and p.parts[0] in LOCAL_TOP:
        return LOCAL_TOP[p.parts[0]]
    for part in p.parts[:-1]:
        if part in LOCAL_PARTS:
            return LOCAL_PARTS[part]
    if p.suffix.lower() not in TEXT_EXTENSIONS and p.name not in TEXT_NAMES:
        return "not an approved source/documentation format"
    return None


def classify(path, data, pub=None, reviewed=None):
    for part in PurePosixPath(path).parts[:-1]:
        if part in VENDOR_PARTS:
            return "exclude", VENDOR_PARTS[part]
    reason = location_reason(path)
    if reason:
        return "local-only", reason
    for pattern, decision, why in NAME_RULES:
        if pattern.search(PurePosixPath(path).name):
            return decision, why
    errors = content_errors(path, data)
    if errors == ["binary content"]:
        return "local-only", "binary content"
    review = (reviewed or {}).get(pub)
    if errors and review and review["sha256"] == hashlib.sha256(data).hexdigest():
        return "candidate", "accepted after review: " + review["note"]
    if errors:
        return "exclude", "; ".join(errors)
    return "candidate", "source/tool/documentation candidate; ownership and license review pending"


def tree(cwd, rev):
    """{path: (mode, oid)} of the blobs in a commit; gitlinks and symlinks are reported as their own modes."""
    result = {}
    for entry in git("ls-tree", "-r", "-z", rev, cwd=cwd).split(b"\0"):
        if entry:
            meta, path = entry.split(b"\t", 1)
            mode, kind, oid = meta.decode().split()
            result[path.decode()] = (mode, oid)
    return result


def read_blobs(cwd, oids):
    """Read many blobs through one `git cat-file --batch`."""
    unique = sorted(set(oids))
    if not unique:
        return {}
    output = subprocess.check_output(["git", "cat-file", "--batch"], cwd=cwd, input=("\n".join(unique) + "\n").encode())
    result, pos = {}, 0
    for expected in unique:
        end = output.index(b"\n", pos)
        oid, kind, size = output[pos:end].decode().split()
        if oid != expected or kind != "blob":
            raise SystemExit("unexpected object %s (%s)" % (expected, kind))
        pos = end + 1
        result[oid] = output[pos:pos + int(size)]
        pos += int(size) + 1
    return result


def record(pub_path, mode, oid, data, decision, reason):
    r = {"path": pub_path, "decision": decision, "reason": reason, "git_mode": mode, "git_object": oid}
    if data is not None:
        r.update({"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    return r


def keys_of(args):
    if args.all:
        return list(SOURCES)
    if not args.game:
        raise SystemExit("name a game (%s) or pass --all" % ", ".join(SOURCES))
    for g in args.game:
        if g not in SOURCES:
            raise SystemExit("unknown game %s (%s)" % (g, ", ".join(SOURCES)))
    return args.game


def write_file(target, data, mode):
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    if mode == "100755":
        target.chmod(target.stat().st_mode | 0o111)


def init(keys, rev="HEAD"):
    manifest = inventory()
    for key in keys:
        repo, prefix = SOURCES[key]
        if key in manifest["sources"]:
            print("%s: already imported at %s; use sync" % (key, manifest["sources"][key]["source_commit"][:12]))
            continue
        src = source_dir(key)
        commit = git("rev-parse", "--verify", rev + "^{commit}", cwd=src).decode().strip()
        files = tree(src, commit)
        blobs = read_blobs(src, [oid for mode, oid in files.values() if mode in ("100644", "100755")])
        counts = {}
        for path, (mode, oid) in sorted(files.items()):
            pub = "%s/%s" % (prefix, path)
            if mode not in ("100644", "100755"):
                r = record(pub, mode, oid, None, "local-only", "symlink or submodule; not imported")
            else:
                data = blobs[oid]
                decision, reason = classify(path, data, pub, manifest.get("reviewed"))
                r = record(pub, mode, oid, data, decision, reason)
                if decision == "candidate":
                    write_file(ROOT / pub, data, mode)
            counts[r["decision"]] = counts.get(r["decision"], 0) + 1
            manifest["files"].append(r)
        origin = subprocess.run(["git", "remote", "get-url", "origin"], cwd=src, capture_output=True, text=True).stdout.strip()
        manifest["sources"][key] = {"repository": repo, "origin": origin, "directory": prefix, "source_commit": commit}
        print("%-12s %s %s  %s" % (key, repo, commit[:12], "  ".join("%s %d" % kv for kv in sorted(counts.items()))))
    write_inventory(manifest)
    return 0


def sync(keys, to="HEAD", apply=False):
    """Carry committed source changes into the candidate (dry run unless apply).

    Candidate files left untouched here are replaced; files edited here are three-way merged; local-only/excluded
    records get new hashes so import-local keeps working.  A new or changed path whose screening fails is recorded
    as excluded and reported; a new path that passes is copied.  A review recorded with `accept` holds only for the
    content it was made for.  Nothing is staged; run check afterwards.
    """
    manifest = inventory()
    records = {r["path"]: r for r in manifest["files"]}
    reviewed = manifest.get("reviewed", {})
    status = 0
    for key in keys:
        repo, prefix = SOURCES[key]
        meta = manifest["sources"].get(key)
        if not meta:
            print("%s: not imported; use init" % key)
            continue
        src = source_dir(key)
        since = meta["source_commit"]
        target_commit = git("rev-parse", "--verify", to + "^{commit}", cwd=src).decode().strip()
        if since == target_commit:
            print("%-12s up to date at %s" % (key, since[:12]))
            continue
        old, new = tree(src, since), tree(src, target_commit)
        changed = sorted(p for p in set(old) | set(new) if old.get(p) != new.get(p))
        blobs = read_blobs(src, [new[p][1] for p in changed if p in new and new[p][0] in ("100644", "100755")] +
                           [old[p][1] for p in changed if p in old and old[p][0] in ("100644", "100755")])
        plan = []
        for path in changed:
            pub = "%s/%s" % (prefix, path)
            prev = records.get(pub)
            if path not in new:
                plan.append(("delete" if prev and prev["decision"] == "candidate" else "forget", pub, None, None))
                continue
            mode, oid = new[path]
            if mode not in ("100644", "100755"):
                plan.append(("record", pub, record(pub, mode, oid, None, "local-only", "symlink or submodule; not imported"), None))
                continue
            data = blobs[oid]
            decision, reason = classify(path, data, pub, reviewed)
            r = record(pub, mode, oid, data, decision, reason)
            if decision != "candidate":
                was = prev and prev["decision"] == "candidate"
                plan.append(("withdraw" if was else "record", pub, r, None))
                continue
            target = ROOT / pub
            ours = target.read_bytes() if target.is_file() else None
            base = blobs.get(old[path][1]) if path in old else None
            action = "copy" if ours is None or ours == base or ours == data else "merge"
            plan.append((action, pub, r, base))
        print("%-12s %s..%s" % (key, since[:12], target_commit[:12]))
        for action, pub, r, _ in plan:
            if action != "record" and action != "forget":
                print("  %-8s %s" % (action, pub))
            elif r and r["decision"] == "exclude":
                print("  %-8s %s (%s)" % ("exclude", pub, r["reason"]))
        if not apply:
            continue
        for action, pub, r, base in plan:
            target = ROOT / pub
            if action in ("delete", "withdraw"):
                target.unlink(missing_ok=True)
            if action == "copy":
                write_file(target, read_blobs(src, [r["git_object"]])[r["git_object"]], r["git_mode"])
            elif action == "merge":
                with tempfile.TemporaryDirectory() as tmp:
                    b, t = Path(tmp, "base"), Path(tmp, "theirs")
                    b.write_bytes(base or b"")
                    t.write_bytes(read_blobs(src, [r["git_object"]])[r["git_object"]])
                    rc = subprocess.run(["git", "merge-file", "-L", "publication", "-L", since[:12], "-L",
                                         target_commit[:12], str(target), str(b), str(t)], cwd=ROOT).returncode
                if rc:
                    print("CONFLICT %s: resolve the markers" % pub, file=sys.stderr)
                    status = 1
            if action in ("delete", "forget"):
                records.pop(pub, None)
            elif r:
                records[pub] = r
        meta["source_commit"] = target_commit
    if apply:
        manifest["files"] = list(records.values())
        write_inventory(manifest)
        print("Nothing staged. Run check before committing.")
    else:
        print("Dry run; pass --apply to write.")
    return status


def accept(pub, note):
    """Record a review of an excluded path and copy it in.  Location rules (game media, vendor trees) cannot be
    overridden; only a failed content screen can."""
    manifest = inventory()
    r = next((r for r in manifest["files"] if r["path"] == pub), None)
    if not r or r["decision"] != "exclude" or r["reason"] in VENDOR_PARTS.values():
        raise SystemExit("%s: not an excluded path whose content screen can be reviewed" % pub)
    key = next(k for k, (_, d) in SOURCES.items() if pub.startswith(d + "/"))
    data = read_blobs(source_dir(key), [r["git_object"]])[r["git_object"]]
    manifest.setdefault("reviewed", {})[pub] = {"sha256": r["sha256"], "screen": r["reason"], "note": note}
    r["decision"], r["reason"] = "candidate", "accepted after review: " + note
    write_file(ROOT / pub, data, r["git_mode"])
    write_inventory(manifest)
    print("accepted %s; stage it and run check" % pub)
    return 0


def stage():
    """Index every candidate and every file this copy owns; drop withdrawn paths from the index."""
    manifest = inventory()
    candidates = sorted(r["path"] for r in manifest["files"] if r["decision"] == "candidate")
    tracked = git("ls-files", "-z").decode().split("\0")
    keep = set(candidates)
    stale = [t for t in tracked if t and not owned(t) and t not in keep]
    for i in range(0, len(stale), 500):
        git("rm", "--cached", "-q", "--", *stale[i:i + 500])
    for i in range(0, len(candidates), 500):
        git("add", "-f", "--", *candidates[i:i + 500])
    git("add", "-A", "--", *sorted(t for t in OWNED_TOP if (ROOT / t).exists()))
    print("staged %d candidates; %d withdrawn paths removed from the index" % (len(candidates), len(stale)))
    return 0


def show_status():
    manifest = inventory()
    for key, (repo, prefix) in SOURCES.items():
        meta = manifest["sources"].get(key)
        if not meta:
            print("%-12s not imported" % key)
            continue
        src = source_dir(key)
        head = git("rev-parse", "HEAD", cwd=src).decode().strip()
        behind = int(git("rev-list", "--count", "%s..%s" % (meta["source_commit"], head), cwd=src).decode())
        n = sum(1 for r in manifest["files"] if r["path"].startswith(prefix + "/") and r["decision"] == "candidate")
        print("%-12s %-18s %s  %4d files  %s" % (key, repo, meta["source_commit"][:12], n,
                                                 "current" if not behind else "%d commits behind" % behind))
    return 0


def owned(path):
    """True for files the publication copy owns (outside the imported directories)."""
    return not any(path == d or path.startswith(d + "/") for _, d in SOURCES.values()) and path.split("/")[0] in OWNED_TOP


def check(ready=False, history=False):
    manifest = inventory()
    records = {r["path"]: r for r in manifest["files"]}
    # A local-only payload under another name is caught here, unless the same bytes are a candidate in their own
    # right (Comanche's reference/ copies F29's documents, which F29 publishes).
    banned = ({r["sha256"] for r in manifest["files"] if r["decision"] != "candidate" and r.get("bytes", 0) > 64} -
              {r.get("sha256") for r in manifest["files"] if r["decision"] == "candidate"})
    errors = []
    entries = []
    for entry in git("ls-files", "--stage", "-z").split(b"\0"):
        if entry:
            meta, path = entry.split(b"\t", 1)
            mode, oid, stage = meta.decode().split()
            entries.append((path.decode(), mode, oid, stage))
    if not entries:
        errors.append("no staged/tracked files to check; stage the candidate first")
    blobs = read_blobs(ROOT, [oid for _, mode, oid, _ in entries if mode in ("100644", "100755")])

    def screen(path, mode, oid, where=""):
        if mode not in ("100644", "100755"):
            return ["%s%s: symlink, submodule or unmerged entry" % (where, path)]
        data = blobs[oid] if oid in blobs else git("cat-file", "blob", oid)
        found = []
        r = records.get(path)
        if not owned(path):
            if not r or r["decision"] != "candidate":
                found.append("%s%s: not a candidate in the inventory (%s)" % (where, path, r["reason"] if r else "unknown"))
            elif r.get("git_object") != oid and not where:
                pass  # edited in the publication copy; screened below like any other content
        elif PurePosixPath(path).suffix.lower() not in TEXT_EXTENSIONS and PurePosixPath(path).name not in TEXT_NAMES:
            found.append("%s%s: unapproved file format" % (where, path))
        if hashlib.sha256(data).hexdigest() in banned:
            found.append("%s%s: payload matches a local-only/excluded file" % (where, path))
        review = manifest.get("reviewed", {}).get(path)
        accepted = review and review["sha256"] == hashlib.sha256(data).hexdigest()
        if not accepted:
            found.extend("%s%s: %s" % (where, path, e) for e in content_errors(path, data))
        return found

    for path, mode, oid, stage in entries:
        if stage != "0":
            errors.append("%s: unmerged" % path)
            continue
        errors.extend(screen(path, mode, oid))
    if history:
        seen = set()
        for commit in git("rev-list", "--all").decode().split():
            for path, (mode, oid) in tree(ROOT, commit).items():
                if (path, oid) not in seen:
                    seen.add((path, oid))
                    errors.extend(screen(path, mode, oid, "history %s " % commit[:12]))
    if ready and manifest.get("status") != "approved-for-publication":
        errors.append("publication blocked: provenance, rights and packaging review is incomplete (docs/PUBLICATION.md)")
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print("PASS: %d indexed files meet the mechanical checks. Rights review is separate." % len(entries))
    return 0


def import_local(key):
    """Copy a game's local-only files from the private checkout into ignored paths here, hash-verified."""
    manifest = inventory()
    meta = manifest["sources"].get(key)
    if not meta:
        raise SystemExit("%s is not imported" % key)
    src, prefix = source_dir(key), SOURCES[key][1]
    todo, skipped = [], []
    for r in manifest["files"]:
        if not r["path"].startswith(prefix + "/") or r["decision"] == "candidate" or "sha256" not in r:
            continue
        rel = r["path"][len(prefix) + 1:]
        s, d = src / rel, ROOT / r["path"]
        if not s.is_file() or hashlib.sha256(s.read_bytes()).hexdigest() != r["sha256"]:
            skipped.append("%s: missing or changed in %s" % (rel, src.name))
            continue
        if subprocess.run(["git", "check-ignore", "-q", "--", r["path"]], cwd=ROOT).returncode:
            skipped.append("%s: not ignored here, so it is not copied" % r["path"])
            continue
        if d.exists():
            if hashlib.sha256(d.read_bytes()).hexdigest() != r["sha256"]:
                skipped.append("%s: a different local file is in the way" % r["path"])
            continue
        todo.append((s, d, r["git_mode"]))
    for s, d, mode in todo:
        write_file(d, s.read_bytes(), mode)
    for line in skipped:
        print("skipped " + line)
    print("Restored %d local-only files for %s; Git tracking is unchanged." % (len(todo), key))
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command", required=True)
    for name in ("init", "sync"):
        p = sub.add_parser(name)
        p.add_argument("game", nargs="*")
        p.add_argument("--all", action="store_true")
        p.add_argument("--to", default="HEAD", help="source revision to import (default HEAD)")
        if name == "sync":
            p.add_argument("--apply", action="store_true")
    acc = sub.add_parser("accept", help="publish an excluded path after reviewing it; bound to its current content")
    acc.add_argument("path")
    acc.add_argument("note", help="the evidence that it is not game content")
    sub.add_parser("status")
    sub.add_parser("stage")
    c = sub.add_parser("check")
    c.add_argument("--ready", action="store_true")
    c.add_argument("--history", action="store_true")
    i = sub.add_parser("import-local")
    i.add_argument("game")
    a = ap.parse_args()
    if a.command == "init":
        return init(keys_of(a), a.to)
    if a.command == "sync":
        return sync(keys_of(a), a.to, a.apply)
    if a.command == "accept":
        return accept(a.path, a.note)
    if a.command == "status":
        return show_status()
    if a.command == "stage":
        return stage()
    if a.command == "check":
        return check(a.ready, a.history)
    return import_local(a.game)


if __name__ == "__main__":
    sys.exit(main())
