import { build } from 'esbuild';
import { readFile, writeFile } from 'node:fs/promises';

const { metafile } = await build({
  entryPoints: ['scripts/wallet-vendor.js'],
  outfile: 'web/vendor/wallet.js',
  bundle: true,
  format: 'esm',
  platform: 'browser',
  target: ['es2022'],
  minify: true,
  legalComments: 'none',
  inject: ['scripts/browser-globals.js'],
  metafile: true,
});
// Retain the licenses of every package included in the bundle, not just direct dependencies.
const packages = new Set(Object.keys(metafile.inputs).map(path => {
  const start = path.lastIndexOf('node_modules/');
  if (start < 0) return;
  const name = path.slice(start + 13).match(/^(?:@[^/]+\/)?[^/]+/)[0];
  return path.slice(0, start + 13) + name + '/';
}).filter(Boolean));
const licenses = [];
for (const directory of [...packages].sort()) {
  const { name, version } = JSON.parse(await readFile(directory + 'package.json', 'utf8'));
  let license;
  for (const file of ['LICENSE', 'LICENSE.md', 'LICENSE.txt', 'LICENCE.md', 'license', 'LICENSE-MIT']) {
    try { license = await readFile(directory + file, 'utf8'); break; } catch (error) {
      if (error.code !== 'ENOENT') throw error;
    }
  }
  if (!license) throw new Error(`Missing bundled license: ${name}`);
  licenses.push(`${name}@${version}\n\n${license.replace(/\r\n?/g, '\n').trimEnd()}`);
}
await writeFile('web/vendor/wallet.LICENSES.txt', licenses.join('\n\n----------------------------------------\n\n') + '\n');
