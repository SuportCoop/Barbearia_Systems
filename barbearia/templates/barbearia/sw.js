const CACHE_NAME = 'barberhub-barbearia-cache-v1';
const urlsToCache = [
  '/dashboard/',
  '/login/',
  '/register/'
];

// Install Event
self.addEventListener('install', event => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        console.log('Cache aberto com sucesso!');
        return cache.addAll(urlsToCache).catch(err => {
          console.warn('Algumas URLs falharam ao cachear durante instalação:', err);
        });
      })
  );
});

// Activate Event
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(cacheName => {
          if (cacheName !== CACHE_NAME) {
            console.log('Limpando cache antigo:', cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    }).then(() => self.clients.claim())
  );
});

// Fetch Event (Network first, fallback to cache)
self.addEventListener('fetch', event => {
  // Only intercept GET requests
  if (event.request.method !== 'GET') return;

  const url = new URL(event.request.url);
  // Bypass service worker cache for dynamic dashboard and management views to avoid stale CSRF tokens
  if (
    url.pathname.includes('/dashboard/') ||
    url.pathname.includes('/desenvolvedor/') ||
    url.pathname.includes('/barbeiro/') ||
    url.pathname.includes('/cliente/')
  ) {
    return; // Let browser handle request normally from network
  }

  event.respondWith(
    fetch(event.request)
      .then(response => {
        // If valid response, clone and cache it dynamically for subpages
        if (response && response.status === 200 && response.type === 'basic') {
          const responseToCache = response.clone();
          caches.open(CACHE_NAME).then(cache => {
            cache.put(event.request, responseToCache);
          });
        }
        return response;
      })
      .catch(() => {
        // Fallback to cache if network fails
        return caches.match(event.request).then(cachedResponse => {
          if (cachedResponse) {
            return cachedResponse;
          }
          // If not in cache, let it fail or return a simple offline warning
        });
      })
  );
});

// Push Notification Event (Native Push Simulation Support)
self.addEventListener('push', event => {
  let data = { title: 'BarberHub', body: 'Lembrete de corte!' };
  
  if (event.data) {
    try {
      data = event.data.json();
    } catch (e) {
      data.body = event.data.text();
    }
  }

  const options = {
    body: data.body,
    icon: 'https://images.unsplash.com/photo-1503951914875-452162b0f3f1?w=192&h=192&fit=crop',
    vibrate: [100, 50, 100],
    data: {
      dateOfArrival: Date.now(),
      primaryKey: '1'
    },
    actions: [
      { action: 'explore', title: 'Abrir App' }
    ]
  };

  event.waitUntil(
    self.registration.showNotification(data.title, options)
  );
});

// Notification Click Event
self.addEventListener('notificationclick', event => {
  event.notification.close();
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(windowClients => {
      // If a window is already open, focus it, otherwise open a new one
      for (let client of windowClients) {
        if (client.url.includes('/dashboard/') && 'focus' in client) {
          return client.focus();
        }
      }
      if (clients.openWindow) {
        return clients.openWindow('/dashboard/');
      }
    })
  );
});
