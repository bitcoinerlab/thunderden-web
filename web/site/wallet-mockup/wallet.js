import { renderQr } from '../qr.js';
import { FIXTURE } from './fixture.js';
import { paymentFrames } from './exchange.js';
import { scanReply } from './scanner.js';

// Public BIP39 abandon/about vector, encoded as the standard numeric SeedQR.
renderQr(document.querySelector('#seed-qr'), FIXTURE.seedQr, 'Public 12-word demo SeedQR');
document.querySelector('#demo-words').replaceChildren(...FIXTURE.words.map((word, index) => {
  const item = document.createElement('span');
  const number = document.createElement('b');
  number.textContent = String(index + 1).padStart(2, '0');
  item.append(number, word);
  return item;
}));

const format = value => value.toLocaleString('en-US') + ' sats';
document.querySelector('#payment-amount').textContent = format(FIXTURE.paymentSats);
document.querySelector('#payment-fee').textContent = format(FIXTURE.feeSats);
document.querySelector('#payment-address').textContent = FIXTURE.address;
const frames = paymentFrames();
let animation;
let scanning;
const video = document.querySelector('#reply-video');

function stop() {
  clearInterval(animation);
  scanning?.abort();
  video.srcObject?.getTracks().forEach(track => track.stop());
  video.srcObject = null;
}

function show(step) {
  stop();
  document.body.dataset.step = step;
  for (const name of ['seed', 'payment', 'scan', 'done']) document.querySelector(`#${name}-step`).hidden = name !== step;
  document.querySelector(`#${step}-title`).focus({ preventScroll: true });
  window.scrollTo(0, 0);
  if (step === 'payment') {
    let frame = 0;
    const paint = () => renderQr(document.querySelector('#payment-qr'), frames[frame++ % frames.length], 'Unsigned demo payment QR');
    paint();
    animation = setInterval(paint, 250);
  }
}

async function scan() {
  show('scan');
  const controller = scanning = new AbortController();
  const status = document.querySelector('#scan-status');
  const retry = document.querySelector('#scan-retry');
  const progress = document.querySelector('#reply-progress');
  retry.hidden = true;
  progress.value = 0;
  status.textContent = 'Hold the QR in view until the scan finishes.';
  try {
    await scanReply(video, controller.signal, value => { progress.value = value; });
    if (!controller.signal.aborted) show('done');
  } catch (error) {
    if (controller.signal.aborted) return;
    status.textContent = error.name === 'NotAllowedError' ? 'Allow camera access to scan the reply.'
      : error.name === 'NotFoundError' ? 'No camera found. Try a phone with a camera.' : error.message;
    retry.hidden = false;
  }
}

document.querySelector('#seed-next').addEventListener('click', () => show('payment'));
document.querySelector('#scan-next').addEventListener('click', scan);
document.querySelector('#scan-retry').addEventListener('click', scan);
for (const button of document.querySelectorAll('[data-back]')) button.addEventListener('click', () => show(button.dataset.back));
window.addEventListener('pagehide', stop);
document.addEventListener('visibilitychange', () => {
  if (document.hidden) {
    stop();
    if (document.body.dataset.step === 'scan') {
      document.querySelector('#scan-status').textContent = 'Camera paused.';
      document.querySelector('#scan-retry').hidden = false;
    }
  } else if (document.body.dataset.step === 'payment') {
    show('payment');
  }
});
document.body.dataset.step = 'seed';
