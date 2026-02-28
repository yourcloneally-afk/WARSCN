import json
import pytest
import models
import alert_utils
import config


class TestCheckProximity:
    def test_finds_nearby_events(self):
        models.insert_events_batch([
            {
                "title": "Nearby strike",
                "description": "Close to user",
                "location_name": "Tehran",
                "lat": 35.70,
                "lon": 51.40,
                "severity": 0.8,
                "category": "confirmed",
                "timestamp": "2026-02-28T10:00:00+00:00",
            },
            {
                "title": "Far away event",
                "description": "Far from user",
                "location_name": "London",
                "lat": 51.50,
                "lon": -0.12,
                "severity": 0.9,
                "category": "confirmed",
                "timestamp": "2026-02-28T10:00:00+00:00",
            },
        ])
        results = alert_utils.check_proximity(35.69, 51.39, radius_km=50)
        assert len(results) >= 1
        titles = [r["title"] for r in results]
        assert "Nearby strike" in titles
        assert "Far away event" not in titles

    def test_respects_radius(self):
        models.insert_events_batch([{
            "title": "Distant event",
            "lat": 40.0, "lon": 55.0, "severity": 0.9,
            "category": "confirmed",
            "timestamp": "2026-02-28T10:00:00+00:00",
        }])
        results = alert_utils.check_proximity(35.0, 51.0, radius_km=10)
        assert len(results) == 0

    def test_includes_distance(self):
        models.insert_events_batch([{
            "title": "Close event",
            "lat": 35.70, "lon": 51.40, "severity": 0.8,
            "category": "confirmed",
            "timestamp": "2026-02-28T10:00:00+00:00",
        }])
        results = alert_utils.check_proximity(35.69, 51.39, radius_km=50)
        assert len(results) >= 1
        assert "distance_km" in results[0]
        assert results[0]["distance_km"] < 50


class TestSeverityLabel:
    def test_high(self):
        assert alert_utils.severity_label(0.8) == "HIGH"

    def test_medium(self):
        assert alert_utils.severity_label(0.5) == "MEDIUM"

    def test_low(self):
        assert alert_utils.severity_label(0.2) == "LOW"


class TestFormatAlertMessage:
    def test_contains_key_info(self):
        event = {
            "title": "Missile launch detected",
            "severity": 0.85,
            "sources": json.dumps(["GDELT", "ReliefWeb", "ACLED"]),
        }
        msg = alert_utils.format_alert_message(event, distance_km=30)
        assert "Missile launch" in msg
        assert "30" in msg
        assert "3" in msg  # source count

    def test_handles_missing_data(self):
        event = {"title": "Unknown", "severity": 0.3, "sources": "[]"}
        msg = alert_utils.format_alert_message(event)
        assert "Unknown" in msg


class TestSendSms:
    def test_skips_when_not_configured(self):
        original = config.HAS_TWILIO
        config.HAS_TWILIO = False
        result = alert_utils.send_sms("+1234567890", "Test")
        assert result is False
        config.HAS_TWILIO = original


class TestSendEmail:
    def test_skips_when_not_configured(self):
        original = config.HAS_EMAIL
        config.HAS_EMAIL = False
        result = alert_utils.send_email("test@test.com", "Subject", "Body")
        assert result is False
        config.HAS_EMAIL = original
