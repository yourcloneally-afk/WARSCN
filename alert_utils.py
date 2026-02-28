"""Alert system: proximity detection, WebSocket push, SMS (Twilio), email."""

import logging
import smtplib
from email.mime.text import MIMEText

from geopy.distance import geodesic

import config
import models
from translations import t

logger = logging.getLogger(__name__)


def check_proximity(user_lat, user_lon, radius_km=None):
    """Find recent high-severity events within radius of user location."""
    radius_km = radius_km or config.ALERT_RADIUS_KM
    nearby = models.get_nearby_events(
        user_lat, user_lon, radius_km, hours=6, min_severity=0.5
    )

    results = []
    for ev in nearby:
        if ev.get("lat") is None or ev.get("lon") is None:
            continue
        dist = geodesic(
            (user_lat, user_lon), (ev["lat"], ev["lon"])
        ).kilometers
        if dist <= radius_km:
            ev["distance_km"] = round(dist, 1)
            results.append(ev)

    results.sort(key=lambda e: e["distance_km"])
    return results


def severity_label(severity):
    if severity >= 0.7:
        return "HIGH"
    if severity >= 0.4:
        return "MEDIUM"
    return "LOW"


def format_alert_message(event, distance_km=None, lang="en"):
    """Format a human-readable alert message."""
    dist = distance_km or event.get("distance_km", "?")
    title = event.get("title", "Unknown event")
    level = severity_label(event.get("severity", 0))
    sources = event.get("sources", "[]")
    if isinstance(sources, str):
        import json
        try:
            sources = json.loads(sources)
        except Exception:
            sources = []
    source_count = len(sources) if isinstance(sources, list) else 1

    line1 = t("alert_nearby", lang, title=title, distance=dist)
    line2 = t("alert_severity", lang, level=level, sources=source_count)
    return f"{line1}\n{line2}"


# ---------------------------------------------------------------------------
# Notification channels
# ---------------------------------------------------------------------------

def send_sms(phone, message):
    """Send SMS via Twilio. Fails silently with logging."""
    if not config.HAS_TWILIO:
        logger.debug("Twilio not configured, skipping SMS")
        return False
    try:
        from twilio.rest import Client
        client = Client(config.TWILIO_ACCOUNT_SID, config.TWILIO_AUTH_TOKEN)
        client.messages.create(
            body=message[:1600],
            from_=config.TWILIO_PHONE,
            to=phone,
        )
        logger.info("SMS sent to %s", phone[:4] + "****")
        return True
    except Exception as e:
        logger.error("SMS send failed: %s", e)
        return False


def send_email(to_addr, subject, body):
    """Send email via SMTP with STARTTLS. Fails silently with logging."""
    if not config.HAS_EMAIL:
        logger.debug("Email not configured, skipping")
        return False
    try:
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = subject
        msg["From"] = config.ALERT_EMAIL_USER
        msg["To"] = to_addr

        with smtplib.SMTP(config.ALERT_EMAIL_SMTP, 587, timeout=10) as server:
            server.starttls()
            server.login(config.ALERT_EMAIL_USER, config.ALERT_EMAIL_PASS)
            server.send_message(msg)
        logger.info("Email sent to %s", to_addr)
        return True
    except Exception as e:
        logger.error("Email send failed: %s", e)
        return False


# ---------------------------------------------------------------------------
# Subscription processing (called by scheduler)
# ---------------------------------------------------------------------------

def process_subscriptions(socketio=None):
    """For each opted-in subscriber, check proximity and notify."""
    subscribers = models.get_alert_subscribers()
    if not subscribers:
        return

    for sub in subscribers:
        lat, lon = sub.get("lat"), sub.get("lon")
        if lat is None or lon is None:
            continue

        radius = sub.get("alert_radius_km", config.ALERT_RADIUS_KM)
        nearby = check_proximity(lat, lon, radius)

        last_notified = sub.get("last_notified_event_id", 0) or 0
        new_alerts = [e for e in nearby if e.get("id", 0) > last_notified and e.get("severity", 0) >= 0.6]

        if not new_alerts:
            continue

        lang = sub.get("language", "en")
        top_alert = new_alerts[0]
        msg = format_alert_message(top_alert, lang=lang)

        # WebSocket push
        if socketio:
            try:
                socketio.emit("alert", {
                    "message": msg,
                    "event": {
                        "id": top_alert.get("id"),
                        "title": top_alert.get("title"),
                        "severity": top_alert.get("severity"),
                        "distance_km": top_alert.get("distance_km"),
                        "lat": top_alert.get("lat"),
                        "lon": top_alert.get("lon"),
                        "category": top_alert.get("category"),
                    },
                }, room=sub["session_id"])
            except Exception as e:
                logger.error("WebSocket push failed: %s", e)

        # SMS
        phone = sub.get("phone")
        if phone:
            send_sms(phone, msg)

        # Email
        email = sub.get("email")
        if email:
            send_email(email, "WARSCAN Alert", msg)

        # Update last notified
        models.upsert_session(
            sub["session_id"],
            last_notified_event_id=top_alert.get("id", 0),
        )
