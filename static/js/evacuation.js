/**
 * WARSCAN - Evacuation Controller
 */

const Evacuation = {
    origin: null,
    destination: null,
    currentRoute: null,

    getLocation() {
        const statusEl = document.getElementById('user-location-text');
        
        if (!navigator.geolocation) {
            statusEl.innerHTML = '<i class="bi bi-x-circle" style="color: var(--ws-danger);"></i> Geolocation not supported';
            return;
        }

        statusEl.innerHTML = '<i class="bi bi-arrow-repeat spin"></i> Getting location...';

        navigator.geolocation.getCurrentPosition(
            (pos) => {
                const lat = pos.coords.latitude;
                const lon = pos.coords.longitude;
                
                this.origin = { lat, lon };
                App.setLocation(lat, lon);
                
                statusEl.innerHTML = `<i class="bi bi-check-circle" style="color: var(--ws-success);"></i> ${lat.toFixed(4)}, ${lon.toFixed(4)}`;
                
                // Center map and load safe zones
                if (typeof WarscanMap !== 'undefined') {
                    WarscanMap.flyTo(lat, lon, 10);
                    WarscanMap.loadSafeZones(lat, lon);
                }
            },
            (err) => {
                console.error('[Evacuation] Geolocation error:', err);
                statusEl.innerHTML = `<i class="bi bi-x-circle" style="color: var(--ws-danger);"></i> Location access denied`;
            },
            { enableHighAccuracy: true, timeout: 10000 }
        );
    },

    pickFromMap() {
        if (typeof WarscanMap !== 'undefined') {
            const input = document.getElementById('dest-input');
            input.placeholder = 'Click on the map...';
            input.value = '';
            
            WarscanMap.enableDestinationPick((lat, lon) => {
                this.destination = { lat, lon };
                input.value = `${lat.toFixed(4)}, ${lon.toFixed(4)}`;
                input.placeholder = 'Click map or enter coords';
            });
        }
    },

    calculate() {
        if (!this.origin) {
            alert('Please set your location first.');
            return;
        }

        // Parse destination from input if not set via map
        if (!this.destination) {
            const input = document.getElementById('dest-input').value;
            const match = input.match(/(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)/);
            if (match) {
                this.destination = { lat: parseFloat(match[1]), lon: parseFloat(match[2]) };
            } else {
                alert('Please set a destination.');
                return;
            }
        }

        const btn = document.getElementById('calc-route-btn');
        btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Calculating...';
        btn.disabled = true;

        fetch('/api/route', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                origin: [this.origin.lon, this.origin.lat],
                destination: [this.destination.lon, this.destination.lat]
            })
        })
        .then(r => r.json())
        .then(data => {
            btn.innerHTML = '<i class="bi bi-signpost-split-fill"></i> Calculate Route';
            btn.disabled = false;

            if (data.error) {
                alert('Route calculation failed: ' + data.error);
                return;
            }

            this.currentRoute = data;
            this.displayRoute(data);
        })
        .catch(err => {
            console.error('[Evacuation] Route error:', err);
            btn.innerHTML = '<i class="bi bi-signpost-split-fill"></i> Calculate Route';
            btn.disabled = false;
            alert('Route calculation failed.');
        });
    },

    displayRoute(data) {
        const results = document.getElementById('route-results');
        results.classList.remove('d-none');

        // Distance & duration
        const distance = data.distance_km || (data.distance / 1000);
        const duration = data.duration_min || Math.round(data.duration / 60);
        
        document.getElementById('route-distance').textContent = distance.toFixed(1);
        document.getElementById('route-duration').textContent = duration;

        // Warning if route passes through danger zones
        const warning = document.getElementById('route-warning');
        if (data.passes_danger_zone) {
            warning.classList.remove('d-none');
            warning.querySelector('span').textContent = 'This route passes near active threat zones. Exercise caution.';
        } else {
            warning.classList.add('d-none');
        }

        // Steps
        const stepsContainer = document.getElementById('route-steps');
        if (data.steps && data.steps.length > 0) {
            stepsContainer.innerHTML = data.steps.map((step, i) => `
                <div class="route-step">
                    <div class="step-number">${i + 1}</div>
                    <div class="step-text">${step.instruction || step.text || 'Continue'}</div>
                    <div class="step-distance">${step.distance ? (step.distance / 1000).toFixed(1) + ' km' : ''}</div>
                </div>
            `).join('');
        } else {
            stepsContainer.innerHTML = '<p style="color: var(--ws-text-muted); font-size: 0.8rem;">Detailed directions not available.</p>';
        }

        // Show on map
        if (typeof WarscanMap !== 'undefined' && data.geometry) {
            WarscanMap.showRoute(data);
        }
    }
};

// CSS for spinner
const style = document.createElement('style');
style.textContent = `
    .spin {
        animation: spin 1s linear infinite;
    }
    @keyframes spin {
        from { transform: rotate(0deg); }
        to { transform: rotate(360deg); }
    }
`;
document.head.appendChild(style);
