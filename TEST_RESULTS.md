# WARSCAN – Localhost 1738 Test Results

**Server:** Running at http://127.0.0.1:1738 (start with `PORT=1738 SECRET_KEY=test python app.py`)

---

## Fix applied before testing

- **Index 500 error:** `render_template("index.html", **_ctx(), threat_level=threat)` was passing `threat_level` twice (it’s already in `_ctx()`). Updated to `return render_template("index.html", **_ctx())`. Index now returns **200**.

---

## What works

### Pages (all return 200)

| Page | URL | Status |
|------|-----|--------|
| Dashboard | `/` | 200 – map, threat banner, side panel, event feed |
| About | `/about` | 200 – data sources, privacy, limitations |
| Emergency resources | `/emergency` | 200 – numbers, embassies, first aid, go-bag |
| Safe report (valid token) | `/safe/<token>` | 200 – “X is Safe” message |
| Safe report (invalid/expired) | `/safe/nonexistent` | 404 – handled correctly |

### API GET (all 200)

| Endpoint | Purpose |
|----------|---------|
| `/api/events` | Event list (JSON); supports `category`, `hours`, `limit` |
| `/api/events/geojson` | Events as GeoJSON for map |
| `/api/danger_zones` | Danger polygons (GeoJSON) |
| `/api/safe_zones` | Safe zones; optional `?lat=&lon=&radius=` |
| `/api/threat_level` | Current threat level + label + action text |
| `/api/alerts` | Proximity alerts; optional `?lat=&lon=&radius=` |
| `/api/traffic_tile_url` | TomTom tile URL or null |

### API POST (all return success/expected behavior)

| Endpoint | Body | Result |
|----------|------|--------|
| `/api/set_location` | `{"lat", "lon"}` | `{"ok": true}` |
| `/api/route` | `{"start_lat", "start_lon", "end_lat", "end_lon"}` | Route GeoJSON + distance + steps (straight-line if no Geoapify key) |
| `/api/subscribe_alerts` | `{"phone", "email", "radius_km"}` | Subscription saved |
| `/api/safe_report` | `{"alias", "message", "city", "lat", "lon"}` | `{"ok", "url", "token"}` |
| `/api/set_language` | `{"lang": "en"\|"he"\|"fa"\|"ar"}` | `{"ok", "lang"}` |

### Static assets (all 200)

- `/static/css/style.css`
- `/static/js/app.js`, `map.js`, `events.js`, `alerts.js`, `evacuation.js`, `pdf-export.js`
- `/static/manifest.json`, `/static/service-worker.js`
- `/static/sounds/alert.wav` (alert notification sound)
- `/static/icons/icon-192.png`, `icon-512.png`

### Data and behavior

- **Threat level:** Resolves correctly (e.g. MODERATE with action “Monitor updates…”).
- **Events:** GDELT + Google RSS feed the DB; event list and GeoJSON return data.
- **Evacuation route:** Without Geoapify key, returns straight-line + warning; with key would return turn-by-turn.
- **Safe report:** Creates token and URL; `/safe/<token>` shows the “X is Safe” page.

---

## What to test manually in the browser

These need a real browser on http://127.0.0.1:1738:

1. **Map** – Loads; event markers; heatmap; danger zones; layer toggles; zoom/pan.
2. **“Use My Location”** – Asks for geolocation; sets location and updates map.
3. **Event feed** – Loads events; filter buttons (All / Confirmed / Developing / Rumored); click event → map flies to it.
4. **Evacuate tab** – Set destination (click map or type coords) → “Calculate Safe Route” → route appears on map; steps and “Download PDF” work.
5. **Alert bell** – Offcanvas with alert history (empty until first push).
6. **Subscribe alerts** – Form submit; “Enable Alerts” stores phone/email/radius.
7. **“I’m Safe” FAB** – Opens modal; submit → copy/share link; `/safe/<token>` works.
8. **Language dropdown** – EN/HE/FA/AR; page reloads with new language.
9. **Theme toggle** – Dark/light; persists in localStorage.
10. **Battery saver** – Toggle; reduces refresh rate and disables heatmap.
11. **SocketIO** – Real-time updates when scheduler pushes new events (every 5 min or after refresh).
12. **Service worker** – After first load, offline or slow network still serves cached shell/API.

---

## Known limitations / notes

| Item | Note |
|------|------|
| **ReliefWeb** | 403 with default `appname=warscan`; requires pre-approved appname. App still works without it. |
| **Routing** | Without `GEOAPIFY_API_KEY`, route is straight-line + warning. |
| **Traffic layer** | Without `TOMTOM_API_KEY`, traffic tile URL is null; layer not shown. |
| **Alert sound** | File is WAV, served as `/static/sounds/alert.wav`; works in modern browsers. |
| **GET /api/route** | Correctly returns 405; route endpoint is POST-only. |

---

## Summary

- **All server routes and APIs** tested and working (pages 200, APIs 200/404/405 as designed).
- **Fix:** Index 500 was due to duplicate `threat_level`; fixed so dashboard loads.
- **Manual check:** Use the list above in the browser to confirm map, buttons, modals, and real-time behavior.
