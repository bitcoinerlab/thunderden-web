import { clearCameraFrame, startCamera } from './camera.js';
import { qcode, readPpm } from './display.js';
import { Qmp } from './qmp.js';
import { RELEASE } from './release.js';

const screen = document.querySelector('#screen');
const context = screen.getContext('2d');
const status = document.querySelector('#status');
const boot = document.querySelector('#boot');
const restart = document.querySelector('#restart');
const log = document.querySelector('#log');
const cameraButton = document.querySelector('#camera');
const cameraStatus = document.querySelector('#camera-status');
const cameraVideo = document.querySelector('#camera-video');
const pressed = new Set();
let qmp;
let running = false;
let pixels;
let emulator;
let stopCamera;

function cameraOff() {
  stopCamera?.();
  stopCamera = undefined;
  cameraVideo.hidden = true;
  cameraButton.textContent = 'Enable camera';
  cameraStatus.textContent = 'Camera off.';
}

function cameraError(error) {
  cameraOff();
  const messages = {
    NotAllowedError: 'Camera permission denied. Allow camera access for this site in your browser and OS settings, then retry.',
    NotFoundError: 'No camera found.',
    NotReadableError: 'Camera is busy or blocked by the OS. Close other camera apps and retry.',
  };
  cameraStatus.textContent = messages[error.name] ?? `Camera error: ${error.message}`;
}

function fail(error) {
  running = false;
  cameraOff();
  cameraButton.disabled = true;
  status.textContent = `Stopped: ${error.message ?? error}. See emulator diagnostics below. Restart to try again.`;
  log.textContent += String(error.message ?? error) + '\n';
  restart.disabled = false;
}

async function load(path) {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`Cannot load ${path}. Run npm run setup first.`);
  return new Uint8Array(await response.arrayBuffer());
}

async function refresh(module) {
  if (!running) return;
  try {
    await qmp.command('screendump', { filename: '/screen.ppm' });
    const { width, height, rgb } = readPpm(module.FS.readFile('/screen.ppm'));
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
    screen.dataset.frames = String(Number(screen.dataset.frames ?? 0) + 1);
    setTimeout(() => refresh(module), 500);
  } catch (error) { fail(error); }
}

boot.addEventListener('click', async () => {
  boot.disabled = true;
  restart.disabled = false;
  try {
    if (!crossOriginIsolated) throw new Error('Shared memory requires COOP/COEP headers. Use npm start and open localhost.');
    status.textContent = 'Loading emulator and checking the original 64 MiB Thunderden image…';
    const names = ['bios-256k.bin', 'vgabios-stdvga.bin', 'kvmvapic.bin', 'linuxboot_dma.bin'];
    const [image, bios, { default: init }] = await Promise.all([
      load('./assets/thunderden.img'),
      Promise.all(names.map(async name => [name, await load('./emulator/' + name)])),
      import('./emulator/qemu-system-x86_64.js'),
    ]);
    const digest = new Uint8Array(await crypto.subtle.digest('SHA-256', image));
    const hash = [...digest].map(byte => byte.toString(16).padStart(2, '0')).join('');
    if (hash !== RELEASE.sha256) throw new Error('Thunderden image checksum mismatch');
    status.textContent = 'Starting x86-64 emulator…';
    qmp = new Qmp(line => { log.textContent += line + '\n'; });
    const module = await init({
      pty: qmp.pty,
      mainScriptUrlOrBlob: new URL('./emulator/qemu-system-x86_64.js', import.meta.url).href,
      arguments: [
        '-m', '1024', '-smp', '1', '-cpu', 'qemu64', '-accel', 'tcg,tb-size=128',
        '-L', '/bios', '-display', 'none', '-S', '-nic', 'none', '-no-reboot',
        '-drive', 'file=/thunderden.img,format=raw,if=virtio,readonly=on',
        '-vga', 'none', '-device', 'VGA,xres=1280,yres=800',
        // EHCI passed guest camera scanning in Wasm; xHCI timed out.
        '-device', 'virtio-rng-pci', '-device', 'usb-ehci,id=ehci',
        '-videodev', 'frame-file,id=cam0,path=/camera.yuyv',
        '-device', 'usb-video,bus=ehci.0,videodev=cam0', '-qmp', 'stdio',
      ],
      preRun: [instance => {
        instance.FS.mkdir('/bios');
        for (const [name, bytes] of bios) instance.FS.writeFile('/bios/' + name, bytes);
        instance.FS.writeFile('/thunderden.img', image);
        clearCameraFrame(instance.FS);
      }],
      print: line => { log.textContent += line + '\n'; },
      printErr: line => { log.textContent += line + '\n'; },
      onAbort: error => fail(new Error(String(error))),
    });
    await Promise.race([
      qmp.greeting,
      new Promise((_, reject) => setTimeout(() => reject(new Error('Emulator startup timed out')), 30000)),
    ]);
    await qmp.command('qmp_capabilities');
    running = true;
    emulator = module;
    cameraButton.disabled = false;
    status.textContent = `Booting unchanged Thunderden ${RELEASE.tag}. Click the screen to use the keyboard; boot can take several minutes.`;
    screen.focus();
    await qmp.command('cont');
    refresh(module);
  } catch (error) { fail(error); }
});

cameraButton.addEventListener('click', async () => {
  if (stopCamera) {
    cameraOff();
    screen.focus();
    return;
  }
  cameraButton.disabled = true;
  cameraStatus.textContent = 'Requesting camera permission…';
  try {
    const stop = await startCamera(emulator.FS, cameraVideo, cameraError);
    if (!running) { stop(); return; }
    stopCamera = stop;
    cameraVideo.hidden = false;
    cameraButton.textContent = 'Stop camera';
    cameraStatus.textContent = 'Camera on. Frames stay in this browser; choose Scan a QR code in Thunderden.';
    screen.focus();
  } catch (error) { cameraError(error); }
  finally { cameraButton.disabled = !running; }
});

function key(code, down) {
  return { type: 'key', data: { down, key: { type: 'qcode', data: code } } };
}

for (const type of ['keydown', 'keyup']) {
  screen.addEventListener(type, event => {
    const code = qcode(event.code);
    if (!running || !code) return;
    event.preventDefault();
    if (event.repeat) return;
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
}
screen.addEventListener('blur', releaseKeys);
window.addEventListener('blur', releaseKeys);
restart.addEventListener('click', () => location.reload());
