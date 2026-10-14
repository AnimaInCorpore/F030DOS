// N/A - captured-input fixture runner. Does not replace connected producers.
import { sub_0003AFF3 } from './unit-classes.mjs';
import { fromHex, toHex } from './check-fixture.mjs';
export function checkUnitClasses(fixture) {
  const state = new Uint8Array(0x33240);
  for (const span of fixture.input.stateSpans) state.set(fromHex(span.hex),span.offset);
  const expected = state.slice();
  for (const span of fixture.output.stateSpans) expected.set(fromHex(span.hex),span.offset);
  const result = sub_0003AFF3(state,fixture.virtualBase);
  if (result.eax !== fixture.output.eax || toHex(state) !== toHex(expected))
    throw Error('Unit classes / side averages / random state differ from DOS');
  return result;
}
