import { cameraAvailability, clearCameraFrame, startCamera } from './camera.js';
import { isNetworkMenu } from './boot-screen.js';
import { readBootKernel } from './disk.js';
import { qcode, readPpm } from './display.js';
import { Qmp } from './qmp.js';
import { RELEASE } from './release.js';
import { estimatedBootProgress, fetchAsset, loadingProgress, verifyImage } from './startup.js';

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
const bootProgress = document.querySelector('#boot-progress');
const bootProgressBar = document.querySelector('#boot-progress-bar');
const diagnostics = document.querySelector('#diagnostics');
const aboutDialog = document.querySelector('#about-dialog');
const cameraPanel = document.querySelector('#camera-panel');
const cameraLed = document.querySelector('#camera-led');
const cameraRequest = document.querySelector('#camera-request');
const cameraEnable = document.querySelector('#camera-enable');
const cameraCancel = document.querySelector('#camera-cancel');
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
let cameraUse = false;
let cameraAttempt;
let cameraPause;
let cameraDelivered = false;
let deliveryTimer;

function startGuestBoot() {
  guestBooting = true;
  startup.hidden = true;
  const started = performance.now();
  const tick = () => {
    const seconds = (performance.now() - started) / 1000;
    const value = estimatedBootProgress(seconds);
    const description = value === undefined ? 'Still booting…' : 'Estimated startup progress';
    bootProgressBar.setAttribute('aria-valuetext', `${description} · ${Math.floor(seconds)} s elapsed`);
    if (value === undefined) bootProgressBar.removeAttribute('value');
    else bootProgressBar.value = value;
  };
  document.querySelector('#boot-title').textContent = 'Booting Thunder Den…';
  document.querySelector('#boot-message').textContent = 'A real Linux system with Bitcoin Core’s cryptography, right in your browser.';
  document.querySelector('#boot-estimate').hidden = false;
  bootProgress.hidden = false;
  bootControls.hidden = false;
  bootDetails.disabled = false;
  tick();
  bootTimer = setInterval(tick, 200);
}

function finishGuestBoot(detected) {
  guestBooting = false;
  clearInterval(bootTimer);
  if (detected) {
    bootProgressBar.value = 1;
    bootProgressBar.setAttribute('aria-valuetext', 'Thunder Den is ready');
  }
  bootCover.hidden = true;
  bootControls.hidden = true;
  screen.inert = false;
  screen.dataset.ready = detected ? 'true' : 'manual';
  status.textContent = detected
    ? 'Thunder Den is ready. Click the screen to capture keyboard input.'
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
  // Keep the image's fill, including its initial empty state, between measured updates.
  if (value !== undefined) progress.value = value;
  else if (name !== 'image') progress.removeAttribute('value');
  const elapsed = (performance.now() - Number(row.dataset.started)) / 1000;
  const duration = elapsed < 1 ? `${Math.round(elapsed * 1000)} ms` : `${elapsed.toFixed(1)} s`;
  const message = detail + (done ? ` · ${duration}` : '');
  if (name === 'image') {
    row.querySelector('small').textContent = done ? '100%' : value === undefined ? '' : `${Math.floor(value * 100)}%`;
    progress.setAttribute('aria-valuetext', message);
  } else row.querySelector('small').textContent = message;
}

const mib = bytes => `${Number((bytes / 1024 / 1024).toFixed(1))} MiB`;

function downloadProgress(name, afterDownload) {
  return (loaded, total, done) => {
    const size = total || (name === 'image' ? RELEASE.bytes : done ? loaded : 0);
    if (size) document.querySelector(`#startup-${name} .asset-size`).textContent = ` · ${mib(size)}`;
    if (done) { stage(name, afterDownload); return; }
    const progress = loadingProgress(loaded, size, name === 'image' ? RELEASE.contentBytes : size);
    const detail = progress.finishing ? 'Finishing image…'
      : progress.value === undefined ? 'Loading…' : `${Math.floor(progress.value * 100)}%`;
    stage(name, detail, progress.finishing ? undefined : progress.value, false);
  };
}

function cameraOff() {
  cameraAttempt?.abort();
  cameraAttempt = undefined;
  stopCamera?.();
  stopCamera = undefined;
  clearTimeout(deliveryTimer);
  if (emulator) clearCameraFrame(emulator.FS);
  cameraVideo.hidden = true;
  cameraLed.dataset.active = 'false';
  cameraButton.textContent = 'Enable camera';
  cameraStatus.textContent = 'Camera off.';
}

function cameraError(error) {
  cameraOff();
  cameraPanel.hidden = false;
  const messages = {
    NotAllowedError: 'Camera permission denied. Allow access in your browser and system settings, then try again.',
    NotFoundError: 'No camera was found on this device.',
    NotReadableError: 'The camera could not be opened. It may be busy or blocked by system settings.',
  };
  cameraStatus.textContent = messages[error.name] ?? error.message;
  if (cameraUse) waitForCamera(cameraStatus.textContent).catch(fail);
  else cameraStatus.textContent += ' You can still enter public test recovery words and view public keys.';
}

async function waitForCamera(problem = '') {
  if (!running || !cameraUse) return;
  releaseKeys();
  if (!cameraPause) cameraPause = qmp.command('stop');
  screen.inert = true;
  cameraPanel.hidden = true;
  const opening = cameraRequest.hidden;
  cameraRequest.hidden = false;
  const unavailable = cameraAvailability();
  document.querySelector('#camera-request-title').textContent = problem || unavailable ? 'Camera unavailable' : 'Camera access is needed';
  document.querySelector('#camera-request-message').textContent = problem || unavailable || 'The virtual device needs your camera.';
  document.querySelector('#camera-fallback').hidden = !(problem || unavailable);
  const waiting = document.querySelector('#camera-request-waiting');
  waiting.hidden = !cameraAttempt;
  waiting.textContent = cameraLed.dataset.active === 'true' ? 'Starting camera…' : 'Waiting for browser permission…';
  cameraEnable.hidden = Boolean(unavailable);
  cameraEnable.disabled = Boolean(cameraAttempt);
  cameraEnable.textContent = problem ? 'Try again' : 'Enable camera';
  updateKeyboardState();
  if (opening || problem || (cameraEnable.disabled && document.activeElement === cameraEnable)) {
    (cameraEnable.disabled || cameraEnable.hidden ? cameraCancel : cameraEnable).focus();
  }
  await cameraPause;
}

async function resumeCamera(cancel = false) {
  const paused = cameraPause;
  if (!paused) return;
  await paused;
  if (!running) return;
  const cancelUse = cancel && cameraUse;
  cameraPause = undefined;
  await qmp.command('cont');
  if (!running) return;
  // QMP accepts input events only while the VM is running.
  // Keep the USB device attached: the guest grants camera-node permissions
  // before dropping privileges, so replugged devices cannot be reopened in
  // the same signer process. Use the guest's existing cancel binding instead.
  if (cancelUse) await qmp.command('input-send-event', { events: [key('esc', true), key('esc', false)] });
  cameraRequest.hidden = true;
  screen.inert = false;
  updateKeyboardState();
  screen.focus({ preventScroll: true });
}

function watchCameraDelivery() {
  clearTimeout(deliveryTimer);
  if (!cameraUse || cameraDelivered) return;
  deliveryTimer = setTimeout(() => {
    if (cameraUse && !cameraDelivered) cameraError(new Error('The camera is on, but video delivery to the virtual device is not confirmed. Try again or cancel.'));
  }, 15000);
}

async function cameraEvent(message) {
  if (!running || message.data?.id !== 'cam0') return;
  if (message.event === 'VIDEO_STREAMING') {
    cameraUse = message.data.active;
    cameraDelivered = false;
    clearTimeout(deliveryTimer);
    if (cameraUse) {
      if (!stopCamera) await waitForCamera();
      else watchCameraDelivery();
    } else if (cameraPause) await resumeCamera();
  } else if (message.event === 'VIDEO_FRAME') {
    cameraDelivered = true;
    clearTimeout(deliveryTimer);
  } else if (message.event === 'VIDEO_ERROR') {
    cameraError(new Error('The virtual camera could not deliver video. Try again or cancel.'));
  }
}

async function enableCamera() {
  if (!running || cameraAttempt || stopCamera) return;
  const attempt = new AbortController();
  cameraAttempt = attempt;
  cameraButton.textContent = 'Cancel camera request';
  cameraPanel.hidden = false;
  cameraStatus.textContent = 'Waiting for browser permission…';
  if (cameraUse) await waitForCamera();
  try {
    const stop = await startCamera(emulator.FS, cameraVideo, cameraError, attempt.signal, active => {
      cameraLed.dataset.active = String(active);
      if (active) {
        cameraStatus.textContent = 'Starting camera…';
        document.querySelector('#camera-request-waiting').textContent = 'Starting camera…';
      }
    });
    if (!running || attempt.signal.aborted) { stop(); return; }
    stopCamera = stop;
    cameraPanel.hidden = false;
    cameraVideo.hidden = false;
    cameraButton.textContent = 'Stop camera';
    cameraStatus.textContent = 'Camera on. Virtual camera: 320×240 at 10 fps. Images stay on your device.';
    cameraAttempt = undefined;
    if (cameraPause) await resumeCamera();
    watchCameraDelivery();
  } catch (error) {
    if (!attempt.signal.aborted) cameraError(error);
  } finally {
    if (cameraAttempt === attempt) cameraAttempt = undefined;
    cameraButton.disabled = !running;
  }
}

async function cancelCamera() {
  if (cameraCancel.disabled) return;
  if (cameraUse && !cameraPause) {
    releaseKeys();
    cameraPause = qmp.command('stop');
    screen.inert = true;
  }
  cameraOff();
  cameraPanel.hidden = true;
  cameraCancel.disabled = true;
  try { await resumeCamera(true); }
  finally { cameraCancel.disabled = false; }
}

function fail(error) {
  if (startupFailed) return; // Keep the first failure, not subsequent pending-command errors.
  startupFailed = true;
  cameraUse = false;
  cameraRequest.hidden = true;
  qmp?.close(error);
  guestBooting = false;
  clearInterval(bootTimer);
  bootCover.hidden = false;
  bootControls.hidden = true;
  screen.inert = true;
  screen.dataset.ready = 'false';
  diagnostics.open = true;
  startup.hidden = true;
  bootProgress.hidden = true;
  document.querySelector('#boot-title').textContent = 'The demo stopped';
  document.querySelector('#boot-message').textContent = 'Restart the demo to try again.';
  document.querySelector('#boot-estimate').hidden = true;
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
    status.textContent = 'Loading Thunder Den. Download progress is shown on the screen.';
    const names = ['bios-256k.bin', 'vgabios-stdvga.bin', 'kvmvapic.bin', 'linuxboot_dma.bin'];
    const [{ image, kernel }, wasm, [bios, { default: init }]] = await Promise.all([
      (async () => {
        stage('image', 'Connecting…');
        const response = await fetchAsset('./assets/thunderden.img', {
          signal: startupController.signal,
          onProgress: downloadProgress('image', 'Checking image…'),
        });
        const image = new Uint8Array(await response.arrayBuffer());
        await verifyImage(image, RELEASE.sha256);
        const kernel = readBootKernel(image);
        stage('image', 'Ready', 1);
        return { image, kernel };
      })(),
      (async () => {
        stage('wasm', 'Connecting…');
        const response = await fetchAsset('./emulator/qemu-system-x86_64.wasm', {
          signal: startupController.signal,
          onProgress: downloadProgress('wasm', 'Preparing emulator…'),
        });
        const wasm = await WebAssembly.compileStreaming(response);
        stage('wasm', 'Ready', 1);
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
    status.textContent = 'Preparing emulator…';
    qmp = new Qmp(line => { log.textContent += line + '\n'; }, message => cameraEvent(message).catch(fail));
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
        '-videodev', 'frame-file,id=cam0,path=/camera.yuyv,mode=browser,ready=/camera.ready',
        '-device', 'usb-video,id=camera,bus=ehci.0,videodev=cam0', '-qmp', 'stdio',
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
    status.textContent = 'Booting Thunder Den…';
    refresh(module);
  } catch (error) { fail(error); }
}

cameraButton.addEventListener('click', () => (cameraAttempt || stopCamera ? cancelCamera() : enableCamera()).catch(fail));
cameraEnable.addEventListener('click', () => enableCamera().catch(fail));
cameraCancel.addEventListener('click', () => cancelCamera().catch(fail));
cameraRequest.addEventListener('keydown', event => {
  if (event.key === 'Escape' && !cameraCancel.disabled) {
    event.preventDefault();
    cancelCamera().catch(fail);
  }
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
    // Enter can activate the help card on keydown and release over the canvas.
    if (type === 'keyup' && !pressed.has(code)) return;
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
  keyboardPrompt.hidden = screen.dataset.ready !== 'true' || keyboardUsed || !cameraRequest.hidden;
  screen.tabIndex = keyboardPrompt.hidden ? 0 : -1;
  screen.dataset.keyboard = active ? 'active' : 'released';
  keyboardStatus.textContent = startupFailed ? 'Keyboard unavailable — restart the demo'
    : !cameraRequest.hidden ? 'Camera setup · Choose an option on the screen'
    : !running || screen.inert ? 'Keyboard available after startup'
    : active ? 'Keyboard active · Click outside to release'
    : 'Click the screen to capture keyboard input';
}
screen.addEventListener('focus', updateKeyboardState);
keyboardPrompt.addEventListener('click', () => screen.focus({ preventScroll: true }));
screen.addEventListener('blur', releaseKeys);
window.addEventListener('focus', updateKeyboardState);
window.addEventListener('blur', releaseKeys);
window.addEventListener('pagehide', cameraOff);
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
