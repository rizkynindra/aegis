const CACHE_NAME = 'aegis-v2';

const PRECACHE_URLS = [
    '/login',
    '/manifest.json',
    '/static/offline.html',
    '/static/js/pwa.js',
    '/static/css/login.css',
    '/static/icons/icon-192.png',
    '/static/icons/icon-512.png',
    '/static/icons/apple-touch-icon.png',
    '/static/images/logo.png',
];

self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) =>
            Promise.all(
                PRECACHE_URLS.map((url) =>
                    cache.add(url).catch((error) => {
                        console.warn('Precache skipped', url, error);
                    })
                )
            )
        ).then(() => self.skipWaiting())
    );
});

self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((cacheNames) =>
            Promise.all(
                cacheNames
                    .filter((name) => name !== CACHE_NAME)
                    .map((name) => caches.delete(name))
            )
        ).then(() => self.clients.claim())
    );
});

self.addEventListener('fetch', (event) => {
    const { request } = event;
    if (request.method !== 'GET') return;

    const url = new URL(request.url);
    if (url.origin !== self.location.origin) return;
    if (url.pathname.startsWith('/api/')) return;

    if (request.mode === 'navigate') {
        event.respondWith(networkFirst(request));
        return;
    }

    if (url.pathname.startsWith('/static/')) {
        const cachePromise = caches.open(CACHE_NAME);
        const cachedPromise = cachePromise.then((cache) => cache.match(request));
        const networkPromise = fetch(request)
            .then(async (response) => {
                if (response.ok) {
                    const cache = await cachePromise;
                    await cache.put(request, response.clone());
                }
                return response;
            })
            .catch(() => null);

        event.waitUntil(networkPromise.then(() => undefined));
        event.respondWith(
            cachedPromise.then(async (cached) => {
                if (cached) return cached;
                return (await networkPromise) || offlineResponse();
            })
        );
    }
});

async function networkFirst(request) {
    try {
        const response = await fetch(request);
        if (response.ok) {
            const cache = await caches.open(CACHE_NAME);
            cache.put(request, response.clone());
        }
        return response;
    } catch (error) {
        const cached = await caches.match(request);
        return cached || (await caches.match('/static/offline.html')) || offlineResponse();
    }
}

function offlineResponse() {
    return new Response('Offline', {
        status: 503,
        headers: { 'Content-Type': 'text/plain; charset=utf-8' },
    });
}

self.addEventListener('push', (event) => {
    let data = { title: 'AEGIS Alert', body: 'Ada aktivitas baru di sistem.' };
    try {
        data = event.data ? event.data.json() : data;
    } catch (error) {
        data = { title: 'AEGIS Alert', body: event.data ? event.data.text() : data.body };
    }

    event.waitUntil(
        self.registration.showNotification(data.title, {
            body: data.body,
            icon: '/static/icons/icon-192.png',
            badge: '/static/icons/icon-192.png',
            vibrate: [200, 100, 200],
            tag: 'aegis-notification',
            renotify: true,
            data: { url: data.url || '/' },
        })
    );
});

self.addEventListener('notificationclick', (event) => {
    event.notification.close();
    const targetUrl = new URL(event.notification.data?.url || '/', self.location.origin).href;

    event.waitUntil(
        self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((windowClients) => {
            for (const client of windowClients) {
                if (client.url.startsWith(self.location.origin) && 'focus' in client) {
                    return client.focus();
                }
            }
            return self.clients.openWindow(targetUrl);
        })
    );
});
