/**
 * EvacScan - Event Feed Controller
 */

const EventFeed = {
    events: [],
    filter: 'all',
    refreshInterval: null,

    init() {
        this.fetchEvents();
        this.refreshInterval = setInterval(() => this.fetchEvents(), 60000);
    },

    fetchEvents() {
        fetch('/api/events')
            .then(r => r.json())
            .then(data => {
                this.events = data.events || [];
                this.render();
                this.updateLastUpdated();
            })
            .catch(err => {
                console.error('[EventFeed] Fetch failed:', err);
            });
    },

    handleNewEvents(newEvents) {
        if (!newEvents || !newEvents.length) return;
        
        const existingIds = new Set(this.events.map(e => e.id));
        const added = newEvents.filter(e => !existingIds.has(e.id));
        
        if (added.length > 0) {
            this.events = [...added, ...this.events].slice(0, 100);
            this.render();
            this.updateLastUpdated();
        }
    },

    setFilter(filter) {
        this.filter = filter;
        this.render();
    },

    render() {
        const container = document.getElementById('event-feed');
        if (!container) return;

        let filtered = this.events;
        if (this.filter !== 'all') {
            filtered = this.events.filter(e => e.category === this.filter);
        }

        if (filtered.length === 0) {
            container.innerHTML = `
                <div style="text-align: center; padding: 40px 20px; color: var(--ws-text-muted);">
                    <i class="bi bi-inbox" style="font-size: 2rem; margin-bottom: 12px; display: block;"></i>
                    <p style="margin: 0; font-size: 0.85rem;">No events to display</p>
                </div>
            `;
            return;
        }

        container.innerHTML = filtered.map(event => this.renderCard(event)).join('');
    },

    renderCard(event) {
        const severity = event.severity || 0;
        const severityClass = severity >= 7 ? 'high' : severity >= 4 ? 'medium' : 'low';
        const severityWidth = Math.min(100, Math.max(10, severity * 10));
        const category = event.category || 'rumored';
        const timeAgo = this.formatTimeAgo(event.published_at);

        return `
            <div class="event-card" onclick="EventFeed.showOnMap(${event.lat}, ${event.lon})">
                <div class="event-header">
                    <span class="event-badge ${category}">${category}</span>
                    <span class="event-time">${timeAgo}</span>
                </div>
                <div class="event-title">${this.escapeHtml(event.title)}</div>
                <div class="event-severity">
                    <div class="event-severity-bar ${severityClass}" style="width: ${severityWidth}%"></div>
                </div>
                <div class="event-meta">
                    <span class="event-meta-item">
                        <i class="bi bi-geo-alt"></i>
                        ${event.location || 'Unknown location'}
                    </span>
                    <span class="event-meta-item">
                        <i class="bi bi-newspaper"></i>
                        ${event.source || 'Unknown'}
                    </span>
                </div>
            </div>
        `;
    },

    showOnMap(lat, lon) {
        if (lat && lon && typeof EvacScanMap !== 'undefined') {
            EvacScanMap.flyTo(lat, lon, 10);
        }
    },

    formatTimeAgo(dateStr) {
        if (!dateStr) return 'Unknown';
        
        try {
            const date = new Date(dateStr);
            const now = new Date();
            const diffMs = now - date;
            const diffMins = Math.floor(diffMs / 60000);
            const diffHours = Math.floor(diffMs / 3600000);
            const diffDays = Math.floor(diffMs / 86400000);

            if (diffMins < 1) return 'Just now';
            if (diffMins < 60) return `${diffMins}m ago`;
            if (diffHours < 24) return `${diffHours}h ago`;
            if (diffDays < 7) return `${diffDays}d ago`;
            return date.toLocaleDateString();
        } catch {
            return 'Unknown';
        }
    },

    updateLastUpdated() {
        const el = document.getElementById('last-updated-text');
        if (el) {
            const now = new Date();
            el.textContent = `Updated ${now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
        }
    },

    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
};
