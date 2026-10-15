import assert from 'node:assert/strict';
import test from 'node:test';
import { FRAME_BYTES, FRAME_PATH, publishFrame, rgbaToYuyv } from '../web/camera.js';

test('black and white have neutral chroma and video-range luminance', () => {
  assert.deepEqual(rgbaToYuyv(Uint8Array.of(0, 0, 0, 255, 255, 255, 255, 255)),
    Uint8Array.of(16, 128, 235, 128));
});

test('red produces YUYV, not UYVY, and alpha is ignored', () => {
  assert.deepEqual(rgbaToYuyv(Uint8Array.of(255, 0, 0, 0, 255, 0, 0, 255)),
    Uint8Array.of(82, 90, 82, 240));
});

test('conversion can reuse an output buffer', () => {
  const output = new Uint8Array(4);
  assert.equal(rgbaToYuyv(new Uint8Array(8), output), output);
});

test('reject odd pixel counts and mismatched output buffers', () => {
  assert.throws(() => rgbaToYuyv(new Uint8Array(4)));
  assert.throws(() => rgbaToYuyv(new Uint8Array(8), new Uint8Array(3)));
});

test('publish only complete frames, using atomic replacement', () => {
  const calls = [];
  const fs = {
    writeFile: (path, data) => calls.push(['write', path, data]),
    rename: (from, to) => calls.push(['rename', from, to]),
  };
  assert.throws(() => publishFrame(fs, new Uint8Array(1)));
  assert.equal(calls.length, 0);
  const frame = new Uint8Array(FRAME_BYTES);
  publishFrame(fs, frame);
  assert.deepEqual(calls, [
    ['write', `${FRAME_PATH}.next`, frame],
    ['rename', `${FRAME_PATH}.next`, FRAME_PATH],
  ]);
});
