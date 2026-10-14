; Route: N/A - TOS XBIOS platform replacement.
; Source boundary: this file is active only for the traced CPU attract milestone.
;
; XBIOS 	macro definitions (c) 1994 by Sascha Springer

	macro	Gettime
	move	#23,-(a7)
	trap	#14
	addq	#2,a7
	endm

	macro	Logbase
	move	#3,-(a7)
	trap	#14
	addq	#2,a7
	endm

	macro	Physbase
	move	#2,-(a7)
	trap	#14
	addq	#2,a7
	endm

	macro	Setscreen
	move	\3,-(a7)
	pea		\2
	pea		\1
	move	#5,-(a7)
	trap	#14
	lea		12(a7),a7
	endm

	macro	Vsync
	move	#37,-(a7)
	trap	#14
	addq	#2,a7
	endm

; Falcon

	macro	Montype
	move	#89,-(a7)
	trap	#14
	addq	#2,a7
	endm

	macro	Vsetmode
	move	\1,-(a7)
	move	#88,-(a7)
	trap	#14
	addq	#4,a7
	endm

	macro	Dsp_Available
	pea		\2
	pea		\1
	move	#106,-(a7)
	trap	#14
	lea		10(a7),a7
	endm

	macro	Dsp_Reserve
	move.l	\2,-(sp)
	move.l	\1,-(sp)
	move	#107,-(sp)
	trap	#14
	lea		10(sp),sp
	endm

	macro	Dsp_LoadProgram
	pea		\3
	move	\2,-(sp)
	pea		\1
	move	#108,-(sp)
	trap	#14
	lea		12(sp),sp
	endm

	macro	Dsp_ExecProg
	move	\3,-(sp)
	move	\2,-(sp)
	pea		\1
	move	#109,-(sp)
	trap	#14
	lea		12(sp),sp
	endm

	macro	Dsp_LodToBinary
	pea		\2,-(sp)
	pea		\1,-(sp)
	move	#111,-(sp)
	trap	#14
	lea		10(sp),sp
	endm

; Falcon sound system (XBIOS 128-139). Parameter order is the C binding's;
; every macro pops its own arguments. Used by sound.s only.
	macro	Locksnd
	move	#128,-(a7)
	trap	#14
	addq	#2,a7
	endm

	macro	Unlocksnd
	move	#129,-(a7)
	trap	#14
	addq	#2,a7
	endm

	macro	Soundcmd
	move	\2,-(a7)
	move	\1,-(a7)
	move	#130,-(a7)
	trap	#14
	addq	#6,a7
	endm

	macro	Setbuffer
	move.l	\3,-(a7)
	move.l	\2,-(a7)
	move	\1,-(a7)
	move	#131,-(a7)
	trap	#14
	lea		12(a7),a7
	endm

	macro	Setmode
	move	\1,-(a7)
	move	#132,-(a7)
	trap	#14
	addq	#4,a7
	endm

	macro	Settracks
	move	\2,-(a7)
	move	\1,-(a7)
	move	#133,-(a7)
	trap	#14
	addq	#6,a7
	endm

	macro	Setmontracks
	move	\1,-(a7)
	move	#134,-(a7)
	trap	#14
	addq	#4,a7
	endm

	macro	Buffoper
	move	\1,-(a7)
	move	#136,-(a7)
	trap	#14
	addq	#4,a7
	endm

	macro	Devconnect
	move	\5,-(a7)
	move	\4,-(a7)
	move	\3,-(a7)
	move	\2,-(a7)
	move	\1,-(a7)
	move	#139,-(a7)
	trap	#14
	lea		12(a7),a7
	endm
