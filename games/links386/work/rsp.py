#!/usr/bin/env python3
"""A minimal GDB remote-serial-protocol client, enough to breakpoint and
watchpoint QEMU.

Derived from `F030Comanche/work/rsp.py` (the family's worked example, cited in
the cross-project ledger S6) and extended here with `Z2`/`z2` write
watchpoints: L386 needs to know *who writes* one word, not what the state is at
a known instruction, and QMP has neither breakpoints nor watchpoints.

Used with QMP, not instead of it.  The stub reports *that* it stopped, not
*where*: read the PC back through QMP `info registers` and check it against
what was armed, or a wrong-address stop yields a capture that looks coherent
and is not.

Watchpoint notes specific to QEMU:

  * `Z2,addr,len` takes the address the TLB sees, which on x86 is the
    **linear** address -- segment base already folded in, paging not yet
    applied.  So it catches a write through *any* selector whose base plus
    offset lands there, which is the whole point when the suspected writer
    reaches the slot through a descriptor that is only live between
    interrupts.  It does not catch a write through a *different* linear
    address that paging maps to the same physical page.
  * A write watchpoint reports after the store, and QEMU may leave the PC on
    the storing instruction or just past it.  Do not infer; read the PC and
    disassemble both.
  * Resuming needs the same lift/step/re-arm dance a repeated breakpoint
    needs -- see `cont_from_stop`.
"""
import select
import socket


class Rsp:
    def __init__(self, port, timeout=30):
        self.sock = socket.create_connection(("127.0.0.1", port), timeout=timeout)
        self.sock.settimeout(timeout)
        self.buf = b""

    def settimeout(self, t):
        self.sock.settimeout(t)

    def _send(self, payload):
        csum = sum(payload.encode()) & 0xFF
        self.sock.sendall(f"${payload}#{csum:02x}".encode())
        while True:
            b = self._raw(1)
            if b in (b"+", b"-"):
                return
            self.buf = b + self.buf
            return

    def _raw(self, n):
        while len(self.buf) < n:
            d = self.sock.recv(4096)
            if not d:
                raise EOFError("gdbstub closed")
            self.buf += d
        out, self.buf = self.buf[:n], self.buf[n:]
        return out

    def _recv(self):
        while True:
            c = self._raw(1)
            if c == b"$":
                break
        body = b""
        while True:
            c = self._raw(1)
            if c == b"#":
                break
            body += c
        self._raw(2)                      # checksum
        self.sock.sendall(b"+")
        return body.decode(errors="replace")

    def cmd(self, payload):
        self._send(payload)
        return self._recv()

    # kind 0 = software breakpoint, 2 = write watchpoint, 3 = read, 4 = access
    def insert(self, kind, addr, length=1):
        return self.cmd(f"Z{kind},{addr:x},{length}")

    def remove(self, kind, addr, length=1):
        return self.cmd(f"z{kind},{addr:x},{length}")

    def interrupt(self, tries=200):
        """Stop a running guest (RSP Ctrl-C) and collect the stop reply.

        Needed to arm *late*: an address that executes hundreds of times
        during startup and once more in the failing window is unreadable when
        armed from boot, and the failing hit is the only one that matters.
        """
        self.sock.sendall(b"\x03")
        for _ in range(tries):
            try:
                r = self._recv()
            except socket.timeout:
                return None
            if r.startswith(("T", "S")):
                return r
        return None

    def send_cont(self):
        """Start the guest running; the stop reply is collected separately so
        the caller can do QMP work (screenshots, keys) while it runs."""
        self._send("c")

    def poll_stop(self, wait=0.4):
        """A stop reply if one has arrived, None if the guest is still running.

        `select` first, then a blocking read: timing out *inside* `_recv`
        would drop the bytes of a half-arrived packet, and the next poll would
        resynchronise on a truncated reply -- a hit silently lost, which is
        the one failure this whole run cannot afford.
        """
        if not self.buf:
            ready, _, _ = select.select([self.sock], [], [], wait)
            if not ready:
                return None
        r = self._recv()
        return r if r.startswith(("T", "S")) else None

    def step(self, tries=400):
        self._send("s")
        for _ in range(tries):
            try:
                r = self._recv()
            except socket.timeout:
                return None
            if r.startswith(("T", "S")):
                return r
        return None

    def cont_from_stop(self, armed):
        """Resume from a stop, re-arming everything in `armed`.

        `armed` is [(kind, addr, len), ...].  Plain `c` is not enough: QEMU
        re-tests a breakpoint at the start of the block it is about to
        execute, so continuing from a PC that still carries one stops again
        without running an instruction -- an unlimited stream of identical
        "hits" that reads as a frozen guest rather than a tool fault.  A write
        watchpoint can present the same way when QEMU leaves the PC on the
        storing instruction.  Lift, single-step, re-arm, then continue.
        """
        for kind, addr, ln in armed:
            self.remove(kind, addr, ln)
        stepped = self.step()
        for kind, addr, ln in armed:
            self.insert(kind, addr, ln)
        return stepped

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass
