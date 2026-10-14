// DOS contract: analysis/display-driver.md, "Copy exports 6, 7, 11" (VESA480.DLL).
// Implements only the DOS-measured domain: source and destination spans equal,
// both inside their bitmaps/screen, no shadow buffer. Anything else throws:
// clipping, rejection, 16.16 stretch and the shadow filter remain Unproven.
export const SCREEN_W = 640;
export const SCREEN_H = 480;

function checkDomain(desc, src, dst) {
  const [x0, y0, x1, y1] = src;
  const [dx0, dy0, dx1, dy1] = dst;
  if (desc.shadow) throw Error('Unproven: shadow-buffer copy');
  if (x0 < 0 || y0 < 0 || x1 > desc.maxX || y1 > desc.maxY || x1 < x0 || y1 < y0)
    throw Error('Unproven: source rectangle outside the bitmap');
  if (dx0 < 0 || dy0 < 0 || dx1 >= SCREEN_W || dy1 >= SCREEN_H)
    throw Error('Unproven: clipped destination');
  if (dx1 - dx0 !== x1 - x0 || dy1 - dy0 !== y1 - y0) throw Error('Unproven: stretched copy');
}

// bitmap: { pixels: Uint8Array, maxX, maxY, shadow }, rows packed at stride maxX + 1.
// export 11: bitmap sub-rectangle `src` = [x0, y0, x1, y1] to screen rectangle `dst`.
export function blitRectToScreen(screen, bitmap, src, dst) {
  checkDomain(bitmap, src, dst);
  const stride = bitmap.maxX + 1;
  const width = src[2] - src[0] + 1;
  for (let row = 0; row <= src[3] - src[1]; row++) {
    const from = (src[1] + row) * stride + src[0];
    screen.set(bitmap.pixels.subarray(from, from + width), (dst[1] + row) * SCREEN_W + dst[0]);
  }
}

// export 6: the whole bitmap to a screen rectangle.
export function blitToScreen(screen, bitmap, dst) {
  blitRectToScreen(screen, bitmap, [0, 0, bitmap.maxX, bitmap.maxY], dst);
}

// export 7: a screen rectangle into the whole bitmap.
export function readFromScreen(screen, bitmap, src) {
  const dst = [0, 0, bitmap.maxX, bitmap.maxY];
  checkDomain(bitmap, dst, src);
  const stride = bitmap.maxX + 1;
  for (let row = 0; row <= bitmap.maxY; row++) {
    const from = (src[1] + row) * SCREEN_W + src[0];
    bitmap.pixels.set(screen.subarray(from, from + stride), row * stride);
  }
}
