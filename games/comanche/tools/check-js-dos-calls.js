#!/usr/bin/env node
/*
 * check-js-dos-calls: run the JavaScript pilot, menu and mission-end routines on
 * the inputs the original was given, and compare with what the original left.
 *
 * The fixtures are work/replay_dos/dos-call-*.json, made by work/dos_call.py,
 * which points the running original's EIP at a routine with chosen memory and
 * registers and reads the result at the instruction that ends it. They are
 * derived and git-ignored: when one is absent its check reports SKIP.
 *
 * N/A - target artefact: an oracle probe, no DOS routine.
 * record: analysis/functions/browser-attract.md#mission-end-statistics
 *   (and the records of each routine named by the fixture's "routine")
 *
 * Usage: node tools/check-js-dos-calls.js [--dir work/replay_dos] [--routine R]
 * Exits non-zero on any difference.
 */

"use strict";

const fs = require("node:fs");
const path = require("node:path");

const ROOT = path.resolve(__dirname, "..");
for (const name of ["dos-text-data.js", "dos-pilot.js", "dos-menu.js", "dos-damage.js"]) {
  // eslint-disable-next-line global-require
  require(path.join(ROOT, "jsComanche", name));
}
const TEXT = globalThis.ComancheDOSText;
const PILOT = globalThis.ComanchePilot;
const MENU = globalThis.ComancheMenu;

const hex = (value) => new Uint8Array(Buffer.from(value, "hex"));
const dword = (bytes, offset) => (bytes[offset] | (bytes[offset + 1] << 8) | (bytes[offset + 2] << 16) | (bytes[offset + 3] << 24)) >>> 0;
const same = (left, right) => Buffer.compare(Buffer.from(left), Buffer.from(right)) === 0;

function firstDifference(left, right) {
  for (let index = 0; index < Math.max(left.length, right.length); index += 1) {
    if (left[index] !== right[index]) return `byte ${index} (0x${index.toString(16)}): js ${left[index]} dos ${right[index]}`;
  }
  return "equal";
}

const CHECKS = {
  "format-number": (fixture, failures) => {
    for (const [index, c] of fixture.cases.entries()) {
      const buffer = new Uint8Array(24).fill(0xfc);
      PILOT.formatNumber(buffer, fixture.base, c.width, c.value);
      const expected = hex(c.buffer_out);
      if (!same(buffer, expected)) failures.push(`case ${index} value ${c.value} width ${c.width}: ${firstDifference(buffer, expected)}`);
    }
  },

  percent: (fixture, failures) => {
    for (const [index, c] of fixture.cases.entries()) {
      const buffer = new Uint8Array(8).fill(0xaa);
      const acc = { score: c.score_in, lastPct: 0 };
      PILOT.percentField(acc, buffer, fixture.base, c.total, c.count);
      const expected = hex(c.buffer_out);
      if (!same(buffer, expected)) failures.push(`case ${index} ${c.count}/${c.total}: ${firstDifference(buffer, expected)}`);
      if (acc.score !== c.score_out || acc.lastPct !== c.last_out) failures.push(`case ${index}: score js ${acc.score} dos ${c.score_out}, last js ${acc.lastPct} dos ${c.last_out}`);
    }
  },

  statistics: (fixture, failures) => {
    for (const [index, c] of fixture.cases.entries()) {
      const i = c.input;
      const objects = [];
      for (let slot = 0; slot <= 130; slot += 1) objects.push({ active: 0, aux: 0, goal: 0 });
      for (const [slot, active, aux, goal] of i.objects) objects[slot] = { active, aux, goal };
      const result = PILOT.missionStatistics({
        fuel: i.fuel, fuelMax: i.fuel_max, hullNow: i.hull_now, hullMax: i.hull_max, objects,
        targetCount: i.target_count, ammo: i.ammo, loadout: i.loadout, allyWrecked: i.ally,
        text: TEXT.debriefScreen.bytes,
      });
      const label = `case ${index} (${i.scenario})`;
      const expectedText = hex(c.text_out);
      if (!same(result.text, expectedText)) failures.push(`${label}: text ${firstDifference(result.text, expectedText)}`);
      const counters = hex(c.counters_out);        // 0002824C..: goals, total, done, ?, alive, kills, score, last
      const wanted = [counters[0], counters[1], counters[2], dword(counters, 4), dword(counters, 8), dword(counters, 12), dword(counters, 16)];
      const got = [result.goals, result.goalsTotal, result.goalsDone, result.enemiesAlive, result.kills, result.score, result.lastPct];
      if (JSON.stringify(got) !== JSON.stringify(wanted)) failures.push(`${label}: counters js ${got} dos ${wanted}`);
      if (result.fuel !== c.fuel_out) failures.push(`${label}: fuel js ${result.fuel} dos ${c.fuel_out}`);
      if (result.hullNow !== c.hull_out[0] >>> 0 && (result.hullNow | 0) !== c.hull_out[0]) failures.push(`${label}: hull js ${result.hullNow} dos ${c.hull_out[0]}`);
      if ((result.hullMax | 0) !== c.hull_out[1]) failures.push(`${label}: hull max js ${result.hullMax} dos ${c.hull_out[1]}`);
    }
  },

  "briefing-loop": (fixture, failures) => {
    for (const [index, c] of fixture.cases.entries()) {
      const text = hex(c.text);
      const image = new Uint8Array(c.prefix + text.length);
      image.fill(0x41, 0, c.prefix);
      image.set(text, c.prefix);
      const wrapped = MENU.wrapBriefing(image, c.prefix);
      const expected = hex(c.out);
      if (!same(wrapped.bytes, expected)) failures.push(`case ${index}: ${firstDifference(wrapped.bytes, expected)}`);
      if (wrapped.next - c.prefix !== c.next) failures.push(`case ${index}: source end js ${wrapped.next - c.prefix} dos ${c.next}`);
    }
  },

  "scan-list": (fixture, failures) => {
    for (const [index, c] of fixture.cases.entries()) {
      const file = hex(c.file);
      const result = MENU.scanMissionList(file, file.length);
      const names = hex(c.names);
      const star = hex(c.star);
      const promo = hex(c.promo);
      const text = hex(c.text);
      // 0xCC and 0xEE are the fill the probe poked: bytes the routine left alone
      // slot 10 (00029ED5) overlaps the pointer table at 00029EF0, so only its end
      // marker is compared, and only when fewer than ten titles were found
      const limit = 10 * 0x20 + (c.count < 10 ? 4 : 0);
      for (let at = 0; at < limit; at += 1) {
        const jsByte = result.names[at];
        const wanted = names[at] === 0xcc ? 0 : names[at];
        if (jsByte !== wanted) { failures.push(`case ${index}: names byte ${at}: js ${jsByte} dos ${names[at]}`); break; }
      }
      for (let k = 0; k < 10; k += 1) {
        const s = star[k] === 0xee ? 0 : star[k];
        const p = promo[k] === 0xee ? 0 : promo[k];
        if (result.star[k] !== s || result.promo[k] !== p) failures.push(`case ${index}: row ${k} star/promo js ${result.star[k]}/${result.promo[k]} dos ${s}/${p}`);
        const pointer = dword(text, k * 4);
        const wantedPointer = pointer === 0xeeeeeeee ? -1 : pointer - 0x3cc20;
        if (result.text[k] !== wantedPointer) failures.push(`case ${index}: row ${k} text pointer js ${result.text[k]} dos ${wantedPointer}`);
      }
      // 0x1234 is the value the probe poked into [0002A100]: the routine left at
      // 0002A200 (no closing brace for the title) before writing the count
      const wantedCount = c.count === 0x1234 ? 0 : c.count;
      if (result.count !== wantedCount) failures.push(`case ${index}: count js ${result.count} dos ${c.count}`);
    }
  },

  decode: (fixture, failures) => {
    for (const [index, c] of fixture.cases.entries()) {
      const data = hex(c.data);
      const out = MENU.decodeMissionImage(data);
      const expected = hex(c.out).subarray(0, out.length);
      if (!same(out, expected)) failures.push(`case ${index}: ${firstDifference(out, expected)}`);
    }
  },

  "skip-line": (fixture, failures) => {
    for (const [index, c] of fixture.cases.entries()) {
      const image = new Uint8Array(hex(c.data).length + 0x200);
      image.set(hex(c.data));
      let end = null;
      let error = false;
      try {
        end = MENU.skipLine(image, c.start);
      } catch (exception) {
        error = true;
      }
      if (error !== c.error || (!error && end !== c.end)) failures.push(`case ${index}: js ${error ? "error" : end} dos ${c.error ? "error" : c.end}`);
    }
  },

  "your-stats": (fixture, failures) => {
    for (const [index, c] of fixture.cases.entries()) {
      const screen = MENU.yourStatsScreen(hex(c.roster), c.pilot);
      const expected = hex(c.screen_out);
      if (!same(screen, expected)) failures.push(`case ${index}: ${firstDifference(screen, expected)}`);
    }
  },

  "pilot-record": (fixture, failures) => {
    for (const [index, c] of fixture.cases.entries()) {
      const roster = hex(c.roster);
      const debrief = Uint8Array.from(TEXT.debriefScreen.bytes);
      const ctx = {
        campaignDigits: hex(c.digits), star: hex(c.star), promo: hex(c.promo), sentences: TEXT.debriefScreen.bytes,
        hullNow: c.hull, kills: c.kills, score: c.score,
      };
      if (c.won) PILOT.pilotRecordWon(roster, ctx);
      else PILOT.pilotRecordLost(roster, debrief, ctx);
      const expected = hex(c.roster_out);
      if (!same(roster, expected)) failures.push(`case ${index} (${c.won ? "won" : "lost"}): roster ${firstDifference(roster, expected)}`);
      const message = debrief.subarray(PILOT.DEBRIEF.MESSAGE, PILOT.DEBRIEF.MESSAGE + 0x2f);
      if (!same(message, hex(c.message_out))) failures.push(`case ${index} (${c.won ? "won" : "lost"}): setback sentence ${firstDifference(message, hex(c.message_out))}`);
    }
  },

  "roster-sort": (fixture, failures) => {
    for (const [index, c] of fixture.cases.entries()) {
      const roster = hex(c.roster_in);
      const selected = PILOT.rosterSort(roster, c.selected_in);
      const expected = hex(c.roster_out);
      if (!same(roster, expected)) failures.push(`case ${index}: roster ${firstDifference(roster, expected)}`);
      if (selected !== c.selected_out) failures.push(`case ${index}: [00027DAA] js ${selected} dos ${c.selected_out}`);
    }
  },

  "row-colours": (fixture, failures) => {
    for (const [index, c] of fixture.cases.entries()) {
      const roster = hex(c.roster);
      const pilot = roster[PILOT.ROSTER.CURRENT];
      const digit = hex(c.digits)[roster[PILOT.ROSTER.CAMPAIGNS + pilot]] - 0x30;
      const won = roster.subarray(PILOT.ROSTER.MISSIONS + pilot * 100 + digit * 10, PILOT.ROSTER.MISSIONS + pilot * 100 + digit * 10 + 10);
      const names = new Uint8Array(11 * MENU.NAME_SLOT);
      names.set(hex(c.names));
      const colours = MENU.missionRowColours(won, hex(c.star), names);
      const expectedNames = hex(c.names_out);
      if (!same(names.subarray(0, expectedNames.length), expectedNames)) failures.push(`case ${index}: names ${firstDifference(names, expectedNames)}`);
      const expectedColours = hex(c.colours_out).map((value) => (value === 0xcc ? 0 : value));
      if (!same(colours.subarray(0, 10), expectedColours)) failures.push(`case ${index}: colours ${firstDifference(colours, expectedColours)}`);
    }
  },

  "list-selection": (fixture, failures) => {
    for (const [index, c] of fixture.cases.entries()) {
      const selected = MENU.missionListSelection(hex(c.roster), hex(c.digits));
      if (selected !== c.al) failures.push(`case ${index}: js ${selected} dos ${c.al}`);
    }
  },

  "list-choice": (fixture, failures) => {
    for (const [index, c] of fixture.cases.entries()) {
      const roster = hex(c.roster);
      const result = MENU.missionListChoice(roster, hex(c.digits), hex(c.colours), c.row);
      const expected = hex(c.roster_out);
      if (!same(roster, expected)) failures.push(`case ${index}: roster ${firstDifference(roster, expected)}`);
      if (result.locked !== c.locked) failures.push(`case ${index}: locked js ${result.locked} dos ${c.locked}`);
    }
  },

  "object-clear": (fixture, failures) => {
    for (const [index, c] of fixture.cases.entries()) {
      const active = hex(c.active);
      const mission = { objects: Array.from(active, (value) => ({ active: value })), dword22368: c.dword_22368, allyWrecked: c.ally };
      PILOT.clearMissionObjects(mission);
      const got = Uint8Array.from(mission.objects, (object) => object.active);
      const expected = hex(c.active_out);
      if (!same(got, expected)) failures.push(`case ${index}: active bytes ${firstDifference(got, expected)}`);
      if (mission.dword22368 !== c.dword_22368_out || mission.allyWrecked !== c.ally_out) failures.push(`case ${index}: [00022368] js ${mission.dword22368} dos ${c.dword_22368_out}, [00022384] js ${mission.allyWrecked} dos ${c.ally_out}`);
    }
  },

  route: (fixture, failures) => {
    const names = { "00005690": "attract", "00005AE3": "menu", "000287E2": "lost", "000288ED": "won" };
    for (const [index, c] of fixture.cases.entries()) {
      const session = { attractActive: c.attract === 1, missionFlown: c.flown };
      const route = PILOT.missionEndRoute(session, c.hull, c.done);
      if (route !== names[c.stop]) failures.push(`case ${index}: js ${route} dos ${names[c.stop]} (attract ${c.attract}, flown ${c.flown}, hull ${c.hull}, goals ${c.done})`);
      if (session.missionFlown !== c.flown_out) failures.push(`case ${index}: [00019D91] js ${session.missionFlown} dos ${c.flown_out}`);
    }
  },

  "game-column": (fixture, failures) => {
    const settings = Uint8Array.from({ length: 35 }, (_, index) => 0x40 + index);
    for (const c of fixture.cases) {
      const action = MENU.optionsGameAction({ settings }, c.code);
      const label = `key ${c.code}`;
      // where the original's routine leaves: 00026E8F for About and for an unknown key (after
      // the About box's key wait), the abort, exit and return targets for 3, 4 and 1
      const targets = { "abort-mission": 0x2873d, exit: 0x6b14, return: 0x2615c };
      if (action.action in targets) {
        if (parseInt(c.end, 16) !== targets[action.action] || action.target !== targets[action.action]) failures.push(`${label}: js ${action.action} -> ${action.target}, dos ${c.end}`);
      } else if (action.action === "save-settings") {
        if (c.writes.length !== 1 || c.writes[0].edx !== 0x25dbc || c.writes[0].ebx !== action.bytes.length || action.bytes.length !== 35) failures.push(`${label}: write js 35 bytes at 0x25dbc, dos ${JSON.stringify(c.writes)}`);
        if (action.file !== "Comanche.MNU") failures.push(`${label}: file ${action.file}`);
      } else if (parseInt(c.end, 16) !== 0x26e8f || c.writes.length) {
        failures.push(`${label}: js ${action.action}, dos ${c.end} ${JSON.stringify(c.writes)}`);
      }
    }
  },

  toggles: (fixture, failures) => {
    for (const [index, c] of fixture.cases.entries()) {
      const menu = { settings: hex(c.settings), braces: {} };
      for (const [address, value] of Object.entries(c.braces)) menu.braces[parseInt(address, 16)] = value;
      MENU.optionsToggle(menu, c.code);
      const expected = hex(c.settings_out);
      if (!same(menu.settings, expected)) failures.push(`case ${index} key 0x${c.code.toString(16)}: settings ${firstDifference(menu.settings, expected)}`);
      for (const [address, value] of Object.entries(c.braces_out)) {
        if (menu.braces[parseInt(address, 16)] !== value) failures.push(`case ${index} key 0x${c.code.toString(16)}: brace ${address} js ${menu.braces[parseInt(address, 16)]} dos ${value}`);
      }
    }
  },

  "name-entry": (fixture, failures) => {
    for (const [index, c] of fixture.cases.entries()) {
      const roster = hex(c.roster);
      const state = MENU.nameEntryStart();
      let selected = c.slot;
      for (const [code, shift] of c.keys) {
        const outcome = MENU.nameEntryKey(state, code, shift !== 0 && shift !== false);
        if (outcome === "accept") {
          selected = MENU.createPilot(roster, c.slot, state.field);
          break;
        }
        if (outcome === "cancel") break;
      }
      const label = `case ${index}`;
      const expected = hex(c.roster_out);
      if (!same(roster, expected)) failures.push(`${label}: roster ${firstDifference(roster, expected)}`);
      const field = hex(c.field_out);
      if (!same(state.field, field)) failures.push(`${label}: field ${firstDifference(state.field, field)}`);
      if (state.cursor !== c.cursor_out) failures.push(`${label}: cursor js ${state.cursor} dos ${c.cursor_out}`);
      if (selected !== c.selected_out) failures.push(`${label}: [00027DAA] js ${selected} dos ${c.selected_out}`);
    }
  },
};

// Returns { routine, status, text } per fixture file found (SKIP when absent).
function checkDosCalls(options = {}) {
  const dir = path.resolve(ROOT, options.dir || "work/replay_dos");
  const results = [];
  for (const routine of Object.keys(CHECKS)) {
    if (options.routine && options.routine !== routine) continue;
    const file = path.join(dir, `dos-call-${routine}.json`);
    if (!fs.existsSync(file)) { results.push({ routine, status: "SKIP", text: `${routine} (capture absent)` }); continue; }
    const fixture = JSON.parse(fs.readFileSync(file, "utf8"));
    const failures = [];
    CHECKS[routine](fixture, failures);
    results.push(failures.length
      ? { routine, status: "FAIL", text: `${routine}: ${failures.length} of ${fixture.cases.length} differ, first ${failures.slice(0, 5).join("; ")}` }
      : { routine, status: "PASS", text: `${routine}: ${fixture.cases.length} cases agree with the original at ${fixture.entry || "its entry"}` });
  }
  return results;
}

module.exports = { checkDosCalls };

if (require.main === module) {
  const args = process.argv.slice(2);
  const value = (flag, fallback) => (args.indexOf(flag) >= 0 ? args[args.indexOf(flag) + 1] : fallback);
  const results = checkDosCalls({ dir: value("--dir", "work/replay_dos"), routine: value("--routine", null) });
  for (const result of results) console.log(`${result.status} ${result.text}`);
  process.exitCode = results.some((result) => result.status === "FAIL") ? 1 : 0;
}
