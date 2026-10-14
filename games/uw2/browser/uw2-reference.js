/*
 * UW2 DOS source loader.
 *
 * Only the files consumed by the recovered intro path are mapped here. The
 * loader feeds those bytes into the small virtual DOS file boundary.
 */
(function (global) {
  "use strict";

  var query = new URLSearchParams(global.location.search);
  /* Target artefact; record: analysis/functions/file-boundary.md. */
  var FILE_SYSTEM = global.UW2DosFS.create({
    mode: query.get("fs") === "memory" ? "memory" : "persistent",
    databaseName: "f030-uw2-dos-files-v2",
    namespace: "f030-uw2",
    profile: "default",
    variant: "canvas-cutscene-cs000-v1"
  });
  var SOURCE_RESOURCES = {
    "d3/cuts/lback000.byt": "../work/extracted/D3/CUTS/LBACK000.BYT",
    "d4/cuts/cs000.n01": "../work/extracted/D4/CUTS/CS000.N01",
    "d4/cuts/cs000.n02": "../work/extracted/D4/CUTS/CS000.N02",
    "d4/cuts/cs000.n12": "../work/extracted/D4/CUTS/CS000.N12"
  };

  function copyBytes(value) {
    var source = value instanceof Uint8Array ? value : new Uint8Array(value);
    return new Uint8Array(source);
  }

  function sourceResource(path) {
    var relative = path.replace(/^\\+/, "").replace(/\\/g, "/").toLowerCase();
    return SOURCE_RESOURCES[relative];
  }

  /* N/A - host import adapter; record: analysis/functions/file-boundary.md. */
  async function hostLoader(path) {
    var response = await fetch(sourceResource(path), { cache: "no-cache" });
    return new Uint8Array(await response.arrayBuffer());
  }

  /* Target artefact; record: analysis/functions/file-boundary.md. */
  async function readDosFile(name) {
    var handle = await FILE_SYSTEM.open(name, hostLoader);
    try {
      var start = FILE_SYSTEM.tell(handle);
      var end = FILE_SYSTEM.seek(handle, 0, 2);
      FILE_SYSTEM.seek(handle, start, 0);
      var result = await FILE_SYSTEM.read(handle, end - start);
      return copyBytes(result.data);
    } finally {
      FILE_SYSTEM.close(handle);
    }
  }

  global.UW2Reference = {
    readDosFile: readDosFile,
    sourceResource: sourceResource
  };
}(window));
