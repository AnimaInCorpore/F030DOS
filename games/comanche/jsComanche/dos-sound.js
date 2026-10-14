/*
 * The DOS sound driver: MS3 music and FM effects, as the original's register
 * writes.
 *
 * This is the music/FM half of Comanche's audio, flat 0002B9CF-0002C4A0. It is
 * one driver with five devices behind a table of seven routines each, selected
 * by command 3: 1 PC speaker, 2 Sound Blaster FM and 3 AdLib (the same OPL2
 * routines), 4 Roland MPU-401 (UART mode), 5 none. Its only outputs are port
 * writes - OPL2 register pairs through 0002C1B8, MPU-401 bytes through 0002BF88
 * and 0002BFD9 - and the music is driven by one call per timer interrupt
 * (00001D2C: `call [0002C48C]`, the PIT at 0x47B4 = 65.0 Hz).
 *
 * The module is a function-level transcription over ONE memory image: the
 * flat image's own bytes, 0 .. 00032B20, with the driver's variables and its
 * constant tables at the addresses the listing uses, plus the song buffers the
 * caller places above it. Keeping the DOS addresses means the aliasing the
 * original has (a channel nibble above 9 indexes past a ten-byte array into
 * the next one) is reproduced rather than guarded against. The registers are
 * explicit, because the original relies on them: a routine's result is often
 * whatever its callee left in AH (see `tick`, the effect expiry).
 *
 * The device and the world are INPUTS, never invented:
 *   - the tick is the caller's `tick()` call; there is no clock in here;
 *   - the OPL status the detection reads (0002C20D, 0002C236) comes from
 *     `hooks.oplStatus()`, the MPU-401's acknowledge byte from
 *     `hooks.mpuAck()`, the PC speaker's port 0x61 from `hooks.port61()`;
 *   - the delay-loop calibration [00001C8E] (only the MPU time-out [0002D161]
 *     depends on it) from `options.delayLoops`.
 *
 * Writes are collected as arrays: ["o", register, value] OPL2,
 * ["m", byte] MPU-401 data port 0x330, ["c", byte] MPU-401 command port 0x331,
 * ["p", port, value] the PC speaker's ports 0x43/0x42/0x61. This is the form
 * work/trace_sound_writes.py captures from the running original.
 *
 * The digital effect layer (00004E26-00004F6D, 000050B4, the mixer fill at
 * 00005220) is the second half of the module: three 8-bit sample slots mixed
 * into a 0x800-byte half of the Sound Blaster's double buffer by `fill()`.
 * Its "write stream" is that buffer. `effect()` is the FM redirect inside
 * 00004E8E (`mov eax, ebp; jmp 0002B9CF` when [00019DF9] is zero);
 * `digitalEffect()` is the digital branch of the same routine.
 */
// Target artefact; record: analysis/functions/browser-attract.md#sound-driver-module
(() => {
  "use strict";

  const FLAT_END = 0x32B20;          // end of the image's flat content region
  const ENTRY_COMMAND = 0x2B9CF;
  const TICK_ENTRY = 0x2BBF2;
  const RET_STUB = 0x2B9F6;          // the "no device" routine: a bare ret

  // Variables (flat addresses), named by what the listing does with them.
  const V = {
    tickVector: 0x2C48C,     // dword: what the timer ISR calls
    cursor: 0x2C490,         // dword: the next event of the song
    song: 0x2C494,           // dword: the song being played (0 = none)
    queued: 0x2C498,         // dword: the song queued behind it
    flags: 0x2C49C,          // byte: flags the song was started with
    queuedFlags: 0x2C49D,    // byte
    playing: 0x2C49E,        // byte: 0xFF while a song runs
    paused: 0x2C49F,         // byte: 0xFF while paused
    command: 0x2C4A0,        // word: the AX the last command was given
    countdown: 0x2C4A2,      // word: ticks to the next event
    note: 0x2C4A4,           // 16 bytes: last note per MIDI channel (written, never read)
    link: 0x2C4B4,           // 10 bytes: channel doubling (from song+0x10)
    songPatch: 0x2C4C4,      // 10 bytes: the song's patch per channel (song+0x20)
    loaded: 0x2C4D4,         // 10 bytes: the patch loaded on the channel (0xFF none)
    envPtr: 0x2C4E8,         // 10 dwords: cursor in the patch's pitch envelope
    envStart: 0x2C528,       // 10 dwords: start of that envelope
    pitchOffset: 0x2C568,    // 10 bytes: the E events' value
    baseNote: 0x2C578,       // 10 bytes: the note last keyed on (plus transpose)
    sentNote: 0x2C588,       // 10 bytes: the pitch last sent (0xFF = none)
    transpose: 0x2C598,      // 10 bytes
    master: 0x2C5A8,         // byte: music volume (command 7)
    scale: 0x2C5A9,          // 10 bytes: patch volume scale
    keyOn: 0x2C5B9,          // 10 bytes
    voice: 0x2C5C9,          // 10 bytes: effect time left (non-zero = the channel is an effect's)
    cmdTable: 0x2C5D9,
    voiceOrder: 0x2C619,     // 8 bytes per device: the channels an effect may take
    device: 0x2C4E4,
    fxBase: 0x2D404,         // dword: which half of an effect's entry is being played
    fxTable: 0x2D408,
    oplModLevel: 0x2D10D,    // 9 bytes: the patch's byte 1 per voice
    oplShadow: 0x2D116,      // 9 bytes: the B0 register's value per voice
    oplOp1: 0x2D11F,         // 9 bytes: offset of the first operator (the modulator in FM mode)
    oplOp2: 0x2D128,         // 9 bytes: offset of the second operator (the carrier)
    oplVoiceOf: 0x2D131,     // 16 bytes: music channel -> OPL voice (>= 9 none)
    mpuChannelOf: 0x2D141,   // 16 bytes: music channel -> MIDI channel (0 none)
    mpuNote: 0x2D151,        // 16 bytes
    mpuTimeout: 0x2D161,     // word
    mpuInit: 0x2D163,        // the MT-32 display SysEx
    mpuProgram: 0x2D183,     // program map
    speakerWords: 0x2D203,
    transposeTable: 0x2D4D0,
    scaleTable: 0x2D550,
    defaultEnv: 0x2D5D0,
    envTable: 0x2D5E6,
    patches: 0x2C70D,
    fnum: 0x2CF0D,
  };
  const DELAY_LOOPS = 0x1C8E;
  const TABLE_SLOTS = [0x2C649, 0x2C665, 0x2C681, 0x2C69D, 0x2C6B9, 0x2C6D5, 0x2C6F1];
  const T = { init: 0, end: 1, silence: 2, note: 3, pitch: 4, patch: 5, detect: 6 };

  // Target artefact; record: analysis/functions/browser-attract.md#sound-driver-module
  class Machine {
    // Target artefact; record: analysis/functions/browser-attract.md#sound-driver-module
    constructor(image, options = {}) {
      if (image.length < FLAT_END) throw new Error("sound driver: the image must cover the flat region");
      this.ram = Uint8Array.from(image.subarray(0, FLAT_END));
      this.songs = [];
      this.openBusReads = 0;
      this.writes = [];
      this.beforeWrite = null;
      this.beforeStore = null;
      this.hooks = options.hooks || {};
      if (options.digitalFlag !== undefined) this.ram[0x19DF9] = options.digitalFlag;
      this.eax = 0; this.ebx = 0; this.ecx = 0; this.edx = 0;
      this.esi = 0; this.edi = 0; this.ebp = 0;
      this.stack = [];
      if (options.delayLoops !== undefined) this.w16(DELAY_LOOPS, options.delayLoops);
      // The game's own start-up adds [00019E70] = 0x40000 to 256 dwords at 0002D7F0
      // (000055E8-00005602). The driver reads them only through patch 255, which every
      // one-voice FM effect loads for its second, empty half: the envelope pointer table
      // at 0002D5E6 + 4*255 lands in them (0x61800004 once relocated, 0x61800000 before). The
      // second half's channel is taken again by the effect's first half, so the pointer is
      // only read by a tick that arrives between the two. It is an option because a capture
      // that restores the image's bytes has none.
      if (options.relocateTable) {
        for (let at = 0x2D7F0; at < 0x2D7F0 + 0x400; at += 4) this.w32(at, (this.r32(at) + 0x40000) >>> 0);
      }
    }

    // Target artefact; record: analysis/functions/browser-attract.md#sound-driver-module
    r8(address) {
      if (this.beforeStore) this.beforeStore();
      address >>>= 0;
      if (address < FLAT_END) return this.ram[address];
      for (const song of this.songs) {
        if (address >= song.base && address < song.base + song.bytes.length) return song.bytes[address - song.base];
      }
      // Memory the machine does not have reads as 0x00 (open bus; what QEMU's 16 MB PC returns,
      // measured by calling `mov al, [addr]` in the guest for 0x61800000, 0x61800004, 0x01000000,
      // 0x80000000, 0xFFFF0000, and what the original's tick reads through the wild envelope
      // pointer of patch 255, see #sound-driver-effects). Counted so a caller can tell.
      this.openBusReads += 1;
      return 0x00;
    }

    // Target artefact; record: analysis/functions/browser-attract.md#sound-driver-module
    w8(address, value) {
      if (this.beforeStore) this.beforeStore();
      address >>>= 0;
      if (address >= FLAT_END) throw new Error(`sound driver: write outside the image ${address.toString(16)}`);
      this.ram[address] = value & 0xFF;
    }

    // Target artefact; record: analysis/functions/browser-attract.md#sound-driver-module
    r16(address) { return this.r8(address) | (this.r8(address + 1) << 8); }

    // Target artefact; record: analysis/functions/browser-attract.md#sound-driver-module
    w16(address, value) { this.w8(address, value); this.w8(address + 1, value >>> 8); }

    // Target artefact; record: analysis/functions/browser-attract.md#sound-driver-module
    r32(address) {
      return (this.r8(address) | (this.r8(address + 1) << 8) | (this.r8(address + 2) << 16)
        | (this.r8(address + 3) << 24)) >>> 0;
    }

    // Target artefact; record: analysis/functions/browser-attract.md#sound-driver-module
    w32(address, value) {
      this.w8(address, value); this.w8(address + 1, value >>> 8);
      this.w8(address + 2, value >>> 16); this.w8(address + 3, value >>> 24);
    }

    // Target artefact; record: analysis/functions/browser-attract.md#sound-driver-module
    push(name) { this.stack.push(this[name]); }

    // Target artefact; record: analysis/functions/browser-attract.md#sound-driver-module
    pop(name) { this[name] = this.stack.pop(); }
  }

  // The 8- and 16-bit register views x86 code uses: [name, shift, mask, register].
  const VIEWS = [
    ["al", 0, 0xFF, "eax"], ["ah", 8, 0xFF, "eax"], ["ax", 0, 0xFFFF, "eax"],
    ["bl", 0, 0xFF, "ebx"], ["bh", 8, 0xFF, "ebx"], ["bx", 0, 0xFFFF, "ebx"],
    ["cl", 0, 0xFF, "ecx"], ["ch", 8, 0xFF, "ecx"], ["cx", 0, 0xFFFF, "ecx"],
    ["dl", 0, 0xFF, "edx"], ["dh", 8, 0xFF, "edx"], ["dx", 0, 0xFFFF, "edx"],
  ];
  for (const [name, shift, mask, register] of VIEWS) {
    Object.defineProperty(Machine.prototype, name, {
      // Target artefact; record: analysis/functions/browser-attract.md#sound-driver-module
      get() { return (this[register] >>> shift) & mask; },
      // Target artefact; record: analysis/functions/browser-attract.md#sound-driver-module
      set(value) {
        this[register] = ((this[register] & ~(mask << shift)) | ((value & mask) << shift)) >>> 0;
      },
    });
  }

  // Target artefact; record: analysis/functions/browser-attract.md#sound-driver-module
  function create(image, options = {}) {
    const m = new Machine(image, options);

    // ---- the ports ---------------------------------------------------------
    // Target artefact; record: analysis/functions/browser-attract.md#sound-driver-module
    // Every port write of every device: collected for the caller. `m.beforeWrite`, when set,
    // runs first: it is how a test harness lets a timer interrupt arrive between two writes
    // of a driver call (see `interrupt`).
    function emit(entry) {
      if (m.beforeWrite) m.beforeWrite();
      m.writes.push(entry);
    }

    // DOS: FUN_0002C1B8 [0002C1B8-0002C1E9]; record: analysis/functions/browser-attract.md#sound-driver-opl
    // The OPL2 register write: AH = register to port 0x388, AL = value to 0x389,
    // each followed by a calibrated delay (no effect on the stream). Preserves
    // ECX, EDX and the high half of EAX; AX is NOT preserved: the delay loops
    // after the data write (0002C1DB-0002C1E3) count AX down from [00001C8E],
    // so the helper returns with AX = 0 (`mov ax, [1C8E]; dec ax; jne` ends at 0).
    // Callers that read AH after a table-3 call (the tick's effect expiry) see 0.
    function opl() { emit(["o", m.ah, m.al]); m.ax = 0; }

    // DOS: FUN_0002BF88 [0002BF88-0002BFA9]; record: analysis/functions/browser-attract.md#sound-driver-mpu
    // One byte to the MPU-401 data port 0x330 once port 0x331 bit 6 reads clear.
    function mpuData() { emit(["m", m.al]); }

    // DOS: FUN_0002BFD9 [0002BFD9-0002C01C]; record: analysis/functions/browser-attract.md#sound-driver-mpu
    // One byte to the command port 0x331 and the wait for the acknowledge on the
    // data port: returns the byte read (0xFE for a reset acknowledge) in AL.
    function mpuCommand() {
      emit(["c", m.al]);
      m.al = m.hooks.mpuAck ? m.hooks.mpuAck() : 0xFE;
    }

    // DOS: FUN_0002BFAA [0002BFAA]; record: analysis/functions/browser-attract.md#sound-driver-mpu
    // A bare `ret`. The four-instruction routine at 0002BFAB (the command write
    // without the ack wait) is not reached: every caller goes to 0002BFAA, so the
    // 0xD0 / 0xDF prefixes of the MPU-401's intelligent mode are never sent.
    function mpuPrefix() { /* ret */ }

    // ---- OPL2 device (devices 2 and 3) -------------------------------------
    // DOS: FUN_0002C254 [0002C254-0002C311]; record: analysis/functions/browser-attract.md#sound-driver-opl
    // Table 5 for the OPL2: load patch AL on music channel CH. The patch is 16
    // bytes at 0002C70D + 16*AL: bytes 0 2 3 4 to the operator at [0002D128]'s
    // offset, bytes 5 (6 inverted) 7 8 9 to the one at [0002D11F]'s, byte 10 to
    // the voice's C0 register, byte 1 is remembered for the key-on's level.
    function oplPatch() {
      m.ebx = m.ch;
      m.ch = m.r8(V.oplVoiceOf + m.ebx);
      if (m.ch >= 9) return;
      m.ebx = ((m.al << 4) + V.patches) >>> 0;
      m.esi = m.ch;
      m.dh = m.r8(V.oplOp2 + m.esi);
      m.dl = m.r8(V.oplOp1 + m.esi);
      m.al = m.r8(V.oplShadow + m.esi) & 0xDF;
      m.ah = 0xB0 | m.ch; opl();
      m.al = m.r8(m.ebx); m.ah = 0x20 | m.dh; opl();
      m.al = m.r8(m.ebx + 2); m.ah = 0x60 | m.dh; opl();
      m.al = m.r8(m.ebx + 3); m.ah = 0x80 | m.dh; opl();
      m.al = m.r8(m.ebx + 4); m.ah = 0xE0 | m.dh; opl();
      m.al = m.r8(m.ebx + 5); m.ah = 0x20 | m.dl; opl();
      m.al = m.r8(m.ebx + 6); m.ah = 0x40 | m.dl; m.al ^= 0x3F; opl();
      m.al = m.r8(m.ebx + 7); m.ah = 0x60 | m.dl; opl();
      m.al = m.r8(m.ebx + 8); m.ah = 0x80 | m.dl; opl();
      m.al = m.r8(m.ebx + 9); m.ah = 0xE0 | m.dl; opl();
      m.al = m.r8(m.ebx + 10); m.ah = 0xC0 | m.ch; opl();
      m.al = m.r8(m.ebx + 1);
      m.w8(V.oplModLevel + m.esi, m.al);
    }

    // DOS: FUN_0002C354 [0002C354-0002C37E]; record: analysis/functions/browser-attract.md#sound-driver-opl
    // Table 2 for the OPL2: for each of the nine voices, total level 0x3F on the
    // operator at [0002D128] and the B0 register cleared (key off).
    function oplSilence() {
      m.ecx = 9;
      m.dh = 0;
      do {
        m.ebx = m.dh;
        m.dl = m.r8(V.oplOp2 + m.ebx);
        m.ah = 0x40 | m.dl; m.al = 0x3F; opl();
        m.ax = 0xB000; m.ah |= m.dh; opl();
        m.dh = (m.dh + 1) & 0xFF;
        m.ecx = (m.ecx - 1) >>> 0;
      } while (m.ecx !== 0);
    }

    // DOS: FUN_0002C312 [0002C312-0002C353]; record: analysis/functions/browser-attract.md#sound-driver-opl
    // Table 0 for the OPL2: waveform select on (reg 01 = 20), reg 08 = 0, reg BD =
    // C0 (deep AM and vibrato), all voices silenced, then patch 0 on every channel
    // 0..8 after setting each voice's B0 shadow to 1F. Returns AL = 0xFF.
    function oplInit() {
      m.ax = 0x0120; opl();
      m.ax = 0x0800; opl();
      m.ax = 0xBDC0; opl();
      oplSilence();
      m.ecx = 9;
      m.ebx = 0;
      do {
        m.push("ecx"); m.push("ebx");
        m.al = 0x1F; m.w8(V.oplShadow + m.ebx, m.al);
        m.al = 0;
        m.ch = m.bl;
        oplPatch();
        m.pop("ebx"); m.pop("ecx");
        m.ebx = (m.ebx + 1) >>> 0;
        m.ecx = (m.ecx - 1) >>> 0;
      } while (m.ecx !== 0);
      m.al = 0xFF;
    }

    // DOS: FUN_0002C380 [0002C380-0002C3C8]; record: analysis/functions/browser-attract.md#sound-driver-opl
    // Table 4 for the OPL2: set the pitch of channel CH to note index AH (twice the
    // semitone). The word at 0002CF0D + 2*AH is the F-number and block; the
    // key-on bit of the B0 shadow is kept. A0 gets the low byte, B0 the rest.
    function oplPitch() {
      m.ebx = m.ch;
      m.ch = m.r8(V.oplVoiceOf + m.ebx);
      if (m.ch >= 9) return;
      m.esi = m.ch;
      m.ebx = ((m.ah << 1) + V.fnum) >>> 0;
      m.ax = m.r16(m.ebx);
      m.bl = m.r8(V.oplShadow + m.esi) & 0xE0;
      m.ah |= m.bl;
      m.w8(V.oplShadow + m.esi, m.ah);
      m.ah = 0xA0 | m.ch; opl();
      m.al = m.r8(V.oplShadow + m.esi);
      m.ah = 0xB0 | m.ch; opl();
    }

    // DOS: FUN_0002C3C9 [0002C3C9-0002C431]; record: analysis/functions/browser-attract.md#sound-driver-opl
    // Table 3 for the OPL2, entered with EBX = the music channel: key on (AH != 0,
    // CL = velocity) or off (AH = 0). The level written to the operator at
    // [0002D128]'s offset is (patch byte 1 or (CL/4 + 0x20, at most 0x3F)) xor
    // 0x3F; then B0 with the key bit set or cleared. AH is left at 0xB0 or voice.
    function oplNote() {
      m.ch = m.r8(V.oplVoiceOf + m.ebx);
      if (m.ch >= 9) return;
      m.esi = m.ch;
      m.dh = m.r8(V.oplOp2 + m.esi);
      if (m.ah === 0) {
        m.al = m.r8(V.oplShadow + m.esi) & 0xDF;
        m.w8(V.oplShadow + m.esi, m.al);
        m.ah = 0xB0 | m.ch; opl();
        return;
      }
      m.cl = (m.cl >>> 2) & 0xFF;
      m.cl = (m.cl + 0x20) & 0xFF;
      if (!(m.cl < 0x3F)) m.cl = 0x3F;
      m.al = m.r8(V.oplModLevel + m.esi);
      m.ah = 0x40 | m.dh;
      m.al |= m.cl;
      m.al ^= 0x3F;
      opl();
      m.al = m.r8(V.oplShadow + m.esi) | 0x20;
      m.w8(V.oplShadow + m.esi, m.al);
      m.ah = 0xB0 | m.ch; opl();
    }

    // DOS: FUN_0002C1EA [0002C1EA-0002C253]; record: analysis/functions/browser-attract.md#sound-driver-opl
    // Table 6 for the OPL2: is an OPL2 there? Reset both timers (reg 04 = 60 then
    // 80), read the status (BH = status and E0), set timer 1 (reg 02 = FF, reg 04
    // = 21), wait, read the status again (BL = (status and E0) xor C0), reset the
    // timers. AL = 0xFF when BH or BL is zero, else 0. The two status reads are
    // the card's, from hooks.oplStatus().
    function oplDetect() {
      m.ax = 0x0460; opl();
      m.ax = 0x0480; opl();
      m.bh = (m.hooks.oplStatus() & 0xE0);
      m.ax = 0x02FF; opl();
      m.ax = 0x0421; opl();
      m.bl = ((m.hooks.oplStatus() & 0xE0) ^ 0xC0);
      m.ax = 0x0460; opl();
      m.ax = 0x0480; opl();
      m.bh |= m.bl;
      m.al = (m.bh === 0) ? 0xFF : 0;
    }

    // ---- MPU-401 device (device 4, UART mode) ------------------------------
    // DOS: FUN_0002C01E [0002C01E-0002C07C]; record: analysis/functions/browser-attract.md#sound-driver-mpu
    // Table 3 for the MPU-401, EBX = music channel: note on (AH = twice the note,
    // CL = velocity capped at 0x7F) as 9n note vel, or off (AH = 0) as 8n note 40
    // with the note remembered from the on. Channels with [0002D141] = 0 are mute.
    function mpuNote() {
      m.ch = m.r8(V.mpuChannelOf + m.ebx);
      if (m.ch === 0) return;
      if (m.ah === 0) {
        mpuPrefix();
        m.al = m.ch | 0x80; mpuData();
        m.al = m.r8(V.mpuNote + m.ebx); mpuData();
        m.al = 0x40; mpuData();
        return;
      }
      m.ah >>>= 1;
      m.w8(V.mpuNote + m.ebx, m.ah);
      mpuPrefix();
      m.al = m.ch | 0x90; mpuData();
      m.al = m.ah; mpuData();
      m.al = m.cl;
      if (!(m.cl <= 0x7F)) m.al = 0x7F;
      mpuData();
    }

    // DOS: FUN_0002C07D [0002C07D-0002C0C9]; record: analysis/functions/browser-attract.md#sound-driver-mpu
    // Table 4 for the MPU-401: pitch as a pitch-bend. With the note the channel
    // was keyed with at [0002C578]: bend = (AH - base + 0x18) * 0xAA * 4, sent as
    // En low7 high7.
    function mpuPitch() {
      m.ebx = m.ch;
      m.ch = m.r8(V.mpuChannelOf + m.ebx);
      if (m.ch === 0) return;
      m.ah = (m.ah - m.r8(V.baseNote + m.ebx)) & 0xFF;
      m.ah = (m.ah + 0x18) & 0xFF;
      m.al = m.ah;
      m.ah = 0;
      m.cl = 0xAA;
      m.ax = (m.al * m.cl) & 0xFFFF;
      m.ax = (m.ax << 1) & 0xFFFF;
      m.dl = m.al & 0x7F;
      m.ax = (m.ax << 1) & 0xFFFF;
      m.dh = m.ah & 0x7F;
      mpuPrefix();
      m.al = 0xE0 | m.ch; mpuData();
      m.al = m.dl; mpuData();
      m.al = m.dh; mpuData();
    }

    // DOS: FUN_0002C0CA [0002C0CA-0002C0F9]; record: analysis/functions/browser-attract.md#sound-driver-mpu
    // Table 5 for the MPU-401: patch AL on channel CH as the program change Cn
    // (map[AL] - 1), the map at 0002D183.
    function mpuPatch() {
      m.ebx = m.al;
      m.cl = m.r8(V.mpuProgram + m.ebx);
      m.cl = (m.cl - 1) & 0xFF;
      m.ebx = m.ch;
      m.ch = m.r8(V.mpuChannelOf + m.ebx);
      if (m.ch === 0) return;
      mpuPrefix();
      m.al = 0xC0 | m.ch; mpuData();
      m.al = m.cl; mpuData();
    }

    // DOS: FUN_0002C135 [0002C135-0002C189]; record: analysis/functions/browser-attract.md#sound-driver-mpu
    // Table 0 for the MPU-401 (the tail of table 2 falls into it): set the
    // time-out [0002D161] = [00001C8E] << 5, send the Roland MT-32 display
    // SysEx at 0002D163 (a bare 0xFC resets the running checksum in CH, 0xFD is
    // replaced by it, 0xFF ends the list), then the UART-mode command 0x3F with
    // its acknowledge. AL = the acknowledge.
    function mpuInit() {
      m.cx = (m.r16(DELAY_LOOPS) << 5) & 0xFFFF;
      m.w16(V.mpuTimeout, m.cx);
      m.al = 0xDF; mpuPrefix();
      m.ebx = 0;
      for (;;) {
        m.al = m.r8(V.mpuInit + m.ebx);
        if (m.al === 0xFF) break;
        if (m.al === 0xFD) {
          m.ch &= 0x7F;
          m.ch = (-m.ch) & 0xFF;
          m.ch &= 0x7F;
          m.al = m.ch;
        } else if (m.al === 0xFC) {
          m.ch = 0;
          m.ebx = (m.ebx + 1) >>> 0;
          continue;
        }
        m.ch = (m.ch + m.al) & 0xFF;
        mpuData();
        m.ebx = (m.ebx + 1) >>> 0;
      }
      m.al = 0xFF;
      m.al = 0x3F;
      mpuCommand();
    }

    // DOS: FUN_0002C0FA [0002C0FA-0002C134]; record: analysis/functions/browser-attract.md#sound-driver-mpu
    // Table 2 for the MPU-401: control change 7B 00 (all notes off) on the sixteen
    // MIDI channels, 0xBF first; then it falls through into table 0's body.
    function mpuSilence() {
      m.al = 0xB9; mpuPrefix();
      m.al = 0xB9; mpuPrefix();
      m.ecx = 0x10;
      do {
        m.push("ecx");
        m.al = 0xD0; mpuPrefix();
        m.pop("ecx");
        m.al = (0xB0 + m.cl) & 0xFF;
        m.al = (m.al - 1) & 0xFF;
        m.push("ecx");
        mpuData();
        m.al = 0x7B; mpuData();
        m.al = 0; mpuData();
        m.pop("ecx");
        m.ecx = (m.ecx - 1) >>> 0;
      } while (m.ecx !== 0);
      mpuInit();
    }

    // DOS: FUN_0002C18A [0002C18A-0002C1B7]; record: analysis/functions/browser-attract.md#sound-driver-mpu
    // Table 6 for the MPU-401: reset (command 0xFF) and expect the acknowledge
    // 0xFE, twice if the first does not answer. AL = 0xFF or 0.
    function mpuDetect() {
      m.cx = (m.r16(DELAY_LOOPS) << 5) & 0xFFFF;
      m.w16(V.mpuTimeout, m.cx);
      m.al = 0xFF; mpuCommand();
      if (m.al === 0xFE) { m.al = 0xFF; return; }
      m.al = 0xFF; mpuCommand();
      m.al = (m.al === 0xFE) ? 0xFF : 0;
    }

    // ---- PC speaker (device 1) and the empty devices -----------------------
    // DOS: FUN_0002C432 [0002C432-0002C43A]; record: analysis/functions/browser-attract.md#sound-driver-speaker
    // Table 0 for the speaker: gate off (port 0x61 bit 1 cleared). AL = 0xFF.
    function speakerInit() {
      const value = (m.hooks.port61 ? m.hooks.port61() : 0) & 0xFD;
      emit(["p", 0x61, value]);
      m.al = 0xFF;
    }

    // DOS: FUN_0002C43C [0002C43C-0002C442]; record: analysis/functions/browser-attract.md#sound-driver-speaker
    // Table 2 for the speaker: gate off.
    function speakerSilence() {
      const value = (m.hooks.port61 ? m.hooks.port61() : 0) & 0xFD;
      emit(["p", 0x61, value]);
    }

    // DOS: FUN_0002C45F [0002C45F-0002C47D]; record: analysis/functions/browser-attract.md#sound-driver-speaker
    // Table 4 for the speaker: channel 0 only; PIT channel 2 (mode 3) is loaded
    // with the word at 0002D203 + 2*AH.
    function speakerPitch() {
      if (m.ch >= 1) return;
      m.ebx = m.ah;
      m.al = 0xB6; emit(["p", 0x43, 0xB6]);
      m.ax = m.r16(V.speakerWords + 2 * m.ebx);
      emit(["p", 0x42, m.al]);
      m.al = m.ah;
      emit(["p", 0x42, m.al]);
    }

    // DOS: FUN_0002C443 [0002C443-0002C45E]; record: analysis/functions/browser-attract.md#sound-driver-speaker
    // Table 3 for the speaker: note on (AH != 0) sets the pitch and the gate
    // bits 0 and 1 of port 0x61, off clears bit 1.
    function speakerNote() {
      if (m.ch >= 1) return;
      const port61 = m.hooks.port61 ? m.hooks.port61() : 0;
      if (m.ah !== 0) {
        speakerPitch();
        emit(["p", 0x61, (port61 | 3) & 0xFF]);
      } else {
        emit(["p", 0x61, port61 & 0xFD]);
      }
    }

    // DOS: FUN_0002B9F6 [0002B9F6]; record: analysis/functions/browser-attract.md#sound-driver-core
    // The routine every empty table slot points at: a bare `ret`. (The empty device
    // 5's own slots, 0002C485-0002C48A, are `ret` too, and its detect at 0002C482
    // clears AH.)
    function noop() { /* ret */ }

    // DOS: FUN_0002C482 [0002C482-0002C484]; record: analysis/functions/browser-attract.md#sound-driver-core
    // Table 6 of the empty device: `xor ah, ah; ret` - AL is left as the caller's.
    function noneDetect() { m.ah = 0; }

    // DOS: FUN_0002C47F [0002C47F-0002C481]; record: analysis/functions/browser-attract.md#sound-driver-speaker
    // Table 6 of the speaker: always present.
    function speakerDetect() { m.al = 0xFF; }

    const CODE = new Map([
      [0x2B9F6, noop], [0x2C43B, noop], [0x2C47E, noop], [0x2C485, noop], [0x2C486, noop],
      [0x2C487, noop], [0x2C488, noop], [0x2C489, noop], [0x2C48A, noop], [0x2C37F, noop],
      [0x2C01D, noop],
      [0x2C432, speakerInit], [0x2C43C, speakerSilence], [0x2C443, speakerNote],
      [0x2C45F, speakerPitch], [0x2C47F, speakerDetect],
      [0x2C312, oplInit], [0x2C354, oplSilence], [0x2C3C9, oplNote], [0x2C380, oplPitch],
      [0x2C254, oplPatch], [0x2C1EA, oplDetect],
      [0x2C135, mpuInit], [0x2C0FA, mpuSilence], [0x2C01E, mpuNote], [0x2C07D, mpuPitch],
      [0x2C0CA, mpuPatch], [0x2C18A, mpuDetect], [0x2C482, noneDetect],
    ]);

    // Target artefact; record: analysis/functions/browser-attract.md#sound-driver-core
    // An indirect call or jump in the original: the code address held in a table
    // slot, resolved to the transcribed routine.
    function callSlot(slot) {
      const address = m.r32(slot);
      const routine = CODE.get(address);
      if (!routine) throw new Error(`sound driver: no routine for code address ${address.toString(16)} (slot ${slot.toString(16)})`);
      routine();
    }

    // ---- the music core ----------------------------------------------------
    // DOS: FUN_0002BC8B [0002BC8B-0002BCE9]; record: analysis/functions/browser-attract.md#sound-driver-core
    // Key a channel: CH = channel, AH = note (0 = off), CL = velocity. Paused or
    // AH = 0 is a key-off. Otherwise the velocity is scaled by the patch's scale
    // (0002C5A9) and the music volume (0002C5A8): hi = scale*master >> 8,
    // CL = ((hi + 1) * (CL << 1)) >> 8; the channel's pitch-envelope cursor is
    // rewound, the key state set, the transposed note (AH + [0002C598]) saved as
    // the base note and [0002C588] invalidated (so the next tick sends the pitch).
    function keyChannel() {
      m.ebx = m.ch;
      if (m.r8(V.paused) !== 0 || m.ah === 0) {
        m.ah = 0;
        m.w8(V.keyOn + m.ebx, m.ah);
        callSlot(TABLE_SLOTS[T.note]);
        return;
      }
      m.push("eax");
      m.al = m.r8(V.scale + m.ebx);
      m.ax = (m.al * m.r8(V.master)) & 0xFFFF;
      m.cl = (m.cl << 1) & 0xFF;
      m.ah = (m.ah + 1) & 0xFF;
      m.al = m.ah;
      m.ax = (m.al * m.cl) & 0xFFFF;
      m.cl = m.ah;
      m.eax = m.r32(V.envStart + m.ebx * 4);
      m.w32(V.envPtr + m.ebx * 4, m.eax);
      m.w8(V.keyOn + m.ebx, 1);
      m.pop("eax");
      m.ah = (m.ah + m.r8(V.transpose + m.ebx)) & 0xFF;
      m.w8(V.baseNote + m.ebx, m.ah);
      m.w8(V.sentNote + m.ebx, 0xFF);
      callSlot(TABLE_SLOTS[T.note]);
    }

    // DOS: FUN_0002BF3A [0002BF3A-0002BF87]; record: analysis/functions/browser-attract.md#sound-driver-core
    // Make AL the song's patch for channel CH ([0002C4C4]) and load it. The
    // second entry (0002BF43) loads without recording: [0002C4D4] = AL, the
    // patch's pitch envelope pointer (0002D5E6) to both cursors, its scale
    // (0002D550) and transpose (0002D4D0), then table 5.
    function loadPatch(record) {
      m.ebx = m.ch;
      if (record) m.w8(V.songPatch + m.ebx, m.al);
      m.ebx = m.ch;
      m.eax = m.al;
      m.w8(V.loaded + m.ebx, m.al);
      m.edx = m.r32(V.envTable + m.eax * 4);
      m.w32(V.envStart + m.ebx * 4, m.edx);
      m.w32(V.envPtr + m.ebx * 4, m.edx);
      m.dl = m.r8(V.scaleTable + m.eax);
      m.w8(V.scale + m.ebx, m.dl);
      m.dl = m.r8(V.transposeTable + m.eax);
      m.w8(V.transpose + m.ebx, m.dl);
      m.al = m.r8(V.loaded + m.ebx);
      callSlot(TABLE_SLOTS[T.patch]);
    }

    // DOS: FUN_0002BF12 [0002BF12-0002BF39]; record: analysis/functions/browser-attract.md#sound-driver-core
    // Silence the music: for channels 0..9 clear the pitch offset and, unless the
    // channel is an effect's, key it off.
    function silence() {
      m.ebx = 0;
      m.ch = 0;
      do {
        m.ah = 0;
        m.w8(V.pitchOffset + m.ebx, m.ah);
        if (m.r8(V.voice + m.ebx) === m.ah) {
          m.cl = 0;
          m.push("ecx"); m.push("ebx");
          keyChannel();
          m.pop("ebx"); m.pop("ecx");
        }
        m.ch = (m.ch + 1) & 0xFF;
        m.ebx = (m.ebx + 1) >>> 0;
      } while (m.ch < 0x0A);
    }

    // DOS: FUN_0002BEDC [0002BEDC-0002BEEF]; record: analysis/functions/browser-attract.md#sound-driver-core
    // Stop the music: not playing, nothing queued, channels silenced.
    function stopMusic() {
      m.w8(V.playing, 0);
      m.w8(V.queuedFlags, 0);
      silence();
    }

    // DOS: FUN_0002BD00 [0002BD00-0002BD74]; record: analysis/functions/browser-attract.md#sound-driver-core
    // Start a song: AL = flags (bit 0 queue behind a song that is playing, bit 1
    // loop), EBX = the buffer (0 ignored). The ten bytes at song+0x10 become the
    // channel links, the ten at song+0x20 the patches (loaded flags 0xFF), the
    // events start at song+0x30; the countdown is 1 so the first tick reads the
    // first event.
    function startMusic() {
      if (m.ebx === 0) return;
      if ((m.al & 1) !== 0 && m.r8(V.playing) !== 0) {
        m.w8(V.queuedFlags, m.al);
        m.w32(V.queued, m.ebx);
        return;
      }
      begin();
    }

    // DOS: FUN_0002BD00 [0002BD1D-0002BD74]; record: analysis/functions/browser-attract.md#sound-driver-core
    // The start proper (0002BD1D), also entered from the end-of-song path.
    function begin() {
      m.w8(V.flags, m.al);
      m.w32(V.song, m.ebx);
      m.esi = (m.ebx + 0x10) >>> 0;
      for (let i = 0; i < 10; i += 1) m.w8(V.link + i, m.r8(m.esi + i));
      m.esi = (m.esi + 10 + 6) >>> 0;
      for (m.ebx = 0; m.ebx < 10; m.ebx += 1) {
        m.al = m.r8(m.esi);
        m.w8(V.songPatch + m.ebx, m.al);
        m.w8(V.loaded + m.ebx, 0xFF);
        m.esi = (m.esi + 1) >>> 0;
      }
      m.esi = (m.esi + 6) >>> 0;
      m.w32(V.cursor, m.esi);
      stopMusic();
      m.w16(V.countdown, 1);
      m.w8(V.playing, 0xFF);
    }

    // DOS: FUN_0002BD75 [0002BD75-0002BE0E]; record: analysis/functions/browser-attract.md#sound-driver-ms3
    // Read the next event. AL = 0 at the end marker FF 2F. Otherwise AL = 1,
    // CH = the channel (0xFF for events that key nothing), AH = the first data
    // byte (the note; 0 for a note off), CL = the second (the velocity), DX = the
    // delay to the event after it: one byte below 0x80, or two bytes
    // ((b0 & 0x7F) << 7) | b1. Status 9n note vel; 8n; Cn program (loaded now);
    // Dn; En pitch offset; Bn p1 p2; anything else two bytes. The `inc bx` at
    // 0002BDED is a 16-bit increment.
    function readEvent() {
      m.ebx = m.r32(V.cursor);
      m.al = m.r8(m.ebx);
      m.ah = m.r8(m.ebx + 1);
      if (m.ax === 0x2FFF) { m.al = 0; return; }
      m.edx = m.ebx;
      m.ebx = m.al;
      m.bl &= 0x0F;
      m.ch = m.bl;
      m.cl = m.al;
      m.cl &= 0xF0;
      let toChannelEnd = false;
      if (m.cl === 0x90) {
        m.w8(V.note + m.ebx, m.ah);
        m.edx = (m.edx + 1) >>> 0;
      } else if (m.cl === 0x80) {
        m.ah = 0;
        m.cl = 0;
        m.w8(V.note + m.ebx, m.ah);
        m.edx = (m.edx + 1) >>> 0;
        m.ebx = m.edx;
        toChannelEnd = true;
      } else {
        if (m.cl === 0xC0) {
          m.al = m.ah;
          m.push("edx");
          loadPatch(true);
          m.pop("edx");
        } else if (m.cl === 0xE0) {
          m.w8(V.pitchOffset + m.ebx, m.ah);
        } else if (m.cl === 0xB0) {
          m.edx = (m.edx + 1) >>> 0;
        }
        m.ch = 0xFF;
      }
      if (!toChannelEnd) {
        m.ebx = (m.edx + 1) >>> 0;
        m.cl = m.r8(m.ebx);
        m.bx = (m.bx + 1) & 0xFFFF;
      }
      m.edx = m.r8(m.ebx);
      if ((m.dl & 0x80) !== 0) {
        m.dl &= 0x7F;
        m.ebx = (m.ebx + 1) >>> 0;
        m.al = m.r8(m.ebx);
        m.dh = m.dl;
        m.dl = 0;
        m.dx >>>= 1;
        m.dl |= m.al;
      }
      m.ebx = (m.ebx + 1) >>> 0;
      m.w32(V.cursor, m.ebx);
      m.al = 1;
    }

    // DOS: FUN_0002BE68 [0002BE68-0002BEDB]; record: analysis/functions/browser-attract.md#sound-driver-ms3
    // The sequencer, called by the tick while a song plays: count the delay down
    // and, at zero, play every event whose delay is zero (the loop) and arm the
    // next delay. An event on a channel that is an effect's (0002C5C9 non-zero) is
    // skipped. A channel's link byte (0002C4B4 + channel) re-plays the event on
    // the channel numbered one less. At the end of the song: silence, and the
    // queued song, else the same song again if bit 1 of its flags, else none.
    function sequencer() {
      m.w16(V.countdown, (m.r16(V.countdown) - 1) & 0xFFFF);
      if (m.r16(V.countdown) !== 0) return;
      for (;;) {
        readEvent();
        if (m.al === 0) { endOfSong(); return; }
        m.w16(V.countdown, m.dx);
        if (m.ch !== 0xFF) {
          for (;;) {
            m.ebx = m.ch;
            if (m.r8(V.voice + m.ebx) === m.bh) {
              m.w8(V.voice + m.ebx, 0);
              m.al = m.r8(V.loaded + m.ebx);
              if (m.r8(V.songPatch + m.ebx) !== m.al) {
                m.al = m.r8(V.songPatch + m.ebx);
                m.push("ecx"); m.push("eax");
                loadPatch(false);
                m.pop("eax"); m.pop("ecx");
              }
              m.push("ecx"); m.push("eax");
              m.ah = (m.ah << 1) & 0xFF;
              keyChannel();
              m.pop("eax"); m.pop("ecx");
            }
            m.ebx = m.ch;
            m.ch = m.r8(V.link + m.ebx);
            if (m.ch === 0) break;
            m.ch = (m.ch - 1) & 0xFF;
          }
        }
        if (m.r16(V.countdown) !== 0) return;
      }
    }

    // DOS: FUN_0002BE68 [0002BE0F-0002BE67]; record: analysis/functions/browser-attract.md#sound-driver-ms3
    // The end of a song (readEvent found FF 2F).
    function endOfSong() {
      m.w16(V.countdown, 1);
      silence();
      m.w8(V.playing, 0);
      if ((m.r8(V.queuedFlags) & 1) !== 0) {
        m.ebx = m.r32(V.queued);
        m.al = m.r8(V.queuedFlags);
        m.w8(V.queuedFlags, 0);
        begin();
        return;
      }
      if ((m.r8(V.flags) & 2) !== 0) {
        m.ebx = m.r32(V.song);
        m.al = m.r8(V.flags);
        begin();
        return;
      }
      m.w32(V.song, 0);
    }

    // DOS: FUN_0002BBF2 [0002BBF2-0002BC7B]; record: analysis/functions/browser-attract.md#sound-driver-core
    // The tick (installed in [0002C48C] by a successful device select, called by
    // the timer ISR at 00001D2C 65 times a second). Run the sequencer if a song
    // plays; then for channels 9 down to 0: an effect's time counts down (key off
    // when it reaches 2); the pitch is the base note plus the E-event offset plus
    // the pitch envelope's next step (0x80 holds, 0x81 loops); a changed pitch
    // goes to table 4. Ends with table 1.
    function musicTick() {
      if (m.r8(V.playing) !== 0) sequencer();
      m.ebx = 9;
      do {
        m.ah = m.r8(V.baseNote + m.ebx);
        if (m.r8(V.voice + m.ebx) !== 0) {
          m.w8(V.voice + m.ebx, (m.r8(V.voice + m.ebx) - 1) & 0xFF);
          if (m.r8(V.voice + m.ebx) === 2) {
            m.ah = 0;
            m.ch = m.bl;
            m.push("ebx");
            keyChannel();
            m.pop("ebx");
          }
        }
        m.ah = (m.ah + m.r8(V.pitchOffset + m.ebx)) & 0xFF;
        for (;;) {
          m.edx = m.r32(V.envPtr + m.ebx * 4);
          m.al = m.r8(m.edx);
          if (m.al === 0x80) break;
          if (m.al === 0x81) {
            m.edx = m.r32(V.envStart + m.ebx * 4);
            m.w32(V.envPtr + m.ebx * 4, m.edx);
            continue;
          }
          m.ah = (m.ah + m.al) & 0xFF;
          m.w32(V.envPtr + m.ebx * 4, m.r32(V.envPtr + m.ebx * 4) + 1);
          break;
        }
        m.ch = m.bl;
        if (m.r8(V.sentNote + m.ebx) !== m.ah) {
          m.w8(V.sentNote + m.ebx, m.ah);
          m.push("ebx");
          callSlot(TABLE_SLOTS[T.pitch]);
          m.pop("ebx");
        }
        m.ebx = (m.ebx - 1) >>> 0;
      } while ((m.ebx | 0) >= 0);
      callSlot(TABLE_SLOTS[T.end]);
    }

    // ---- the commands ------------------------------------------------------
    // DOS: FUN_0002BB51 [0002BB51-0002BBBA]; record: analysis/functions/browser-attract.md#sound-driver-effects
    // Play one half of effect AL: pick the first free channel from the device's
    // list (0002C619 + 8*device: for OPL 7 6 5 4 3 2 1 9; the last one taken when
    // all are busy), mark it an effect's for entry byte 0 ticks, load patch
    // (byte 1) - 1, and key it at note (byte 2) with volume (byte 3) * the
    // command's volume nibble (nibble << 4, 0xFF if zero) >> 8. The entry is
    // 0002D408 + 8*AL (+4 for the second half: [0002D404]).
    function effectHalf() {
      m.ebp = (m.r8(V.device) << 3) >>> 0;
      m.ah = 8;
      m.ebx = 0;
      for (;;) {
        m.ch = m.r8(V.voiceOrder + m.ebp);
        m.bl = m.ch;
        if (m.r8(V.keyOn + m.ebx) === 0) break;
        m.ebp = (m.ebp + 1) >>> 0;
        m.ah = (m.ah - 1) & 0xFF;
        if (m.ah === 0) break;
      }
      m.ebp = m.ebx;
      m.ebx = m.al;
      m.bx = (m.bx << 3) & 0xFFFF;
      m.ebx = (m.ebx + m.r32(V.fxBase)) >>> 0;
      m.al = m.r8(m.ebx);
      m.w8(V.voice + m.ebp, m.al);
      m.al = (m.r8(m.ebx + 1) - 1) & 0xFF;
      m.push("ecx"); m.push("ebx");
      loadPatch(false);
      m.pop("ebx"); m.pop("ecx");
      m.ax = m.r16(V.command);
      m.ah &= 0x0F;
      m.cl = 4;
      m.ah = (m.ah << 4) & 0xFF;
      if (m.ah === 0) m.ah = 0xFF;
      m.al = m.r8(m.ebx + 3);
      m.ax = (m.al * m.ah) & 0xFFFF;
      m.cl = m.ah;
      m.ah = m.r8(m.ebx + 2);
      keyChannel();
    }

    // DOS: FUN_0002BB09 [0002BB09-0002BB50]; record: analysis/functions/browser-attract.md#sound-driver-effects
    // Command 0, 1, 2: AL = effect. [0002D404] is set to the second half's
    // address (0002D40C); if the dword at 0002D40C + AL (the original indexes
    // it with AL, not 8*AL) is non-zero the second half is played first; then the
    // first half (0002D408). AL = 0xFF.
    function cmdEffect() {
      m.w32(V.fxBase, 4);
      m.w32(V.fxBase, (m.r32(V.fxBase) + V.fxTable) >>> 0);
      m.ebx = m.al;
      m.ebx = (m.ebx + m.r32(V.fxBase)) >>> 0;
      if (m.r32(m.ebx) !== 0) {
        m.push("eax");
        effectHalf();
        m.pop("eax");
      }
      m.w32(V.fxBase, 0);
      m.w32(V.fxBase, (m.r32(V.fxBase) + V.fxTable) >>> 0);
      effectHalf();
      m.al = 0xFF;
    }

    // DOS: FUN_0002B9F7 [0002B9F7-0002BB00]; record: analysis/functions/browser-attract.md#sound-driver-core
    // Command 3: select the device in AL (1..5). A device already selected is
    // shut down first (the effects' flags cleared, music silenced, table 2). Then
    // the seven table slots are copied from the new device's column, the pause
    // flag cleared and table 0 (init) called; if it returns zero the tick vector
    // is the empty routine and AL = 0. Otherwise the music is stopped, the ten
    // channels' state and cursors reset (master volume 0xFF) and the tick vector
    // set to 0002BBF2. AL = 0xFF.
    function cmdSelect() {
      m.al = m.r8(V.device);
      if (m.al !== 0) {
        for (let i = 0; i < 10; i += 1) m.w8(V.voice + i, 0);
        silence();
        callSlot(TABLE_SLOTS[T.silence]);
      }
      m.bl = m.r8(V.command);
      if (m.bl === 0 || m.bl > 5) { disable(); return; }
      m.w8(V.device, m.bl);
      m.ebx = m.bl;
      // EAX is the loaded pointer each time, so after the last copy AL is the low
      // byte of the device's detect routine - the "result" of an init that does nothing.
      for (const slot of TABLE_SLOTS) { m.eax = m.r32(slot + 4 + m.ebx * 4); m.w32(slot, m.eax); }
      m.w8(V.paused, 0);
      callSlot(TABLE_SLOTS[T.init]);
      if (m.al === 0) { disable(); return; }
      stopMusic();
      m.ebx = 0;
      m.ecx = 10;
      do {
        m.w8(V.master, 0xFF);
        m.w32(V.song, 0);
        m.w8(V.playing, 0);
        m.w8(V.sentNote + m.ebx, 0);
        m.w8(V.voice + m.ebx, 0);
        m.w8(V.keyOn + m.ebx, 0);
        m.eax = V.defaultEnv;
        m.w32(V.envPtr + m.ebx * 4, m.eax);
        m.w32(V.envStart + m.ebx * 4, m.eax);
        m.bx = (m.bx + 1) & 0xFFFF;
        m.ecx = (m.ecx - 1) >>> 0;
      } while (m.ecx !== 0);
      m.eax = TICK_ENTRY;
      m.w32(V.tickVector, m.eax);
      m.al = 0xFF;
    }

    // DOS: FUN_0002B9F7 [0002BA29-0002BA35]; record: analysis/functions/browser-attract.md#sound-driver-core
    // The failure exit of command 3: the tick vector becomes the empty routine,
    // AL = 0.
    function disable() {
      m.eax = RET_STUB;
      m.w32(V.tickVector, m.eax);
      m.al = 0;
    }

    // DOS: FUN_0002BBC1 [0002BBC1-0002BBD9]; record: analysis/functions/browser-attract.md#sound-driver-core
    // Command 4 pauses (the channels silenced, key-ons refused), 5 resumes, 6
    // asks whether a song plays (AL = [0002C49E]), 7 sets the music volume to AL.
    function cmdPause() { silence(); m.w8(V.paused, 0xFF); m.al = 0xFF; }
    // DOS: FUN_0002BBD0 [0002BBD0-0002BBDA]; record: analysis/functions/browser-attract.md#sound-driver-core
    // Command 5: resume.
    function cmdResume() { m.w8(V.paused, 0); m.al = 0xFF; }
    // DOS: FUN_0002BBBB [0002BBBB-0002BBC1]; record: analysis/functions/browser-attract.md#sound-driver-core
    // Command 6: is a song playing.
    function cmdQuery() { m.al = m.r8(V.playing); }
    // DOS: FUN_0002BB01 [0002BB01-0002BB09]; record: analysis/functions/browser-attract.md#sound-driver-core
    // Command 7: set the music volume (0002C5A8).
    function cmdVolume() { m.w8(V.master, m.al); m.al = 0xFF; }
    // DOS: FUN_0002BBDA [0002BBDA-0002BBF1]; record: analysis/functions/browser-attract.md#sound-driver-core
    // Command 8: detect device AL (table 6 of that device, not the selected one).
    function cmdDetect() {
      m.ebx = m.r8(V.command);
      if (m.bl > 5) { unsupported(); return; }
      const address = m.r32(0x2C6F5 + m.ebx * 4);
      const routine = CODE.get(address);
      if (!routine) throw new Error(`sound driver: no detect routine ${address.toString(16)}`);
      routine();
    }
    // DOS: FUN_0002B9F3 [0002B9F3-0002B9F5]; record: analysis/functions/browser-attract.md#sound-driver-core
    // Commands 9..15 and device numbers above 5 for command 8: AL = 0.
    function unsupported() { m.al = 0; }

    const COMMANDS = new Map([
      [0x2BB09, cmdEffect], [0x2B9F7, cmdSelect], [0x2BBC1, cmdPause], [0x2BBD0, cmdResume],
      [0x2BBBB, cmdQuery], [0x2BB01, cmdVolume], [0x2BBDA, cmdDetect], [0x2B9F3, unsupported],
    ]);

    // DOS: FUN_0002B9CF [0002B9CF-0002B9F2]; record: analysis/functions/browser-attract.md#sound-driver-core
    // The driver's one command entry: AX is saved at [0002C4A0], the high nibble
    // of AH indexes the dword table at 0002C5D9. Returns AL.
    function command(ax) {
      m.ax = ax & 0xFFFF;
      m.w16(V.command, m.ax);
      m.ebx = m.ah;
      m.bl = (m.bl >>> 2) & 0x3C;
      const address = m.r32(V.cmdTable + m.bl);
      const handler = COMMANDS.get(address);
      if (!handler) throw new Error(`sound driver: no handler for ${address.toString(16)}`);
      handler();
      return m.al;
    }

    // ---- the digital effect layer -------------------------------------------
    // Three slots, each with: the sample being played [0000414E+4s], its limit
    // [0000415A+4s], its step [00004142+4s] (16.16, added per output sample), its
    // position [00004166+4s] (16.16, starts at 4: the record's two header words),
    // and the next one staged [00004172+4s] with step [0000417E+4s], shift
    // [0000418D+s] and bias [0000418A+s]. A slot with the silence record 000040E2
    // is idle. The shift/bias of the playing sample are patched into the mix loop's
    // immediates (0000527A/C, 000052A4/7, 000052D0/3), which is why they live in
    // the image here.
    const SILENCE = 0x40E2;
    const SLOT = { playing: 0x414E, limit: 0x415A, step: 0x4142, position: 0x4166,
      staged: 0x4172, stagedStep: 0x417E, stagedShift: 0x418D, stagedBias: 0x418A };
    const PATCH_SHIFT = [0x527A, 0x52A4, 0x52D0];
    const PATCH_BIAS = [0x527C, 0x52A7, 0x52D3];
    const BIAS_TABLE = 0x4A02;

    // DOS: FUN_00004EA2 [00004EA2-00004F6D]; record: analysis/functions/browser-attract.md#sound-driver-digital
    // Start the sample at EAX on a slot: BL < 0x80 names it; 0xFF takes the first
    // idle slot, else the slot already playing this exact sample, else (DL = 0)
    // slot 0, else drops it; 0xFE skips the idle search. The slot's pointer, limit
    // (the record's first word), step (ECX, or the record's second word when ECX is
    // 0) and position (4.0) are set and the attenuation DL (a right shift 0..7, with
    // its bias from 0x4A02) patched into the mix loop. Returns EAX = the sample.
    function stageSample() {
      if ((m.bl & 0x80) !== 0) {
        let place = false;
        if (m.bl !== 0xFE) {
          m.ebx = 0;
          if (m.r32(0x414E) === SILENCE) place = true;
          else {
            m.bl = 1;
            if (m.r32(0x4152) === SILENCE) place = true;
            else { m.bl = 2; if (m.r32(0x4156) === SILENCE) place = true; }
          }
        }
        if (!place) {
          m.bl = 0;
          if (m.r32(0x414E) === m.eax) place = true;
          else {
            m.bl = 1;
            if (m.r32(0x4152) === m.eax) place = true;
            else { m.bl = 2; if (m.r32(0x4156) === m.eax) place = true; }
          }
          if (!place) {
            if (m.dl >= 1) return;
            m.bl = 0;
          }
        }
      }
      m.esi = m.eax;
      m.ebx = m.bl;
      m.w32(SLOT.playing + m.ebx * 4, m.esi);
      m.eax = m.r16(m.esi);
      m.w32(SLOT.limit + m.ebx * 4, m.eax);
      if (m.ecx === 0) m.ecx = m.r16(m.esi + 2);
      m.w32(SLOT.step + m.ebx * 4, m.ecx);
      m.w32(SLOT.position + m.ebx * 4, 0x40000);
      m.edx = m.dl;
      const which = m.bl < 2 ? m.bl : 2;
      m.w8(PATCH_SHIFT[which], m.dl);
      m.al = m.r8(BIAS_TABLE + m.edx);
      m.w8(PATCH_BIAS[which], m.al);
      m.eax = m.esi;
    }

    // DOS: FUN_00004E2E [00004E26-00004E86]; record: analysis/functions/browser-attract.md#sound-driver-digital
    // A speech cue: AL = id (1-based) in the bank at [00019E9C] (SPEAK1; 00004E26
    // uses [00019EA0], SPEAK0). Nothing if the bank is not loaded or slot 2 still
    // has a one-shot staged; slot 2, or 1 when slots 0 and 1 are both idle; skipped
    // if the sample is already playing on slot 0 or 1; started with DL = 0, ECX = 0.
    function speech(bankVariable) {
      m.esi = m.r32(bankVariable);
      if (m.esi === 0) return;
      m.ebx = m.r32(0x417A);
      if (m.r32(0x4156) !== m.ebx) return;
      m.bl = 2;
      if (m.r32(0x414E) === SILENCE && m.r32(0x4152) === SILENCE) m.bl = 1;
      m.push("ecx");
      m.eax = m.al;
      m.dl = 0;
      m.ecx = 0;
      m.eax = (m.r32(m.esi + m.eax * 4) + m.esi) >>> 0;
      if (m.r32(0x414E) !== m.eax && m.r32(0x4152) !== m.eax) stageSample();
      m.pop("ecx");
    }

    // DOS: FUN_00004E8E [00004E8E-00004EA0]; record: analysis/functions/browser-attract.md#sound-driver-digital
    // An effect request with the registers the callers set: EBP = id (1-based) in
    // the bank at [00019E98] (SND1), BL = slot spec, DL = attenuation, ECX = step or
    // 0. With [00019DF9] zero this is the FM driver instead (see effect()).
    function digitalEffect() {
      m.esi = m.r32(0x19E98);
      m.eax = (m.r32(m.esi + m.ebp * 4) + m.esi) >>> 0;
      stageSample();
    }

    // DOS: FUN_00004F6E [00004F6E-00004FBA]; record: analysis/functions/browser-attract.md#sound-driver-digital
    // Stage the sample at EAX as the NEXT one on slot BL: pointer, step (ECX, or the
    // record's), shift and its bias are only stored (00004F7D-00004F9A); if the
    // slot is idle (still the silence record) the sample is started now.
    function stageVoice() {
      m.esi = m.eax;
      m.ebx = m.bl;
      if (m.ecx === 0) m.ecx = m.r16(m.esi + 2);
      m.w32(SLOT.staged + m.ebx * 4, m.esi);
      m.w32(SLOT.stagedStep + m.ebx * 4, m.ecx);
      m.w8(SLOT.stagedShift + m.ebx, m.dl);
      m.edx = m.dl;
      m.al = m.r8(BIAS_TABLE + m.edx);
      m.w8(SLOT.stagedBias + m.ebx, m.al);
      m.eax = m.esi;
      if (m.r32(SLOT.playing + m.ebx * 4) === SILENCE) stageSample();
    }

    // DOS: FUN_000050B4 [000050B4-000051B6]; record: analysis/functions/browser-attract.md#sound-driver-digital
    // Reset: every slot's staged sample is the silence record (step 0, shift 0,
    // bias 0) and the playing one is replaced by it (limit 15, step 0, position 4)
    // where it was not already.
    function resetMixer() {
      for (let slot = 0; slot < 3; slot += 1) {
        m.w32(SLOT.staged + slot * 4, SILENCE);
        m.w32(SLOT.stagedStep + slot * 4, 0);
        m.w8(SLOT.stagedShift + slot, 0);
        m.w8(SLOT.stagedBias + slot, 0);
      }
      for (let slot = 0; slot < 3; slot += 1) {
        m.ebx = SILENCE;
        if (m.r32(SLOT.playing + slot * 4) === m.ebx) continue;
        m.w32(SLOT.playing + slot * 4, m.ebx);
        m.w32(SLOT.limit + slot * 4, m.r16(m.ebx));
        m.w32(SLOT.step + slot * 4, m.r32(SLOT.stagedStep + slot * 4));
        m.w32(SLOT.position + slot * 4, 0x40000);
      }
    }

    // DOS: FUN_00004E0C [00004E0C-00004E25]; record: analysis/functions/browser-attract.md#sound-driver-digital
    // Select the dither mask: AL in 0..0x11 indexes the dwords at 0x4998 into
    // [00004194].
    function setRate(al) {
      if (al > 0x11) return;
      m.w32(0x4194, m.r32(0x4998 + al * 4));
    }

    // DOS: FUN_00005220 [00005220-0000531A]; record: analysis/functions/browser-attract.md#sound-driver-digital
    // The mixer fill, run by the Sound Blaster's IRQ for each half-buffer of the
    // DMA double buffer: toggle [00004FDC] by 0x800, and for each of the 0x800
    // output bytes sum the three slots' samples (each >> its shift + its bias,
    // advanced by its step; a slot past its limit takes its staged sample first,
    // 000051C0/00005320/00005380), add the dither error of the previous pass
    // ([00004198 + (counter & mask)]), (sum + 1) >> 2 with the dropped bit rotated
    // into the table index, and look the result up in the curve table whose
    // address is the displacement at 00005307 (4C0A loud, 4A0A soft). Returns the
    // bytes written.
    function fill() {
      let edi = m.r32(0x4FDC) ^ 0x800;
      m.w32(0x4FDC, edi);
      edi = (edi + m.r32(0x4FD4)) >>> 0;
      const end = (edi + 0x800) >>> 0;
      m.w32(0x4FD8, end);
      const out = new Uint8Array(0x800);
      let n = 0;
      const steps = [m.r32(0x4142), m.r32(0x4146), m.r32(0x414A)];
      // DOS: FUN_00005220 [000051C0-00005213, 00005320-00005373, 00005380-000053D3]; record: analysis/functions/browser-attract.md#sound-driver-digital
      // 000051C0 / 00005320 / 00005380: the staged sample becomes the playing one.
      const restage = (slot) => {
        const staged = m.r32(SLOT.staged + slot * 4);
        m.w32(SLOT.limit + slot * 4, m.r16(staged));
        steps[slot] = m.r32(SLOT.stagedStep + slot * 4);
        m.w32(SLOT.step + slot * 4, steps[slot]);
        m.w8(PATCH_SHIFT[slot], m.r8(SLOT.stagedShift + slot));
        m.w8(PATCH_BIAS[slot], m.r8(SLOT.stagedBias + slot));
        m.w32(SLOT.position + slot * 4, 0x40000);
        m.w32(SLOT.playing + slot * 4, staged);
      };
      // DOS: FUN_00005220 [00005261-00005283, 00005285-000052AB, 000052B1-000052D7]; record: analysis/functions/browser-attract.md#sound-driver-digital
      // One slot's contribution: the byte at its position, >> shift, + bias (8-bit).
      const contribution = (slot) => {
        if ((m.r32(SLOT.position + slot * 4) >>> 16) >= m.r32(SLOT.limit + slot * 4)) restage(slot);
        const index = m.r32(SLOT.position + slot * 4) >>> 16;
        const value = m.r8((index + m.r32(SLOT.playing + slot * 4)) >>> 0);
        const shifted = (value >>> m.r8(PATCH_SHIFT[slot])) & 0xFF;
        const biased = (shifted + m.r8(PATCH_BIAS[slot])) & 0xFF;
        m.w32(SLOT.position + slot * 4, (m.r32(SLOT.position + slot * 4) + steps[slot]) >>> 0);
        return biased;
      };
      while (edi !== end) {
        const sum = contribution(0) + contribution(1) + contribution(2);
        const slotIndex = (m.r32(0x4190) & m.r32(0x4194)) >>> 0;
        m.w32(0x4190, (m.r32(0x4190) + 1) >>> 0);
        const total = (sum + m.r8(0x4198 + slotIndex) + 1) >>> 0;
        const carry = (total >>> 1) & 1;           // the bit `shr eax, 2` drops last
        const quarter = total >>> 2;
        m.w8(0x4198 + slotIndex, quarter);
        const index = ((quarter << 1) | carry) & 0xFFFF;   // rcl ax, 1
        out[n] = m.r8((index + m.r32(0x5307)) >>> 0);
        n += 1;
        edi = (edi + 1) >>> 0;
      }
      return out;
    }

    return {
      machine: m,
      command,
      // DOS: FUN_0002BD00 [0002BD00-0002BD74]; record: analysis/functions/browser-attract.md#sound-driver-core
      // `al` = flags, `base` = the flat address of a song that was placed with
      // placeSong(), or 0.
      start(al, base) { m.al = al; m.ebx = base >>> 0; startMusic(); },
      // DOS: FUN_0002BEDC [0002BEDC-0002BEEF]; record: analysis/functions/browser-attract.md#sound-driver-core
      stop() { stopMusic(); },
      // DOS: FUN_00001D20 [00001D2C]; record: analysis/functions/browser-attract.md#sound-driver-core
      // What the timer ISR does with the driver: `call [0002C48C]`.
      tick() {
        const address = m.r32(V.tickVector);
        if (address === TICK_ENTRY) musicTick();
        else if (address !== RET_STUB) throw new Error(`sound driver: tick vector ${address.toString(16)}`);
      },
      // DOS: FUN_00001D20 [00001D20-00001D2C]; record: analysis/functions/browser-attract.md#sound-driver-core
      // The timer ISR arriving in the middle of a driver call: it pushes EAX, EBX, ECX, EDX, ESI, EDI
      // and EBP (00001D20-00001D2B), calls the tick vector and pops them again, so the call it
      // interrupted resumes with its registers.
      interrupt() {
        const saved = [m.eax, m.ebx, m.ecx, m.edx, m.esi, m.edi, m.ebp];
        const hook = m.beforeWrite;
        const storeHook = m.beforeStore;
        m.beforeWrite = null;
        m.beforeStore = null;
        this.tick();
        m.beforeWrite = hook;
        m.beforeStore = storeHook;
        [m.eax, m.ebx, m.ecx, m.edx, m.esi, m.edi, m.ebp] = saved;
      },
      // Target artefact; record: analysis/functions/browser-attract.md#sound-driver-module
      // Test harness: `callback` runs before each port write (see `emit`), `storeCallback` before each
      // access to memory, load or store (an interrupt can arrive between any two instructions; only
      // the ones around a memory access or a port write can change what the tick then does: an
      // interrupt between a load and the store of the value it read makes the store stale).
      setBeforeWrite(callback, storeCallback = null) { m.beforeWrite = callback; m.beforeStore = storeCallback; },
      // Target artefact; record: analysis/functions/browser-attract.md#sound-driver-module
      // Test harness: the whole machine state (memory, registers, stack, pending writes, song buffers)
      // and its restoration, so a call can be run again with the interrupt arriving elsewhere.
      snapshot() {
        return { ram: Uint8Array.from(m.ram), regs: [m.eax, m.ebx, m.ecx, m.edx, m.esi, m.edi, m.ebp],
          stack: m.stack.slice(), songs: m.songs.slice(), writes: m.writes.slice(), open: m.openBusReads };
      },
      // Target artefact; record: analysis/functions/browser-attract.md#sound-driver-module
      restore(snap) {
        m.ram.set(snap.ram);
        [m.eax, m.ebx, m.ecx, m.edx, m.esi, m.edi, m.ebp] = snap.regs;
        m.stack = snap.stack.slice();
        m.songs = snap.songs.slice();
        m.writes = snap.writes.slice();
        m.openBusReads = snap.open;
      },
      // DOS: FUN_00004E8E [00004E8E-00004E96]; record: analysis/functions/browser-attract.md#sound-driver-effects
      // An effect request with [00019DF9] zero: `mov eax, ebp; jmp 0002B9CF`.
      effect(ebp) {
        if (m.r8(0x19DF9) !== 0) throw new Error("sound driver: [00019DF9] is non-zero, effects go to the digital mixer");
        return command(ebp & 0xFFFF);
      },
      // DOS: FUN_00004E8E [00004E8E-00004EA0]; record: analysis/functions/browser-attract.md#sound-driver-digital
      // The digital branch: EBP, BL, DL, ECX as the caller set them.
      fx(ebp, bl, dl, ecx) { m.ebp = ebp >>> 0; m.bl = bl; m.dl = dl; m.ecx = ecx >>> 0; digitalEffect(); },
      // DOS: FUN_00004E2E [00004E2E-00004E86]; record: analysis/functions/browser-attract.md#sound-driver-digital
      // A SPEAK1 cue.
      speechA(al) { m.eax = al; speech(0x19E9C); },
      // DOS: FUN_00004E26 [00004E26-00004E86]; record: analysis/functions/browser-attract.md#sound-driver-digital
      // A SPEAK0 cue.
      speechB(al) { m.eax = al; speech(0x19EA0); },
      // DOS: FUN_00004F6E [00004F6E-00004FBA]; record: analysis/functions/browser-attract.md#sound-driver-digital
      // Stage a sample record (flat address) on a slot.
      voice(eax, bl, dl, ecx) { m.eax = eax >>> 0; m.bl = bl; m.dl = dl; m.ecx = ecx >>> 0; stageVoice(); },
      // DOS: FUN_000050B4 [000050B4-000051B6]; record: analysis/functions/browser-attract.md#sound-driver-digital
      resetMixer() { resetMixer(); },
      // DOS: FUN_00004E0C [00004E0C-00004E25]; record: analysis/functions/browser-attract.md#sound-driver-digital
      setRate(al) { setRate(al); },
      // DOS: FUN_00005220 [00005220-0000531A]; record: analysis/functions/browser-attract.md#sound-driver-digital
      fill() { return fill(); },
      // Target artefact; record: analysis/functions/browser-attract.md#sound-driver-module
      // Overwrite bytes wherever they are (the image or a placed song): the game reuses the buffer at
      // 0002DB10 for other data while a song is still playing from it.
      pokeBytes(address, bytes) {
        for (let i = 0; i < bytes.length; i += 1) {
          const at = address + i;
          if (at < FLAT_END) { m.ram[at] = bytes[i]; continue; }
          const song = m.songs.find((x) => at >= x.base && at < x.base + x.bytes.length);
          if (song) song.bytes[at - song.base] = bytes[i];
        }
      },
      // Target artefact; record: analysis/functions/browser-attract.md#sound-driver-module
      // Set a dword / byte of the image (game variables the probe also set).
      pokeDword(address, value) { m.w32(address, value); },
      // Target artefact; record: analysis/functions/browser-attract.md#sound-driver-module
      pokeByte(address, value) { m.w8(address, value); },
      // Target artefact; record: analysis/functions/browser-attract.md#sound-driver-module
      // Put song bytes at a flat address (where the game's loader left them).
      placeSong(base, bytes) {
        // the part of the buffer inside the image (the game's loader reads MENUMUS2.MS3 and
        // OPENMUS.MS3 to 0002DF10 and 0002DB10, BSS in the file) is written into it
        let inside = 0;
        if (base < FLAT_END) {
          inside = Math.min(bytes.length, FLAT_END - base);
          m.ram.set(bytes.subarray(0, inside), base);
        }
        if (inside === bytes.length) return;
        const rest = bytes.subarray(inside);
        const at = base + inside;
        m.songs = m.songs.filter((song) => at >= song.base + song.bytes.length || at + rest.length <= song.base);
        m.songs.push({ base: at, bytes: rest });
      },
      // Target artefact; record: analysis/functions/browser-attract.md#sound-driver-module
      takeWrites() { const out = m.writes; m.writes = []; return out; },
      // Target artefact; record: analysis/functions/browser-attract.md#sound-driver-module
      read(address, count) { return Array.from(m.ram.subarray(address, address + count)); },
    };
  }

  // DOS: FUN_00015E6E [00015E6E-00015F6C]; record: analysis/functions/browser-attract.md#sound-driver-ms3
  // The music files as the game's loader leaves them in memory: 'KRL0' + dword
  // size is stored, 'KRL1' + dword size is run-length coded (0001644B: a byte
  // below 0xC0 is literal, otherwise count = byte and 0x3F and the next byte is
  // repeated count times, until `size` bytes exist), anything else (a bare .MS3,
  // read by 00015DD0) is the file. The result starts at the 'MS3-KGF' signature,
  // which is the address 0002BD00 is given.
  function decodeMusicFile(file) {
    const tag = String.fromCharCode(file[0], file[1], file[2], file[3]);
    const size = (file[4] | (file[5] << 8) | (file[6] << 16) | (file[7] << 24)) >>> 0;
    if (tag === "KRL0") return Uint8Array.from(file.subarray(8, 8 + size));
    if (tag === "KRL1") {
      const out = new Uint8Array(size);
      let written = 0;
      let at = 8;
      while (written < size) {
        const byte = file[at]; at += 1;
        if (byte < 0xC0) { out[written] = byte; written += 1; continue; }
        const count = byte & 0x3F;
        const value = file[at]; at += 1;
        for (let i = 0; i < count && written < size; i += 1) { out[written] = value; written += 1; }
      }
      return out;
    }
    return Uint8Array.from(file);
  }

  globalThis.ComancheSound = { create, decodeMusicFile, V, FLAT_END };
})();
