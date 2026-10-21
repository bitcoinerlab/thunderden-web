import { createHash } from 'node:crypto';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { readBootKernel } from '../web/disk.js';
import { RELEASE } from '../web/site/release.js';

try {
  let image;
  if (process.argv[2]) image = await readFile(process.argv[2]);
  else {
    if (!RELEASE.url) throw new Error('The pinned website test image is not published. Use npm run setup:site -- /path/to/thunderden.img');
    console.log(`Downloading the unchanged ${RELEASE.tag} website image...`);
    const response = await fetch(RELEASE.url, { signal: AbortSignal.timeout(120000) });
    if (!response.ok) throw new Error(`Image download returned HTTP ${response.status}`);
    image = Buffer.from(await response.arrayBuffer());
  }
  if (createHash('sha256').update(image).digest('hex') !== RELEASE.sha256) {
    throw new Error('Image checksum does not match the pinned website image.');
  }
  if (image.length !== RELEASE.bytes || image.findLastIndex(byte => byte !== 0) + 1 !== RELEASE.contentBytes) {
    throw new Error('Image size does not match the pinned loading metadata.');
  }
  readBootKernel(image);
  const directory = new URL('../web/assets/site/', import.meta.url);
  await mkdir(directory, { recursive: true });
  await writeFile(new URL('thunderden.img', directory), image);
  console.log('Unchanged website demo image verified and copied. Run npm start and open http://127.0.0.1:4173/site/');
} catch (error) {
  console.error(error.message);
  process.exitCode = 1;
}
