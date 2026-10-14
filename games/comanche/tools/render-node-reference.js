#!/usr/bin/env node
/*
 * The former Node renderer was not a ground-truth implementation. It used a
 * pinned camera, guessed RGB565 colours, synthetic clouds, and a different
 * terrain walk. The CPU 68030 renderer is the reference; this command remains
 * only to make stale invocations fail loudly instead of producing evidence
 * from invented data.
 */
console.error(
  "render-node-reference.js is obsolete: capture the Falcon CPU path and " +
  "compare it with tools/compare-terrain.py."
);
process.exit(2);
