// N/A - differential harness; expected globals/arrays/reads came from DOS.
import { readFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { checkLoader, checkLoaderStrings } from '../web/reference/check-loader.mjs';
const fixture = JSON.parse(await readFile(new URL('./fixtures/dos-loader.json', import.meta.url)));
const sha = data => createHash('sha256').update(data).digest('hex');
const exe = await readFile(new URL('../game/EXE/PANZER.EXE', import.meta.url));
if (sha(exe) !== fixture.authority) throw Error('Wrong DOS build');
const resources = {};
for (const [name, identity] of Object.entries(fixture.resources)) {
  const data = new Uint8Array(await readFile(new URL(`../game/DAT/${name}`, import.meta.url)));
  if (sha(data) !== identity.sha256 || data.length !== identity.bytes) throw Error(`Wrong ${name}`);
  resources[name] = data;
}
const result = checkLoader(fixture, resources);
const strings = checkLoaderStrings(fixture);
result.reads.forEach((read, i) => {
  if (sha(read.data) !== fixture.output.reads[i].sha256) throw Error(`Read ${i} differs from DOS bytes`);
});
console.log(`PASS sub_00037E75: ${result.reads.length} DOS reads, all globals and six arrays equal; ${strings} string contracts equal`);
