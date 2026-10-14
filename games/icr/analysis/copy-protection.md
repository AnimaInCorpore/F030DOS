# Copy-protection gate — IndyCar Racing v1.05

Status: `RESOLVED` — the gate is fully recovered from the authority
executable: the challenge tables, the answer hash and the acceptance path are
all read out of `INDYCAR.EXE`, and the DOS oracle is driven past the screen to
the main menu with the game's own comparison confirming the answer. Nothing is
patched.

## Reproduction

`work/build_dos_hdd.py` + `work/run_qemu.py` reach the gate unaided; no
keypresses are needed to skip the attract sequence:

```text
python work/build_dos_hdd.py --no-boot
python work/run_qemu.py --timeout 170 --shot 90 --shot 120
```

The splash and its animated flight shots appear from ~20 s, and by ~80–90 s the
screen is the checkered-flag prompt:

```text
Page 126, line 1, word 1?

        Copy Protection
              —
  Please look in your manual
     for the requested word.
```

The page/line pair **differs between runs** (`92/3`, `92/5`, `112/2` and
`126/1` observed), so the challenge is generated per run.

To answer it and continue:

```text
python work/drive_protection.py --shot 200
```

## The mechanism

All addresses are runtime linear; code maps to the file at `−0x13EEDC` and data
at `−0x13FEDC` ([`executable.md`](executable.md)).

### Challenge selection — `0x1BF607`

```text
mov  ebx, 0xA9                  ; 169 challenges
xor  edx, edx
call 0x1A5577                   ; seed = seed * 0x19660D  (LCG at 0x1E3DBC)
div  ebx                        ; edx = seed mod 169  -> challenge index
mov  eax, [edx*2 + 0x1F28A2]    ; 16-bit table, read as a dword …
sar  eax, 0x10                  ; … keeping the entry itself, sign-extended
mov  [0x1EBDA8], edx            ; the index is kept for the answer check
```

The packed entry becomes the printed pair:

```text
page = 0xFF - ((v >> 4) & 0xFF)
line = 7 - (v >> 12)
```

The 169 entries at `0x1F28A4` (file `0xB29C8`) decode to 169 **distinct**
pairs, pages 4..128 and lines 1..6 — consistent with a real manual, and both
independently observed challenges `(92, 3)` and `(126, 1)` are in the table,
which is what confirms the decode.

### The answer hash — `0x1BF320`

```text
ecx = 1
for each of at most 3 characters b:      ; stops at NUL or after 3
    ecx = (ecx + ecx) - 1
    ecx ^= b | (b << 7)
```

The typed string is lowercased in place first (`0x1DC837` is a plain A–Z
`tolower`), so only the **first three characters, case-folded**, matter.

### Acceptance — `0x1BF350`

```text
[0x1EBD90] = 0                       ; answered flag
… lowercase the buffer at 0x1EBDAC in place …
mov  eax, 0x1EBDAC
call 0x1BF320                        ; hash the typed word
mov  [0x1EBDA0], eax
mov  eax, [0x1EBDA8]                 ; the challenge index
cmp  edx, [eax*4 + 0x1EC460]         ; against the expected-hash table
jne  reject
     [0x1EBD94] = 1                  ; accepted
```

The 169 expected values at `0x1EC460` (file `0xAC584`) are **hashes, not
words** — which is why no plaintext word list exists anywhere in
`INDYCAR.EXE` or `MAIN.DAT`. Both tables are byte-identical in the file and in
a RAM dump, i.e. they carry no load-time fixups and can be read statically.

## Answering it

`tools/re/protection.py` transcribes the hash and reads both tables from the
hash-checked authority executable:

```text
python tools/re/protection.py --answer 112 2
    challenge index 94: type "ps"
python tools/re/protection.py --list
```

Every one of the 169 entries has a preimage within three characters. **The
hash is lossy and the preimages are not the manual's words**: entries have
1–61 three-character preimages each, so what the tool produces is *an accepted
string*, not the printed word. Nothing may record a recovered preimage as the
manual word.

`work/drive_protection.py` closes the loop against the running game. A fixed
`run_qemu.py --key` script cannot work here — the challenge is random — so the
driver reads the index the game selected out of guest memory, answers it, and
checks the game's own flags:

```text
--- prompt at t=79s: 'Page 112, line 2, word 1?', challenge index 94 ---
  table says index 94 is page 112, line 2, hash 0x00004912
  answering "ps"
--- answered=1 accepted=1 (PASSED) ---
```

The driver cross-checks the table's page/line against the text on screen
before answering and aborts if they disagree, so a future drift in the data
delta fails loudly instead of silently answering the wrong challenge.

Two independent runs, two different challenges, both accepted — index 94
(`page 112, line 2`, answered `ps`) and index 56 (`page 92, line 5`, answered
`bah`) — each followed by the main menu. One pass would not have separated a
recovered mechanism from a lucky collision; two challenges with different
lengths of answer do.

## Wait loop

At the prompt the CPU spins in a two-address loop, sampled 18 of 20 times:

```text
linear 0x1999D7 / 0x1999E0   =  file 0x5AAFB (code delta +0x13EEDC)
    cmp dword [0x1E325C], 0
    jne …
    inc ebx
    jmp …
    cmp dword [0x1E3B70], 0
    je  …
```

`0x1E325C` and `0x1E3B70` are the fixed-up form of the operands
`0x325C`/`0x3B70` stored in the file (data base `0x1E0000` added by the
loader); `0x1E325C` is also the frame counter incremented at `0x1BF6C0`.

## What this opens

The oracle now reaches the main menu — `SINGLE RACE`, `CHAMPIONSHIP SEASON`,
`2-PLAYER RACE`, `PRESEASON TESTING`, `CARS`, `OPTIONS`, `EXIT` — which is the
first state from which menu and track flow can be exercised. See
[`runtime.md`](runtime.md).
