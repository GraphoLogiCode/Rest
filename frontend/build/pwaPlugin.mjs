import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
// Build-time plugin: every app version precaches only its explicit public shell.
export function pwaPlugin() {
  let root;
  return {
    name: 'rest-installable-app',
    apply: 'build',
    configResolved(config) { root = config.root; },
    generateBundle(_options, bundle) {
      const assets = Object.keys(bundle).filter(name => /\.(js|css)$/.test(name)).sort().map(name => '/' + name);
      const hash = createHash('sha256').update(JSON.stringify(assets));
      for (const file of ['manifest.webmanifest', 'favicon.svg', 'icons/rest-192.png', 'icons/rest-512.png', 'icons/rest-maskable-512.png', 'icons/apple-touch-icon.png']) hash.update(readFileSync(resolve(root, 'public', file)));
      const revision = hash.digest('hex').slice(0,16);
      const shell = ['/index.html', '/manifest.webmanifest', '/favicon.svg', '/icons/rest-192.png', '/icons/rest-512.png', '/icons/rest-maskable-512.png', '/icons/apple-touch-icon.png', ...assets];
      this.emitFile({ type: 'asset', fileName: 'sw.js', source: workerSource(revision, shell) });
    },
  };
}
export function workerSource(revision, shell) {
  return `
const CACHE = 'rest-shell-${revision}';
const PUBLIC_SHELL = ${JSON.stringify(shell)};
const ALLOWED = new Set(PUBLIC_SHELL);
self.addEventListener('install', event => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE);
    for (const path of PUBLIC_SHELL) {
      const response = await fetch(new Request(path, { cache: 'reload', credentials: 'omit' }));
      if (!response.ok || response.redirected) throw new Error('Shell asset unavailable');
      await cache.put(path, response);
    }
  })());
});
self.addEventListener('activate', event => {
  event.waitUntil((async () => {
    for (const key of await caches.keys()) {
      if (key.startsWith('rest-shell-') && key !== CACHE) await caches.delete(key);
    }
    await self.clients.claim();
  })());
});
self.addEventListener('message', event => {
  if (event.data?.type === 'SKIP_WAITING') self.skipWaiting();
});
self.addEventListener('fetch', event => {
  const request = event.request;
  const url = new URL(request.url);
  // Account APIs, uploads, photos, auth callbacks, query strings and foreign
  // origins are never intercepted or persisted by this worker.
  if (request.method !== 'GET' || url.origin !== self.location.origin || url.search || request.headers.has('Authorization')) return;
  if (request.mode === 'navigate' && url.pathname === '/') {
    event.respondWith(fetch(request).catch(async () => {
      const cached = await caches.match('/index.html', { cacheName: CACHE });
      return cached || Response.error();
    }));
    return;
  }
  if (!ALLOWED.has(url.pathname)) return;
  event.respondWith((async () => {
    const cache = await caches.open(CACHE);
    const cached = await cache.match(url.pathname);
    if (cached) return cached;
    // Public assets are immutable for this version. Never store arbitrary fetches.
    return fetch(request);
  })());
});
`;
}
