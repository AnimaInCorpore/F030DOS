import { readFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { checkUnitClasses } from '../web/reference/check-unit-classes.mjs';
const fixture = JSON.parse(await readFile(new URL('./fixtures/dos-unit-classes.json', import.meta.url)));
if (createHash('sha256').update(await readFile(new URL('../game/EXE/PANZER.EXE',import.meta.url)))
  .digest('hex') !== fixture.authority) throw Error('Wrong DOS build');
checkUnitClasses(fixture);
console.log('PASS sub_0003AFF3: all 400 classes, both side averages, final seed and EAX equal DOS');
