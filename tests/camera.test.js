import assert from 'node:assert/strict';
import test from 'node:test';
import { WIDTH, HEIGHT, FRAME_BYTES, FRAME_PATH, READY_PATH, cameraAvailability, requestCamera, startCamera, clearCameraFrame, publishFrame, rgbaToYuyv } from '../web/camera.js';

test('browser camera buffers match the smaller virtual camera mode', () => {
  assert.equal(WIDTH, 320);
  assert.equal(HEIGHT, 240);
  assert.equal(FRAME_BYTES, 153600);
});

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

test('clearing the camera publishes video black rather than retaining the last QR', () => {
  let frame;
  const calls = [];
  clearCameraFrame({ writeFile: (path, bytes) => { calls.push([path, bytes]); frame = bytes; }, rename() {} });
  assert.deepEqual(calls[0], [READY_PATH, Uint8Array.of(0)]);
  assert.equal(frame.length, FRAME_BYTES);
  assert.equal(frame.every((byte, index) => byte === (index % 2 ? 128 : 16)), true);
});

function browserMedia(t, getUserMedia) {
  for (const [name, value] of [['isSecureContext', true], ['navigator', { mediaDevices: { getUserMedia } }]]) {
    const before = Object.getOwnPropertyDescriptor(globalThis, name);
    Object.defineProperty(globalThis, name, { configurable: true, value });
    t.after(() => before ? Object.defineProperty(globalThis, name, before) : delete globalThis[name]);
  }
}

test('camera capability checks do not request permission', async t => {
  let calls = 0;
  browserMedia(t, () => { calls++; });
  assert.equal(cameraAvailability(), '');
  assert.equal(calls, 0);
  navigator.mediaDevices.getUserMedia = undefined;
  assert.match(cameraAvailability(), /cannot provide camera access/);
  await assert.rejects(requestCamera(), /cannot provide camera access/);
  assert.equal(calls, 0);
});

test('camera requests retain the small video profile and no audio', async t => {
  let constraints;
  const stream = {};
  browserMedia(t, options => { constraints = options; return Promise.resolve(stream); });
  assert.equal(await requestCamera(), stream);
  assert.equal(constraints.audio, false);
  assert.equal(constraints.video.width.ideal, WIDTH);
  assert.equal(constraints.video.height.ideal, HEIGHT);
  assert.equal(constraints.video.frameRate.ideal, 10);
});

test('cancelling a pending request immediately rejects and stops a late grant', async t => {
  let grant, stopped = 0;
  browserMedia(t, () => new Promise(resolve => { grant = resolve; }));
  const controller = new AbortController();
  const pending = requestCamera(controller.signal);
  controller.abort();
  await assert.rejects(pending, { name: 'AbortError' });
  grant({ getTracks: () => [{ stop() { stopped++; } }] });
  await Promise.resolve();
  assert.equal(stopped, 1);
});

test('an already cancelled request never opens the camera', async t => {
  let calls = 0;
  browserMedia(t, () => { calls++; });
  const controller = new AbortController();
  controller.abort();
  await assert.rejects(requestCamera(controller.signal), { name: 'AbortError' });
  assert.equal(calls, 0);
});

function cameraHarness(t) {
  const track = new EventTarget();
  let stops = 0;
  track.stop = () => { stops++; };
  const stream = { getTracks: () => [track], getVideoTracks: () => [track] };
  browserMedia(t, () => Promise.resolve(stream));
  const context = { fillRect() {}, drawImage() {}, getImageData: () => ({ data: new Uint8Array(WIDTH * HEIGHT * 4) }) };
  const video = { readyState: 2, videoWidth: WIDTH, videoHeight: HEIGHT,
    play: () => Promise.resolve(), pause() {} };
  const writes = [];
  const fs = { writeFile: (path, bytes) => writes.push([path, bytes.slice()]),
    rename: (from, to) => writes.push(['rename', from, to]) };
  for (const [name, value] of [['document', { createElement: () => ({ getContext: () => context }) }], ['window', new EventTarget()]]) {
    const before = Object.getOwnPropertyDescriptor(globalThis, name);
    Object.defineProperty(globalThis, name, { configurable: true, value });
    t.after(() => before ? Object.defineProperty(globalThis, name, before) : delete globalThis[name]);
  }
  return { video, fs, writes, stops: () => stops };
}

test('capture marks ready only after a complete frame and clears readiness on stop', async t => {
  const { video, fs, writes, stops } = cameraHarness(t);
  const active = [];
  const stop = await startCamera(fs, video, assert.fail, undefined, value => active.push(value));
  assert.deepEqual(writes.map(([path]) => path), [`${FRAME_PATH}.next`, 'rename', READY_PATH]);
  assert.deepEqual(writes[2], [READY_PATH, Uint8Array.of(1)]);
  assert.deepEqual(active, [true]);
  stop();
  stop();
  assert.equal(stops(), 1);
  assert.equal(video.srcObject, null);
  assert.deepEqual(writes[3], [READY_PATH, Uint8Array.of(0)]);
  assert.deepEqual(active, [true, false]);
});

test('cancellation while video startup is pending releases the camera immediately', async t => {
  const { video, fs, writes, stops } = cameraHarness(t);
  const controller = new AbortController();
  let playing;
  const started = new Promise(resolve => { playing = resolve; });
  video.play = () => { playing(); return new Promise(() => {}); };
  const pending = startCamera(fs, video, assert.fail, controller.signal);
  await started;
  controller.abort();
  await assert.rejects(pending, { name: 'AbortError' });
  assert.equal(stops(), 1);
  assert.equal(video.srcObject, null);
  assert.equal(writes.some(([path, bytes]) => path === READY_PATH && bytes[0] === 1), false);
});

test('cancellation just after permission resolves cannot start capture', async t => {
  const { video, fs, stops } = cameraHarness(t);
  const controller = new AbortController();
  let plays = 0;
  video.play = () => { plays++; return Promise.resolve(); };
  const pending = startCamera(fs, video, assert.fail, controller.signal);
  queueMicrotask(() => controller.abort());
  await assert.rejects(pending, { name: 'AbortError' });
  assert.equal(plays, 0);
  assert.equal(stops(), 1);
  assert.equal(video.srcObject, null);
});
