# WARSCAN -- Real-Time Conflict Monitor & Evacuation Tool

A Flask-based web application that aggregates verified conflict data from multiple independent sources, visualizes threats on an interactive map, computes evacuation routes avoiding danger zones, and delivers real-time proximity alerts. Designed for civilians, aid workers, and journalists in or near conflict zones.

**Works with zero paid API keys.** Free data sources (GDELT, ReliefWeb, Google News RSS) provide baseline coverage out of the box. Optional paid APIs enhance data depth.

---

## Quick Start (Local)

```bash
# Clone and enter the project
git clone <your-repo-url>
cd Warscan

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Download TextBlob corpora (one time)
python -m textblob.download_corpora

# Configure
cp .env.example .env
# Edit .env and set SECRET_KEY (required), add optional API keys

# Run
flask run
# Or with SocketIO support:
python app.py
```

Open http://localhost:5000

---

## Deploy to Railway

1. Push this code to a GitHub repository
2. Go to [railway.app](https://railway.app) and create a new project
3. Select **Deploy from GitHub repo** and connect your repository
4. Go to the **Variables** tab and add:
   - `SECRET_KEY` = any random string (required)
   - Add any optional API keys from the table below
5. Railway will auto-detect the `Procfile` and deploy

The app will be live at your Railway-provided URL within minutes.

---

## API Keys

| Service | What it adds | Env Var | Required | Sign Up |
|---------|-------------|---------|----------|---------|
| *(none)* | GDELT, ReliefWeb, Google News RSS work with no keys | -- | -- | -- |
| NewsData.io | 87K+ news sources, 206 countries | `NEWSDATA_API_KEY` | No | [newsdata.io](https://newsdata.io/register) |
| ACLED | Academic conflict data with precise geo + fatalities | `ACLED_API_KEY` + `ACLED_EMAIL` | No | [acleddata.com](https://acleddata.com/register) |
| Mediastack | Additional global news coverage | `MEDIASTACK_API_KEY` | No | [mediastack.com](https://mediastack.com/signup) |
| Geoapify | Turn-by-turn evacuation routing | `GEOAPIFY_API_KEY` | No | [geoapify.com](https://myprojects.geoapify.com/register) |
| TomTom | Real-time traffic overlay on map | `TOMTOM_API_KEY` | No | [developer.tomtom.com](https://developer.tomtom.com/user/register) |
| Twilio | SMS alert delivery | `TWILIO_ACCOUNT_SID` + `TWILIO_AUTH_TOKEN` + `TWILIO_PHONE` | No | [twilio.com](https://www.twilio.com/try-twilio) |

---

## Features

- **Threat Level Banner** -- Color-coded real-time threat assessment (CRITICAL/HIGH/MODERATE/LOW) with actionable advice
- **Interactive Map** -- Leaflet.js with event markers, heatmap, danger zone polygons, safe zone locations, and evacuation routes
- **Multi-Source Verification** -- Events cross-referenced across sources: 3+ sources = Confirmed, 2 = Developing, 1 = Rumored
- **Evacuation Router** -- Calculates routes avoiding active danger zones (Geoapify), with turn-by-turn directions
- **Real-Time Alerts** -- WebSocket push notifications for nearby threats, with browser notifications and optional SMS/email
- **"I'm Safe" Feature** -- Generate a shareable link to tell family you're safe (no accounts needed)
- **PDF Evacuation Plan** -- Download a printable PDF with route, directions, and emergency contacts (works offline)
- **Emergency Resources** -- Pre-cached page with emergency numbers, embassy contacts, first aid, go-bag checklist
- **PWA / Offline Mode** -- Installable as a phone app, works offline with cached data and map tiles
- **4 Languages** -- English, Hebrew (עברית), Persian (فارسی), Arabic (العربية) with RTL support
- **Dark Mode** -- Default dark theme with light mode toggle, battery saver mode
- **Accessibility** -- ARIA landmarks, keyboard navigation, reduced motion support, high contrast mode

---

## Architecture

```
Browser (PWA) <--WebSocket--> Flask-SocketIO <--Scheduler--> GDELT / ReliefWeb / RSS / APIs
                                    |
                                 SQLite (events.db)
```

- **Backend**: Flask + Flask-SocketIO + APScheduler
- **Frontend**: Bootstrap 5.3 + Leaflet.js + vanilla JavaScript
- **Data refresh**: Every 5 minutes via background scheduler
- **Caching**: SQLite for events + geocode cache; Service Worker for offline

---

## Running Tests

```bash
pip install -r requirements.txt
pytest tests/ -v
```

---

## Project Structure

```
app.py              Flask app, routes, SocketIO, scheduler
config.py           Environment variables and feature flags
models.py           SQLite schema and CRUD helpers
api_utils.py        Multi-source data fetchers (7 sources)
utils.py            Processing pipeline (geocode, score, verify, dedup)
map_utils.py        GeoJSON, danger zones, routing, safe zones
alert_utils.py      Proximity detection, SMS, email, WebSocket push
translations.py     Lightweight i18n (EN/HE/FA/AR)
templates/          Jinja2 HTML templates
static/             CSS, JavaScript, PWA manifest, service worker
tests/              pytest test suite
```

---

## Disclaimer

WARSCAN aggregates publicly available data from third-party sources. It is **not a substitute for official emergency services** or government directives. Always verify critical information with official sources. Evacuation routes are computed using civilian road data and may not reflect current ground conditions. Severity scores are algorithmic estimates, not expert assessments.

---

## License

MIT
