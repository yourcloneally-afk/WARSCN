/**
 * EvacScan - Map Controller
 */

const EvacScanMap = {
    map: null,
    layers: {
        events: null,
        heatmap: null,
        dangerZones: null,
        safeZones: null,
        route: null
    },
    markers: [],
    batteryMode: false,

    init() {
        this.map = L.map('map', {
            center: [31.5, 35.0],
            zoom: 6,
            zoomControl: false,
            attributionControl: false
        });

        // Add zoom control to bottom right
        L.control.zoom({ position: 'bottomright' }).addTo(this.map);

        // Dark tile layer
        const darkTiles = L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
            maxZoom: 19,
            subdomains: 'abcd'
        });

        const lightTiles = L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
            maxZoom: 19,
            subdomains: 'abcd'
        });

        // Use dark tiles by default
        darkTiles.addTo(this.map);
        this.darkTiles = darkTiles;
        this.lightTiles = lightTiles;

        // Initialize layer groups
        this.layers.events = L.layerGroup().addTo(this.map);
        this.layers.dangerZones = L.layerGroup().addTo(this.map);
        this.layers.safeZones = L.layerGroup().addTo(this.map);
        this.layers.route = L.layerGroup().addTo(this.map);

        // Load initial data
        this.loadEvents();
        this.loadDangerZones();

        // Watch for theme changes
        this.observeTheme();
    },

    observeTheme() {
        const observer = new MutationObserver(() => {
            const isLight = document.body.classList.contains('light-mode');
            if (isLight) {
                this.map.removeLayer(this.darkTiles);
                this.lightTiles.addTo(this.map);
            } else {
                this.map.removeLayer(this.lightTiles);
                this.darkTiles.addTo(this.map);
            }
        });
        observer.observe(document.body, { attributes: true, attributeFilter: ['class'] });
    },

    loadEvents() {
        fetch('/api/events')
            .then(r => r.json())
            .then(data => {
                this.updateEvents(data.events || []);
            })
            .catch(err => console.error('[Map] Events load failed:', err));
    },

    updateEvents(events) {
        this.layers.events.clearLayers();
        this.markers = [];

        events.forEach(event => {
            if (!event.lat || !event.lon) return;

            const severity = event.severity || 0;
            const color = severity >= 7 ? '#ef4444' : severity >= 4 ? '#f59e0b' : '#3b82f6';
            const radius = Math.max(6, Math.min(12, severity));

            const marker = L.circleMarker([event.lat, event.lon], {
                radius: radius,
                fillColor: color,
                fillOpacity: 0.8,
                color: '#fff',
                weight: 2
            });

            marker.bindPopup(`
                <div style="min-width: 200px;">
                    <div style="font-weight: 600; margin-bottom: 8px;">${event.title || 'Unknown Event'}</div>
                    <div style="font-size: 0.8rem; color: #888; margin-bottom: 4px;">
                        <i class="bi bi-geo-alt"></i> ${event.location || 'Unknown'}
                    </div>
                    <div style="font-size: 0.8rem; color: #888;">
                        <i class="bi bi-clock"></i> ${event.published_at || 'Unknown time'}
                    </div>
                </div>
            `);

            marker.addTo(this.layers.events);
            this.markers.push(marker);
        });

        // Update heatmap if not in battery mode
        if (!this.batteryMode && events.length > 0) {
            this.updateHeatmap(events);
        }
    },

    updateHeatmap(events) {
        if (this.layers.heatmap) {
            this.map.removeLayer(this.layers.heatmap);
        }

        const heatData = events
            .filter(e => e.lat && e.lon)
            .map(e => [e.lat, e.lon, (e.severity || 5) / 10]);

        if (heatData.length > 0) {
            this.layers.heatmap = L.heatLayer(heatData, {
                radius: 25,
                blur: 15,
                maxZoom: 10,
                gradient: {
                    0.2: '#3b82f6',
                    0.4: '#f59e0b',
                    0.6: '#ef4444',
                    1.0: '#dc2626'
                }
            }).addTo(this.map);
        }
    },

    loadDangerZones() {
        fetch('/api/danger_zones')
            .then(r => r.json())
            .then(data => {
                this.layers.dangerZones.clearLayers();
                
                if (data.geojson && data.geojson.features) {
                    L.geoJSON(data.geojson, {
                        style: {
                            fillColor: '#ef4444',
                            fillOpacity: 0.15,
                            color: '#ef4444',
                            weight: 1,
                            dashArray: '4'
                        }
                    }).addTo(this.layers.dangerZones);
                }
            })
            .catch(err => console.error('[Map] Danger zones load failed:', err));
    },

    loadSafeZones(lat, lon) {
        fetch(`/api/safe_zones?lat=${lat}&lon=${lon}`)
            .then(r => r.json())
            .then(data => {
                this.layers.safeZones.clearLayers();
                this.renderSafeZonesList(data.zones || []);

                (data.zones || []).forEach(zone => {
                    if (!zone.lat || !zone.lon) return;

                    const icon = L.divIcon({
                        className: 'safe-zone-marker',
                        html: `<div style="background: #10b981; width: 24px; height: 24px; border-radius: 50%; border: 2px solid #fff; display: flex; align-items: center; justify-content: center; box-shadow: 0 2px 8px rgba(0,0,0,0.3);"><i class="bi bi-plus" style="color: #fff; font-size: 14px;"></i></div>`,
                        iconSize: [24, 24],
                        iconAnchor: [12, 12]
                    });

                    L.marker([zone.lat, zone.lon], { icon })
                        .bindPopup(`<b>${zone.name || 'Safe Zone'}</b><br>${zone.type || ''}`)
                        .addTo(this.layers.safeZones);
                });
            })
            .catch(err => console.error('[Map] Safe zones load failed:', err));
    },

    renderSafeZonesList(zones) {
        const container = document.getElementById('safe-zones-list');
        if (!container) return;

        if (zones.length === 0) {
            container.innerHTML = '<p style="color: var(--ws-text-muted); font-size: 0.75rem;">No safe zones found nearby.</p>';
            return;
        }

        container.innerHTML = zones.slice(0, 5).map(zone => `
            <div class="safe-zone-item" onclick="EvacScanMap.flyTo(${zone.lat}, ${zone.lon}, 14)">
                <div class="safe-zone-icon">
                    <i class="bi bi-${zone.type === 'hospital' ? 'hospital' : zone.type === 'shelter' ? 'house' : 'geo-alt'}" style="color: var(--ws-success);"></i>
                </div>
                <div class="safe-zone-info">
                    <div class="safe-zone-name">${zone.name || 'Unknown'}</div>
                    <div class="safe-zone-type">${zone.type || 'Safe zone'}</div>
                </div>
            </div>
        `).join('');
    },

    showRoute(routeData) {
        this.layers.route.clearLayers();

        if (routeData.geometry && routeData.geometry.coordinates) {
            const coords = routeData.geometry.coordinates.map(c => [c[1], c[0]]);
            
            // Route line
            L.polyline(coords, {
                color: '#3b82f6',
                weight: 5,
                opacity: 0.8
            }).addTo(this.layers.route);

            // Start marker
            if (coords.length > 0) {
                L.circleMarker(coords[0], {
                    radius: 8,
                    fillColor: '#10b981',
                    fillOpacity: 1,
                    color: '#fff',
                    weight: 2
                }).addTo(this.layers.route);
            }

            // End marker
            if (coords.length > 1) {
                L.circleMarker(coords[coords.length - 1], {
                    radius: 8,
                    fillColor: '#ef4444',
                    fillOpacity: 1,
                    color: '#fff',
                    weight: 2
                }).addTo(this.layers.route);
            }

            // Fit bounds
            this.map.fitBounds(L.latLngBounds(coords), { padding: [50, 50] });
        }
    },

    clearRoute() {
        this.layers.route.clearLayers();
    },

    flyTo(lat, lon, zoom = 12) {
        this.map.flyTo([lat, lon], zoom, { duration: 1 });
    },

    centerOnUser() {
        if (App.currentLocation) {
            this.flyTo(App.currentLocation.lat, App.currentLocation.lon, 12);
        } else {
            Evacuation.getLocation();
        }
    },

    refreshAll() {
        this.loadEvents();
        this.loadDangerZones();
        if (App.currentLocation) {
            this.loadSafeZones(App.currentLocation.lat, App.currentLocation.lon);
        }
    },

    setBatteryMode(enabled) {
        this.batteryMode = enabled;
        if (enabled && this.layers.heatmap) {
            this.map.removeLayer(this.layers.heatmap);
        } else if (!enabled) {
            this.loadEvents();
        }
    },

    enableDestinationPick(callback) {
        this.map.once('click', (e) => {
            callback(e.latlng.lat, e.latlng.lng);
        });
        
        this.map.getContainer().style.cursor = 'crosshair';
        setTimeout(() => {
            this.map.getContainer().style.cursor = '';
        }, 10000);
    }
};
