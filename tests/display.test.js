import assert from 'node:assert/strict';
import test from 'node:test';
import { readPpm, qcode } from '../web/display.js';

test('PPM screen pixels are not mistaken for header whitespace', () => {
  const header = new TextEncoder().encode('P6\n2 1\n255\n');
  const bytes = new Uint8Array([...header, 10, 32, 0, 255, 128, 64]);
  const frame = readPpm(bytes);
  assert.equal(frame.width, 2);
  assert.equal(frame.height, 1);
  assert.deepEqual(frame.rgb, Uint8Array.of(10, 32, 0, 255, 128, 64));
});

test('reject malformed or truncated screen dumps', () => {
  for (const text of ['P6\n0 1\n255\n', 'P6\n99999 1\n255\n', 'P3\n2 1\n255\n', 'P6\n2 1\n255\n']) {
    assert.throws(() => readPpm(new TextEncoder().encode(text)));
  }
});

test('map physical keys to QEMU keys, including modifiers and punctuation', () => {
  assert.equal(qcode('KeyA'), 'a');
  assert.equal(qcode('Digit3'), '3');
  assert.equal(qcode('ArrowDown'), 'down');
  assert.equal(qcode('ShiftRight'), 'shift_r');
  assert.equal(qcode('Quote'), 'apostrophe');
  assert.equal(qcode('F12'), 'f12');
  assert.equal(qcode('Unidentified'), undefined);
});
