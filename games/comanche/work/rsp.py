#!/usr/bin/env python3
"""A minimal GDB remote-serial-protocol client, enough to breakpoint QEMU.

Why this exists: the marcher's silhouettes and the state that produced them
can only be sampled together at a known instruction. A timed sample - even a
frozen one - can pair one frame's camera with another frame's silhouettes,
because the frame driver latches, renders, then integrates. QMP has no
breakpoint; the gdbstub does.

Used with QMP, not instead of it: this stops the guest at an address, and the
existing QMP reads then run against a machine that is stopped at a known point.
"""
import socket


class Rsp:
    def __init__(self, port, timeout=30):
        self.sock = socket.create_connection(("127.0.0.1", port), timeout=timeout)
        self.sock.settimeout(timeout)
        self.buf = b""

    def _send(self, payload):
        csum = sum(payload.encode()) & 0xFF
        self.sock.sendall(f"${payload}#{csum:02x}".encode())
        # swallow the ack
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

    def set_break(self, addr, kind=1):
        return self.cmd(f"Z0,{addr:x},{kind}")

    def clear_break(self, addr, kind=1):
        return self.cmd(f"z0,{addr:x},{kind}")

    def cont_until_stop(self, tries=400):
        """Continue and wait for a stop reply, retrying past spurious ones."""
        self._send("c")
        for _ in range(tries):
            try:
                r = self._recv()
            except socket.timeout:
                return None
            if r.startswith(("T", "S")):
                return r
        return None

    def step(self):
        """Execute one instruction; returns the stop reply or None."""
        self._send("s")
        for _ in range(400):
            try:
                r = self._recv()
            except socket.timeout:
                return None
            if r.startswith(("T", "S")):
                return r
        return None

    def cont_from_break(self, addr, kind=1, tries=400):
        """Resume from a stop AT `addr` and run to the next hit of it.

        Plain `c` does not work here. QEMU re-tests the breakpoint at the
        start of the block it is about to execute, so continuing from a PC
        that still carries one stops again immediately without running a
        single instruction: the guest looks frozen and the capture loop
        returns an unlimited stream of byte-identical "ticks" - the state is
        real, the repetition is the tool. Real GDB avoids this by lifting the
        breakpoint, stepping one instruction and re-arming it, which is what
        this does. Only a repeated-breakpoint loop meets it; a single stop
        (dump_marcher_tables.py) never does.
        """
        self.clear_break(addr, kind)
        stepped = self.step()
        self.set_break(addr, kind)
        if stepped is None:
            return None
        return self.cont_until_stop(tries)

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass
