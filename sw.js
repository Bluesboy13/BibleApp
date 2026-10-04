// Offline support: cache the app and the Bible text on first visit.
// Bump CACHE whenever files change so phones pick up a complete, matching set.
const CACHE = 'kjv-v27';
const ASSETS = [
  './', 'index.html', 'css/style.css', 'js/app.js', 'js/sync.js', 'js/firebase-config.js',
  'vendor/firebase.js', 'data/kjv.json', 'manifest.webmanifest',
  'icons/icon.svg', 'icons/icon-192.png', 'icons/icon-512.png', 'icons/apple-touch-icon.png',
];
// Only the app itself and its web fonts are cached; sign-in and sync always go to the network.
const isFont = (url) => url.hostname === 'fonts.googleapis.com' || url.hostname === 'fonts.gstatic.com';
// The app's code and page are checked with the server first so updates arrive together;
// the large, rarely changing files (Bible text, SDK, icons, fonts) are served from the cache.
const isAppCode = (url) =>
  url.origin === self.location.origin && /(\/|\.html|\.js|\.css|\.webmanifest)$/.test(url.pathname) &&
  !url.pathname.endsWith('/vendor/firebase.js');

self.addEventListener('install', (e) => {
  // cache: 'reload' skips the browser's HTTP cache so every file is the current version.
  e.waitUntil(
    caches.open(CACHE)
      .then((c) => c.addAll(ASSETS.map((a) => new Request(a, { cache: 'reload' }))))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== 'GET') return;
  // Bibles from the FreeBiblos texts repo are kept once downloaded (its list is checked online first).
  if (url.hostname === 'freebiblos.github.io' && url.pathname.startsWith('/BibleApp-texts/')) {
    e.respondWith(url.pathname.endsWith('/index.json') ? networkFirst(e.request) : cacheFirst(e.request));
    return;
  }
  if (url.origin !== self.location.origin && !isFont(url)) return;
  // Recorded audio streams straight from the server (media needs range requests).
  if (url.pathname.includes('/audio/')) return;
  e.respondWith(isAppCode(url) ? networkFirst(e.request) : cacheFirst(e.request));
});

// Try the server (bypassing the HTTP cache); fall back to the saved copy when offline or slow.
async function networkFirst(req) {
  const cache = await caches.open(CACHE);
  try {
    const res = await Promise.race([
      fetch(req, { cache: 'no-cache' }),
      new Promise((_, reject) => setTimeout(() => reject(new Error('timeout')), 4000)),
    ]);
    if (res.ok) cache.put(req, res.clone());
    return res;
  } catch (err) {
    const cached = await cache.match(req, { ignoreSearch: true });
    if (cached) return cached;
    return fetch(req);
  }
}

async function cacheFirst(req) {
  const cache = await caches.open(CACHE);
  const cached = await cache.match(req, { ignoreSearch: true });
  if (cached) return cached;
  const res = await fetch(req);
  if (res && (res.ok || res.type === 'opaque')) cache.put(req, res.clone());
  return res;
}
