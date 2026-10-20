import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFile } from 'node:fs/promises';
import { RELEASE as standalone } from '../web/release.js';
import { RELEASE as website } from '../web/site/release.js';

if (!process.argv[2]) throw new Error('Usage: npm run check:cloudflare -- https://your-preview.workers.dev');
const origin = new URL(process.argv[2]);
const emulator = JSON.parse(await readFile(new URL('../deploy/emulator.json', import.meta.url), 'utf8'));
const request = (path, options) => fetch(new URL(path, origin), { signal: AbortSignal.timeout(120000), ...options });
function isolated(response) {
  assert.equal(response.headers.get('Cross-Origin-Opener-Policy'), 'same-origin');
  assert.equal(response.headers.get('Cross-Origin-Embedder-Policy'), 'require-corp');
}
for (const [path, marker] of [['/', 'data-demo="website"'], ['/wallet-mockup/', 'id="seed-qr"'], ['/demo/', 'Browser demo · Preview 8']]) {
  const response = await request(path);
  assert.equal(response.status, 200, path);
  isolated(response);
  assert.ok((await response.text()).includes(marker), path);
  console.log('Page and shared-memory headers:', path);
}
for (const [path, expected, type] of [
  ['/assets/site/thunderden.img', website, 'application/octet-stream'],
  ['/assets/thunderden.img', standalone, 'application/octet-stream'],
  ['/emulator/qemu-system-x86_64.wasm', emulator.files['qemu-system-x86_64.wasm'], 'application/wasm'],
]) {
  const response = await request(path);
  assert.equal(response.status, 200, path);
  isolated(response);
  assert.equal(response.headers.get('Content-Type'), type);
  assert.equal(response.headers.get('Content-Encoding'), 'gzip');
  assert.equal(Number(response.headers.get('X-Uncompressed-Content-Length')), expected.bytes);
  const bytes = Buffer.from(await response.arrayBuffer());
  assert.equal(bytes.length, expected.bytes);
  assert.equal(createHash('sha256').update(bytes).digest('hex'), expected.sha256);
  const etag = response.headers.get('ETag');
  assert.ok(etag);
  const cached = await request(path, { headers: { 'If-None-Match': etag } });
  assert.equal(cached.status, 304);
  assert.equal((await cached.arrayBuffer()).byteLength, 0);
  const head = await request(path, { method: 'HEAD' });
  assert.equal(head.status, 200);
  assert.equal(head.headers.get('Content-Encoding'), 'gzip');
  assert.equal((await head.arrayBuffer()).byteLength, 0);
  console.log('Decoded checksum, type, HEAD and cache revalidation:', path);
}
for (const path of ['/missing-file.js', '/assets/site/missing.img', '/encoded-assets.json']) {
  const response = await request(path);
  assert.equal(response.status, 404, path);
  await response.body?.cancel();
}
console.log('PASS: HTTP deployment checks. Browser boot and physical camera checks are separate.');
