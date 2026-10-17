import { clearCameraFrame, startCamera } from './camera.js';
import { isNetworkMenu } from './boot-screen.js';
import { readBootKernel } from './disk.js';
import { qcode, readPpm } from './display.js';
import { Qmp } from './qmp.js';
import { RELEASE } from './release.js';
import { fetchAsset, verifyImage } from './startup.js';

const screen = document.querySelector('#screen');
const context = screen.getContext('2d');
const status = document.querySelector('#status');
const restart = document.querySelector('#restart');
const log = document.querySelector('#log');
const cameraButton = document.querySelector('#camera');
const cameraStatus = document.querySelector('#camera-status');
const cameraVideo = document.querySelector('#camera-video');
const startup = document.querySelector('#startup');
const bootCover = document.querySelector('#boot-cover');
const bootControls = document.querySelector('#boot-controls');
const bootDetails = document.querySelector('#boot-details');
const bootElapsed = document.querySelector('#boot-elapsed');
const diagnostics = document.querySelector('#diagnostics');
const aboutDialog = document.querySelector('#about-dialog');
const cameraPanel = document.querySelector('#camera-panel');
const cameraLed = document.querySelector('#camera-led');
const keyboardGuide = document.querySelector('#keyboard-guide');
const keyboardStatus = document.querySelector('#keyboard-status');
const keyboardPrompt = document.querySelector('#keyboard-prompt');
const pressed = new Set();
let qmp;
let running = false;
let pixels;
let emulator;
let stopCamera;
let startupController;
let startupFailed = false;
let guestBooting = false;
let bootTimer;
let menuFrames = 0;
let keyboardUsed = false;

function startGuestBoot() {
  guestBooting = true;
  startup.hidden = true;
  const started = performance.now();
  const tick = () => { bootElapsed.textContent = `${Math.floor((performance.now() - started) / 1000)} s elapsed`; };
  document.querySelector('#boot-title').textContent = 'Starting Thunderden…';
  document.querySelector('#boot-message').textContent = 'The original software is starting locally in your browser.';
  document.querySelector('#boot-estimate').hidden = false;
  bootElapsed.hidden = false;
  bootControls.hidden = false;
  bootDetails.disabled = false;
  tick();
  bootTimer = setInterval(tick, 1000);
}

function finishGuestBoot(detected) {
  guestBooting = false;
  clearInterval(bootTimer);
  bootCover.hidden = true;
  bootControls.hidden = true;
  screen.inert = false;
  screen.dataset.ready = detected ? 'true' : 'manual';
  status.textContent = detected
    ? 'Thunderden is ready. Click the screen to use the keyboard.'
    : 'Showing the virtual device. Guest boot may still be in progress.';
  updateKeyboardState();
}

bootDetails.addEventListener('click', () => {
  const showDetails = !bootCover.hidden;
  bootCover.hidden = showDetails;
  screen.inert = !showDetails;
  bootDetails.textContent = showDetails ? 'Hide boot details' : 'Show boot details';
  bootDetails.setAttribute('aria-expanded', String(showDetails));
  diagnostics.open = showDetails;
  updateKeyboardState();
});

function stage(name, detail, value, done = value === 1) {
  if (startupFailed) return;
  const row = document.querySelector(`#startup-${name}`);
  const progress = row.querySelector('progress');
  row.dataset.started ??= String(performance.now());
  row.dataset.state = done ? 'done' : 'active';
  if (value === undefined) progress.removeAttribute('value');
  else progress.value = value;
  const elapsed = (performance.now() - Number(row.dataset.started)) / 1000;
  const duration = elapsed < 1 ? `${Math.round(elapsed * 1000)} ms` : `${elapsed.toFixed(1)} s`;
  row.querySelector('small').textContent = detail + (done ? ` · ${duration}` : '');
}

const mib = bytes => `${(bytes / 1024 / 1024).toFixed(1)} MiB`;

function downloadProgress(name, afterDownload) {
  return (loaded, total, done) => {
    if (done) { stage(name, afterDownload); return; }
    const fraction = total ? Math.min(loaded / total, 1) : undefined;
    const detail = total
      ? `${mib(loaded)} / ${mib(total)} unpacked · ${Math.floor(fraction * 100)}%`
      : `${mib(loaded)} unpacked`;
    stage(name, detail, fraction, false);
  };
}

function cameraOff() {
  stopCamera?.();
  stopCamera = undefined;
  cameraVideo.hidden = true;
  cameraLed.dataset.active = 'false';
  cameraButton.textContent = 'Enable camera';
  cameraStatus.textContent = 'Camera off.';
}

function cameraError(error) {
  cameraOff();
  cameraPanel.hidden = false;
  const messages = {
    NotAllowedError: 'Camera permission denied. Allow camera access for this site in your browser and OS settings, then retry.',
    NotFoundError: 'No camera found.',
    NotReadableError: 'Camera is busy or blocked by the OS. Close other camera apps and retry.',
  };
  cameraStatus.textContent = messages[error.name] ?? `Camera error: ${error.message}`;
}

function fail(error) {
  if (startupFailed) return; // Keep the first failure, not subsequent pending-command errors.
  startupFailed = true;
  qmp?.close(error);
  guestBooting = false;
  clearInterval(bootTimer);
  bootCover.hidden = false;
  bootControls.hidden = true;
  screen.inert = true;
  screen.dataset.ready = 'false';
  diagnostics.open = true;
  startup.hidden = true;
  keyboardGuide.hidden = true;
  document.querySelector('.boot-spinner').hidden = true;
  document.querySelector('#boot-title').textContent = 'Virtual device stopped';
  document.querySelector('#boot-message').textContent = 'Restart the demo to try again.';
  document.querySelector('#boot-estimate').hidden = true;
  bootElapsed.hidden = true;
  const errorMessage = document.querySelector('#boot-error');
  errorMessage.textContent = String(error.message ?? error);
  errorMessage.hidden = false;
  document.querySelector('#retry').hidden = false;
  document.querySelector('#boot-diagnostics').hidden = false;
  startupController?.abort();
  for (const row of startup.querySelectorAll('[data-state="active"]')) {
    row.dataset.state = 'error';
    row.querySelector('progress').value = 0;
    row.querySelector('small').textContent = 'Stopped — see the on-screen error.';
  }
  running = false;
  updateKeyboardState();
  cameraOff();
  cameraButton.disabled = true;
  status.textContent = `Stopped: ${error.message ?? error}. Open About for emulator diagnostics. Restart to try again.`;
  qmp?.flush(); // Preserve a final diagnostic even if the emulator omitted its newline.
  log.textContent += String(error.message ?? error) + '\n';
  restart.disabled = false;
}

async function load(path) {
  const response = await fetch(path, { signal: startupController.signal });
  if (!response.ok) throw new Error(`Cannot load ${path}. Run npm run setup first.`);
  return new Uint8Array(await response.arrayBuffer());
}

async function refresh(module) {
  if (!running) return;
  try {
    await qmp.command('screendump', { filename: '/screen.ppm' });
    const frame = readPpm(module.FS.readFile('/screen.ppm'));
    const { width, height, rgb } = frame;
    if (!pixels || pixels.width !== width || pixels.height !== height) {
      screen.width = width;
      screen.height = height;
      pixels = context.createImageData(width, height);
      pixels.data.fill(255);
    }
    for (let i = 0, j = 0; i < pixels.data.length; i += 4, j += 3) {
      pixels.data[i] = rgb[j];
      pixels.data[i + 1] = rgb[j + 1];
      pixels.data[i + 2] = rgb[j + 2];
    }
    context.putImageData(pixels, 0, 0);
    if (guestBooting) {
      menuFrames = isNetworkMenu(frame) ? menuFrames + 1 : 0;
      if (menuFrames >= 2) finishGuestBoot(true);
    }
    screen.dataset.frames = String(Number(screen.dataset.frames ?? 0) + 1);
    // Wait after completion so slow dumps cannot build a queue of stale screens.
    setTimeout(() => refresh(module), 33);
  } catch (error) { fail(error); }
}

async function start() {
  restart.disabled = false;
  try {
    if (!crossOriginIsolated) throw new Error('Shared memory requires COOP/COEP headers. Use npm start and open localhost.');
    startup.hidden = false;
    bootCover.hidden = false;
    startupController = new AbortController();
    status.textContent = 'Preparing files in parallel. Progress and timings are shown on the virtual screen.';
    const names = ['bios-256k.bin', 'vgabios-stdvga.bin', 'kvmvapic.bin', 'linuxboot_dma.bin'];
    const [{ image, kernel }, wasm, [bios, { default: init }]] = await Promise.all([
      (async () => {
        stage('image', 'Connecting…');
        const response = await fetchAsset('./assets/thunderden.img', {
          signal: startupController.signal,
          onProgress: downloadProgress('image', 'Finishing image preparation…'),
        });
        const image = new Uint8Array(await response.arrayBuffer());
        stage('image', `${mib(image.length)} original image ready`, 1);
        await verifyImage(image, RELEASE.sha256);
        const kernel = readBootKernel(image);
        return { image, kernel };
      })(),
      (async () => {
        stage('wasm', 'Connecting…');
        const response = await fetchAsset('./emulator/qemu-system-x86_64.wasm', {
          signal: startupController.signal,
          onProgress: downloadProgress('wasm', 'Finishing WebAssembly compilation…'),
        });
        const wasm = await WebAssembly.compileStreaming(response);
        stage('wasm', 'Emulator downloaded and compiled', 1);
        return wasm;
      })(),
      (async () => {
        const support = await Promise.all([
          Promise.all(names.map(async name => [name, await load('./emulator/' + name)])),
          import('./emulator/qemu-system-x86_64.js'),
        ]);
        return support;
      })(),
    ]);
    status.textContent = 'Starting x86-64 emulator…';
    qmp = new Qmp(line => { log.textContent += line + '\n'; });
    let rejectInstantiation;
    const instantiationFailed = new Promise((_, reject) => { rejectInstantiation = reject; });
    const initialized = init({
      instantiateWasm(imports, receiveInstance) {
        WebAssembly.instantiate(wasm, imports)
          .then(instance => receiveInstance(instance, wasm)).catch(rejectInstantiation);
        return {}; // Emscripten is notified asynchronously by receiveInstance.
      },
      pty: qmp.pty,
      mainScriptUrlOrBlob: new URL('./emulator/qemu-system-x86_64.js', import.meta.url).href,
      arguments: [
        '-m', '1024', '-smp', '1', '-cpu', 'qemu64', '-accel', 'tcg,tb-size=128',
        '-L', '/bios', '-display', 'none', '-S', '-nic', 'none', '-no-reboot',
        // Direct boot of the original kernel skips GRUB; no extra initramfs.
        '-kernel', '/thunderden-kernel',
        '-append', 'console=tty1 quiet loglevel=3 acpi=off random.trust_cpu=off random.trust_bootloader=off',
        '-no-acpi',
        '-drive', 'file=/thunderden.img,format=raw,if=virtio,readonly=on',
        '-vga', 'none', '-device', 'VGA,xres=640,yres=480',
        // EHCI passed guest camera scanning in Wasm; xHCI timed out.
        '-device', 'virtio-rng-pci', '-device', 'usb-ehci,id=ehci',
        '-videodev', 'frame-file,id=cam0,path=/camera.yuyv,mode=browser',
        '-device', 'usb-video,bus=ehci.0,videodev=cam0', '-qmp', 'stdio',
      ],
      preRun: [instance => {
        instance.FS.mkdir('/bios');
        for (const [name, bytes] of bios) instance.FS.writeFile('/bios/' + name, bytes);
        instance.FS.writeFile('/thunderden.img', image);
        instance.FS.writeFile('/thunderden-kernel', kernel);
        clearCameraFrame(instance.FS);
      }],
      print: line => { log.textContent += line + '\n'; },
      printErr: line => { log.textContent += line + '\n'; },
      onAbort: error => fail(new Error(String(error))),
      onExit: code => fail(new Error(`Emulator exited with status ${code}`)),
    });
    const module = await Promise.race([initialized, instantiationFailed]);
    await Promise.race([
      qmp.greeting,
      new Promise((_, reject) => setTimeout(() => reject(new Error('Emulator startup timed out')), 30000)),
    ]);
    await qmp.command('qmp_capabilities');
    running = true;
    emulator = module;
    cameraButton.disabled = false;
    startGuestBoot();
    await qmp.command('cont');
    status.textContent = 'Starting your virtual Thunderden…';
    refresh(module);
  } catch (error) { fail(error); }
}

cameraButton.addEventListener('click', async () => {
  if (stopCamera) {
    cameraOff();
    cameraPanel.hidden = true;
    return;
  }
  cameraButton.disabled = true;
  cameraPanel.hidden = false;
  cameraStatus.textContent = 'Requesting camera permission…';
  try {
    const stop = await startCamera(emulator.FS, cameraVideo, cameraError);
    if (!running) { stop(); return; }
    stopCamera = stop;
    cameraLed.dataset.active = 'true';
    cameraVideo.hidden = false;
    cameraButton.textContent = 'Stop camera';
    cameraStatus.textContent = 'Camera on. Virtual camera: 320×240 at 10 fps. Frames stay in this browser; choose Scan a QR code in Thunderden.';
  } catch (error) { cameraError(error); }
  finally { cameraButton.disabled = !running; }
});

function key(code, down) {
  return { type: 'key', data: { down, key: { type: 'qcode', data: code } } };
}

for (const type of ['keydown', 'keyup']) {
  screen.addEventListener(type, event => {
    const code = qcode(event.code);
    if (!running || screen.inert || !code) return;
    event.preventDefault();
    if (event.repeat) return;
    // A user inspecting the raw display can take control even if recognition fails.
    if (type === 'keydown' && guestBooting && bootCover.hidden) finishGuestBoot(false);
    if (type === 'keydown') pressed.add(code);
    else pressed.delete(code);
    qmp.command('input-send-event', { events: [key(code, type === 'keydown')] }).catch(fail);
  });
}
function releaseKeys() {
  if (running && pressed.size) {
    qmp.command('input-send-event', { events: [...pressed].map(code => key(code, false)) }).catch(fail);
  }
  pressed.clear();
  updateKeyboardState();
}
function updateKeyboardState() {
  const active = running && !screen.inert && document.activeElement === screen && document.hasFocus();
  if (active) keyboardUsed = true;
  keyboardPrompt.hidden = screen.dataset.ready !== 'true' || keyboardUsed;
  screen.dataset.keyboard = active ? 'active' : 'released';
  keyboardStatus.textContent = startupFailed ? 'Keyboard unavailable — restart the demo'
    : !running || screen.inert ? 'Keyboard available after startup'
    : active ? 'Keyboard active · Click outside to release'
    : 'Click the screen to use your keyboard';
}
screen.addEventListener('focus', updateKeyboardState);
keyboardPrompt.addEventListener('click', () => screen.focus({ preventScroll: true }));
screen.addEventListener('blur', releaseKeys);
window.addEventListener('focus', updateKeyboardState);
window.addEventListener('blur', releaseKeys);
document.addEventListener('pointerdown', event => {
  if (event.target !== screen && document.activeElement === screen) screen.blur();
});
restart.addEventListener('click', () => location.reload());
document.querySelector('#retry').addEventListener('click', () => location.reload());
document.querySelector('#about').addEventListener('click', () => aboutDialog.showModal());
document.querySelector('#boot-diagnostics').addEventListener('click', () => {
  diagnostics.open = true;
  aboutDialog.showModal();
  diagnostics.scrollIntoView({ block: 'nearest' });
});
document.querySelector('#camera-close').addEventListener('click', () => {
  cameraPanel.hidden = true;
});

start();
