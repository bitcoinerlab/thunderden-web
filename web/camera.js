// Emulator-host frames only: no files are created in the Thunderden guest.
export const WIDTH = 640;
export const HEIGHT = 480;
export const FRAME_BYTES = WIDTH * HEIGHT * 2;
export const FRAME_PATH = '/camera.yuyv';

// BT.601 limited-range YUYV, with one chroma pair for every two pixels.
export function rgbaToYuyv(rgba, output = new Uint8Array(rgba.length / 2)) {
  if (rgba.length % 8 !== 0 || output.length !== rgba.length / 2) {
    throw new Error('YUYV requires pairs of RGBA pixels and a matching output buffer');
  }
  for (let i = 0, j = 0; i < rgba.length; i += 8, j += 4) {
    const r = rgba[i] + rgba[i + 4];
    const g = rgba[i + 1] + rgba[i + 5];
    const b = rgba[i + 2] + rgba[i + 6];
    output[j] = ((66 * rgba[i] + 129 * rgba[i + 1] + 25 * rgba[i + 2] + 128) >> 8) + 16;
    output[j + 1] = ((-38 * r - 74 * g + 112 * b + 256) >> 9) + 128;
    output[j + 2] = ((66 * rgba[i + 4] + 129 * rgba[i + 5] + 25 * rgba[i + 6] + 128) >> 8) + 16;
    output[j + 3] = ((112 * r - 94 * g - 18 * b + 256) >> 9) + 128;
  }
  return output;
}

export function publishFrame(fs, frame) {
  if (frame.length !== FRAME_BYTES) {
    throw new Error(`Camera frames must contain ${FRAME_BYTES} bytes of 640x480 YUYV`);
  }
  // Replacement, rather than overwriting an open file, prevents torn frames.
  fs.writeFile(`${FRAME_PATH}.next`, frame);
  fs.rename(`${FRAME_PATH}.next`, FRAME_PATH);
}
