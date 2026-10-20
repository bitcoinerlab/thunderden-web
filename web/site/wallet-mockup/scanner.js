import { decodeQr } from '../../vendor/wallet.js';
import { SignedReply } from './exchange.js';

export async function scanReply(video, signal, onProgress) {
  let stream;
  try {
    if (!navigator.mediaDevices?.getUserMedia) throw new Error('Camera scanning needs HTTPS and camera access.');
    stream = await navigator.mediaDevices.getUserMedia({ audio: false, video: {
      facingMode: { ideal: 'environment' }, width: { ideal: 640 }, height: { ideal: 480 }, frameRate: { ideal: 10 },
    } });
    signal.throwIfAborted();
    const stop = () => stream.getTracks().forEach(track => track.stop());
    signal.addEventListener('abort', stop, { once: true });
    try {
      video.srcObject = stream;
      await video.play();
      signal.throwIfAborted();
      const canvas = document.createElement('canvas');
      const context = canvas.getContext('2d', { willReadFrequently: true });
      const receiver = new SignedReply();
      while (!signal.aborted) {
        if (!stream.active) throw new Error('Camera stopped. Try again.');
        if (video.readyState >= 2) {
          canvas.width = Math.min(640, video.videoWidth);
          canvas.height = Math.round(canvas.width * video.videoHeight / video.videoWidth);
          context.drawImage(video, 0, 0, canvas.width, canvas.height);
          const image = context.getImageData(0, 0, canvas.width, canvas.height);
          const code = decodeQr(image.data, image.width, image.height, { inversionAttempts: 'dontInvert' });
          if (code) {
            const result = receiver.receive(code.data);
            if (result.complete) return;
            onProgress(result.progress);
          }
        }
        await new Promise(resolve => setTimeout(resolve, 100));
      }
      signal.throwIfAborted();
    } finally {
      signal.removeEventListener('abort', stop);
    }
  } finally {
    stream?.getTracks().forEach(track => track.stop());
    if (video.srcObject === stream) video.srcObject = null;
  }
}
