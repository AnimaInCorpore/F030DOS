bits 16
org 0
%define rn_al 0
%define rn_cl 1
%define rn_dl 2
%define rn_bl 3
%define rn_ax 0
%define rn_cx 1
%define rn_dx 2
%define rn_bx 3
%define rn_sp 4
%define rn_bp 5
%define rn_si 6
%define rn_di 7
%macro mov_rr 2
        db 0x8b, 0xc0 | ((rn_ %+ %1) << 3) | (rn_ %+ %2)
%endmacro
%macro xor_rr 2
        db 0x33, 0xc0 | ((rn_ %+ %1) << 3) | (rn_ %+ %2)
%endmacro
%macro or_rr 2
        db 0x0b, 0xc0 | ((rn_ %+ %1) << 3) | (rn_ %+ %2)
%endmacro
%macro mov_rr8 2
        db 0x8a, 0xc0 | ((rn_ %+ %1) << 3) | (rn_ %+ %2)
%endmacro
        mov_rr bp, sp
        xor_rr ax, ax
        or_rr  ax, ax
        mov_rr ax, si
        mov_rr sp, bp
        mov_rr8 al, bl
