#!/usr/bin/env node
/*
 * export-sound-trace: play a song through the JavaScript sound driver and write the OPL2 register
 * writes it makes in the trace format of the sibling project ../F030OPL2
 * (`W <microseconds> <context> <register hex> <value hex>`, read by `opl-rt-fixture trace` and
 * `tools/opl/rt-stream-gate.py`).
 *
 * N/A - target artefact: a host tool over jsComanche/dos-sound.js, no DOS routine.
 * record: analysis/functions/browser-attract.md#sound-driver-module
 *
 * The clock is the driver's own: one tick per PIT interrupt, 18356 / 1193182 s = 15384.07 us, so a
 * write made by tick n is stamped n * 15384.07 us and the writes of the commands before the first
 * tick are stamped 0. The context is `M` for the select and start commands and `T` for ticks.
 *
 * Usage: node tools/export-sound-trace.js FILE [--device 3] [--flags 0] [--ticks N] [--out FILE.ev]
 *                                              [--against build/sound/openmus.json]
 *   FILE is a song of the installed game (OPENMUS.MS3, FANFARE.RLE, MUSDAY.RLE, ...). Without --ticks
 *   the song is played to its end (the driver reports it through command 0x6000) and 20 ticks beyond.
 *   --against compares the (register, value) sequence with a capture of the original
 *   (work/trace_sound_writes.py direct, scenario of the same song) and exits non-zero on a difference.
 */

"use strict";

const crypto = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const ROOT = path.resolve(__dirname, "..");
const ASSET_ROOT = path.join(ROOT, "assets", "extracted", "comanche_hdd");
const FLAT_SHA256 = "a2c2b50d4e2d85ecbf210440927927323b0a176613beb25d74c0cdde8dae1a6c";
const TICK_US = 18356 * 1e6 / 1193182;
const SONG_BASE = 0x400000;     // above the image, where a heap allocation would be

function loadImage() {
  const exe = fs.readFileSync(path.join(ASSET_ROOT, "UNPACKED.EXE"));
  const header = (exe[8] | (exe[9] << 8)) * 16;
  const flat = exe.subarray(header + 0x1700, header + 0x1700 + 207648);
  if (crypto.createHash("sha256").update(flat).digest("hex") !== FLAT_SHA256) throw new Error("not the hashed DOS image");
  return Uint8Array.from(flat);
}

function loadSound() {
  const context = vm.createContext({ console, Uint8Array, Map, Error, Math, Number, String, Object, Array });
  context.globalThis = context;
  vm.runInContext(fs.readFileSync(path.join(ROOT, "jsComanche", "dos-sound.js"), "utf8"), context, { filename: "dos-sound.js" });
  return context.ComancheSound;
}

function main() {
  const args = process.argv.slice(2);
  const options = { device: 3, flags: 0, ticks: null, out: null, against: null };
  let file = null;
  for (let i = 0; i < args.length; i += 1) {
    if (args[i] === "--device") options.device = Number(args[++i]);
    else if (args[i] === "--flags") options.flags = Number(args[++i]);
    else if (args[i] === "--ticks") options.ticks = Number(args[++i]);
    else if (args[i] === "--out") options.out = args[++i];
    else if (args[i] === "--against") options.against = args[++i];
    else file = args[i];
  }
  if (!file) throw new Error("usage: export-sound-trace.js FILE [--device N] [--flags N] [--ticks N] [--out FILE.ev] [--against CAPTURE.json]");
  const Sound = loadSound();
  const driver = Sound.create(loadImage(), { hooks: { oplStatus: (() => { const s = [0x00, 0xC0]; return () => s.shift(); })() } });
  const song = Sound.decodeMusicFile(fs.readFileSync(path.join(ASSET_ROOT, file)));
  driver.placeSong(SONG_BASE, song);
  const lines = [];
  const pairs = [];
  const emit = (tick, context) => {
    for (const w of driver.takeWrites()) {
      if (w[0] !== "o") continue;
      lines.push(`W ${Math.round(tick * TICK_US)} ${context} ${w[1].toString(16)} ${w[2].toString(16)}`);
      pairs.push([w[1], w[2]]);
    }
  };
  driver.command(0x8000 | options.device);
  driver.command(0x3000 | options.device);
  driver.start(options.flags, SONG_BASE);
  emit(0, "M");
  let tick = 0;
  const limit = options.ticks !== null ? options.ticks : 200000;
  let after = 0;
  while (tick < limit) {
    tick += 1;
    driver.tick();
    emit(tick, "T");
    if (options.ticks === null && driver.command(0x6000) === 0) {
      after += 1;
      if (after > 20) break;
    }
  }
  if (options.out) {
    fs.mkdirSync(path.dirname(path.resolve(options.out)), { recursive: true });
    fs.writeFileSync(options.out, `${lines.join("\n")}\n`);
  }
  console.log(`${file}: ${tick} ticks (${(tick * TICK_US / 1e6).toFixed(1)} s), ${lines.length} OPL writes${options.out ? ` -> ${options.out}` : ""}`);
  if (options.against) {
    const capture = JSON.parse(fs.readFileSync(options.against, "utf8"));
    const theirs = [];
    let ticks = 0;
    for (const op of capture.ops) {
      for (const w of op.writes) if (w[0] === "o") theirs.push([w[1], w[2]]);
      if (op.op === "tick") ticks += 1;
      if (ticks >= tick && op.op === "tick") break;
    }
    const n = Math.min(pairs.length, theirs.length);
    let at = 0;
    while (at < n && pairs[at][0] === theirs[at][0] && pairs[at][1] === theirs[at][1]) at += 1;
    if (at < n || (options.ticks !== null && pairs.length !== theirs.length)) {
      console.log(`FAIL differs from the capture at write ${at}`);
      process.exit(1);
    }
    console.log(`ok   the first ${n} writes equal the original's (${options.against})`);
  }
}

main();
