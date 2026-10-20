import compressed from '../dist/encoded-assets.json';

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const asset = compressed[url.pathname];
    if (!asset) return env.ASSETS.fetch(request);
    if (request.method !== 'GET' && request.method !== 'HEAD') {
      return new Response('Method not allowed', { status: 405, headers: { Allow: 'GET, HEAD' } });
    }
    url.pathname += '.gz';
    const requestHeaders = new Headers(request.headers);
    // Partial gzip bodies cannot be decoded as complete images or Wasm modules.
    requestHeaders.delete('Range');
    requestHeaders.delete('If-Range');
    requestHeaders.set('Accept-Encoding', 'identity');
    const response = await env.ASSETS.fetch(new Request(url, {
      method: request.method, headers: requestHeaders,
    }));
    if (response.status !== 200 && response.status !== 304) return response;
    const headers = new Headers(response.headers);
    headers.set('Content-Type', asset.type);
    headers.set('Content-Encoding', 'gzip');
    headers.set('X-Uncompressed-Content-Length', String(asset.bytes));
    headers.set('Cache-Control', 'public, max-age=0, must-revalidate, no-transform');
    headers.set('Cross-Origin-Opener-Policy', 'same-origin');
    headers.set('Cross-Origin-Embedder-Policy', 'require-corp');
    headers.set('X-Content-Type-Options', 'nosniff');
    // The stored body is already gzip encoded. Never encode it a second time.
    return new Response(response.body, { status: response.status, headers, encodeBody: 'manual' });
  },
};
