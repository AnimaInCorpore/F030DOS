#!/usr/bin/env node
/*
 * js-sound-stream: the mixer bytes jsComanche/dos-sound.js produces for one
 * SND1 effect played alone from silence (the explosion, id 1, bl 0xFF, dl 0,
 * ecx 0 by default), N fills of 0x800 bytes, as raw bytes.
 *
 * N/A - target artefact: a test helper, no DOS routine.
 * record: analysis/functions/sound-falcon.md#verification
 *
 * Usage: node tools/js-sound-stream.js <outfile> [fills] [id] [dl] [ecx]
 */
"use strict";
const crypto = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const ROOT = path.resolve(__dirname, "..");
const ASSETS = path.join(ROOT, "assets", "extracted", "comanche_hdd");
const [out, fills = "40", id = "1", dl = "0", ecx = "0"] = process.argv.slice(2);
if (!out) { console.error("usage: js-sound-stream.js <outfile> [fills] [id] [dl] [ecx]"); process.exit(2); }

const exe = fs.readFileSync(path.join(ASSETS, "UNPACKED.EXE"));
const header = (exe[8] | (exe[9] << 8)) * 16;
const image = Uint8Array.from(exe.subarray(header + 0x1700, header + 0x1700 + 207648));
if (crypto.createHash("sha256").update(image).digest("hex") !== "a2c2b50d4e2d85ecbf210440927927323b0a176613beb25d74c0cdde8dae1a6c") throw new Error("image");
const context = vm.createContext({ console, Uint8Array, Map, Error, Math, Number, String, Object, Array });
context.globalThis = context;
vm.runInContext(fs.readFileSync(path.join(ROOT, "jsComanche", "dos-sound.js"), "utf8"), context, { filename: "dos-sound.js" });
const Sound = context.ComancheSound;
const driver = Sound.create(image, { hooks: {}, digitalFlag: 1, delayLoops: 492 });
const bank = Sound.decodeMusicFile(fs.readFileSync(path.join(ASSETS, "SND1.RLE")));
driver.placeSong(4218448, bank);
driver.pokeDword(0x19E98, 4218448);
driver.setRate(2);
driver.resetMixer();
driver.fx(Number(id), 0xFF, Number(dl), Number(ecx));
const chunks = [];
for (let i = 0; i < Number(fills); i += 1) chunks.push(Buffer.from(driver.fill()));
fs.writeFileSync(out, Buffer.concat(chunks));
