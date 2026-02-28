/**
 * EvacScan - Alerts Controller
 */

const Alerts = {
    history: [],
    audio: null,
    maxHistory: 50,

    init() {
        this.audio = new Audio('/static/sounds/alert.wav');
        this.audio.volume = 0.5;
        this.loadHistory();
    },

    handleIncoming(alert) {
        // Play sound
        this.playSound();

        // Show browser notification
        App.requestNotificationPermission();
        App.showNotification(alert.title || 'EvacScan Alert', alert.message || 'New threat detected nearby');

        // Show modal
        this.showModal(alert);

        // Add to history
        this.addToHistory(alert);
    },

    playSound() {
        if (this.audio) {
            this.audio.currentTime = 0;
            this.audio.play().catch(() => {});
        }
    },

    showModal(alert) {
        const body = document.getElementById('alertModalBody');
        if (!body) return;

        body.innerHTML = `
            <div style="margin-bottom: 16px;">
                <div style="font-size: 0.7rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.1em; color: var(--ws-text-muted); margin-bottom: 6px;">Alert</div>
                <p style="margin: 0; font-size: 1rem; font-weight: 500;">${alert.title || 'Threat Detected'}</p>
            </div>
            <div style="margin-bottom: 16px;">
                <div style="font-size: 0.7rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.1em; color: var(--ws-text-muted); margin-bottom: 6px;">Details</div>
                <p style="margin: 0; color: var(--ws-text-secondary);">${alert.message || 'A potential threat has been detected in your area.'}</p>
            </div>
            ${alert.distance_km ? `
            <div style="background: rgba(239, 68, 68, 0.1); border: 1px solid rgba(239, 68, 68, 0.3); border-radius: 8px; padding: 12px; display: flex; align-items: center; gap: 10px;">
                <i class="bi bi-geo-alt-fill" style="color: var(--ws-danger); font-size: 1.2rem;"></i>
                <span style="font-size: 0.9rem;"><strong>${alert.distance_km.toFixed(1)} km</strong> from your location</span>
            </div>
            ` : ''}
        `;

        const modal = new bootstrap.Modal(document.getElementById('alertModal'));
        modal.show();
    },

    addToHistory(alert) {
        const item = {
            id: Date.now(),
            title: alert.title || 'Alert',
            message: alert.message || '',
            time: new Date().toISOString(),
            severity: alert.severity || 'high'
        };

        this.history.unshift(item);
        if (this.history.length > this.maxHistory) {
            this.history = this.history.slice(0, this.maxHistory);
        }

        this.saveHistory();
        this.renderHistory();
        this.updateBadge();
    },

    renderHistory() {
        const container = document.getElementById('alert-history-list');
        if (!container) return;

        if (this.history.length === 0) {
            container.innerHTML = '<p style="color: var(--ws-text-muted); font-size: 0.8rem;">No alerts yet.</p>';
            return;
        }

        container.innerHTML = this.history.map(item => `
            <div class="alert-history-item">
                <div class="alert-history-title">${this.escapeHtml(item.title)}</div>
                <div class="alert-history-message">${this.escapeHtml(item.message)}</div>
                <div class="alert-history-time">${this.formatTime(item.time)}</div>
            </div>
        `).join('');
    },

    updateBadge() {
        const badge = document.getElementById('alert-badge');
        if (!badge) return;

        const count = this.history.length;
        if (count > 0) {
            badge.textContent = count > 99 ? '99+' : count;
            badge.classList.remove('d-none');
        } else {
            badge.classList.add('d-none');
        }
    },

    loadHistory() {
        try {
            const saved = localStorage.getItem('ws-alert-history');
            if (saved) {
                this.history = JSON.parse(saved);
                this.renderHistory();
                this.updateBadge();
            }
        } catch (e) {
            this.history = [];
        }
    },

    saveHistory() {
        try {
            localStorage.setItem('ws-alert-history', JSON.stringify(this.history));
        } catch (e) {
            // Storage full or unavailable
        }
    },

    formatTime(isoString) {
        try {
            const date = new Date(isoString);
            return date.toLocaleString();
        } catch {
            return 'Unknown';
        }
    },

    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
};
