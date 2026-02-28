/**
 * EvacScan Service Worker
 * Caching strategies: app shell (cache-first), API (stale-while-revalidate),
 * map tiles (cache-first for saved, network-first for others)
 */

const CACHE_NAME = 'evacscan-v1';
const APP_SHELL = [
    '/',
    '/emergency',
    '/about',
    '/static/css/style.css',
    '/static/js/app.js',
    '/static/js/map.js',
    '/static/js/events.js',
    '/static/js/alerts.js',
    '/static/js/evacuation.js',
    '/static/js/pdf-export.js',
    '/static/manifest.json',
];

const API_ROUTES = ['/api/events', '/api/danger_zones', '/api/threat_level'];

self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(CACHE_NAME).then(cache => {
            return cache.addAll(APP_SHELL).catch(err => {
                console.warn('SW: Some app shell resources failed to cache:', err);
            });
        })
    );
    self.skipWaiting();
});

self.addEventListener('activate', event => {
    event.waitUntil(
        caches.keys().then(keys =>
            Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
        )
    );
    self.clients.claim();
});

self.addEventListener('fetch', event => {
    const url = new URL(event.request.url);

    // Skip non-GET and cross-origin socket.io
    if (event.request.method !== 'GET') return;
    if (url.pathname.startsWith('/socket.io')) return;

    // API routes: stale-while-revalidate
    if (API_ROUTES.some(r => url.pathname.startsWith(r))) {
        event.respondWith(staleWhileRevalidate(event.request));
        return;
    }

    // Map tiles: cache-first (OpenStreetMap, TomTom)
    if (url.hostname.includes('tile.openstreetmap.org') ||
        url.hostname.includes('api.tomtom.com')) {
        event.respondWith(cacheFirst(event.request));
        return;
    }

    // App shell and static assets: cache-first with network fallback
    if (url.origin === self.location.origin) {
        event.respondWith(cacheFirst(event.request));
        return;
    }

    // CDN resources: cache-first
    event.respondWith(cacheFirst(event.request));
});

async function cacheFirst(request) {
    const cached = await caches.match(request);
    if (cached) return cached;
    try {
        const response = await fetch(request);
        if (response.ok) {
            const cache = await caches.open(CACHE_NAME);
            cache.put(request, response.clone());
        }
        return response;
    } catch (err) {
        // Offline fallback for HTML pages
        if (request.headers.get('Accept')?.includes('text/html')) {
            const fallback = await caches.match('/');
            if (fallback) return fallback;
        }
        throw err;
    }
}

async function staleWhileRevalidate(request) {
    const cache = await caches.open(CACHE_NAME);
    const cached = await cache.match(request);

    const fetchPromise = fetch(request).then(response => {
        if (response.ok) {
            cache.put(request, response.clone());
        }
        return response;
    }).catch(() => cached);

    return cached || fetchPromise;
}
