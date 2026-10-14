#!/usr/bin/env node
/*
 * Exercise the connected attract runtime as one sequence.
 *
 * This is a coverage witness, not a DOS parity oracle: it follows all four
 * connected attract passes and records the remaining target presentation
 * adaptation separately from DOS frame parity.
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

function increment(map, key) {
  map[key] = (map[key] || 0) + 1;
}

async function main() {
  const output = path.resolve(ROOT, process.argv[2] || "build/acceptance/sequence/browser-sequence.json");
  const { sandbox, canvas } = makeContext();
  const context = vm.createContext(sandbox);
  loadSources(context);
  const evidence = await sandbox.ComancheDOS.loadAttractEvidence();
  const runtime = sandbox.ComancheRuntime.create({ canvas, evidence });
  const surface = runtime.terrainSurface;
  const expectedPasses = [1, 2, 3, 0];
  const observedPasses = [];
  const events = [];
  const frameHashes = [];
  const cameraKeys = {};
  const commandKeys = {};
  const replayKeys = {};
  const viewVariantChanges = [];
  let lastViewVariant = null;
  let errors = [];
  let supportedBoundary = null;

  function collectTrace() {
    const trace = runtime.lastTrace;
    if (!trace) return;
    for (const event of trace.events || []) events.push(event);
    if (trace.framebufferHash) frameHashes.push(trace.framebufferHash);
    const variant = trace.state?.view?.variant;
    if (variant !== undefined && variant !== lastViewVariant) {
      viewVariantChanges.push({ tick: trace.tick, variant });
      lastViewVariant = variant;
    }
  }

  try {
    for (let cycle = 0; cycle < expectedPasses.length; cycle += 1) {
      let guard = 0;
      while (runtime.mode !== "demo" && guard < 2000) {
        runtime.advanceTicks(1);
        collectTrace();
        guard += 1;
      }
      if (runtime.mode !== "demo") throw new Error(`cycle ${cycle}: demo was not reached`);
      const pass = runtime.pass;
      const demoIndex = runtime.demoIndex;
      const traced = runtime.demo.records.length;
      observedPasses.push({ cycle, pass, demoIndex, records: runtime.demo.records.length, traced });
      for (const record of runtime.demo.records) {
        const key = record.key & 0xff;
        increment(replayKeys, `0x${key.toString(16).padStart(2, "0")}`);
        if (key >= 0x02 && key <= 0x09) increment(cameraKeys, `0x${key.toString(16).padStart(2, "0")}`);
        if (key === 0x1a || key === 0x1b || key === 0x27 || key === 0x28) increment(commandKeys, `0x${key.toString(16).padStart(2, "0")}`);
      }
      for (let index = 0; index < traced; index += 1) {
        runtime.advanceTicks(1);
        collectTrace();
        if (runtime.terrainSurface !== surface) throw new Error(`cycle ${cycle}: terrain buffer identity changed`);
      }
      // The next frame consumes the exhausted replay and performs the actual
      // attract transition into the next opening screen.
      runtime.advanceTicks(1);
      collectTrace();
    }
  } catch (error) {
    errors.push(error.stack || error.message || String(error));
  }

  const expectedDemoIndexes = [1, 2, 3, 0];
  const transitionEvents = events.filter((event) => event.startsWith("demo-enter:") || event.startsWith("attract-pass:"));
  const cameraSupported = Object.keys(cameraKeys).length === 0 || ("view_variant" in runtime);
  runtime.destroy();
  const result = {
    schema: "f030-browser-sequence-v1",
    implementation: "javascript",
    scope: "browser-only",
    dos_image_sha256: sha256(fs.readFileSync(DOS_IMAGE)),
    expected_passes: expectedPasses,
    observed_passes: observedPasses,
    expected_demo_indexes: expectedDemoIndexes,
    transition_events: transitionEvents,
    replay_key_counts: replayKeys,
    command_key_counts: commandKeys,
    external_camera_key_counts: cameraKeys,
    external_camera_support: cameraSupported ? "PASS" : "Unproven",
    view_variant_changes: viewVariantChanges,
    buffer_reuse: {
      terrain_surface_identity_stable: runtime.terrainSurface === surface,
      frame_hashes_observed: frameHashes.length,
      scheduler_stopped_after_destroy: runtime.scheduler.running === false,
    },
    supported_boundary: supportedBoundary,
    errors,
    status: errors.length === 0
      && JSON.stringify(observedPasses.map((row) => row.pass)) === JSON.stringify(expectedPasses)
      && JSON.stringify(observedPasses.map((row) => row.demoIndex)) === JSON.stringify(expectedDemoIndexes)
      && cameraSupported
      && runtime.terrainSurface === surface
      && runtime.scheduler.running === false
      ? "PASS" : "Unproven",
  };
  fs.mkdirSync(path.dirname(output), { recursive: true });
  fs.writeFileSync(output, `${JSON.stringify(result, null, 2)}\n`);
  console.log(`${result.status}: browser sequence ${observedPasses.map((row) => `pass${row.pass}/DEMO${row.demoIndex}`).join(" -> ")} -> ${output}`);
  if (!cameraSupported) console.log("  Unproven: DEMO streams contain external-camera selectors but the browser runtime exposes no view_variant seam");
  if (errors.length) console.log(`  errors: ${errors.join("; ")}`);
  if (supportedBoundary) console.log(`  supported boundary: pass ${supportedBoundary.pass} record ${supportedBoundary.record}; ${supportedBoundary.reason}`);
  process.exitCode = result.status === "PASS" ? 0 : 1;
}

main().catch((error) => {
  console.error(error.stack || error.message || error);
  process.exitCode = 1;
});
