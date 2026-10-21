import assert from 'node:assert/strict';
import { once } from 'node:events';
import test from 'node:test';
import { createDemoServer } from '../scripts/serve.mjs';

test('serve the page with shared-memory headers but not files outside web/', async () => {
  const server = createDemoServer();
  server.listen(0, '127.0.0.1');
  await once(server, 'listening');
  const base = `http://127.0.0.1:${server.address().port}`;
  try {
    const page = await fetch(base);
    assert.equal(page.status, 200);
    assert.equal(page.headers.get('cross-origin-opener-policy'), 'same-origin');
    assert.equal(page.headers.get('cross-origin-embedder-policy'), 'require-corp');
    assert.equal(page.headers.get('cache-control'), 'no-cache');
    const etag = page.headers.get('etag');
    assert.ok(etag);
    assert.match(await page.text(), /Loading Thunder Den/);
    const cached = await fetch(base, { headers: { 'If-None-Match': etag } });
    assert.equal(cached.status, 304);
    assert.equal(cached.headers.get('cross-origin-embedder-policy'), 'require-corp');
    assert.equal(await cached.text(), '');
    const js = await fetch(base + '/app.js', { method: 'HEAD' });
    assert.match(js.headers.get('content-type'), /javascript/);
    assert.equal(js.headers.get('content-encoding'), 'gzip');
    assert.ok(Number(js.headers.get('x-uncompressed-content-length')) > 1024);
    assert.equal(js.headers.get('vary'), 'Accept-Encoding');
    const plain = await fetch(base + '/app.js', { headers: { 'Accept-Encoding': 'gzip;q=0' } });
    assert.equal(plain.headers.get('content-encoding'), null);
    const compressed = await fetch(base + '/app.js', { headers: { 'Accept-Encoding': 'gzip' } });
    assert.equal(compressed.headers.get('content-encoding'), 'gzip');
    assert.equal(await compressed.text(), await plain.text());
    for (const [path, type] of [['/style.css', 'text/css'], ['/laptop.svg', 'image/svg+xml'], ['/brand/thunderden-horizontal-paper.svg', 'image/svg+xml']]) {
      const asset = await fetch(base + path);
      assert.equal(asset.status, 200);
      assert.ok(asset.headers.get('content-type').startsWith(type));
      assert.equal(asset.headers.get('content-encoding'), 'gzip');
      assert.ok((await asset.text()).length > 1024);
    }
    const escaped = await fetch(base + '/..%2Fpackage.json');
    assert.equal(escaped.status, 403);
    const missing = await fetch(base + '/missing');
    assert.equal(missing.status, 404);
    for (const path of ['/site/', '/site/wallet-mockup/']) {
      const nested = await fetch(base + path);
      assert.equal(nested.status, 200, path);
      assert.equal(nested.headers.get('cross-origin-opener-policy'), 'same-origin');
      assert.match(await nested.text(), /Thunder Den/);
    }
    const font = await fetch(base + '/fonts/InterVariable.woff2');
    assert.equal(font.headers.get('content-type'), 'font/woff2');
    assert.equal(new TextDecoder().decode((await font.arrayBuffer()).slice(0, 4)), 'wOF2');
    const consoleFont = await fetch(base + '/fonts/TerminusTTF-4.49.3.ttf');
    assert.equal(consoleFont.status, 200);
    assert.equal(consoleFont.headers.get('content-type'), 'font/ttf');
    assert.deepEqual([...new Uint8Array(await consoleFont.arrayBuffer()).slice(0, 4)], [0, 1, 0, 0]);
  } finally {
    server.close();
    server.closeAllConnections();
    await once(server, 'close');
  }
});
