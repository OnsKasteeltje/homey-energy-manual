const CACHE_NAME = 'home-energy-pwa-v5';
const APP_SHELL = ['./', './manifest.webmanifest', './assets/home-energy-app-icon.svg'];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(APP_SHELL))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(key => key !== CACHE_NAME).map(key => caches.delete(key))))
      .then(() => self.clients.claim())
      .then(() => self.clients.matchAll({ type: 'window', includeUncontrolled: true }))
      .then(clients => Promise.all(clients.map(client => {
        try {
          return client.navigate(client.url);
        } catch (error) {
          return null;
        }
      })))
  );
});

self.addEventListener('fetch', event => {
  const request = event.request;
  if (request.method !== 'GET') return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  // Live JSON/status feeds must always bypass the service-worker cache.
  if (url.pathname.endsWith('.json')) return;

  // Navigation and executable/style assets are network-first. Never serve a cached
  // version while the network is available; cached copies are offline fallback only.
  const isMutableAsset = request.mode === 'navigate' || /\.(?:js|css)$/.test(url.pathname);
  if (isMutableAsset) {
    event.respondWith(
      fetch(request, { cache: 'no-store' })
        .then(response => {
          if (response.ok) {
            const copy = response.clone();
            caches.open(CACHE_NAME).then(cache => cache.put(request, copy));
          }
          return response;
        })
        .catch(() => caches.match(request).then(hit => hit || (request.mode === 'navigate' ? caches.match('./') : undefined)))
    );
    return;
  }

  event.respondWith(
    caches.match(request).then(hit => hit || fetch(request).then(response => {
      if (response.ok) {
        const copy = response.clone();
        caches.open(CACHE_NAME).then(cache => cache.put(request, copy));
      }
      return response;
    }))
  );
});
