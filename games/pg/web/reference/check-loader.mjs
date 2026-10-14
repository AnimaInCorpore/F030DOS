// N/A - isolated contract runner. Captured state does not replace game boot.
import { sub_00037E75 } from './loader.mjs';
import { fromHex, toHex } from './check-fixture.mjs';
import { sub_00060907, sub_00060926 } from './strings.mjs';

export function checkLoaderStrings(fixture) {
  for (const [index, sample] of fixture.strings.entries()) {
    const destination = fromHex(sample.input.destinationHex);
    const source = fromHex(sample.input.sourceHex);
    const fn = sample.functionId === 'sub_00060907' ? sub_00060907 : sub_00060926;
    const result = fn(destination, 0, source, 0);
    const actual = { destinationHex: toHex(destination),
      eaxReturnsDestination: result.eax === 0, edxSourceDelta: result.edx };
    if (JSON.stringify(actual) !== JSON.stringify(sample.output))
      throw Error(`String helper ${index} differs from DOS`);
  }
  return fixture.strings.length;
}

export function checkLoader(fixture, resources) {
  const state = new Uint8Array(0x220000);
  for (const span of fixture.input.stateSpans) state.set(fromHex(span.hex), span.offset);
  const reads = [], streams = [], operations = [];
  const io = {
    open(path) {
      const name = path.split(/[\\/]/).at(-1).toUpperCase();
      if (!resources[name]) throw Error(`Missing resource ${name}`);
      const stream = { name, position: 0, closed: false };
      streams.push(stream); operations.push(`open:${name}`); return stream;
    },
    read(stream, itemSize, itemCount, callVaddr) {
      if (stream.closed) throw Error('Read after close');
      const data = resources[stream.name].slice(stream.position, stream.position + itemSize * itemCount);
      if (data.length !== itemSize * itemCount) throw Error('Short read outside verified fixture scope');
      reads.push({ callVaddr, itemSize, itemCount, returnedItems: itemCount,
        fileOffset: stream.position, resource: stream.name, bytes: data.length, data });
      stream.position += data.length; return data;
    },
    close(stream) { stream.closed = true; operations.push(`close:${stream.name}`); },
  };
  const actual = sub_00037E75(state, fixture.virtualBase, io);
  if (actual.eax !== fixture.output.eax) throw Error('Loader EAX differs from DOS');
  for (const span of fixture.output.stateSpans) {
    if (toHex(state.slice(span.offset, span.offset + span.hex.length / 2)) !== span.hex)
      throw Error(`Loader global mismatch at ${span.offset.toString(16)}`);
  }
  for (const array of fixture.output.arrays) {
    const offset = array.address - fixture.virtualBase;
    if (toHex(state.slice(offset, offset + array.hex.length / 2)) !== array.hex)
      throw Error(`Loader array mismatch at ${array.address.toString(16)}`);
  }
  if (reads.length !== fixture.output.reads.length) throw Error('Loader read count differs from DOS');
  reads.forEach((read, index) => {
    for (const key of Object.keys(fixture.output.reads[index])) {
      if (key !== 'sha256' && read[key] !== fixture.output.reads[index][key])
        throw Error(`Loader read ${index} ${key} differs from DOS`);
    }
  });
  if (streams.some(s => !s.closed || s.position !== resources[s.name].length))
    throw Error('Loader did not consume and close both resources');
  return { actual, reads, operations };
}
