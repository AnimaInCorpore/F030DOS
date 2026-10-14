/*
 * Browser readers for the recovered DOS data boundary.
 *
 * The hashed DOS executable and captured DOS execution are authoritative.
 * This module is the host-side import/fixture boundary for the first browser
 * milestone. It supplies the connected DOS attract path; it is not a second
 * implementation of game logic. Resource/data sources enter this boundary
 * only when the milestone route traces their DOS consumer.
 */
// Target artefact; record: analysis/functions/browser-attract.md#dos-file-boundary
(() => {
  "use strict";

  const MAP_SIZE = 1024;
  const MAP_BYTES = MAP_SIZE * MAP_SIZE;
  const CONSOLE_WIDTH = 328;
  const CONSOLE_HEIGHT = 290;
  const CONSOLE_BYTES = CONSOLE_WIDTH * CONSOLE_HEIGHT;
  // 00019689's cases load consol1s..consol4s for variants 1..4 and consol5s
  // for 5, 6 and 7 alike. Only the cockpit's is 290 rows; the four the
  // external views use are 245, because the panel they draw is shallower.
  // 00007AA0's run list differs per image but its row extent does not -
  // surface rows 46..213, screen rows 0..167 - so the first 240 rows of
  // either image map to the screen the same way.
  const CONSOLE_HEIGHT_EXTERNAL = 245;
  const CONSOLE_BYTES_EXTERNAL = CONSOLE_WIDTH * CONSOLE_HEIGHT_EXTERNAL;
  const CONSOLE_NAMES = [null, "CONSOL1S.DTA", "CONSOL2S.DTA", "CONSOL3S.DTA",
                         "CONSOL4S.DTA", "CONSOL5S.DTA"];
  const DTA_MAGIC = "Kyle DTA";
  const MISSION_XOR = [0x03, 0x06, 0x12, 0x11];
  const textDecoder = new TextDecoder("latin1");

  const assetRoot = new URL("../assets/extracted/comanche_hdd/", globalThis.location.href);
  const fileSystem = ComancheDosFS.create();

  // DOS: FUN_00016381 [00016381]; record: analysis/functions/browser-attract.md#resource-decoders
  const readU16 = (bytes, offset) => bytes[offset] | (bytes[offset + 1] << 8);
  // DOS: FUN_00016381 [00016381]; record: analysis/functions/browser-attract.md#resource-decoders
  const readI16 = (bytes, offset) => {
    const value = readU16(bytes, offset);
    return value & 0x8000 ? value - 0x10000 : value;
  };
  // DOS: FUN_00018C29/00019A2D [entries 00018C29,00019A2D]; record: analysis/functions/browser-attract.md#demo-replay
  const readU32 = (bytes, offset) => (
    bytes[offset]
    | (bytes[offset + 1] << 8)
    | (bytes[offset + 2] << 16)
    | (bytes[offset + 3] << 24)
  ) >>> 0;
  // DOS: FUN_00018C29/00019A2D [entries 00018C29,00019A2D]; record: analysis/functions/browser-attract.md#demo-replay
  const readI32 = (bytes, offset) => readU32(bytes, offset) | 0;

  // Target artefact; record: analysis/functions/browser-attract.md#dos-file-boundary
  function resourceUrl(name) {
    return new URL(String(name).replace(/\\/g, "/"), assetRoot).href;
  }

  // Target artefact; record: analysis/functions/browser-attract.md#dos-file-boundary
  async function hostLoader(name) {
    const response = await fetch(resourceUrl(name));
    if (!response.ok) {
      const error = new Error(`${name}: HTTP ${response.status}`);
      error.status = response.status;
      throw error;
    }
    return new Uint8Array(await response.arrayBuffer());
  }

  // Target artefact; record: analysis/functions/browser-attract.md#dos-file-boundary
  async function readDosFile(name) {
    return fileSystem.readAll(name, hostLoader);
  }

  // Target artefact; record: analysis/functions/browser-attract.md#resource-decoders
  function requireRange(bytes, offset, count, label) {
    if (offset < 0 || count < 0 || offset + count > bytes.length) {
      throw new Error(`${label}: byte range ${offset}+${count} exceeds ${bytes.length}`);
    }
  }

  // DOS: FUN_00016381 [00016381]; record: analysis/functions/browser-attract.md#resource-decoders
  function readDtaHeader(bytes, name) {
    requireRange(bytes, 0, 128, name);
    if (textDecoder.decode(bytes.subarray(0, 8)) !== DTA_MAGIC) {
      throw new Error(`${name}: expected ${DTA_MAGIC} signature`);
    }
    return {
      widthMax: readU16(bytes, 8),
      heightMax: readU16(bytes, 10),
      displayWidth: readU16(bytes, 12),
      displayHeight: readU16(bytes, 14),
    };
  }

  // DOS: FUN_00016381 [00016381]; record: analysis/functions/browser-attract.md#resource-decoders
  function decodeDta(bytes, expectedBytes = null, name = "DTA") {
    const header = readDtaHeader(bytes, name);
    const expected = expectedBytes === null
      ? (header.widthMax + 1) * (header.heightMax + 1)
      : expectedBytes;
    if (!Number.isSafeInteger(expected) || expected <= 0) {
      throw new Error(`${name}: invalid decoded size ${expected}`);
    }

    const pixels = new Uint8Array(expected);
    let input = 128;
    let output = 0;
    while (output < expected) {
      if (input >= bytes.length) throw new Error(`${name}: DTA stream ended at ${output}/${expected} bytes`);
      const token = bytes[input++];
      let count = 1;
      let value = token;
      if ((token & 0xc0) === 0xc0) {
        count = token & 0x3f;
        if (count === 0) throw new Error(`${name}: zero-count DTA RLE run`);
        if (input >= bytes.length) throw new Error(`${name}: truncated DTA RLE run`);
        value = bytes[input++];
      }
      if (output + count > expected) {
        throw new Error(`${name}: DTA run crosses decoded boundary`);
      }
      pixels.fill(value, output, output + count);
      output += count;
    }

    return { name, header, pixels, expectedBytes: expected, consumed: input };
  }

  // DOS: FUN_00016381 [00016381]; record: analysis/functions/browser-attract.md#resource-decoders
  function paletteFromBytes(bytes, offset, name) {
    if (offset + 769 > bytes.length || bytes[offset] !== 0x0c) return null;
    const sixBit = new Uint8Array(256 * 3);
    const rgb = new Uint8Array(256 * 3);
    for (let index = 0; index < sixBit.length; index += 1) {
      const value = bytes[offset + 1 + index];
      sixBit[index] = value >> 2;
      rgb[index] = value;
    }
    return { name, offset, sixBit, rgb };
  }

  // DOS: FUN_0001644B [0001644B]; SG bank palette contract; record:
  // analysis/functions/browser-attract.md#resource-decoders
  function sgPaletteFromBytes(bytes, offset, name) {
    if (offset + 769 > bytes.length || bytes[offset] !== 0x0c) return null;
    const sixBit = bytes.slice(offset + 1, offset + 769);
    return { name, offset, sixBit, rgb: sixBit.slice() };
  }

  // DOS: FUN_00016381 [00016381]; record: analysis/functions/browser-attract.md#resource-decoders
  function parseDtaResource(bytes, expectedBytes = null, name = "DTA") {
    const decoded = decodeDta(bytes, expectedBytes, name);
    const palette = paletteFromBytes(bytes, decoded.consumed, name);
    return {
      ...decoded,
      palette,
      trailing: bytes.slice(palette ? decoded.consumed + 769 : decoded.consumed),
    };
  }

  // DOS: FUN_0001644B [0001644B]; record: analysis/functions/browser-attract.md#resource-decoders
  function decodeKrl(bytes, name = "RLE") {
    requireRange(bytes, 0, 8, name);
    const tag = textDecoder.decode(bytes.subarray(0, 4));
    if (tag !== "KRL0" && tag !== "KRL1") throw new Error(`${name}: unsupported container ${tag}`);
    const expected = readU32(bytes, 4);
    if (!Number.isSafeInteger(expected)) throw new Error(`${name}: invalid declared size`);

    if (tag === "KRL0") {
      requireRange(bytes, 8, expected, name);
      return {
        name,
        tag,
        declaredSize: expected,
        image: bytes.slice(8, 8 + expected),
        consumed: 8 + expected,
        trailing: bytes.slice(8 + expected),
      };
    }

    const image = new Uint8Array(expected);
    let input = 8;
    let output = 0;
    while (output < expected) {
      if (input >= bytes.length) throw new Error(`${name}: KRL1 stream ended at ${output}/${expected} bytes`);
      const token = bytes[input++];
      let count = 1;
      let value = token;
      if (token >= 0xc0) {
        count = token & 0x3f;
        if (count === 0) throw new Error(`${name}: zero-count KRL1 run`);
        if (input >= bytes.length) throw new Error(`${name}: truncated KRL1 run`);
        value = bytes[input++];
      }
      if (output + count > expected) throw new Error(`${name}: KRL1 run exceeds declared size`);
      image.fill(value, output, output + count);
      output += count;
    }

    return {
      name,
      tag,
      declaredSize: expected,
      image,
      consumed: input,
      trailing: bytes.slice(input),
    };
  }

  // DOS: FUN_0001644B [0001644B]; record: analysis/functions/browser-attract.md#resource-decoders
  function parseSgImage(image, name) {
    requireRange(image, 0, 8, name);
    if (image[0] !== 0x53 || image[1] !== 0x47) throw new Error(`${name}: decoded payload is not SG`);
    const count = readU16(image, 2);
    const paletteOffset = readU32(image, 4);
    const palette = sgPaletteFromBytes(image, paletteOffset, name);
    if (!palette) throw new Error(`${name}: SG palette marker is missing`);

    const sprites = [];
    for (let index = 1; index <= count; index += 1) {
      const offset = index * 8;
      requireRange(image, offset, 8, `${name} sprite ${index}`);
      const width = image[offset];
      const height = image[offset + 1];
      const xOffset = image[offset + 2] & 0x80 ? image[offset + 2] - 0x100 : image[offset + 2];
      const yOffset = image[offset + 3] & 0x80 ? image[offset + 3] - 0x100 : image[offset + 3];
      const pixels = readU32(image, offset + 4);
      if (width && height) requireRange(image, pixels, width * height, `${name} sprite ${index}`);
      sprites.push({ width, height, xOffset, yOffset, pixels });
    }
    return { tag: "SG", count, palette, sprites };
  }

  // DOS: FUN_0001644B [0001644B]; record: analysis/functions/browser-attract.md#resource-decoders
  function parseSkyImage(image, name) {
    // SKY*.RLE is an SG container with one special directory record.  Its
    // width byte is 150, the authored strip height, and the payload is 512
    // column-major strips beginning at +16.  It is not a 320x240 raster.
    requireRange(image, 0, 16 + 512 * 150, name);
    if (image[0] !== 0x53 || image[1] !== 0x47) throw new Error(`${name}: sky payload is not SG`);
    if (readU16(image, 2) !== 1 || image[8] !== 150 || readU32(image, 12) !== 16) {
      throw new Error(`${name}: sky SG directory does not match the 512x150 strip contract`);
    }
    const paletteOffset = readU32(image, 4);
    const palette = sgPaletteFromBytes(image, paletteOffset, name);
    if (!palette) throw new Error(`${name}: sky palette marker is missing`);
    return {
      tag: "SKY-SG",
      width: 512,
      height: 150,
      columnMajor: true,
      pixels: image.slice(16, 16 + 512 * 150),
      palette,
    };
  }

  // DOS: FUN_00005BBF [00005BBF]; record: analysis/functions/browser-attract.md#resource-decoders
  function parseDtl(bytes, name) {
    if (bytes.length !== 5004) throw new Error(`${name}: expected exactly 5004 bytes`);
    const values = new Int32Array(1251);
    for (let index = 0; index < values.length; index += 1) values[index] = readI32(bytes, index * 4);
    return {
      name,
      byteLength: bytes.length,
      columnCount: values[0],
      tables: [
        values.slice(1, 251),
        values.slice(251, 501),
        values.slice(501, 751),
        values.slice(751, 1001),
        values.slice(1001, 1251),
      ],
    };
  }

  // DOS: FUN_0002A14A [0002A14A]; record: analysis/functions/browser-attract.md#mission-selection
  function decodeMissionBytes(bytes, name) {
    if (!bytes.length) throw new Error(`${name}: empty mission stream`);
    const decoded = bytes.slice();
    if (decoded[0] === 0x7b) return decoded;
    if (decoded.length % 4 !== 0) throw new Error(`${name}: encrypted stream is not dword aligned`);
    for (let offset = 0; offset < decoded.length; offset += 4) {
      for (let index = 0; index < 4; index += 1) decoded[offset + index] ^= MISSION_XOR[index];
    }
    return decoded;
  }

  // DOS: FUN_0002A15D [0002A15D]; record: analysis/functions/browser-attract.md#mission-selection
  function braceText(line, name) {
    const start = line.indexOf("{");
    const end = line.indexOf("}", start + 1);
    if (start < 0 || end < 0) throw new Error(`${name}: malformed brace line ${JSON.stringify(line)}`);
    return line.slice(start + 1, end);
  }

  // DOS: FUN_0002A2BF [0002A2BF]; record: analysis/functions/browser-attract.md#mission-selection
  function decimalFields(line, name, expected = null) {
    const raw = line.trim().replace(/^\*/, "");
    const fields = raw.split(",").map((value) => value.trim());
    if (expected !== null && fields.length !== expected) {
      throw new Error(`${name}: expected ${expected} comma fields, got ${fields.length}`);
    }
    if (fields.some((value) => !/^[+-]?\d+$/.test(value))) {
      throw new Error(`${name}: non-decimal field in ${JSON.stringify(line)}`);
    }
    return { raw: line, fields, values: fields.map((value) => Number.parseInt(value, 10)) };
  }

  // DOS: FUN_0002A1AD [0002A1AD-0002A299]; record: analysis/functions/browser-attract.md#mission-selection
  function readUntilDelimiter(lines, cursor, name) {
    const result = [];
    while (cursor < lines.length && lines[cursor].trim() !== "<") {
      result.push(lines[cursor]);
      cursor += 1;
    }
    if (cursor >= lines.length) throw new Error(`${name}: missing '<' delimiter`);
    return { lines: result, cursor: cursor + 1 };
  }

  // DOS: FUN_000290C6/0002A1AD [000290C6-00029359 / 0002A1AD-0002A299]; record: analysis/functions/browser-attract.md#mission-selection
  function parseMissionFile(bytes, fileName = "MISSION.MIS") {
    const decoded = decodeMissionBytes(bytes, fileName);
    // The shipped mission files include a terminal NUL after the final CR/LF;
    // it is file padding, not another authored record.
    const lines = textDecoder.decode(decoded).replace(/\0+$/, "").replace(/\r/g, "").split("\n");
    let cursor = 0;
    while (cursor < lines.length && !lines[cursor].trim()) cursor += 1;
    if (cursor >= lines.length || !lines[cursor].trim().startsWith("{")) {
      throw new Error(`${fileName}: missing campaign title`);
    }
    const catalogLine = lines[cursor++];
    const catalogTitle = braceText(catalogLine, fileName);
    const missions = [];

    while (true) {
      while (cursor < lines.length && !lines[cursor].trim()) cursor += 1;
      if (cursor >= lines.length || !lines[cursor].trim()) break;
      if (!lines[cursor].trim().startsWith("{")) {
        throw new Error(`${fileName}: expected mission title at line ${cursor + 1}`);
      }
      const titleLine = lines[cursor++];
      const title = braceText(titleLine, `${fileName} mission ${missions.length}`);

      const descriptionBlock = readUntilDelimiter(lines, cursor, `${fileName} mission ${missions.length} description`);
      cursor = descriptionBlock.cursor;
      const descriptionLines = descriptionBlock.lines;

      const resourceBlock = readUntilDelimiter(lines, cursor, `${fileName} mission ${missions.length} resources`);
      cursor = resourceBlock.cursor;
      const resourceRecords = resourceBlock.lines
        .filter((line) => line.trim())
        .map((line) => ({ raw: line, name: line.trim().toUpperCase() }));
      if (!resourceRecords.length) throw new Error(`${fileName} mission ${missions.length}: empty resource list`);

      if (cursor >= lines.length) throw new Error(`${fileName} mission ${missions.length}: missing kind`);
      const kind = decimalFields(lines[cursor++], `${fileName} mission ${missions.length} kind`, 1);
      if (cursor >= lines.length) throw new Error(`${fileName} mission ${missions.length}: missing start tuple`);
      const start = decimalFields(lines[cursor++], `${fileName} mission ${missions.length} start`, 3);
      // 0002920E-00029234. This read five lines on an assumption about the
      // file's layout, and the fifth was not a scalar line at all: after the
      // loadout pair and 00029204's fuel number, the original skips ONE line
      // and then READS nine numbers - 00029213's `mov ecx, 8` loop into
      // [00019E38] with each value decremented, then one more into
      // [00019E40]/[00019E44]. Those nine are a single line here
      // ("5,3,5,3,3,3,6,3,30"), so the fifth line consumed was the first
      // placement record.
      //
      // That record is the eleven-field "0,0,0,1,0,0,0,0,0,0,0" whose type is
      // 0 - dispatch entry 0 at 00023462, which installs the fixed slot-31
      // object that 00007CC5's camera aims at and 00024C0A draws in the
      // external views. Eating it left the browser with eight records, all
      // type 2, and no slot 31 at all. The original parses NINE,
      // [0x19D64] = 9, types 0,2,2,2,2,2,2,2,2.
      const scalarLines = [];
      for (let index = 0; index < 4; index += 1) {
        if (cursor >= lines.length) throw new Error(`${fileName} mission ${missions.length}: missing scalar line ${index}`);
        scalarLines.push(lines[cursor++]);
      }

      const objectRecords = [];
      while (cursor < lines.length && lines[cursor].trim() !== "<") {
        const line = lines[cursor++];
        if (!line.trim()) continue;
        const record = decimalFields(line, `${fileName} mission ${missions.length} object ${objectRecords.length}`, 11);
        const [type, f1, f2, f3, x, y, heading, f7, f8, f9, f10] = record.values;
        objectRecords.push({
          ...record,
          continuation: line.trim().startsWith("*"),
          // DOS 000068A5 copies these eleven fields into the factory scratch
          // block before dispatching 0002231C. Keep the names beside the raw
          // tuple so the browser factory cannot accidentally treat f2/f3 as
          // sprite numbers: they are mission-resource slot indices.
          type,
          f1,
          f2,
          f3,
          x,
          y,
          heading,
          f7,
          f8,
          f9,
          f10,
        });
      }
      if (cursor >= lines.length) throw new Error(`${fileName} mission ${missions.length}: missing object delimiter`);
      cursor += 1;

      const resources = resourceRecords.map((record) => record.name);
      missions.push({
        fileName,
        catalogTitle,
        catalogLine,
        title,
        titleLine,
        descriptionLines,
        description: descriptionLines.map((line) => line.trim()).filter(Boolean).join(" "),
        resourceRecords,
        resources,
        kind,
        start,
        scalarLines,
        objectRecords,
        objectCount: objectRecords.length,
        resourceSlots: resources.length,
      });
    }

    if (!missions.length) throw new Error(`${fileName}: no mission records`);
    return { fileName, catalogTitle, catalogLine, missions, byteLength: bytes.length };
  }

  // DOS: FUN_0002A320/0002913C [entries 0002A320,0002913C]; record: analysis/functions/browser-attract.md#mission-selection
  function selectedResources(mission) {
    const heightName = mission.resources.find((name) => /^D[1-4]\.DTA$/.test(name));
    const colourName = mission.resources.find((name) => /^C[1-4]\.DTA$/.test(name));
    const paletteName = mission.resources.find((name) => /^(?:N?P)\d+\.DTA$/.test(name));
    const skyName = mission.resources.find((name) => /^SKY[1-4]\.RLE$/.test(name));
    if (!heightName || !colourName || !paletteName || !skyName) {
      throw new Error(`${mission.fileName}: mission ${mission.title} lacks an authored DTA/C/ P/sky resource slot`);
    }
    return { heightName, colourName, paletteName, skyName };
  }

  // Target artefact; record: analysis/functions/browser-attract.md#resource-decoders
  function inspectRle(bytes, name) {
    const container = decodeKrl(bytes, name);
    const marker = textDecoder.decode(container.image.subarray(0, 2));
    let payload = { marker };
    if (marker === "SG") {
      if (name.startsWith("SKY")) {
        payload = parseSkyImage(container.image, name);
      } else {
        const parsed = parseSgImage(container.image, name);
        // DOS has two real SG pixel organizations. COMA/CONS/ZOVE are the
        // plane-chunked family consumed by 00025880; HUDS and all mission
        // object banks are the column-major, bottom-first family consumed by
        // the object/sprite blitters. Keep the fact attached to the decoded
        // bank so a normal object bank cannot silently be decoded as planes.
        payload = {
          ...parsed,
          pixelLayout: /^(?:COMA|CONS|ZOVE)\.RLE$/i.test(name)
            ? "planar-bottom-first"
            : "column-bottom-first",
        };
      }
    }
    return { ...container, payload };
  }

  // Target artefact; record: analysis/functions/browser-attract.md#resource-decoders
  function inspectDta(bytes, name, expectedBytes = null) {
    const decoded = parseDtaResource(bytes, expectedBytes, name);
    return { ...decoded, payload: { marker: DTA_MAGIC, width: decoded.header.widthMax + 1, height: decoded.header.heightMax + 1 } };
  }

  // Target artefact; record: analysis/functions/browser-attract.md#resource-decoders
  function requireDtaShape(image, width, height, name) {
    // Target artefact: host-side fixture validation before semantic rendering.
    if (image.header.widthMax + 1 !== width || image.header.heightMax + 1 !== height) {
      throw new Error(`${name}: expected authored ${width}x${height} DTA shape`);
    }
  }

  // Target artefact; record: analysis/functions/browser-attract.md#resource-decoders
  function requireSgShape(bank, index, width, height, name) {
    // Target artefact: host-side fixture validation before semantic rendering.
    if (bank.payload.count < index) throw new Error(`${name}: missing authored sprite ${index}`);
    const sprite = bank.payload.sprites[index - 1];
    if (!sprite.width || !sprite.height) throw new Error(`${name}: sprite ${index} is empty`);
    if (width !== null && height !== null && (sprite.width !== width || sprite.height !== height)) {
      throw new Error(`${name}: sprite ${index} is ${sprite.width}x${sprite.height}, expected ${width}x${height}`);
    }
  }

  // DOS: FUN_00018C29/00019A2D [entries 00018C29,00019A2D]; record: analysis/functions/browser-attract.md#demo-replay
  function parseDemo(bytes, name = "DEMO.SCR") {
    requireRange(bytes, 0, 17, name);
    const declaredLength = readU32(bytes, 0);
    if (declaredLength !== bytes.length - 4) {
      throw new Error(`${name}: declared length ${declaredLength} does not equal file size minus four ${bytes.length - 4}`);
    }
    const headerBytes = 13;
    const recordBytes = declaredLength - headerBytes;
    if (recordBytes < 0 || recordBytes % 8 !== 0) {
      throw new Error(`${name}: ${recordBytes} bytes remain after the 13-byte header, not a whole record stream`);
    }
    const header = {
      raw: bytes.slice(4, 17),
      x: readI32(bytes, 4),
      y: readI32(bytes, 8),
      angle: readU32(bytes, 12),
      angleHex: `0x${readU32(bytes, 12).toString(16).padStart(8, "0")}`,
      altitude: bytes[16],
    };
    const records = [];
    for (let offset = 17, index = 0; offset < bytes.length; offset += 8, index += 1) {
      records.push({
        index,
        offset,
        key: bytes[offset],
        collective: bytes[offset + 1],
        trigger1: bytes[offset + 2],
        trigger2: bytes[offset + 3],
        axis1: readI16(bytes, offset + 4),
        axis2: readI16(bytes, offset + 6),
        raw: bytes.slice(offset, offset + 8),
      });
    }
    return { name, declaredLength, headerBytes, header, records, cursor: 0 };
  }

  // Target artefact; record: analysis/functions/browser-attract.md#dos-file-boundary
  async function loadMissionEvidence(mission) {
    const selected = selectedResources(mission);
    // DOS 00006494-000067A4 loads these six common banks into the model
    // pointers 00019E74..00019E88. They are not mission trailing slots: the
    // transient attract weapon/effect states use them directly.
    const dynamicNames = [
      "BULL.RLE", "CHAF.RLE", "ROCK.RLE", "HELL.RLE", "STGR.RLE", "BOOM.RLE",
    ];
    const names = [...new Set([
      ...mission.resources,
      ...dynamicNames,
      selected.heightName,
      selected.colourName,
      selected.paletteName,
      selected.skyName,
      "HIGH.DTL",
      "CONSOL1S.DTA",
      "CONSOL2S.DTA",
      "CONSOL3S.DTA",
      "CONSOL4S.DTA",
      "CONSOL5S.DTA",
      "BACK.DTA",
      "RH66SIDE.DTA",
      "TPIC.DTA",
      "ZOVE.RLE",
      "COMA.RLE",
      "CONS.RLE",
      "HUDS.RLE",
      "DEMO0.SCR",
      "DEMO1.SCR",
      "DEMO2.SCR",
      "DEMO3.SCR",
    ])];
    const loaded = new Map();
    await Promise.all(names.map(async (name) => loaded.set(name, await readDosFile(name))));

    const height = inspectDta(loaded.get(selected.heightName), selected.heightName, MAP_BYTES);
    const colour = inspectDta(loaded.get(selected.colourName), selected.colourName, MAP_BYTES);
    const palette = inspectDta(loaded.get(selected.paletteName), selected.paletteName);
    const sky = inspectRle(loaded.get(selected.skyName), selected.skyName);
    const detail = parseDtl(loaded.get("HIGH.DTL"), "HIGH.DTL");
    const consoleImage = inspectDta(loaded.get("CONSOL1S.DTA"), "CONSOL1S.DTA", CONSOLE_BYTES);
    requireDtaShape(consoleImage, CONSOLE_WIDTH, CONSOLE_HEIGHT, "CONSOL1S.DTA");
    // Indexed by the variant the case loads it for, so the runtime can select
    // with [00019D86] directly. Entry 0 is unused: the variant is 1..8.
    const consoleImages = [null, consoleImage];
    for (let digit = 2; digit <= 5; digit += 1) {
      const name = CONSOLE_NAMES[digit];
      const image = inspectDta(loaded.get(name), name, CONSOLE_BYTES_EXTERNAL);
      requireDtaShape(image, CONSOLE_WIDTH, CONSOLE_HEIGHT_EXTERNAL, name);
      consoleImages.push(image);
    }
    const opening = {
      back: inspectDta(loaded.get("BACK.DTA"), "BACK.DTA"),
      side: inspectDta(loaded.get("RH66SIDE.DTA"), "RH66SIDE.DTA"),
      title: inspectDta(loaded.get("TPIC.DTA"), "TPIC.DTA"),
    };
    const banks = {
      zove: inspectRle(loaded.get("ZOVE.RLE"), "ZOVE.RLE"),
      coma: inspectRle(loaded.get("COMA.RLE"), "COMA.RLE"),
      cons: inspectRle(loaded.get("CONS.RLE"), "CONS.RLE"),
      huds: inspectRle(loaded.get("HUDS.RLE"), "HUDS.RLE"),
    };
    // DOS 00019EA4 resolves f2/f3 through the ten mission object-bank slots
    // following the eleven common resources. These are normal column-major
    // SG banks; COMA/CONS/ZOVE are the separate planar family.
    const objectBanks = mission.resources.slice(11).map((name) => inspectRle(loaded.get(name), name));
    const dynamicBanks = new Map(dynamicNames.map((name) => [name, inspectRle(loaded.get(name), name)]));
    requireDtaShape(opening.back, 328, 240, "BACK.DTA");
    requireDtaShape(opening.side, 328, 240, "RH66SIDE.DTA");
    requireDtaShape(opening.title, 328, 390, "TPIC.DTA");
    requireSgShape(banks.cons, 0x09, null, null, "CONS.RLE");
    requireSgShape(banks.cons, 0x25, null, null, "CONS.RLE");
    requireSgShape(banks.cons, 0x39, null, null, "CONS.RLE");
    requireSgShape(banks.huds, 1, 192, 5, "HUDS.RLE");
    requireSgShape(banks.huds, 2, null, null, "HUDS.RLE");
    requireSgShape(banks.huds, 0x21, null, null, "HUDS.RLE");
    const demos = new Map();
    for (let index = 0; index < 4; index += 1) {
      const name = `DEMO${index}.SCR`;
      demos.set(name, parseDemo(loaded.get(name), name));
    }
    return {
      mission,
      selected,
      height,
      colour,
      palette,
      sky,
      detail,
      consoleImage,
      consoleImages,
      opening,
      banks,
      objectBanks,
      dynamicBanks,
      demos,
    };
  }

  // DOS: FUN_00028F05/0002A1AD [00028F05-0002A299]; record: analysis/functions/browser-attract.md#mission-selection
  // The attract path forces campaign 0 and installs one authored mission
  // resource family per pass before the four recorded DEMO streams. This is
  // the connected game-path loader, not a browser mission selector.
  // DOS: FUN_00028F05/0002A1AD [00028F05-0002A299]; record: analysis/functions/browser-attract.md#mission-selection
  async function loadAttractEvidence() {
    const bytes = await readDosFile("0.MIS");
    const campaign = parseMissionFile(bytes, "0.MIS");
    // DOS: FUN_00005690/00028C3E; the attract pass counter is also the
    // campaign-0 mission index used immediately before DEMO<n> is loaded.
    // Keep one evidence object per pass so DEMO1 is not rendered over the
    // first mission's map and sky.
    if (campaign.missions.length < 4) {
      throw new Error(`${campaign.fileName}: attract cycle requires four authored missions`);
    }
    const passes = await Promise.all(campaign.missions.slice(0, 4).map((source, index) => loadMissionEvidence({
      ...source,
      campaignDigit: 0,
      campaignIndex: index,
      campaignTitle: campaign.catalogTitle,
      id: `0:${index}`,
    })));
    return {
      campaign,
      passes,
    };
  }

  globalThis.ComancheDOS = {
    assetRoot: assetRoot.href,
    fileSystem,
    readDosFile,
    decodeDta,
    decodeKrl,
    parseDemo,
    parseMissionFile,
    loadAttractEvidence,
    loadMissionEvidence,
  };
})();
