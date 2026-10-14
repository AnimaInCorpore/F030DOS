#!/usr/bin/env node
/*
 * check-js-damage: run the JavaScript player damage and death chain against the
 * DOS captures of work/trace_player_damage.py (work/replay_dos/damage-*.json,
 * derived and git-ignored; regenerate with that script).
 *
 * N/A - target artefact: an oracle probe, no DOS routine.
 * record: analysis/functions/browser-attract.md#player-damage-chain
 *
 * What is compared.
 *   crash     every crash the original took (breakpoints 00019424, 0001947B and
 *             000194E0) is replayed through ComancheDamage.crashResponse with
 *             the RNG the damage tail really read ([00019DB8] at 0001947B, the
 *             one input the JavaScript cannot reproduce): the restored position
 *             and altitude, the bounce, the shake countdown, the two damage
 *             cells, the hull, the death cue and the stirred RNG are compared
 *             with the state at 000194E0. The stirred RNG is exact unless the
 *             timer ISR stepped it in between (counted separately).
 *   wreck, sinking, engine
 *             the browser runtime is flown over the same demo to the same
 *             replay cursor, the same poke is made, and every following tick is
 *             compared by records consumed with the state at 00019555: the
 *             death block's countdown, collective, stick, screen drop, view
 *             variant, the sinking altitude, the damaged engine's cap and the
 *             tail rotor's yaw. The chase view the death block selects runs the
 *             original's frame driver again inside the tick (the cursor jumps by
 *             two records and the countdown by two); the browser takes it as one
 *             tick, so rows from that tick on are compared on the countdown by
 *             record count only.
 *
 *   collide   the collision test 000192EE-0001934F: at each sample the original
 *             had the player set at an offset from one mission object (box edges
 *             in X and Y, altitude differences around 0x1F/0x20) and went to
 *             00019424 (a collision) or fell through to 00019352; ComancheDamage.
 *             objectCollision is run on the object table the original read and
 *             must give the same answer at every sample.
 *
 * Usage: node tools/check-js-damage.js [--dir work/replay_dos] [--scenario S]
 * Exits non-zero on any difference.
 */

"use strict";

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const ROOT = path.resolve(__dirname, "..");
const JS_ROOT = path.join(ROOT, "jsComanche");

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
    console, document, location: { href: "http://127.0.0.1:8765/F030Comanche/jsComanche/" },
    URL, TextDecoder, Uint8Array, Uint8ClampedArray, Uint16Array, Int16Array, Int32Array,
    ArrayBuffer, BigInt, Map, Set, Math, Number, Object, String, Error, TypeError,
    fetch: async (url) => {
      const pathname = new URL(url).pathname;
      const file = path.resolve(ROOT, pathname.replace(/^\/F030Comanche\//, ""));
      if (!file.startsWith(ROOT + path.sep)) throw new Error(`loader escaped workspace: ${file}`);
      if (!fs.existsSync(file)) return { ok: false, status: 404, arrayBuffer: async () => new ArrayBuffer(0) };
      const bytes = fs.readFileSync(file);
      return { ok: true, status: 200, arrayBuffer: async () => bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength) };
    },
    requestAnimationFrame() { return 1; },
    cancelAnimationFrame() {},
  };
  sandbox.window = sandbox;
  sandbox.globalThis = sandbox;
  return { sandbox, canvas };
}

function loadSources(context) {
  for (const name of ["dos-fs.js", "dos-data.js", "sine-q31.js", "object-bearing.js", "dos-text-data.js",
    "dos-pilot.js", "dos-menu.js", "dos-damage.js", "dos-runtime.js"]) {
    vm.runInContext(fs.readFileSync(path.join(JS_ROOT, name), "utf8"), context, { filename: name });
  }
}

function cellKey(index) {
  return `cell${index}_19E${(0x38 + index).toString(16).toUpperCase()}`;
}

function cellsFrom(row) {
  return Array.from({ length: 8 }, (_, index) => row[cellKey(index)]);
}

function checkCrashes(damage, capture, failures) {
  let crashes = 0;
  let stirred = 0;
  let isr = 0;
  const events = capture.events;
  for (let index = 0; index + 2 < events.length; index += 1) {
    const [crash, tail, core] = [events[index], events[index + 1], events[index + 2]];
    if (crash.kind !== "crash" || tail.kind !== "tail" || core.kind !== "core") continue;
    crashes += 1;
    const state = {
      cells: Uint8Array.from(cellsFrom(crash)),
      hullPoints: crash.hull_19E40,
      deathCue: crash.cue_19E49,
      x: crash.x_19CD4,
      y: crash.y_19CD8,
      frameX: crash.frame_x_19CDC,
      frameY: crash.frame_y_19CE0,
      altitude: crash.alt_19DFC,
      previousAltitude: crash.prevalt_19DF6,
      fwd: crash.fwd_19CC8,
      lat: crash.lat_19CD0,
      shakeCountdown: crash.countdown_19DC0,
      rng: tail.rng_19DB8,
    };
    const result = damage.crashResponse(state);
    const label = `crash at cursor ${crash.cursor_19ECC}`;
    const expect = (name, actual, wanted) => {
      if ((actual | 0) !== (wanted | 0)) failures.push(`${label}: ${name} js ${actual} dos ${wanted}`);
    };
    expect("x", state.x, core.x_19CD4);
    expect("y", state.y, core.y_19CD8);
    expect("altitude", state.altitude, core.alt_19DFC);
    expect("fwd", state.fwd, core.fwd_19CC8);
    expect("lat", state.lat, core.lat_19CD0);
    expect("hull", state.hullPoints, core.hull_19E40);
    expect("death cue", state.deathCue, core.cue_19E49);
    const wanted = cellsFrom(core);
    for (let cell = 0; cell < 8; cell += 1) expect(`cell ${cell}`, state.cells[cell], wanted[cell]);
    // the countdown is armed to 10 and the timer ISR may already have stepped it
    if (state.shakeCountdown !== 10 || core.countdown_19DC0 > 10) failures.push(`${label}: shake countdown js ${state.shakeCountdown} dos ${core.countdown_19DC0}`);
    if ((state.rng >>> 0) === (core.rng_19DB8 >>> 0)) stirred += 1;
    else isr += 1;
    if (!result.sounds.length) failures.push(`${label}: no sound request`);
  }
  return { crashes, stirred, isr };
}

function checkCollisions(damage, capture, failures) {
  let agree = 0;
  for (const sample of capture.samples) {
    const objects = new Array(31).fill(null);
    for (const entry of sample.objects) {
      if (entry.slot >= 1) objects[entry.slot] = entry;
    }
    const hit = damage.objectCollision(
      { altitude: sample.player.altitude, x: sample.player.x, y: sample.player.y }, objects) !== 0;
    const label = `sample cursor ${sample.cursor} slot ${sample.slot} dx ${sample.dx} dy ${sample.dy} da ${sample.da}`;
    if (hit !== (sample.outcome === "collision")) failures.push(`${label}: js ${hit ? "collision" : "none"} dos ${sample.outcome}`);
    else agree += 1;
  }
  return { samples: capture.samples.length, agree };
}

async function checkFlown(env, capture, name, failures) {
  const demo = capture.demo_digit;
  const runtime = env.sandbox.ComancheRuntime.create({ canvas: makeCanvas(), evidence: env.evidence });
  runtime.pass = demo;
  runtime.installPassEvidence(env.evidence.passes[demo]);
  runtime.enterDemo(demo);
  const byRecords = new Map();
  for (const row of capture.events) {
    if (row.kind === "tick") byRecords.set((row.cursor_19ECC - 13) / 8, row);
  }
  const pokeRecords = (capture.poked_at_cursor - 13) / 8;
  const last = Math.max(...byRecords.keys());
  let compared = 0;
  let chased = false;
  let endRecord = null;
  const endRow = capture.events.find((row) => row.kind === "end");
  if (endRow) endRecord = (endRow.cursor_19ECC - 13) / 8;
  for (let record = 1; record <= last + 2; record += 1) {
    const row = byRecords.get(record);
    if (capture.scenario === "crash") {
      const tail = capture.events.find((event) => event.kind === "tail" && (event.cursor_19ECC - 13) / 8 === record);
      if (tail) runtime.shake.rng = tail.rng_19DB8 >>> 0;
    }
    runtime.advanceTicks(1);
    if (record === pokeRecords) {
      if (capture.scenario === "wreck" || capture.scenario === "sinking") {
        runtime.hull.down = 1;
        runtime.hull.timer = 0x64;
        if (capture.scenario === "wreck") runtime.hull.points = -1;
      } else if (capture.scenario === "engine") {
        runtime.hull.cells[0] = 0xff;
        runtime.hull.cells[1] = 0xff;
      }
    }
    const forceAltitude = capture.scenario === "crash" && record >= pokeRecords && record < pokeRecords + 41;
    if (!row || record <= pokeRecords) {
      if (forceAltitude) runtime.flight.altitude = 0;
      continue;
    }
    const variant = runtime.view_variant;
    const expect = (field, actual, wanted) => {
      if ((actual | 0) !== (wanted | 0)) failures.push(`${name}: record ${record} ${field} js ${actual} dos ${wanted}`);
    };
    const afterChase = capture.scenario === "wreck" && row.variant_19D86 === 6 || chased;
    if (afterChase) chased = true;
    expect("death timer", runtime.hull.timer, row.timer_19E48);
    expect("death cue", runtime.hull.down, row.cue_19E49);
    expect("view variant", variant, row.variant_19D86);
    if (!chased) {
      expect("collective", runtime.flight.collective, row.collective_19D82);
      expect("screen drop", runtime.crashDrop, row.drop_19DC4);
      expect("stick 1", runtime.flight.axis1, row.axis1_19DC8);
      expect("stick 2", runtime.flight.axis2, row.axis2_19DCC);
      expect("altitude", runtime.flight.altitude, row.alt_19DFC);
      expect("x", runtime.flight.dosX, row.x_19CD4);
      expect("y", runtime.flight.dosY, row.y_19CD8);
      expect("forward speed ceiling", runtime.flight.maxSpeed, row.maxspd_19CCC);
      expect("torque gauge", runtime.flight.torque, row.torque_19D84);
      expect("turn", runtime.flight.turn, row.turn_19D08);
      expect("angle", runtime.flight.angle, row.angle_19D04);
    } else {
      expect("screen drop", runtime.crashDrop, row.drop_19DC4);
    }
    compared += 1;
    // the crash scenario forces the altitude to 0 after the state is read, as
    // the probe does at 00019555
    if (forceAltitude) runtime.flight.altitude = 0;
  }
  let ended = null;
  if (endRecord !== null) {
    ended = runtime.flight.missionEnd === 1 || runtime.hull.timer === 0;
    if (!ended) failures.push(`${name}: the flight did not end where DOS did (record ${endRecord})`);
  }
  runtime.destroy();
  return { compared, ended };
}

// DOS: N/A - target artefact: runs the browser reference over the captures.
// Returns one { scenario, status, text } per scenario: "PASS", "FAIL" or "SKIP"
// (capture absent).
async function checkDamage(options = {}) {
  const dir = path.resolve(ROOT, options.dir || "work/replay_dos");
  const only = options.scenario || null;
  const { sandbox } = makeContext();
  const context = vm.createContext(sandbox);
  loadSources(context);
  const env = { sandbox, evidence: await sandbox.ComancheDOS.loadAttractEvidence() };
  const damage = sandbox.ComancheDamage;
  const results = [];
  for (const scenario of ["crash", "wreck", "sinking", "engine", "collide"]) {
    if (only && only !== scenario) continue;
    const file = path.join(dir, `damage-${scenario}.json`);
    if (!fs.existsSync(file)) { results.push({ scenario, status: "SKIP", text: `${scenario} (capture absent)` }); continue; }
    const capture = JSON.parse(fs.readFileSync(file, "utf8"));
    const failures = [];
    if (scenario === "collide") {
      const collisions = checkCollisions(damage, capture, failures);
      results.push(failures.length
        ? { scenario, status: "FAIL", text: `collide: ${failures.length} differences, first ${failures.slice(0, 6).join("; ")}` }
        : { scenario, status: "PASS", text: `collide: ${collisions.agree} of ${collisions.samples} box and altitude samples agree` });
      continue;
    }
    const summary = scenario === "crash" ? checkCrashes(damage, capture, failures) : null;
    const flown = await checkFlown(env, capture, scenario, failures);
    if (failures.length) {
      results.push({ scenario, status: "FAIL", text: `${scenario}: ${failures.length} differences, first ${failures.slice(0, 6).join("; ")}` });
    } else {
      const crashes = summary ? `, ${summary.crashes} crashes (${summary.stirred} with the exact stirred RNG, ${summary.isr} stepped by the timer ISR)` : "";
      results.push({ scenario, status: "PASS", text: `${scenario}: ${flown.compared} ticks compared${crashes}` });
    }
  }
  return results;
}

module.exports = { checkDamage };

if (require.main === module) {
  const args = process.argv.slice(2);
  const value = (flag, fallback) => (args.indexOf(flag) >= 0 ? args[args.indexOf(flag) + 1] : fallback);
  checkDamage({ dir: value("--dir", "work/replay_dos"), scenario: value("--scenario", null)}).then((results) => {
    for (const result of results) console.log(`${result.status} ${result.text}`);
    process.exitCode = results.some((result) => result.status === "FAIL") ? 1 : 0;
  }).catch((error) => { console.error(error.stack || error); process.exitCode = 1; });
}
