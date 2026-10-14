#!/usr/bin/env python3
"""Minimal FAT12/16/32 image browser: list and extract files.

Usage:
    fat.py list  image.img [dir]
    fat.py get   image.img file_in_image dest_path
    fat.py put   image.img host_path file_in_image   (creates dir/file; 0x00-filled free space)
    fat.py tree  image.img
"""
import struct, sys

ATTR_READ=1; ATTR_HIDDEN=2; ATTR_SYSTEM=4; ATTR_VOL=8; ATTR_DIR=16; ATTR_ARCH=32

class Fat:
    def __init__(self, data):
        self.d = data
        bps = struct.unpack("<H", data[11:13])[0]
        spc = struct.unpack("<B", data[13:14])[0]
        if spc == 0: raise SystemExit("not a FAT boot sector")
        self.bps, self.spc = bps, spc
        nrsv = struct.unpack("<H", data[14:16])[0]
        ntf  = struct.unpack("<B", data[16:17])[0]
        nres = struct.unpack("<H", data[17:19])[0]
        total16 = struct.unpack("<H", data[19:21])[0]
        media = data[21]
        nft = struct.unpack("<H", data[22:24])[0]
        total = total16 if total16 else struct.unpack("<I", data[32:36])[0]
        fat_secs = (nft * bps + bps - 1) // bps if nft else ((total16 * spc - 9) // 32 + 1) // spc
        self.fat_off = (nrsv + 0) * bps if False else (nrsv) * bps
        self.fat_sz = fat_secs * bps
        self.root_off = (nrsv + (fat_secs if ntf else 0)) * bps
        self.data_off = self.root_off + (37 * 32 if ntf else 0)
        self.ntf = bool(ntf)
        self.total = total
        if media == 0xF8 or (media == 0xFF and total16 < 65525):
            self.ftype = 12
        elif media in (0xF0, 0xF8, 0xFF):
            self.ftype = 16
        else:
            # fallback heuristic on cluster count
            self.ftype = 12
        if nft == 0:
            nft = (self.fat_sz + bps - 1) // bps
        self.nft = nft
        last = ((total16 if total16 else total) * spc - self.root_off - 37*32//1)
        # cluster count
        data_start = self.root_off + (37*32 if ntf else 0)
        self.nc = (total * bps - data_start) // spc
        if self.nc < 4085: self.ftype = 12
        elif self.nc < 65525: self.ftype = 16
        else: self.ftype = 32

    def cluster_of(self, off):
        return (off - self.data_off) // self.spc

    def off_of(self, clus):
        return self.data_off + clus * self.spc

    def fat_get(self, clus):
        i = clus * self.ftype // 8
        off = self.fat_off + i
        if self.ftype == 12:
            v = self.d[off] | (self.d[off+1] << 8)
            return v >> (4 if i % 2 else 0) & 0xFFF
        if self.ftype == 16:
            return struct.unpack("<H", self.d[off:off+2])[0]
        v = struct.unpack("<I", self.d[off:off+4])[0] & 0x0FFFFFFF
        return v

    def chain(self, clus):
        out, c = [], clus
        while 2 < c < (1 << (self.ftype if self.ftype<32 else 32)) - 7:
            if c in out: break
            out.append(c)
            c = self.fat_get(c)
        return out

    def file_data(self, clus):
        return b"".join(self.d[self.off_of(c): self.off_of(c) + self.spc]
                        for c in self.chain(clus))

    def dir_entries(self, dir_off, dir_sz=None):
        if dir_off is None:
            raise SystemExit("use data cluster dir")
        base = dir_off if isinstance(dir_off, int) else None
        # dir_off can be absolute offset (root) or cluster
        if base is not None:
            blob = self.d[base: base + (dir_sz or 37*32)]
        else:
            blob = self.file_data(dir_off)
        for i in range(0, len(blob) - 31, 32):
            e = blob[i:i+32]
            if not e or e[0] in (0, 0xE5): continue
            name = e[0:8].decode("latin1").strip()
            ext = e[8:11].decode("latin1").strip()
            attr = e[11]
            clus_h, clus_l = struct.unpack("<HH", e[26:30])
            clus = clus_h | clus_l
            size = struct.unpack("<I", e[28:32])[0]
            yield name, ext, attr, clus, size

    def find(self, path):
        """Return (offset_range or cluster, is_dir) for /A/B.C style path (no leading slash needed)."""
        cur = ("root", None)
        for part in [p for p in path.replace("\\","/").split("/") if p]:
            if cur[0] == "root":
                offs = lambda: self.dir_entries(self.root_off)
            else:
                offs = lambda: self.dir_entries(cur[1])
            for name, ext, attr, clus, size in offs():
                if part.upper() in (f"{name}.{ext}".upper(), name.upper(), f"{name}{ext}".upper(),
                                    f"{name}     {ext}".upper()):
                    if attr & ATTR_DIR:
                        cur = ("dir", clus)
                        break
                    else:
                        return clus, size
            else:
                raise SystemExit(f"not found: {part} in {path}")
        if cur[0] == "root":
            return "root", None
        return cur[1], None

    def free_cluster(self):
        for c in range(2, self.nc + 1):
            if self.fat_get(c) == 0:
                return c
        raise SystemExit("no free clusters")

    def set_fat(self, clus, val):
        i = clus * self.ftype // 8
        off = self.fat_off + i
        if self.ftype == 12:
            v = self.d[off] | (self.d[off+1] << 8)
            if i % 2: v = (v & 0xFF) | (val << 4)
            else:     v = (v & 0xFFF0) | val
            self.d[off:off+2] = struct.pack("<H", v)
        elif self.ftype == 16:
            self.d[off:off+2] = struct.pack("<H", val)
        else:
            v = struct.unpack("<I", self.d[off:off+4])[0]
            v = (v & 0xF0000000) | val
            self.d[off:off+4] = struct.pack("<I", v)

    def alloc(self, nbytes):
        clus = self.free_cluster()
        self.set_fat(clus, 0xFFFFFFFF)  # EOF; will fix below
        prev = None
        rem = nbytes
        cur = clus
        while rem > 0:
            self.set_fat(cur, 0xFFFFFFFF)
            rem -= self.spc
            if rem > 0:
                nxt = self.free_cluster()
                self.set_fat(cur, nxt)
                cur = nxt
        self.set_fat(cur, 0xFFFFFFFF)
        return clus

    def make_entry(self, name, ext, attr, clus, size):
        n = name.upper().ljust(8).encode("latin1")[:8]
        e = bytearray(32)
        e[0:8] = n
        e[8:11] = ext.upper().ljust(3).encode("latin1")
        e[11] = attr
        e[26:28] = struct.pack("<H", (clus >> 16) & 0xFFFF)
        e[28:30] = struct.pack("<H", clus & 0xFFFF)
        e[28:32] = struct.pack("<I", size)
        return bytes(e)

    def append_entry(self, dir_clus, entry):
        """Append a 32-byte entry to a directory (cluster-based)."""
        chain = self.chain(dir_clus)
        # ensure a free slot; grow dir by one cluster if needed
        last_off = self.off_of(chain[-1])
        last_end = last_off + self.spc
        if last_end % 32 == 0:  # full
            nxt = self.free_cluster()
            self.set_fat(dir_clus + 0, dir_clus)  # noop
            # link new cluster to dir chain
            self.set_fat(chain[-1], nxt)
            self.set_fat(nxt, 0xFFFFFFFF)
            self.d[self.off_of(nxt): self.off_of(nxt)+self.spc] = b"\0" * self.spc
            last_off = self.off_of(nxt)
            chain.append(nxt)
        slot = last_off + ((last_off + 32 - 1) // 32 + 1) * 32 - 32
        if slot >= last_off + self.spc:
            slot = last_off
        self.d[slot:slot+32] = entry

def main():
    cmd, img = sys.argv[1], sys.argv[2]
    f = Fat(open(img, "rb").read())
    print(f"# FAT{f.ftype} bps={f.bps} spc={f.spc} clusters={f.nc} fat_sectors={f.nft} total={f.total}")
    if cmd in ("list", "tree"):
        def walk(off, depth, is_root=False):
            entries = list(f.dir_entries(f.root_off if is_root else off))
            for name, ext, attr, clus, size in entries:
                nm = f"{name}.{ext}".strip() if ext else name
                if attr & ATTR_DIR:
                    print(" " * depth + nm + "/")
                    if cmd == "tree":
                        walk(clus, depth + 2)
                else:
                    print(" " * depth + f"{nm:16s} {size}")
        walk(0, 0, True)
    elif cmd == "get":
        src, dst = sys.argv[3], sys.argv[4]
        clus, size = f.find(src)
        open(dst, "wb").write(f.file_data(clus))
        print(f"{src} -> {dst} ({size} bytes)")
    elif cmd == "put":
        host, dest = sys.argv[3], sys.argv[4]
        data = open(host, "rb").read()
        clus = f.alloc((len(data) + f.spc - 1) // f.spc * f.spc)
        off = f.off_of(clus)
        f.d[off:off+len(data)] = data
        nm, ext = dest.upper().split(".")
        f.append_entry(0 if False else _rootdir(f), f.make_entry(nm[:8], ext[:3], 0, clus, len(data)))
        open(img, "wb").write(f.d)
        print(f"put {dest} ({len(data)} bytes) at cluster {clus}")
def _rootdir(f):
    # root directory of a FAT12/16 image is a plain area, not a cluster;
    # for put(), we only support appending to a *cluster* dir — caller passes cluster.
    raise SystemExit("put to root of FAT12/16 not supported; use a cluster dir")
if __name__ == "__main__":
    main()
