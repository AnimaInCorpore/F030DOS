// N/A - differential fixture adapter, not a game seed initializer.
import * as functions from './rng.mjs';
import { fromHex, toHex } from './check-fixture.mjs';
export function checkRng(fixture) {
  for (const [index, sample] of fixture.cases.entries()) {
    const state = new Uint8Array(0x7500);
    state.set(fromHex(sample.input.seedHex), 0x74f0);
    const result = functions[sample.functionId](state, fixture.virtualBase, sample.input.eax);
    const actual = { seedHex: toHex(state.slice(0x74f0, 0x74f4)), eax: result.eax };
    if (JSON.stringify(actual) !== JSON.stringify(sample.output))
      throw Error(`RNG fixture ${index} differs from DOS`);
    if (state.some((byte, offset) => byte !== 0 && (offset < 0x74f0 || offset >= 0x74f4)))
      throw Error('RNG changed bytes outside seed');
  }
  return fixture.cases.length;
}
