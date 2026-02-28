import json
import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["DB_PATH"] = ":memory:"
os.environ["SECRET_KEY"] = "test-secret"

import config
config.DB_PATH = ":memory:"

import models


@pytest.fixture(autouse=True)
def setup_db(tmp_path):
    db_path = str(tmp_path / "test.db")
    config.DB_PATH = db_path
    models.init_db()
    yield
    config.DB_PATH = ":memory:"


@pytest.fixture
def sample_events():
    return [
        {
            "title": "Airstrike reported near Tehran",
            "description": "Multiple sources confirm an airstrike targeting military installations near Tehran.",
            "source_name": "GDELT",
            "source_url": "https://example.com/1",
            "timestamp": "2026-02-28T10:00:00+00:00",
            "location_text": "Tehran, Iran",
            "lat": 35.6892,
            "lon": 51.3890,
            "goldstein_scale": -9.0,
            "mention_count": 15,
            "raw": {},
        },
        {
            "title": "Airstrike hits military base in Tehran area",
            "description": "Unconfirmed reports of aerial bombardment near Tehran.",
            "source_name": "ReliefWeb",
            "source_url": "https://example.com/2",
            "timestamp": "2026-02-28T10:15:00+00:00",
            "location_text": "Tehran",
            "lat": 35.70,
            "lon": 51.40,
            "goldstein_scale": -8.5,
            "mention_count": 8,
            "raw": {},
        },
        {
            "title": "Airstrike in Iran confirmed by state media",
            "description": "Iranian state media confirms strikes on military targets.",
            "source_name": "Google News",
            "source_url": "https://example.com/3",
            "timestamp": "2026-02-28T10:30:00+00:00",
            "location_text": "Tehran, Iran",
            "lat": 35.69,
            "lon": 51.39,
            "goldstein_scale": -9.5,
            "mention_count": 25,
            "raw": {},
        },
        {
            "title": "Ceasefire negotiations underway in Geneva",
            "description": "Diplomatic talks between parties resume in Geneva.",
            "source_name": "ReliefWeb",
            "source_url": "https://example.com/4",
            "timestamp": "2026-02-28T12:00:00+00:00",
            "location_text": "Geneva, Switzerland",
            "lat": 46.2044,
            "lon": 6.1432,
            "goldstein_scale": 4.0,
            "mention_count": 5,
            "raw": {},
        },
        {
            "title": "Missile launch detected from southern region",
            "description": "Satellite imagery shows missile launch activity.",
            "source_name": "GDELT",
            "source_url": "https://example.com/5",
            "timestamp": "2026-02-28T11:00:00+00:00",
            "location_text": "Southern Iran",
            "lat": 30.0,
            "lon": 52.0,
            "goldstein_scale": -7.0,
            "mention_count": 10,
            "raw": {},
        },
    ]


@pytest.fixture
def sample_gdelt_response():
    return {
        "articles": [
            {
                "url": "https://example.com/article1",
                "title": "Iran conflict escalation report",
                "seendate": "20260228100000",
                "domain": "example.com",
                "sourcecountry": "Iran",
                "numarts": "5",
            },
            {
                "url": "https://example.com/article2",
                "title": "Israel defense updates amid tensions",
                "seendate": "20260228110000",
                "domain": "news.example.com",
                "sourcecountry": "Israel",
                "numarts": "3",
            },
        ]
    }


@pytest.fixture
def sample_reliefweb_response():
    return {
        "data": [
            {
                "fields": {
                    "title": "Humanitarian situation in Iran",
                    "body": "Aid organizations report...",
                    "url": "https://reliefweb.int/report/1",
                    "date": {"original": "2026-02-28T08:00:00+00:00"},
                    "country": [{"name": "Iran"}],
                    "source": [{"name": "OCHA"}],
                }
            }
        ]
    }


@pytest.fixture
def flask_client():
    from app import app
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client
