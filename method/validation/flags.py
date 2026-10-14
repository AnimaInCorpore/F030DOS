"""N/A - conservative backward liveness over an adapter-supplied flag graph."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Node:
    reads: int
    writes: int
    successors: tuple
    escapes: bool = False


def liveness(nodes, all_flags):
    """Return live-in/out masks. Unknown exits observe every flag.

    An adapter supplies proven *unconditional* writes. Undefined or conditional
    effects must retain their input flags until independently resolved. Calls can be
    modeled precisely only with a proven ABI/return graph; otherwise escape.
    """
    live_in = {pc: 0 for pc in nodes}
    live_out = dict(live_in)
    changed = True
    while changed:
        changed = False
        for pc, node in reversed(list(nodes.items())):
            out = all_flags if node.escapes else 0
            for target in node.successors:
                out |= live_in.get(target, all_flags)
            incoming = node.reads | (out & ~node.writes)
            if (incoming, out) != (live_in[pc], live_out[pc]):
                live_in[pc], live_out[pc] = incoming, out
                changed = True
    return live_in, live_out
