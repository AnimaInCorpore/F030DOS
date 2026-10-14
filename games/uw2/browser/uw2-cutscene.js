/*
 * UW2 browser reference: cutscene function slice.
 *
 * The DOS executable remains authoritative.  This module mirrors the
 * recovered function contracts at the file/record/frame boundary: LPF page
 * and record lookup, ANIM delta decoding, and indexed framebuffer display.
 */
(function (global) {
  "use strict";

  var WIDTH = 320;
  var HEIGHT = 200;
  var FRAME_BYTES = WIDTH * HEIGHT;
  var LPF_DIR = 0x0500;
  var LPF_PAGE_BASE = 0x0B00;
  var LPF_PAGE_STRIDE = 0x10000;
  var LPF_PALETTE_START = 0x0100;
  var LPF_PALETTE_END = 0x0500;

  function copyBytes(value) {
    var source = value instanceof Uint8Array
      ? value
      : new Uint8Array(value);
    return new Uint8Array(source);
  }

  function readU16LE(bytes, offset) {
    return bytes[offset] | (bytes[offset + 1] << 8);
  }

  function readI16LE(bytes, offset) {
    var value = readU16LE(bytes, offset);
    return value < 0x8000 ? value : value - 0x10000;
  }

  function readU32LE(bytes, offset) {
    return (bytes[offset] |
      (bytes[offset + 1] << 8) |
      (bytes[offset + 2] << 16) |
      (bytes[offset + 3] << 24)) >>> 0;
  }

  /* DOS: 0x828E3 cutscene_run; record: analysis/functions/cutscene-intro.md. */
  function parseLPF(input) {
    var bytes = copyBytes(input);
    var pages = readU16LE(bytes, 0x06);
    var recordCount = readU32LE(bytes, 0x08);
    var width = readU16LE(bytes, 0x14);
    var height = readU16LE(bytes, 0x16);
    var records = new Array(recordCount);
    var pageModes = [];
    for (var pageIndex = 0; pageIndex < pages; pageIndex += 1) {
      var directoryOffset = LPF_DIR + pageIndex * 6;
      var baseRecord = readU16LE(bytes, directoryOffset);
      var pageRecordCount = readU16LE(bytes, directoryOffset + 2);
      var declaredBytes = readU16LE(bytes, directoryOffset + 4);
      var pageOffset = LPF_PAGE_BASE + pageIndex * LPF_PAGE_STRIDE;
      var sizes = [];
      var sizeSum = 0;
      for (var sizeIndex = 0; sizeIndex < pageRecordCount; sizeIndex += 1) {
        var size = readU16LE(bytes, pageOffset + 8 + sizeIndex * 2);
        sizes.push(size);
        sizeSum += size;
      }
      var balance = declaredBytes === sizeSum
        ? "payload"
        : declaredBytes === sizeSum + 8 + pageRecordCount * 2
          ? "whole-page"
          : "unbalanced";
      pageModes.push({
        index: pageIndex,
        baseRecord: baseRecord,
        recordCount: pageRecordCount,
        declaredBytes: declaredBytes,
        sizeSum: sizeSum,
        balance: balance
      });

      var payloadOffset = pageOffset + 8 + pageRecordCount * 2;
      for (var recordOffset = 0; recordOffset < pageRecordCount; recordOffset += 1) {
        var recordIndex = baseRecord + recordOffset;
        var recordSize = sizes[recordOffset];
        var recordEnd = payloadOffset + recordSize;
        records[recordIndex] = bytes.slice(payloadOffset, recordEnd);
        payloadOffset = recordEnd;
      }
    }
    return {
      bytes: bytes,
      width: width,
      height: height,
      pages: pages,
      recordCount: recordCount,
      paletteBgra: bytes.slice(LPF_PALETTE_START, LPF_PALETTE_END),
      records: records,
      pageModes: pageModes
    };
  }

  /* DOS: 0x828E3 cutscene_run; record: analysis/functions/cutscene-intro.md. */
  function decodeRecord(recordInput, previousInput) {
    var record = copyBytes(recordInput);
    var previous = copyBytes(previousInput);
    if (!record.length) {
      return previous;
    }

    var output = previous;
    var position = record[1] ? readU16LE(record, 2) : 0;
    if (position & 1) {
      position += 1;
    }
    var cursor = 4;
    while (cursor < record.length) {
      var rawCount = record[cursor++];
      var count = rawCount < 0x80 ? rawCount : rawCount - 0x100;
      if (count > 0) {
        output.set(record.subarray(cursor, cursor + count), position);
        cursor += count;
        position += count;
        continue;
      }
      if (count === 0) {
        count = record[cursor++];
        var value = record[cursor++];
        output.fill(value, position, position + count);
        position += count;
        continue;
      }

      count &= 0x7f;
      if (count) {
        position += count;
        continue;
      }
      var rawLong = readU16LE(record, cursor);
      var signedLong = readI16LE(record, cursor);
      cursor += 2;
      if (signedLong > 0) {
        position += signedLong;
      } else if (signedLong === 0) {
        break;
      } else {
        count = rawLong & 0x7fff;
        if (count >= 0x4000) {
          count -= 0x4000;
          value = record[cursor++];
          output.fill(value, position, position + count);
          position += count;
        } else {
          output.set(record.subarray(cursor, cursor + count), position);
          cursor += count;
          position += count;
        }
      }
    }
    return output;
  }

  /* DOS: 0x828E3 cutscene_run; record: analysis/functions/cutscene-intro.md. */
  function decodeFrames(input) {
    var parsed = parseLPF(input);
    var previous = new Uint8Array(FRAME_BYTES);
    var frames = [];
    for (var index = 0; index < parsed.records.length; index += 1) {
      previous = decodeRecord(parsed.records[index], previous);
      frames.push(previous);
    }
    parsed.frames = frames;
    return parsed;
  }

  /* DOS: 0x83150 cutscene_load_lback; record: analysis/functions/cutscene-intro.md. */
  function readLback(input) {
    return copyBytes(input);
  }

  function channelTo565(value, bits) {
    return Math.round(value * ((1 << bits) - 1) / 255);
  }

  /* Target artefact; record: analysis/functions/presentation-rgb565.md. */
  function paletteToRgb565(paletteBgra) {
    var palette = copyBytes(paletteBgra);
    var words = new Uint16Array(256);
    for (var index = 0; index < 256; index += 1) {
      var offset = index * 4;
      var blue = channelTo565(palette[offset], 5);
      var green = channelTo565(palette[offset + 1], 6);
      var red = channelTo565(palette[offset + 2], 5);
      words[index] = (red << 11) | (green << 5) | blue;
    }
    return words;
  }

  function unpackRgb565(word) {
    return {
      r: Math.round(((word >>> 11) & 31) * 255 / 31),
      g: Math.round(((word >>> 5) & 63) * 255 / 63),
      b: Math.round((word & 31) * 255 / 31)
    };
  }

  /* Target artefact; record: analysis/functions/presentation-rgb565.md. */
  function frameToRgb565(frameInput, paletteBgra) {
    var frame = copyBytes(frameInput);
    var palette = paletteToRgb565(paletteBgra);
    var words = new Uint16Array(FRAME_BYTES);
    var bytes = new Uint8Array(FRAME_BYTES * 2);
    for (var index = 0; index < FRAME_BYTES; index += 1) {
      var word = palette[frame[index]];
      words[index] = word;
      bytes[index * 2] = word >>> 8;
      bytes[index * 2 + 1] = word & 0xff;
    }
    return { words: words, bytes: bytes };
  }

  /* Target artefact; record: analysis/functions/presentation-rgb565.md. */
  function drawFrame(canvas, frameInput, paletteBgra) {
    var frame = copyBytes(frameInput);
    var rgb565 = frameToRgb565(frame, paletteBgra);
    canvas.width = WIDTH;
    canvas.height = HEIGHT;
    var context = canvas.getContext("2d");
    var image = context.createImageData(WIDTH, HEIGHT);
    for (var index = 0; index < FRAME_BYTES; index += 1) {
      var rgb = unpackRgb565(rgb565.words[index]);
      var offset = index * 4;
      image.data[offset] = rgb.r;
      image.data[offset + 1] = rgb.g;
      image.data[offset + 2] = rgb.b;
      image.data[offset + 3] = 255;
    }
    context.putImageData(image, 0, 0);
    return rgb565;
  }

  global.UW2Cutscene = {
    WIDTH: WIDTH,
    HEIGHT: HEIGHT,
    FRAME_BYTES: FRAME_BYTES,
    parseLPF: parseLPF,
    decodeRecord: decodeRecord,
    decodeFrames: decodeFrames,
    readLback: readLback,
    paletteToRgb565: paletteToRgb565,
    frameToRgb565: frameToRgb565,
    drawFrame: drawFrame
  };
}(window));
