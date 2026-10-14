/*
 * The end of a flight and the pilot roster, from the DOS listing.
 *
 * Every function here is a pure transcription of a recovered DOS routine over
 * an explicit state object; none reads the browser, a clock or a random
 * source. DOS byte and dword semantics are kept explicit: the roster is the
 * 1,450-byte COMANCHE.NAM image at flat 00029582 and its dwords are
 * little-endian, counters are unsigned 32-bit unless the listing compares them
 * signed, and a "byte" is masked to eight bits wherever the original's
 * register is one.
 *
 * Not carried, because the route is the audio and display phase and not game
 * state: every sound call (0002B9CF, 00004FE4, 000050B4, 0002BEDC and the
 * 0002873D tail's), the stack reset at 00028748, the file write 00015D40 and
 * the screens 00028A1F/00028B37 (a host performs those from the results here).
 * The wall-clock shake RNG [00019DB8] never enters this module.
 *
 * Record: analysis/functions/browser-attract.md#mission-end-statistics,
 * #mission-end-route and #roster-ranking.
 */
// Target artefact; record: analysis/functions/browser-attract.md#mission-end-route
(() => {
  "use strict";

  // The roster image: flat 00029582, 1450 bytes (the file COMANCHE.NAM). Each
  // offset is the DOS address minus 00029582, as the Falcon's ROSTER_*
  // constants carry them.
  const ROSTER = Object.freeze({
    BASE: 0x29582,
    BYTES: 1450,           // 000288A2 / 000281F4: ebx = 0x5AA
    STRIDE: 43,            // 0x2B, 00028B69 and 00029F4E-0002A057
    PILOTS: 8,
    NAME: 9,               // 0002958B - 00029582: the name text
    NAME_CHARS: 0x16,      // 000281B3 ecx
    RANK: 0x1f,            // 000295A1 - 00029582
    CURRENT: 0x17f,        // 00029701: the selected pilot
    CAMPAIGNS: 0x180,      // 00029702: a byte a pilot, the campaign file index
    PROGRESS: 0x188,       // 0002970A: ten bytes a pilot, the mission chosen per campaign
    SELECTED: 0x1d8,       // 0002975A: the mission chosen last
    COUNT: 0x1da,          // 0002975C: a dword a pilot, missions won (the ranking key)
    SCORE: 0x1fa,          // 0002977C: a dword a pilot
    KILLS: 0x21a,          // 0002979C: a dword a pilot
    MISSIONS: 0x23a,       // 000297BC: 100 bytes a pilot, 10 campaigns x 10 missions won
    DONE: 0x55a,           // 00029ADC: ten bytes a pilot, a campaign completed
  });

  // The debrief screen image at flat 000284B1 (ComancheDOSText.debriefScreen):
  // seven 0x2F-byte sentences, then the score screen at 000285FA.
  const DEBRIEF = Object.freeze({
    BASE: 0x284b1,
    BYTES: 584,
    MESSAGE_LENGTH: 0x2f,
    SUCCESS: 0x284b1 - 0x284b1,
    ABORTED: 0x284e0 - 0x284b1,
    RUBBLE: 0x2850f - 0x284b1,
    DEFEAT: 0x2853e - 0x284b1,
    NO_WINGMAN: 0x2856d - 0x284b1,
    NO_FUEL: 0x2859c - 0x284b1,
    SETBACK: 0x285cb - 0x284b1,
    SCORE: 0x2860b - 0x284b1,
    PCT_SURVIVED: 0x28619 - 0x284b1,
    PCT_GOALS: 0x28633 - 0x284b1,
    PCT_ENEMIES: 0x28653 - 0x284b1,
    PCT_WEAPONS: 0x2866d - 0x284b1,
    PCT_FUEL: 0x28687 - 0x284b1,
    MESSAGE: 0x286a1 - 0x284b1,
  });

  // DOS: FUN_00028261 [00028261-000284B0]; record: analysis/functions/browser-attract.md#mission-end-statistics
  // Unsigned 32-bit wrap, the width of every dword the listing adds.
  const u32 = (value) => value >>> 0;

  // DOS: FUN_00028261 [00028261-000284B0]; record: analysis/functions/browser-attract.md#mission-end-statistics
  // Signed 32-bit view, for the comparisons the listing makes with jns/js.
  const s32 = (value) => value | 0;

  // DOS: FUN_00029F36 [00029F36-0002A0FE]; record: analysis/functions/browser-attract.md#roster-ranking
  // Little-endian dword read at a roster offset (the file is the DOS image).
  function rosterGet32(roster, offset) {
    return u32(roster[offset] | (roster[offset + 1] << 8) | (roster[offset + 2] << 16) | (roster[offset + 3] << 24));
  }

  // DOS: FUN_00029F36 [00029F36-0002A0FE]; record: analysis/functions/browser-attract.md#roster-ranking
  // Little-endian dword write at a roster offset.
  function rosterSet32(roster, offset, value) {
    const v = u32(value);
    roster[offset] = v & 0xff;
    roster[offset + 1] = (v >>> 8) & 0xff;
    roster[offset + 2] = (v >>> 16) & 0xff;
    roster[offset + 3] = (v >>> 24) & 0xff;
  }

  // DOS: FUN_00028C25 [00028C25-00028C3D]; record: analysis/functions/browser-attract.md#mission-end-statistics
  // The number formatter. `buffer[edi..edi+ecx)` takes the decimal digits of
  // `value` right-justified: edi moves to the last character (00028C25
  // add edi,ecx / dec edi), each pass writes `or dl,0x30` of value mod 10,
  // and the loop stops after the pass that leaves the quotient zero or when
  // ecx runs out (00028C38 je / 00028C3B loop). Characters before the first
  // digit keep what they held. `value` is the unsigned dword in eax.
  function formatNumber(buffer, edi, ecx, value) {
    let position = edi + ecx - 1;                       // 00028C25-00028C27
    let quotient = u32(value);
    let count = ecx;
    for (;;) {
      buffer[position] = 0x30 | (quotient % 10);        // 00028C2D-00028C34 xor edx,edx / div ebp / or dl,0x30
      quotient = Math.floor(quotient / 10);
      if (quotient === 0) break;                        // 00028C36-00028C38
      position -= 1;                                    // 00028C3A
      count -= 1;
      if (count === 0) break;                           // 00028C3B loop
    }
    return buffer;
  }

  // DOS: FUN_000286F9 [000286F9-0002873C]; record: analysis/functions/browser-attract.md#mission-end-statistics
  // One percentage. eax = 100 * count, the low dword of the 64-bit product
  // (000286FB-00028704 mul ebx drops edx at 00028706 xor edx,edx), divided by
  // the total unsigned (00028708 div ebp) - or left at 100 when the total is
  // zero (00028700 or ebp,ebp / 00028702 je). The result is added to the
  // running score and kept as the last percentage (0002870A-00028710), and its
  // low byte only reaches the digit divides (0002871C xor ah,ah): two blanks
  // 0xFD first, then the ones digit, then - while the quotient is non-zero -
  // the tens, then the hundreds. `acc` is { score, lastPct } ([00028258],
  // [0002825C]); `edi` is the field's first character.
  function percentField(acc, buffer, edi, total, count) {
    let percent = 100;                                   // 000286FB
    if (u32(total) !== 0) {                              // 00028700-00028702
      const product = u32(Math.imul(100, u32(count)));   // 00028704 mul ebx, eax
      percent = Math.floor(product / u32(total));        // 00028706-00028708 xor edx,edx / div ebp
    }
    acc.score = u32(acc.score + percent);                // 0002870A
    acc.lastPct = percent;                               // 00028710
    buffer[edi] = 0xfd;                                  // 00028715 mov word [edi], 0xFDFD
    buffer[edi + 1] = 0xfd;
    let al = percent & 0xff;                             // 0002871C xor ah,ah leaves ax = al
    buffer[edi + 2] = (al % 10) | 0x30;                  // 0002871E-00028723 div cl / or ah,0x30
    al = Math.floor(al / 10);
    if (al === 0) return;                                // 00028726
    buffer[edi + 1] = (al % 10) | 0x30;                  // 0002872C-00028731
    al = Math.floor(al / 10);
    if (al === 0) return;                                // 00028734
    buffer[edi] = al | 0x30;                             // 00028738-0002873A
  }

  // DOS: FUN_00028261 [00028261-000284B0]; record: analysis/functions/browser-attract.md#mission-end-statistics
  // The mission statistics. `input` is the explicit state the routine reads:
  //   fuel        [00019D60] signed dword (a negative tank is zero, 00028268)
  //   fuelMax     [00019D5C] the mission's tank
  //   hullNow     [00019E40] / hullMax [00019E44] the hull counters, each
  //               stepped up by one (00028274, 0002827A) and the first held
  //               non-negative (00028287-00028289)
  //   objects     slots 1..30: { active [00021921+n], aux [00021DB3+n],
  //               goal [00021F39+n] } as bytes
  //   targetCount [00028260] byte, the mission's enemy targets
  //   ammo        [00019D2C..40] six dwords; loadout [00019D44..58] six dwords
  //   allyWrecked [00022384] byte
  //   text        the 584-byte debrief image (ComancheDOSText.debriefScreen)
  // Returns the patched copy of the image and every counter the original
  // leaves in [0002824C-0002825C], and the three globals it stepped. The
  // input is not modified.
  function missionStatistics(input) {
    const text = Uint8Array.from(input.text);
    let fuel = s32(input.fuel);
    if (fuel < 0) fuel = 0;                                   // 00028261-0002826A
    let hullNow = u32(input.hullNow + 1);                     // 00028274 inc dword
    const hullMax = u32(input.hullMax + 1);                   // 0002827A inc dword
    if (s32(hullNow) < 0) hullNow = 0;                        // 00028280-00028289

    const acc = { score: 0, lastPct: 0 };                     // 00028293 [00028258] = 0
    let goalsTotal = 0;                                       // 0002829D [0002824D] byte
    let goals = 0;                                            // 000282A4 [0002824C] byte
    let enemiesAlive = 0;                                     // 000282AB [00028250]
    for (let slot = 0x1e; slot >= 1; slot -= 1) {             // 000282B5 ecx = 0x1E, 00028309 loop
      const object = input.objects[slot];
      const active = (object.active & 0xff) !== 0;            // 000282BA
      const aux = object.aux & 0xff;
      if (active && aux !== 9 && aux !== 6 && aux !== 3) {    // 000282C3-000282DC
        enemiesAlive = u32(enemiesAlive + 1);                 // 000282DE
      }
      if ((object.goal & 0xff) !== 0) {                       // 000282E4-000282EB
        goalsTotal = (goalsTotal + 1) & 0xff;                 // 000282ED
        if (!active) {                                        // 000282F3-000282FA
          goals = (goals + 1) & 0xff;                         // 000282FC
          acc.score = u32(acc.score + 0x64);                  // 00028302
        }
      }
    }
    const goalsDone = goalsTotal === goals ? 1 : 0;           // 0002830B-00028319 sete
    if (goalsDone) acc.score = u32(acc.score + 0x5dc);        // 0002831E-00028322

    percentField(acc, text, DEBRIEF.PCT_GOALS, goalsTotal, goals);          // 0002832C-0002833F
    percentField(acc, text, DEBRIEF.PCT_SURVIVED, hullMax, hullNow);        // 00028344-00028355
    acc.score = u32(acc.score + u32(acc.lastPct << 4));       // 0002835A-00028362 shl eax,4

    const targetCount = input.targetCount & 0xff;             // 00028368 movzx edx, byte
    const kills = u32(targetCount - enemiesAlive);            // 0002836F-00028377 [00028254]
    acc.score = u32(acc.score + u32(kills << 5));             // 0002837D-00028382
    percentField(acc, text, DEBRIEF.PCT_ENEMIES, targetCount, kills);       // 00028388-0002838D

    // DOS: FUN_00028261 [00028392-000283D8]; record: analysis/functions/browser-attract.md#mission-end-statistics
    // 00028392-000283B7 and 000283BD-000283D8: the first load counts shifted
    // down by 7 (the gun's rounds), the second by 3 (the rockets), and the
    // other four whole - for the starting loads and what is left alike.
    const weaponSum = (values) => u32(
      (u32(values[0]) >>> 7) + (u32(values[1]) >>> 3) + u32(values[2]) + u32(values[3]) + u32(values[4]) + u32(values[5]),
    );
    percentField(acc, text, DEBRIEF.PCT_WEAPONS, weaponSum(input.loadout), weaponSum(input.ammo));   // 000283E9
    percentField(acc, text, DEBRIEF.PCT_FUEL, input.fuelMax, fuel);                                   // 000283EE-000283FF

    // 00028404-00028478: the sentence. Each test overrides the one before it,
    // and esi is always set by the last of them: a standing hull sets the
    // aborted sentence (00028425) and a lost one the defeat (00028473).
    let sentence = DEBRIEF.ABORTED;
    if (goals !== 0) sentence = DEBRIEF.RUBBLE;               // 0002840E-00028417
    if (hullNow !== 0) {                                      // 0002841C-00028425
      sentence = DEBRIEF.ABORTED;
      if (fuel === 0) sentence = DEBRIEF.NO_FUEL;             // 0002842A-00028433
    }
    if (goalsDone) {                                          // 00028438-0002843F
      sentence = DEBRIEF.SUCCESS;                             // 00028441
      if ((input.allyWrecked & 0xff) !== 0) {                 // 00028446-0002844D
        sentence = DEBRIEF.NO_WINGMAN;                        // 0002844F
        acc.score = acc.score < 0x3e8 ? 0 : acc.score - 0x3e8;   // 00028454-00028460 sub / jae / mov 0
      }
    }
    if (hullNow === 0) sentence = DEBRIEF.DEFEAT;             // 0002846A-00028473
    // 00028478 rep movsb, ecx = 0x2F, from the image's own sentence to 000286A1.
    const original = input.text;
    for (let index = 0; index < DEBRIEF.MESSAGE_LENGTH; index += 1) {
      text[DEBRIEF.MESSAGE + index] = original[sentence + index];
    }
    if (hullNow === 0) acc.score = 0;                         // 0002847A-00028483
    text.fill(0xfc, DEBRIEF.SCORE, DEBRIEF.SCORE + 8);        // 0002848D-00028497
    formatNumber(text, DEBRIEF.SCORE, 8, acc.score);          // 0002849C-000284AB

    return {
      text,
      fuel,
      hullNow,
      hullMax,
      goalsTotal,                                             // [0002824D]
      goals,                                                  // [0002824C]
      goalsDone,                                              // [0002824E]
      enemiesAlive,                                           // [00028250]
      kills,                                                  // [00028254]
      score: acc.score,                                       // [00028258]
      lastPct: acc.lastPct,                                   // [0002825C]
    };
  }

  // DOS: FUN_00029F36 [00029F36-0002A0AC]; record: analysis/functions/browser-attract.md#roster-ranking
  // The ranking sort. A selection sort over the eight pilots by missions won:
  // ebx runs 8 down to 2 (1-based pilots); each pass finds, scanning pilots
  // ebx-1 down to 1, the pilot with the strictly fewest wins (an earlier-found
  // equal keeps its place, 00029F57 jae) starting from pilot ebx's own count,
  // and swaps that pilot with pilot ebx. The swap carries the campaign byte,
  // the ten progress and ten completion bytes, the three dwords, the name
  // record and the hundred mission flags - the name record as ecx = 0x2B >> 2
  // = TEN dwords (0002A072), so the record's last three bytes (the final two
  // rank slots, offsets 40 and 41, and the 0 terminator) stay where they were.
  // `selected` is [00027DAA], which follows the selected pilot to wherever
  // they land (0002A039-0002A053). Returns the new [00027DAA].
  function rosterSort(roster, selected) {
    let current = selected & 0xff;
    // DOS: FUN_00029F36 [00029F5F-0002A0A6]; record: analysis/functions/browser-attract.md#roster-ranking
    // The swap of `length` bytes between two roster places (the original's
    // xchg and rep-xchg sequences for each array).
    const xchg = (offsetA, offsetB, length) => {
      for (let index = 0; index < length; index += 1) {
        const held = roster[offsetA + index];
        roster[offsetA + index] = roster[offsetB + index];
        roster[offsetB + index] = held;
      }
    };
    for (let ebx = 8; ebx > 1; ebx -= 1) {                    // 00029F37 / 00029F3C-00029F41
      let eax = ebx;                                          // 00029F3E
      let esi = rosterGet32(roster, ROSTER.COUNT + (ebx - 1) * 4);       // 00029F47 [ebx*4 + 00029758]
      for (let ecx = ebx - 1; ecx >= 1; ecx -= 1) {           // 00029F40 dec ecx / 00029F5D loop
        const edi = rosterGet32(roster, ROSTER.COUNT + (ecx - 1) * 4);   // 00029F4E
        if (edi < esi) {                                      // 00029F55-00029F57 cmp / jae
          esi = edi;                                          // 00029F59
          eax = ecx;                                          // 00029F5B
        }
      }
      const a = eax - 1;
      const b = ebx - 1;
      xchg(ROSTER.CAMPAIGNS + a, ROSTER.CAMPAIGNS + b, 1);                   // 00029F5F-00029F6B
      xchg(ROSTER.PROGRESS + a * 10, ROSTER.PROGRESS + b * 10, 10);          // 00029F75-00029FB6
      xchg(ROSTER.DONE + a * 10, ROSTER.DONE + b * 10, 10);                  // 00029FBD-00029FEF
      xchg(ROSTER.COUNT + a * 4, ROSTER.COUNT + b * 4, 4);                   // 00029FF8-0002A006
      xchg(ROSTER.SCORE + a * 4, ROSTER.SCORE + b * 4, 4);                   // 0002A00D-0002A01B
      xchg(ROSTER.KILLS + a * 4, ROSTER.KILLS + b * 4, 4);                   // 0002A022-0002A030
      if (a === current) current = b;                         // 0002A039-0002A041
      else if (b === current) current = a;                    // 0002A049-0002A051
      xchg(a * ROSTER.STRIDE, b * ROSTER.STRIDE, 40);         // 0002A056-0002A07D ecx = 0x2B >> 2 dwords
      xchg(ROSTER.MISSIONS + a * 100, ROSTER.MISSIONS + b * 100, 100);       // 0002A07F-0002A0A6
    }
    return rosterRefreshRanks(roster, current);               // 00029F41 je 0002A0AD
  }

  // DOS: FUN_00029F36 [0002A0AD-0002A0FE]; record: analysis/functions/browser-attract.md#roster-ranking
  // The ranking numbers back into the name records: from the last pilot to the
  // first, the won count's ones, tens and hundreds digits go to record bytes
  // 5, 4 and 3, a zero tens or hundreds digit as the blank 0xFD (0002A0D4-0002A0D9,
  // 0002A0E5-0002A0EA), and the current pilot [00029701] takes [00027DAA]
  // (0002A0F4-0002A0F9). Returns [00027DAA].
  function rosterRefreshRanks(roster, selected) {
    for (let ecx = 8; ecx >= 1; ecx -= 1) {                   // 0002A0AD / 0002A0F2 loop
      let eax = rosterGet32(roster, ROSTER.COUNT + (ecx - 1) * 4);       // 0002A0BC
      const record = (ecx - 1) * ROSTER.STRIDE;               // 0002A0B7 edi = 0x296AF, minus 0x2B a pass
      roster[record + 5] = 0x30 | (eax % 10);                 // 0002A0C5-0002A0CA
      eax = Math.floor(eax / 10);
      let digit = 0x30 | (eax % 10);                          // 0002A0CF-0002A0D1
      if (digit === 0x30) digit = 0xfd;                       // 0002A0D4-0002A0D9
      roster[record + 4] = digit;                             // 0002A0DB
      eax = Math.floor(eax / 10);
      digit = 0x30 | (eax % 10);                              // 0002A0E0-0002A0E2
      if (digit === 0x30) digit = 0xfd;                       // 0002A0E5-0002A0EA
      roster[record + 3] = digit;                             // 0002A0EC
    }
    roster[ROSTER.CURRENT] = selected & 0xff;                 // 0002A0F4-0002A0F9
    return selected & 0xff;
  }

  // DOS: FUN_0002873D [00028819-00028830]; record: analysis/functions/browser-attract.md#mission-end-route
  // The pilot's campaign: [00029D47 + [00029702 + pilot]] - '0', the digit of
  // the campaign file the pilot is on. `campaignDigits` is [00029D47..], the
  // ASCII characters 0002A104-0002A1A9 leaves for the campaign files found.
  function pilotCampaign(roster, campaignDigits) {
    const pilot = roster[ROSTER.CURRENT];                     // 000288ED movzx ebx, [00029701]
    const index = roster[ROSTER.CAMPAIGNS + pilot];           // 000288F4
    const digit = (campaignDigits[index] & 0xff) - 0x30;      // 000288FB-00028902 sub ebp,0x30
    return { pilot, digit };
  }

  // DOS: FUN_0002873D [000287E2-000288E8]; record: analysis/functions/browser-attract.md#mission-end-route
  // The pilot's record after a flight that was not won. A hull still standing
  // (an abort or an empty tank, 000287E2 jne 0002887B) only has its kills
  // added. A lost hull on a campaign not yet marked completed
  // ([00029ADC + 10 * pilot + digit] not 1, 00028810) walks back over the
  // mission chosen last and the one before: where the mission is gated behind
  // its predecessor (`star[mission]`, [00029F18]) and its won flag
  // ([000297BC + 100 * pilot + 10 * digit + mission]) is set, the flag is
  // cleared and the setback sentence replaces the debrief's (00028863-00028872).
  // `debrief` is the 584-byte image; `session.hullNow` is [00019E40].
  function pilotRecordLost(roster, debrief, ctx) {
    const { pilot, digit } = pilotCampaign(roster, ctx.campaignDigits);
    if (u32(ctx.hullNow) === 0 && roster[ROSTER.DONE + pilot * 10 + digit] !== 1) {   // 000287E2-00028817
      let mission = roster[ROSTER.SELECTED];                  // 00028840 [0002975A]
      let flag = pilot * 100 + digit * 10 + mission;          // 00028819-00028847
      for (let ecx = 2; ecx > 0; ecx -= 1) {                  // 0002883B ecx = 2, 00028879 loop
        if (ctx.star[mission] !== 0 && roster[ROSTER.MISSIONS + flag] !== 0) {  // 00028849-00028859
          roster[ROSTER.MISSIONS + flag] = 0;                 // 0002885B
          const source = ctx.sentences;                       // 00028863-00028872 rep movsb, ecx = 0x2F
          for (let index = 0; index < DEBRIEF.MESSAGE_LENGTH; index += 1) {
            debrief[DEBRIEF.MESSAGE + index] = source[DEBRIEF.SETBACK + index];
          }
        }
        flag -= 1;                                            // 00028875 dec eax
        mission -= 1;                                         // 00028876 dec ebx
        if (mission < 0) break;                               // 00028877 js 0002887B
      }
    }
    rosterSet32(roster, ROSTER.KILLS + pilot * 4,             // 0002887B-00028887
      rosterGet32(roster, ROSTER.KILLS + pilot * 4) + ctx.kills);
    return { won: false };
  }

  // DOS: FUN_0002873D [000288ED-000289CF]; record: analysis/functions/browser-attract.md#mission-end-route
  // The pilot's record after a won flight. The mission read is the campaign's
  // progress byte ([0002970A + 10 * pilot + digit], 00028930) - not
  // [0002975A] - and its won flag is set and the pilot's won count stepped
  // (00028939-00028940). A mission with a promotion byte (`promo[mission]`,
  // [00029F2C]) completes the campaign ([00029ADC + ...] = 1, 00028973) and
  // stamps that byte into the first slot among record bytes 32..41 that is
  // blank (0xFC) or already equal (00028998-000289A4). Then the score and the
  // kills are added (000289A6-000289BE).
  function pilotRecordWon(roster, ctx) {
    const { pilot, digit } = pilotCampaign(roster, ctx.campaignDigits);
    const mission = roster[ROSTER.PROGRESS + pilot * 10 + digit];       // 00028930
    roster[ROSTER.MISSIONS + pilot * 100 + digit * 10 + mission] = 1;   // 00028927-00028939
    rosterSet32(roster, ROSTER.COUNT + pilot * 4, rosterGet32(roster, ROSTER.COUNT + pilot * 4) + 1);  // 00028940
    if ((ctx.promo[mission] & 0xff) !== 0) {                  // 00028949-00028950
      roster[ROSTER.DONE + pilot * 10 + digit] = 1;           // 00028959-00028973
      const stamp = ctx.promo[mission] & 0xff;                // 0002898D mov bl
      let position = pilot * ROSTER.STRIDE + 0x1f;            // 00028986-00028988 + 000295A1
      for (let ecx = 10; ecx > 0; ecx -= 1) {                 // 00028993 ecx = 0xA, 000289A2 loop
        position += 1;                                        // 00028998
        if (roster[position] === 0xfc || roster[position] === stamp) break;   // 00028999-000289A0
      }
      roster[position] = stamp;                               // 000289A4
    }
    rosterSet32(roster, ROSTER.SCORE + pilot * 4,             // 000289A6-000289B2
      rosterGet32(roster, ROSTER.SCORE + pilot * 4) + ctx.score);
    rosterSet32(roster, ROSTER.KILLS + pilot * 4,             // 000289B9-000289BE
      rosterGet32(roster, ROSTER.KILLS + pilot * 4) + ctx.kills);
    return { won: true };
  }

  // DOS: FUN_000227A6 [000227A6-000227BE]; record: analysis/functions/browser-attract.md#mission-end-route
  // The object clear: the 130 active bytes from [00021922] (slots 1..130; slot 0
  // and anything past 130 are not touched), the dword [00022368] and the wingman
  // flag [00022384] go to zero (rep stosb, ecx = 0x82; two stores).
  function clearMissionObjects(mission) {
    for (let slot = 1; slot <= 0x82; slot += 1) {             // 000227A6-000227B2
      if (mission.objects[slot]) mission.objects[slot].active = 0;
    }
    mission.dword22368 = 0;                                   // 000227B4
    mission.allyWrecked = 0;                                  // 000227B9
  }

  // DOS: FUN_0002873D [000287AB-000287E2]; record: analysis/functions/browser-attract.md#mission-end-route
  // The road out of 0002873D once the statistics have run: the attract cycle
  // ([00019ED4] == 1) goes on to the next pass (000287AB-000287B2 je 00005690);
  // no flight under way ([00019D91] == 0) goes to the menu (000287B8-000287BF je
  // 00005AE3); otherwise [00019D91] is cleared (000287C5) and a standing hull
  // ([00019E40] != 0) with every goal destroyed ([0002824E] != 0) is a win
  // (000287CC-000287DC jne 000288ED), anything else the not-won record
  // (000287E2). `session` is { attractActive, missionFlown }; returns "attract",
  // "menu", "won" or "lost".
  function missionEndRoute(session, hullNow, goalsDone) {
    if (session.attractActive) return "attract";              // 000287AB-000287B2
    if (!session.missionFlown) return "menu";                 // 000287B8-000287BF
    session.missionFlown = 0;                                 // 000287C5
    return u32(hullNow) !== 0 && (goalsDone & 0xff) !== 0 ? "won" : "lost";   // 000287CC-000287E2
  }

  // DOS: FUN_0002873D [0002873D-00028A1F]; record: analysis/functions/browser-attract.md#mission-end-route
  // Where every way of ending a flight lands. `mission` is the state it reads
  // and clears; the steps are in the original's order:
  //   00028772  the statistics (above)
  //   0002877C  000227A6: the 130 active bytes [00021922..] and [00022368],
  //             [00022384] to zero
  //   00028795  the designator box [00019D1C..28] to zero
  //   000287AB  [00019ED4] == 1 (the attract cycle) -> 00005690, the next pass
  //   000287B8  no flight under way ([00019D91] == 0) -> 00005AE3, the menu
  //   000287C5  [00019D91] = 0; then the pilot's record and the debrief 00028A1F
  // The shake phase, countdown and screen drop [00019DBC/C0/C4] are zeroed
  // first (0002874D-00028761). The roster is updated and ranked only on the
  // debrief path; the caller writes the file (00015D40) and shows 00028A1F.
  // `input` is { mission, roster, session, tables, text }: `session` is
  // { attractActive: [00019ED4] === 1, missionFlown: [00019D91] }, `tables` the
  // mission list's `star`/`promo` and the campaign digits, `text` the debrief
  // image. Returns { route, stats, debriefText, selected } and mutates `mission`
  // (fuel, hull counters, active flags, shake, designator box), `session` and
  // `roster`.
  function missionEnd(input) {
    const { mission, roster, session, tables } = input;
    const sentences = input.text;
    mission.shake.phase = 0;                                  // 0002874D [00019DBC]
    mission.shake.countdown = 0;                              // 00028757 [00019DC0]
    mission.crashDrop = 0;                                    // 00028761 [00019DC4]
    const stats = missionStatistics({                         // 00028772
      fuel: mission.fuel,
      fuelMax: mission.fuelMax,
      hullNow: mission.hullNow,
      hullMax: mission.hullMax,
      objects: mission.objects,
      targetCount: mission.targetCount,
      ammo: mission.ammo,
      loadout: mission.loadout,
      allyWrecked: mission.allyWrecked,
      text: sentences,
    });
    mission.fuel = stats.fuel;                                // 0002826A
    mission.hullNow = stats.hullNow;                          // 00028274-00028289
    mission.hullMax = stats.hullMax;
    clearMissionObjects(mission);                             // 0002877C call 000227A6
    mission.designator = [0, 0, 0, 0];                        // 00028795-000287A6
    const route = missionEndRoute(session, stats.hullNow, stats.goalsDone);    // 000287AB-000287E2
    const current = roster ? roster[ROSTER.CURRENT] : 0;
    if (route === "attract" || route === "menu") return { route, stats, debriefText: stats.text, selected: current };
    const debriefText = Uint8Array.from(stats.text);
    const ctx = {
      campaignDigits: tables.campaignDigits,
      star: tables.star,
      promo: tables.promo,
      sentences,
      hullNow: stats.hullNow,
      kills: stats.kills,
      score: stats.score,
    };
    const won = route === "won";
    if (won) pilotRecordWon(roster, ctx);                     // 000287DC je 000288ED
    else pilotRecordLost(roster, debriefText, ctx);           // 000287E2
    const selected = rosterSort(roster, roster[ROSTER.CURRENT]);   // 00028898 / 000289CF with [00027DAA] = [00029701]
    return { route: "debrief", won, stats, debriefText, selected };
  }

  globalThis.ComanchePilot = {
    ROSTER,
    DEBRIEF,
    rosterGet32,
    rosterSet32,
    formatNumber,
    percentField,
    missionStatistics,
    rosterSort,
    rosterRefreshRanks,
    pilotCampaign,
    pilotRecordLost,
    pilotRecordWon,
    clearMissionObjects,
    missionEndRoute,
    missionEnd,
  };
})();
