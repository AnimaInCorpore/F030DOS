; WC1 68030 <-> DSP56001 C2P wire protocol.
;
; 24-bit words are transported through the Falcon DSP host port. A command
; then a sequence word precede each 320-pixel scanline; 107 packed source
; words follow. The DSP replies with a distinct opcode, echoes the sequence,
; and returns 107 packed destination words. The first worker revision echoes
; scanline payloads to prove ordering/flow control before it is allowed to
; replace the byte-exact 68030 C2P oracle.

C2P_PROTOCOL_VERSION    EQU     1
C2P_CMD_PING            EQU     $574350 ; "WCP"
C2P_CMD_LOOPBACK        EQU     $57434C ; "WCL"
C2P_CMD_SCANLINE        EQU     $574331 ; "WC1"
C2P_REPLY_HELLO         EQU     $435032 ; "CP2"
C2P_REPLY_SCANLINE      EQU     $435031 ; "CP1"
C2P_REPLY_BAD_COMMAND   EQU     $424144 ; "BAD"

C2P_SCREEN_WIDTH        EQU     320
C2P_SCREEN_HEIGHT       EQU     200
C2P_DSP_WORD_BYTES      EQU     3
C2P_SCANLINE_WORDS      EQU     107
C2P_SCANLINE_PAD_BYTES  EQU     1
