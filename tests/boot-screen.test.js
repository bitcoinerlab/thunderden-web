import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { isNetworkMenu } from '../web/boot-screen.js';

const fixture = JSON.parse(readFileSync(new URL('./fixtures/network-menu.json', import.meta.url)));

function frame(markers = fixture.markers, foreground = 255) {
  const { width, height } = fixture;
  const rgb = new Uint8Array(width * height * 3).fill(25);
  for (const marker of markers) {
    const bits = Buffer.from(marker.bits, 'hex');
    assert.equal(bits.length * 8, marker.width * marker.height);
    for (let bit = 0; bit < marker.width * marker.height; bit++) {
      if (!(bits[bit >> 3] & (0x80 >> (bit % 8)))) continue;
      const x = marker.x + bit % marker.width;
      const y = marker.y + Math.floor(bit / marker.width);
      rgb.fill(foreground, (y * width + x) * 3, (y * width + x) * 3 + 3);
    }
  }
  return { width, height, rgb };
}

test('recognize the actual public network-menu title and completed footer', () => {
  assert.equal(isNetworkMenu(frame()), true);
  assert.equal(isNetworkMenu(frame(fixture.markers, 85)), true);
});

test('a blank screen or partially painted menu does not mean the guest is ready', () => {
  assert.equal(isNetworkMenu(frame([])), false);
  for (const marker of fixture.markers) assert.equal(isNetworkMenu(frame([marker])), false);
});

test('reject another layout or a changed footer instead of guessing readiness', () => {
  const image = frame();
  assert.equal(isNetworkMenu({ ...image, width: 800 }), false);
  const offset = (448 * image.width + 8) * 3;
  image.rgb.fill(255, offset, offset + 3);
  assert.equal(isNetworkMenu(image), false);
});
