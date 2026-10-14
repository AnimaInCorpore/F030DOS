#!/usr/bin/env node
/*
 * Emit the browser implementation's authoritative replay boundaries.
 *
 * This is intentionally a VM harness, not a second game implementation. The
 * runtime still imports the shipped DOS assets and DEMO*.SCR records. The
 * output is joined to DOS and Falcon traces by the DOS file cursor.
 */

"use strict";

const crypto = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const ROOT = path.resolve(__dirname, "..");
const JS_ROOT = path.join(ROOT, "jsComanche");
const DOS_IMAGE = path.join(ROOT, "assets", "extracted", "comanche_hdd", "UNPACKED.EXE");

function sha256(bytes) {
  return crypto.createHash("sha256").update(bytes).digest("hex");
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
  return { width, height, getContext() { return context; } };
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
      if (!file.startsWith(ROOT + path.sep)) throw new Error(`loader escaped workspace: ${file}`);
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
    vm.runInContext(fs.readFileSync(path.join(JS_ROOT, name), "utf8"), context, { filename: name });
  }
}

function state(row, liveFlight = null) {
  const flight = row?.flight;
  const view = row?.view;
  const live = liveFlight || {};
  return {
    pass: row?.pass ?? null,
    mode: row?.mode ?? null,
    screen: row?.screen ?? null,
    demoIndex: row?.demoIndex ?? null,
    demoCursor: row?.demoCursor === undefined ? null : 13 + (row.demoCursor * 8),
    flight: flight ? {
      x_0x19CD4: flight.dosX,
      y_0x19CD8: flight.dosY,
      angle_0x19D04: flight.angle >>> 0,
      alt_0x19DFC: flight.altitude,
      turn_0x19D08: live.turn,
      fwd_0x19CC8: live.fwd,
      lat_0x19CD0: live.lat,
      roll_0x19CF0: live.roll,
      pitch_0x19CF4: live.pitch,
    } : null,
    view: view ? {
      variant_0x19D86: view.variant,
      angle_0x19D00: view.angle >>> 0,
      slope_0x19CF8: view.slope,
      offset_0x19CFC: view.offset,
      camera_x_0x19CD4: view.cameraX,
      camera_y_0x19CD8: view.cameraY,
      camera_dos_x: view.cameraDosX,
      camera_dos_y: view.cameraDosY,
      camera_alt_0x19DF8: view.cameraAltitude,
      fixed_target_dos_x: view.fixedTargetDosX,
      fixed_target_dos_y: view.fixedTargetDosY,
    } : null,
  };
}

async function main() {
  const args = process.argv.slice(2);
  const value = (name, fallback) => {
    const index = args.indexOf(name);
    return index >= 0 ? args[index + 1] : fallback;
  };
  const pass = Number(value("--pass", "1"));
  // 284 records is the supported DEMO1 boundary: record index 284 (the 285th)
  // is the no-damage bounce, DOS 00019461, that arms the screen shake. Its
  // display consumers are not recovered, so this cross-machine parity trace
  // stops the armed presentation there; the browser-only target witness uses
  // the documented crop adaptation (analysis/functions/browser-attract.md#shake-timer).
  const records = Number(value("--records", "284"));
  const output = path.resolve(ROOT, value("--out", "build/acceptance/three-way/browser-demo1.json"));
  if (!Number.isInteger(pass) || pass < 0 || pass > 3) throw new Error("--pass must be 0..3");
  if (!Number.isInteger(records) || records < 1) throw new Error("--records must be positive");

  const { sandbox, canvas } = makeContext();
  const context = vm.createContext(sandbox);
  loadSources(context);
  const evidence = await sandbox.ComancheDOS.loadAttractEvidence();
  const runtime = sandbox.ComancheRuntime.create({ canvas, evidence });
  runtime.pass = pass;
  runtime.installPassEvidence(evidence.passes[pass]);
  runtime.enterDemo(pass);

  const rows = [];
  for (let index = 0; index < records; index += 1) {
    runtime.advanceTicks(1);
    const trace = runtime.lastTrace;
    const before = state(trace.rendered);
    const after = state(trace.state, runtime.flight);
    const input = trace.input || [];
    const functionIds = ["FUN_0000D3C0", "FUN_00018C29/FUN_00019A2D", "FUN_00018F94"];
    if (input[0] >= 0x02 && input[0] <= 0x09) {
      functionIds.push("FUN_0001959F", "FUN_00007D25");
    }
    rows.push({
      tick: index,
      function_ids: functionIds,
      input,
      pre: before,
      post: after,
      output: {
        framebuffer_fnv1a_rgb565: trace.framebufferHash,
        demo_cursor_after: after.demoCursor,
      },
    });
  }

  const image = fs.readFileSync(DOS_IMAGE);
  const result = {
    implementation: "javascript",
    dos_image_sha256: sha256(image),
    pass,
    demo_stream: `DEMO${pass}.SCR`,
    records,
    coordinate_contract: "DOS 10.22 raw boundary; browser 16.16 render coordinates",
    rows,
  };
  fs.mkdirSync(path.dirname(output), { recursive: true });
  fs.writeFileSync(output, `${JSON.stringify(result, null, 2)}\n`);
  console.log(`wrote ${rows.length} browser boundary rows -> ${output}`);
}

main().catch((error) => {
  console.error(error.stack || error.message || error);
  process.exitCode = 1;
});
