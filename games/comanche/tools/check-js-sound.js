#!/usr/bin/env node
/*
 * check-js-sound: run the JavaScript sound driver (jsComanche/dos-sound.js)
 * against the DOS captures of work/trace_sound_writes.py (build/sound/*.json,
 * derived and git-ignored; regenerate with that script, see
 * analysis/functions/sound-driver.md).
 *
 * N/A - target artefact: an oracle probe, no DOS routine.
 * record: analysis/functions/browser-attract.md#sound-driver-module
 *
 * What is compared, per capture:
 *   - every op of the script the original was driven through (select device,
 *     start song, tick, effect, stop, ...) is replayed on the JavaScript driver
 *     with the same arguments; the OPL2 register writes, MPU-401 bytes and PC
 *     speaker port writes it makes are compared with the original's, in order,
 *     op by op;
 *   - a command's returned AL;
 *   - after every op, the bytes the driver's variables changed in (the capture's
 *     "windows": the FM driver's state 0002C48C-0002C5D9, 0002D10D-0002D163,
 *     0002D404-0002D408, the digital slots and dither 00004142-000041B7, the
 *     mix loop's patched immediates, the buffer pointers and the bank variables),
 *     compared with what the original changed there;
 *   - for the digital layer, every 0x800 bytes the mixer fill 00005220 produces.
 * The card's answers are inputs taken FROM the capture, never computed: the OPL
 * status the detection reads ("s" entries), the MPU-401 acknowledge (0xFE, the
 * byte the probe returns for 0002BFD9) and the speaker port's reads ("i").
 *
 * Usage: node tools/check-js-sound.js [--dir build/sound] [name ...]
 * Exits non-zero on any difference.
 */

"use strict";

const crypto = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const ROOT = path.resolve(__dirname, "..");
const ASSET_ROOT = path.join(ROOT, "assets", "extracted", "comanche_hdd");
const FLAT_SHA256 = "a2c2b50d4e2d85ecbf210440927927323b0a176613beb25d74c0cdde8dae1a6c";
const FLAT_BYTES = 207648;
const SPEAKER_PORT = { 0x2C436: 0x61, 0x2C440: 0x61, 0x2C455: 0x61, 0x2C45C: 0x61, 0x2C469: 0x43, 0x2C475: 0x42, 0x2C47B: 0x42 };
const FLAT_AT = 0x1700;      // the flat program's offset in the MZ load module

function loadImage() {
  const exe = fs.readFileSync(path.join(ASSET_ROOT, "UNPACKED.EXE"));
  const header = (exe[8] | (exe[9] << 8)) * 16;           // MZ header paragraphs
  const flat = exe.subarray(header + FLAT_AT, header + FLAT_AT + FLAT_BYTES);
  const sha = crypto.createHash("sha256").update(flat).digest("hex");
  if (sha !== FLAT_SHA256) throw new Error(`the flat image is not the hashed one: ${sha}`);
  return Uint8Array.from(flat);
}

function loadSound() {
  const context = vm.createContext({ console, Uint8Array, Map, Error, Math, Number, String, Object, Array });
  context.globalThis = context;
  vm.runInContext(fs.readFileSync(path.join(ROOT, "jsComanche", "dos-sound.js"), "utf8"), context,
    { filename: "dos-sound.js" });
  return context.ComancheSound;
}

function windows(driver, list) {
  return list.map(([lo, hi]) => [lo, driver.read(lo, hi - lo)]);
}

function diffWindows(before, after) {
  const out = [];
  for (let w = 0; w < before.length; w += 1) {
    const [lo, old] = before[w];
    const now = after[w][1];
    for (let i = 0; i < now.length; i += 1) if (old[i] !== now[i]) out.push([lo + i, now[i]]);
  }
  return out;
}

const hex = (value) => value.toString(16).toUpperCase();

function checkCapture(Sound, image, name, capture) {
  if (capture.image_sha256 !== FLAT_SHA256) throw new Error(`${name}: captured against another image`);
  const queues = { s: [], i: [] };
  const hooks = {
    oplStatus() {
      if (!queues.s.length) throw new Error(`${name}: the driver read an OPL status the original did not`);
      return queues.s.shift();
    },
    mpuAck() { return 0xFE; },
    port61() {
      if (!queues.i.length) throw new Error(`${name}: the driver read port 0x61 the original did not`);
      return queues.i.shift();
    },
  };
  const driver = Sound.create(image, { hooks, digitalFlag: capture.digital_flag, delayLoops: capture.delay_1c8e });
  const placed = new Set();
  const list = capture.windows;
  let shadow = windows(driver, list);
  let compared = 0;
  let writes = 0;
  let pcmBytes = 0;
  for (const op of capture.ops) {
    const expected = [];
    queues.s.length = 0;
    queues.i.length = 0;
    for (const w of op.writes) {
      if (w[0] === "s") queues.s.push(w[1]);
      else if (w[0] === "i") queues.i.push(w[2]);
      else expected.push(w);
    }
    let ret = null;
    if (op.op === "command") ret = driver.command(op.ax);
    else if (op.op === "start_bytes") {
      driver.placeSong(op.ebx, Uint8Array.from(Buffer.from(op.hex, "hex")));
      driver.start(op.al, op.ebx);
    } else if (op.op === "start") {
      if (!placed.has(op.ebx)) {
        const file = fs.readFileSync(path.join(ASSET_ROOT, op.file));
        const bytes = Sound.decodeMusicFile(file);
        if (bytes.length !== op.size) throw new Error(`${name}: ${op.file} decodes to ${bytes.length}, the capture has ${op.size}`);
        driver.placeSong(op.ebx, bytes);
        placed.add(op.ebx);
      }
      driver.start(op.al, op.ebx);
    } else if (op.op === "stop") driver.stop();
    else if (op.op === "tick") driver.tick();
    else if (op.op === "effect") ret = driver.effect(op.ebp);
    else if (op.op === "digital") driver.pokeByte(0x19DF9, op.flag);
    else if (op.op === "poke_bytes") driver.placeSong(op.address, Uint8Array.from(Buffer.from(op.bytes, "hex")));
    else if (op.op === "poke32") driver.pokeDword(op.address, op.value);
    else if (op.op === "bank") {
      const bytes = Sound.decodeMusicFile(fs.readFileSync(path.join(ASSET_ROOT, op.file)));
      if (bytes.length !== op.size) throw new Error(`${name}: ${op.file} decodes to ${bytes.length}, the capture has ${op.size}`);
      driver.placeSong(op.at, bytes);
      driver.pokeDword(op.variable, op.at);
    } else if (op.op === "rate") driver.setRate(op.al);
    else if (op.op === "reset") driver.resetMixer();
    else if (op.op === "fx") driver.fx(op.ebp, op.bl, op.dl, op.ecx);
    else if (op.op === "speecha") driver.speechA(op.al);
    else if (op.op === "speechb") driver.speechB(op.al);
    else if (op.op === "voice" || op.op === "silence_voice") driver.voice(op.eax, op.bl, op.dl, op.ecx);
    else if (op.op === "fill") {
      const pcm = Buffer.from(driver.fill()).toString("hex");
      if (pcm !== op.pcm) {
        let at = 0;
        while (at < pcm.length && pcm[at] === op.pcm[at]) at += 1;
        throw new Error(`${name} op ${op.i} (fill): the mixed bytes differ from byte ${at >> 1}: JavaScript ${pcm.slice(at & ~1, (at & ~1) + 8)}..., DOS ${op.pcm.slice(at & ~1, (at & ~1) + 8)}...`);
      }
      pcmBytes += pcm.length / 2;
    } else throw new Error(`${name}: unknown op ${op.op}`);
    const got = driver.takeWrites();
    const label = `${name} op ${op.i} (${op.op}${op.ax !== undefined ? " ax=" + hex(op.ax) : ""}`
      + `${op.ebp !== undefined ? " ebp=" + hex(op.ebp) : ""})`;
    if (JSON.stringify(got) !== JSON.stringify(expected)) {
      let at = 0;
      while (at < got.length && at < expected.length && JSON.stringify(got[at]) === JSON.stringify(expected[at])) at += 1;
      throw new Error(`${label}: the writes differ from write ${at}: JavaScript ${JSON.stringify(got[at])} (of ${got.length}), `
        + `DOS ${JSON.stringify(expected[at])} (of ${expected.length})`);
    }
    if (queues.s.length || queues.i.length) throw new Error(`${label}: the original read card state the driver did not`);
    if (op.op === "command" && ret !== op.ret_al) throw new Error(`${label}: returned AL ${hex(ret)}, DOS ${hex(op.ret_al)}`);
    const now = windows(driver, list);
    const delta = diffWindows(shadow, now);
    shadow = now;
    if (JSON.stringify(delta) !== JSON.stringify(op.delta)) {
      throw new Error(`${label}: the driver's variables changed differently: JavaScript ${JSON.stringify(delta.slice(0, 6))}... `
        + `(${delta.length}), DOS ${JSON.stringify(op.delta.slice(0, 6))}... (${op.delta.length})`);
    }
    compared += 1;
    writes += expected.length;
  }
  return { ops: compared, writes, pcmBytes };
}

// The game's own call sequence (work/trace_sound_writes.py natural): every ISR entry is a
// tick, every entry of 0002B9CF / 0002BD00 / 0002BEDC (not the driver's own) is that call with
// the registers it had, and the card's writes are one stream in the order they happened.
//
// A timer interrupt can arrive in the middle of a driver call; the capture then has the call's
// first k writes, the tick's, and the call's remainder, and the ISR's entry is recorded at
// position k of the stream. The replay therefore runs every call with a hook that fires the
// next recorded ISR (re-entrantly, as the original's ISR does) as soon as the stream has
// reached that ISR's position and the call still has a write to make. Every write of the
// JavaScript is compared with the original's at the same index, so the whole interleaving
// has to agree, not just the multiset.
const GAME_WRITTEN = [[0x2C5A8, 0x2C5A9], [0x2C494, 0x2C498]];
const NATURAL_STATE = [[0x2C48C, 0x2C5D9], [0x2D10D, 0x2D163], [0x2D404, 0x2D408]];
const INTERNAL_STOP_CALLERS = new Set([0x2BAA9, 0x2BD64]);

function songBytes(window) {
  // The song at the start of a window of memory: everything up to the end marker FF 2F, found by
  // walking the events the way the reader does (0002BD75).
  let p = 0x30;
  while (!(window[p] === 0xFF && window[p + 1] === 0x2F)) {
    const status = window[p] & 0xF0;
    p += status === 0x80 ? 1 : status === 0xB0 ? 3 : 2;
    p += (window[p] & 0x80) ? 2 : 1;
    if (p >= window.length - 2) throw new Error("no end marker in the song window");
  }
  return Uint8Array.from(window.subarray(0, p + 2));
}

function checkNatural(Sound, image, name, log) {
  if (log.image_sha256 !== FLAT_SHA256) throw new Error(`${name}: captured against another image`);
  const statuses = [];
  const port61 = [];
  const expected = [];
  const events = [];
  for (const ev of log.events) {
    if (ev.at === "stop" && INTERNAL_STOP_CALLERS.has(ev.caller)) continue;
    if (["isr", "cmd", "start", "stop"].includes(ev.at)) events.push({ ev, pos: expected.length });
    else if (ev.at === "opl") expected.push(["o", ev.reg, ev.val]);
    else if (ev.at === "mpu_data") expected.push(["m", ev.val]);
    else if (ev.at === "mpu_cmd") expected.push(["c", ev.val]);
    else if (ev.at.startsWith("opl_status")) statuses.push(ev.val);
    else if (ev.at.startsWith("spk_in")) port61.push(ev.val);
    else if (ev.at.startsWith("spk_out")) expected.push(["p", SPEAKER_PORT[parseInt(ev.at.slice(8), 16)], ev.val]);
  }
  const hooks = {
    oplStatus() {
      if (!statuses.length) throw new Error(`${name}: the driver read an OPL status the original did not`);
      return statuses.shift();
    },
    mpuAck() { return 0xFE; },
    port61() {
      if (!port61.length) throw new Error(`${name}: the driver read port 0x61 the original did not`);
      return port61.shift();
    },
  };
  const driver = Sound.create(image, { hooks, delayLoops: log.delay_1c8e, relocateTable: true });
  const stats = { ticks: 0, commands: 0, interrupted: 0, songs: 0, writes: 0, gamePokes: 0, truncated: 0 };
  let checked = 0;
  const fired = new Set();
  const stateNow = () => NATURAL_STATE.map(([lo, hi]) => Buffer.from(driver.read(lo, hi - lo)).toString("hex")).join("");
  const stateDiffs = (want) => {
    // the addresses where the JavaScript's variables are not the original's at that entry
    const got = stateNow();
    const out = [];
    let offset = 0;
    for (const [lo, hi] of NATURAL_STATE) {
      for (let i = 0; i < hi - lo; i += 1) {
        const x = parseInt(got.slice((offset + i) * 2, (offset + i) * 2 + 2), 16);
        const y = parseInt(want.slice((offset + i) * 2, (offset + i) * 2 + 2), 16);
        if (x !== y) out.push({ address: lo + i, js: x, dos: y });
      }
      offset += hi - lo;
    }
    return out;
  };
  const stateDiff = (want) => stateDiffs(want).map((d) => `${d.address.toString(16)}: JS ${d.js.toString(16)} DOS ${d.dos.toString(16)}`);
  const sameState = (ev) => stateNow() === ev.state;
  // The bytes at the song cursor as the original had them at that entry: the game reuses the
  // buffer a song plays from (0002DB10 is also its demo buffer), so they can differ from the file.
  const adoptSong = (ev) => {
    if (!ev.cursor_bytes) return;
    const cursor = driver.machine.r32(0x2C490);
    driver.pokeBytes(cursor, Uint8Array.from(Buffer.from(ev.cursor_bytes, "hex")));
  };
  const compare = (label, lastEvent = false) => {
    const got = driver.takeWrites();
    for (const w of got) {
      // the capture stops when its time is up, which can be inside the last ISR's writes
      if (lastEvent && checked >= expected.length) { stats.truncated = got.length; break; }
      if (checked >= expected.length || JSON.stringify(w) !== JSON.stringify(expected[checked])) {
        const around = (list, from) => list.slice(Math.max(0, from - 6), from + 6).map((x) => (x ? x.join(":") : "-")).join(" ");
        throw new Error(`${label}: write ${checked} is ${JSON.stringify(w)} in JavaScript, `
          + `${JSON.stringify(expected[checked])} in the original\n  original: ${around(expected, checked)}`);
      }
      checked += 1;
    }
  };
  const doCall = (ev) => {
    if (ev.at === "cmd") { driver.command(ev.eax & 0xFFFF); stats.commands += 1; }
    else if (ev.at === "start") {
      if (ev.song) { driver.placeSong(ev.ebx, songBytes(Buffer.from(ev.song, "hex"))); stats.songs += 1; }
      driver.start(ev.eax & 0xFF, ev.ebx);
      stats.commands += 1;
    } else { driver.stop(); stats.commands += 1; }
  };
  for (let index = 0; index < events.length; index += 1) {
    const { ev } = events[index];
    if (fired.has(index)) continue;
    const label = `${name}: event ${index} (${ev.at}${ev.eax !== undefined ? " eax=" + ev.eax.toString(16) : ""}, isr ${ev.isr})`;
    // every entry of the original's driver or ISR starts from the variables the original had - except
    // for the two the GAME writes itself, between driver calls: the music volume [0002C5A8]
    // (000267FC, 00026818, 00026D37, 00026D59 store 0xFA, 0x64 or 0x73) and the current-song
    // pointer [0002C494] (000056C9, 0002789B... clear it). Those are inputs: adopted, counted.
    if (ev.state && !sameState(ev)) {
      const diffs = stateDiffs(ev.state);
      const foreign = diffs.filter((d) => !GAME_WRITTEN.some(([lo, hi]) => d.address >= lo && d.address < hi));
      if (foreign.length) {
        throw new Error(`${label}: the driver's variables differ at the entry: ${stateDiff(ev.state).slice(0, 6).join("; ")}`);
      }
      for (const d of diffs) driver.pokeByte(d.address, d.dos);
      stats.gamePokes += 1;
    }
    adoptSong(ev);
    if (ev.at === "isr") {
      driver.tick();
      stats.ticks += 1;
      compare(label, index === events.length - 1);
      continue;
    }
    // A call. The ISRs that follow it in the log (before the next call) may have arrived inside it.
    // The stream says after which write one did, not before which instruction; the original's
    // variables at the ISR's entry say the rest: the first access to memory (or port write) at or
    // after that write where the JavaScript's variables are the original's is where the interrupt
    // goes in. An interrupt for which there is no such place was after the call.
    const queue = [];
    for (let next = index + 1; next < events.length && events[next].ev.at === "isr" && queue.length < 8; next += 1) {
      if (!fired.has(next)) queue.push(next);
    }
    if (queue.length) {
      const wanted = () => (queue.length ? events[queue[0]] : null);
      let accessCount = 0;
      const check = () => {
        accessCount += 1;
        const isr = wanted();
        while (isr && !fired.has(queue[0]) && checked + driver.machine.writes.length >= isr.pos && isr.ev.state && sameState(isr.ev)) {
          if (process.env.SOUND_TRACE === String(index)) console.log(`   interrupt fires: writes so far ${checked + driver.machine.writes.length}, ISR position ${isr.pos}, accesses ${accessCount}`);
          fired.add(queue.shift());
          adoptSong(isr.ev);
          driver.interrupt();
          stats.ticks += 1;
          stats.interrupted += 1;
          if (!queue.length) break;
          break;
        }
      };
      driver.setBeforeWrite(check, check);
    }
    doCall(ev);
    driver.setBeforeWrite(null);
    compare(label, index === events.length - 1);
  }
  if (checked !== expected.length) {
    throw new Error(`${name}: the original made ${expected.length} writes, the JavaScript ${checked}`);
  }
  stats.writes = checked;
  return stats;
}

const DEFAULT_DIR = path.join(ROOT, "build", "sound");
const DEFAULT_NATURAL = path.join(ROOT, "build", "sound-natural", "natural-attract.json");

// Run every capture in `dir` (or the named ones) and the natural run, if there is one. Returns
// one {status, text} per capture: PASS, FAIL, or SKIP when there is nothing to compare with
// (the captures are derived and git-ignored: regenerate with work/trace_sound_writes.py).
function checkSound({ dir = DEFAULT_DIR, names = [], natural = DEFAULT_NATURAL } = {}) {
  const results = [];
  let files = [];
  try {
    files = fs.readdirSync(dir).filter((f) => f.endsWith(".json"))
      .filter((f) => !names.length || names.includes(f.replace(/\.json$/, ""))).sort();
  } catch (error) {
    files = [];
  }
  const wantNatural = natural && (!names.length || names.includes("natural")) && fs.existsSync(natural);
  if (!files.length && !wantNatural) {
    return [{ status: "SKIP", text: `sound driver (no captures in ${path.relative(ROOT, dir)}; run work/trace_sound_writes.py)` }];
  }
  const Sound = loadSound();
  const image = loadImage();
  let totalOps = 0;
  let totalWrites = 0;
  let totalPcm = 0;
  let failed = 0;
  for (const file of files) {
    const name = file.replace(/\.json$/, "");
    const capture = JSON.parse(fs.readFileSync(path.join(dir, file), "utf8"));
    try {
      const result = checkCapture(Sound, image, name, capture);
      totalOps += result.ops;
      totalWrites += result.writes;
      totalPcm += result.pcmBytes;
      results.push({ status: "PASS", text: `${name}: ${result.ops} ops, ${result.writes} writes${result.pcmBytes ? `, ${result.pcmBytes} mixed bytes` : ""} identical` });
    } catch (error) {
      failed += 1;
      results.push({ status: "FAIL", text: error.message });
    }
  }
  if (files.length) {
    results.push({ status: failed ? "FAIL" : "PASS", text: `${files.length - failed}/${files.length} sound captures identical (${totalOps} ops, ${totalWrites} writes, ${totalPcm} mixed bytes)` });
  }
  if (wantNatural) {
    try {
      const log = JSON.parse(fs.readFileSync(natural, "utf8"));
      const r = checkNatural(Sound, image, path.basename(natural), log);
      results.push({ status: "PASS", text: `natural run: ${r.ticks} ticks, ${r.commands} driver calls (${r.songs} songs, ${r.interrupted} interrupted by a tick, ${r.gamePokes} adoptions of the game's own writes), ${r.writes} writes identical` });
    } catch (error) {
      results.push({ status: "FAIL", text: error.message });
    }
  }
  return results;
}

function main() {
  const args = process.argv.slice(2);
  let dir = DEFAULT_DIR;
  let natural = DEFAULT_NATURAL;
  const names = [];
  for (let i = 0; i < args.length; i += 1) {
    if (args[i] === "--dir") { dir = path.resolve(args[i + 1]); i += 1; }
    else if (args[i] === "--natural") { natural = path.resolve(args[i + 1]); i += 1; if (!names.includes("natural")) names.push("natural"); }
    else names.push(args[i]);
  }
  if (names.length === 1 && names[0] === "natural") dir = path.join(ROOT, "build", "no-captures");
  const results = checkSound({ dir, names, natural });
  for (const r of results) console.log(`${r.status === "PASS" ? "ok  " : r.status}${r.status === "PASS" ? " " : " "} ${r.text}`);
  process.exit(results.some((r) => r.status === "FAIL") ? 1 : 0);
}

module.exports = { checkSound };

if (require.main === module) main();
