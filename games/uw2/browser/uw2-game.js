/*
 * UW2 canvas display adapter.
 *
 * The decoded cutscene frames form a deterministic presentation timeline.
 * requestAnimationFrame only selects which already-decoded frame to show; it
 * is not the DOS simulation clock and does not advance authoritative state.
 */
(function (global) {
  "use strict";

  var cutscene = global.UW2Cutscene;
  var reference = global.UW2Reference;
  var input = global.UW2Input;
  var canvas = document.getElementById("game-canvas");
  var SEGMENT_FILES = [
    "D4\\CUTS\\CS000.N01",
    "D4\\CUTS\\CS000.N12",
    "D4\\CUTS\\CS000.N02"
  ];
  var state = {
    phases: [],
    timeline: [],
    timelineMs: 0,
    loaded: false
  };
  var presentation = {
    startedAt: null,
    lastIndex: -1
  };

  /* Target artefact: a fixed presentation duration, not DOS timing. */
  function makePhase(frames, paletteBgra, frameMs) {
    return { frames: frames, paletteBgra: paletteBgra, frameMs: frameMs };
  }

  /* Target artefact: flatten the decoded frames into a replayable view. */
  function buildPresentationTimeline(phases) {
    var timeline = [];
    var elapsed = 0;
    phases.forEach(function (phase) {
      phase.frames.forEach(function (frame) {
        timeline.push({
          start: elapsed,
          end: elapsed + phase.frameMs,
          frame: frame,
          paletteBgra: phase.paletteBgra
        });
        elapsed += phase.frameMs;
      });
    });
    return { entries: timeline, durationMs: elapsed };
  }

  /* Target artefact: present one indexed frame through the Canvas adapter. */
  function renderTimelineItem(item) {
    cutscene.drawFrame(canvas, item.frame, item.paletteBgra);
  }

  /* Target artefact: wall-clock selection for presentation only. */
  function present(now) {
    if (!state.loaded || !state.timelineMs) {
      global.requestAnimationFrame(present);
      return;
    }
    if (presentation.startedAt === null) {
      presentation.startedAt = now;
    }
    var elapsed = (now - presentation.startedAt) % state.timelineMs;
    var index = 0;
    while (index + 1 < state.timeline.length && elapsed >= state.timeline[index].end) {
      index += 1;
    }
    if (index !== presentation.lastIndex) {
      presentation.lastIndex = index;
      renderTimelineItem(state.timeline[index]);
    }
    global.requestAnimationFrame(present);
  }

  /* N/A - browser transport adapter; no event changes game state. */
  function handleKeyboardEvent(event) {
    input.driver.queueKeyboardEvent(event);
  }

  async function load() {
    var phases = await Promise.all(SEGMENT_FILES.map(async function (name, index) {
      var bytes = await reference.readDosFile(name);
      var decoded = cutscene.decodeFrames(bytes);
      return makePhase(decoded.frames, decoded.paletteBgra, index ? 180 : 240);
    }));
    var backgroundBytes = await reference.readDosFile("D3\\CUTS\\LBACK000.BYT");
    var background = cutscene.readLback(backgroundBytes);
    phases.push(makePhase([background], phases[phases.length - 1].paletteBgra, 2200));
    var timeline = buildPresentationTimeline(phases);
    state.phases = phases;
    state.timeline = timeline.entries;
    state.timelineMs = timeline.durationMs;
    state.loaded = true;
    renderTimelineItem(state.timeline[0]);
    global.requestAnimationFrame(present);
  }

  canvas.addEventListener("keydown", handleKeyboardEvent);
  load();
}(window));
