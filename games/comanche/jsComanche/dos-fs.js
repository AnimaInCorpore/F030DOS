/*
 * In-memory DOS file boundary for the browser reference.
 *
 * The connected page imports the installed DOS files for one run. It does
 * not create a second source of truth in a persistent browser store or retain
 * user metadata between runs.
 */
// Target artefact; record: analysis/functions/browser-attract.md#dos-file-boundary
(() => {
  "use strict";

  // Target artefact; record: analysis/functions/browser-attract.md#dos-file-boundary
  function normalizeDosPath(path) {
    let value = String(path || "").replace(/\//g, "\\").trim();
    const drive = value.match(/^([A-Za-z]):/);
    const drivePrefix = drive ? `${drive[1].toUpperCase()}:\\` : "";
    value = value.replace(/^[A-Za-z]:/, "").replace(/^\\+/, "");
    const parts = [];
    for (const part of value.split("\\")) {
      if (!part || part === ".") continue;
      if (part === "..") {
        if (parts.length) parts.pop();
        continue;
      }
      parts.push(part.toUpperCase());
    }
    if (!parts.length) throw new Error("DOS file path is empty");
    return `${drivePrefix}${parts.join("\\")}`;
  }

  // Target artefact; record: analysis/functions/browser-attract.md#dos-file-boundary
  function asBytes(value) {
    const tag = Object.prototype.toString.call(value);
    if (value instanceof Uint8Array || tag === "[object Uint8Array]") return Uint8Array.from(value);
    if (value instanceof ArrayBuffer || tag === "[object ArrayBuffer]") return new Uint8Array(value.slice(0));
    throw new TypeError("DOS file content must be an ArrayBuffer or Uint8Array");
  }

  // Target artefact; record: analysis/functions/browser-attract.md#dos-file-boundary
  class DosFileSystem {
    // Target artefact; record: analysis/functions/browser-attract.md#dos-file-boundary
    constructor() {
      this.files = new Map();
      this.handles = new Map();
      this.nextHandle = 5;
    }

    // Target artefact; record: analysis/functions/browser-attract.md#dos-file-boundary
    async importBytes(path, content) {
      const canonical = normalizeDosPath(path);
      const bytes = asBytes(content);
      this.files.set(canonical, bytes.slice());
      return bytes.slice();
    }

    // Target artefact; record: analysis/functions/browser-attract.md#dos-file-boundary
    async readAll(path, loader = null) {
      const canonical = normalizeDosPath(path);
      const cached = this.files.get(canonical);
      if (cached) return cached.slice();
      if (!loader) throw new Error(`${canonical}: DOS file is not installed`);
      return this.importBytes(canonical, await loader(canonical));
    }

    // Target artefact; record: analysis/functions/browser-attract.md#dos-file-boundary
    async open(path, loader = null) {
      const canonical = normalizeDosPath(path);
      const bytes = await this.readAll(canonical, loader);
      const handle = this.nextHandle++;
      this.handles.set(handle, { bytes, position: 0, path: canonical });
      return handle;
    }

    // Target artefact; record: analysis/functions/browser-attract.md#dos-file-boundary
    read(handle, count = null) {
      const file = this.handles.get(handle);
      if (!file) throw new Error(`invalid DOS file handle ${handle}`);
      const requested = count === null ? file.bytes.length - file.position : Math.max(0, Math.trunc(count));
      const end = Math.min(file.bytes.length, file.position + requested);
      const result = file.bytes.slice(file.position, end);
      file.position = end;
      return result;
    }

    // Target artefact; record: analysis/functions/browser-attract.md#dos-file-boundary
    seek(handle, offset, whence = 0) {
      const file = this.handles.get(handle);
      if (!file) throw new Error(`invalid DOS file handle ${handle}`);
      const base = whence === 0 ? 0 : whence === 1 ? file.position : file.bytes.length;
      file.position = base + Math.trunc(offset);
      return file.position;
    }

    // Target artefact; record: analysis/functions/browser-attract.md#dos-file-boundary
    tell(handle) {
      const file = this.handles.get(handle);
      if (!file) throw new Error(`invalid DOS file handle ${handle}`);
      return file.position;
    }

    // Target artefact; record: analysis/functions/browser-attract.md#dos-file-boundary
    close(handle) {
      if (!this.handles.delete(handle)) throw new Error(`invalid DOS file handle ${handle}`);
    }

    // Target artefact; record: analysis/functions/browser-attract.md#dos-file-boundary
    clear() {
      this.files.clear();
      this.handles.clear();
    }
  }

  window.ComancheDosFS = {
    DosFileSystem,
    normalizeDosPath,
    // Target artefact; record: analysis/functions/browser-attract.md#dos-file-boundary
    create() {
      return new DosFileSystem();
    },
  };
})();
