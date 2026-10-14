// N/A - differential test runner; authority remains the captured DOS outputs.
import { readFile } from 'node:fs/promises';
import { checkFixture } from '../web/reference/check-fixture.mjs';
const fixtures = JSON.parse(await readFile(new URL('./fixtures/dos-geometry.json', import.meta.url)));
if (fixtures.authority !== '115ada29636b32c3e07446fdf4569d97324d357a1e71dafb859dd95c3cb69a86') {
  throw Error('Wrong DOS build');
}
for (const fixture of fixtures.cases) {
  checkFixture(fixture);
  console.log(`PASS ${fixture.id}: ${fixture.functionId} (${fixture.kind})`);
}
console.log(`${fixtures.cases.length} JavaScript/DOS contract fixtures equal`);
