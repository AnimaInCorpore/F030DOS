/*
 * The player's damage and death chain, from the DOS flight handler.
 *
 * FUN_00018D20/FUN_00018F94 spend most of their length on a helicopter that is
 * still flying; this module is the rest of it: what a hit does to the eight
 * damage cells [00019E38..3F] and the hull [00019E40], how a wreck is flown
 * until the flight ends, and what a damaged engine or tail rotor does to the
 * controls. The functions are pure transcriptions over one explicit state
 * object (below), deterministic given its fields, and return the requests the
 * original makes of other subsystems (the end of the flight, the chase view,
 * a wreck puff, sounds) as data instead of calling them.
 *
 * The shake RNG [00019DB8] is the PIT-driven pseudo-random source of
 * analysis/functions/browser-attract.md#shake-timer: it advances on a
 * wall-clock timer, so it is an INPUT here (`rng`), never advanced by these
 * functions except by the explicit stir the original performs at 00019492 and
 * 000194B2. Sound is outside the first playable scope and is returned only as
 * a request list.
 *
 * State (DOS address, width):
 *   cells         [00019E38..3F] eight bytes: tail rotor, engine, targeting
 *                 cell [00019E3A], [00019E3C], the gun [00019E3D], ...
 *   hullPoints    [00019E40] signed dword; negative means the hull is gone
 *   deathCue      [00019E49] byte: 1 once the hull went negative
 *   deathTimer    [00019E48] byte: counts down from 0x64 while deathCue is set
 *   axis1, axis2  [00019DC8], [00019DCC] signed dwords: the stick
 *   collective    [00019D82] byte
 *   altitude      [00019DFC] byte
 *   maxSpeed      [00019CCC] dword, the forward speed ceiling
 *   shakeCountdown[00019DC0] dword
 *   viewVariant   [00019D86] byte
 *   crashDrop     [00019DC4] dword: how far the wreck's screen has sunk
 *   rng           [00019DB8] dword: the PIT-driven shake RNG (input)
 *   x, y          [00019CD4], [00019CD8] signed dwords, 10.22
 *   frameX, frameY, previousAltitude  [00019CDC], [00019CE0], [00019DF6]
 *   fwd, lat      [00019CC8], [00019CD0] signed dwords
 *   torque        [00019D84] byte, the T gauge
 */
// Target artefact; record: analysis/functions/browser-attract.md#player-damage-chain
(() => {
  "use strict";

  // DOS: FUN_00018F94 [00018EE3-00018F93]; record: analysis/functions/browser-attract.md#player-damage-chain
  // 32-bit signed view of a dword.
  const i32 = (value) => value | 0;

  // DOS: FUN_00018F94 [00018EE3-00018F93]; record: analysis/functions/browser-attract.md#player-damage-chain
  // The death block. Nothing happens until [00019E49] is set. Then the wreck's
  // countdown [00019E48] drops by that byte each tick (00018EF0 sub byte) and
  // when it reaches zero the flight ends (00018EF6 je 0002873D). Meanwhile the
  // stick is zeroed (00018EFC, 00018F06). With the hull still non-negative
  // (00018F10-00018F17: a hit on the wingman's side, a bomb) the collective is
  // held at 0xFE, the helicopter climbs 4 a tick while its altitude is 0xFA or
  // less, and once it reaches 0xE6 the speed stick is pulled to -0x15E
  // (0xFFFFFEA2) - a sink onto the ground nose-up. With the hull negative the
  // collective is zero (the rotor has stopped), the shake counts ten
  // (00018F4C), the cockpit view's screen sinks 0x52 a tick (00018F5F) and at
  // 0xE6A the chase view takes over (00018F66-00018F70: a call to 00019820,
  // the key-7 case, and sound 0x0B), and every sixteenth RNG phase
  // ([00019DB8] & 0xF == 0) a wreck puff is made from the fixed object, slot
  // 0x1F (00018F7E-00018F8F, 000227BF). Returns the requests it made.
  function deathBlock(state) {
    const requests = { missionEnd: false, chaseView: false, wreckFromSlot: 0, sounds: [] };
    if ((state.deathCue & 0xff) === 0) return requests;      // 00018EE3-00018EEA
    state.deathTimer = (state.deathTimer - state.deathCue) & 0xff;   // 00018EF0
    if (state.deathTimer === 0) {                            // 00018EF6
      requests.missionEnd = true;
      return requests;
    }
    state.axis1 = 0;                                         // 00018EFC
    state.axis2 = 0;                                         // 00018F06
    if (i32(state.hullPoints) >= 0) {                        // 00018F10-00018F17
      state.collective = 0xfe;                               // 00018F19
      if (state.altitude <= 0xfa) state.altitude = (state.altitude + 4) & 0xff;   // 00018F20-00018F29
      if (state.altitude >= 0xe6) state.axis2 = i32(0xfffffea2);   // 00018F30-00018F39
      return requests;                                       // 00018F43 jmp 00018F94
    }
    state.collective = 0;                                    // 00018F45
    state.shakeCountdown = 10;                               // 00018F4C
    if ((state.viewVariant & 0xff) === 1) {                  // 00018F56-00018F5D
      state.crashDrop = (state.crashDrop + 0x52) >>> 0;      // 00018F5F
      if (state.crashDrop >= 0xe6a) {                        // 00018F66-00018F70 jb
        requests.chaseView = true;                           // 00018F72 call 00019820
        requests.sounds.push(0x0b);                          // 00018F77-00018F79 call 00004E2E
      }
    }
    if ((state.rng & 0xf) === 0) requests.wreckFromSlot = 0x1f;   // 00018F7E-00018F8F
    return requests;
  }

  // DOS: FUN_00018F94 [00018F94-00018FB6]; record: analysis/functions/browser-attract.md#player-damage-chain
  // A damaged engine (cell [00019E39] negative) sinks the helicopter one unit
  // a tick while its altitude is above 10 and caps its forward speed at
  // 0x800000 on those ticks (00018F9D-00018FAD). The cap stays until a repair
  // or a new mission restores 0x1800000 (00026B65, 000063EC).
  function engineDamage(state) {
    if ((state.cells[1] & 0x80) === 0) return;               // 00018F94-00018F9B jns
    if (state.altitude <= 0x0a) return;                      // 00018F9D-00018FA4 jbe
    state.altitude = (state.altitude - 1) & 0xff;            // 00018FA6
    state.maxSpeed = 0x800000;                               // 00018FAD
  }

  // DOS: FUN_00018F94 [00018FB7-00019002]; record: analysis/functions/browser-attract.md#player-damage-chain
  // The T gauge [00019D84]: the speed stick sar 5 one's-complemented when
  // negative (cdq / xor eax, edx), plus three times the collective, clamped to
  // 0xC8 on an unsigned compare, halved by `shr al, 1` while the engine cell is
  // negative. 00018FE7-00019002 then turns it into the engine pitch word
  // [00004186] = min(torque << 8, 0x8000) + 0x4000, returned as `enginePitch`
  // (an audio register; not carried further). Returns both.
  function torqueGauge(state) {
    const stick = i32(state.axis2) >> 5;                     // 00018FC1-00018FC6
    let eax = (stick ^ (stick >> 31)) >>> 0;                 // 00018FC9-00018FCA cdq / xor eax, edx
    eax = (eax + ((state.collective & 0xff) * 3)) >>> 0;    // 00018FB7-00018FCC lea ebx, [ebx + ebx*2]
    let al = eax & 0xff;
    if (eax >= 0xc8) al = 0xc8;                              // 00018FCE-00018FD5
    if ((state.cells[1] & 0x80) !== 0) al >>= 1;             // 00018FD7-00018FE0 shr al, 1
    state.torque = al;                                       // 00018FE2
    let pitch = al << 8;                                     // 00018FE7-00018FEE
    if (pitch > 0x8000) pitch = 0x8000;                      // 00018FF1-00018FF8
    return { torque: al, enginePitch: pitch + 0x4000 };      // 00018FFD-00019002
  }

  // DOS: FUN_00018F94 [000190AB-000190B4]; record: analysis/functions/browser-attract.md#player-damage-chain
  // A damaged tail rotor (cell [00019E38] negative) adds a constant yaw of
  // 0x600000 to the turn rate before the clamp at 000190BE.
  function tailRotorYaw(state) {
    return (state.cells[0] & 0x80) !== 0 ? 0x600000 : 0;     // 000190AB-000190B4
  }

  // DOS: FUN_00018F94 [000192EE-0001934F]; record: analysis/functions/browser-attract.md#player-damage-chain
  // The collision test against the thirty mission objects, slot 0x1E down to 1
  // (000192EE ebx = 0x1E, 0001934F dec / jne). Slot `n` collides when it is
  // active (000192F3), its altitude [00021A25 + n] is within the 9-bit half
  // difference of `sub al; rcr al, 1; cbw; xor al, ah` of 0xF (000192FC-0001930F:
  // the carry of the subtraction is the sign), both |x - x_n| and |y - y_n|
  // (one's-complemented, cdq / xor) are at most 0x1400000 (00019311-0001933B)
  // and its state routine is not the explosion's 000237B0 (0001933D-00019348).
  // `objects[n]` is { active, altitude, x, y, state } for n = 1..30 (x, y are
  // the 10.22 dwords [00020C6C + 4n], [00020E74 + 4n]). Returns the colliding
  // slot or 0; the first one found, scanning down, takes the 00019424 crash.
  function objectCollision(state, objects) {
    for (let slot = 0x1e; slot >= 1; slot -= 1) {
      const object = objects[slot];
      if (!object || (object.active & 0xff) === 0) continue; // 000192F3-000192FA
      const difference = (state.altitude & 0xff) - (object.altitude & 0xff);   // 000192FC-00019301 sub al
      const borrow = difference < 0 ? 1 : 0;
      let al = ((difference & 0xff) >> 1) | (borrow << 7);   // 00019307 rcr al, 1
      al ^= (al & 0x80) ? 0xff : 0;                          // 00019309-0001930B cbw / xor al, ah
      if (al > 0x0f) continue;                               // 0001930D-0001930F
      const dx = i32(state.x - object.x);                    // 00019311-00019316
      if (((dx ^ (dx >> 31)) >>> 0) > 0x1400000) continue;   // 00019320-00019325
      const dy = i32(state.y - object.y);                    // 00019327-0001932C
      if (((dy ^ (dy >> 31)) >>> 0) > 0x1400000) continue;   // 00019336-0001933B
      if (object.state === 0x237b0) continue;                // 0001933D-00019348
      return slot;                                           // 0001934A jmp 00019424
    }
    return 0;
  }

  // DOS: FUN_00018F94 [00019424-000194D0]; record: analysis/functions/browser-attract.md#player-damage-chain
  // The crash response, for ground contact (00019382 ja) and for an object
  // alike. The frame-start position and the previous altitude are restored
  // (00019424-0001943D). A wreck (deathCue set) goes no further
  // (00019442-00019449). Otherwise the lateral and forward speeds are negated
  // and the forward one halved (0001944F-0001945B sar), ten ticks of shake are
  // armed (00019461), the altitude gains 4 saturating at 0xFF (0001946B-00019474),
  // and the hit is paid for (0001947B-000194D0):
  //   a sound, 2 + (rng & 3), when (rng & 3) < 2 (0001947B-00019488)
  //   rng += x                                   (00019492, the restored x)
  //   cells[(byte & 7)]--  and  cells[byte >> 5]--, byte = low byte of rng
  //                                               (00019498-000194AC, bytes wrap)
  //   rng = ror(rng, 8)                           (000194B2)
  //   hullPoints -= rng & 3, and a negative result sets deathCue (000194B9-000194C9)
  //   a second sound through 00004E8E             (000194D0-000194DB)
  // The RNG is the wall-clock source: `rng` is read as given. Returns
  // { crashed: true, sounds }.
  function crashResponse(state) {
    const sounds = [];
    state.x = i32(state.frameX);                             // 00019424-00019429
    state.y = i32(state.frameY);                             // 0001942E-00019433
    state.altitude = state.previousAltitude & 0xff;          // 00019438-0001943D
    if ((state.deathCue & 0xff) !== 0) return { crashed: true, sounds };   // 00019442-00019449
    state.lat = i32(-state.lat);                             // 0001944F neg
    state.fwd = i32(-state.fwd);                             // 00019455 neg
    state.fwd >>= 1;                                         // 0001945B sar
    state.shakeCountdown = 10;                               // 00019461
    state.altitude = Math.min(0xff, state.altitude + 4);     // 0001946B-00019474
    const low = state.rng & 3;                               // 0001947B-00019482
    if (low < 2) sounds.push(low + 2);                       // 00019484-00019488 call 00004E2E
    state.rng = (state.rng + state.x) >>> 0;                 // 0001948D-00019492
    const byte = state.rng & 0xff;                           // 00019498-0001949F
    state.cells[byte & 7] = (state.cells[byte & 7] - 1) & 0xff;   // 000194A1-000194A3
    state.cells[byte >> 5] = (state.cells[byte >> 5] - 1) & 0xff; // 000194A9-000194AC
    state.rng = ((state.rng >>> 8) | (state.rng << 24)) >>> 0;     // 000194B2 ror 8
    state.hullPoints = i32(state.hullPoints - (state.rng & 3));    // 000194B9-000194C1
    if (state.hullPoints < 0) state.deathCue = 1;            // 000194C7-000194C9
    sounds.push(0xff);                                       // 000194D0-000194DB call 00004E8E
    return { crashed: true, sounds };
  }

  // DOS: FUN_00026AB6 [00026B49-00026B87]; record: analysis/functions/browser-attract.md#player-damage-chain
  // The options menu's All Damage Repaired (key code 0x40): the hull
  // [00019E40] takes the mission's [00019E44] (00026B4D-00026B52), the wreck's
  // countdown becomes 0x64 and the cue clears (00026B57-00026B5E), the speed
  // ceiling returns to 0x1800000 (00026B65) and every damage cell is 0x0A
  // (00026B6F-00026B7B rep stosb). The message of 00026A6C is shown.
  function repairAll(state, hullMax) {
    state.hullPoints = i32(hullMax);                         // 00026B4D-00026B52
    state.deathTimer = 0x64;                                 // 00026B57
    state.deathCue = 0;                                      // 00026B5E
    state.maxSpeed = 0x1800000;                              // 00026B65
    state.cells.fill(0x0a);                                  // 00026B6F-00026B7B
  }

  globalThis.ComancheDamage = {
    deathBlock,
    engineDamage,
    torqueGauge,
    tailRotorYaw,
    objectCollision,
    crashResponse,
    repairAll,
  };
})();
