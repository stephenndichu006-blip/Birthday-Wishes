async function loadBirthday() {
    try {
        const birthdayResponse = await fetch("/api/birthday");

        if (!birthdayResponse.ok) {
            throw new Error("Failed to fetch birthday details.");
        }

        const data = await birthdayResponse.json();
        hideOfflineMessage();
        applyBirthdayData(data);
        fillBirthdayForm(data);

        if (document.body.dataset.page === "admin") {
            const historyResponse = await fetch("/api/birthday/history");
            if (historyResponse.ok) {
                const historyPayload = await historyResponse.json();
                renderBirthdayHistory(historyPayload.history || []);
            }
        } else {
            renderBirthdayHistory([]);
        }
    } catch (error) {
        showOfflineMessage();
        applyBirthdayData({ name: "Not available", day: "Not available", date: "Not available" });
        renderBirthdayHistory([]);
        showStatus("Could not load birthday details from the backend.", "error");
    }
}

async function registerServiceWorker() {
    if (!("serviceWorker" in navigator)) {
        return;
    }

    try {
        await navigator.serviceWorker.register("/service-worker.js");
    } catch (error) {
        console.error("Service worker registration failed.", error);
    }
}

let audioContext;
let activeBirthdayPlayback = null;
let resolvedCandlesSongUrl = null;
const celebrationMusicKey = "birthday-wishes-celebration-active";
const celebrationMusicTimeKey = "birthday-wishes-celebration-time";
const celebrationMusicSourceKey = "birthday-wishes-celebration-source";
let sharedBirthdayAudio = null;
let autoSlideFadeTimeoutId = null;
let autoSlideNavTimeoutId = null;
let clientNavigationInitialized = false;
let currentBirthdayData = null;

const candleSongCandidates = [
    "/assets/music/candles-song.mp3",
    "/assets/music/happy-birthday.mp3",
    "/assets/music/birthday-song.mp3",
    "/assets/music/candles-song.m4a",
    "/assets/music/happy-birthday.m4a",
    "/assets/music/birthday-song.m4a",
    "/assets/music/candles-song.ogg",
    "/assets/music/happy-birthday.ogg",
    "/assets/music/birthday-song.ogg",
    "/assets/music/candles-song.wav",
    "/assets/music/happy-birthday.wav",
    "/assets/music/birthday-song.wav"
];

const baseBirthdayMelody = [
    { note: "C4", beats: 0.75 },
    { note: "C4", beats: 0.25 },
    { note: "D4", beats: 1 },
    { note: "C4", beats: 1 },
    { note: "F4", beats: 1 },
    { note: "E4", beats: 2 },
    { note: "C4", beats: 0.75 },
    { note: "C4", beats: 0.25 },
    { note: "D4", beats: 1 },
    { note: "C4", beats: 1 },
    { note: "G4", beats: 1 },
    { note: "F4", beats: 2 },
    { note: "C4", beats: 0.75 },
    { note: "C4", beats: 0.25 },
    { note: "C5", beats: 1 },
    { note: "A4", beats: 1 },
    { note: "F4", beats: 1 },
    { note: "E4", beats: 1 },
    { note: "D4", beats: 2 },
    { note: "A#4", beats: 0.75 },
    { note: "A#4", beats: 0.25 },
    { note: "A4", beats: 1 },
    { note: "F4", beats: 1 },
    { note: "G4", beats: 1 },
    { note: "F4", beats: 2 }
];

const noteFrequencies = {
    C4: 261.63,
    D4: 293.66,
    E4: 329.63,
    F4: 349.23,
    G4: 392.0,
    A4: 440.0,
    "A#4": 466.16,
    C5: 523.25
};

function getAudioContext() {
    if (!audioContext) {
        const AudioContextClass = window.AudioContext || window.webkitAudioContext;
        if (!AudioContextClass) {
            return null;
        }
        audioContext = new AudioContextClass();
    }

    return audioContext;
}

function getSharedBirthdayAudio() {
    if (sharedBirthdayAudio) {
        return sharedBirthdayAudio;
    }

    const existing = document.getElementById("global-birthday-audio");
    if (existing instanceof HTMLAudioElement) {
        sharedBirthdayAudio = existing;
        return sharedBirthdayAudio;
    }

    const audio = document.createElement("audio");
    audio.id = "global-birthday-audio";
    audio.preload = "auto";
    audio.loop = true;
    audio.hidden = true;
    audio.addEventListener("timeupdate", () => {
        try {
            window.sessionStorage.setItem(celebrationMusicTimeKey, String(audio.currentTime));
        } catch (error) {
            // Ignore storage issues during passive syncing.
        }
    });
    audio.addEventListener("play", () => {
        try {
            if (audio.currentSrc) {
                window.sessionStorage.setItem(celebrationMusicSourceKey, audio.currentSrc);
            }
        } catch (error) {
            // Ignore storage issues during passive syncing.
        }
    });
    document.body.appendChild(audio);
    sharedBirthdayAudio = audio;
    return sharedBirthdayAudio;
}

function saveCelebrationPlaybackState(songUrl, currentTime = 0) {
    try {
        window.sessionStorage.setItem(celebrationMusicSourceKey, songUrl);
        window.sessionStorage.setItem(celebrationMusicTimeKey, String(currentTime));
    } catch (error) {
        // Ignore storage issues and continue without resume support.
    }
}

function readCelebrationPlaybackState() {
    try {
        const songUrl = window.sessionStorage.getItem(celebrationMusicSourceKey) || "";
        const rawTime = window.sessionStorage.getItem(celebrationMusicTimeKey) || "0";
        const currentTime = Number.parseFloat(rawTime);
        return {
            songUrl,
            currentTime: Number.isFinite(currentTime) ? currentTime : 0
        };
    } catch (error) {
        return {
            songUrl: "",
            currentTime: 0
        };
    }
}

async function playBirthdaySong(mode = "celebration", triggerButton = null) {
    const context = getAudioContext();
    if (!context) {
        return;
    }

    if (context.state === "suspended") {
        await context.resume();
    }

    if (activeBirthdayPlayback) {
        stopBirthdaySong();
        if (triggerButton) {
            triggerButton.textContent = triggerButton.dataset.songMode === "finale"
                ? "Play Finale Song"
                : "Play Happy Birthday Song";
        }
        return;
    }

    const settings = mode === "finale"
        ? { bpm: 118, wave: "triangle", gain: 0.05, label: "Stop Finale Song" }
        : { bpm: 132, wave: "sine", gain: 0.06, label: "Stop Happy Birthday Song" };

    const beatSeconds = 60 / settings.bpm;
    const now = context.currentTime + 0.05;
    const masterGain = context.createGain();
    masterGain.gain.value = settings.gain;
    masterGain.connect(context.destination);

    let elapsed = 0;
    const oscillators = [];

    for (const segment of baseBirthdayMelody) {
        const oscillator = context.createOscillator();
        const noteGain = context.createGain();
        oscillator.type = settings.wave;
        oscillator.frequency.value = noteFrequencies[segment.note];
        oscillator.connect(noteGain);
        noteGain.connect(masterGain);

        const startTime = now + elapsed;
        const duration = segment.beats * beatSeconds;
        const stopTime = startTime + duration;

        noteGain.gain.setValueAtTime(0.0001, startTime);
        noteGain.gain.exponentialRampToValueAtTime(0.6, startTime + 0.02);
        noteGain.gain.exponentialRampToValueAtTime(0.0001, stopTime);

        oscillator.start(startTime);
        oscillator.stop(stopTime);
        oscillators.push(oscillator);
        elapsed += duration;
    }

    activeBirthdayPlayback = {
        oscillators,
        button: triggerButton,
        timeoutId: window.setTimeout(() => {
            stopBirthdaySong();
        }, (elapsed + 0.1) * 1000)
    };

    if (triggerButton) {
        triggerButton.textContent = settings.label;
    }
}

function stopBirthdaySong() {
    if (!activeBirthdayPlayback) {
        return;
    }

    for (const oscillator of activeBirthdayPlayback.oscillators) {
        try {
            oscillator.stop();
        } catch (error) {
            // Oscillators may already be stopped by the time cleanup runs.
        }
    }

    if (activeBirthdayPlayback.button) {
        activeBirthdayPlayback.button.textContent = activeBirthdayPlayback.button.dataset.songMode === "finale"
            ? "Play Finale Song"
            : "Play Happy Birthday Song";
    }

    window.clearTimeout(activeBirthdayPlayback.timeoutId);
    activeBirthdayPlayback = null;
}

async function resolveCandlesSongUrl() {
    if (resolvedCandlesSongUrl !== null) {
        return resolvedCandlesSongUrl;
    }

    for (const candidate of candleSongCandidates) {
        try {
            const response = await fetch(candidate, { method: "HEAD" });
            if (response.ok) {
                resolvedCandlesSongUrl = candidate;
                return resolvedCandlesSongUrl;
            }
        } catch (error) {
            // Ignore individual lookup failures and continue trying other candidates.
        }
    }

    resolvedCandlesSongUrl = "";
    return resolvedCandlesSongUrl;
}

async function playCandlesLocalSong() {
    if ((currentBirthdayData?.settings?.music_mode || "local") !== "local") {
        return false;
    }

    const audio = getSharedBirthdayAudio();
    if (!audio) {
        return false;
    }

    const songUrl = await resolveCandlesSongUrl();
    if (!songUrl) {
        return false;
    }

    const savedState = readCelebrationPlaybackState();
    const expectedSrc = window.location.origin + songUrl;

    if (audio.src !== expectedSrc) {
        audio.src = songUrl;
        audio.load();
        audio.currentTime = 0;
    }

    if (savedState.songUrl === expectedSrc && savedState.currentTime > 0) {
        audio.currentTime = savedState.currentTime;
    }

    try {
        await audio.play();
        saveCelebrationPlaybackState(songUrl, audio.currentTime);
        return true;
    } catch (error) {
        return false;
    }
}

function enableCelebrationMusic() {
    try {
        window.localStorage.setItem(celebrationMusicKey, "true");
    } catch (error) {
        // Ignore storage issues and continue without cross-page persistence.
    }
}

function isCelebrationMusicEnabled() {
    try {
        return window.localStorage.getItem(celebrationMusicKey) === "true";
    } catch (error) {
        return false;
    }
}

function updateCelebrationMusicStatus(message) {
    void message;
}

function stopCelebrationMusic() {
    try {
        window.localStorage.removeItem(celebrationMusicKey);
        window.sessionStorage.removeItem(celebrationMusicTimeKey);
        window.sessionStorage.removeItem(celebrationMusicSourceKey);
    } catch (error) {
        // Ignore storage issues during cleanup.
    }

    stopBirthdaySong();

    const audio = getSharedBirthdayAudio();
    audio.pause();
    audio.currentTime = 0;

}

function ensureCelebrationMusicControls() {
    return;
}

async function startCelebrationMusicForPage() {
    const page = document.body.dataset.page || "";
    if (!isCelebrationMusicEnabled() || page === "admin") {
        return;
    }

    ensureCelebrationMusicControls();

    const playedLocalSong = await playCandlesLocalSong();
    if (playedLocalSong) {
        updateCelebrationMusicStatus("Playing your birthday music across the celebration.");
        return;
    }

    if (!activeBirthdayPlayback) {
        await playBirthdaySong("celebration");
        updateCelebrationMusicStatus("Playing the built-in Happy Birthday melody.");
    }
}

const slideshowPages = [
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
    "/finale.html"
];

let slideDurationMs = 14000;
const fadeDurationMs = 900;

function normalizePath(path) {
    return path === "/" ? "/home.html" : path;
}

function syncHeadMetadata(nextDocument) {
    document.title = nextDocument.title || document.title;

    const currentTheme = document.querySelector('meta[name="theme-color"]');
    const nextTheme = nextDocument.querySelector('meta[name="theme-color"]');
    if (currentTheme && nextTheme) {
        currentTheme.setAttribute("content", nextTheme.getAttribute("content") || "#9f2d56");
    }
}

function preserveGlobalNodes() {
    return [
        document.getElementById("global-birthday-audio"),
        document.getElementById("celebration-music-controls")
    ].filter(Boolean);
}

function applyBodyAttributes(sourceBody) {
    document.body.className = sourceBody.className;
    Array.from(document.body.attributes)
        .filter((attribute) => attribute.name.startsWith("data-"))
        .forEach((attribute) => {
            document.body.removeAttribute(attribute.name);
        });

    Array.from(sourceBody.attributes)
        .filter((attribute) => attribute.name.startsWith("data-"))
        .forEach((attribute) => {
            document.body.setAttribute(attribute.name, attribute.value);
        });
}

function initializePageFeatures() {
    if (document.body.dataset.page !== "admin") {
        enableCelebrationMusic();
    }

    loadBirthday();
    setupBirthdayForm();
    setupBirthdaySongControls();
    setupAutoSlideshow();
    setupCandles();
    ensureCelebrationMusicControls();
    startCelebrationMusicForPage();
}

async function navigateToPage(path, options = {}) {
    const normalizedPath = normalizePath(path);
    if (!options.force && normalizedPath === normalizePath(window.location.pathname)) {
        return;
    }

    try {
        const response = await fetch(normalizedPath, { cache: "no-store" });
        if (!response.ok) {
            window.location.href = normalizedPath;
            return;
        }

        const html = await response.text();
        const parser = new DOMParser();
        const nextDocument = parser.parseFromString(html, "text/html");
        const nextBody = nextDocument.body.cloneNode(true);
        nextBody.querySelectorAll("script").forEach((script) => script.remove());

        const preservedNodes = preserveGlobalNodes();
        applyBodyAttributes(nextDocument.body);
        document.body.innerHTML = nextBody.innerHTML;
        preservedNodes.forEach((node) => document.body.appendChild(node));
        syncHeadMetadata(nextDocument);

        if (options.replace) {
            window.history.replaceState({ path: normalizedPath }, "", normalizedPath);
        } else {
            window.history.pushState({ path: normalizedPath }, "", normalizedPath);
        }

        initializePageFeatures();
        window.scrollTo({ top: 0, behavior: "auto" });
    } catch (error) {
        window.location.href = normalizedPath;
    }
}

function setupClientNavigation() {
    if (clientNavigationInitialized) {
        return;
    }

    clientNavigationInitialized = true;

    document.addEventListener("click", (event) => {
        const target = event.target;
        if (!(target instanceof Element)) {
            return;
        }

        const link = target.closest("a[href]");
        if (!(link instanceof HTMLAnchorElement)) {
            return;
        }

        const url = new URL(link.href, window.location.origin);
        const normalizedPath = normalizePath(url.pathname);

        if (url.origin !== window.location.origin || !slideshowPages.includes(normalizedPath)) {
            return;
        }

        event.preventDefault();
        navigateToPage(normalizedPath);
    });

    window.addEventListener("popstate", () => {
        navigateToPage(window.location.pathname, { replace: true, force: true });
    });
}

function applyBirthdayData(data) {
    currentBirthdayData = data;
    const name = data.name || "Ann Wanjiku";
    const nameTargets = document.querySelectorAll("#birthday-name-admin");
    const dayTargets = document.querySelectorAll("#birthday-day, #birthday-day-inline");
    const dateTargets = document.querySelectorAll("#birthday-date, #birthday-date-inline");
    const savedTarget = document.getElementById("saved-birthday");
    const updatedTarget = document.getElementById("saved-updated-at");
    const countTarget = document.getElementById("saved-count");

    nameTargets.forEach((element) => {
        element.textContent = name;
    });

    dayTargets.forEach((element) => {
        element.textContent = data.day;
    });

    dateTargets.forEach((element) => {
        element.textContent = data.date;
    });

    if (savedTarget) {
        savedTarget.textContent = `${name} - ${data.day}, ${data.date}`;
    }

    if (updatedTarget) {
        updatedTarget.textContent = formatTimestamp(data.updated_at);
    }

    if (countTarget) {
        countTarget.textContent = String(data.save_count || 0);
    }

    applySettings(data.settings || {});
    applyGuestWishes(data.guest_wishes || []);
    applyReasonsWall(data.reasons_wall || []);
    applyFavoriteThings(data.favorite_things || []);
    applyMilestones(data.milestones || []);
    applyMemorySlides(data.memory_slides || []);
    applyFinaleMessage(data.settings?.finale_message || "");
    ensureWelcomeOverlay(data.settings || {});
}

function fillBirthdayForm(data) {
    const form = document.getElementById("birthday-form");
    if (!form) {
        return;
    }

    form.elements.name.value = data.name || "";
    form.elements.day.value = data.day;
    form.elements.date.value = data.date;
    form.elements.welcomeTitle.value = data.settings?.welcome_title || "";
    form.elements.welcomeSubtitle.value = data.settings?.welcome_subtitle || "";
    form.elements.finaleMessage.value = data.settings?.finale_message || "";
    form.elements.autoplayEnabled.value = String(Boolean(data.settings?.autoplay_enabled));
    form.elements.slideDurationSeconds.value = String(data.settings?.slide_duration_seconds || 14);
    form.elements.musicMode.value = data.settings?.music_mode || "local";
    form.elements.guestWishes.value = (data.guest_wishes || []).join("\n");
    form.elements.reasonsWall.value = (data.reasons_wall || []).join("\n");
    form.elements.favoriteThings.value = stringifyLabeledItems(data.favorite_things || []);
    form.elements.milestones.value = stringifyMilestones(data.milestones || []);
    form.elements.memorySlides.value = stringifyMemorySlides(data.memory_slides || []);
}

function showStatus(message, type) {
    const status = document.getElementById("form-status");
    if (!status) {
        return;
    }

    status.textContent = message;
    status.className = `form-status ${type}`;
}

function parseLineList(value) {
    return value
        .split(/\r?\n/)
        .map((line) => line.trim())
        .filter(Boolean);
}

function parseLabeledItems(value) {
    return parseLineList(value)
        .map((line) => {
            const [label, ...rest] = line.split("|");
            return { label: (label || "").trim(), value: rest.join("|").trim() };
        })
        .filter((item) => item.label && item.value);
}

function parseMilestones(value) {
    return parseLineList(value)
        .map((line) => {
            const [time, title, ...rest] = line.split("|");
            return { time: (time || "").trim(), title: (title || "").trim(), detail: rest.join("|").trim() };
        })
        .filter((item) => item.time && item.title && item.detail);
}

function parseMemorySlides(value) {
    return parseLineList(value)
        .map((line) => {
            const [title, caption, ...rest] = line.split("|");
            return { title: (title || "").trim(), caption: (caption || "").trim(), image: rest.join("|").trim() };
        })
        .filter((item) => item.title && item.caption && item.image);
}

function stringifyLabeledItems(items) {
    return items.map((item) => `${item.label} | ${item.value}`).join("\n");
}

function stringifyMilestones(items) {
    return items.map((item) => `${item.time} | ${item.title} | ${item.detail}`).join("\n");
}

function stringifyMemorySlides(items) {
    return items.map((item) => `${item.title} | ${item.caption} | ${item.image}`).join("\n");
}

function applySettings(settings) {
    slideDurationMs = Number(settings.slide_duration_seconds || 14) * 1000;
    document.body.dataset.autoslide = settings.autoplay_enabled === false ? "off" : "";

    const finaleMessage = document.getElementById("finale-message");
    if (finaleMessage && settings.finale_message) {
        finaleMessage.textContent = settings.finale_message;
    }
}

function applyGuestWishes(wishes) {
    const target = document.getElementById("guest-wishes-list");
    if (!target) {
        return;
    }

    target.innerHTML = wishes
        .map((wish) => `<article class="wish-card accent-cream"><h2>Guest Wish</h2><p>${wish}</p></article>`)
        .join("");
}

function applyReasonsWall(reasons) {
    const target = document.getElementById("reasons-wall-list");
    if (!target) {
        return;
    }

    target.innerHTML = reasons
        .map((reason, index) => `<article class="importance-card"><span class="label">${String(index + 1).padStart(2, "0")}</span><p>${reason}</p></article>`)
        .join("");
}

function applyFavoriteThings(items) {
    const target = document.getElementById("favorite-things-list");
    if (!target) {
        return;
    }

    target.innerHTML = items
        .map((item) => `<article class="crown-card"><span class="label">${item.label}</span><h2>${item.value}</h2></article>`)
        .join("");
}

function applyMilestones(items) {
    const target = document.getElementById("timeline-milestones");
    if (!target) {
        return;
    }

    target.innerHTML = items
        .map((item, index) => `
            <article class="timeline-card">
                <span class="timeline-step">${index + 1}</span>
                <p class="eyebrow">${item.time}</p>
                <h2>${item.title}</h2>
                <p>${item.detail}</p>
            </article>
        `)
        .join("");
}

function applyMemorySlides(items) {
    const track = document.getElementById("memory-slider-track");
    const dots = document.getElementById("memory-slider-dots");
    if (!track || !dots) {
        return;
    }

    track.innerHTML = items
        .map((item) => `
            <article class="memory-slide">
                <figure class="gallery-frame memory-slide-frame">
                    <img src="${item.image}" alt="${item.title}">
                </figure>
                <div class="memory-slide-copy">
                    <span class="label">${item.title}</span>
                    <p>${item.caption}</p>
                </div>
            </article>
        `)
        .join("");

    dots.innerHTML = items
        .map((_, index) => `<button type="button" class="memory-dot${index === 0 ? " active" : ""}" data-memory-index="${index}" aria-label="Open memory slide ${index + 1}"></button>`)
        .join("");

    setupMemorySlider();
}

function applyFinaleMessage(message) {
    const target = document.getElementById("finale-message");
    if (target && message) {
        target.textContent = message;
    }
}

function ensureWelcomeOverlay(settings) {
    if (document.body.dataset.page !== "home") {
        const existing = document.getElementById("welcome-overlay");
        if (existing) {
            existing.remove();
        }
        return;
    }

    let overlay = document.getElementById("welcome-overlay");
    if (!overlay) {
        return;
    }

    overlay.classList.remove("hidden");
    document.getElementById("welcome-start-panel")?.classList.remove("hidden");
    document.getElementById("birthday-intro-panel")?.classList.add("hidden");

    const startButton = document.getElementById("welcome-start-button");
    if (startButton && startButton.dataset.bound !== "true") {
        startButton.dataset.bound = "true";
        startButton.addEventListener("click", () => {
            document.getElementById("welcome-start-panel")?.classList.add("hidden");
            document.getElementById("birthday-intro-panel")?.classList.remove("hidden");
        });
    }

    const continueButton = document.getElementById("birthday-intro-continue");
    if (continueButton && continueButton.dataset.bound !== "true") {
        continueButton.dataset.bound = "true";
        continueButton.addEventListener("click", async () => {
            overlay?.classList.add("hidden");
            await startCelebrationMusicForPage();
        });
    }

    const title = document.getElementById("welcome-overlay-title");
    const subtitle = document.getElementById("welcome-overlay-subtitle");
    if (title) {
        title.textContent = settings.welcome_title || "Welcome to the birthday experience";
    }
    if (subtitle) {
        subtitle.textContent = settings.welcome_subtitle || "Tap to begin and enjoy the celebration.";
    }
}

function showOfflineMessage() {
    let banner = document.getElementById("offline-banner");
    if (!banner) {
        banner = document.createElement("div");
        banner.id = "offline-banner";
        banner.className = "offline-banner";
        banner.textContent = "You are offline. The birthday pages and saved content already on this device are still available.";
        document.body.appendChild(banner);
    }
}

function hideOfflineMessage() {
    document.getElementById("offline-banner")?.remove();
}

function setupMemorySlider() {
    const track = document.getElementById("memory-slider-track");
    const dots = Array.from(document.querySelectorAll(".memory-dot"));
    if (!track || !dots.length) {
        return;
    }

    dots.forEach((dot) => {
        dot.addEventListener("click", () => {
            const index = Number(dot.dataset.memoryIndex || "0");
            track.style.transform = `translateX(-${index * 100}%)`;
            dots.forEach((item, itemIndex) => item.classList.toggle("active", itemIndex === index));
        });
    });
}

function setupBirthdaySongControls() {
    const buttons = Array.from(document.querySelectorAll(".music-toggle"));
    if (!buttons.length) {
        return;
    }

    buttons.forEach((button) => {
        button.addEventListener("click", async () => {
            if (button.id === "candles-song-toggle") {
                const playedLocalSong = await playCandlesLocalSong();
                if (playedLocalSong) {
                    button.textContent = "Playing Local Song";
                    updateCelebrationMusicStatus("Playing your birthday music across the celebration.");
                    return;
                }
            }

            await playBirthdaySong(button.dataset.songMode || "celebration", button);
        });
    });
}

function formatTimestamp(value) {
    if (!value) {
        return "Not available";
    }

    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) {
        return value;
    }

    return parsed.toLocaleString();
}

function renderBirthdayHistory(history) {
    const target = document.getElementById("birthday-history");
    if (!target) {
        return;
    }

    if (!history.length) {
        target.innerHTML = "<p>No changes recorded yet.</p>";
        return;
    }

    target.innerHTML = history
        .map((entry) => {
            const actionLabel = entry.action === "reset" ? "Reset from" : "Previous value";
            const replacedAt = formatTimestamp(entry.replaced_at);
            return `<p><strong>${actionLabel}:</strong> ${entry.name} - ${entry.day}, ${entry.date}<br><span>${replacedAt}</span></p>`;
        })
        .join("");
}

function setupBirthdayForm() {
    const form = document.getElementById("birthday-form");
    if (!form) {
        return;
    }

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        showStatus("Saving birthday details...", "");

        const payload = {
            name: form.elements.name.value.trim(),
            day: form.elements.day.value.trim(),
            date: form.elements.date.value.trim(),
            settings: {
                welcome_title: form.elements.welcomeTitle.value.trim(),
                welcome_subtitle: form.elements.welcomeSubtitle.value.trim(),
                finale_message: form.elements.finaleMessage.value.trim(),
                autoplay_enabled: form.elements.autoplayEnabled.value === "true",
                slide_duration_seconds: Number(form.elements.slideDurationSeconds.value || 14),
                music_mode: form.elements.musicMode.value
            },
            guest_wishes: parseLineList(form.elements.guestWishes.value),
            reasons_wall: parseLineList(form.elements.reasonsWall.value),
            favorite_things: parseLabeledItems(form.elements.favoriteThings.value),
            milestones: parseMilestones(form.elements.milestones.value),
            memory_slides: parseMemorySlides(form.elements.memorySlides.value)
        };

        try {
            const response = await fetch("/api/birthday", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify(payload)
            });

            const result = await response.json();
            if (!response.ok) {
                throw new Error(result.error || "Could not save birthday details.");
            }

            applyBirthdayData(result);
            await loadBirthday();
            showStatus("Birthday details saved successfully.", "success");
        } catch (error) {
            showStatus(error.message, "error");
        }
    });

    const resetButton = document.getElementById("reset-birthday");
    if (!resetButton) {
        return;
    }

    resetButton.addEventListener("click", async () => {
        showStatus("Resetting birthday details...", "");

        try {
            const response = await fetch("/api/birthday/reset", {
                method: "POST"
            });
            const result = await response.json();
            if (!response.ok) {
                throw new Error(result.error || "Could not reset birthday details.");
            }

            fillBirthdayForm(result);
            applyBirthdayData(result);
            await loadBirthday();
            showStatus("Birthday details were reset to the backend defaults.", "success");
        } catch (error) {
            showStatus(error.message, "error");
        }
    });
}

function setupAutoSlideshow() {
    window.clearTimeout(autoSlideFadeTimeoutId);
    window.clearTimeout(autoSlideNavTimeoutId);

    if (document.body.dataset.autoslide === "off") {
        return;
    }

    const currentPath = normalizePath(window.location.pathname);
    const currentIndex = slideshowPages.indexOf(currentPath);

    if (currentIndex === -1) {
        return;
    }

    const nextIndex = (currentIndex + 1) % slideshowPages.length;
    const nextPage = slideshowPages[nextIndex];

    autoSlideFadeTimeoutId = window.setTimeout(() => {
        document.body.classList.add("page-fade-out");
    }, slideDurationMs - fadeDurationMs);

    autoSlideNavTimeoutId = window.setTimeout(() => {
        navigateToPage(nextPage);
    }, slideDurationMs);
}

function setupCandles() {
    const candles = Array.from(document.querySelectorAll(".candle"));
    if (!candles.length) {
        return;
    }

    const status = document.getElementById("candle-status");
    const wishReveal = document.getElementById("wish-reveal");
    const finaleLink = document.getElementById("finale-link");
    const celebrationMoment = document.getElementById("celebration-moment");

    const updateCandleMessage = () => {
        const remaining = candles.filter((candle) => !candle.classList.contains("blown")).length;

        if (remaining > 0) {
            status.textContent = `${remaining} candle${remaining === 1 ? "" : "s"} ${remaining === 1 ? "is" : "are"} still shining. Tap each candle to blow ${remaining === 1 ? "it" : "them"} out.`;
            return;
        }

        status.textContent = "All the candles are out. Make your wish, Ann Wanjiku.";
        wishReveal.classList.add("visible");
        document.body.classList.add("candles-celebrating");
        celebrationMoment.classList.remove("hidden");
        celebrationMoment.classList.add("visible");
        finaleLink.classList.remove("hidden");
        enableCelebrationMusic();
        ensureCelebrationMusicControls();
        saveCelebrationPlaybackState("", 0);

        const songButton = document.getElementById("candles-song-toggle");
        if (songButton) {
            playCandlesLocalSong().then((playedLocalSong) => {
                if (playedLocalSong) {
                    songButton.textContent = "Playing Local Song";
                    updateCelebrationMusicStatus("Playing your birthday music across the celebration.");
                    return;
                }

                if (!activeBirthdayPlayback) {
                    playBirthdaySong("celebration", songButton);
                    updateCelebrationMusicStatus("Playing the built-in Happy Birthday melody.");
                }
            });
        }
    };

    candles.forEach((candle) => {
        candle.addEventListener("click", () => {
            candle.classList.add("blown");
            candle.disabled = true;
            updateCandleMessage();
        });
    });
}

document.addEventListener("DOMContentLoaded", () => {
    registerServiceWorker();
    setupClientNavigation();
    initializePageFeatures();
});
