#!/usr/bin/env node
/*
 * Deterministic proof gate for the connected JavaScript DOS-attract slice.
 *
 * This is deliberately independent of a live browser. It checks provenance
 * comments, the hashed DOS image, the generated Q31 table, authored mission
 * resource selection, decoded format boundaries, palette representations, the
 * independent HIGH.DTL projection table, the complete 250x192 terrain walk,
 * and the supported pass-one replay transition through a mocked Canvas. The
 * route trace is the source-generation boundary; this script validates the
 * JavaScript counterpart after that route has been recorded.
 */

"use strict";

const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { proveMenus } = require("./prove-browser-menus.js");

const ROOT = path.resolve(__dirname, "..");
const JS_ROOT = path.join(ROOT, "jsComanche");
const ASSET_ROOT = path.join(ROOT, "assets", "extracted", "comanche_hdd");
const DOS_IMAGE = path.join(ASSET_ROOT, "UNPACKED.EXE");
const RECORD_FILE = path.join(ROOT, "analysis", "functions", "browser-attract.md");
const DOS_SHA256 = "4498ab2b797379a492208aed4ed1947bcea0dccde3363fb98d03e8318cefd697";

function fail(message) {
  throw new Error(`proof failed: ${message}`);
}

function check(condition, message) {
  if (!condition) fail(message);
}

function sha256(bytes) {
  return crypto.createHash("sha256").update(bytes).digest("hex");
}

function sourceAnnotation(lines, index) {
  const comments = [];
  for (let cursor = index - 1; cursor >= 0; cursor -= 1) {
    const line = lines[cursor].trim();
    if (!line) continue;
    if (line.startsWith("//") || line.startsWith("/*") || line.startsWith("*") || line.startsWith("*/")) {
      comments.unshift(line);
      continue;
    }
    break;
  }
  return comments.join(" ");
}

// The anchors browser-attract.md actually defines, in the form a link to it
// would use: lowercased, backticks and punctuation dropped, spaces hyphenated.
// A record section is written as "## `view-basis`" and answers to
// "#view-basis"; the prose sections are matched too, so a citation may point
// at either.
function recordAnchors() {
  const source = fs.readFileSync(RECORD_FILE, "utf8");
  const anchors = new Set();
  for (const line of source.split(/\r?\n/)) {
    const heading = /^#{2,6}\s+(.+?)\s*$/.exec(line);
    if (!heading) continue;
    anchors.add(heading[1]
      .toLowerCase()
      .replace(/`/g, "")
      .replace(/[^\w\s-]/g, "")
      .trim()
      .replace(/\s+/g, "-"));
  }
  check(anchors.size > 0, "browser-attract.md defines no headings to cite");
  return anchors;
}

// Every row of a record table has to have the column count its header does.
//
// The §4.2 records are markdown tables, and a literal `|` written in prose -
// `|dx|` for a magnitude, `max|e|` for an error bound - splits that row into
// extra cells. The table stops rendering as a table from there down, and
// nothing else notices: the anchors still resolve, the text is still in the
// file, and the record silently stops being readable as a record. It happened
// twice while these records were being written.
//
// The header's own count is the reference rather than a fixed 3, so a future
// record with different columns is checked against itself.
function checkRecordTables() {
  const lines = fs.readFileSync(RECORD_FILE, "utf8").split(/\r?\n/);
  let header = null;
  let headerLine = 0;
  let rows = 0;
  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index];
    if (!line.startsWith("|")) {
      header = null;
      continue;
    }
    const pipes = (line.match(/\|/g) || []).length;
    if (header === null) {
      header = pipes;
      headerLine = index + 1;
    } else {
      check(pipes === header,
        `browser-attract.md:${index + 1} has ${pipes} pipes where the table `
        + `opened at line ${headerLine} has ${header} - an unescaped '|' in `
        + "prose splits the row into extra cells");
    }
    rows += 1;
  }
  check(rows > 0, "browser-attract.md has no record tables");
  return rows;
}

function auditJavaScriptProvenance() {
  const controlNames = new Set(["if", "for", "while", "switch", "catch", "with"]);
  const anchors = recordAnchors();
  const tableRows = checkRecordTables();
  // Every citation in every source, not only the ones beside a definition:
  // a record that names no section is a record that does not exist, and the
  // well-formedness check below cannot tell the difference. 6797903 landed
  // with its whole view subsystem citing a #view-basis that had not been
  // written, and this gate passed it.
  const citedAnywhere = new Set();
  const files = fs.readdirSync(JS_ROOT)
    .filter((name) => name.endsWith(".js"))
    .sort();
  check(files.length > 0, "no JavaScript sources found");

  for (const name of files) {
    const source = fs.readFileSync(path.join(JS_ROOT, name), "utf8");
    const lines = source.split(/\r?\n/);
    for (let index = 0; index < lines.length; index += 1) {
      const cited = lines[index].match(/browser-attract\.md#([-\w]+)/g) || [];
      for (const reference of cited) {
        const anchor = reference.replace(/^.*#/, "");
        citedAnywhere.add(anchor);
        check(anchors.has(anchor),
          `${name}:${index + 1} cites browser-attract.md#${anchor}, which has no section`);
      }
    }
  }

  for (const name of files) {
    const file = path.join(JS_ROOT, name);
    const lines = fs.readFileSync(file, "utf8").split(/\r?\n/);
    const definitions = [];
    for (let index = 0; index < lines.length; index += 1) {
      const line = lines[index];
      if (/^\s*\(\(\)\s*=>\s*\{/.test(line)) {
        definitions.push([index, "anonymous module wrapper"]);
      }
      const functionMatch = /^\s*(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(/.exec(line);
      if (functionMatch) definitions.push([index, functionMatch[1]]);
      const classMatch = /^\s*class\s+([A-Za-z_$][\w$]*)\b/.exec(line);
      if (classMatch) definitions.push([index, `class ${classMatch[1]}`]);
      const methodMatch = /^\s*(?:async\s+)?([A-Za-z_$][\w$]*)\s*\([^;{}]*\)\s*\{/.exec(line);
      if (methodMatch && !controlNames.has(methodMatch[1])) definitions.push([index, methodMatch[1]]);
      const arrowMatch = /^\s*(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s+)?(?:\([^)]*\)|[A-Za-z_$][\w$]*)\s*=>/.exec(line);
      if (arrowMatch) definitions.push([index, arrowMatch[1]]);
    }

    for (const [index, symbol] of definitions) {
      const annotation = sourceAnnotation(lines, index);
      const hasRecord = /record:\s*(?:\/\/\s*)?analysis\/functions\/browser-attract\.md#[-\w]+/.test(annotation);
      const hasDos = /DOS:\s+FUN_[0-9A-F/]+\s*\[[^\]]+\]/.test(annotation);
      const hasTarget = /Target artefact|N\/A - platform replacement/.test(annotation);
      check(hasRecord, `${name}:${index + 1} ${symbol} has no adjacent durable record`);
      check(hasDos || hasTarget, `${name}:${index + 1} ${symbol} has neither DOS identity nor target marker`);
    }
  }

  const sineSource = fs.readFileSync(path.join(JS_ROOT, "sine-q31.js"), "utf8");
  check(/Target data artefact; record: analysis\/functions\/browser-attract\.md#sine-table/.test(sineSource),
    "sine-q31.js has no durable data record");
  return { files: files.length, anchors: citedAnywhere.size, tableRows };
}

function makeCanvas(width = 320, height = 240) {
  const context = {
    imageSmoothingEnabled: false,
    fillStyle: "#000",
    createImageData: (w, h) => ({ data: new Uint8ClampedArray(w * h * 4) }),
    putImageData() {},
    fillRect() {},
    drawImage() {},
  };
  return {
    width,
    height,
    getContext() { return context; },
  };
}

function makeContext() {
  const canvas = makeCanvas();
  const document = {
    getElementById() { return canvas; },
    createElement() { return makeCanvas(0, 0); },
  };
  const sandbox = {
    console,
    document,
    location: { href: "http://127.0.0.1:8765/F030Comanche/jsComanche/" },
    URL,
    TextDecoder,
    Uint8Array,
    Uint8ClampedArray,
    Uint16Array,
    Int16Array,
    Int32Array,
    ArrayBuffer,
    BigInt,
    Map,
    Set,
    Math,
    Number,
    Object,
    String,
    Error,
    TypeError,
    fetch: async (url) => {
      const pathname = new URL(url).pathname;
      const relative = pathname.replace(/^\/F030Comanche\//, "");
      const file = path.resolve(ROOT, relative);
      check(file.startsWith(ROOT + path.sep), `host loader escaped workspace: ${file}`);
      if (!fs.existsSync(file)) return { ok: false, status: 404, arrayBuffer: async () => new ArrayBuffer(0) };
      const bytes = fs.readFileSync(file);
      return {
        ok: true,
        status: 200,
        arrayBuffer: async () => bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength),
      };
    },
    requestAnimationFrame() { return 1; },
    cancelAnimationFrame() {},
  };
  sandbox.window = sandbox;
  sandbox.globalThis = sandbox;
  return { sandbox, canvas };
}

function loadSources(context) {
  for (const name of ["dos-fs.js", "dos-data.js", "sine-q31.js", "object-bearing.js", "dos-text-data.js", "dos-pilot.js", "dos-menu.js", "dos-damage.js", "dos-runtime.js"]) {
    const source = fs.readFileSync(path.join(JS_ROOT, name), "utf8");
    vm.runInContext(source, context, { filename: name });
  }
}

function dominantIndex(bytes) {
  const counts = new Uint32Array(256);
  for (const value of bytes) counts[value] += 1;
  let best = 0;
  for (let index = 1; index < counts.length; index += 1) {
    if (counts[index] > counts[best]) best = index;
  }
  return best;
}

function assertRgb565Blue(word, label) {
  const red = (word >> 11) & 0x1f;
  const green = (word >> 5) & 0x3f;
  const blue = word & 0x1f;
  check(blue > red && blue > 8, `${label} is not a blue sky word: 0x${word.toString(16)}`);
}

// Independent DOS arithmetic oracle for FUN_00015AD9. Keep this separate
// from dos-runtime.js so the proof does not merely call the implementation
// under test twice.
function dosHi32(left, right) {
  return Number((BigInt(left | 0) * BigInt(right | 0)) >> 32n) | 0;
}

function dosProjectionTable(detail) {
  const result = new Uint8Array(250 * 256);
  for (let ring = 0; ring < 250; ring += 1) {
    const slope = dosHi32(detail.tables[2][ring], 0x03000000);
    const bias = detail.tables[3][ring] | 0;
    for (let height = 0; height < 256; height += 1) {
      // DOS: row = clamp(high32(((height << 24) - 0x80000000) * slope) + bias, 0, 0xff00).
      const fixed = ((BigInt(height - 128) * (1n << 24n) * BigInt(slope)) >> 32n) + BigInt(bias);
      result[(ring * 256) + height] = fixed <= 0n ? 0 : fixed >= 0xff00n ? 0xff : Number(fixed >> 8n);
    }
  }
  return result;
}

async function proveRuntime() {
  const { sandbox, canvas } = makeContext();
  const context = vm.createContext(sandbox);
  loadSources(context);

  const runtimeSource = fs.readFileSync(path.join(JS_ROOT, "dos-runtime.js"), "utf8");
  check(/const left = xReference - sprite\.xOffset;/.test(runtimeSource),
    "sprite blitters quantize DOS pixel coordinates");
  check(!/Math\.floor\(\(xReference - sprite\.xOffset\) \/ 4\)/.test(runtimeSource),
    "sprite blitters still contain the retired four-pixel quantization");
  check(/eight-bit fractional accumulator seeded at 0x80/.test(runtimeSource),
    "sight-line walker does not record the DOS byte-accumulator contract");
  check(!/const slope = Math\.floor\(\(dy \* 0x10000\) \/ \(dx \+ 1\)\)/.test(runtimeSource),
    "sight-line walker still uses the retired full-width accumulator");
  check(/const cameraHeight = \(127 - \(this\.view_camera_altitude >> 1\)\) & 0xff;/.test(runtimeSource)
    && /this\.buildViewBasis\(\);/.test(runtimeSource),
    "terrain camera page does not use the selected DOS view basis and 127-altitude\/2 bias");
  check(/occlusion\.fill\(PAGE_ANCHOR\)/.test(runtimeSource),
    "terrain occlusion is not seeded at the DOS page anchor");
  check(/this\.drawTerrainSpan\(column, screenRow \+ 1 - tilt, oldHorizon - tilt, word\);/.test(runtimeSource),
    "terrain spans do not preserve the DOS inclusive row order");
  check(/const strip = \(origin \+ TERRAIN_COLS - 1 - column\) & \(SKY_STRIPS - 1\);/.test(runtimeSource),
    "sky strips do not preserve the DOS right-to-left column pairing");
  check(/this\.frame\.set\(this\.terrainSurface\);/.test(runtimeSource)
    && /this\.terrainSurface\.set\(this\.frame\);/.test(runtimeSource)
    && /drawCockpitStage/.test(runtimeSource),
  "terrain surface is not persistent across console\/HUD composition");

  check(/this\.objects = this\.spawnMissionObjects\(\);/.test(runtimeSource)
    && /this\.drawTerrainStage\(\);/.test(runtimeSource)
    && /objectTransform\(\)/.test(runtimeSource)
    && /objectFindPage\(object\)/.test(runtimeSource),
  "attract frame does not preserve the DOS active-object pass");
  // The contract is that one presentation admits at most ONE logical tick, so
  // a slow frame never integrates several replay records into one displayed
  // frame. This used to be asserted by pinning the accumulator line verbatim,
  // which froze an implementation detail rather than the contract - and the
  // detail it froze was a bug: capping before the test threw away any frame
  // shorter than a tick, giving 37.5 ticks/s at 75 Hz and 48.0 at 144 Hz
  // against the intended 60. Assert the shape that matters instead.
  {
    const loop = /const presentLoop = \(now\) => \{[\s\S]*?\n      \};/.exec(runtimeSource);
    check(loop, "the fixture scheduler's presentation loop was not found");
    const body = loop[0];
    const ticks = (body.match(/this\.onTick\(\);/g) || []).length;
    assert.equal(ticks, 1, "the presentation loop admits more than one tick per frame");
    check(!/for \([^)]*\) this\.onTick\(\);/.test(body) && !/while \([^)]*\)[\s\S]{0,40}this\.onTick\(\);/.test(body),
      "browser scheduler still performs catch-up flight integrations");
    check(/this\.remainder \+= elapsed;/.test(body),
      "the fixture accumulator does not carry unused frame time");
    check(/this\.remainder = Math\.min\(this\.remainder, FIXTURE_TICK_MS\);/.test(body),
      "the fixture accumulator is not capped, so a stall could spiral");
  }

  const image = fs.readFileSync(DOS_IMAGE);
  check(sha256(image) === DOS_SHA256, "authoritative DOS image SHA-256 changed");
  const headerBytes = image.readUInt16LE(8) * 16;
  const pages = image.readUInt16LE(4);
  const lastPageBytes = image.readUInt16LE(2);
  const imageEnd = pages * 512 - (512 - lastPageBytes);
  const loadModule = image.subarray(headerBytes, imageEnd);
  const flat = loadModule.subarray(0x1700);
  const sine = sandbox.ComancheSineQ31;
  check(sine instanceof Int32Array && sine.length === 640, "Q31 table is not 640 entries");
  for (let index = 0; index < 640; index += 1) {
    // The DOS disassembly quotes flat addresses; the unpacked MZ image has an
    // MZ header and a 0x1700-byte bootstrap before the flat program.
    check(sine[index] === flat.readInt32LE(0x32120 + index * 4), `Q31 table differs at entry ${index}`);
  }
  check(sine[0] === 0 && sine[128] === 0x7fffffff && sine[384] === -0x80000000,
    "Q31 boundary entries are wrong");
  for (let index = 0; index < 128; index += 1) check(sine[index] === sine[index + 512], `Q31 overhang differs at ${index}`);
  const bearing = sandbox.ComancheObjectBearingCorrection;
  check(bearing instanceof Uint8Array && bearing.length === 2048,
    "object/view bearing table is not the DOS 2048-byte range");
  for (let index = 0; index < bearing.length; index += 1) {
    check(bearing[index] === flat[0x223a5 + index], `bearing correction differs at ${index}`);
  }

  const evidence = await sandbox.ComancheDOS.loadAttractEvidence();
  const expected = [
    ["D1.DTA", "C1.DTA", "P12.DTA", "SKY2.RLE"],
    ["D4.DTA", "C4.DTA", "NP44.DTA", "SKY4.RLE"],
    ["D3.DTA", "C3.DTA", "P34.DTA", "SKY4.RLE"],
    ["D2.DTA", "C2.DTA", "P23.DTA", "SKY3.RLE"],
  ];
  assert.equal(evidence.passes.length, 4, "attract evidence does not contain four passes");
  for (let index = 0; index < expected.length; index += 1) {
    const pass = evidence.passes[index];
    assert.deepEqual([
      pass.selected.heightName,
      pass.selected.colourName,
      pass.selected.paletteName,
      pass.selected.skyName,
    ], expected[index], `pass ${index} resource family`);
    assert.equal(pass.mission.campaignDigit, 0, `pass ${index} is not campaign zero`);
    assert.equal(pass.mission.campaignIndex, index, `pass ${index} mission index`);
    assert.equal(pass.height.pixels.length, 1024 * 1024, `pass ${index} height map size`);
    assert.equal(pass.colour.pixels.length, 1024 * 1024, `pass ${index} colour map size`);
    assert.equal(pass.sky.payload.width, 512, `pass ${index} sky width`);
    assert.equal(pass.sky.payload.height, 150, `pass ${index} sky height`);
    assert.equal(pass.detail.byteLength, 5004, `pass ${index} HIGH.DTL size`);
    assert.equal(pass.demos.size, 4, `pass ${index} demo set`);
    for (const demoIndex of [0, 1, 2, 3]) {
      const demo = pass.demos.get(`DEMO${demoIndex}.SCR`);
      check(demo && demo.declaredLength === fs.statSync(path.join(ASSET_ROOT, `DEMO${demoIndex}.SCR`)).size - 4,
        `DEMO${demoIndex} boundary`);
      check((demo.declaredLength - 13) % 8 === 0, `DEMO${demoIndex} record width`);
      const raw = fs.readFileSync(path.join(ASSET_ROOT, `DEMO${demoIndex}.SCR`));
      assert.equal(demo.header.x, raw.readInt32LE(4), "replay X byte order/sign");
      assert.equal(demo.header.y, raw.readInt32LE(8), "replay Y byte order/sign");
      assert.equal(demo.header.angle, raw.readUInt32LE(12), "replay angle byte order");
      for (const record of demo.records) {
        assert.equal(record.axis1, raw.readInt16LE(record.offset + 4), "axis1 byte order/sign");
        assert.equal(record.axis2, raw.readInt16LE(record.offset + 6), "axis2 byte order/sign");
      }
    }

    const paletteBytes = await sandbox.ComancheDOS.readDosFile(pass.selected.paletteName);
    const dtaPalette = pass.palette.palette;
    for (let channel = 0; channel < 768; channel += 1) {
      assert.equal(dtaPalette.rgb[channel], paletteBytes[dtaPalette.offset + 1 + channel],
        `${pass.selected.paletteName} raw palette channel ${channel}`);
      assert.equal(dtaPalette.sixBit[channel], paletteBytes[dtaPalette.offset + 1 + channel] >> 2,
        `${pass.selected.paletteName} DAC conversion ${channel}`);
    }

    const skyBytes = await sandbox.ComancheDOS.decodeKrl(
      await sandbox.ComancheDOS.readDosFile(pass.selected.skyName), pass.selected.skyName,
    );
    for (let channel = 0; channel < 768; channel += 1) {
      assert.equal(pass.sky.payload.palette.sixBit[channel], skyBytes.image[pass.sky.payload.palette.offset + 1 + channel],
        `${pass.selected.skyName} SG palette channel ${channel}`);
    }
  }

  const runtime = sandbox.ComancheRuntime.create({ canvas, evidence });
  assert.equal(runtime.pass, 1, "attract cycle does not begin at pass one");
  assert.equal(runtime.evidence.mission.campaignIndex, 1, "pass-one mission is not installed");
  assert.equal(runtime.evidence.selected.skyName, "SKY4.RLE", "pass-one sky is not SKY4");
  assert.equal(runtime.screen, "fanfare", "pass-one screen is not fanfare");
  const expectedProjection = dosProjectionTable(runtime.evidence.detail);
  check(runtime.ringPageTable.length === expectedProjection.length, "DOS projection table has the wrong size");
  for (let index = 0; index < expectedProjection.length; index += 1) {
    assert.equal(runtime.ringPageTable[index], expectedProjection[index], `HIGH.DTL projection differs at ${index}`);
  }
  runtime.advanceTicks(1080);
  assert.equal(runtime.mode, "demo", "opening screens did not transition to replay");
  assert.equal(runtime.demoIndex, 1, "pass-one replay is not DEMO1");
  assert.equal(runtime.demoCursor, 0, "replay consumed input before its first drawn frame");
  assert.equal(runtime.objects.length, runtime.evidence.mission.objectCount,
    "attract replay did not install the authored mission records including slot 31");
  assert.equal(runtime.flight.x, runtime.demo.header.x >> 6, "DEMO X header was not converted from DOS 10.22");
  assert.equal(runtime.flight.y, runtime.demo.header.y >> 6, "DEMO Y header was not converted from DOS 10.22");
  // 0002920E-00029234: the mission parses NINE placement records, types
  // 0,2,2,2,2,2,2,2,2, and [0x19D64] = 9. Record 0 is the type-0 entry
  // "0,0,0,1,0,0,0,0,0,0,0", dispatch entry 0 at 00023462, which installs the
  // fixed slot-31 object 00007CC5's camera aims at and 00024C0A draws. These
  // assertions previously pinned the eight-record parse that dropped it.
  // 00019689's cases load consol1s..consol4s for variants 1..4 and consol5s
  // for 5, 6 and 7 alike, so all five have to be staged, not just the
  // cockpit's. Only variant 1's is 290 rows; the four the external views use
  // are 245. DEMO1 spends 178 frames in variant 6 and 153 in variant 7, so a
  // missing CONSOL5S would leave 41% of the pass drawing the wrong panel.
  {
    const images = runtime.evidence.consoleImages;
    check(images && images.length === 6, "the five console images are not staged");
    for (let digit = 1; digit <= 5; digit += 1) {
      const image = images[digit];
      check(image, `CONSOL${digit}S.DTA is missing from the evidence set`);
      assert.equal(image.header.widthMax + 1, 328,
        `CONSOL${digit}S.DTA is not the authored 328-byte pitch`);
      assert.equal(image.header.heightMax + 1, digit === 1 ? 290 : 245,
        `CONSOL${digit}S.DTA has the wrong authored height`);
      check(runtime.consoleLookups[digit], `CONSOL${digit}S.DTA has no remapped palette`);
    }
  }
  assert.equal(runtime.evidence.mission.objectCount, 9,
    "campaign-0 mission 1 does not parse the DOS nine placement records");
  // Joined rather than deepEqual: runtime.objects is built inside the vm
  // realm, so its Array prototype is not this one and deepStrictEqual
  // rejects it on identity alone.
  assert.equal(runtime.objects.map((entry) => entry.type).join(","), "0,2,2,2,2,2,2,2,2",
    "DEMO1 placement record types are not the DOS 0,2,2,2,2,2,2,2,2");
  assert.equal(runtime.objects[0].slot, 31, "the type-0 record did not install slot 31");
  assert.equal(runtime.objects[0].stateAddr, 0x23800, "slot-31 object state is not DOS 00023800");
  assert.equal(runtime.objects[0].drawAddr, 0x24c0a, "slot-31 object draw is not DOS 00024C0A");
  assert.equal(runtime.objects[1].stateAddr, 0x23cf0, "DEMO1 first type-2 object state is not DOS 00023CF0");
  assert.equal(runtime.objects[1].drawAddr, 0x24fed, "DEMO1 first type-2 object draw is not DOS 00024FED");
  assert.equal(runtime.objects[1].modelA.name, "TANK.RLE", "DEMO1 model A did not resolve f2 to TANK.RLE");
  assert.equal(runtime.objects[1].modelB.name, "TURR.RLE", "DEMO1 model B did not resolve f3 to TURR.RLE");

  // 00019689's view cases against the DOS capture. Traced on the shipped
  // image with work/trace_replay_flight.py --view-basis, breaking at 00007D7F
  // once per integration tick. DEMO1 takes 0x07 into the chase camera at
  // record 30, 0x08 into the fixed camera at 206 and 0x02 back to the cockpit
  // at 357; 41% of the pass is external, so dropping these keys draws it all
  // from inside the helicopter.
  //
  // These are RECORD indices. The capture's own transitions land at ticks 31,
  // 209 and 362 because the 00007D7F breakpoint samples the basis build after
  // the record is consumed, and 00019689's tail runs two further frames of
  // its own before the next record.
  {
    const records = runtime.demo.records;
    const before = runtime.view_variant;
    const timeline = [];
    let variant = 1;
    runtime.view_variant = 1;
    for (let index = 0; index < records.length; index += 1) {
      const key = records[index].key & 0xff;
      if (key >= 0x02 && key <= 0x09) runtime.applyViewKey(key);
      if ((runtime.view_variant & 0xff) !== variant) {
        variant = runtime.view_variant & 0xff;
        timeline.push(`${index}:${variant}`);
      }
    }
    runtime.view_variant = before;
    assert.equal(timeline.join(" "), "30:6 206:7 357:1",
      "DEMO1 view-key timeline does not match the DOS capture");
  }
  assert.equal(runtime.evidence.objectBanks[2].payload.pixelLayout, "column-bottom-first",
    "mission object SG banks were decoded with the planar layout");
  const firstRecord = runtime.currentRecord();
  check(firstRecord, "pass-one replay has no first record");
  runtime.advanceTicks(1);
  assert.equal(runtime.demoCursor, 1, "replay did not consume one record after drawing");
  assert.deepEqual(Array.from(runtime.lastTrace.input), Array.from(firstRecord.raw), "replay trace bytes changed");
  check(/^[0-9a-f]{8}$/.test(runtime.lastTrace.framebufferHash), "frame trace has no deterministic RGB565 hash");

  // QEMU reaches the replay callback table and allocates dynamic slots from
  // DEMO1 trigger records. Keep that boundary executable in the proof rather
  // than treating weapons/effects as an untested visual convention.
  runtime.enterDemo(1);
  runtime.advanceTicks(12);
  // The tanks' aim raises the CHAF threat flag in the first frame and the
  // countermeasure decision at 00019555 launches a cloud (DOS slot 130 from
  // record 1, work/replay_dos/objects-demo1.json), so the first dynamic slot
  // is not the weapon; the weapon is the one that is not a countermeasure.
  const dynamicWeapon = runtime.objects.find((object) => object.dynamic && object.active && !object.effectCounter);
  check(dynamicWeapon, "DEMO1 trigger records did not allocate a DOS dynamic slot");
  assert.equal(dynamicWeapon.stateAddr, 0x24680, "weapon selector did not use DOS callback state 00024680");
  assert.equal(dynamicWeapon.bankName, "HELL.RLE", "weapon selector did not resolve DOS model pointer 00019E80");
  assert.equal(runtime.evidence.dynamicBanks.get("BOOM.RLE").payload.count, 20,
    "DOS 00019E88 BOOM bank was not loaded");

  // The QEMU-traced 00022A00/00022AA0 factories are also executable through
  // the replay effect gates, including their authored timers and bank names.
  runtime.flight.altitude = 0x40;
  runtime.effectATrigger = true;
  runtime.dispatchFlightEffects();
  // The key path (0001959F -> 00022A00/00022AA0) launches without the "none in
  // the air" test, so a countermeasure the object pass already raised can be
  // in flight; the one this call made is the freshest, i.e. the one whose
  // timer (counted down every tick) is highest.
  const freshest = (counter) => runtime.objects
    .filter((object) => object.effectCounter === counter && object.active)
    .sort((left, right) => right.timer - left.timer)[0];
  const bull = freshest("A");
  check(bull, "DOS BULL effect factory did not allocate a transient slot");
  assert.equal(bull.stateAddr, 0x24480, "BULL effect state is not DOS 00024480");
  assert.equal(bull.bankName, "BULL.RLE", "BULL effect bank is not DOS 00019E74");
  assert.equal(bull.timer, 0x14, "BULL effect timer is not DOS 0x14");
  runtime.effectBTrigger = true;
  runtime.dispatchFlightEffects();
  const chaff = freshest("B");
  check(chaff, "DOS CHAF effect factory did not allocate a transient slot");
  assert.equal(chaff.stateAddr, 0x244a0, "CHAF effect state is not DOS 000244A0");
  assert.equal(chaff.bankName, "CHAF.RLE", "CHAF effect bank is not DOS 00019E78");
  assert.equal(chaff.timer, 0x1e, "CHAF effect timer is not DOS 0x1E");

  // Each attract pass owns a different authored mission/object-bank family.
  // Draw a short prefix of every replay so the factory and scaled SG path are
  // not only covered by DEMO1's tank pair.
  for (let passIndex = 0; passIndex < 4; passIndex += 1) {
    runtime.pass = passIndex;
    runtime.installPassEvidence(evidence.passes[passIndex]);
    runtime.enterDemo(passIndex);
    assert.equal(runtime.objects.length, runtime.evidence.mission.objectCount,
      `pass ${passIndex} object count`);
    if (passIndex === 3) {
      const type4 = runtime.objects.find((object) => object.stateAddr === 0x23840);
      check(type4, "DEMO3 did not install the DOS 00023840 type-4 state");
      assert.equal(type4.drawAddr, 0x24fed, "DEMO3 type-4 draw route is not DOS 00024FED");
    }
    runtime.advanceTicks(3);
  }

  // Independent traversal oracle for FUN_0000D950. Replacing the sample
  // emitter lets this check cover every ring/column coordinate without
  // depending on the renderer's own map lookup or span writer.
  // 00007AA0's transfer spans exactly 168 rows - surface 46..213, screen
  // 0..167 - at both captured variants, the 261-run shaped consol1s list and
  // the 168-run full-width consol5s one. Below it the original leaves its page
  // standing. This port clipped at VIEW_H - 1 and drew terrain into rows
  // 168..239, so the bound is asserted by writing past it and checking the
  // sentinel survives.
  {
    const column = 96;
    const x = (column - 16) * 2;
    const sentinel = 0x1234;
    for (let row = 0; row < 240; row += 1) runtime.frame[(row * 320) + x] = sentinel;
    runtime.drawTerrainSpan(column, 0, 239, 0x7fff);
    assert.equal(runtime.frame[(167 * 320) + x], 0x7fff,
      "the surface transfer does not reach screen row 167");
    for (const row of [168, 200, 239]) {
      assert.equal(runtime.frame[(row * 320) + x], sentinel,
        `the surface transfer wrote to screen row ${row}, past 00007AA0's 168-row extent`);
    }
  }

  runtime.enterDemo(0);
  const originalDrawTerrainSample = runtime.drawTerrainSample;
  const samples = [];
  runtime.drawTerrainSample = (column, x, y, cameraHeight) => samples.push({ column, x, y, cameraHeight });
  // drawTerrain is called here without its frame stage, so the basis 0000D950
  // builds at its first instruction has to be established the same way the
  // stage does. The oracle below derives the walk from the flight angle, which
  // is what variant 1's identity handler leaves in [00019CB0]/[00019CB4].
  runtime.buildViewBasis();
  assert.equal(runtime.view_variant, 1, "replay entry is not the DOS cockpit variant");
  runtime.drawTerrain();
  runtime.drawTerrainSample = originalDrawTerrainSample;
  assert.equal(samples.length, 250 * 192, "DOS terrain walk does not visit 250 rings x 192 columns");
  {
    const flight = runtime.flight;
    const tables = runtime.evidence.detail.tables;
    const forwardX = runtime.view_sin;
    const forwardY = runtime.view_cos;
    const cameraHeight = (127 - (runtime.view_camera_altitude >> 1)) & 0xff;
    // DOS 0000D974/0000D97A load raw 10.22 camera registers. DTL
    // products remain in that scale through the SHLD map lookup.
    let centreX = runtime.view_camera_dos_x | 0;
    let centreY = runtime.view_camera_dos_y | 0;
    let sampleIndex = 0;
    for (let ring = 0; ring < 250; ring += 1) {
      const forwardStep = tables[1][ring] | 0;
      const lateralStep = tables[0][ring] | 0;
      centreX = (centreX + dosHi32(forwardStep, forwardX)) | 0;
      centreY = (centreY - dosHi32(forwardStep, forwardY)) | 0;
      const lateralX = dosHi32(lateralStep, forwardY);
      const lateralY = dosHi32(lateralStep, forwardX);
      let x = centreX;
      let y = centreY;
      for (let column = 95; column >= 0; column -= 1) {
        const actual = samples[sampleIndex++];
        assert.deepEqual(actual, { column, x, y, cameraHeight }, `DOS left terrain walk differs at ring ${ring}, column ${column}`);
        x = (x - lateralX) | 0;
        y = (y - lateralY) | 0;
      }
      x = (centreX + lateralX) | 0;
      y = (centreY + lateralY) | 0;
      for (let column = 96; column < 192; column += 1) {
        const actual = samples[sampleIndex++];
        assert.deepEqual(actual, { column, x, y, cameraHeight }, `DOS right terrain walk differs at ring ${ring}, column ${column}`);
        x = (x + lateralX) | 0;
        y = (y + lateralY) | 0;
      }
    }
  }

  // Exercise the real sample lookup separately from traversal. DOS
  // 0000D9EE/0000D9F2 pack the top ten bits of raw unsigned registers;
  // include cell boundaries and signed/wrapped coordinates. This catches
  // a marcher corrected to 10.22 with a sampler still reading 16.16.
  for (const [x, y] of [[0x003fffff, 0x00400000], [0x00400000, 0x003fffff],
    [-1, -2147483648], [0x7fffffff, 0]]) {
    let sampledIndex;
    const heights = new Proxy({}, { get(_target, key) { sampledIndex = Number(key); return 0; } });
    const horizon = new Int16Array(192).fill(213);
    runtime.drawTerrainSample(95, x, y, 0, 0, horizon, heights,
      runtime.colourMap, new Int16Array(192));
    const unsignedX = BigInt.asUintN(32, BigInt(x));
    const unsignedY = BigInt.asUintN(32, BigInt(y));
    const expectedIndex = Number((unsignedY / 4194304n) * 1024n + unsignedX / 4194304n);
    assert.equal(sampledIndex, expectedIndex, `DOS SHLD map address for ${x},${y}`);
  }

  // Exercise every recovered selector contract, including the two external
  // cameras and the DOS 0x09 fixed-camera re-selection quirk. This is a
  // runtime behavior check; complete DOS frame parity remains a separate gate.
  runtime.enterDemo(1);
  const defaultCamera = [runtime.view_camera_x, runtime.view_camera_y, runtime.view_camera_altitude];
  runtime.applyViewKey(0x03);
  assert.equal(runtime.view_variant, 2, "0x03 did not select DOS left view variant 2");
  assert.equal(runtime.view_slope, runtime.flight.pitch << 2, "left view slope transform differs");
  runtime.applyViewKey(0x04);
  assert.equal(runtime.view_variant, 3, "0x04 did not select DOS right view variant 3");
  runtime.applyViewKey(0x05);
  assert.equal(runtime.view_variant, 4, "0x05 did not select DOS rear view variant 4");
  runtime.applyViewKey(0x06);
  assert.equal(runtime.view_variant, 5, "0x06 did not select DOS level view variant 5");
  runtime.applyViewKey(0x07);
  assert.equal(runtime.view_variant, 6, "0x07 did not select DOS chase view variant 6");
  assert.equal(runtime.view_offset, 0, "chase view retains a non-zero pitch offset");
  check(runtime.view_camera_x !== defaultCamera[0] || runtime.view_camera_y !== defaultCamera[1],
    "chase view does not move the camera behind the helicopter");
  runtime.applyViewKey(0x08);
  assert.equal(runtime.view_variant, 7, "0x08 did not select DOS fixed-ground view variant 7");
  const fixedCamera = [runtime.view_camera_x, runtime.view_camera_y, runtime.view_camera_altitude];
  runtime.applyViewKey(0x09);
  assert.equal(runtime.view_variant, 7, "0x09 did not re-select DOS fixed-ground variant 7");
  assert.deepEqual([runtime.view_camera_x, runtime.view_camera_y, runtime.view_camera_altitude], fixedCamera,
    "0x09 incorrectly re-placed the fixed camera");
  runtime.applyViewKey(0x02);
  assert.equal(runtime.view_variant, 1, "0x02 did not restore DOS cockpit view variant 1");
  assert.equal(runtime.view_angle >>> 0, runtime.flight.angle >>> 0, "cockpit view did not restore flight angle");

  // The cockpit console is only the bezel. DOS 00007580 and 00007860 must
  // paint the two MFD bodies over it; checking their interior pixels catches
  // a regression where the surrounding CONS art renders but both screens stay
  // at the authored black clear value.
  runtime.enterDemo(1);
  runtime.advanceTicks(9); // DEMO1 record 7 selects the first target.
  const originalObjectPass = runtime.updateObjectPass;
  const originalObjectDraw = runtime.objectDraw;
  let objectDrawCalls = 0;
  let objectPixelChanges = 0;
  runtime.objectDraw = function (...args) {
    objectDrawCalls += 1;
    return originalObjectDraw.apply(this, args);
  };
  runtime.updateObjectPass = function (...args) {
    const before = this.frame.slice();
    const result = originalObjectPass.apply(this, args);
    for (let index = 0; index < before.length; index += 1) {
      if (before[index] !== this.frame[index]) objectPixelChanges += 1;
    }
    return result;
  };
  runtime.advanceTicks(30);
  runtime.updateObjectPass = originalObjectPass;
  runtime.objectDraw = originalObjectDraw;
  check(objectDrawCalls > 0 && objectPixelChanges > 0,
    "active object sprite pass did not change the framebuffer");
  const mfdHasInk = (left, top, width, height) => {
    for (let y = top; y < top + height; y += 1) {
      for (let x = left; x < left + width; x += 1) {
        if (runtime.frame[(y * 320) + x] !== 0) return true;
      }
    }
    return false;
  };
  check(mfdHasInk(76, 182, 64, 32), "left MFD map body remained black");
  check(mfdHasInk(180, 182, 64, 32), "right MFD target body remained black");

  runtime.frame.fill(0);
  runtime.drawSightLine(170, 70);
  const expectedSight = new Set();
  {
    const centerX = 0xa5;
    const centerY = 0x5a;
    const dx = Math.abs(170 - centerX);
    const dy = Math.abs(70 - centerY);
    let x = centerX;
    let y = centerY;
    const sx = 170 < centerX ? -1 : 1;
    const sy = 70 < centerY ? -1 : 1;
    if (dx >= dy) {
      const stepByte = ((Math.trunc((dy * 0x10000) / (dx + 1)) + 0x100) >>> 8) & 0xff;
      let fraction = 0x80;
      for (let step = 0; step <= dx; step += 1) {
        expectedSight.add(`${x},${y}`);
        x += sx;
        const sum = fraction + stepByte;
        fraction = sum & 0xff;
        if (sum > 0xff) y += sy;
      }
    } else {
      const stepByte = ((Math.trunc((dx * 0x10000) / (dy + 1)) + 0x100) >>> 8) & 0xff;
      let fraction = 0x80;
      for (let step = 0; step <= dy; step += 1) {
        expectedSight.add(`${x},${y}`);
        y += sy;
        const sum = fraction + stepByte;
        fraction = sum & 0xff;
        if (sum > 0xff) x += sx;
      }
    }
  }
  const actualSight = new Set();
  for (let y = 0; y < 240; y += 1) {
    for (let x = 0; x < 320; x += 1) {
      if (runtime.frame[(y * 320) + x] === 0x47e8) actualSight.add(`${x},${y}`);
    }
  }
  assert.deepEqual(actualSight, expectedSight, "DOS sight-line byte walk differs");

  runtime.installPassEvidence(evidence.passes[0]);
  const sky2Source = dominantIndex(evidence.passes[0].sky.payload.pixels);
  assert.equal(sky2Source, 167, "SKY2 dominant authored source index changed");
  assert.equal(runtime.skyLookup[sky2Source], 16, "SKY2 source index did not remap to the authored blue entry");
  assertRgb565Blue(runtime.skyPalette[sky2Source], "SKY2 dominant sky");

  runtime.installPassEvidence(evidence.passes[1]);
  assert.equal(runtime.skyLookup[1], 255, "SKY4 viewport fill is not the active entry 255");
  const nightWord = runtime.skyPalette[1];
  check(((nightWord >> 5) & 0x3f) > ((nightWord >> 11) & 0x1f), "SKY4 fill is not night-green");

  // A long render must keep the replay alive while the target presentation
  // applies the recovered phase displacement to its cropped surface.
  runtime.shake.countdown = 10;
  runtime.scheduler.onElapsed(1000);
  assert.equal(runtime.shake.countdown, 0);
  assert.equal(runtime.shakePresentationUnproven, true);
  runtime.present();

  // The first DEMO1 external-camera segment must return to the cockpit at
  // record 357. Keep the full replay live through the recovered shake target
  // presentation so the browser cannot regress to a frozen external frame.
  const longRuntime = sandbox.ComancheRuntime.create({ canvas: makeCanvas(), evidence });
  longRuntime.pass = 1;
  longRuntime.installPassEvidence(evidence.passes[1]);
  longRuntime.enterDemo(1);
  for (let index = 0; index <= 357; index += 1) longRuntime.advanceTicks(1);
  assert.equal(longRuntime.mode, "demo", "DEMO1 stopped before the cockpit returned");
  assert.equal(longRuntime.view_variant, 1, "DEMO1 did not return to the cockpit view");
  assert.doesNotThrow(() => longRuntime.present(), "DEMO1 presentation stopped at the first impact");
  longRuntime.destroy();

  // Optional retained DOS execution fixture (captured at 0000F317; see
  // docs/DOS-ORACLE.md). Compare the production marcher/sample routines,
  // not a second traversal model. Only the captured ring prefix is scored.
  const captureArg = process.argv.indexOf("--dos-marcher");
  if (captureArg >= 0) {
    const capturePath = path.resolve(process.argv[captureArg + 1]);
    const dump = JSON.parse(fs.readFileSync(capturePath, "utf8"));
    const state = dump.state;
    const readCapture = (key) => fs.readFileSync(path.join(path.dirname(capturePath), dump[key]));
    const silhouettes = readCapture("silhouettes_file");
    // Older retained captures carry the DOS DTL arrays without a pages file.
    // Reconstruct those pages with the independent projection oracle above.
    runtime.ringPageTable = dump.pages_file ? readCapture("pages_file")
      : dosProjectionTable({ tables: [null, null,
        dump.dtl_slopes_0x1A6B4, dump.dtl_biases_0x1AA9C] });
    runtime.evidence = { ...runtime.evidence,
      height: { pixels: readCapture("heightmap_file") },
      detail: { tables: [dump.dtl_lateral_0x19EE4, dump.dtl_forward_0x1A2CC] } };
    runtime.view_camera_dos_x = state.camera_x_0x19CD4 | 0;
    runtime.view_camera_dos_y = state.camera_y_0x19CD8 | 0;
    runtime.view_sin = state.sin_0x19CB0 | 0;
    runtime.view_cos = state.cos_0x19CB4 | 0;
    runtime.view_camera_altitude = state.altitude_0x19DFC;
    let scored = 0;
    const sample = runtime.drawTerrainSample;
    runtime.drawTerrainSample = function (...args) {
      const ring = args[4] / 256;
      if (ring >= state.ring_count_0x19EE0) return;
      sample.apply(this, args);
      if (args[0] !== 191) return;
      const reference = silhouettes.subarray(ring * 256 + 0x20, ring * 256 + 0xe0);
      // Retain the existing DOS comparison's non-uniform-ring criterion
      // and exclude columns 56..135 shared with the rear-view archive.
      if (new Set(reference).size < 4) return;
      for (let column = 0; column < 192; column += 1) {
        if (column >= 56 && column <= 135) continue;
        assert.equal(213 - args[5][column], reference[column],
          `captured DOS horizon ring ${ring}, column ${column}`);
        scored += 1;
      }
    };
    runtime.drawTerrain();
    runtime.drawTerrainSample = sample;
    check(scored > 0, "DOS capture had no non-uniform terrain rings to score");
    console.log(`PASS captured DOS terrain horizons: ${scored}/${scored}`);
  }

  // The player damage chain as the flight tick carries it
  // (analysis/functions/browser-attract.md#player-damage-chain). The pure
  // functions are proved in tools/prove-browser-menus.js; this checks that
  // flightTick enters them at the listing's points. DEMO1 is entered fresh and
  // flightTick is called directly, so no replay record or object pass runs.
  {
    const damageRuntime = sandbox.ComancheRuntime.create({ canvas: makeCanvas(), evidence });
    damageRuntime.pass = 1;
    damageRuntime.installPassEvidence(evidence.passes[1]);
    damageRuntime.enterDemo(1);
    const flight = damageRuntime.flight;

    // 00019424-000194D0: a ground crash restores the frame-start position,
    // bounces, arms ten ticks of shake and pays with two damage-cell steps
    // and (rng >>> 8) & 3 hull points, the RNG stirred by the restored x.
    flight.altitude = 0;
    flight.previousAltitude = 3;
    flight.axis1 = 0;
    flight.axis2 = 0;
    flight.fwd = 0x200000;
    flight.lat = 0x100000;
    damageRuntime.shake.rng = 0x01020304;
    const cellsBefore = Array.from(damageRuntime.hull.cells);
    const pointsBefore = damageRuntime.hull.points;
    damageRuntime.flightTick();
    assert.equal(flight.crashes, 1, "a ground hit at altitude 0 is not a crash");
    assert.equal(damageRuntime.shake.countdown, 10, "00019461 arms ten ticks of shake");
    const stirred = (0x01020304 + flight.frameDosX) >>> 0;
    assert.equal(damageRuntime.shake.rng, ((stirred >>> 8) | (stirred << 24)) >>> 0, "[00019DB8] is stirred by the restored x and rotated right by 8");
    const stepped = Array.from(damageRuntime.hull.cells).map((value, index) => (cellsBefore[index] - value) & 0xff);
    assert.equal(stepped.reduce((sum, value) => sum + value, 0), 2, "two damage-cell steps");
    assert.equal(stepped[stirred & 7] > 0 && stepped[(stirred & 0xff) >> 5] > 0, true, "the cells the low byte names");
    assert.equal(pointsBefore - damageRuntime.hull.points, (damageRuntime.shake.rng & 3), "hull points lost = byte 1 of the stirred RNG & 3");

    // 00018EE3-00018F93: a wreck with the hull gone. 100 ticks end the flight
    // (00018EF6 je 0002873D), the cockpit view's screen sinks 0x52 a tick and
    // the chase view takes over when it reaches 0xE6A, 45 ticks in; with
    // [00019DB8] & 0xF == 0 a wreck puff is made from slot 31 every tick.
    damageRuntime.enterDemo(1);
    damageRuntime.hull.down = 1;
    damageRuntime.hull.points = -1;
    damageRuntime.shake.rng = 0;
    const wreck = damageRuntime.flight;
    wreck.altitude = 0xc0;
    wreck.previousAltitude = 0xc0;
    const puffsBefore = damageRuntime.objects.filter((object) => object.stateAddr === 0x237b0).length;
    let chaseTick = 0;
    let endTick = 0;
    for (let tick = 1; tick <= 100 && !endTick; tick += 1) {
      wreck.axis1 = 55;
      wreck.axis2 = 66;
      damageRuntime.flightTick();
      assert.equal(damageRuntime.hull.timer, 100 - tick, `wreck countdown after tick ${tick}`);
      if (!chaseTick && damageRuntime.view_variant === 6) chaseTick = tick;
      if (wreck.missionEnd) endTick = tick;
    }
    assert.equal(chaseTick, 45, "the chase view starts when the screen has sunk 0xE6A");
    assert.equal(damageRuntime.crashDrop, 0, "the chase view's tail (000196CF -> 0001687D) zeroes the screen drop");
    assert.equal(endTick, 100, "the flight ends when the countdown reaches zero");
    assert.ok(damageRuntime.objects.filter((object) => object.stateAddr === 0x237b0).length > puffsBefore,
      "the wreck puffs from the fixed object");
    assert.equal(wreck.collective, 0, "the rotor has stopped");
    damageRuntime.destroy();
  }

  // Pilot, menu and damage modules (tools/prove-browser-menus.js): derived
  // fixtures from the hashed image, the shipped assets and the DOS captures.
  const menuProof = await proveMenus({ flat });
  for (const line of menuProof.report) console.log(`PASS ${line}`);
  for (const line of menuProof.dosResults) console.log(line);

  const audit = auditJavaScriptProvenance();
  console.log(`PASS source-audit ${audit.files} JavaScript files, `
    + `${audit.anchors} record anchors resolved, `
    + `${audit.tableRows} record table rows well-formed`);
  console.log("PASS DOS image SHA-256 and 640-entry Q31 table");
  console.log("PASS campaign-0 mission/resource families, DTA/SG palettes, DTL and DEMO boundaries");
  console.log("PASS pass-one attract transition, draw-before-replay ordering, SKY2 blue and SKY4 fill");
  console.log("PASS DOS attract active-object factory, projection, draw order and frame-driver ordering");
  console.log("PASS HIGH.DTL projection table and 250x192 DOS terrain traversal");
  console.log("PASS DOS sprite origin and sight-line byte-accumulator arithmetic");
  console.log("PASS shake timer and cropped target presentation continue after impact");
}

proveRuntime().catch((error) => {
  console.error(error.stack || error);
  process.exitCode = 1;
});
