import { createHash } from 'node:crypto';
import { copyFile, mkdir, readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { RELEASE } from '../web/release.js';

const root = new URL('../', import.meta.url);
const source = new URL('../thunderden-qemu-wasm/build/thunderden-wasm/emulator/', root);
const destination = new URL('web/emulator/', root);

try {
  await mkdir(destination, { recursive: true });
  for (const name of [
    'qemu-system-x86_64.js', 'qemu-system-x86_64.wasm', 'qemu-system-x86_64.worker.js',
    'bios-256k.bin', 'vgabios-stdvga.bin', 'kvmvapic.bin', 'linuxboot_dma.bin',
  ]) {
    try {
      await copyFile(new URL(name, source), new URL(name, destination));
    } catch (error) {
      if (error.code === 'ENOENT') {
        throw new Error(`Build the sibling thunderden-qemu-wasm repository first. Missing ${fileURLToPath(new URL(name, source))}`);
      }
      throw error;
    }
  }

  const imagePath = new URL('web/assets/thunderden.img', root);
  let bytes;
  if (process.argv[2]) {
    bytes = await readFile(process.argv[2]);
  } else {
    try {
      bytes = await readFile(imagePath);
    } catch (error) {
      if (error.code !== 'ENOENT') throw error;
      console.log(`Downloading the unchanged ${RELEASE.tag} image (64 MiB)…`);
      const response = await fetch(RELEASE.url, { signal: AbortSignal.timeout(120000) });
      if (!response.ok) throw new Error(`Image download returned HTTP ${response.status}`);
      bytes = new Uint8Array(await response.arrayBuffer());
    }
  }
  if (createHash('sha256').update(bytes).digest('hex') !== RELEASE.sha256) {
    throw new Error('Image checksum mismatch. Only the pinned, unchanged preview.8 release is accepted.');
  }
  if (bytes.length !== RELEASE.bytes || bytes.findLastIndex(byte => byte !== 0) + 1 !== RELEASE.contentBytes) {
    throw new Error('Pinned image progress metadata does not match the verified image.');
  }
  await mkdir(new URL('web/assets/', root), { recursive: true });
  await writeFile(imagePath, bytes);
  console.log('Emulator assets copied and Thunderden image checksum verified. Run: npm start');
} catch (error) {
  console.error(error.message);
  process.exitCode = 1;
}
