import { createHash } from 'node:crypto';
import { cp, mkdir, readFile, readdir, rm, stat, writeFile } from 'node:fs/promises';
import { gzipSync, gunzipSync } from 'node:zlib';
import { RELEASE as standalone } from '../web/release.js';
import { RELEASE as website } from '../web/site/release.js';

const root = new URL('../', import.meta.url);
const output = new URL('dist/', root);
const hash = bytes => createHash('sha256').update(bytes).digest('hex');
const emulator = JSON.parse(await readFile(new URL('deploy/emulator.json', root), 'utf8'));
const encoded = {};

await rm(output, { recursive: true, force: true });
await mkdir(output, { recursive: true });
// Copy only website sources, never local image archives or comparison bundles.
for (const entry of await readdir(new URL('web/', root), { withFileTypes: true })) {
  if (entry.isFile() || ['brand', 'fonts', 'site', 'vendor'].includes(entry.name)) {
    await cp(new URL(`web/${entry.name}`, root), new URL(entry.name, output), { recursive: true });
  }
}

function check(bytes, expected, name) {
  if (bytes.length !== expected.bytes || hash(bytes) !== expected.sha256) {
    throw new Error(`Pinned asset does not match: ${name}`);
  }
  if (expected.contentBytes && bytes.findLastIndex(byte => byte !== 0) + 1 !== expected.contentBytes) {
    throw new Error(`Pinned loading metadata does not match: ${name}`);
  }
}

async function compress(path, bytes, type) {
  const gzip = gzipSync(bytes, { level: 9 });
  if (!gunzipSync(gzip).equals(bytes)) throw new Error(`Compression round trip failed: ${path}`);
  const target = new URL(path + '.gz', output);
  await mkdir(new URL('./', target), { recursive: true });
  await writeFile(target, gzip);
  encoded['/' + path] = { type, bytes: bytes.length, sha256: hash(bytes) };
  console.log(`${path}: ${bytes.length} decoded bytes -> ${gzip.length} uploaded bytes`);
}

for (const [path, release] of [['assets/thunderden.img', standalone], ['assets/site/thunderden.img', website]]) {
  const bytes = await readFile(new URL('web/' + path, root));
  check(bytes, release, path);
  await compress(path, bytes, 'application/octet-stream');
}
await mkdir(new URL('emulator/', output), { recursive: true });
for (const [name, expected] of Object.entries(emulator.files)) {
  const bytes = await readFile(new URL('web/emulator/' + name, root));
  check(bytes, expected, name);
  if (name.endsWith('.wasm')) await compress('emulator/' + name, bytes, 'application/wasm');
  else await writeFile(new URL('emulator/' + name, output), bytes);
}

// Published routes differ from the local development routes; module paths stay put.
const publishHtml = html => html.replace(/<base href="[^"]+">/, '<base href="/">')
  .replaceAll('href="./site/"', 'href="./"')
  .replaceAll('href="./site/#', 'href="./#')
  .replaceAll('href="./site/wallet-mockup/"', 'href="./wallet-mockup/"');
await mkdir(new URL('demo/', output));
await writeFile(new URL('demo/index.html', output),
  (await readFile(new URL('web/index.html', root), 'utf8')).replace('<html lang="en">', '<html lang="en">\n<base href="/">'));
await writeFile(new URL('index.html', output), publishHtml(await readFile(new URL('web/site/index.html', root), 'utf8')));
await mkdir(new URL('wallet-mockup/', output));
await writeFile(new URL('wallet-mockup/index.html', output),
  publishHtml(await readFile(new URL('web/site/wallet-mockup/index.html', root), 'utf8')));
await writeFile(new URL('site/site.js', output), (await readFile(new URL('web/site/site.js', root), 'utf8'))
  .replace("new URL('./site/wallet-mockup/', document.baseURI)", "new URL('./wallet-mockup/', document.baseURI)"));
await rm(new URL('site/index.html', output));
await rm(new URL('site/wallet-mockup/index.html', output));
for (const name of ['_headers', '_redirects']) await cp(new URL('deploy/' + name, root), new URL(name, output));
await writeFile(new URL('404.html', output), '<!doctype html>\n<meta charset="utf-8">\n<title>Not found - Thunder Den</title>\n<h1>Page not found</h1>\n<a href="/">Thunder Den home</a>\n');
await writeFile(new URL('encoded-assets.json', output), JSON.stringify(encoded, null, 2) + '\n');
await writeFile(new URL('.assetsignore', output), 'encoded-assets.json\n');
for (const name of await readdir(output, { recursive: true })) {
  const info = await stat(new URL(name, output));
  if (info.isFile() && info.size > 25 * 1024 * 1024) throw new Error(`Cloudflare asset exceeds 25 MiB: ${name}`);
}
console.log('Cloudflare preview prepared: /, /wallet-mockup/ and /demo/.');
