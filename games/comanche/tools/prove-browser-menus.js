#!/usr/bin/env node
/*
 * Proof gate for the pilot, mission-end, menu and damage modules of the
 * JavaScript DOS reference: jsComanche/dos-pilot.js, dos-menu.js, dos-damage.js
 * and their data, jsComanche/dos-text-data.js.
 *
 * Run by tools/prove-browser-attract.js after the runtime proof, or alone:
 *
 *     node tools/prove-browser-menus.js
 *
 * Fixture sources, in the order of preference:
 *   - the hashed DOS image (every text and table is compared with it byte for
 *     byte; structural facts such as the 0x2F-byte sentence length are read
 *     out of it);
 *   - the shipped asset tree (COMANCHE.NAM, COMANCHE.MNU, 0.MIS, 1.MIS);
 *   - DOS captures taken at instructions by work/trace_mission_end.py,
 *     work/trace_mission_live.py, work/trace_player_damage.py and
 *     work/dos_call.py (work/replay_dos/mission-*.json, damage-*.json and
 *     dos-call-*.json, derived and gitignored: when absent those checks report
 *     SKIP, never PASS);
 *   - the briefing the original shows for the first mission, as recorded in the
 *     project notes: four lines, checked against the DOS width table.
 * Inputs that no capture holds - which object was shot - are reconstructed from
 * the mission file's own records, and the check says so. Where there is no DOS
 * evidence at all (the ranking sort's reordering, the menu screens) the
 * expectations are an independent transcription of the listing and the check
 * is labelled as such; those rows stay Unproven in the function records. The
 * damage chain's captures are checked by tools/check-js-damage.js and the
 * routines called directly in the original by tools/check-js-dos-calls.js;
 * this gate runs both last.
 */

"use strict";

const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");

const ROOT = path.resolve(__dirname, "..");
const JS_ROOT = path.join(ROOT, "jsComanche");
const ASSET_ROOT = path.join(ROOT, "assets", "extracted", "comanche_hdd");
const CAPTURE_ROOT = path.join(ROOT, "work", "replay_dos");

function loadModules() {
  for (const name of ["dos-text-data.js", "dos-pilot.js", "dos-menu.js", "dos-damage.js"]) {
    // eslint-disable-next-line global-require
    require(path.join(JS_ROOT, name));
  }
  return {
    text: globalThis.ComancheDOSText,
    pilot: globalThis.ComanchePilot,
    menu: globalThis.ComancheMenu,
    damage: globalThis.ComancheDamage,
  };
}

function flatImage() {
  // The same derivation tools/prove-browser-attract.js uses: the MZ load
  // module's flat region starts 0x1700 bytes in.
  const image = fs.readFileSync(path.join(ASSET_ROOT, "UNPACKED.EXE"));
  const headerBytes = image.readUInt16LE(8) * 16;
  const pages = image.readUInt16LE(4);
  const lastPageBytes = image.readUInt16LE(2);
  const imageEnd = pages * 512 - (512 - lastPageBytes);
  return image.subarray(headerBytes, imageEnd).subarray(0x1700);
}

const hex = (value) => new Uint8Array(Buffer.from(value, "hex"));
const dword = (bytes, offset) => (bytes[offset] | (bytes[offset + 1] << 8) | (bytes[offset + 2] << 16) | (bytes[offset + 3] << 24)) >>> 0;

function readCapture(name) {
  const file = path.join(CAPTURE_ROOT, `${name}.json`);
  if (!fs.existsSync(file)) return null;
  return JSON.parse(fs.readFileSync(file, "utf8"));
}

// The mission file as the original holds it, decoded with 0002A2F8's rule, and
// its placement records as 00029250-0002933F parses them: type, f1 (the second
// field) and the '*' continuation.
function missionRecords(menu, fileName) {
  const raw = fs.readFileSync(path.join(ASSET_ROOT, fileName));
  const image = menu.decodeMissionImage(new Uint8Array(raw));
  const text = Buffer.from(image.subarray(0, raw.length)).toString("latin1").replace(/\r/g, "");
  const missions = [];
  // Each mission is "{title}", its description, "<", the resource names,
  // "<", the scalar lines and placement records, "<"; the campaign title line
  // is the first '{...}'.
  let cursor = text.indexOf("}") + 1;
  for (;;) {
    const open = text.indexOf("{", cursor);
    if (open < 0) break;
    const close = text.indexOf("}", open);
    const description = text.indexOf("\n<\n", close);
    const resources = text.indexOf("\n<\n", description + 3);
    const records = text.indexOf("\n<\n", resources + 3);
    if (description < 0 || resources < 0 || records < 0) break;
    const lines = text.slice(resources + 3, records + 1).split("\n");
    // kind, start, size?, loadout, fuel, damage line (five scalar lines in
    // the file; the original skips the unused ones, see parseMissionFile), then
    // the eleven-field records.
    const objects = lines.filter((line) => /^\*?\d+(,\d+){10}$/.test(line.trim()))
      .filter((line) => line.trim().split(",").length === 11);
    const placement = [];
    for (const line of objects) {
      const star = line.trim().startsWith("*");
      const fields = line.trim().replace(/^\*/, "").split(",").map((value) => parseInt(value, 10));
      placement.push({ star, type: fields[0], f1: fields[1] });
    }
    missions.push({ title: text.slice(open + 1, close), records: placement });
    cursor = records + 3;
  }
  return missions;
}

// The thirty object slots as 00021921/00021DB3/00021F39 hold them after the
// factories ran (00023297: aux from f1, 000232B3: the star), reconstructed from
// the mission's records and the number of enemies still alive. Type 0 is the
// fixed slot 31 and takes none of slots 1..30. Targets (f1 2 or 3) are
// destroyed first-to-last until `alive` of them remain.
function stageObjects(records, alive) {
  const objects = [];
  for (let slot = 0; slot <= 130; slot += 1) objects.push({ active: 0, aux: 0, goal: 0 });
  let slot = 30;
  const targets = [];
  for (const record of records) {
    if (record.type === 0) continue;
    const object = objects[slot];
    slot -= 1;
    object.active = 1;
    object.aux = [9, 6, 7, 8, 3][record.f1] ?? 0;                 // 000232E9 / 00023484
    object.goal = record.star ? 1 : 0;                            // 000232B3
    if (record.f1 === 2 || record.f1 === 3) targets.push(object); // 000292C0-000292CC
  }
  const destroyed = targets.length - alive;
  for (let index = 0; index < destroyed; index += 1) targets[index].active = 0;
  return { objects, targetCount: targets.length };
}

async function proveMenus(options = {}) {
  const flat = options.flat || flatImage();
  const { text, pilot, menu, damage } = loadModules();
  const ROSTER = pilot.ROSTER;
  const DEBRIEF = pilot.DEBRIEF;
  const report = [];

  // ---------------------------------------------------------------- data ---
  // Every transcribed text and table against the hashed image.
  {
    for (const [name, entry] of Object.entries(text)) {
      const expected = flat.subarray(entry.address, entry.address + entry.bytes.length);
      assert.equal(Buffer.compare(Buffer.from(entry.bytes), Buffer.from(expected)), 0,
        `ComancheDOSText.${name} differs from flat ${entry.address.toString(16)}`);
    }
    // Structure read out of the image: the seven sentences are 0x2F bytes with
    // a 0 in the last, the score screen begins '|o', and the sentence slot at
    // 000286A1 (a copy of the first) has the same shape.
    for (const sentence of [DEBRIEF.SUCCESS, DEBRIEF.ABORTED, DEBRIEF.RUBBLE, DEBRIEF.DEFEAT,
      DEBRIEF.NO_WINGMAN, DEBRIEF.NO_FUEL, DEBRIEF.SETBACK, DEBRIEF.MESSAGE]) {
      assert.equal(text.debriefScreen.bytes[sentence + DEBRIEF.MESSAGE_LENGTH - 1], 0, `sentence at ${sentence} is not 0x2F bytes`);
    }
    assert.equal(text.debriefScreen.bytes[0x285fa - 0x284b1], 0x7c, "score screen does not begin at 000285FA");
    assert.equal(text.debriefScreen.bytes[DEBRIEF.BYTES - 1], 0xff, "debrief image does not end in 0xFF");
    assert.equal(text.debriefScreen.bytes[DEBRIEF.SCORE - 1], 0x20, "score field is not preceded by 'Score: '");
    assert.equal(text.yourStatsScreen.bytes[text.yourStatsScreen.bytes.length - 1], 0xff, "stats template does not end in 0xFF");
    report.push(`${Object.keys(text).length} text/table ranges equal the image`);
  }

  // ---------------------------------------------------- number formatting ---
  {
    const widthsTested = [];
    for (const value of [0, 7, 10, 99, 100, 4096, 12345678, 4294967295]) {
      for (const width of [1, 3, 4, 8, 10]) {
        const buffer = new Uint8Array(16).fill(0xfc);
        pilot.formatNumber(buffer, 2, width, value);
        const digits = String(value);
        const written = digits.length >= width ? digits.slice(digits.length - width) : digits;
        const expected = new Uint8Array(16).fill(0xfc);
        for (let index = 0; index < written.length; index += 1) expected[2 + width - written.length + index] = written.charCodeAt(index);
        assert.deepEqual(Array.from(buffer), Array.from(expected), `00028C25 value ${value} width ${width}`);
        widthsTested.push(width);
      }
    }
    // 000286F9: 100 * count (low dword) / total, the byte-wide digit fields.
    for (const [total, count] of [[0, 5], [10, 10], [30, 7], [7, 0], [255, 999], [3, 4294967295], [4294967295, 100], [1000, 12345]]) {
      const buffer = new Uint8Array(8).fill(0);
      const acc = { score: 5, lastPct: 0 };
      pilot.percentField(acc, buffer, 1, total, count);
      const product = BigInt(count) * 100n & 0xffffffffn;
      const percent = total === 0 ? 100 : Number(product / BigInt(total));
      assert.equal(acc.lastPct, percent, `000286F9 percent of ${count}/${total}`);
      assert.equal(acc.score, (5 + percent) >>> 0, `000286F9 score of ${count}/${total}`);
      const low = String(percent & 0xff);
      const expected = [0xfd, 0xfd, 0xfd];
      for (let index = 0; index < low.length; index += 1) expected[3 - low.length + index] = low.charCodeAt(index);
      assert.deepEqual(Array.from(buffer.subarray(1, 4)), expected, `000286F9 digits of ${count}/${total}`);
    }
    report.push("number formatter and percentage fields");
  }

  // ------------------------------------------------- the roster (the file) ---
  const rosterFile = new Uint8Array(fs.readFileSync(path.join(ASSET_ROOT, "COMANCHE.NAM")));
  {
    assert.equal(rosterFile.length, ROSTER.BYTES, "COMANCHE.NAM is not the 1,450 bytes 000288A2 writes");
    assert.equal(ROSTER.BASE + ROSTER.CURRENT, 0x29701);
    assert.equal(ROSTER.BASE + ROSTER.CAMPAIGNS, 0x29702);
    assert.equal(ROSTER.BASE + ROSTER.PROGRESS, 0x2970a);
    assert.equal(ROSTER.BASE + ROSTER.SELECTED, 0x2975a);
    assert.equal(ROSTER.BASE + ROSTER.COUNT, 0x2975c);
    assert.equal(ROSTER.BASE + ROSTER.SCORE, 0x2977c);
    assert.equal(ROSTER.BASE + ROSTER.KILLS, 0x2979c);
    assert.equal(ROSTER.BASE + ROSTER.MISSIONS, 0x297bc);
    assert.equal(ROSTER.BASE + ROSTER.DONE, 0x29adc);
    assert.equal(ROSTER.DONE + 80, ROSTER.BYTES, "the completion bytes do not end the file");
    for (let pilotIndex = 0; pilotIndex < 8; pilotIndex += 1) {
      const record = pilotIndex * ROSTER.STRIDE;
      assert.equal(rosterFile[record], 0x20, `record ${pilotIndex} byte 0`);
      assert.equal(rosterFile[record + 1], 0x7c, `record ${pilotIndex} '|b'`);
      assert.equal(rosterFile[record + 2], 0x62);
      assert.equal(rosterFile[record + 6], 0x7c, `record ${pilotIndex} '|g'`);
      assert.equal(rosterFile[record + 7], 0x67);
      assert.equal(rosterFile[record + ROSTER.STRIDE - 1], 0, `record ${pilotIndex} terminator`);
      assert.equal(rosterFile[record + ROSTER.RANK], 0x20, `record ${pilotIndex} rank gap byte`);
    }
    // The shipped file is a fixed point of the ranking and its digit refresh:
    // the original wrote it from its own sort, so re-running both over it must
    // change nothing - a check on offsets, widths and the digit rule at once.
    const roster = Uint8Array.from(rosterFile);
    const selected = pilot.rosterSort(roster, roster[ROSTER.CURRENT]);
    assert.equal(Buffer.compare(Buffer.from(roster), Buffer.from(rosterFile)), 0, "the shipped roster is not a fixed point of 00029F36");
    assert.equal(selected, rosterFile[ROSTER.CURRENT]);
    report.push("roster layout and ranking fixed point");
  }

  // ------------------------------------------------- the ranking reorders ---
  {
    // An independent array-of-pilots transcription of 00029F36 against the
    // byte-offset one: counts chosen with ties and a pilot that must move.
    const base = Uint8Array.from(rosterFile);
    const counts = [2, 9, 9, 0, 5, 5, 1, 7];
    for (let index = 0; index < 8; index += 1) {
      pilot.rosterSet32(base, ROSTER.COUNT + index * 4, counts[index]);
      pilot.rosterSet32(base, ROSTER.SCORE + index * 4, 1000 + index);
      pilot.rosterSet32(base, ROSTER.KILLS + index * 4, 50 + index);
      base[ROSTER.CAMPAIGNS + index] = index & 1;
      for (let slot = 0; slot < 10; slot += 1) {
        base[ROSTER.PROGRESS + index * 10 + slot] = (index * 3 + slot) & 7;
        base[ROSTER.DONE + index * 10 + slot] = (index + slot) & 1;
      }
      for (let slot = 0; slot < 100; slot += 1) base[ROSTER.MISSIONS + index * 100 + slot] = (index + slot) & 1;
      // distinct name records, including the three bytes the original does
      // not swap (offsets 40..42)
      for (let slot = 0; slot < ROSTER.STRIDE - 1; slot += 1) base[index * ROSTER.STRIDE + slot] = 0x41 + index;
    }
    const pilots = [];
    for (let index = 0; index < 8; index += 1) {
      pilots.push({
        campaign: base[ROSTER.CAMPAIGNS + index],
        progress: Array.from(base.subarray(ROSTER.PROGRESS + index * 10, ROSTER.PROGRESS + index * 10 + 10)),
        done: Array.from(base.subarray(ROSTER.DONE + index * 10, ROSTER.DONE + index * 10 + 10)),
        count: counts[index],
        score: 1000 + index,
        kills: 50 + index,
        name: Array.from(base.subarray(index * ROSTER.STRIDE, index * ROSTER.STRIDE + ROSTER.STRIDE)),
        missions: Array.from(base.subarray(ROSTER.MISSIONS + index * 100, ROSTER.MISSIONS + index * 100 + 100)),
        id: index,
      });
    }
    // reference: ebx = 8..2, scan ecx = ebx-1..1, strict less keeps the first
    // found; the swap exchanges every field but only 40 name bytes.
    let tracked = 6;                                              // [00027DAA]
    for (let ebx = 8; ebx >= 2; ebx -= 1) {
      let eax = ebx;
      let low = pilots[ebx - 1].count;
      for (let ecx = ebx - 1; ecx >= 1; ecx -= 1) {
        if (pilots[ecx - 1].count < low) { low = pilots[ecx - 1].count; eax = ecx; }
      }
      const a = pilots[eax - 1];
      const b = pilots[ebx - 1];
      for (const key of ["campaign", "progress", "done", "count", "score", "kills", "missions", "id"]) {
        const held = a[key]; a[key] = b[key]; b[key] = held;
      }
      for (let index = 0; index < 40; index += 1) { const held = a.name[index]; a.name[index] = b.name[index]; b.name[index] = held; }
      if (eax - 1 === tracked) tracked = ebx - 1;
      else if (ebx - 1 === tracked) tracked = eax - 1;
    }
    const roster = Uint8Array.from(base);
    const after = pilot.rosterSort(roster, 6);
    assert.equal(after, tracked, "[00027DAA] does not follow the selected pilot");
    for (let index = 0; index < 8; index += 1) {
      const expected = pilots[index];
      assert.equal(roster[ROSTER.CAMPAIGNS + index], expected.campaign, `campaign byte of rank ${index}`);
      assert.deepEqual(Array.from(roster.subarray(ROSTER.PROGRESS + index * 10, ROSTER.PROGRESS + index * 10 + 10)), expected.progress);
      assert.deepEqual(Array.from(roster.subarray(ROSTER.DONE + index * 10, ROSTER.DONE + index * 10 + 10)), expected.done);
      assert.equal(pilot.rosterGet32(roster, ROSTER.COUNT + index * 4), expected.count);
      assert.equal(pilot.rosterGet32(roster, ROSTER.SCORE + index * 4), expected.score);
      assert.equal(pilot.rosterGet32(roster, ROSTER.KILLS + index * 4), expected.kills);
      assert.deepEqual(Array.from(roster.subarray(ROSTER.MISSIONS + index * 100, ROSTER.MISSIONS + index * 100 + 100)), expected.missions);
      // the name record: 40 bytes moved with the pilot, the last three stay
      const record = Array.from(roster.subarray(index * ROSTER.STRIDE, index * ROSTER.STRIDE + ROSTER.STRIDE));
      const expectedRecord = expected.name.slice();
      for (let at = 40; at < ROSTER.STRIDE; at += 1) expectedRecord[at] = base[index * ROSTER.STRIDE + at];
      // the digits of 0002A0AD overwrite bytes 3..5
      const digits = String(expected.count).padStart(3, "0").split("").map((c) => c.charCodeAt(0));
      if (digits[0] === 0x30) digits[0] = 0xfd;
      if (digits[1] === 0x30 && digits[0] === 0xfd) digits[1] = 0xfd;
      else if (digits[1] === 0x30) digits[1] = 0xfd;
      expectedRecord[3] = digits[0];
      expectedRecord[4] = digits[1];
      expectedRecord[5] = digits[2];
      assert.deepEqual(record, expectedRecord, `name record of rank ${index}`);
    }
    // descending order by won count, ties in the order the scan leaves them
    const order = [];
    for (let index = 0; index < 8; index += 1) order.push(pilot.rosterGet32(roster, ROSTER.COUNT + index * 4));
    for (let index = 1; index < 8; index += 1) assert.ok(order[index - 1] >= order[index], `rank order ${order.join(",")}`);
    assert.equal(roster[ROSTER.CURRENT], after, "00029701 does not take [00027DAA]");
    // the three bytes the original leaves in place, stated plainly: the last
    // two rank slots (offsets 40, 41) and the terminator (42) of every record
    for (let index = 0; index < 8; index += 1) {
      for (let at = 40; at < ROSTER.STRIDE; at += 1) {
        assert.equal(roster[index * ROSTER.STRIDE + at], base[index * ROSTER.STRIDE + at], `record ${index} byte ${at} moved with the pilot`);
      }
    }
    report.push("ranking sort reorders by the DOS scan (40-byte name swap)");
  }

  // ------------------------------------------------------ mission lists ---
  const files = {};
  for (const fileName of ["0.MIS", "1.MIS"]) {
    const raw = new Uint8Array(fs.readFileSync(path.join(ASSET_ROOT, fileName)));
    const image = menu.decodeMissionImage(raw);
    const list = menu.scanMissionList(image, raw.length);
    files[fileName] = { raw, image, list };
    // independent: the titles, stars and digits by regular expression
    const source = Buffer.from(image.subarray(0, raw.length)).toString("latin1");
    const titleEnd = source.indexOf("}");
    const pattern = /\{([^}]*)\}(\*(\d)?)?/g;
    pattern.lastIndex = titleEnd + 1;
    const expected = [];
    for (let match = pattern.exec(source); match && expected.length < 10; match = pattern.exec(source)) {
      if (match[1].includes("\n")) continue;
      expected.push({ name: match[1], star: match[2] ? 1 : 0, promo: match[3] !== undefined ? parseInt(match[3], 10) + 1 : 0, end: match.index + match[1].length + 2 });
    }
    assert.equal(list.count, 10, `${fileName} mission count`);
    for (let index = 0; index < 10; index += 1) {
      const slot = index * menu.NAME_SLOT;
      assert.equal(Buffer.from(list.names.subarray(slot, slot + 4)).toString("latin1"), "|g  ", `${fileName} row ${index} colour prefix`);
      const shown = Buffer.from(list.names.subarray(slot + 4, slot + 0x1f)).toString("latin1").replace(/\xfc+$/, "");
      assert.equal(shown, expected[index].name, `${fileName} row ${index} name`);
      assert.equal(list.names[slot + 0x1f], 0, `${fileName} row ${index} terminator`);
      assert.equal(list.star[index], expected[index].star, `${fileName} row ${index} star`);
      assert.equal(list.promo[index], expected[index].promo, `${fileName} row ${index} promotion digit`);
      assert.equal(list.text[index], expected[index].end, `${fileName} row ${index} description pointer`);
    }
    // 1.MIS's 11th '{' is a description block; the scan must stop at ten
    assert.equal(list.names[10 * menu.NAME_SLOT + 2] === 0xff || list.names[10 * menu.NAME_SLOT] === 0, true);
  }
  report.push("mission list scan of 0.MIS and 1.MIS");

  // ---------------------------------------------------------- row colours ---
  {
    const { list } = files["1.MIS"];
    const rosterCopy = Uint8Array.from(rosterFile);
    const pilotIndex = 0;
    const digit = 1;
    const wonFlags = (pattern) => {
      const flags = new Uint8Array(10);
      for (const index of pattern) flags[index] = 1;
      return flags;
    };
    const colourString = (flags) => {
      const names = Uint8Array.from(list.names);
      const colours = menu.missionRowColours(flags, list.star, names);
      for (let index = 0; index < 10; index += 1) assert.equal(names[index * 0x20 + 1], colours[index], "the row's own letter and [00029F22] disagree");
      return Array.from(colours.subarray(0, 10), (value) => String.fromCharCode(value)).join("");
    };
    // 1.MIS stars rows 3..9 (the file's own "*" after their braces).
    assert.equal(Array.from(list.star).join(""), "0001111111");
    assert.equal(colourString(wonFlags([])), "gggooooooo", "nothing flown");
    assert.equal(colourString(wonFlags([0])), "bggooooooo", "first flown");
    assert.equal(colourString(wonFlags([0, 1, 2])), "bbbgoooooo", "three flown opens the first starred row");
    assert.equal(colourString(wonFlags([0, 1, 2, 3])), "bbbbgooooo", "four flown");
    assert.equal(colourString(wonFlags([1, 2])), "gbbooooooo", "a gap keeps starred rows locked");
    assert.equal(colourString(wonFlags([0, 1, 3])), "bbgboooooo", "a won starred row behind a gap is blue, the next starred one stays locked");
    // the choice: the row is stored before the lock test
    const colours = menu.missionRowColours(wonFlags([0]), list.star, Uint8Array.from(list.names));
    const digits = Uint8Array.from([0x30, 0x31]);
    const locked = menu.missionListChoice(rosterCopy, digits, colours, 5);
    assert.equal(locked.locked, true, "an orange row is refused");
    assert.equal(rosterCopy[ROSTER.SELECTED], 5, "the refused row is still stored as the mission chosen last");
    assert.equal(rosterCopy[ROSTER.PROGRESS + pilotIndex * 10 + digit], 5, "and as the campaign's progress byte");
    const open = menu.missionListChoice(rosterCopy, digits, colours, 1);
    assert.equal(open.locked, false);
    report.push("mission list colours and lock");
  }

  // -------------------------------------------------------------- briefing ---
  {
    const widths = text.charWidths.bytes;
    const lineWidth = (line) => Array.from(line).reduce((sum, character) => sum + widths[character.charCodeAt(0)], 0);
    const { image, list } = files["1.MIS"];
    const first = menu.buildBriefing(image, list.names, list.text[0], 0);
    // The original's own screen shows the first mission as exactly these four
    // lines. They are in 1.MIS (campaign file index 1: the pilots' campaign
    // byte); 0.MIS's first mission is "Oil Tank Holiday", a different text.
    assert.deepEqual(first.lines.map((line) => line.replace(/ +$/, "")), [
      "If you're going to see the world, it might as well",
      "be from behind enemy lines. Fortunately it's night",
      "and the enemy hasn't spotted you yet. Pick'em off",
      "one by one, and let your wingman have some fun.",
    ], "1.MIS mission 0 briefing is not the four lines the original shows");
    assert.equal(first.bytes[0], 0x7c);
    assert.equal(first.bytes[1], 0x62);
    // The 0x1C name bytes are the slot's name, its 0xFC pad and the slot's own
    // 0 terminator (00029098 copies 0x1C from 00029D99, which ends at the
    // slot's last byte), so the title line ends in that 0.
    assert.equal(Buffer.from(first.bytes.subarray(3, 3 + 0x1c)).toString("latin1").replace(/[\xfc\x00]+$/, ""), "Werewolves on Patrol");
    assert.equal(first.bytes[3 + 0x1b], 0, "the name copy ends in the slot's 0 terminator");
    assert.equal(first.bytes[first.bytes.length - 1], 0xff);
    // Every line of every briefing of both campaigns: none wider than 0x118,
    // and a line only ends where the next word would not fit.
    let lineCount = 0;
    for (const [fileName, { image: missionImage, list: missionList }] of Object.entries(files)) {
      for (let mission = 0; mission < 10; mission += 1) {
        const built = menu.buildBriefing(missionImage, missionList.names, missionList.text[mission], mission);
        const body = built.lines;
        // a '^' ends a paragraph early, so only text without one is held to
        // "a line ends where the next word does not fit"
        const paragraph = Buffer.from(missionImage.subarray(missionList.text[mission])).toString("latin1")
          .split("\n<\n")[0].includes("^");
        for (let index = 0; index < body.length; index += 1) {
          const width = lineWidth(body[index]);
          assert.ok(width <= 0x118, `${fileName} mission ${mission} line ${index} is ${width} wide`);
          if (index + 1 < body.length && body[index + 1].length > 0 && !paragraph) {
            const word = body[index + 1].split(" ")[0];
            assert.ok(width + widths[0x20] + lineWidth(word) > 0x118,
              `${fileName} mission ${mission} line ${index} ends before the next word fits`);
          }
          lineCount += 1;
        }
        // no text is lost: the lines, joined, equal the description with its
        // white space folded (a '^' is the only code that ends a paragraph)
        const sourceText = Buffer.from(missionImage.subarray(missionList.text[mission], missionImage.length)).toString("latin1");
        const description = sourceText.slice(sourceText.indexOf("\n") + 1, sourceText.indexOf("\n<")).replace(/\r/g, "")
          .replace(/\^/g, " ").replace(/\s+/g, " ").trim();
        assert.equal(body.join(" ").replace(/\s+/g, " ").trim(), description, `${fileName} mission ${mission} lost text`);
      }
    }
    // The 0x118 boundary, by construction: a string of 'i' wraps exactly where
    // the width table says, with no space to break at.
    const probe = "x".repeat(60);
    const synthetic = new Uint8Array(Buffer.from(`{c}\r\n{m}\r\n${probe}\r\n<\r\n`, "latin1"));
    const synList = menu.scanMissionList(synthetic, synthetic.length);
    const built = menu.buildBriefing(synthetic, synList.names, synList.text[0], 0);
    let sum = 0;
    let fits = 0;
    while (sum + widths[0x78] <= 0x118) { sum += widths[0x78]; fits += 1; }
    assert.equal(built.lines[0].length, fits + 1, "a line with no space breaks after the overflowing character");
    // the line skipper: blank, indented and ';' lines are passed over
    const skipImage = new Uint8Array(Buffer.from("{t}*\r\n\r\n   indented\r\n;comment\r\nText\r\n", "latin1"));
    assert.equal(Buffer.from(skipImage.subarray(menu.skipLine(skipImage, 3), menu.skipLine(skipImage, 3) + 4)).toString("latin1"), "Text");
    assert.throws(() => menu.skipLine(new Uint8Array(0x200).fill(0x41), 0), /no line end/);
    report.push(`briefing: the original's four lines, ${lineCount} wrapped lines within 0x118`);
  }

  // ------------------------------------------------------- Your Stats text ---
  {
    const roster = Uint8Array.from(rosterFile);
    const screen = menu.yourStatsScreen(roster, 0);
    const base = text.yourStatsScreen.address;
    const shown = Buffer.from(screen).toString("latin1");
    assert.ok(shown.includes("Total Player Score: "), "template text");
    // pilot 0 of the shipped file: score 5523, 1 mission won, 120 kills
    assert.equal(pilot.rosterGet32(roster, ROSTER.SCORE), 5523);
    assert.equal(Buffer.from(screen.subarray(0x28af6 - base, 0x28afe - base)).toString("latin1"), "\xfc\xfc\xfc\xfc5523");
    assert.equal(Buffer.from(screen.subarray(0x28b02 - base, 0x28b06 - base)).toString("latin1"), "\xfc\xfc1\xfc");
    assert.equal(Buffer.from(screen.subarray(0x28b1c - base, 0x28b20 - base)).toString("latin1"), "\xfc120");
    assert.deepEqual(Array.from(screen.subarray(0x28abd - base, 0x28abd - base + 0x21)), Array.from(roster.subarray(9, 9 + 0x21)),
      "the name field is the record's bytes 9..41");
    report.push("Your Stats template patch");
  }

  // ------------------------------------------------------ options (Game) ---
  {
    const settingsFile = new Uint8Array(fs.readFileSync(path.join(ASSET_ROOT, "COMANCHE.MNU")));
    assert.equal(settingsFile.length, menu.SETTINGS_BYTES, "COMANCHE.MNU is not the 35 bytes 00026D94 writes");
    const braces = {};
    for (const [code, entry] of Object.entries(menu.SWITCHES)) {
      // the menu text takes its braces from the settings block when the menu
      // opens (000268A5-000268BE), so the text starts as the file says
      assert.ok(flat[entry.brace] === 0x7b || flat[entry.brace] === 0x7d, `key ${code}: no brace at ${entry.brace.toString(16)}`);
      braces[entry.brace] = settingsFile[entry.setting - 0x25dbc];
      assert.equal(entry.setting - 0x25dbc, menu.SETTINGS_SWITCH + (entry.setting - 0x25dd8), "settings byte offset");
    }
    const state = { settings: Uint8Array.from(settingsFile), braces: { ...braces } };
    // the seven store targets are consecutive bytes 25DD8..25DDE
    assert.deepEqual(Object.values(menu.SWITCHES).map((entry) => entry.setting).sort(), [0x25dd8, 0x25dd9, 0x25dda, 0x25ddb, 0x25ddc, 0x25ddd, 0x25dde]);
    for (const code of Object.keys(menu.SWITCHES)) {
      const entry = menu.SWITCHES[code];
      const before = state.braces[entry.brace];
      assert.equal(menu.optionsToggle(state, Number(code)), true);
      assert.equal(state.braces[entry.brace], before ^ 6, `key ${code} brace`);
      assert.equal(state.settings[entry.setting - 0x25dbc], before ^ 6, `key ${code} settings byte`);
      menu.optionsToggle(state, Number(code));
      assert.equal(state.braces[entry.brace], before, `key ${code} toggles back`);
    }
    assert.equal(menu.optionsToggle(state, 0x7f), false);
    assert.equal(Buffer.compare(Buffer.from(state.settings), Buffer.from(settingsFile)), 0, "toggling twice leaves the file unchanged");
    const save = menu.optionsGameAction(state, 2);
    assert.equal(save.action, "save-settings");
    assert.equal(save.file, "Comanche.MNU");
    assert.equal(save.bytes.length, 35);
    assert.equal(Buffer.compare(Buffer.from(save.bytes), Buffer.from(settingsFile)), 0);
    assert.equal(menu.optionsGameAction(state, 3).action, "abort-mission");
    assert.equal(menu.optionsGameAction(state, 4).action, "exit");
    assert.equal(menu.optionsGameAction(state, 0).action, "about");
    assert.equal(menu.optionsGameAction(state, 0x20).action, "none");
    report.push("options toggles, Save Menu Settings, About");
  }

  // ------------------------------------------------------------ name entry ---
  {
    const scancodeOf = (character, shifted) => {
      const table = shifted ? text.keyShift.bytes : text.keyLower.bytes;
      const index = table.indexOf(character.charCodeAt(0));
      assert.ok(index > 0, `no scancode for ${character}`);
      return index;
    };
    const type = (state, string) => {
      for (const character of string) {
        const shifted = character !== character.toLowerCase();
        const lower = character.toLowerCase();
        const scancode = scancodeOf(shifted ? character : lower, shifted);
        assert.equal(menu.nameEntryKey(state, scancode, shifted), null);
      }
    };
    // FIFO: newest first
    let fifo = 0;
    for (const code of [0x1e, 0x30, 0x2e]) fifo = menu.keyFifoPush(fifo, code);
    const popped = [];
    for (let index = 0; index < 4; index += 1) { const step = menu.keyFifoPop(fifo); popped.push(step.code); fifo = step.fifo; }
    assert.deepEqual(popped, [0x2e, 0x30, 0x1e, 0], "the key FIFO gives the newest key first");

    const state = menu.nameEntryStart();
    assert.deepEqual(Array.from(state.field.subarray(0, 3)), [0x5f, 0xfc, 0xfc]);
    type(state, "Ace");
    assert.equal(state.cursor, 3);
    assert.equal(menu.nameEntryKey(state, 0x0e, false), null);
    assert.equal(state.cursor, 2);
    assert.deepEqual(Array.from(state.field.subarray(0, 4)), [0x41, 0x63, 0x5f, 0xfc], "a backspace blanks the place after the cursor");
    type(state, "k");
    assert.equal(menu.nameEntryKey(state, 0x39, false), null);   // the space bar: [000019E9 + 0x39] = 0x20
    assert.equal(state.cursor, 4);
    // Return accepts: the cursor byte becomes 0xFC and the record is built.
    const accept = menu.nameEntryKey(state, 0x1c, false);
    assert.equal(accept, "accept");
    assert.equal(state.field[4], 0xfc);
    const roster = Uint8Array.from(rosterFile);
    const slot = 7;
    for (let index = 0; index < 10; index += 1) { roster[ROSTER.PROGRESS + slot * 10 + index] = 3; roster[ROSTER.DONE + slot * 10 + index] = 1; }
    roster[ROSTER.CAMPAIGNS + slot] = 1;
    pilot.rosterSet32(roster, ROSTER.COUNT + slot * 4, 4);
    pilot.rosterSet32(roster, ROSTER.SCORE + slot * 4, 4);
    pilot.rosterSet32(roster, ROSTER.KILLS + slot * 4, 4);
    roster.fill(1, ROSTER.MISSIONS + slot * 100, ROSTER.MISSIONS + slot * 100 + 100);
    // the replaced pilot had four missions won and ranks above the zero-count
    // pilots; the new one has none, so the ranking puts them at the bottom
    // of the order again: with pilot 0 on one win and the rest on none they stay
    // where they are
    pilot.rosterSet32(roster, ROSTER.COUNT + slot * 4, 0);
    const newIndex = menu.createPilot(roster, slot, state.field);
    assert.equal(newIndex, slot, "the new pilot's index after the ranking");
    const bytes = Array.from(roster.subarray(slot * ROSTER.STRIDE, (slot + 1) * ROSTER.STRIDE));
    const expectedRecord = [...text.nameRecordPrefix.bytes, ...state.field.subarray(0, ROSTER.NAME_CHARS), ...text.nameRecordSuffix.bytes];
    assert.equal(expectedRecord.length, ROSTER.STRIDE, "9 + 0x16 + 12 is one record");
    assert.deepEqual(bytes, expectedRecord, "the new pilot's 43-byte record");
    assert.equal(Buffer.from(bytes.slice(9, 13)).toString("latin1"), "Ack ", "the typed name");
    assert.equal(bytes[13], 0xfc, "and the field's pad after it");
    for (let index = 0; index < 10; index += 1) {
      assert.equal(roster[ROSTER.PROGRESS + slot * 10 + index], 0);
      assert.equal(roster[ROSTER.DONE + slot * 10 + index], 0);
    }
    assert.equal(pilot.rosterGet32(roster, ROSTER.COUNT + slot * 4), 0);
    assert.equal(roster[ROSTER.CAMPAIGNS + slot], 0);
    assert.ok(roster.subarray(ROSTER.MISSIONS + slot * 100, ROSTER.MISSIONS + slot * 100 + 100).every((value) => value === 0));
    // the width stop: wide characters stop the cursor where the table's sum
    // reaches 0x6C; narrow ones stop at the 0x16th place
    const wide = menu.nameEntryStart();
    const widths = text.charWidths.bytes;
    let sum = 0;
    let expectedCursor = 0;
    for (let index = 0; index < 30; index += 1) {
      menu.nameEntryKey(wide, scancodeOf("W", true), true);
      sum += widths[0x57];
      if (sum < 0x6c && expectedCursor < 0x16) expectedCursor += 1;
    }
    assert.equal(wide.cursor, expectedCursor, "the width stop");
    assert.ok(wide.cursor < 0x16);
    const narrow = menu.nameEntryStart();
    for (let index = 0; index < 40; index += 1) menu.nameEntryKey(narrow, scancodeOf("i", false), false);
    assert.equal(narrow.cursor, 0x16, "the cursor stops at 0x16");
    // Esc and an empty Return leave without a pilot
    assert.equal(menu.nameEntryKey(menu.nameEntryStart(), 1, false), "cancel");
    assert.equal(menu.nameEntryKey(menu.nameEntryStart(), 0x1c, false), "cancel");
    report.push("new-pilot name entry and record");
  }

  // ------------------------------------------------- damage (listing only) ---
  {
    const base = () => ({
      cells: Uint8Array.from([4, 2, 4, 2, 2, 2, 5, 2]),
      hullPoints: 30,
      deathCue: 0,
      deathTimer: 100,
      axis1: 123,
      axis2: -77,
      collective: 0x40,
      altitude: 0x80,
      previousAltitude: 0x7e,
      maxSpeed: 0x1800000,
      shakeCountdown: 0,
      viewVariant: 1,
      crashDrop: 0,
      rng: 0x12345678,
      x: 0x10000000,
      y: 0x08000000,
      frameX: 0x0fff0000,
      frameY: 0x07ff0000,
      fwd: 0x400000,
      lat: -0x100000,
      torque: 0,
    });
    // a live pilot: the death block does nothing
    const live = base();
    assert.deepEqual(damage.deathBlock(live), { missionEnd: false, chaseView: false, wreckFromSlot: 0, sounds: [] });
    assert.equal(live.axis1, 123);
    // a wreck with the hull gone: rotor stopped, ten-tick shake, screen sinks
    // 0x52 a tick, the chase view at 0xE6A, a wreck puff when rng & 0xF == 0
    const wreck = base();
    wreck.deathCue = 1;
    wreck.hullPoints = -1;
    wreck.rng = 0x1230;
    const first = damage.deathBlock(wreck);
    assert.equal(wreck.deathTimer, 99);
    assert.equal(wreck.collective, 0);
    assert.equal(wreck.axis1, 0);
    assert.equal(wreck.axis2, 0);
    assert.equal(wreck.shakeCountdown, 10);
    assert.equal(wreck.crashDrop, 0x52);
    assert.equal(first.wreckFromSlot, 0x1f);
    assert.equal(first.chaseView, false);
    let ticks = 1;
    let chase = false;
    while (!chase) {
      const step = damage.deathBlock(wreck);
      ticks += 1;
      chase = step.chaseView;
      if (chase) assert.deepEqual(step.sounds, [0x0b]);
    }
    assert.equal(wreck.crashDrop, 0x52 * ticks);
    assert.equal(wreck.crashDrop >= 0xe6a && wreck.crashDrop - 0x52 < 0xe6a, true, "the chase view starts at the first tick past 0xE6A");
    assert.equal(ticks, Math.ceil(0xe6a / 0x52));
    // external views do not sink
    const external = base();
    external.deathCue = 1; external.hullPoints = -3; external.viewVariant = 6; external.rng = 1;
    damage.deathBlock(external);
    assert.equal(external.crashDrop, 0);
    // the countdown ends the flight at zero
    const timer = base();
    timer.deathCue = 1; timer.hullPoints = -1;
    let ended = 0;
    for (let tick = 1; tick <= 100; tick += 1) { if (damage.deathBlock(timer).missionEnd) { ended = tick; break; } }
    assert.equal(ended, 100, "a wreck flies 100 ticks");
    // the sinking wreck: the hull still non-negative
    const sinking = base();
    sinking.deathCue = 1; sinking.hullPoints = 4; sinking.altitude = 0xe0;
    damage.deathBlock(sinking);
    assert.equal(sinking.collective, 0xfe);
    assert.equal(sinking.altitude, 0xe4);
    assert.equal(sinking.axis2, 0);
    damage.deathBlock(sinking);
    assert.equal(sinking.altitude, 0xe8);
    assert.equal(sinking.axis2, -0x15e, "from altitude 0xE6 the speed stick is pulled to -0x15E");
    const high = base();
    high.deathCue = 1; high.hullPoints = 0; high.altitude = 0xfb;
    damage.deathBlock(high);
    assert.equal(high.altitude, 0xfb, "above 0xFA the altitude is not raised");
    // engine, T gauge, tail rotor
    const engine = base();
    engine.cells[1] = 0xff;
    damage.engineDamage(engine);
    assert.equal(engine.altitude, 0x7f);
    assert.equal(engine.maxSpeed, 0x800000);
    const low = base();
    low.cells[1] = 0x80; low.altitude = 0x0a;
    damage.engineDamage(low);
    assert.equal(low.altitude, 0x0a);
    assert.equal(low.maxSpeed, 0x1800000);
    // stick -77: sar 5 = -3, one's complement = 2; collective 0x40 * 3 = 192
    // gives 194 (< 0xC8); 194 << 8 is past 0x8000, so the pitch word is capped
    const gauge = base();
    assert.deepEqual(damage.torqueGauge(gauge), { torque: 194, enginePitch: 0x8000 + 0x4000 });
    assert.equal(gauge.torque, 194);
    const slow = base();
    slow.axis2 = 0; slow.collective = 0x10;
    assert.deepEqual(damage.torqueGauge(slow), { torque: 0x30, enginePitch: 0x3000 + 0x4000 });
    const hurt = base();
    hurt.cells[1] = 0x80;
    hurt.axis2 = 0;
    hurt.collective = 0x20;
    assert.equal(damage.torqueGauge(hurt).torque, 0x60 >> 1);
    const cap = base();
    cap.axis2 = 0x7fff; cap.collective = 0xff;
    assert.equal(damage.torqueGauge(cap).torque, 0xc8);
    assert.equal(damage.tailRotorYaw({ cells: Uint8Array.from([0x80, 0, 0, 0, 0, 0, 0, 0]) }), 0x600000);
    assert.equal(damage.tailRotorYaw({ cells: Uint8Array.from([0x7f, 0, 0, 0, 0, 0, 0, 0]) }), 0);
    // the collision test: altitude half-difference and the position box
    const objectsAt = (entry) => { const list = new Array(31).fill(null); list[12] = entry; return list; };
    const near = { active: 1, altitude: 0x80, x: 0x10100000, y: 0x08000000, state: 0x23cf0 };
    assert.equal(damage.objectCollision(base(), objectsAt(near)), 12);
    // cdq / xor eax, edx takes the one's complement of a negative difference,
    // so the box is one unit wider on the side where the object is ahead
    // (dx = x - x_n < 0): |dx| <= 0x1400001 there, <= 0x1400000 behind it.
    assert.equal(damage.objectCollision(base(), objectsAt({ ...near, x: 0x10000000 + 0x1400001 })), 12, "ahead by 0x1400001");
    assert.equal(damage.objectCollision(base(), objectsAt({ ...near, x: 0x10000000 + 0x1400002 })), 0, "ahead by 0x1400002");
    assert.equal(damage.objectCollision(base(), objectsAt({ ...near, x: 0x10000000 - 0x1400000 })), 12, "behind by 0x1400000");
    assert.equal(damage.objectCollision(base(), objectsAt({ ...near, x: 0x10000000 - 0x1400001 })), 0, "behind by 0x1400001");
    assert.equal(damage.objectCollision(base(), objectsAt({ ...near, y: 0x08000000 + 0x1400001 })), 12, "ahead in y by 0x1400001");
    assert.equal(damage.objectCollision(base(), objectsAt({ ...near, y: 0x08000000 - 0x1400001 })), 0, "behind in y by 0x1400001");
    assert.equal(damage.objectCollision(base(), objectsAt({ ...near, state: 0x237b0 })), 0, "an explosion is not hit");
    assert.equal(damage.objectCollision(base(), objectsAt({ ...near, active: 0 })), 0);
    // the altitude test: sub al / rcr al,1 / cbw / xor al,ah keeps (diff >> 1)
    // for a positive difference and its one's complement for a negative one,
    // so the player may be up to 0x1F above the object and 0x20 below it
    assert.equal(damage.objectCollision(base(), objectsAt({ ...near, altitude: 0x80 - 0x1f })), 12, "player above by 0x1F");
    assert.equal(damage.objectCollision(base(), objectsAt({ ...near, altitude: 0x80 - 0x20 })), 0, "player above by 0x20");
    assert.equal(damage.objectCollision(base(), objectsAt({ ...near, altitude: 0x80 + 0x20 })), 12, "player below by 0x20");
    assert.equal(damage.objectCollision(base(), objectsAt({ ...near, altitude: 0x80 + 0x21 })), 0, "player below by 0x21");
    // the crash response: restore, bounce, shake, altitude, damage
    const crash = base();
    crash.rng = 0x00000001;
    const result = damage.crashResponse(crash);
    assert.equal(crash.x, 0x0fff0000);
    assert.equal(crash.y, 0x07ff0000);
    assert.equal(crash.lat, 0x100000);
    assert.equal(crash.fwd, -0x400000 >> 1);
    assert.equal(crash.shakeCountdown, 10);
    assert.equal(crash.altitude, 0x7e + 4);
    // rng: low bits 1 < 2: sound 3; rng + x, then bytes of the sum
    const sum = (1 + 0x0fff0000) >>> 0;
    const low8 = sum & 0xff;
    const expectedCells = Uint8Array.from([4, 2, 4, 2, 2, 2, 5, 2]);
    expectedCells[low8 & 7] -= 1;
    expectedCells[low8 >> 5] -= 1;
    assert.deepEqual(Array.from(crash.cells), Array.from(expectedCells));
    const rotated = ((sum >>> 8) | (sum << 24)) >>> 0;
    assert.equal(crash.rng, rotated);
    assert.equal(crash.hullPoints, 30 - (rotated & 3));
    assert.equal(crash.deathCue, 0);
    assert.deepEqual(result.sounds, [3, 0xff]);
    // a fatal hit, and a wreck takes no bounce and no damage
    const fatal = base();
    fatal.hullPoints = 0; fatal.rng = 0x03000000 - 0x0fff0000;
    for (let attempt = 0; attempt < 4 && fatal.deathCue === 0; attempt += 1) { fatal.hullPoints = 1; fatal.rng = (0x03000000 + attempt) >>> 0; damage.crashResponse(fatal); }
    const dead = base();
    dead.deathCue = 1;
    dead.cells.fill(9);
    damage.crashResponse(dead);
    assert.deepEqual(Array.from(dead.cells), [9, 9, 9, 9, 9, 9, 9, 9]);
    assert.equal(dead.fwd, 0x400000, "a wreck is not bounced");
    assert.equal(dead.x, 0x0fff0000, "but the position is restored");
    const repaired = base();
    repaired.hullPoints = -5; repaired.deathCue = 1; repaired.deathTimer = 7; repaired.maxSpeed = 0x800000;
    damage.repairAll(repaired, 31);
    assert.equal(repaired.hullPoints, 31);
    assert.equal(repaired.deathTimer, 0x64);
    assert.equal(repaired.deathCue, 0);
    assert.equal(repaired.maxSpeed, 0x1800000);
    assert.deepEqual(Array.from(repaired.cells), [10, 10, 10, 10, 10, 10, 10, 10]);
    report.push("damage chain unit cases (listing transcription)");
  }

  // ----------------------------------------- DOS captures: statistics etc. ---
  const dosResults = [];
  {
    const live = [
      ["mission-live-abort300", "1.MIS", "stats", "enter", null],
      ["mission-live-win300", "1.MIS", "stats", "enter", null],
    ];
    const demo = [
      ["mission-end-c213", "0.MIS", 1],
      ["mission-end-c2405", "0.MIS", 1],
    ];
    const compare = (name, expected, result) => {
      // the buffer 000285FA..000286F9 (0x100 bytes) of the capture
      // (the dump is 0x100 bytes and its last byte, 000286F9, is the code after
      // the 584-byte image, so the comparison ends at the image's 0xFF)
      const offset = 0x285fa - DEBRIEF.BASE;
      const length = Math.min(expected.length, DEBRIEF.BYTES - offset);
      const got = Buffer.from(result.text.subarray(offset, offset + length)).toString("latin1");
      assert.equal(got, Buffer.from(expected.subarray(0, length)).toString("latin1"), `${name}: the patched score screen differs from the DOS buffer`);
    };
    for (const [name, fileName, statsKey, enterKey] of live) {
      const capture = readCapture(name);
      if (!capture) { dosResults.push(`SKIP ${name} (capture absent)`); continue; }
      const enter = capture[enterKey];
      const stats = capture[statsKey];
      const state = hex(enter.globals_19D2C);
      const counters = hex(stats.counters_28250);
      const hull = hex(enter.hull_19E40);
      const records = missionRecords(menu, fileName)[0].records;
      // [28250] alive enemies after the statistics, from the capture; the
      // mission's records stage the rest (all starred records are targets here)
      const staged = stageObjects(records, dword(counters, 0));
      assert.equal(staged.targetCount, counters[0x10], `${name}: the mission's target count [00028260]`);
      const result = pilot.missionStatistics({
        fuel: dword(state, 0x34) | 0,
        fuelMax: dword(state, 0x30),
        hullNow: dword(hull, 0),
        hullMax: dword(hull, 4),
        objects: staged.objects,
        targetCount: staged.targetCount,
        ammo: Array.from({ length: 6 }, (_, index) => dword(state, index * 4)),
        loadout: Array.from({ length: 6 }, (_, index) => dword(state, 0x18 + index * 4)),
        allyWrecked: hex(enter.flag_22384)[0],
        text: text.debriefScreen.bytes,
      });
      compare(name, hex(stats.screen_285FA), result);
      assert.equal(result.enemiesAlive, dword(counters, 0), `${name}: [00028250]`);
      assert.equal(result.kills, dword(counters, 4), `${name}: [00028254]`);
      assert.equal(result.score, dword(counters, 8), `${name}: [00028258]`);
      assert.equal(result.lastPct, dword(counters, 12), `${name}: [0002825C]`);
      assert.equal(result.hullNow, dword(hex(stats.hull_19E40), 0), `${name}: [00019E40] after the step`);
      assert.equal(result.hullMax, dword(hex(stats.hull_19E40), 4), `${name}: [00019E44] after the step`);
      dosResults.push(`PASS ${name} statistics (${result.score} points)`);

      // the pilot record: the roster before, after 0002873D's record update,
      // the ranking and the save, against the original's own bytes
      const pre = hex(enter.roster_29570).slice(0x12, 0x12 + ROSTER.BYTES);
      const post = hex(capture.debrief.roster_29570).slice(0x12, 0x12 + ROSTER.BYTES);
      const roster = Uint8Array.from(pre);
      const list = menu.scanMissionList(menu.decodeMissionImage(new Uint8Array(fs.readFileSync(path.join(ASSET_ROOT, fileName)))), fs.statSync(path.join(ASSET_ROOT, fileName)).size);
      const mission = {
        shake: { phase: 3, countdown: 5 },
        crashDrop: 9,
        fuel: dword(state, 0x34) | 0,
        fuelMax: dword(state, 0x30),
        hullNow: dword(hull, 0),
        hullMax: dword(hull, 4),
        objects: staged.objects,
        targetCount: staged.targetCount,
        ammo: Array.from({ length: 6 }, (_, index) => dword(state, index * 4)),
        loadout: Array.from({ length: 6 }, (_, index) => dword(state, 0x18 + index * 4)),
        allyWrecked: hex(enter.flag_22384)[0],
      };
      const outcome = pilot.missionEnd({
        mission,
        roster,
        session: { attractActive: false, missionFlown: 1 },
        tables: { campaignDigits: Uint8Array.from([0x30, 0x31]), star: list.star, promo: list.promo },
        text: text.debriefScreen.bytes,
      });
      assert.equal(outcome.route, "debrief");
      assert.equal(outcome.won, name.includes("win"), `${name}: the win test`);
      assert.equal(Buffer.compare(Buffer.from(roster), Buffer.from(post)), 0, `${name}: the roster after 0002873D differs from the original's`);
      compare(name, hex(capture.debrief.screen_285FA), { text: outcome.debriefText });
      assert.equal(mission.shake.phase, 0);
      assert.equal(mission.shake.countdown, 0);
      assert.equal(mission.crashDrop, 0);
      assert.ok(mission.objects.slice(1, 131).every((object) => object.active === 0), "000227A6 leaves an active slot");
      dosResults.push(`PASS ${name} pilot record and debrief (${outcome.won ? "won" : "aborted"})`);
    }
    for (const [name, fileName, missionIndex] of demo) {
      const capture = readCapture(name);
      if (!capture) { dosResults.push(`SKIP ${name} (capture absent)`); continue; }
      const state = hex(capture.globals_19D2C);
      const counters = hex(capture.counters_28250);
      const hull = hex(capture.hull_19E40);
      const records = missionRecords(menu, fileName)[missionIndex].records;
      const staged = stageObjects(records, dword(counters, 0));
      assert.equal(staged.targetCount, counters[0x10], `${name}: [00028260]`);
      const result = pilot.missionStatistics({
        fuel: dword(state, 0x34) | 0,
        fuelMax: dword(state, 0x30),
        hullNow: dword(hull, 0) - 1,                    // the capture is after the +1 of 00028274
        hullMax: dword(hull, 4) - 1,
        objects: staged.objects,
        targetCount: staged.targetCount,
        ammo: Array.from({ length: 6 }, (_, index) => dword(state, index * 4)),
        loadout: Array.from({ length: 6 }, (_, index) => dword(state, 0x18 + index * 4)),
        allyWrecked: hex(capture.flag_22384)[0],
        text: text.debriefScreen.bytes,
      });
      compare(name, hex(capture.buffers_285FA).subarray(0, 0x100), result);
      assert.equal(result.score, dword(counters, 8));
      assert.equal(result.kills, dword(counters, 4));
      assert.equal(result.lastPct, dword(counters, 12));
      dosResults.push(`PASS ${name} statistics (${result.score} points)`);
    }
  }

  // The damage chain against the DOS captures of work/trace_player_damage.py.
  for (const result of await require("./check-js-damage.js").checkDamage({ dir: path.relative(ROOT, CAPTURE_ROOT) })) {
    assert.notEqual(result.status, "FAIL", `damage capture: ${result.text}`);
    dosResults.push(`${result.status} damage ${result.text}`);
  }

  // The DOS sound driver against the captures of work/trace_sound_writes.py (build/sound,
  // build/sound-natural): every port write, returned value, variable and mixed byte.
  for (const result of require("./check-js-sound.js").checkSound()) {
    assert.notEqual(result.status, "FAIL", `sound driver: ${result.text}`);
    dosResults.push(`${result.status} sound ${result.text}`);
  }

  // The routines called directly in the original with chosen inputs
  // (work/dos_call.py): every JavaScript routine below agrees on random cases.
  for (const result of require("./check-js-dos-calls.js").checkDosCalls({ dir: path.relative(ROOT, CAPTURE_ROOT) })) {
    assert.notEqual(result.status, "FAIL", `DOS call: ${result.text}`);
    dosResults.push(`${result.status} DOS call ${result.text}`);
  }

  return { report, dosResults };
}

module.exports = { proveMenus };

if (require.main === module) {
  proveMenus().then(({ report, dosResults }) => {
    for (const line of report) console.log(`PASS ${line}`);
    for (const line of dosResults) console.log(line);
  }).catch((error) => {
    console.error(error.stack || error);
    process.exitCode = 1;
  });
}
