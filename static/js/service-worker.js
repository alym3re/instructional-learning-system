const CACHE_NAME = 'gls-v3';
const OFFLINE_URL = '/offline/';
const ASSETS = [
  '/',
  '/static/css/base.css',
  '/static/css/pwa.css',
  '/static/js/pwa.js',
  '/static/js/darkmode.js',
  '/static/images/logo.png',
  '/static/images/icons/icon-192x192.png',
  '/static/images/icons/icon-512x512.png',
  OFFLINE_URL
];

// Install and cache initial assets
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => cache.addAll(ASSETS))
      .then(() => self.skipWaiting())
  );
});

// Clean up old caches
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((c) => {
          if (c !== CACHE_NAME) return caches.delete(c);
        })
      );
    }).then(() => self.clients.claim())
  );
});

// Helper: Update cache with network response
function updateCache(request, response) {
  if (response && response.ok) {
    caches.open(CACHE_NAME).then((cache) => {
      cache.put(request, response);
    });
  }
}

// Fetch strategy
self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET') return;

  // Handle navigations (HTML pages)
  if (event.request.mode === 'navigate') {
    event.respondWith(
      fetch(event.request)
        .then((response) => {
          // Save the page for future offline use
          const cloned = response.clone();
          updateCache(event.request, cloned);
          return response;
        })
        .catch(() =>
          // If network fails, try serving the cached page
          caches.match(event.request).then((cachedPage) =>
            cachedPage || caches.match(OFFLINE_URL)
          )
        )
    );
    return;
  }

  // For static assets: cache-first
  event.respondWith(
    caches.match(event.request).then((cached) => {
      if (cached) return cached;
      return fetch(event.request)
        .then((response) => {
          // Dynamically cache new static assets
          updateCache(event.request, response.clone());
          return response;
        })
        .catch(() => {
          // Optional: serve offline asset for images, etc.
          if (event.request.destination === 'image') {
            return caches.match('/static/images/logo.png');
          }
        });
    })
  );
});
