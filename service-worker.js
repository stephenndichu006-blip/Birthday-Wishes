const STATIC_CACHE = "birthday-wishes-static-v5";
const RUNTIME_CACHE = "birthday-wishes-runtime-v5";
const OFFLINE_URL = "/home.html";

const APP_SHELL = [
    "/",
    "/home.html",
    "/wishes.html",
    "/celebration.html",
    "/gallery.html",
    "/blessings.html",
    "/letter.html",
    "/highlights.html",
    "/journey.html",
    "/memories.html",
    "/queen.html",
    "/toast.html",
    "/candles.html",
    "/finale.html",
    "/admin.html",
    "/style.css",
    "/app.js",
    "/assets/app-icon-192.png",
    "/assets/app-icon-512.png",
    "/assets/birthday-bloom.svg",
    "/assets/floral-frame.svg",
    "/assets/golden-cake.svg",
    "/assets/music/candles-song.wav",
    "/assets/photos/photo-1.jpeg",
    "/assets/photos/photo-2.jpeg",
    "/assets/photos/photo-3.jpeg",
    "/manifest.webmanifest",
];

self.addEventListener("install", (event) => {
    event.waitUntil(
        caches.open(STATIC_CACHE).then((cache) => cache.addAll(APP_SHELL)).then(() => self.skipWaiting())
    );
});

self.addEventListener("activate", (event) => {
    event.waitUntil(
        caches.keys().then((keys) =>
            Promise.all(
                keys
                    .filter((key) => ![STATIC_CACHE, RUNTIME_CACHE].includes(key))
                    .map((key) => caches.delete(key))
            )
        ).then(() => self.clients.claim())
    );
});

self.addEventListener("fetch", (event) => {
    const request = event.request;
    if (request.method !== "GET") {
        return;
    }

    const url = new URL(request.url);
    if (url.origin !== self.location.origin) {
        return;
    }

    if (url.pathname.startsWith("/api/")) {
        event.respondWith(networkFirst(request));
        return;
    }

    if (shouldUseNetworkFirst(url.pathname)) {
        event.respondWith(networkFirst(request));
        return;
    }

    if (request.mode === "navigate") {
        event.respondWith(navigationStrategy(request));
        return;
    }

    event.respondWith(cacheFirst(request));
});

async function cacheFirst(request) {
    const cached = await caches.match(request);
    if (cached) {
        return cached;
    }

    const response = await fetch(request);
    const cache = await caches.open(RUNTIME_CACHE);
    cache.put(request, response.clone());
    return response;
}

async function networkFirst(request) {
    try {
        const response = await fetch(request);
        const cache = await caches.open(RUNTIME_CACHE);
        cache.put(request, response.clone());
        return response;
    } catch (error) {
        const cached = await caches.match(request);
        if (cached) {
            return cached;
        }

        return new Response(JSON.stringify({ error: "Offline" }), {
            status: 503,
            headers: { "Content-Type": "application/json; charset=utf-8" },
        });
    }
}

async function navigationStrategy(request) {
    try {
        const response = await fetch(request);
        const cache = await caches.open(RUNTIME_CACHE);
        cache.put(request, response.clone());
        return response;
    } catch (error) {
        const cached = await caches.match(request);
        return cached || caches.match(OFFLINE_URL);
    }
}

function shouldUseNetworkFirst(pathname) {
    return (
        pathname.endsWith(".html") ||
        pathname.endsWith(".js") ||
        pathname.endsWith(".css") ||
        pathname.endsWith(".webmanifest")
    );
}
