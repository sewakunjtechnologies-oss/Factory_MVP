// Factory Control — minimal service worker.
//
// Goal: make the app installable on Android Chrome (PWA install prompt requires
// a controlled fetch handler) and survive a brief network blip on the factory
// floor. We deliberately use a "network-first" strategy so the user never sees
// stale POs or stock — the cache only kicks in when the network actually fails.

const CACHE_NAME = "factory-shell-v2";

// App shell — fetched on install so the home screen icon launches even offline.
const PRECACHE = [
  "/",
  "/manifest.webmanifest",
  "/icons/icon-192.png",
  "/icons/icon-512.png",
  "/icons/apple-touch-icon.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(PRECACHE)).catch(() => {}),
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k))),
    ),
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const request = event.request;

  // Only handle GETs — never cache POST/PATCH/DELETE (writes must hit the network).
  if (request.method !== "GET") return;

  const url = new URL(request.url);

  // Never cache the API — POs, stock, reminders, etc. must always be fresh.
  if (url.pathname.startsWith("/api/")) return;

  // Network-first for navigations + static assets; fall back to cache only on failure.
  event.respondWith(
    fetch(request)
      .then((response) => {
        // Cache same-origin successful GETs for offline fallback (app shell).
        if (response && response.ok && url.origin === self.location.origin) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(request, clone)).catch(() => {});
        }
        return response;
      })
      .catch(() =>
        caches.match(request).then((cached) => cached || caches.match("/")),
      ),
  );
});

// Allow the page to trigger an update without forcing a reload.
self.addEventListener("message", (event) => {
  if (event.data === "skip-waiting") self.skipWaiting();
});
