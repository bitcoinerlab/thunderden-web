import assert from 'node:assert/strict';
import test from 'node:test';
import { readBootKernel } from '../web/disk.js';

// Synthetic public FAT32 data, not a bootable image or wallet material.
function fixture() {
  const image = new Uint8Array(8 * 512);
  const view = new DataView(image.buffer);
  view.setUint16(510, 0xaa55, true);
  view.setUint32(454, 1, true);
  view.setUint16(512 + 11, 512, true);
  image[512 + 13] = 1;
  view.setUint16(512 + 14, 1, true);
  image[512 + 16] = 1;
  view.setUint32(512 + 36, 1, true);
  view.setUint32(512 + 44, 2, true);
  view.setUint32(1024 + 2 * 4, 0x0fffffff, true);
  view.setUint32(1024 + 3 * 4, 5, true);
  view.setUint32(1024 + 5 * 4, 0x0fffffff, true);
  image.set(new TextEncoder().encode('BZIMAGE    '), 1536);
  image[1536 + 11] = 0x20;
  view.setUint16(1536 + 26, 3, true);
  view.setUint32(1536 + 28, 700, true);
  const kernel = new Uint8Array(700).fill(42);
  kernel.set(new TextEncoder().encode('HdrS'), 0x202);
  image.set(kernel.subarray(0, 512), 2048);
  image.set(kernel.subarray(512), 3072);
  return { image, kernel, view };
}

test('extract the existing kernel across fragmented FAT clusters without changing the image', () => {
  const { image, kernel } = fixture();
  const original = image.slice();
  assert.deepEqual(readBootKernel(image), kernel);
  assert.deepEqual(image, original);
});

test('reject a missing kernel instead of substituting another payload', () => {
  const { image } = fixture();
  image[1536] = 0;
  assert.throws(() => readBootKernel(image), /no embedded bzImage/);
});

test('reject truncated kernel chains and invalid Linux headers', () => {
  const { image, view } = fixture();
  view.setUint32(1024 + 3 * 4, 0x0fffffff, true);
  assert.throws(() => readBootKernel(image), /truncated embedded Linux/);
  const bad = fixture();
  bad.image[3074] = 0;
  assert.throws(() => readBootKernel(bad.image), /embedded Linux/);
});

test('reject cyclic and out-of-range cluster chains', () => {
  const { image, view } = fixture();
  view.setUint32(1024 + 3 * 4, 3, true);
  assert.throws(() => readBootKernel(image), /boot partition/);
  view.setUint32(1024 + 3 * 4, 12345, true);
  assert.throws(() => readBootKernel(image), /boot partition/);
});

test('reject malformed boot partitions', () => {
  assert.throws(() => readBootKernel(new Uint8Array(4)), /boot partition/);
  const { image, view } = fixture();
  view.setUint32(454, 99999, true);
  assert.throws(() => readBootKernel(image), /boot partition/);
});
