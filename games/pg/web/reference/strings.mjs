// DOS sub_00060907 / sub_00060926. Records: analysis/functions/sub_000609*.md.
// Byte-addressed buffers; offsets are the explicit host pointer representation.
export function sub_00060907(destination, dest, source, src = 0) {
  const original = dest;
  while (true) {
    const first = source[src];
    destination[dest] = first;
    if (first === 0) return { eax: original, edx: src };
    const second = source[src + 1];
    src += 2;
    destination[dest + 1] = second;
    dest += 2;
    if (second === 0) return { eax: original, edx: src };
  }
}

export function sub_00060926(destination, dest, source, src = 0) {
  const original = dest;
  while (destination[dest] !== 0) dest++;
  sub_00060907(destination, dest, source, src);
  return { eax: original, edx: src };
}
