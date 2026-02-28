/**
 * WARSCAN - Global Application Controller
 */

const App = {
    socket: null,
    currentLocation: null,
    lang: document.body.dataset.lang || 'en',
    batteryMode: false,
    theme: 'dark',

    init() {
        this.initSocket();
        this.loadPreferences();
        this.setupNotifications();
    },

    initSocket() {
        try {
            this.socket = io({
                transports: ['websocket', 'polling'],
                reconnectionAttempts: 5,
                reconnectionDelay: 2000
            });

            this.socket.on('connect', () => {
                console.log('[WARSCAN] Connected to server');
                this.updateConnectionStatus(true);
            });

            this.socket.on('disconnect', () => {
                console.log('[WARSCAN] Disconnected');
                this.updateConnectionStatus(false);
            });

            this.socket.on('new_events', (data) => {
                if (typeof EventFeed !== 'undefined') {
                    EventFeed.handleNewEvents(data.events);
                }
                if (typeof WarscanMap !== 'undefined') {
                    WarscanMap.updateEvents(data.events);
                }
            });

            this.socket.on('threat_level_update', (data) => {
                this.updateThreatBanner(data.level);
            });

            this.socket.on('alert', (data) => {
                if (typeof Alerts !== 'undefined') {
                    Alerts.handleIncoming(data);
                }
            });
        } catch (e) {
            console.warn('[WARSCAN] Socket init failed:', e);
        }
    },

    updateConnectionStatus(connected) {
        const status = document.getElementById('map-status');
        if (status) {
            if (connected) {
                status.classList.remove('offline');
                status.innerHTML = '<span id="last-updated-text">Connected</span>';
            } else {
                status.classList.add('offline');
                status.innerHTML = '<i class="bi bi-wifi-off"></i> Offline';
            }
        }
    },

    updateThreatBanner(level) {
        const banner = document.getElementById('threat-banner');
        if (!banner) return;

        banner.className = 'threat-banner threat-' + level.toLowerCase();
        const label = document.getElementById('threat-label-text');
        if (label) {
            const labels = {
                'CRITICAL': 'Critical Threat',
                'HIGH': 'High Threat',
                'MODERATE': 'Moderate Threat',
                'LOW': 'Low Threat',
                'UNKNOWN': 'Unknown'
            };
            label.textContent = labels[level] || level;
        }
    },

    loadPreferences() {
        const savedTheme = localStorage.getItem('ws-theme');
        if (savedTheme) {
            this.setTheme(savedTheme);
        }

        const savedBattery = localStorage.getItem('ws-battery');
        if (savedBattery === 'true') {
            this.setBatteryMode(true);
        }
    },

    setTheme(theme) {
        this.theme = theme;
        document.body.classList.remove('dark-mode', 'light-mode');
        document.body.classList.add(theme + '-mode');
        localStorage.setItem('ws-theme', theme);

        const icon = document.querySelector('#theme-toggle i');
        if (icon) {
            icon.className = theme === 'dark' ? 'bi bi-sun-fill' : 'bi bi-moon-fill';
        }
    },

    setBatteryMode(enabled) {
        this.batteryMode = enabled;
        localStorage.setItem('ws-battery', enabled);

        const btn = document.getElementById('battery-saver-btn');
        if (btn) {
            btn.classList.toggle('active', enabled);
        }

        if (typeof WarscanMap !== 'undefined') {
            WarscanMap.setBatteryMode(enabled);
        }
    },

    setupNotifications() {
        if ('Notification' in window && Notification.permission === 'default') {
            // Will request on first alert
        }
    },

    requestNotificationPermission() {
        if ('Notification' in window && Notification.permission === 'default') {
            Notification.requestPermission();
        }
    },

    showNotification(title, body) {
        if ('Notification' in window && Notification.permission === 'granted') {
            new Notification(title, {
                body: body,
                icon: '/static/icons/icon-192.png',
                badge: '/static/icons/icon-192.png',
                tag: 'warscan-alert',
                renotify: true
            });
        }
    },

    setLocation(lat, lon) {
        this.currentLocation = { lat, lon };
        if (this.socket && this.socket.connected) {
            this.socket.emit('set_location', { lat, lon });
        }
    }
};

// Global functions for HTML onclick handlers
function toggleTheme() {
    App.setTheme(App.theme === 'dark' ? 'light' : 'dark');
}

function toggleBatterySaver() {
    App.setBatteryMode(!App.batteryMode);
}

function setLang(lang) {
    document.cookie = `lang=${lang};path=/;max-age=31536000`;
    window.location.reload();
}

function showSafeModal() {
    const modal = new bootstrap.Modal(document.getElementById('safeModal'));
    document.getElementById('safe-result').classList.add('d-none');
    document.getElementById('safe-submit-btn').style.display = '';
    modal.show();
}

function submitSafeReport() {
    const alias = document.getElementById('safe-alias').value;
    const message = document.getElementById('safe-message').value;
    const loc = App.currentLocation;

    fetch('/api/safe_report', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            alias: alias,
            message: message,
            lat: loc?.lat,
            lon: loc?.lon
        })
    })
    .then(r => r.json())
    .then(data => {
        if (data.token) {
            const link = window.location.origin + '/safe/' + data.token;
            document.getElementById('safe-link').value = link;
            document.getElementById('safe-result').classList.remove('d-none');
            document.getElementById('safe-submit-btn').style.display = 'none';
        }
    })
    .catch(err => {
        console.error('Safe report failed:', err);
    });
}

function copySafeLink() {
    const input = document.getElementById('safe-link');
    input.select();
    navigator.clipboard.writeText(input.value);
}

function shareSafeLink() {
    const link = document.getElementById('safe-link').value;
    if (navigator.share) {
        navigator.share({
            title: "I'm Safe - WARSCAN",
            text: "I wanted to let you know I'm safe.",
            url: link
        });
    } else {
        copySafeLink();
    }
}

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', () => {
    App.init();
});
