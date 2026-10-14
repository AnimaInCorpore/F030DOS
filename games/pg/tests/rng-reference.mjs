import { readFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { checkRng } from '../web/reference/check-rng.mjs';
const fixture = JSON.parse(await readFile(new URL('./fixtures/dos-rng.json', import.meta.url)));
const exe = await readFile(new URL('../game/EXE/PANZER.EXE', import.meta.url));
if (createHash('sha256').update(exe).digest('hex') !== fixture.authority) throw Error('Wrong DOS build');
console.log(`PASS ${checkRng(fixture)} DOS RNG fixtures: pointer, seed stores and chained transitions`);
