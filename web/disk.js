// Read the existing Linux kernel from the verified image's FAT32 boot partition.
// No disk bytes are changed and no extra kernel or initramfs is supplied.
export function readBootKernel(image) {
  const invalid = () => new Error('Invalid release boot partition');
  if (image.length < 1024) throw invalid();
  const view = new DataView(image.buffer, image.byteOffset, image.byteLength);
  if (view.getUint16(510, true) !== 0xaa55) throw invalid();
  const volume = view.getUint32(454, true) * 512;
  if (volume + 512 > image.length) throw invalid();
  const sector = view.getUint16(volume + 11, true);
  const clusterBytes = sector * image[volume + 13];
  const reserved = view.getUint16(volume + 14, true);
  const fats = image[volume + 16];
  const fatBytes = sector * view.getUint32(volume + 36, true);
  const fat = volume + reserved * sector;
  const data = fat + fats * fatBytes;
  if (sector !== 512 || !clusterBytes || !reserved || !fats || !fatBytes || data >= image.length) throw invalid();

  function* clusters(first) {
    const seen = new Set();
    for (let cluster = first; cluster < 0x0ffffff8;) {
      const offset = data + (cluster - 2) * clusterBytes;
      if (cluster < 2 || seen.has(cluster) || (cluster + 1) * 4 > fatBytes
          || offset + clusterBytes > image.length) throw invalid();
      seen.add(cluster);
      yield offset;
      cluster = view.getUint32(fat + cluster * 4, true) & 0x0fffffff;
    }
  }

  function find(first, name, directory = false) {
    for (const offset of clusters(first)) {
      for (let entry = offset; entry < offset + clusterBytes; entry += 32) {
        if (image[entry] === 0) return;
        const attributes = image[entry + 11];
        if (image[entry] === 0xe5 || attributes & 0x08 || Boolean(attributes & 0x10) !== directory) continue;
        if (new TextDecoder().decode(image.subarray(entry, entry + 11)) !== name) continue;
        return { first: view.getUint16(entry + 20, true) * 65536 + view.getUint16(entry + 26, true),
          size: view.getUint32(entry + 28, true) };
      }
    }
  }

  const root = view.getUint32(volume + 44, true);
  let file = find(root, 'BZIMAGE    ');
  if (!file) {
    // New images share this EFI-stub Linux kernel between BIOS and UEFI boot.
    const efi = find(root, 'EFI        ', true);
    const boot = efi && find(efi.first, 'BOOT       ', true);
    file = boot && find(boot.first, 'BOOTX64 EFI');
  }
  if (!file) throw new Error('Release image has no embedded bzImage/EFI Linux kernel');
  const { first, size } = file;
  if (size < 0x206 || size > image.length) throw invalid();
  const kernel = new Uint8Array(size);
  let copied = 0;
  for (const offset of clusters(first)) {
    const length = Math.min(clusterBytes, size - copied);
    kernel.set(image.subarray(offset, offset + length), copied);
    copied += length;
    if (copied === size) break;
  }
  if (copied !== size || new DataView(kernel.buffer).getUint32(0x202, true) !== 0x53726448) {
    throw new Error('Invalid or truncated embedded Linux kernel');
  }
  return kernel;
}
