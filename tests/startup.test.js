import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import test from 'node:test';
import { estimatedBootProgress, fetchAsset, loadingProgress, verifyImage } from '../web/startup.js';

test('image loading progress excludes trailing padding without changing the full size', () => {
  const mib = 1024 * 1024;
  assert.deepEqual(loadingProgress(8 * mib, 64 * mib, 16 * mib), { value: .5, finishing: false });
  assert.deepEqual(loadingProgress(16 * mib, 64 * mib, 16 * mib), { value: 1, finishing: true });
  assert.deepEqual(loadingProgress(48 * mib, 64 * mib, 16 * mib), { value: 1, finishing: true });
});

test('emulator progress uses its complete decoded size and unknown sizes stay indeterminate', () => {
  assert.deepEqual(loadingProgress(50, 100), { value: .5, finishing: false });
  assert.deepEqual(loadingProgress(100, 100), { value: 1, finishing: false });
  assert.deepEqual(loadingProgress(50, 0), { value: undefined, finishing: false });
});

test('the ten-second estimate never completes boot and becomes indeterminate afterwards', () => {
  assert.equal(estimatedBootProgress(0), 0);
  assert.equal(estimatedBootProgress(6), .6);
  assert.ok(estimatedBootProgress(9.999) < 1);
  assert.equal(estimatedBootProgress(10), undefined);
  assert.equal(estimatedBootProgress(120), undefined);
});

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

test('full-image verification still rejects changes inside the excluded padding', async () => {
  const image = new Uint8Array(1024);
  image.set(new TextEncoder().encode('Public image fixture'));
  const expected = createHash('sha256').update(image).digest('hex');
  await verifyImage(image, expected);
  image[1023] = 1;
  await assert.rejects(verifyImage(image, expected), /image checksum mismatch/);
});
