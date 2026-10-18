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

function sharedKernelFixture() {
  const result = fixture();
  const { image, view } = result;
  const file = image.slice(1536, 1568);
  image.fill(0, 1536, 1568);
  for (const [entry, name, first] of [[1536, 'EFI        ', 4], [2560, 'BOOT       ', 6]]) {
    image.set(new TextEncoder().encode(name), entry);
    image[entry + 11] = 0x10;
    view.setUint16(entry + 26, first, true);
    view.setUint32(1024 + first * 4, 0x0fffffff, true);
  }
  image.set(file, 3584);
  image.set(new TextEncoder().encode('BOOTX64 EFI'), 3584);
  return result;
}

test('extract the shared EFI-stub Linux kernel without a separate root bzImage', () => {
  const { image, kernel } = sharedKernelFixture();
  const original = image.slice();
  assert.deepEqual(readBootKernel(image), kernel);
  assert.deepEqual(image, original);
});

test('require real EFI directories and validate the shared Linux payload', () => {
  const notDirectory = sharedKernelFixture();
  notDirectory.image[1536 + 11] = 0x20;
  assert.throws(() => readBootKernel(notDirectory.image), /no embedded/);
  const badKernel = sharedKernelFixture();
  badKernel.image[3074] = 0;
  assert.throws(() => readBootKernel(badKernel.image), /embedded Linux/);
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
