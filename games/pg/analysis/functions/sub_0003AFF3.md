# sub_0003AFF3 — scenario unit-class setup

Canonical recovered DOS ID; vaddr 3AFF3..3B291, file 83297..83535.
PANZER.EXE SHA-256
115ada29636b32c3e07446fdf4569d97324d357a1e71dafb859dd95c3cb69a86.
Status: successful Poland contract matches captured DOS in JS and native m68k;
other scenario/configuration branches and connected producers remain open.
No arguments. Called by scenario loader sub_00037216 after SET/STM and
sub_00039244. Sole direct callee sub_0006337B (random transition).

Visit sides 0/1, each 200 slots in order. Record address is
11C54+slot*98+side*49. Inactive record byte 1F yields class FF. Active records
increment side count, add byte 28 to sum, and take class byte 14 from the
50-byte equipment row at 179B0+record.word15*50. Output is 10694+slot*2+side.
Class 7 yields 7; classes >=11 yield FF; neither consumes random state.
For other classes, one random call uses only its low byte and computes
floor(byte*100/256). Below 2C13[scenario*2+side], output 7. Otherwise a second
call occurs only on side 1 with year byte 2B84<=41. If odd and scenario is
neither 6 nor 38 and class>=8, output 1. Next side-1/scenario-30/class-3 case
also outputs 1; otherwise retain equipment class.

For each side, store rounded average of record byte 28 at 1DD92+side*2:
(sum+floor(count/2))/count, truncated, or zero with no active units. DOS uses
low 16 bits of accumulators before division; maximum 200*255 fits. Return
EAX=1 for the bounded record/type shape: the increment changes the local side
byte to 2 while AL retains the old value 1. Preserve all other general registers
and balance stack. It writes only class bytes, average words and random seed.

Dependency producers remain open: scenario records, equipment table, scenario
selection/date/threshold globals and boot seed. Isolated captured inputs may
test this function, but cannot supply a supported connected game. Fixture and
implementation symbols are linked below. Preserve side/slot
iteration and conditional random-call order; matching class bytes alone does
not certify the state consumed by subsequent simulation.

Fixture: tests/fixtures/dos-unit-classes.json, collected from unchanged
poland-unit-classes-1/route.json at the entry and completed return. Full unit
records, used equipment-class bytes, scenario/year/thresholds and seed are
retained as isolated inputs. Shared expected outputs include all 400 class
bytes, both average words, final seed and EAX. Node checks the complete sparse
arena against DOS outputs and rejects extra writes. Native Falcon030 4 MB
Hatari matches all 412 canonical output bytes; source assembles with -m68000.

JS: web/reference/unit-classes.mjs; native: src/common/unit-classes.s, same
canonical ID. Native a0 replaces the DOS object-2 base; d0 returns EAX; all
other registers preserved. LE word accesses/stores use bytes, including odd
unit record addresses. DIVU handles the same nonnegative bounded numerator as
DOS IDIV; maximum 200*255 fits 16 bits. Flags and dead stack locals differ and
are not consumed. No hardware/stream adapters occur inside this body.
Commands: node tests/unit-classes-reference.mjs; python3
tools/check-native-unit-classes.py --out build/unit-classes-native-new.
Passing captured input state does not close the complete GAME001 loader.
