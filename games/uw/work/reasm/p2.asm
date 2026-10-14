bits 16
org 0
 or word [word bx+0x8], byte 0x8
 mov ax, [word bx+si+0x4]
 mov ax, [es:word bx+0x8]
 add word [word bp-0x2], byte 1
 mov al, [word bx]
