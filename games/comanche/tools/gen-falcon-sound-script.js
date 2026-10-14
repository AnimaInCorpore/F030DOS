#!/usr/bin/env node
/*
 * gen-falcon-sound-script: the input and the expected output of the Falcon
 * mixer test (tools/sound-mixer-test.s, driven by tools/check-falcon-sound.py).
 *
 * N/A - target artefact: a test generator, no DOS routine.
 * record: analysis/functions/sound-falcon.md#verification
 *
 * Writes into the output directory
 *   SNDTEST.SCR   the script the 68030 test program interprets (its header
 *                 documents the byte format),
 *   expected.bin  the bytes the program must write to SNDOUT.BIN, in order,
 *   manifest.json one entry per expected span: its name, source ("dos" = taken
 *                 from a capture of the original, "js" = what jsComanche/dos-sound.js
 *                 produces for the same calls, itself proven against DOS by
 *                 tools/check-js-sound.js), offset and length.
 *
 * Three kinds of scenario:
 *   - every digital capture of build/sound (the DOS's own mixed bytes), played
 *     twice: with the 0x800-byte fills of the capture, and with each fill cut into
 *     pieces of unequal size (the Falcon refill asks for ~250 bytes, not 0x800);
 *   - random call sequences replayed on the JavaScript driver: slot choice with
 *     every bl, shifts 0..7, steps, staging, reset, the dither masks, both curves;
 *   - the two transfer curves themselves, against the image's bytes 00004A0A/00004C0A.
 *
 * Usage: node tools/gen-falcon-sound-script.js <outdir> [--seed N] [--random N]
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
const FLAT_AT = 0x1700;

const BANKS = [
  { file: "SND1.RLE", variable: 0x19E98, at: 4218448, count: 7 },
  { file: "SPEAK1.RLE", variable: 0x19E9C, at: 4293120, count: 15 },
  { file: "SPEAK0.RLE", variable: 0x19EA0, at: 4485680, count: 2 },
];

function loadImage() {
  const exe = fs.readFileSync(path.join(ASSET_ROOT, "UNPACKED.EXE"));
  const header = (exe[8] | (exe[9] << 8)) * 16;
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

function mulberry32(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6D2B79F5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

class Script {
  constructor() { this.bytes = []; this.expected = []; this.manifest = []; }
  u8(...v) { for (const x of v) this.bytes.push(x & 0xFF); }
  u16(v) { this.bytes.push((v >> 8) & 0xFF, v & 0xFF); }
  u32(v) { this.bytes.push((v >>> 24) & 0xFF, (v >>> 16) & 0xFF, (v >>> 8) & 0xFF, v & 0xFF); }
  start() { this.u8(1); }
  fx(id, bl, dl, ecx) { this.u8(2, id, bl, dl); this.u32(ecx); }
  speechA(id) { this.u8(3, id); }
  speechB(id) { this.u8(4, id); }
  voice(bank, id, slot, dl, ecx) { this.u8(5, bank, id, slot, dl); this.u32(ecx); }
  silence(slot, dl) { this.u8(6, slot, dl); }
  rate(al) { this.u8(7, al); }
  reset() { this.u8(8); }
  curve(soft) { this.u8(10, soft ? 1 : 0); }
  tables() { this.u8(11); }
  resample(n) { this.u8(12); this.u16(n); }
  // A fill of `total` bytes, in the given pieces; `expect` are the bytes the pieces together produce.
  fill(pieces, expect, name, source) {
    let sum = 0;
    for (const p of pieces) { this.u8(9); this.u16(p); sum += p; }
    if (sum !== expect.length) throw new Error(`${name}: pieces ${sum} != expected ${expect.length}`);
    this.span(expect, name, source);
  }
  span(expect, name, source) {
    this.manifest.push({ name, source, offset: this.expected.length, length: expect.length });
    for (const b of expect) this.expected.push(b);
  }
  finish() { this.u8(0); }
}

// ---- the DOS captures ------------------------------------------------------
function splits(rng, total, split) {
  if (!split) return [total];
  const out = [];
  let left = total;
  const sizes = [1, 2, 3, 7, 31, 100, 222, 246, 250, 255, 256, 257, 300, 511, 512, 513, 700, 1000];
  while (left > 0) {
    const n = Math.min(left, sizes[Math.floor(rng() * sizes.length)]);
    out.push(n);
    left -= n;
  }
  return out;
}

// The capture's `voice` ops name the bank by its eax; map it back to (bank, id).
function voiceOf(op, banks) {
  for (let b = 0; b < banks.length; b += 1) {
    const base = banks[b].at;
    const bytes = banks[b].bytes;
    for (let id = 1; id <= banks[b].count; id += 1) {
      const rel = bytes[4 * id] | (bytes[4 * id + 1] << 8) | (bytes[4 * id + 2] << 16) | (bytes[4 * id + 3] << 24);
      if (((base + rel) >>> 0) === op.eax) return { bank: b, id };
    }
  }
  throw new Error(`no sample at ${op.eax.toString(16)}`);
}

// ---- random scenarios on the JavaScript driver ------------------------------
function randomScenario(script, Sound, image, rng, name, nOps) {
  const driver = Sound.create(image, { hooks: {}, digitalFlag: 1, delayLoops: 492 });
  const banks = BANKS.map((b) => {
    const bytes = Sound.decodeMusicFile(fs.readFileSync(path.join(ASSET_ROOT, b.file)));
    driver.placeSong(b.at, bytes);
    driver.pokeDword(b.variable, b.at);
    return { ...b, bytes };
  });
  const pick = (list) => list[Math.floor(rng() * list.length)];
  const chance = (p) => rng() < p;
  script.start();
  driver.setRate(2);
  script.rate(2);
  driver.resetMixer();
  script.reset();
  const steps = [0, 0x20000, 0x84A7, 0xFFFF, 0x8000, 0x10000, 0x1234, 0x38000, 0x4000, 0xC000];
  const record = (fillTotal) => {
    const pcm = Buffer.from(driver.fill());
    script.fill(splits(rng, 0x800, true), pcm, `${name} fill ${record.n}`, "js");
    record.n += 1;
  };
  record.n = 0;
  let curveSoft = false;
  for (let i = 0; i < nOps; i += 1) {
    const r = rng();
    if (r < 0.34) {
      const id = 1 + Math.floor(rng() * 7);
      const bl = chance(0.6) ? 0xFF : chance(0.3) ? 0xFE : Math.floor(rng() * 3);
      const dl = chance(0.5) ? 0 : Math.floor(rng() * 8);
      const ecx = chance(0.6) ? 0 : pick(steps);
      driver.fx(id, bl, dl, ecx);
      script.fx(id, bl, dl, ecx);
    } else if (r < 0.48) {
      const id = 1 + Math.floor(rng() * 15);
      driver.speechA(id);
      script.speechA(id);
    } else if (r < 0.53) {
      const id = 1 + Math.floor(rng() * 2);
      driver.speechB(id);
      script.speechB(id);
    } else if (r < 0.66) {
      const bank = Math.floor(rng() * 3);
      const id = 1 + Math.floor(rng() * banks[bank].count);
      const slot = Math.floor(rng() * 3);
      const dl = Math.floor(rng() * 8);
      const ecx = chance(0.6) ? 0 : pick(steps);
      const b = banks[bank];
      const rel = b.bytes[4 * id] | (b.bytes[4 * id + 1] << 8) | (b.bytes[4 * id + 2] << 16) | (b.bytes[4 * id + 3] << 24);
      driver.voice((b.at + rel) >>> 0, slot, dl, ecx);
      script.voice(bank, id, slot, dl, ecx);
    } else if (r < 0.70) {
      const slot = Math.floor(rng() * 3);
      const dl = Math.floor(rng() * 8);
      driver.voice(0x40E2, slot, dl, 0);
      script.silence(slot, dl);
    } else if (r < 0.73) {
      driver.resetMixer();
      script.reset();
    } else if (r < 0.77) {
      const al = chance(0.8) ? Math.floor(rng() * 18) : 18 + Math.floor(rng() * 200);
      driver.setRate(al);
      script.rate(al);
    } else if (r < 0.80) {
      curveSoft = !curveSoft;
      driver.pokeDword(0x5307, curveSoft ? 0x4A0A : 0x4C0A);
      script.curve(curveSoft);
    }
    // time passes: one fill, now and then a long stretch so samples play to their end
    const fills = chance(0.12) ? 4 + Math.floor(rng() * 12) : chance(0.7) ? 1 : 0;
    for (let k = 0; k < fills; k += 1) record();
  }
  for (let k = 0; k < 14; k += 1) record();                  // let everything play out
  return record.n;
}


// ---- the Falcon resampler (src/sound.s snd_resample), as an integer model -----
const RS_STEP = 59238;
function resampleScenario(script, Sound, image, rng, name, fx, totalOut) {
  const driver = Sound.create(image, { hooks: {}, digitalFlag: 1, delayLoops: 492 });
  const bytes = Sound.decodeMusicFile(fs.readFileSync(path.join(ASSET_ROOT, "SND1.RLE")));
  driver.placeSong(BANKS[0].at, bytes);
  driver.pokeDword(BANKS[0].variable, BANKS[0].at);
  driver.setRate(2);
  driver.resetMixer();
  driver.fx(fx.id, fx.bl, fx.dl, fx.ecx);
  script.start();
  script.rate(2);
  script.reset();
  script.fx(fx.id, fx.bl, fx.dl, fx.ecx);
  const input = [];                // every mixer byte generated so far
  let base = 0;                    // input index of the resampler's phase origin
  let phase = 0;
  const sizes = [1, 2, 3, 5, 100, 205, 246, 250, 400, 511, 512, 513, 700, 1000, 1023, 1024];
  let produced = 0;
  while (produced < totalOut) {
    const n = rng() < 0.5 ? sizes[Math.floor(rng() * sizes.length)] : 1 + Math.floor(rng() * 1024);
    const need = (((phase + (n - 1) * RS_STEP) >>> 16) + 2);
    while (input.length - base < need) for (const b of driver.fill()) input.push(b);
    const out = Buffer.alloc(n);
    for (let k = 0; k < n; k += 1) {
      const i = base + (phase >>> 16);
      const a = input[i], c = input[i + 1];
      const f = (phase & 0xFFFF) >>> 1;
      out[k] = ((a + (((c - a) * f) >> 15)) & 0xFF) ^ 0x80;
      phase += RS_STEP;
    }
    base += phase >>> 16;
    phase &= 0xFFFF;
    script.resample(n);
    script.span(out, `${name} resample ${produced}`, "js");
    produced += n;
  }
}

function main() {
  const args = process.argv.slice(2);
  const outDir = args[0];
  if (!outDir) { console.error("usage: gen-falcon-sound-script.js <outdir> [--seed N] [--random N]"); process.exit(2); }
  const seed = Number(args[args.indexOf("--seed") + 1]) || 20261007;
  const randomScenarios = args.includes("--random") ? Number(args[args.indexOf("--random") + 1]) : 2;
  fs.mkdirSync(outDir, { recursive: true });
  const image = loadImage();
  const Sound = loadSound();
  const rng = mulberry32(seed);
  const script = new Script();

  // The transfer curves against the image's bytes.
  script.start();
  script.tables();
  script.span(Buffer.from(image.subarray(0x4A0A, 0x4A0A + 512)), "curve soft 00004A0A", "dos");
  script.span(Buffer.from(image.subarray(0x4C0A, 0x4C0A + 512)), "curve loud 00004C0A", "dos");

  const names = fs.readdirSync(path.join(ROOT, "build", "sound")).filter((f) => /^digital-.*\.json$/.test(f)).sort();
  if (!names.length) throw new Error("build/sound has no digital captures: run work/capture_sound_fixtures.sh");
  for (const f of names) {
    const capture = JSON.parse(fs.readFileSync(path.join(ROOT, "build", "sound", f), "utf8"));
    if (capture.image_sha256 !== FLAT_SHA256) throw new Error(`${f}: another image`);
    // rewrite the voice ops to (bank, id) once, from the banks as the capture placed them
    const banks = BANKS.map((b) => ({ ...b, bytes: Sound.decodeMusicFile(fs.readFileSync(path.join(ASSET_ROOT, b.file))) }));
    for (const op of capture.ops) if (op.op === "voice") { const v = voiceOf(op, banks); op.bank = v.bank; op.id = v.id; }
    for (const split of [false, true]) {
      const copy = JSON.parse(JSON.stringify(capture));
      // handled here rather than in addCapture so the voice op carries its bank
      script.start();
      let fills = 0;
      const label = `${f.replace(/\.json$/, "")}${split ? " (cut)" : ""}`;
      for (const op of copy.ops) {
        switch (op.op) {
          case "digital": case "bank": break;
          case "rate": script.rate(op.al); break;
          case "reset": script.reset(); break;
          case "fx": script.fx(op.ebp, op.bl, op.dl, op.ecx); break;
          case "speecha": script.speechA(op.al); break;
          case "speechb": script.speechB(op.al); break;
          case "voice": script.voice(op.bank, op.id, op.bl, op.dl, op.ecx); break;
          case "silence_voice": script.silence(op.bl, op.dl); break;
          case "poke32":
            if (op.address !== 0x5307) throw new Error(`${label}: poke32 ${op.address.toString(16)}`);
            script.curve(op.value === 0x4A0A);
            break;
          case "fill": {
            const pcm = Buffer.from(op.pcm, "hex");
            script.fill(splits(rng, pcm.length, split), pcm, `${label} fill ${fills}`, "dos");
            fills += 1;
            break;
          }
          default: throw new Error(`${label}: unknown op ${op.op}`);
        }
      }
    }
  }
  for (let i = 0; i < randomScenarios; i += 1) {
    randomScenario(script, Sound, image, rng, `random ${i}`, 260);
  }
  // the resampler, fed by the mixer: an explosion, a launch at double pitch, speech is not in SND1
  const rs = [{ id: 1, bl: 0xFF, dl: 0, ecx: 0 }, { id: 4, bl: 0xFF, dl: 1, ecx: 0x20000 },
    { id: 2, bl: 0xFF, dl: 3, ecx: 0 }, { id: 7, bl: 0xFE, dl: 0, ecx: 0 }];
  for (let i = 0; i < rs.length; i += 1) resampleScenario(script, Sound, image, rng, `resampler ${i}`, rs[i], 36000);
  script.finish();
  fs.writeFileSync(path.join(outDir, "SNDTEST.SCR"), Buffer.from(script.bytes));
  fs.writeFileSync(path.join(outDir, "expected.bin"), Buffer.from(script.expected));
  fs.writeFileSync(path.join(outDir, "manifest.json"), JSON.stringify(script.manifest));
  console.log(`script ${script.bytes.length} bytes, expected ${script.expected.length} bytes, ${script.manifest.length} spans`);
}

main();
