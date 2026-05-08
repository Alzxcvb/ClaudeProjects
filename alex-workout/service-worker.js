const CACHE_NAME = 'alex-workout-v1';

const STATIC_ASSETS = [
  'index.html',
  'push.html',
  'pull.html',
  'legs.html',
  'abs.html',
  'recovery.html',
  'progress.html',
  'references.html',
  'style.css',
  'tracker.js',
  'manifest.json',
  'icon-192.svg',
  'icon-512.svg',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS))
  );
});

self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET') return;

  event.respondWith(
    caches.match(event.request).then((cached) => {
      if (cached) return cached;
      return fetch(event.request).then((response) => {
        const clone = response.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
        return response;
      });
    })
  );
});
