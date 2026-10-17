import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import test from 'node:test';
import { fetchAsset, verifyImage } from '../web/startup.js';

test('count decoded bytes, not the compressed HTTP Content-Length', async t => {
  const original = new TextEncoder().encode('Public fixture\0'.repeat(1000));
  t.mock.method(globalThis, 'fetch', async path => {
    assert.equal(path, '/image.img');
    return new Response(new ReadableStream({
      start(controller) {
        controller.enqueue(original.subarray(0, 20));
        controller.enqueue(original.subarray(20));
        controller.close();
      },
    }), { headers: {
      'Content-Length': '100', 'Content-Encoding': 'gzip',
      'X-Uncompressed-Content-Length': String(original.length),
    } });
  });
  const progress = [];
  const response = await fetchAsset('/image.img', {
    onProgress: (...values) => progress.push(values),
  });
  assert.deepEqual(new Uint8Array(await response.arrayBuffer()), original);
  assert.deepEqual(progress, [
    [0, original.length, false], [20, original.length, false],
    [original.length, original.length, false], [original.length, original.length, true],
  ]);
});

test('leave progress indeterminate when a compressed response has no decoded size', async t => {
  t.mock.method(globalThis, 'fetch', async path => {
    assert.equal(path, '/image.img');
    return new Response('public fixture', { headers: { 'Content-Encoding': 'gzip', 'Content-Length': '100' } });
  });
  const progress = [];
  const response = await fetchAsset('/image.img', { onProgress: (...values) => progress.push(values) });
  assert.equal(await response.text(), 'public fixture');
  assert.deepEqual(progress.at(-1), [14, 0, true]);
});

test('use ordinary Content-Length for an uncompressed response', async t => {
  t.mock.method(globalThis, 'fetch', async () => new Response('fixture', { headers: { 'Content-Length': '7' } }));
  const progress = [];
  const response = await fetchAsset('/image.img', { onProgress: (...values) => progress.push(values) });
  await response.arrayBuffer();
  assert.deepEqual(progress.at(-1), [7, 7, true]);
});

test('compile the Wasm stream without a second download', async t => {
  const bytes = Uint8Array.of(0, 97, 115, 109, 1, 0, 0, 0);
  let requests = 0;
  t.mock.method(globalThis, 'fetch', async path => {
    requests++;
    assert.equal(path, '/emulator.wasm');
    return new Response(bytes);
  });
  const module = await WebAssembly.compileStreaming(await fetchAsset('/emulator.wasm'));
  assert.ok(new WebAssembly.Instance(module));
  assert.equal(requests, 1);
});

test('surface missing assets and interrupted downloads', async t => {
  t.mock.method(globalThis, 'fetch', async () => new Response('', { status: 404 }));
  await assert.rejects(fetchAsset('/missing.img'), /Run npm run setup/);
  globalThis.fetch = async () => new Response(new ReadableStream({
    start(controller) { controller.error(new Error('Transfer interrupted')); },
  }));
  const response = await fetchAsset('/broken.img');
  await assert.rejects(response.arrayBuffer(), /Transfer interrupted/);
});

test('verification accepts only the expected uncompressed image hash', async () => {
  const bytes = new TextEncoder().encode('Public image fixture');
  const expected = createHash('sha256').update(bytes).digest('hex');
  await verifyImage(bytes, expected);
  await assert.rejects(verifyImage(bytes, '0'.repeat(64)), /image checksum mismatch/);
});
