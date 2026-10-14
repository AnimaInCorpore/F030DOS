import { readFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { checkDraw } from '../web/reference/check-draw.mjs';
const fixture = JSON.parse(await readFile(new URL('./fixtures/dos-draw.json', import.meta.url)));
const exe = await readFile(new URL('../game/EXE/PANZER.EXE', import.meta.url));
const dll = await readFile(new URL('../game/LIB/DRV/VESA480.DLL', import.meta.url));
if (createHash('sha256').update(exe).digest('hex') !== fixture.authority) throw Error('Wrong DOS build');
if (createHash('sha256').update(dll).digest('hex') !== fixture.driverDllSha256) throw Error('Wrong display driver');
console.log(`PASS ${checkDraw(fixture)} DOS display-driver fixtures (exports 6, 7, 11; unclipped 1:1 domain)`);
