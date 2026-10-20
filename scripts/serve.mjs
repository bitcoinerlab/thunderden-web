import { createReadStream } from 'node:fs';
import { realpath, stat } from 'node:fs/promises';
import { createServer } from 'node:http';
import { resolve, sep } from 'node:path';
import { pipeline } from 'node:stream';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { createGzip } from 'node:zlib';

const root = fileURLToPath(new URL('../web/', import.meta.url));
const types = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.wasm': 'application/wasm',
  '.woff2': 'font/woff2',
};

export function createDemoServer() {
  return createServer(async (request, response) => {
    response.setHeader('Cross-Origin-Opener-Policy', 'same-origin');
    response.setHeader('Cross-Origin-Embedder-Policy', 'require-corp');
    response.setHeader('X-Content-Type-Options', 'nosniff');
    response.setHeader('Cache-Control', 'no-cache');
    if (request.method !== 'GET' && request.method !== 'HEAD') {
      response.writeHead(405).end('Method not allowed');
      return;
    }
    try {
      const url = new URL(request.url, 'http://localhost');
      const pathname = decodeURIComponent(url.pathname.endsWith('/') ? url.pathname + 'index.html' : url.pathname);
      const candidate = resolve(root, '.' + pathname);
      if (!candidate.startsWith(root)) {
        response.writeHead(403).end('Forbidden');
        return;
      }
      const file = await realpath(candidate);
      if (!file.startsWith(root.endsWith(sep) ? root : root + sep)) {
        response.writeHead(403).end('Forbidden');
        return;
      }
      const info = await stat(file);
      if (!info.isFile()) {
        response.writeHead(404).end('Not found');
        return;
      }
      const extension = file.slice(file.lastIndexOf('.'));
      const compressible = ['.html', '.js', '.css', '.svg', '.wasm', '.img'].includes(extension) && info.size > 1024;
      if (compressible) response.setHeader('Vary', 'Accept-Encoding');
      const etag = `W/"${info.size.toString(16)}-${info.mtimeMs.toString(16)}"`;
      response.setHeader('ETag', etag);
      if (request.headers['if-none-match'] === etag) {
        response.writeHead(304).end();
        return;
      }
      const gzip = compressible && (request.headers['accept-encoding'] ?? '').split(',').some(entry => {
        const [name, ...parameters] = entry.trim().toLowerCase().split(';');
        return name.trim() === 'gzip' && !parameters.some(value => /^q=0(?:\.0*)?$/.test(value.trim()));
      });
      response.setHeader('Content-Type', types[extension] ?? 'application/octet-stream');
      response.setHeader('X-Uncompressed-Content-Length', info.size);
      if (gzip) response.setHeader('Content-Encoding', 'gzip');
      else response.setHeader('Content-Length', info.size);
      response.writeHead(200);
      if (request.method === 'HEAD') response.end();
      else {
        const input = createReadStream(file);
        pipeline(gzip ? [input, createGzip(), response] : [input, response], () => {});
      }
    } catch (error) {
      response.writeHead(error instanceof URIError ? 400 : error.code === 'ENOENT' ? 404 : 500).end('Cannot serve this file');
    }
  });
}

if (process.argv[1] && pathToFileURL(resolve(process.argv[1])).href === import.meta.url) {
  const server = createDemoServer();
  const port = Number(process.env.PORT ?? 4173);
  server.listen(port, '127.0.0.1', () => {
    console.log(`Open http://127.0.0.1:${server.address().port} in desktop Chrome/Chromium.`);
  });
}
