# UWExport.py — export UW.EXE (16-bit) analysis: function table, full disasm, C
# Run: analyzeHeadless ... -process UW.EXE -postScript UWExport.py
# Outputs to C:/Arbeit/F030Underworld/work/ghidra_export/

import os

from ghidra.app.decompiler import DecompInterface
from ghidra.program.model.address import Address

OUTDIR = r"C:\Arbeit\F030Underworld\work\ghidra_export"
os.makedirs(OUTDIR, exist_ok=True)

fm = currentProgram.getFunctionManager()
listing = currentProgram.getListing()
mem = currentProgram.getMemory()

# ---- 1. memory layout ----
with open(os.path.join(OUTDIR, "memory_layout.txt"), "w") as f:
    for blk in mem.getBlocks():
        f.write("%s  %s .. %s  (%d bytes, %s)\n" % (
            blk.getName(), blk.getStart(), blk.getEnd(),
            blk.getSize(), ", ".join(
                name for name, on in [
                    ("r", blk.isReadable()), ("w", blk.isWritable()),
                    ("x", blk.isExecutable())] if on)))

# ---- 2. function table (start, size, name, in-refs) ----
funcs = []
it = fm.getFunctions(True)
while it.hasNext():
    fn = it.next()
    funcs.append(fn)
funcs.sort(key=lambda f: f.getEntry())

with open(os.path.join(OUTDIR, "functions.txt"), "w") as f:
    for fn in funcs:
        body = fn.getBodyAsSet()
        nins = body.numAddresses()
        inrefs = len(fm.getFunctionReferencesTo(fn))
        f.write("%s  size=%d  inrefs=%d  %s%s\n" % (
            fn.getEntry(), nins, inrefs,
            "EXT " if fn.isExternal() else "", fn.getName()))
print("functions: %d" % len(funcs))

# ---- 3. full plain disassembly ----
with open(os.path.join(OUTDIR, "disasm.txt"), "w") as f:
    for blk in mem.getBlocks():
        f.write("; ===== %s : %s .. %s =====\n" % (blk.getName(), blk.getStart(), blk.getEnd()))
        i = listing.getInstructionIterator(blk.getStart())
        while i.hasNext():
            ins = i.next()
            f.write(str(ins) + "\n")

# ---- 4. C export of all internal functions ----
decomp = DecompInterface()
decomp.openProgram(currentProgram)

nc = 0
with open(os.path.join(OUTDIR, "uw_c.c"), "w") as f:
    f.write("// UW.EXE — Ghidra C export (x86 16-bit, Ghidra 12.1.3)\n\n")
    for fn in funcs:
        if fn.isExternal():
            continue
        monitor.startTask(fn.getName())
        try:
            res = decomp.decompile(0, fn, 120, monitor)
            if res is not None and res.dependedUponDecompilation():
                f.write("// @ %s\n" % fn.getEntry())
                f.write(res.getC())
                f.write("\n")
                nc += 1
        except Exception as e:
            print("decomp fail %s: %s" % (fn.getName(), e))
        if monitor.isCancelled():
            break
decomp.dispose()
print("functions decompiled: %d" % nc)
