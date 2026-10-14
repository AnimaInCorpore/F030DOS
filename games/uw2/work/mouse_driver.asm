; Minimal INT 33h mouse driver for the DOS oracle.
;
; UW2.EXE calls exactly three INT 33h subfunctions (verified by exhaustive
; search of the Ghidra disassembly, analysis/qemu-boot.md): AX=0 (reset /
; detect), AX=3 (get position + button status), AX=0Bh (read motion
; counters). Nothing else is implemented; unrecognised AX chains to whatever
; vector was resident before us.
;
; Polls the 8042 auxiliary (PS/2 mouse) port directly instead of hooking
; IRQ12 -- no PIC reprogramming, so it cannot destabilise DOS's own keyboard
; handling even if something here is wrong. Register contract verified
; against stanislavs.org/helppc/int_33-{0,3,b}.html; 8042 port protocol
; against stanislavs.org/helppc/8042.html plus the standard PS/2 mouse
; packet format (utoronto.ca "PS/2 Mouse Interfacing").
;
; Build: nasm -f bin work/mouse_driver.asm -o mouse_driver.com

                bits    16
                org     0x100

start:
                jmp     install

; -----------------------------------------------------------------------
; INT 33h handler. DS is switched to CS on entry so the data below is
; addressable regardless of the caller's DS; every exit path restores it.
; -----------------------------------------------------------------------
int33_handler:
                push    ds
                push    cs
                pop     ds

                cmp     ax, 0
                je      .fn_reset
                cmp     ax, 3
                je      .fn_getpos
                cmp     ax, 0x0b
                je      .fn_getmotion
                pop     ds
                jmp     far [cs:old33]          ; not ours -- chain

.fn_reset:
                call    drain_aux
                mov     word [pos_x], 320
                mov     word [pos_y], 100
                mov     word [mickey_x], 0
                mov     word [mickey_y], 0
                mov     byte [buttons], 0
                pop     ds
                mov     ax, 0xffff              ; "mouse driver installed"
                mov     bx, 2                   ; button count
                iret

.fn_getpos:
                call    drain_aux
                mov     cx, [pos_x]
                mov     dx, [pos_y]
                xor     bh, bh
                mov     bl, [buttons]
                pop     ds
                iret

.fn_getmotion:
                call    drain_aux
                mov     cx, [mickey_x]
                mov     dx, [mickey_y]
                mov     word [mickey_x], 0      ; "since last call" -- clear on read
                mov     word [mickey_y], 0
                pop     ds
                iret

; -----------------------------------------------------------------------
; Drain every byte currently sitting in the 8042 output buffer. Status
; bit 0 = something is there, bit 5 = it came from the aux device rather
; than the keyboard -- leave keyboard bytes untouched for the normal IRQ1
; path instead of swallowing them. DS must already be CS.
; -----------------------------------------------------------------------
drain_aux:
                push    ax
.loop:
                in      al, 0x64
                test    al, 1
                jz      .done                   ; nothing pending
                test    al, 0x20
                jz      .done                   ; keyboard's byte, not ours
                in      al, 0x60
                call    feed_packet_byte
                jmp     .loop
.done:
                pop     ax
                ret

; AL = next raw aux byte. Resyncs on byte 1's framing bit (always 1) so a
; dropped/extra byte cannot permanently misalign the 3-byte packet.
feed_packet_byte:
                push    bx
                mov     bl, [pkt_idx]
                cmp     bl, 0
                jne     .b1
                test    al, 0x08                ; framing bit
                jz      .out                    ; out of sync -- discard, stay at 0
                mov     [pkt_b1], al
                mov     byte [pkt_idx], 1
                jmp     .out
.b1:
                cmp     bl, 1
                jne     .b2
                mov     [pkt_dx], al
                mov     byte [pkt_idx], 2
                jmp     .out
.b2:
                mov     [pkt_dy], al
                mov     byte [pkt_idx], 0
                call    apply_packet
.out:
                pop     bx
                ret

apply_packet:
                push    ax
                push    dx
                mov     al, [pkt_b1]
                and     al, 0x07                ; left/right/middle == INT33h BX bits 0-2
                mov     [buttons], al

                ; signed X delta: sign lives in pkt_b1 bit 4
                xor     ah, ah
                mov     al, [pkt_dx]
                test    byte [pkt_b1], 0x10
                jz      .xpos
                sub     ax, 256
.xpos:
                add     [mickey_x], ax
                add     [pos_x], ax
                call    clamp_x

                ; signed Y delta: sign lives in pkt_b1 bit 5. Hardware
                ; Y+ means "moved away/up"; INT33h/screen Y+ means "down" --
                ; negate once here so both accumulators use screen sense.
                xor     ah, ah
                mov     al, [pkt_dy]
                test    byte [pkt_b1], 0x20
                jz      .ypos
                sub     ax, 256
.ypos:
                neg     ax
                add     [mickey_y], ax
                add     [pos_y], ax
                call    clamp_y

                pop     dx
                pop     ax
                ret

clamp_x:
                cmp     word [pos_x], 0
                jge     .notneg
                mov     word [pos_x], 0
.notneg:
                cmp     word [pos_x], 639
                jle     .notbig
                mov     word [pos_x], 639
.notbig:
                ret

clamp_y:
                cmp     word [pos_y], 0
                jge     .notneg
                mov     word [pos_y], 0
.notneg:
                cmp     word [pos_y], 199
                jle     .notbig
                mov     word [pos_y], 199
.notbig:
                ret

; -----------------------------------------------------------------------
; Install: bring up the 8042 aux port, hook INT 33h, log every phase to
; stdout (redirected to BOOT.LOG by AUTOEXEC.BAT) so a hang or a wrong
; turn is diagnosable instead of just silent, then TSR.
; -----------------------------------------------------------------------
install:
                mov     ax, cs
                mov     ds, ax
                mov     es, ax

                mov     dx, msg_start
                call    print_msg

                call    wait_input_clear
                mov     al, 0xa8                ; enable auxiliary device
                out     0x64, al

                mov     dx, msg_aux_on
                call    print_msg

                call    wait_input_clear
                mov     al, 0xd4                ; next data byte -> aux device
                out     0x64, al
                call    wait_input_clear
                mov     al, 0xf4                ; enable data reporting
                out     0x60, al

                mov     cx, 0xffff              ; bounded wait for the 0xFA ack --
.wait_ack:                                      ; never spin forever on a bad guess
                in      al, 0x64
                test    al, 1
                jz      .ack_retry
                test    al, 0x20
                jz      .ack_retry
                in      al, 0x60                ; consume the ack byte
                jmp     .ack_done
.ack_retry:
                loop    .wait_ack
.ack_done:
                mov     dx, msg_ack
                call    print_msg

                mov     ax, 0x3533              ; AH=35h get vector, AL=33h
                int     0x21
                mov     [old33+0], bx
                mov     [old33+2], es
                push    ds
                mov     dx, int33_handler
                mov     ax, cs
                mov     ds, ax
                mov     ax, 0x2533              ; AH=25h set vector, AL=33h
                int     0x21
                pop     ds

                mov     dx, msg_installed
                call    print_msg

                mov     dx, (resident_end - start + 15) / 16 + 0x10  ; + PSP paragraphs
                mov     ax, 0x3100
                int     0x21                    ; terminate and stay resident

wait_input_clear:
                in      al, 0x64
                test    al, 2
                jnz     wait_input_clear
                ret

print_msg:                                      ; DX = $-terminated string
                mov     ah, 9
                int     0x21
                ret

old33           dd      0
pkt_idx         db      0
pkt_b1          db      0
pkt_dx          db      0
pkt_dy          db      0
buttons         db      0
pos_x           dw      320
pos_y           dw      100
mickey_x        dw      0
mickey_y        dw      0

msg_start       db      'MOUSE33: enabling 8042 aux port...', 13, 10, '$'
msg_aux_on      db      'MOUSE33: aux port enabled, arming stream mode...', 13, 10, '$'
msg_ack         db      'MOUSE33: stream-mode ack seen (or timed out).', 13, 10, '$'
msg_installed   db      'MOUSE33: INT 33h hooked, resident.', 13, 10, '$'

resident_end:
