// HTTP handles compression and caching. Fetch exposes the decoded file bytes.
export function loadingProgress(loaded, total, contentBytes = total) {
  return {
    value: contentBytes ? Math.min(loaded / contentBytes, 1) : undefined,
    finishing: Boolean(contentBytes && contentBytes < total && loaded >= contentBytes),
  };
}

// Elapsed time is only an estimate. Only actual guest readiness can finish boot.
export function estimatedBootProgress(seconds) {
  return seconds < 10 ? seconds / 10 : undefined;
}

export async function fetchAsset(path, { signal, onProgress = () => {} } = {}) {
  const response = await fetch(path, { signal });
  if (!response.ok) throw new Error(`Cannot load ${path}. Run npm run setup first.`);
  // Content-Length describes the compressed body, not the bytes seen here.
  const total = Number(response.headers.get('X-Uncompressed-Content-Length')
    || (!response.headers.get('Content-Encoding') && response.headers.get('Content-Length'))) || 0;
  let loaded = 0;
  onProgress(loaded, total, false);
  const body = response.body.pipeThrough(new TransformStream({
    transform(chunk, controller) {
      loaded += chunk.byteLength;
      onProgress(loaded, total, false);
      controller.enqueue(chunk);
    },
    flush() { onProgress(loaded, total, true); },
  }));
  return new Response(body, {
    headers: { 'Content-Type': path.endsWith('.wasm') ? 'application/wasm' : 'application/octet-stream' },
  });
}

export async function verifyImage(image, expected) {
  const digest = new Uint8Array(await crypto.subtle.digest('SHA-256', image));
  const hash = [...digest].map(byte => byte.toString(16).padStart(2, '0')).join('');
  if (hash !== expected) throw new Error('Thunderden image checksum mismatch');
}
