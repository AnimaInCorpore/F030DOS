/*
 * The menu-side routines of the original, from the DOS listing: the mission
 * list and its briefing, the Your Stats screen, the options menu's Game column
 * and the new-pilot name entry.
 *
 * Like dos-pilot.js these are pure transcriptions over explicit state: no DOM,
 * no clock, no randomness. Screen drawing (the text engine 00027034, the box
 * 0002628E, the palette and page work) is the host's; what lives here is the
 * data the original builds for it - the patched text images, the colour
 * letters, the wrapped briefing, the settings block - and the decisions it
 * makes from key codes and the roster. DOS byte semantics are explicit: text
 * is bytes with the original's 0xFC pad, 0xFD blank, 0xFF end and 0x00 line
 * codes, offsets are the DOS flat addresses minus the buffer's own base, and
 * the roster is the COMANCHE.NAM image of dos-pilot.js.
 *
 * Record: analysis/functions/browser-attract.md#mission-list-scan,
 * #mission-list-gate, #mission-briefing, #menu-your-stats, #menu-options-game
 * and #pilot-name-entry.
 */
// Target artefact; record: analysis/functions/browser-attract.md#mission-list-gate
(() => {
  "use strict";

  const TEXT = globalThis.ComancheDOSText;
  const PILOT = globalThis.ComanchePilot;
  const ROSTER = PILOT.ROSTER;

  // The mission names live in ten 0x20-byte slots from flat 00029D95: the
  // bytes "|g  " (7C 67 20 20), the name, 0xFC pad to the slot's last byte, 0.
  // The colour letter the list recolours is slot byte 1 (00029D96).
  const NAME_SLOT = 0x20;
  const NAME_BASE = 0x29d95;
  const MISSIONS_PER_CAMPAIGN = 10;

  // DOS: FUN_0002A2F8 [0002A2F8-0002A31C]; record: analysis/functions/browser-attract.md#mission-list-scan
  // The mission file as 0002A2F8 leaves it in memory. When the first byte is
  // not '{' the file is XOR-coded dword by dword with 0x11120603 (bytes 03 06
  // 12 11): ecx = (length + 3) >> 2 dwords, lodsd / xor / stosd. `bytes` is the
  // file as read; the result is a copy padded to a whole number of dwords with
  // the zero bytes the original's read buffer held past the file's end (the
  // original decodes those too: bytes beyond the length are Unproven but are
  // never read by the routines below, which stop at the file's own markers).
  function decodeMissionImage(bytes) {
    const dwords = (bytes.length + 3) >> 2;                  // 0002A300-0002A309
    const image = new Uint8Array(dwords * 4);
    image.set(bytes);
    if (image[0] === 0x7b) return image;                     // 0002A30C-0002A30F cmp [esi], '{'
    const key = [0x03, 0x06, 0x12, 0x11];                    // 0002A311 ebx = 0x11120603
    for (let index = 0; index < image.length; index += 1) image[index] ^= key[index & 3];   // 0002A316-0002A31A
    return image;
  }

  // DOS: FUN_0002A1AD [0002A1AD-0002A299]; record: analysis/functions/browser-attract.md#mission-list-scan
  // The mission list of a campaign file. `image` is the decoded file and
  // `length` its byte count ([00015DC8]). The first '}' ends the campaign's
  // title; then for up to ten missions the routine finds the next '{' and '}'
  // (the scans share one count, ecx = remaining length, as `repne scasb` does)
  // and records, per mission k:
  //   star[k]   [00029F18+k]: 1 when the byte after '}' is '*' (the mission is
  //             gated behind the one before it)
  //   promo[k]  [00029F2C+k]: when that '*' is followed by a digit, digit + 1
  //             (the rank byte a win stamps into the pilot's record)
  //   text[k]   [00029EF0+4k]: the offset just after '}' in the image
  //   names     the 0x20-byte slots at 00029D95 ("|g  ", the name, 0xFC, 0)
  // Each pass first writes 00 00 FF 00 at the slot (0002A212), which stays when
  // the next '{' or '}' is missing (0002A21E/0002A226 jne -> ret): the list's
  // end marker, byte 2 = 0xFF.
  function scanMissionList(image, length = image.length) {
    const names = new Uint8Array((MISSIONS_PER_CAMPAIGN + 1) * NAME_SLOT);
    const star = new Uint8Array(MISSIONS_PER_CAMPAIGN);
    const promo = new Uint8Array(MISSIONS_PER_CAMPAIGN);
    const text = new Int32Array(MISSIONS_PER_CAMPAIGN).fill(-1);
    let remaining = length;
    let position = 0;
    // `repne scasb`: scan forward for `byte`, consuming ecx. Returns the offset
    // after the match, or -1 when ecx runs out first (ZF clear, 0002A200 jne).
    // DOS: FUN_0002A1AD [0002A1FE-0002A226]; record: analysis/functions/browser-attract.md#mission-list-scan
    const scan = (byte) => {
      while (remaining > 0) {
        const hit = image[position] === byte;
        position += 1;
        remaining -= 1;
        if (hit) return position;
      }
      return -1;
    };
    if (scan(0x7d) < 0) return { names, star, promo, text, count: 0 };   // 0002A1FE-0002A200
    let resume = position;                                   // 0002A206 edx = edi
    let count = 0;                                           // 0002A208 [0002A100] = 0
    for (let ebp = MISSIONS_PER_CAMPAIGN; ebp > 0; ebp -= 1) {           // 0002A1F7 ebp = 10, 0002A293 dec ebp
      const slot = count * NAME_SLOT;
      names.set([0x00, 0x00, 0xff, 0x00], slot);             // 0002A212 [ebx] = 0x00FF0000
      position = resume;                                     // 0002A218 edi = edx
      if (scan(0x7b) < 0) break;                             // 0002A21A-0002A21E
      const nameStart = position;                            // 0002A220 esi = edi
      if (scan(0x7d) < 0) break;                             // 0002A222-0002A226
      const k = count;                                       // 0002A228 eax = [0002A100]
      promo[k] = 0;                                          // 0002A22D
      let isStar = 0;
      const next = image[position];
      if (next === 0x2a) {                                   // 0002A234-0002A237
        isStar = 1;
        const digit = image[position + 1];
        if (digit >= 0x30 && digit <= 0x39) promo[k] = digit - 0x30 + 1;   // 0002A23C-0002A250
      }
      star[k] = isStar;                                      // 0002A256 [eax + 00029F18] = dl
      text[k] = position;                                    // 0002A25C [eax*4 + 00029EF0] = edi
      count += 1;                                            // 0002A263
      resume = position;                                     // 0002A26A edx = edi
      const length2 = position - nameStart - 1;              // 0002A26C-0002A270 ecx = edi - esi - 1
      let out = slot;
      names.set([0x7c, 0x67, 0x20, 0x20], out);              // 0002A273 [edi] = 0x2020677C
      out += 4;
      for (let index = 0; index < length2; index += 1) {     // 0002A27C rep movsb
        if (out < names.length) names[out] = image[nameStart + index];
        out += 1;
      }
      const fill = (slot + NAME_SLOT) - 1 - out;             // 0002A27E-0002A284 ecx = ebx - 1 - edi
      if (fill > 0) {                                        // 0002A286-0002A288 je / js
        for (let index = 0; index < fill; index += 1) names[out + index] = 0xfc;   // 0002A28A rep stosb
        names[out + fill] = 0;                               // 0002A28E-0002A290
      }
    }
    return { names, star, promo, text, count };
  }

  // DOS: FUN_00028F3F [00028F46-00028FB8]; record: analysis/functions/browser-attract.md#mission-list-gate
  // The colour letter of each mission row. `won` is the pilot's ten won flags
  // for the campaign ([000297BC + 100 * pilot + 10 * digit], esi at 00028F79);
  // `star` the list's [00029F18]; `names` the slots above, whose byte 1 (the
  // letter, [00029D96 + 0x20 k]) is rewritten for every row up to the first slot
  // whose byte 1 is zero (00028FA7-00028FAA je 00028FBA). The rule, with edx
  // counting the won missions passed so far and ebx the row:
  //   green 'g' (0x67) by default;
  //   orange 'o' (0x6F) when edx != ebx - some earlier mission is not won - and
  //   the row is a star mission (00028F91-00028F9E);
  //   blue 'b' (0x62) when the row itself is won (00028FA0-00028FA6), which
  //   also counts it (inc edx).
  // Returns the letters in [00029F22 + k] (zero where the list ended).
  function missionRowColours(won, star, names) {
    const colours = new Uint8Array(MISSIONS_PER_CAMPAIGN + 10);
    let edx = 0;                                             // 00028F8C
    for (let ebx = 0; ebx < MISSIONS_PER_CAMPAIGN; ebx += 1) {           // 00028F85 ecx = 10, 00028FB8 loop
      const al = won[ebx];                                   // 00028F8E lodsb
      let ah = 0x67;                                         // 00028F8F
      if (edx !== ebx && star[ebx] !== 0) ah = 0x6f;         // 00028F91-00028F9E
      if (al !== 0) {                                        // 00028FA0-00028FA2
        ah = 0x62;                                           // 00028FA4
        edx += 1;                                            // 00028FA6
      }
      const slot = ebx * NAME_SLOT;
      if (names[slot + 1] === 0) break;                      // 00028FA7-00028FAA cmp [edi], 0 / je
      names[slot + 1] = ah;                                  // 00028FAC
      colours[ebx] = ah;                                     // 00028FAE [ebx + 00029F22]
    }
    return colours;
  }

  // DOS: FUN_00028F3F [00028FBA-00028FE1]; record: analysis/functions/browser-attract.md#mission-list-gate
  // The row the list opens on: the pilot's progress byte for the campaign they
  // are on, [0002970A + 10 * pilot + digit] (00028FBA-00028FDB), handed to the
  // list menu 00027DB4 in al at 00028FE1.
  function missionListSelection(roster, campaignDigits) {
    const pilot = roster[ROSTER.CURRENT];                    // 00028FBA movzx ebx, [00029701]
    const digit = (campaignDigits[roster[ROSTER.CAMPAIGNS + pilot]] & 0xff) - 0x30;   // 00028FC1-00028FCF
    return roster[ROSTER.PROGRESS + pilot * 10 + digit];     // 00028FD2-00028FDB
  }

  // DOS: FUN_00028F3F [00028FBA-00029033]; record: analysis/functions/browser-attract.md#mission-list-gate
  // The choice from the mission list. The row `ecx` the menu returned
  // (00028FE6 movzx ecx, al) is stored first, as the pilot's progress byte for
  // the campaign ([0002970A + 10 * pilot + digit], 0002900A) and as the mission
  // chosen last ([0002975A], 00029010) - before the lock test, so a refused
  // locked row is still recorded. Then a row whose letter is 'o' (00029016
  // cmp [ecx + 00029F22], 0x6F; jne 00029038) is refused with the message at
  // 000269D5 through 00026E90 and the list is drawn again (00029033 jmp
  // 00028F3F); any other row goes on to the briefing (00029038).
  // Returns { locked, row }.
  function missionListChoice(roster, campaignDigits, colours, row) {
    const pilot = roster[ROSTER.CURRENT];
    const digit = (campaignDigits[roster[ROSTER.CAMPAIGNS + pilot]] & 0xff) - 0x30;   // 00028FF0-00029001
    const ecx = row & 0xff;                                  // 00028FE6
    roster[ROSTER.PROGRESS + pilot * 10 + digit] = ecx;      // 00029001-0002900A
    roster[ROSTER.SELECTED] = ecx;                           // 00029010
    return { locked: colours[ecx] === 0x6f, row: ecx };      // 00029016-0002901D
  }

  // DOS: FUN_0002A29A [0002A29A-0002A2B9]; record: analysis/functions/browser-attract.md#mission-briefing
  // The line skipper. From `position`: scan up to 0xA0 bytes for a CR
  // (0002A29B-0002A2A2 repne scasb with ecx = 0xA0), step over one LF, and take
  // the line if its first byte is above 0x20 and not ';' (0002A2AC-0002A2B4);
  // otherwise scan again. No CR within 0xA0 bytes leaves for the mission file's
  // error exit 00029359 (0002A2B8-0002A2BA), reported here as an Error.
  function skipLine(image, position) {
    for (;;) {
      let count = 0xa0;                                      // 0002A29B
      let found = false;
      while (count > 0) {                                    // 0002A2A0-0002A2A2 repne scasb
        const hit = image[position] === 0x0d;
        position += 1;
        count -= 1;
        if (hit) { found = true; break; }
      }
      if (!found) throw new Error("mission file: no line end within 0xA0 bytes (0002A2B8 -> 00029359)");
      if (image[position] === 0x0a) position += 1;           // 0002A2A6-0002A2AB
      if (image[position] <= 0x20) continue;                 // 0002A2AC jbe
      if (image[position] === 0x3b) continue;                // 0002A2B1 je
      return position;                                       // 0002A2B6 ret
    }
  }

  // DOS: FUN_00029038 [000290C0-00029119]; record: analysis/functions/browser-attract.md#mission-briefing
  // The wrap loop of the briefing builder, from `mov ah, 0x20` (000290C0) to the
  // `<` that ends the text (000290C7 je 00029119). Starting at source offset
  // `start` in `image`: control codes fold to one space (000290CF-000290D8: a
  // CR or tab after a space is dropped, an LF always), '^' becomes a 0 byte - a
  // paragraph break - and resets the line, and the line breaks at the last
  // space once its width in the text engine's table [0002727E] passes 0x118
  // (000290F4-00029106): the output is rewound to that space, which a 0
  // replaces, and the source is rewound to the character after it
  // (00029108-00029117); a line with no space to break at gets its 0 after the
  // overflowing character. Returns { bytes, next }: the bytes stored before the
  // closing 0xFF, and the source offset after the `<` (esi).
  function wrapBriefing(image, start) {
    const widths = TEXT.charWidths.bytes;
    const out = [];
    let esi = start;
    let ah = 0x20;                                           // 000290C0
    let ecx = 0;                                             // 000290C2
    let ebx = -1;                                            // 000290C4 xor ebx, ebx (no break point yet)
    let ebp = -1;                                            // the output length at that space
    for (;;) {                                               // 000290C6
      if (esi >= image.length) throw new Error("mission file: briefing has no '<' end (000290C7)");
      let al = image[esi];
      esi += 1;
      if (al === 0x3c) break;                                // 000290C7-000290C9
      if (al === 0x0a) continue;                             // 000290CB-000290CD
      if (al < 0x20) {                                       // 000290CF-000290D1 jae 000290DA
        if (ah === 0x20) continue;                           // 000290D3-000290D6
        al = 0x20;                                           // 000290D8
      }
      if (al === 0x20) {                                     // 000290DA-000290E0
        ebx = esi;
        ebp = out.length;
      }
      ah = al;                                               // 000290E2
      if (al === 0x5e) {                                     // 000290E4-000290EE
        al = 0;
        ah = 0x20;
        ecx = 0;
        ebx = -1;
      }
      out.push(al);                                          // 000290F0 stosb
      ecx += widths[al];                                     // 000290F1-000290FE
      if (ecx <= 0x118) continue;                            // 00029100-00029106 jbe
      ecx = 0;                                               // 00029108
      if (ebx >= 0) {                                        // 0002910A-0002910C
        esi = ebx;                                           // 0002910E
        out.length = ebp;                                    // 00029110 edi = ebp
      }
      ebx = -1;                                              // 00029112
      out.push(0);                                           // 00029114-00029116
    }
    return { bytes: Uint8Array.from(out), next: esi };
  }

  // DOS: FUN_00029038 [00029038-00029119]; record: analysis/functions/browser-attract.md#mission-briefing
  // The briefing text builder. `image` is the decoded mission file, `names` the
  // list's slots, `textStart` the mission's [00029EF0 + 4 * mission] pointer (an
  // offset into `image`) and `mission` the row ([0002975A]). The output starts
  // "bar-b", 0, the mission's 28-byte name from [00029D99 + 0x20 k] (0x1C bytes:
  // the name, its 0xFC pad and the slot's 0 terminator, 00029098), 0, "bar-g"
  // (00029078-000290A7), then the description from the first line after the
  // title line (skipLine, 000290B1-000290B8) wrapped by wrapBriefing, closed
  // with 0xFF (00029119). Returns { bytes, lines, next } - the output through
  // the 0xFF, its 0-separated lines as text, and the source offset after the
  // `<` (esi, where the rest of the mission parse goes on from).
  function buildBriefing(image, names, textStart, mission) {
    const head = [0x7c, 0x62, 0x00];                         // 00029078-00029085 stosw 0x627C, stosb 0
    const nameOffset = mission * NAME_SLOT + 4;              // 00029D99 - 00029D95
    for (let index = 0; index < 0x1c; index += 1) head.push(names[nameOffset + index]);   // 00029098-0002909E
    head.push(0x00, 0x7c, 0x67);                             // 000290A0-000290A7
    const wrapped = wrapBriefing(image, skipLine(image, textStart));   // 000290B1-000290BD
    const bytes = Uint8Array.from([...head, ...wrapped.bytes, 0xff]);  // 00029119-0002911B
    const lines = [];
    let line = [];
    for (let index = head.length; index < bytes.length; index += 1) {
      if (bytes[index] === 0xff) break;
      if (bytes[index] === 0) {
        lines.push(String.fromCharCode(...line));
        line = [];
      } else {
        line.push(bytes[index]);
      }
    }
    if (line.length) lines.push(String.fromCharCode(...line));
    return { bytes, lines, next: wrapped.next };
  }

  // DOS: FUN_00028B37 [00028B37-00028C20]; record: analysis/functions/browser-attract.md#menu-your-stats
  // The Your Stats screen's text. Four dwords of the template are first set to
  // 0xFCFCFCFC (00028B3C-00028B50: [00028B02], [00028B1C], [00028AF6],
  // [00028AFA]); then the selected pilot's record bytes 9..41 (0x21 bytes from
  // 0002958B + 0x2B * pilot, 00028B62-00028B82) replace the template from
  // 00028ABD, and the pilot's score ([0002977C]), missions won ([0002975C]) and
  // kills ([0002979C]) are formatted by 00028C25 as 8, 3 and 4 digits at
  // 00028AF6, 00028B02 and 00028B1C. Returns a copy of the 130-byte template
  // image (flat 00028AB5) patched in that order.
  function yourStatsScreen(roster, pilot = roster[ROSTER.CURRENT]) {
    const base = TEXT.yourStatsScreen.address;
    const image = Uint8Array.from(TEXT.yourStatsScreen.bytes);
    for (const address of [0x28b02, 0x28b1c, 0x28af6, 0x28afa]) image.fill(0xfc, address - base, address - base + 4);   // 00028B3C-00028B50
    const record = pilot * ROSTER.STRIDE + ROSTER.NAME;      // 00028B62-00028B72
    for (let index = 0; index < 0x21; index += 1) image[0x28abd - base + index] = roster[record + index];   // 00028B78-00028B82
    PILOT.formatNumber(image, 0x28af6 - base, 8, PILOT.rosterGet32(roster, ROSTER.SCORE + pilot * 4));    // 00028B8B-00028B9C
    PILOT.formatNumber(image, 0x28b02 - base, 3, PILOT.rosterGet32(roster, ROSTER.COUNT + pilot * 4));    // 00028BA1-00028BB2
    PILOT.formatNumber(image, 0x28b1c - base, 4, PILOT.rosterGet32(roster, ROSTER.KILLS + pilot * 4));    // 00028BB7-00028BC8
    return image;
  }

  // The settings block [00025DBC..00025DDE], 35 bytes - COMANCHE.MNU. Offsets
  // from 00025DBC: the screen rectangle words 0..0x15, [00025DD2], [00025DD3],
  // then the characters the options menu keeps: detail [00025DD4], sound
  // [00025DD5], music [00025DD6], controls [00025DD7], and seven '{'/'}'
  // switches [00025DD8..00025DDE].
  const SETTINGS_BYTES = 0x23;
  const SETTINGS_SWITCH = 0x25dd8 - 0x25dbc;

  // The seven switches, in menu order of the toggle code: key code, the address
  // of the brace in the menu text, and the settings byte it is stored to.
  // (000 26AB6-00026B49: 0x2E -> [0002677A] / [00025DDE]; 0x2D -> [00026767] /
  // [00025DDD]; 0x14 -> [000266A0] / [00025DD8]; 0x15 -> [000266A9] /
  // [00025DD9]; 0x30 -> [000267AC] / [00025DDA]; 0x31 -> [000267C1] /
  // [00025DDB]; 0x32 -> [000267D2] / [00025DDC].)
  const SWITCHES = Object.freeze({
    0x2e: { brace: 0x2677a, setting: 0x25dde },
    0x2d: { brace: 0x26767, setting: 0x25ddd },
    0x14: { brace: 0x266a0, setting: 0x25dd8 },
    0x15: { brace: 0x266a9, setting: 0x25dd9 },
    0x30: { brace: 0x267ac, setting: 0x25dda },
    0x31: { brace: 0x267c1, setting: 0x25ddb },
    0x32: { brace: 0x267d2, setting: 0x25ddc },
  });

  // DOS: FUN_00026AB6 [00026AB6-00026B49]; record: analysis/functions/browser-attract.md#menu-options-game
  // The seven toggle cases. The brace in the menu text is XORed with 6
  // ('{' 0x7B <-> '}' 0x7D) and the new character is stored both back into the
  // menu text and into the settings byte; `menu.braces` maps the brace's flat
  // address to its byte and `menu.settings` is the 35-byte block. A key code
  // that is not one of the seven changes nothing. Returns whether it matched.
  function optionsToggle(menu, code) {
    const entry = SWITCHES[code & 0xff];
    if (!entry) return false;
    const flipped = menu.braces[entry.brace] ^ 6;            // 00026ABA-00026ABF
    menu.braces[entry.brace] = flipped;                      // 00026AC1
    menu.settings[entry.setting - 0x25dbc] = flipped;        // 00026AC6
    return true;
  }

  // DOS: FUN_00026D8B [00026D8B-00026E8F]; record: analysis/functions/browser-attract.md#menu-options-game
  // The Game column's items (the key code in al):
  //   2  Save Menu Settings: the 35 bytes at 00025DBC are written to
  //      Comanche.MNU (00026D8F-00026D99 edx = 0x25DBC, ebx = 0x23 through
  //      00015D40) and the 'Menu Settings Saved' box of 000269BC is shown
  //      (00026DAB-00026E06, waiting for a key)
  //   3  Abort Mission: jmp 0002873D
  //   4  Exit to DOS: jmp 00006B14
  //   1  the Return item: pop ebx; jmp 0002615C (back into the options bar)
  //   0  About Comanche: the credits box of 0002691C (00026E25-00026E8D)
  // Anything else falls out at 00026E8F ret. The result names the action and
  // carries what the host must write or show; the input is not modified.
  function optionsGameAction(menu, code) {
    switch (code & 0xff) {
      case 2:                                                // 00026D8B-00026D8D
        return { action: "save-settings", file: "Comanche.MNU", bytes: Uint8Array.from(menu.settings), message: TEXT.optionsSaved.bytes };
      case 3:                                                // 00026E07-00026E09
        return { action: "abort-mission", target: 0x2873d };
      case 4:                                                // 00026E0F-00026E11
        return { action: "exit", target: 0x6b14 };
      case 1:                                                // 00026E17-00026E1C
        return { action: "return", target: 0x2615c };
      case 0:                                                // 00026E21-00026E25
        return { action: "about", message: TEXT.optionsAbout.bytes };
      default:
        return { action: "none" };                           // 00026E8F
    }
  }

  // The key FIFO at [00001B70]: four scancode bytes with the newest in byte 0.
  // DOS: FUN_00001B80 [00001BE8-00001BFA]; record: analysis/functions/browser-attract.md#pilot-name-entry
  // The ISR's queue step for a make code (a release code, bit 7 set, is never
  // queued: 00001B9E js 00001C00): the dword moves up one byte
  // ([00001B71] = [00001B70], 00001BE8-00001BEE) and the code takes byte 0.
  function keyFifoPush(fifo, scancode) {
    return (((fifo << 8) >>> 0) | (scancode & 0xff)) >>> 0;
  }

  // DOS: FUN_0002800C [00028084-0002808A]; record: analysis/functions/browser-attract.md#pilot-name-entry
  // The reader's pop, `mov bl, [00001B70]` then `shr dword [00001B70], 8`: the
  // newest code first. Returns { code, fifo }.
  function keyFifoPop(fifo) {
    return { code: fifo & 0xff, fifo: fifo >>> 8 };
  }

  // DOS: FUN_0002800C [0002800C-00028129]; record: analysis/functions/browser-attract.md#pilot-name-entry
  // A fresh name entry: the field [00027FEA] is 32 bytes of 0xFC (00028024-
  // 00028029 rep stosd) and the cursor [0002800B] is 0; the field then shows
  // the cursor, '_' (0x5F) and 0xFC at the cursor (0002802B-00028036 word
  // 0xFC5F).
  function nameEntryStart() {
    const state = { field: new Uint8Array(32).fill(0xfc), cursor: 0 };
    nameEntryShowCursor(state);
    return state;
  }

  // DOS: FUN_0002800C [0002802B-00028036]; record: analysis/functions/browser-attract.md#pilot-name-entry
  // The cursor marks its place at the top of every pass.
  function nameEntryShowCursor(state) {
    state.field[state.cursor] = 0x5f;                        // 00028032-00028036 mov [ebx + 00027FEA], ax
    state.field[state.cursor + 1] = 0xfc;
  }

  // DOS: FUN_0002800C [0002807E-00028129]; record: analysis/functions/browser-attract.md#pilot-name-entry
  // One key of the name entry. `scancode` is the popped FIFO byte, `shiftHeld`
  // true when either shift key reads pressed (the key states [00001A9A] and
  // [00001AA6] are 0x80+ when released, and a character takes the shifted
  // table unless the AND of the two is negative, 000280CE-000280DC).
  //   Esc (1)       leave without a pilot (0002820B)
  //   Return (0x1C) with an empty name leave without a pilot (00028137 je);
  //                 otherwise the cursor's byte becomes 0xFC (0002813D) and the
  //                 pilot is created
  //   Backspace (0xE) back one place unless at the start (000280AD-000280BC)
  //   other keys    a character from [000019E9] (0 = no character, ignored),
  //                 or [00001969] with shift, goes to the cursor's place
  //                 (000280E2-000280E9); the cursor advances unless it has
  //                 reached 0x16 (000280EF-000280F6) or the characters so far
  //                 are at least 0x6C wide in the text engine's table
  //                 (000280FC-0002811D), and the cursor is drawn again.
  // Returns "cancel", "accept" or null (carry on).
  function nameEntryKey(state, scancode, shiftHeld) {
    const widths = TEXT.charWidths.bytes;
    scancode &= 0xff;
    if (scancode === 0) return null;                         // 00028092 or bl,bl / je 0002807E
    if (scancode === 1) return "cancel";                     // 00028096-00028099
    if (scancode === 0x1c) {                                 // 0002809F-000280A2
      if (state.cursor === 0) return "cancel";               // 00028135-00028137
      state.field[state.cursor] = 0xfc;                      // 0002813D
      return "accept";
    }
    if (scancode === 0x0e) {                                 // 000280A8-000280AB
      if (state.cursor === 0) return null;                   // 000280AD-000280B4
      state.cursor -= 1;                                     // 000280B6
      nameEntryShowCursor(state);                            // 000280BC jmp 0002802B
      return null;
    }
    const lower = TEXT.keyLower.bytes[scancode];             // 000280C4
    if (lower === 0) return null;                            // 000280CA-000280CC
    const character = shiftHeld ? TEXT.keyShift.bytes[scancode] : lower;   // 000280CE-000280DC
    state.field[state.cursor] = character;                   // 000280E9
    if (state.cursor >= 0x16) {                              // 000280EF-000280F6 jae 0002802B
      nameEntryShowCursor(state);
      return null;
    }
    let width = 0;                                           // 00028101 ebp = 0
    for (let index = 0; index <= state.cursor; index += 1) width += widths[state.field[index]];   // 00028105-00028118
    if (width < 0x6c) state.cursor += 1;                     // 0002811A-00028123 cmp ebp, 0x6C / jae / inc
    nameEntryShowCursor(state);                              // 00028129 jmp 0002802B
    return null;
  }

  // DOS: FUN_0002800C [0002812E-000281FE]; record: analysis/functions/browser-attract.md#pilot-name-entry
  // The new pilot's record in slot `slot` ([00027DAA]) once Return has taken
  // the name: the ten progress and ten completion bytes, the won count, score
  // and kill dwords and the campaign byte are zeroed (00028145-00028191); the
  // 43-byte name record is the nine bytes of 00027FC0, the field's first 0x16
  // bytes and the twelve of 00027FC9 (00028198-000281C9); the pilot's hundred
  // mission flags are zeroed (000281CB-000281E8 rep stosd, ecx = 0x19); then
  // the roster is ranked (00029F36), which moves [00027DAA] with the pilot.
  // The caller writes the file (00015D40, 000281EF-000281F9). Returns the
  // pilot's index after the ranking.
  function createPilot(roster, slot, field) {
    for (let index = 0; index < 10; index += 1) {            // 00028153-00028167
      roster[ROSTER.PROGRESS + slot * 10 + index] = 0;
      roster[ROSTER.DONE + slot * 10 + index] = 0;
    }
    PILOT.rosterSet32(roster, ROSTER.COUNT + slot * 4, 0);   // 00028170
    PILOT.rosterSet32(roster, ROSTER.SCORE + slot * 4, 0);   // 0002817B
    PILOT.rosterSet32(roster, ROSTER.KILLS + slot * 4, 0);   // 00028186
    roster[ROSTER.CAMPAIGNS + slot] = 0;                     // 00028191
    const record = slot * ROSTER.STRIDE;
    roster.set(TEXT.nameRecordPrefix.bytes, record);                         // 000281A7-000281B1
    roster.set(field.subarray(0, ROSTER.NAME_CHARS), record + 9);            // 000281B3-000281BD
    roster.set(TEXT.nameRecordSuffix.bytes, record + 9 + ROSTER.NAME_CHARS);  // 000281BF-000281C9
    roster.fill(0, ROSTER.MISSIONS + slot * 100, ROSTER.MISSIONS + slot * 100 + 100);   // 000281D2-000281E8
    return PILOT.rosterSort(roster, slot);                   // 000281EA call 00029F36
  }

  globalThis.ComancheMenu = {
    NAME_SLOT,
    NAME_BASE,
    SETTINGS_BYTES,
    SETTINGS_SWITCH,
    SWITCHES,
    decodeMissionImage,
    scanMissionList,
    missionRowColours,
    missionListSelection,
    missionListChoice,
    skipLine,
    wrapBriefing,
    buildBriefing,
    yourStatsScreen,
    optionsToggle,
    optionsGameAction,
    keyFifoPush,
    keyFifoPop,
    nameEntryStart,
    nameEntryShowCursor,
    nameEntryKey,
    createPilot,
  };
})();
