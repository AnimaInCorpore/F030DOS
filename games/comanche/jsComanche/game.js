/* Connected browser entry for the DOS attract slice. */
// Target artefact; record: analysis/functions/browser-attract.md#browser-host
(() => {
  "use strict";

  const canvas = document.getElementById("game-canvas");

  // Target artefact; record: analysis/functions/browser-attract.md#browser-host
  async function load() {
    try {
      // DOS: FUN_00028F05/0002A1AD [00028F05-0002A299]; record: analysis/functions/browser-attract.md#mission-selection
      const evidence = await ComancheDOS.loadAttractEvidence();
      const runtime = ComancheRuntime.create({ canvas, evidence });
      runtime.start();
    } catch (error) {
      // Target artefact; record: analysis/functions/browser-attract.md#dos-file-boundary
      // Import failure stops the host boundary; it does not synthesize a game
      // state or route around an unavailable DOS resource.
      console.error(error);
    }
  }

  load();
})();
