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
    assert.match(await page.text(), /Boot Thunderden/);
    const js = await fetch(base + '/app.js', { method: 'HEAD' });
    assert.match(js.headers.get('content-type'), /javascript/);
    const escaped = await fetch(base + '/..%2Fpackage.json');
    assert.equal(escaped.status, 403);
    const missing = await fetch(base + '/missing');
    assert.equal(missing.status, 404);
  } finally {
    server.close();
    server.closeAllConnections();
    await once(server, 'close');
  }
});
