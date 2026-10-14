/*
 * x86trace -- a QEMU TCG plugin that records which guest bytes actually
 * executed, so a disassembly can be told what is code instead of guessing.
 *
 * The DOS-family counterpart to the telemetry MAME feeds jsm68kdisassembler,
 * except QEMU exposes a supported plugin API, so nothing has to be forked.
 *
 * Stage 1 records one byte of flags per guest linear address in a window:
 *
 *     bit 0  EXEC   this byte was part of an executed instruction
 *     bit 1  START  an executed instruction began at this byte
 *
 * That was deliberately the low end of the 8-byte-per-address record the
 * arcade side uses; the read-width/write/sign-extension bits (R8/R16/R32/
 * WRITE/SEXT) have since been added behind --mem via a memory callback.
 * Keeping the sidecar one byte wide means the file is trivially checkable
 * (its length must equal the window size).
 *
 * Usage:
 *   qemu-system-i386 ... \
 *     -plugin /path/x86trace.so,lo=0x10000,hi=0x90000,out=/path/run.trace
 *
 * lo/hi are guest *linear* addresses. In real mode with no paging that is
 * also the physical address, and file offset = linear - load_base, where
 * load_base is what gdbstub_probe.py already calibrates by hunting two
 * 16-byte windows of the image in guest RAM. Everything outside [lo,hi) is
 * not instrumented at all -- so BIOS, the DOS kernel and TSRs cost nothing
 * and, more importantly, never land in the coverage number.
 *
 * The base sidecar keys by address, not overlay: two overlay segments loaded
 * to the same linear address at different times would merge. The --ovl
 * flush-before-DOS-overwrites mechanism below solves that (used on POR's
 * TPOV and UW1's FBOV pools; see README.md); without --ovl the merge caveat
 * still applies. An --ovl flush clears the live flags for its region (each
 * unit must start from a clean slate), but the flushed coverage is folded
 * into a union array first, and --out reports that union -- so the overlay
 * window nesting inside [lo,hi) no longer drains bytes from the final
 * coverage. The overlay window MUST nest inside [lo,hi); the plugin refuses
 * to start otherwise.
 */
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdbool.h>
#include <string.h>

#include <qemu-plugin.h>

QEMU_PLUGIN_EXPORT int qemu_plugin_version = QEMU_PLUGIN_VERSION;

#define FLAG_EXEC  0x01   /* byte was part of an executed instruction */
#define FLAG_START 0x02   /* an executed instruction began here */
#define FLAG_R8    0x04   /* read as a byte */
#define FLAG_R16   0x08   /* read as a word */
#define FLAG_R32   0x10   /* read as a long */
#define FLAG_WRITE 0x20   /* written */
#define FLAG_SEXT  0x40   /* at least one read was sign-extended */

static uint64_t win_lo;
static uint64_t win_hi;
static char *out_path;
static uint8_t *flags;          /* one byte per address in [win_lo, win_hi) */
static uint8_t *keep;           /* union incl. flushed overlay coverage; only
                                   allocated with --ovl, reported by --out */
static uint64_t n_exec;         /* instruction executions seen in-window */

/*
 * Optional INT 21h log. Turbo Pascal's overlay manager reaches GAME.OVR
 * through DOS, so the file offset and buffer address of every overlay load
 * are visible as ordinary DOS calls -- no need to reverse the manager itself.
 * Off unless int21log= is given, so the default path stays a pure exec trace.
 */
struct dos_call {
    uint64_t vaddr;
    uint32_t eax, ebx, ecx, edx, ds, es;
};
/*
 * Overlay attribution.
 *
 * A Turbo Pascal / Borland overlay buffer hosts different units at the same
 * linear address over time, so a single address-keyed bitmap merges them. The
 * fix is to flush a region's coverage *before* it is overwritten, and to
 * identify what was in it by its own bytes.
 *
 * Content, not DOS bookkeeping: handles are recycled constantly (POR's boot
 * alone does 117 opens against 233 closes), so "handle 5 means GAME.OVR" is
 * not true for the length of a run. The bytes sitting in the buffer are.
 *
 * Each flush record is (buffer address, length, content samples, coverage
 * flags). trace_overlay.py locates the samples in the overlay file and folds
 * the flags onto file offsets.
 */
#define OVL_SAMPLES   4
#define OVL_SAMPLE_SZ 32

static uint64_t ovl_lo, ovl_hi;
static char *ovl_path;
static FILE *ovl_file;
static uint64_t n_flush;
static GByteArray *membuf;

static bool mem_telemetry;

/* Port I/O tallies; see vcpu_io_imm()/vcpu_io_dx() below. */
struct port_stat {
    uint32_t reads, writes;
    uint8_t widths;               /* bit0 = 8-bit, bit1 = 16-bit, bit2 = 32 */
    uint64_t first_pc;
};
static char *io_path;
static struct port_stat *ports;   /* 65536 entries when enabled */

static char *int21_path;
static struct dos_call *calls;
static size_t n_calls, max_calls;

/* Optional caller sidecar for INT 21h.  The ordinary log stays byte-for-byte
 * compatible; this records the far return address sitting on SS:SP before
 * the interrupt instruction executes. */
struct int21_caller {
    uint64_t vaddr;
    uint16_t ret_ip, ret_cs, sp, ss, cur_cs;
    uint8_t valid;
};
static char *int21_callers_path;
static struct int21_caller *callers;

/*
 * QEMU hands out register handles as small indices cast to a pointer, and
 * eax's is legitimately 0 -- so "is this handle null" is not a validity test.
 * Track found-ness separately or every eax read silently returns 0.
 */
struct reg_ref {
    struct qemu_plugin_register *h;
    bool found;
};
static struct reg_ref r_eax, r_ebx, r_ecx, r_edx, r_ds, r_es, r_esp, r_ss, r_cs;
static GByteArray *regbuf;

static uint32_t read_reg(const struct reg_ref *r)
{
    if (!r->found) {
        return 0;
    }
    g_byte_array_set_size(regbuf, 0);
    if (!qemu_plugin_read_register(r->h, regbuf)) {
        return 0;
    }
    uint32_t v = 0;
    for (guint i = 0; i < regbuf->len && i < 4; i++) {
        v |= (uint32_t)regbuf->data[i] << (8 * i);   /* target byte order */
    }
    return v;
}

static void vcpu_init(unsigned int vcpu_index, void *userdata)
{
    (void)vcpu_index; (void)userdata;
    if ((!int21_path && !int21_callers_path && !ovl_path && !io_path) || regbuf) {
        return;
    }
    regbuf = g_byte_array_new();
    GArray *regs = qemu_plugin_get_registers();
    struct { const char *name; struct reg_ref *ref; } want[] = {
        {"eax", &r_eax}, {"ebx", &r_ebx}, {"ecx", &r_ecx},
        {"edx", &r_edx}, {"ds", &r_ds},   {"es", &r_es},
        {"esp", &r_esp}, {"ss", &r_ss}, {"cs", &r_cs},
    };
    for (guint i = 0; regs && i < regs->len; i++) {
        qemu_plugin_reg_descriptor *d =
            &g_array_index(regs, qemu_plugin_reg_descriptor, i);
        for (size_t k = 0; k < sizeof(want) / sizeof(want[0]); k++) {
            if (!strcmp(d->name, want[k].name)) {
                want[k].ref->h = d->handle;
                want[k].ref->found = true;
            }
        }
    }
    if (regs) {
        g_array_free(regs, TRUE);
    }
    for (size_t k = 0; k < sizeof(want) / sizeof(want[0]); k++) {
        if (!want[k].ref->found) {
            fprintf(stderr, "x86trace: register '%s' not exposed; INT 21h log "
                    "will be incomplete\n", want[k].name);
        }
    }
}

/*
 * Write one flush record and clear the region's flags.
 *
 * @sample must be false outside vCPU context: qemu_plugin_read_memory_vaddr
 * asserts on current_cpu, so calling it from the atexit callback aborts QEMU
 * outright rather than returning failure.
 */
static void ovl_flush(uint64_t lo, uint64_t hi, bool sample)
{
    if (!ovl_file || hi <= lo) {
        return;
    }
    uint32_t len = (uint32_t)(hi - lo);
    uint64_t hdr[2] = {lo, (uint64_t)len};
    fwrite(hdr, sizeof(hdr), 1, ovl_file);

    /* Content samples, spread through the region, read before it is clobbered */
    for (int i = 0; i < OVL_SAMPLES; i++) {
        uint8_t buf[OVL_SAMPLE_SZ];
        memset(buf, 0, sizeof(buf));
        uint64_t at = lo + (uint64_t)i * (len / (OVL_SAMPLES + 1));
        if (sample && at + OVL_SAMPLE_SZ <= hi) {
            g_byte_array_set_size(membuf, 0);
            if (qemu_plugin_read_memory_vaddr(at, membuf, OVL_SAMPLE_SZ)
                && membuf->len >= OVL_SAMPLE_SZ) {
                memcpy(buf, membuf->data, OVL_SAMPLE_SZ);
            }
        }
        uint64_t rel = at - lo;
        fwrite(&rel, sizeof(rel), 1, ovl_file);
        fwrite(buf, sizeof(buf), 1, ovl_file);
    }

    /* The region's live flags are cleared so the next resident unit starts
     * from a clean slate -- but first fold them into the union that --out
     * reports, or every flush would drain bytes from the final coverage. */
    fwrite(flags + (lo - win_lo), 1, len, ovl_file);
    if (keep) {
        uint64_t base = lo - win_lo;
        for (uint64_t i = 0; i < len; i++) {
            keep[base + i] |= flags[base + i];
        }
    }
    memset(flags + (lo - win_lo), 0, len);
    n_flush++;
}

static void vcpu_int21(unsigned int vcpu_index, void *udata)
{
    (void)vcpu_index;
    if (n_calls >= max_calls) {
        return;                      /* logged enough; keep running */
    }
    struct dos_call *c = &calls[n_calls++];
    c->vaddr = (uint64_t)(uintptr_t)udata;
    c->eax = read_reg(&r_eax);
    c->ebx = read_reg(&r_ebx);
    c->ecx = read_reg(&r_ecx);
    c->edx = read_reg(&r_edx);
    c->ds  = read_reg(&r_ds);
    c->es  = read_reg(&r_es);

    if (callers) {
        struct int21_caller *r = &callers[n_calls - 1];
        uint32_t sp = read_reg(&r_esp) & 0xffff;
        uint32_t ss = read_reg(&r_ss) & 0xffff;
        uint32_t cs = read_reg(&r_cs) & 0xffff;
        r->vaddr = c->vaddr;
        r->sp = (uint16_t)sp;
        r->ss = (uint16_t)ss;
        r->cur_cs = (uint16_t)cs;
        uint8_t raw[4] = {0, 0, 0, 0};
        if (membuf) {
            g_byte_array_set_size(membuf, 0);
        }
        if (membuf && qemu_plugin_read_memory_vaddr(((uint64_t)ss << 4) + sp,
                                                     membuf, sizeof(raw))
            && membuf->len >= sizeof(raw)) {
            memcpy(raw, membuf->data, sizeof(raw));
            r->ret_ip = (uint16_t)raw[0] | ((uint16_t)raw[1] << 8);
            r->ret_cs = (uint16_t)raw[2] | ((uint16_t)raw[3] << 8);
            r->valid = 1;
        }
    }
}

/* DOS read (AH=3Fh) about to overwrite part of the overlay window. */
static void vcpu_dos_read(unsigned int vcpu_index, void *udata)
{
    (void)vcpu_index; (void)udata;
    /* Mask to AH: comparing the whole shifted EAX means residue in
     * EAX[31:16] (386+ code that did 32-bit arithmetic) silently stops
     * every overlay flush. */
    if (((read_reg(&r_eax) >> 8) & 0xff) != 0x3f) {
        return;
    }
    uint64_t buf = ((uint64_t)read_reg(&r_ds) << 4) + (read_reg(&r_edx) & 0xffff);
    uint64_t len = read_reg(&r_ecx) & 0xffff;
    uint64_t lo = buf > ovl_lo ? buf : ovl_lo;
    uint64_t hi = buf + len < ovl_hi ? buf + len : ovl_hi;
    if (len && lo < hi && lo >= win_lo && hi <= win_hi) {
        ovl_flush(lo, hi, true);
    }
}

/*
 * Callback udata packs (offset-into-window << 8) | insn_size, so the hot path
 * allocates nothing. A window is well under 2^56 and an x86 instruction is at
 * most 15 bytes, so both fit.
 */
static void vcpu_insn_exec(unsigned int vcpu_index, void *udata)
{
    (void)vcpu_index;
    uint64_t packed = (uint64_t)(uintptr_t)udata;
    uint64_t off = packed >> 8;
    unsigned size = packed & 0xff;

    n_exec++;
    flags[off] |= FLAG_START;
    for (unsigned i = 0; i < size; i++) {
        flags[off + i] |= FLAG_EXEC;
    }
}

/*
 * Data-access telemetry: width and signedness of every access the game's own
 * code makes into the window. This is what says whether a field is a byte, a
 * word or a long, and whether it is signed -- the two properties a port must
 * preserve exactly, and the two a disassembly can only guess at.
 *
 * Only instructions inside the window are instrumented, so these are accesses
 * made *by* the program. DOS reading into the same buffers is not recorded.
 */
static void vcpu_mem(unsigned int vcpu_index, qemu_plugin_meminfo_t info,
                     uint64_t vaddr, void *udata)
{
    (void)vcpu_index; (void)udata;
    if (vaddr < win_lo || vaddr >= win_hi) {
        return;
    }
    unsigned shift = qemu_plugin_mem_size_shift(info);
    unsigned size = 1u << shift;
    uint8_t bit = shift == 0 ? FLAG_R8 : shift == 1 ? FLAG_R16 : FLAG_R32;
    bool store = qemu_plugin_mem_is_store(info);
    bool sext = !store && qemu_plugin_mem_is_sign_extended(info);

    for (unsigned i = 0; i < size; i++) {
        uint64_t a = vaddr + i;
        if (a >= win_hi) {
            break;
        }
        uint8_t *f = &flags[a - win_lo];
        *f |= store ? FLAG_WRITE : bit;
        if (sext) {
            *f |= FLAG_SEXT;
        }
    }
}

/*
 * Port I/O. DOS-era hardware is programmed through in/out, which QEMU's own
 * hwprofile plugin cannot see (it covers memory-mapped regions only), so the
 * list of ports a game touches has to come from here. That list is the
 * hardware half of the port's substitution set.
 */
static void note_port(uint32_t port, bool write, unsigned width, uint64_t pc)
{
    struct port_stat *p = &ports[port & 0xffff];
    if (write) {
        p->writes++;
    } else {
        p->reads++;
    }
    p->widths |= width == 1 ? 1 : width == 2 ? 2 : 4;
    if (!p->first_pc) {
        p->first_pc = pc;
    }
}

/*
 * Callback udata layout for both I/O paths:
 *   bits  0-15  immediate port number (imm form only)
 *   bit     16  write
 *   bits 17-18  log2(access width): 0 = byte, 1 = word, 2 = dword
 *   bits 20-    PC of the instruction
 */

/* in/out with the port in an immediate byte -- known at translation time. */
static void vcpu_io_imm(unsigned int vcpu_index, void *udata)
{
    (void)vcpu_index;
    uint64_t v = (uint64_t)(uintptr_t)udata;
    note_port((uint32_t)(v & 0xffff), (v >> 16) & 1,
              1u << ((v >> 17) & 3), v >> 20);
}

/* in/out/ins/outs through DX -- the port is only known at run time. */
static void vcpu_io_dx(unsigned int vcpu_index, void *udata)
{
    (void)vcpu_index;
    uint64_t v = (uint64_t)(uintptr_t)udata;
    note_port(read_reg(&r_edx) & 0xffff, (v >> 16) & 1,
              1u << ((v >> 17) & 3), v >> 20);
}

static void vcpu_tb_trans(struct qemu_plugin_tb *tb, void *userdata)
{
    (void)userdata;
    size_t n = qemu_plugin_tb_n_insns(tb);

    for (size_t i = 0; i < n; i++) {
        struct qemu_plugin_insn *insn = qemu_plugin_tb_get_insn(tb, i);
        uint64_t vaddr = qemu_plugin_insn_vaddr(insn);
        size_t size = qemu_plugin_insn_size(insn);

        if (vaddr < win_lo || vaddr >= win_hi) {
            continue;
        }
        /* Clamp rather than drop: an instruction straddling the top of the
         * window is still evidence about the bytes that are inside it. */
        if (vaddr + size > win_hi) {
            size = win_hi - vaddr;
        }
        if (size > 15) {
            size = 15;
        }
        uint64_t packed = ((vaddr - win_lo) << 8) | (uint64_t)size;
        qemu_plugin_register_vcpu_insn_exec_cb(insn, vcpu_insn_exec,
                                               QEMU_PLUGIN_CB_NO_REGS,
                                               (void *)(uintptr_t)packed);

        if (mem_telemetry) {
            qemu_plugin_register_vcpu_mem_cb(insn, vcpu_mem,
                                             QEMU_PLUGIN_CB_NO_REGS,
                                             QEMU_PLUGIN_MEM_RW, NULL);
        }

        if (io_path) {
            uint8_t op[8] = {0};
            size_t got = qemu_plugin_insn_data(insn, op, sizeof(op));
            /* Walk the prefix bytes: 0x66 flips the word forms to dword in a
             * 16-bit guest, and F2/F3 REP plus segment/address prefixes are
             * legal on the string forms and must not hide the opcode. */
            unsigned k = 0;
            bool osz = false;
            while (k < got) {
                uint8_t b = op[k];
                if (b == 0x66) { osz = true; k++; continue; }
                if (b == 0x67 || b == 0xF0 || b == 0xF2 || b == 0xF3 ||
                    b == 0x26 || b == 0x2E || b == 0x36 || b == 0x3E ||
                    b == 0x64 || b == 0x65) { k++; continue; }
                break;
            }
            if (k < got) {
                uint8_t o = op[k];
                bool imm = (o >= 0xE4 && o <= 0xE7);
                bool dx  = (o >= 0xEC && o <= 0xEF);
                bool str = (o >= 0x6C && o <= 0x6F);   /* INS/OUTS: port in DX */
                if (imm || dx || str) {
                    /* Bit 1 = write, bit 0 = word form -- the same rule in
                     * all three families (E6/E7, EE/EF, 6E/6F write). */
                    bool write = (o & 0x02) != 0;
                    /* 16-bit guest: the word forms are 16-bit by default and
                     * 32-bit under 0x66; the byte forms are always 8-bit.
                     * (The old `prefix ? 2 : 1` recorded an unprefixed
                     * OUT DX,AX as an 8-bit access.) */
                    unsigned wshift = (o & 0x01) ? (osz ? 2u : 1u) : 0u;
                    uint64_t ud = ((uint64_t)vaddr << 20)
                                | ((uint64_t)wshift << 17)
                                | ((uint64_t)write << 16);
                    if (imm && got > k + 1) {
                        qemu_plugin_register_vcpu_insn_exec_cb(
                            insn, vcpu_io_imm, QEMU_PLUGIN_CB_NO_REGS,
                            (void *)(uintptr_t)(ud | op[k + 1]));
                    } else if (dx || str) {
                        qemu_plugin_register_vcpu_insn_exec_cb(
                            insn, vcpu_io_dx, QEMU_PLUGIN_CB_R_REGS,
                            (void *)(uintptr_t)ud);
                    }
                }
            }
        }

        if ((int21_path || int21_callers_path || ovl_path) && size >= 2) {
            uint8_t op[2] = {0, 0};
            qemu_plugin_insn_data(insn, op, sizeof(op));
            if (op[0] == 0xCD && op[1] == 0x21 && ovl_path) {
                qemu_plugin_register_vcpu_insn_exec_cb(insn, vcpu_dos_read,
                                                       QEMU_PLUGIN_CB_R_REGS,
                                                       NULL);
            }
            if (op[0] == 0xCD && op[1] == 0x21) {
                /* Registers are wanted here, so this one asks for them. */
                qemu_plugin_register_vcpu_insn_exec_cb(insn, vcpu_int21,
                                                       QEMU_PLUGIN_CB_R_REGS,
                                                       (void *)(uintptr_t)vaddr);
            }
        }
    }
}

static void plugin_exit(void *p)
{
    (void)p;
    uint64_t span = win_hi - win_lo;
    uint64_t covered = 0, starts = 0;
    char buf[512];

    if (ovl_file) {
        /* Flush the last occupants FIRST, so their coverage reaches the
         * union before it is written below. atexit cannot read guest memory,
         * so their samples come out zeroed and trace_overlay.py identifies
         * them from the run's RAM dump instead. */
        ovl_flush(ovl_lo, ovl_hi, false);
        fclose(ovl_file);
        ovl_file = NULL;
        snprintf(buf, sizeof(buf),
                 "x86trace: %" PRIu64 " overlay flushes -> %s\n",
                 n_flush, ovl_path);
        qemu_plugin_outs(buf);
    }

    /* --out reports the union of live flags and everything --ovl flushed,
     * so per-flush clearing cannot drain the final coverage. */
    uint8_t *rep = flags;
    if (keep) {
        for (uint64_t i = 0; i < span; i++) {
            keep[i] |= flags[i];
        }
        rep = keep;
    }
    for (uint64_t i = 0; i < span; i++) {
        if (rep[i] & FLAG_EXEC)  covered++;
        if (rep[i] & FLAG_START) starts++;
    }

    FILE *f = fopen(out_path, "wb");
    if (!f) {
        snprintf(buf, sizeof(buf), "x86trace: cannot write %s\n", out_path);
        qemu_plugin_outs(buf);
        return;
    }
    fwrite(rep, 1, span, f);
    fclose(f);

    if (int21_path) {
        FILE *lf = fopen(int21_path, "w");
        if (lf) {
            fprintf(lf, "# vaddr ax bx cx dx ds es\n");
            for (size_t i = 0; i < n_calls; i++) {
                struct dos_call *c = &calls[i];
                fprintf(lf, "%" PRIx64 " %04x %04x %04x %04x %04x %04x\n",
                        c->vaddr, c->eax & 0xffff, c->ebx & 0xffff,
                        c->ecx & 0xffff, c->edx & 0xffff,
                        c->ds & 0xffff, c->es & 0xffff);
            }
            fclose(lf);
            snprintf(buf, sizeof(buf), "x86trace: logged %zu INT 21h calls to %s%s\n",
                     n_calls, int21_path,
                     n_calls >= max_calls ? " (LOG FULL -- truncated)" : "");
            qemu_plugin_outs(buf);
        }
    }

    if (int21_callers_path) {
        FILE *cf = fopen(int21_callers_path, "w");
        if (cf) {
            fprintf(cf, "# index vaddr ret_ip ret_cs sp ss cur_cs valid\n");
            for (size_t i = 0; i < n_calls; i++) {
                struct int21_caller *r = &callers[i];
                fprintf(cf, "%zu %" PRIx64 " %04x %04x %04x %04x %04x %u\n",
                        i, r->vaddr, r->ret_ip, r->ret_cs, r->sp, r->ss,
                        r->cur_cs, r->valid);
            }
            fclose(cf);
            snprintf(buf, sizeof(buf),
                     "x86trace: logged %zu INT 21h callers to %s%s\n",
                     n_calls, int21_callers_path,
                     n_calls >= max_calls ? " (LOG FULL -- truncated)" : "");
            qemu_plugin_outs(buf);
        }
    }

    if (ports) {
        FILE *pf = fopen(io_path, "w");
        if (pf) {
            unsigned n = 0;
            fprintf(pf, "# port reads writes widths first_pc\n");
            for (unsigned i = 0; i < 65536; i++) {
                if (!ports[i].reads && !ports[i].writes) {
                    continue;
                }
                n++;
                char wbuf[12];
                wbuf[0] = '\0';
                if (ports[i].widths & 1) { strcat(wbuf, "8"); }
                if (ports[i].widths & 2) {
                    if (wbuf[0]) { strcat(wbuf, "+"); }
                    strcat(wbuf, "16");
                }
                if (ports[i].widths & 4) {
                    if (wbuf[0]) { strcat(wbuf, "+"); }
                    strcat(wbuf, "32");
                }
                fprintf(pf, "%04x %u %u %s %" PRIx64 "\n", i,
                        ports[i].reads, ports[i].writes, wbuf,
                        ports[i].first_pc);
            }
            fclose(pf);
            snprintf(buf, sizeof(buf),
                     "x86trace: %u distinct I/O ports -> %s\n", n, io_path);
            qemu_plugin_outs(buf);
        }
    }

    snprintf(buf, sizeof(buf),
             "x86trace: window 0x%" PRIx64 "-0x%" PRIx64 " (%" PRIu64 " bytes)\n"
             "x86trace: %" PRIu64 " bytes executed (%.2f%%), "
             "%" PRIu64 " instruction starts, %" PRIu64 " executions\n"
             "x86trace: wrote %s\n",
             win_lo, win_hi, span,
             covered, span ? 100.0 * (double)covered / (double)span : 0.0,
             starts, n_exec, out_path);
    qemu_plugin_outs(buf);
}

static int parse_u64(const char *v, uint64_t *out)
{
    char *end = NULL;
    uint64_t r = strtoull(v, &end, 0);   /* 0x... honoured */
    if (end == v || *end != '\0') {
        return -1;
    }
    *out = r;
    return 0;
}

QEMU_PLUGIN_EXPORT int qemu_plugin_install(qemu_plugin_id_t id,
                                           const qemu_info_t *info,
                                           int argc, char **argv)
{
    int have_lo = 0, have_hi = 0;

    (void)info;

    for (int i = 0; i < argc; i++) {
        char *opt = argv[i];
        char *eq = strchr(opt, '=');
        if (!eq) {
            fprintf(stderr, "x86trace: bad argument '%s'\n", opt);
            return -1;
        }
        *eq = '\0';
        const char *val = eq + 1;
        if (!strcmp(opt, "lo")) {
            if (parse_u64(val, &win_lo)) { goto badnum; }
            have_lo = 1;
        } else if (!strcmp(opt, "hi")) {
            if (parse_u64(val, &win_hi)) { goto badnum; }
            have_hi = 1;
        } else if (!strcmp(opt, "out")) {
            out_path = strdup(val);
        } else if (!strcmp(opt, "int21log")) {
            int21_path = strdup(val);
        } else if (!strcmp(opt, "int21callers")) {
            int21_callers_path = strdup(val);
        } else if (!strcmp(opt, "io")) {
            io_path = strdup(val);
        } else if (!strcmp(opt, "mem")) {
            if (!qemu_plugin_bool_parse(opt, val, &mem_telemetry)) {
                fprintf(stderr, "x86trace: mem= wants on/off\n");
                return -1;
            }
        } else if (!strcmp(opt, "ovl")) {
            ovl_path = strdup(val);
        } else if (!strcmp(opt, "ovl_lo")) {
            if (parse_u64(val, &ovl_lo)) { goto badnum; }
        } else if (!strcmp(opt, "ovl_hi")) {
            if (parse_u64(val, &ovl_hi)) { goto badnum; }
        } else {
            fprintf(stderr, "x86trace: unknown argument '%s'\n", opt);
            return -1;
        }
        *eq = '=';
        continue;
    badnum:
        fprintf(stderr, "x86trace: '%s' is not a number\n", val);
        return -1;
    }

    if (!have_lo || !have_hi || !out_path) {
        fprintf(stderr, "x86trace: need lo=, hi= and out=\n");
        return -1;
    }
    if (win_hi <= win_lo) {
        fprintf(stderr, "x86trace: empty window\n");
        return -1;
    }

    flags = calloc(1, win_hi - win_lo);
    if (!flags) {
        fprintf(stderr, "x86trace: cannot allocate %" PRIu64 " bytes\n",
                win_hi - win_lo);
        return -1;
    }

    if (io_path) {
        ports = calloc(65536, sizeof(*ports));
        if (!ports) {
            fprintf(stderr, "x86trace: cannot allocate port table\n");
            return -1;
        }
        qemu_plugin_register_vcpu_init_cb(id, vcpu_init, NULL);
    }

    if (ovl_path) {
        if (ovl_hi <= ovl_lo) {
            fprintf(stderr, "x86trace: ovl= needs ovl_lo=/ovl_hi=\n");
            return -1;
        }
        /* ovl_flush() indexes `flags` at (ovl - win_lo): a window outside
         * [win_lo, win_hi) is an out-of-bounds heap read AND write, so
         * refuse it here instead of corrupting the heap at exit. */
        if (ovl_lo < win_lo || ovl_hi > win_hi) {
            fprintf(stderr, "x86trace: ovl window 0x%" PRIx64 "-0x%" PRIx64
                    " must nest inside lo/hi 0x%" PRIx64 "-0x%" PRIx64 "\n",
                    ovl_lo, ovl_hi, win_lo, win_hi);
            return -1;
        }
        keep = calloc(1, win_hi - win_lo);
        if (!keep) {
            fprintf(stderr, "x86trace: cannot allocate %" PRIu64 " bytes\n",
                    win_hi - win_lo);
            return -1;
        }
        ovl_file = fopen(ovl_path, "wb");
        if (!ovl_file) {
            fprintf(stderr, "x86trace: cannot write %s\n", ovl_path);
            return -1;
        }
        membuf = g_byte_array_new();
        qemu_plugin_register_vcpu_init_cb(id, vcpu_init, NULL);
    }

    if (int21_path || int21_callers_path) {
        max_calls = 400000;
        calls = calloc(max_calls, sizeof(*calls));
        if (!calls) {
            fprintf(stderr, "x86trace: cannot allocate INT 21h log\n");
            return -1;
        }
        if (int21_callers_path) {
            callers = calloc(max_calls, sizeof(*callers));
            if (!callers) {
                fprintf(stderr, "x86trace: cannot allocate INT 21h caller log\n");
                return -1;
            }
            if (!membuf) {
                membuf = g_byte_array_new();
            }
        }
        qemu_plugin_register_vcpu_init_cb(id, vcpu_init, NULL);
    }

    qemu_plugin_register_vcpu_tb_trans_cb(id, vcpu_tb_trans, NULL);
    qemu_plugin_register_atexit_cb(id, plugin_exit, NULL);
    return 0;
}
