// N/A - differential fixture adapter, not a renderer.
import { SCREEN_W, SCREEN_H, blitRectToScreen, blitToScreen, readFromScreen } from './draw.mjs';
import { fromHex, toHex } from './check-fixture.mjs';

const rowsToBytes = (rows) => fromHex(rows.join(''));

export function checkDraw(fixture) {
  for (const [index, sample] of fixture.cases.entries()) {
    const [, ...dst] = sample.args;
    const desc = { maxX: sample.desc[1], maxY: sample.desc[2], shadow: sample.desc[4] };
    const screen = new Uint8Array(SCREEN_W * SCREEN_H);
    const before = sample.screenBefore;   // captured only for export 7, the one that reads the screen
    if (before) before.rows.forEach((row, i) =>
      screen.set(fromHex(row), (before.y0 + i) * SCREEN_W + before.x0));
    let actual;
    if (sample.export === 7) {
      const bitmap = { ...desc, pixels: new Uint8Array((desc.maxX + 1) * (desc.maxY + 1)) };
      readFromScreen(screen, bitmap, dst);
      actual = toHex(bitmap.pixels);
      if (actual !== sample.bitmapAfter.join(''))
        throw Error(`draw fixture ${index} (export 7) differs from DOS`);
      continue;
    }
    const src = sample.export === 11 ? sample.rect.slice(1) : [0, 0, desc.maxX, desc.maxY];
    // Only the source rectangle was captured; place it at its own position in a bitmap.
    const bitmap = { ...desc, pixels: new Uint8Array((desc.maxX + 1) * (desc.maxY + 1)) };
    sample.sourceRows.forEach((row, i) =>
      bitmap.pixels.set(fromHex(row), (src[1] + i) * (desc.maxX + 1) + src[0]));
    if (sample.export === 11) blitRectToScreen(screen, bitmap, src, dst);
    else blitToScreen(screen, bitmap, dst);
    const after = sample.screenAfter;
    const rows = [];
    for (let y = after.y0; y <= after.y1; y++)
      rows.push(toHex(screen.subarray(y * SCREEN_W + after.x0, y * SCREEN_W + after.x1 + 1)));
    if (rows.join('') !== after.rows.join(''))
      throw Error(`draw fixture ${index} (export ${sample.export}) differs from DOS`);
  }
  return fixture.cases.length;
}
