/*
 * UW2 DOS file boundary.
 *
 * The semantic side sees only normalized named byte files and the recovered
 * DOS operations open/read/seek/tell/close. The host adapter may run this in
 * memory-only mode for tests or in versioned persistent mode for the browser;
 * neither mode changes the bytes exposed to the semantic side.
 */
(function (global) {
  "use strict";

  var DB_VERSION = 1;
  var STORE_NAME = "files";
  var TAG = Object.prototype.toString;

  function normalizeDosPath(input) {
    var raw = String(input == null ? "" : input)
      .replace(/\//g, "\\")
      .trim();
    var driveMatch = /^([A-Za-z]:)(?:\\+)?(.*)$/.exec(raw);
    var drive = driveMatch ? driveMatch[1].toUpperCase() : "";
    var body = driveMatch ? driveMatch[2] : raw.replace(/^\\+/, "");
    var parts = [];
    body.split("\\").forEach(function (part) {
      if (!part || part === ".") {
        return;
      }
      if (part === "..") {
        if (parts.length && parts[parts.length - 1] !== "..") {
          parts.pop();
        }
        return;
      }
      parts.push(part.toUpperCase());
    });
    return (drive ? drive + "\\" : "\\") + parts.join("\\");
  }

  function asBytes(value) {
    if (TAG.call(value) === "[object Uint8Array]") {
      return new Uint8Array(value.buffer, value.byteOffset, value.byteLength);
    }
    if (TAG.call(value) === "[object ArrayBuffer]") {
      return new Uint8Array(value);
    }
    if (TAG.call(value) === "[object DataView]") {
      return new Uint8Array(value.buffer, value.byteOffset, value.byteLength);
    }
    return new Uint8Array(value);
  }

  function copyBytes(value) {
    var source = asBytes(value);
    var copy = new Uint8Array(source.byteLength);
    copy.set(source);
    return copy;
  }

  function storageKey(namespace, profile, suffix) {
    return namespace + ":" + profile + ":" + suffix;
  }

  function profileId(profile) {
    var text = String(profile || "default");
    var hash = 2166136261;
    for (var index = 0; index < text.length; index += 1) {
      hash ^= text.charCodeAt(index);
      hash = Math.imul(hash, 16777619) >>> 0;
    }
    return hash.toString(16).padStart(8, "0");
  }

  function safeStorageGet(key) {
    try {
      return global.localStorage.getItem(key);
    } catch (error) {
      return null;
    }
  }

  function safeStorageSet(key, value) {
    try {
      global.localStorage.setItem(key, value);
    } catch (error) {
      return null;
    }
    return value;
  }

  async function sha256Hex(bytes) {
    var subtle = global.crypto && global.crypto.subtle;
    if (!subtle) {
      return "";
    }
    var digest = await subtle.digest("SHA-256", copyBytes(bytes));
    return Array.prototype.map.call(
      new Uint8Array(digest),
      function (value) { return value.toString(16).padStart(2, "0"); }
    ).join("");
  }

  function DosFileSystem(options) {
    options = options || {};
    var persistentSupport = global.indexedDB && global.crypto && global.crypto.subtle;
    this.mode = options.mode === "memory" || !persistentSupport
      ? "memory"
      : "persistent";
    this.databaseName = String(options.databaseName || "f030-uw2-dos-files-v1");
    this.namespace = String(options.namespace || "f030-uw2");
    this.profile = String(options.profile || "default");
    this.variant = String(options.variant || "default");
    this.profileKey = profileId(this.profile);
    this.databaseId = this.databaseName + "-" + this.profileKey;
    this.indexKey = storageKey(this.namespace, this.profileKey, "index-v1");
    this.memory = new Map();
    this.metadata = new Map();
    this.handles = new Map();
    this.nextHandle = 1;
    this.dbPromise = null;
    this.restoreMetadataIndex();
  }

  DosFileSystem.prototype.restoreMetadataIndex = function () {
    if (this.mode !== "persistent") {
      return;
    }
    var encoded = safeStorageGet(this.indexKey);
    if (!encoded) {
      return;
    }
    try {
      var entries = JSON.parse(encoded);
      if (Array.isArray(entries)) {
        entries.forEach(function (entry) {
          if (entry && entry.path) {
            this.metadata.set(entry.path, entry);
          }
        }, this);
      }
    } catch (error) {
      return null;
    }
  };

  DosFileSystem.prototype.rememberMetadata = function (entry) {
    if (this.mode !== "persistent") {
      return;
    }
    this.metadata.set(entry.path, entry);
    safeStorageSet(this.indexKey, JSON.stringify(Array.from(this.metadata.values())));
  };

  DosFileSystem.prototype.openDatabase = function () {
    var self = this;
    if (self.mode !== "persistent" || !global.indexedDB) {
      return Promise.resolve(null);
    }
    if (self.dbPromise) {
      return self.dbPromise;
    }
    self.dbPromise = new Promise(function (resolve) {
      var request;
      try {
        request = global.indexedDB.open(self.databaseId, DB_VERSION);
      } catch (error) {
        resolve(null);
        return;
      }
      request.onupgradeneeded = function () {
        var database = request.result;
        if (!database.objectStoreNames.contains(STORE_NAME)) {
          database.createObjectStore(STORE_NAME, { keyPath: "path" });
        }
      };
      request.onsuccess = function () { resolve(request.result); };
      request.onerror = function () { resolve(null); };
      request.onblocked = function () { resolve(null); };
    });
    return self.dbPromise;
  };

  DosFileSystem.prototype.readPersisted = async function (path) {
    var database = await this.openDatabase();
    if (!database) {
      return null;
    }
    return new Promise(function (resolve) {
      try {
        var request = database.transaction(STORE_NAME, "readonly")
          .objectStore(STORE_NAME).get(path);
        request.onsuccess = function () {
          var record = request.result;
          resolve(record && record.bytes != null ? {
            bytes: copyBytes(record.bytes),
            metadata: record
          } : null);
        };
        request.onerror = function () { resolve(null); };
      } catch (error) {
        resolve(null);
      }
    });
  };

  DosFileSystem.prototype.writePersisted = async function (record) {
    var database = await this.openDatabase();
    if (!database) {
      return;
    }
    await new Promise(function (resolve) {
      try {
        var transaction = database.transaction(STORE_NAME, "readwrite");
        transaction.objectStore(STORE_NAME).put({
          path: record.path,
          bytes: record.bytes.buffer.slice(0),
          size: record.size,
          sha256: record.sha256,
          origin: record.origin,
          variant: record.variant,
          importedAt: record.importedAt
        });
        transaction.oncomplete = function () { resolve(); };
        transaction.onerror = function () { resolve(); };
        transaction.onabort = function () { resolve(); };
      } catch (error) {
        resolve();
      }
    });
  };

  /* Target artefact; record: analysis/functions/file-boundary.md. */
  DosFileSystem.prototype.importBytes = async function (name, value, metadata) {
    var path = normalizeDosPath(name);
    var bytes = copyBytes(value);
    metadata = metadata || {};
    var record = {
      path: path,
      bytes: bytes,
      size: bytes.byteLength,
      sha256: this.mode === "persistent" ? await sha256Hex(bytes) : "",
      origin: String(metadata.origin || "host-import"),
      variant: String(metadata.variant || this.variant),
      importedAt: new Date().toISOString()
    };
    this.memory.set(path, bytes);
    this.rememberMetadata(record);
    await this.writePersisted(record);
    return copyBytes(bytes);
  };

  /* Target artefact; record: analysis/functions/file-boundary.md. */
  DosFileSystem.prototype.readAll = async function (name, hostLoader) {
    var path = normalizeDosPath(name);
    var cached = this.memory.get(path);
    if (cached) {
      return copyBytes(cached);
    }
    var persisted = await this.readPersisted(path);
    if (persisted) {
      this.memory.set(path, persisted.bytes);
      this.rememberMetadata(persisted.metadata);
      return copyBytes(persisted.bytes);
    }
    var imported = await hostLoader(path);
    await this.importBytes(path, imported, { origin: "host-import" });
    return copyBytes(this.memory.get(path));
  };

  /* DOS file boundary; record: analysis/functions/file-boundary.md. */
  DosFileSystem.prototype.open = async function (name, hostLoader) {
    var path = normalizeDosPath(name);
    var bytes = await this.readAll(path, hostLoader);
    var handle = this.nextHandle++;
    this.handles.set(handle, { bytes: bytes, position: 0 });
    return handle;
  };

  DosFileSystem.prototype.getHandle = function (handle) {
    return this.handles.get(handle);
  };

  /* DOS file boundary; record: analysis/functions/file-boundary.md. */
  DosFileSystem.prototype.read = async function (handle, targetOrLength) {
    var state = this.getHandle(handle);
    var target = typeof targetOrLength === "number"
      ? new Uint8Array(Math.max(0, targetOrLength))
      : asBytes(targetOrLength);
    var available = Math.max(0, state.bytes.byteLength - state.position);
    var count = Math.min(target.byteLength, available);
    target.set(state.bytes.subarray(state.position, state.position + count));
    state.position += count;
    return { bytesRead: count, data: target.subarray(0, count) };
  };

  /* DOS file boundary; record: analysis/functions/file-boundary.md. */
  DosFileSystem.prototype.seek = function (handle, offset, origin) {
    var state = this.getHandle(handle);
    var base = origin === 1 ? state.position : origin === 2 ? state.bytes.byteLength : 0;
    state.position = Math.max(0, Math.min(state.bytes.byteLength, base + Number(offset || 0)));
    return state.position;
  };

  /* DOS file boundary; record: analysis/functions/file-boundary.md. */
  DosFileSystem.prototype.tell = function (handle) {
    return this.getHandle(handle).position;
  };

  /* DOS file boundary; record: analysis/functions/file-boundary.md. */
  DosFileSystem.prototype.close = function (handle) {
    this.handles.delete(handle);
  };

  global.UW2DosFS = {
    DosFileSystem: DosFileSystem,
    normalizeDosPath: normalizeDosPath,
    create: function (options) { return new DosFileSystem(options); }
  };
}(window));
