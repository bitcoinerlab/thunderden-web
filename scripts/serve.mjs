import { createReadStream } from 'node:fs';
import { realpath, stat } from 'node:fs/promises';
import { createServer } from 'node:http';
import { resolve, sep } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const root = fileURLToPath(new URL('../web/', import.meta.url));
const types = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.wasm': 'application/wasm',
};

export function createDemoServer() {
  return createServer(async (request, response) => {
    response.setHeader('Cross-Origin-Opener-Policy', 'same-origin');
    response.setHeader('Cross-Origin-Embedder-Policy', 'require-corp');
    response.setHeader('X-Content-Type-Options', 'nosniff');
    response.setHeader('Cache-Control', 'no-store');
    if (request.method !== 'GET' && request.method !== 'HEAD') {
      response.writeHead(405).end('Method not allowed');
      return;
    }
    try {
      const url = new URL(request.url, 'http://localhost');
      const pathname = decodeURIComponent(url.pathname === '/' ? '/index.html' : url.pathname);
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
      response.writeHead(200, {
        'Content-Type': types[extension] ?? 'application/octet-stream',
        'Content-Length': info.size,
      });
      if (request.method === 'HEAD') response.end();
      else createReadStream(file).on('error', () => response.destroy()).pipe(response);
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
