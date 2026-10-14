; Minimal test for `mov ds, cs:[disp32]` with a non-zero CS base.
;
; analysis/executable.md measures the Links 386 `10049` failure down to one
; instruction -- `2E 8E 1D F8 03 00 00` at the extender's 0xC2C136 -- that
; dereferences linear 0x3F8 instead of CS.base + 0x3F8, faults on the garbage
; selector it finds there, and recurses until the interrupt-stack pool empties.
; The attribution to the emulator rests on that one observation inside a large
; program.  This boot sector reproduces the addressing question on its own, with
; no DOS, no extender and no paging, so the answer cannot be a property of Links
; 386.
;
; Three candidate answers are planted, each a *valid* data selector, so the test
; reports an address rather than faulting:
;
;   linear 0x13F8 = CS.base + 0x3F8  ->  0x0018   the architecturally correct one
;   linear 0x03F8 = 0     + 0x3F8    ->  0x0020   a dropped segment base
;   linear 0x23F8 = 0x2000 + 0x3F8   ->  0x0030   DS's base used instead of CS's
;
; Build:  nasm -f bin segtest.asm -o segtest.img            (all bases zero)
;         nasm -f bin -DCTRL segtest.asm -o segtest_ctrl.img (DS/ES/SS base 0x2000)
;
; The CTRL build is the control: it is the same instruction with the same CS
; base, differing only in whether the *default* segment bases are zero -- the
; one state that separated the faulting execution from the working ones.
;
; Exit code through isa-debug-exit is (AL << 1) | 1:
;   AL=1 -> DS=0x18  CS override applied (correct)      exit 3
;   AL=2 -> DS=0x20  read at linear 0x3F8, base dropped exit 5
;   AL=3 -> DS=0x30  read through DS's base             exit 7
;   AL=4 -> anything else                               exit 9

CSBASE  equ 0x1000
DSBASE  equ 0x2000

bits 16
org 0x7C00

start:
    cli
    xor ax, ax
    mov ds, ax
    mov es, ax
    mov ss, ax
    mov sp, 0x7C00

    mov word [0x03F8], 0x0020
    mov word [CSBASE + 0x03F8], 0x0018
    mov word [DSBASE + 0x03F8], 0x0030

    lgdt [gdtr]
    mov eax, cr0
    or  al, 1
    mov cr0, eax
    jmp 0x08:(pm32 - CSBASE)

bits 32
pm32:
    mov eax, 0x10                   ; base 0, limit 4G
    mov ds, eax
    mov es, eax
    mov ss, eax
    mov fs, eax
    mov gs, eax
    mov esp, 0x7C00

%ifdef TWICE
  %define DO_TWICE 1
  %define NONZERO_FIRST 1
%endif
%ifdef TWICEREV
  %define DO_TWICE 1
  %define NONZERO_FIRST 0
%endif
%ifdef DO_TWICE
    ; The same instruction at the same address, executed twice, with the
    ; default segment bases non-zero for one pass and zero for the other.
    ; If both passes agree, the emulator decided once -- at translation time,
    ; cached per code address -- and the first state to reach the block wins.
    ; If they differ, the decision is made per execution.
  %if NONZERO_FIRST
    mov eax, 0x28
  %else
    mov eax, 0x10
  %endif
    mov ds, eax
    mov es, eax
    mov ss, eax
    call test_insn
    mov esi, ebx                    ; first answer
  %if NONZERO_FIRST
    mov eax, 0x10
  %else
    mov eax, 0x28
  %endif
    mov ds, eax
    mov es, eax
    mov ss, eax
    call test_insn
    mov edi, ebx                    ; second answer

    mov eax, 0x10                   ; back to base 0 for reporting
    mov ds, eax
    mov es, eax
    mov ss, eax
    mov bx, si
    call classify
    shl al, 4
    mov cl, al
    mov bx, di
    call classify
    or al, cl                       ; high nibble = pass 1, low = pass 2
    mov dx, 0xF4
    out dx, al
.hang_twice:
    hlt
    jmp .hang_twice
%endif

%ifdef CTRL
    mov eax, 0x28                   ; base 0x2000
    mov ds, eax
    mov es, eax
    mov ss, eax
%endif

    ; ---------- the instruction under test ----------
%ifdef PLAIN
    ; A plain data load with the same override -- is the defect specific to
    ; `mov Sreg, m`, or does it reach every overridden reference?
    db 0x2E, 0x8B, 0x1D, 0xF8, 0x03, 0x00, 0x00   ; mov ebx, cs:[0x3F8]
%elifdef FSCS
    ; The controlled pair for PLAIN: same displacement, same *base*, same
    ; instruction shape -- only the override register differs.  Selector 0x38
    ; has base CSBASE, so the correct answer is 0x18, exactly as for PLAIN.
    mov eax, 0x38
    mov fs, eax
    db 0x64, 0x8B, 0x1D, 0xF8, 0x03, 0x00, 0x00   ; mov ebx, fs:[0x3F8]
%elifdef FSTEST
    ; A non-CS override with a non-zero base, while DS/ES/SS stay at base 0.
    ; The correct answer here is 0x30 (the word at FS.base + 0x3F8 = 0x23F8).
    mov eax, 0x28
    mov fs, eax
    db 0x64, 0x8B, 0x1D, 0xF8, 0x03, 0x00, 0x00   ; mov ebx, fs:[0x3F8]
%else
    db 0x2E, 0x8E, 0x1D, 0xF8, 0x03, 0x00, 0x00   ; mov ds, word cs:[0x3F8]
    mov bx, ds                      ; what did it load?
%endif
    ; ------------------------------------------------

    mov eax, 0x10
    mov es, eax                     ; base 0 again, for the VGA write

    mov al, 4
    cmp bx, 0x18
    jne .not18
    mov al, 1
.not18:
    cmp bx, 0x20
    jne .not20
    mov al, 2
.not20:
    cmp bx, 0x30
    jne .not30
    mov al, 3
.not30:
    push eax

    ; "DS=xx" on the text screen, so the run is readable even without the
    ; exit device -- a silent exit code and a blank screen look identical.
    mov edi, 0xB8000
    mov ah, 0x0F
    mov al, 'D'
    mov [es:edi], ax
    mov al, 'S'
    mov [es:edi + 2], ax
    mov al, '='
    mov [es:edi + 4], ax
    mov edx, ebx
    shr edx, 4
    and edx, 0x0F
    call hexdigit
    mov [es:edi + 6], ax
    mov edx, ebx
    and edx, 0x0F
    call hexdigit
    mov [es:edi + 8], ax

    pop eax
    mov dx, 0xF4
    out dx, al
.hang:
    hlt
    jmp .hang

test_insn:                           ; the load under test, as a callable
    db 0x2E, 0x8B, 0x1D, 0xF8, 0x03, 0x00, 0x00   ; mov ebx, cs:[0x3F8]
    ret

classify:                            ; bx -> al in {1,2,3,4}
    mov al, 4
    cmp bx, 0x18
    jne .c1
    mov al, 1
    ret
.c1:
    cmp bx, 0x20
    jne .c2
    mov al, 2
    ret
.c2:
    cmp bx, 0x30
    jne .c3
    mov al, 3
.c3:
    ret

hexdigit:                            ; dl -> al ascii, ah preserved
    mov al, dl
    add al, '0'
    cmp al, '9'
    jbe .done
    add al, 'A' - '0' - 10
.done:
    ret

%macro GDT_ENTRY 4                   ; base, limit, access, flags
    dw (%2) & 0xFFFF
    dw (%1) & 0xFFFF
    db ((%1) >> 16) & 0xFF
    db (%3)
    db (((%2) >> 16) & 0x0F) | (((%4) << 4) & 0xF0)
    db ((%1) >> 24) & 0xFF
%endmacro

align 8
gdt:
    dq 0
    GDT_ENTRY CSBASE, 0xFFFFF, 0x9A, 0xC    ; 0x08 code32, non-zero base
    GDT_ENTRY 0,      0xFFFFF, 0x92, 0xC    ; 0x10 data, base 0
    GDT_ENTRY 0,      0xFFFFF, 0x92, 0xC    ; 0x18 data, "CS base" answer
    GDT_ENTRY 0,      0xFFFFF, 0x92, 0xC    ; 0x20 data, "zero base" answer
    GDT_ENTRY DSBASE, 0xFFFFF, 0x92, 0xC    ; 0x28 data, base 0x2000
    GDT_ENTRY 0,      0xFFFFF, 0x92, 0xC    ; 0x30 data, "DS base" answer
    GDT_ENTRY CSBASE, 0xFFFFF, 0x92, 0xC    ; 0x38 data, base == CSBASE
gdt_end:

gdtr:
    dw gdt_end - gdt - 1
    dd gdt

    times 510 - ($ - $$) db 0
    dw 0xAA55
