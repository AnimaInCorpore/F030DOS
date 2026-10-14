"""Run the supplied DEARJ.EXE against the five distribution volumes in DOS."""

from __future__ import annotations

import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dosimg


ROOT = dosimg.find_project_root(__file__)
WORK = os.path.join(ROOT, "work", "dearj_probe")
OUT = os.path.join(WORK, "dearj.hdd")
MEDIA = os.path.join(ROOT, "work", "media")

img = dosimg.DosImage(OUT, size_mb=32, work_dir=WORK, label="pg-dearj")
img.mkdir("/PG")
img.add_file(os.path.join(MEDIA, "disk1", "DEARJ.EXE"), "/PG/DEARJ.EXE")
for disk, name in zip(("disk1", "disk2", "disk3", "disk4", "disk5"),
                      ("DATA.A00", "DATA.A01", "DATA.A02", "DATA.A03", "DATA.A04")):
    img.add_file(os.path.join(MEDIA, disk, name), f"/PG/{name}")
img.add_bytes(b"FILES=50\r\nBUFFERS=30\r\n", "/CONFIG.SYS")
img.add_bytes(
    b"@ECHO OFF\r\n"
    b"C:\r\n"
    b"MD \\OUT\r\n"
    b"CD \\OUT\r\n"
    b"C:\\PG\\DEARJ.EXE E -Y C:\\PG\\DATA.A00> C:\\A00.LOG\r\n"
    b"C:\\PG\\DEARJ.EXE E -Y C:\\PG\\DATA.A01> C:\\A01.LOG\r\n"
    b"C:\\PG\\DEARJ.EXE E -Y C:\\PG\\DATA.A02> C:\\A02.LOG\r\n"
    b"C:\\PG\\DEARJ.EXE E -Y C:\\PG\\DATA.A03> C:\\A03.LOG\r\n"
    b"C:\\PG\\DEARJ.EXE E -Y C:\\PG\\DATA.A04> C:\\A04.LOG\r\n"
    b"C:\\QUIT.COM\r\n",
    "/AUTOEXEC.BAT",
)
img.write()
print(OUT)
if "--no-boot" not in sys.argv:
    env = dict(os.environ)
    qemu = r"C:\Program Files\qemu\qemu-system-i386.exe"
    if "QEMU_SYSTEM_I386" not in env and os.path.isfile(qemu):
        env["QEMU_SYSTEM_I386"] = qemu
    raise SystemExit(subprocess.call([
        sys.executable,
        os.path.join(ROOT, "work", "run_qemu.py"),
        "--hdd", OUT,
        "--timeout", "120",
        "--key", "20:y",
        "--key", "40:y",
        "--key", "60:y",
        "--key", "80:y",
        "--key", "100:y",
        "--cat", "::/A00.LOG",
        "--cat", "::/A01.LOG",
        "--cat", "::/A02.LOG",
        "--cat", "::/A03.LOG",
        "--cat", "::/A04.LOG",
    ], env=env))
