const CACHE_NAME = 'aegis-app-v1';
const ASSETS_TO_CACHE = [
    '/',
    '/static/js/script.js',
    'https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap'
];

self.addEventListener('install', (event) => {
    self.skipWaiting(); // Force the waiting service worker to become the active service worker
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            return cache.addAll(ASSETS_TO_CACHE);
        })
    );
});

self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((cacheNames) => {
            return Promise.all(
                cacheNames.map((cache) => {
                    if (cache !== CACHE_NAME) {
                        return caches.delete(cache);
                    }
                })
            );
        })
    );
});

self.addEventListener('fetch', (event) => {
    const url = new URL(event.request.url);

    // Network First for the root page to ensure latest content if online
    if (url.origin === location.origin && url.pathname === '/') {
        event.respondWith(
            fetch(event.request)
                .then((response) => {
                    const resClone = response.clone();
                    caches.open(CACHE_NAME).then((cache) => {
                        cache.put(event.request, resClone);
                    });
                    return response;
                })
                .catch(() => caches.match(event.request))
        );
        return;
    }

    event.respondWith(
        caches.match(event.request).then((response) => {
            return response || fetch(event.request);
        })
    );
});

self.addEventListener('push', (event) => {
    let data = { title: 'AEGIS Alert', body: 'Ada aktivitas baru di sistem.' };
    try {
        data = event.data ? event.data.json() : data;
    } catch (e) {
        data = { title: 'AEGIS Alert', body: event.data.text() };
    }

    const options = {
        body: data.body,
        icon: '/static/icons/icon-192x192.png',
        badge: '/static/icons/icon-72x72.png',
        vibrate: [200, 100, 200, 100, 200],
        tag: 'aegis-notification',
        renotify: true,
        data: {
            url: '/'
        },
        actions: [
            { action: 'open', title: 'Buka Dashboard' }
        ]
    };

    event.waitUntil(
        self.registration.showNotification(data.title, options)
    );
});

self.addEventListener('notificationclick', (event) => {
    event.notification.close();
    event.waitUntil(
        clients.openWindow(event.notification.data.url)
    );
});
