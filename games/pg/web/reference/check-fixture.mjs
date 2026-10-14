// N/A - host fixture adapter. It does not produce expected game outputs.
import { sub_00010976, sub_00048105 } from './geometry.mjs';

export const fromHex = hex => Uint8Array.from(hex.match(/../g) ?? [], pair => parseInt(pair, 16));
export const toHex = bytes => Array.from(bytes, byte => byte.toString(16).padStart(2, '0')).join('');

export function checkFixture(fixture) {
  const state = new Uint8Array(0x33240);
  const view = new DataView(state.buffer);
  const input = fixture.input;
  let actual;
  if (fixture.functionId === 'sub_00010976') {
    state[0xccb1] = input.style;
    view.setUint16(0xcc88, input.maxWidth, true);
    view.setUint16(0xcc86, input.maxHeight, true);
    state.set(fromHex(input.recordHex), 0x21d6 + input.style * 24);
    const output = new Uint8Array(8).fill(0xa5);
    const heightOffset = input.aliasOutputs ? 1 : 3;
    output.set(fromHex(input.widthBefore), 1);
    output.set(fromHex(input.heightBefore), heightOffset);
    const before = state.slice();
    const returned = sub_00010976(state, output, 1, heightOffset);
    if (toHex(state) !== toHex(before)) throw Error(`${fixture.id}: changed input arena`);
    if ([0, 5, 6, 7].some(index => output[index] !== 0xa5)) throw Error(`${fixture.id}: output overrun`);
    actual = { widthHex: toHex(output.slice(1, 3)),
      heightHex: toHex(output.slice(heightOffset, heightOffset + 2)), ...returned };
  } else if (fixture.functionId === 'sub_00048105') {
    const row = 0xc61c + (input.index & 0xff) * 20;
    state.set(fromHex(input.rowBefore), row);
    const expectedState = state.slice();
    expectedState.set(fromHex(fixture.output.rowHex), row);
    const returned = sub_00048105(state, input, input.index);
    actual = { rowHex: toHex(state.slice(row, row + 20)), ...returned };
    if (toHex(state) !== toHex(expectedState)) throw Error(`${fixture.id}: arena mismatch`);
  } else {
    throw Error(`Unknown DOS fixture function ${fixture.functionId}`);
  }
  if (JSON.stringify(actual) !== JSON.stringify(fixture.output)) {
    throw Error(`${fixture.id}: ${JSON.stringify(actual)} differs from DOS ${JSON.stringify(fixture.output)}`);
  }
  return { id: fixture.id, functionId: fixture.functionId, actual };
}
