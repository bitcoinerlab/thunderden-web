// Emulator-host frames only: no files are created in the Thunderden guest.
export const WIDTH = 320;
export const HEIGHT = 240;
export const FRAME_BYTES = WIDTH * HEIGHT * 2;
export const FRAME_PATH = '/camera.yuyv';
export const READY_PATH = '/camera.ready';

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
    throw new Error(`Camera frames must contain ${FRAME_BYTES} bytes of ${WIDTH}x${HEIGHT} YUYV`);
  }
  // Replacement, rather than overwriting an open file, prevents torn frames.
  fs.writeFile(`${FRAME_PATH}.next`, frame);
  fs.rename(`${FRAME_PATH}.next`, FRAME_PATH);
}

export function clearCameraFrame(fs) {
  fs.writeFile(READY_PATH, Uint8Array.of(0));
  const frame = new Uint8Array(FRAME_BYTES).fill(128);
  for (let i = 0; i < frame.length; i += 2) frame[i] = 16;
  publishFrame(fs, frame);
}

export function cameraAvailability() {
  if (!globalThis.isSecureContext) return 'Camera access needs HTTPS or localhost.';
  if (!navigator.mediaDevices?.getUserMedia) return 'This browser cannot provide camera access.';
  return '';
}

export async function requestCamera(signal) {
  const unavailable = cameraAvailability();
  if (unavailable) throw new Error(unavailable);
  signal?.throwIfAborted();
  const pending = navigator.mediaDevices.getUserMedia({
    audio: false,
    video: { width: { ideal: WIDTH }, height: { ideal: HEIGHT },
      aspectRatio: { ideal: WIDTH / HEIGHT }, frameRate: { ideal: 10 }, facingMode: { ideal: 'environment' } },
  });
  return new Promise((resolve, reject) => {
    const cancelled = () => reject(new DOMException('Camera request cancelled', 'AbortError'));
    signal?.addEventListener('abort', cancelled, { once: true });
    pending.then(stream => {
      signal?.removeEventListener('abort', cancelled);
      if (signal?.aborted) {
        for (const track of stream.getTracks()) track.stop();
        cancelled();
      } else resolve(stream);
    }, error => {
      signal?.removeEventListener('abort', cancelled);
      reject(error);
    });
    if (signal?.aborted) cancelled();
  });
}

// Capture the local camera through the browser's media API.
// Pixels stay in the browser and enter the emulator through its host filesystem.
export async function startCamera(fs, video, onError, signal, onActive = () => {}) {
  const stream = await requestCamera(signal);
  const canvas = document.createElement('canvas');
  canvas.width = WIDTH;
  canvas.height = HEIGHT;
  const context = canvas.getContext('2d', { willReadFrequently: true });
  const output = new Uint8Array(FRAME_BYTES);
  let timer;
  let startupTimer;
  let cancelStartup;
  let stopped = false;

  function stop() {
    if (stopped) return;
    stopped = true;
    clearTimeout(timer);
    clearTimeout(startupTimer);
    cancelStartup?.();
    window.removeEventListener('pagehide', stop);
    signal?.removeEventListener('abort', stop);
    for (const track of stream.getTracks()) {
      track.removeEventListener('ended', disconnected);
      track.stop();
    }
    video.pause();
    video.srcObject = null;
    clearCameraFrame(fs); // Replace the latest host frame instead of retaining its QR.
    onActive(false);
  }

  function disconnected() {
    stop();
    onError(new Error('Camera disconnected. Reconnect it and enable the camera again.'));
  }

  function capture() {
    if (video.readyState < 2 || !video.videoWidth || !video.videoHeight) return false;
    const scale = Math.min(WIDTH / video.videoWidth, HEIGHT / video.videoHeight);
    const width = video.videoWidth * scale;
    const height = video.videoHeight * scale;
    context.fillStyle = '#000';
    context.fillRect(0, 0, WIDTH, HEIGHT);
    context.drawImage(video, (WIDTH - width) / 2, (HEIGHT - height) / 2, width, height);
    rgbaToYuyv(context.getImageData(0, 0, WIDTH, HEIGHT).data, output);
    publishFrame(fs, output);
    return true;
  }

  function tick() {
    if (stopped) return;
    try {
      capture();
      timer = setTimeout(tick, 100);
    } catch (error) {
      stop();
      onError(error);
    }
  }

  try {
    signal?.throwIfAborted();
    for (const track of stream.getVideoTracks()) track.addEventListener('ended', disconnected);
    window.addEventListener('pagehide', stop);
    signal?.addEventListener('abort', stop, { once: true });
    video.muted = true;
    video.srcObject = stream;
    onActive(true);
    await Promise.race([video.play(), new Promise((_, reject) => {
      cancelStartup = () => reject(new DOMException('Camera request cancelled', 'AbortError'));
      startupTimer = setTimeout(() => reject(new Error('The camera has not provided an image. Try again.')), 10000);
    })]);
    cancelStartup = undefined;
    clearTimeout(startupTimer);
    if (stopped) throw new Error('Camera stopped during startup. Try enabling it again.');
    if (!capture()) throw new Error('The camera has not provided an image. Try again.');
    fs.writeFile(READY_PATH, Uint8Array.of(1));
    timer = setTimeout(tick, 100);
    return stop;
  } catch (error) {
    stop();
    throw error;
  }
}
