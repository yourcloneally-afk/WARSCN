"""WARSCAN -- Real-Time Conflict Monitor & Evacuation Tool.

Flask-SocketIO application with APScheduler background data refresh.
"""

import json
import logging
import os
import secrets
from datetime import datetime, timezone

import bleach
from apscheduler.schedulers.background import BackgroundScheduler
from flask import (
    Flask, jsonify, render_template, request, session, redirect, url_for,
)
from flask_socketio import SocketIO, join_room

import alert_utils
import api_utils
import config
import map_utils
import models
import utils
from translations import t, is_rtl

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config["SECRET_KEY"] = config.SECRET_KEY
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet" if not config.DEBUG else "threading")

scheduler = BackgroundScheduler(daemon=True)


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------

def _refresh_data():
    """Background job: fetch from all sources, process, push to clients."""
    try:
        raw = api_utils.fetch_all()
        count = utils.process_pipeline(raw)
        logger.info("Refresh complete: %d new events stored", count)

        if count > 0:
            events = models.get_events(hours=6, limit=50)
            threat = models.get_threat_level()
            socketio.emit("new_events", {"count": count, "threat_level": threat})
            socketio.emit("threat_level_update", {"level": threat})

            alert_utils.process_subscriptions(socketio)
    except Exception as e:
        logger.error("Data refresh failed: %s", e)


@app.before_request
def _ensure_session():
    if "sid" not in session:
        session["sid"] = secrets.token_urlsafe(16)
        session["lang"] = _detect_language()


def _detect_language():
    accept = request.headers.get("Accept-Language", "en")
    for lang in ["he", "fa", "ar"]:
        if lang in accept:
            return lang
    return "en"


def _lang():
    return session.get("lang", "en")


def _ctx():
    """Common template context."""
    lang = _lang()
    return {
        "t": lambda key, **kw: t(key, lang, **kw),
        "lang": lang,
        "is_rtl": is_rtl(lang),
        "threat_level": models.get_threat_level(),
        "has_tomtom": config.HAS_TOMTOM,
        "has_geoapify": config.HAS_GEOAPIFY,
    }


# ---------------------------------------------------------------------------
# Page routes
# ---------------------------------------------------------------------------

@app.route("/")
def landing():
    return render_template("landing.html", **_ctx())


@app.route("/dashboard")
def index():
    return render_template("index.html", **_ctx())


@app.route("/about")
def about():
    enabled_sources = ["GDELT", "ReliefWeb", "Google News RSS"]
    if config.HAS_NEWSDATA:
        enabled_sources.append("NewsData.io")
    if config.HAS_ACLED:
        enabled_sources.append("ACLED")
    if config.HAS_MEDIASTACK:
        enabled_sources.append("Mediastack")
    return render_template("about.html", **_ctx(), sources=enabled_sources)


@app.route("/emergency")
def emergency():
    return render_template("emergency.html", **_ctx())


@app.route("/safe/<token>")
def safe_page(token):
    report = models.get_safe_report(token)
    if not report:
        return render_template("about.html", **_ctx(), error="Report expired or not found."), 404
    return render_template("safe.html", **_ctx(), report=report)


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------

@app.route("/api/events")
def api_events():
    category = request.args.get("category")
    event_type = request.args.get("event_type")
    min_sev = request.args.get("min_severity", type=float)
    hours = request.args.get("hours", 24, type=int)
    limit = min(request.args.get("limit", 200, type=int), 500)
    events = models.get_events(
        category=category, event_type=event_type,
        min_severity=min_sev, hours=hours, limit=limit,
    )
    return jsonify({"events": events, "count": len(events)})


@app.route("/api/events/geojson")
def api_events_geojson():
    hours = request.args.get("hours", 24, type=int)
    events = models.get_events(hours=hours, limit=500)
    return jsonify(map_utils.events_to_geojson(events))


@app.route("/api/danger_zones")
def api_danger_zones():
    events = models.get_events(hours=12, min_severity=0.6, limit=200)
    return jsonify(map_utils.build_danger_zones(events))


@app.route("/api/safe_zones")
def api_safe_zones():
    lat = request.args.get("lat", type=float)
    lon = request.args.get("lon", type=float)
    radius = request.args.get("radius", 50, type=int)
    if lat is not None and lon is not None:
        return jsonify(map_utils.find_safe_zones(lat, lon, radius))
    cached = models.get_safe_zones()
    return jsonify(map_utils.safe_zones_to_geojson(cached))


@app.route("/api/route", methods=["POST"])
def api_route():
    data = request.get_json(silent=True) or {}

    # Accept both formats: flat keys or origin/destination arrays [lon, lat]
    origin = data.get("origin")
    destination = data.get("destination")

    if origin and destination and len(origin) == 2 and len(destination) == 2:
        start_lon, start_lat = float(origin[0]), float(origin[1])
        end_lon, end_lat = float(destination[0]), float(destination[1])
    else:
        start_lat = data.get("start_lat")
        start_lon = data.get("start_lon")
        end_lat = data.get("end_lat")
        end_lon = data.get("end_lon")

    if not all([start_lat, start_lon, end_lat, end_lon]):
        return jsonify({"error": "Missing coordinates. Provide origin/destination arrays or start_lat/start_lon/end_lat/end_lon."}), 400

    events = models.get_events(hours=12, min_severity=0.6, limit=200)
    danger = map_utils.build_danger_zones(events)
    result = map_utils.calculate_evacuation_route(
        float(start_lat), float(start_lon), float(end_lat), float(end_lon), danger
    )
    return jsonify(result)


@app.route("/api/threat_level")
def api_threat_level():
    lat = request.args.get("lat", type=float)
    lon = request.args.get("lon", type=float)
    level = models.get_threat_level(lat, lon)
    lang = _lang()
    level_key = f"threat_{level.lower()}"
    action_key = f"action_{level.lower()}"
    return jsonify({
        "level": level,
        "label": t(level_key, lang),
        "action": t(action_key, lang),
    })


@app.route("/api/alerts")
def api_alerts():
    lat = request.args.get("lat", type=float)
    lon = request.args.get("lon", type=float)
    if lat is None or lon is None:
        return jsonify({"alerts": [], "count": 0})
    radius = request.args.get("radius", config.ALERT_RADIUS_KM, type=int)
    nearby = alert_utils.check_proximity(lat, lon, radius)
    return jsonify({"alerts": nearby[:20], "count": len(nearby)})


@app.route("/api/set_location", methods=["POST"])
def api_set_location():
    data = request.get_json(silent=True) or {}
    lat = data.get("lat")
    lon = data.get("lon")
    if lat is None or lon is None:
        return jsonify({"error": "Missing lat/lon"}), 400
    models.upsert_session(session.get("sid", "anon"), lat=lat, lon=lon)
    return jsonify({"ok": True})


@app.route("/api/subscribe_alerts", methods=["POST"])
def api_subscribe():
    data = request.get_json(silent=True) or {}
    sid = session.get("sid", "anon")
    phone = bleach.clean(data.get("phone", ""))
    email = bleach.clean(data.get("email", ""))
    radius = min(data.get("radius_km", config.ALERT_RADIUS_KM), 500)
    models.upsert_session(
        sid, phone=phone, email=email,
        alert_radius_km=radius, alerts_enabled=1,
    )
    return jsonify({"ok": True, "message": "Subscribed to alerts"})


@app.route("/api/safe_report", methods=["POST"])
def api_safe_report():
    data = request.get_json(silent=True) or {}
    alias = bleach.clean(data.get("alias", "Someone"))[:50]
    message = bleach.clean(data.get("message", "I'm safe"))[:200]
    city = bleach.clean(data.get("city", ""))[:100]
    lat = data.get("lat")
    lon = data.get("lon")

    token = secrets.token_urlsafe(12)
    models.create_safe_report(token, alias, message, city, lat, lon)
    url = f"/safe/{token}"
    return jsonify({"ok": True, "url": url, "token": token})


@app.route("/api/set_language", methods=["POST"])
def api_set_language():
    data = request.get_json(silent=True) or {}
    lang = data.get("lang", "en")
    if lang in ("en", "he", "fa", "ar"):
        session["lang"] = lang
        models.upsert_session(session.get("sid", "anon"), language=lang)
    return jsonify({"ok": True, "lang": session.get("lang", "en")})


@app.route("/api/traffic_tile_url")
def api_traffic_tile():
    url = map_utils.get_traffic_tile_url()
    return jsonify({"url": url})


# ---------------------------------------------------------------------------
# SocketIO events
# ---------------------------------------------------------------------------

@socketio.on("connect")
def handle_connect():
    sid = session.get("sid")
    if sid:
        join_room(sid)
    logger.debug("Client connected: %s", sid)


@socketio.on("request_update")
def handle_request_update():
    events = models.get_events(hours=6, limit=50)
    threat = models.get_threat_level()
    socketio.emit("new_events", {"count": len(events), "threat_level": threat}, room=request.sid)


# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------

@app.errorhandler(404)
def not_found(e):
    if request.path.startswith("/api/"):
        return jsonify({"error": "Not found"}), 404
    return render_template("about.html", **_ctx(), error="Page not found"), 404


@app.errorhandler(500)
def server_error(e):
    logger.error("500 error: %s", e)
    if request.path.startswith("/api/"):
        return jsonify({"error": "Internal server error"}), 500
    return render_template("about.html", **_ctx(), error="Something went wrong"), 500


# ---------------------------------------------------------------------------
# App startup
# ---------------------------------------------------------------------------

def create_app():
    models.init_db()
    if not scheduler.running:
        scheduler.add_job(
            _refresh_data, "interval",
            seconds=config.POLL_INTERVAL_SEC,
            id="data_refresh",
            replace_existing=True,
        )
        scheduler.start()
        logger.info("Scheduler started (interval=%ds)", config.POLL_INTERVAL_SEC)

    # Run initial fetch in background after a short delay
    scheduler.add_job(_refresh_data, "date", id="initial_fetch", replace_existing=True)

    models.prune_expired_reports()
    return app


create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 1738))
    import eventlet
    sock = eventlet.listen(("0.0.0.0", port))
    sock.setsockopt(__import__("socket").SOL_SOCKET, __import__("socket").SO_REUSEADDR, 1)
    eventlet.wsgi.server(sock, app, log_output=False)
