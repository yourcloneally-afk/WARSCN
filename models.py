import json
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import config


def get_db_path():
    return config.DB_PATH


@contextmanager
def get_db():
    conn = sqlite3.connect(get_db_path(), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with get_db() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                title_hash TEXT UNIQUE,
                description TEXT,
                location_name TEXT,
                sources TEXT DEFAULT '[]',
                source_url TEXT,
                reliability_score REAL DEFAULT 0.0,
                severity REAL DEFAULT 0.0,
                lat REAL,
                lon REAL,
                category TEXT DEFAULT 'rumored',
                event_type TEXT DEFAULT 'unknown',
                goldstein_scale REAL,
                mention_count INTEGER DEFAULT 1,
                timestamp TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_events_severity ON events(severity);
            CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp);
            CREATE INDEX IF NOT EXISTS idx_events_coords ON events(lat, lon);

            CREATE TABLE IF NOT EXISTS safe_zones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                type TEXT,
                lat REAL NOT NULL,
                lon REAL NOT NULL,
                address TEXT,
                phone TEXT,
                country TEXT,
                last_verified TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS user_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT UNIQUE NOT NULL,
                lat REAL,
                lon REAL,
                phone TEXT,
                email TEXT,
                alert_radius_km INTEGER DEFAULT 100,
                alerts_enabled INTEGER DEFAULT 0,
                language TEXT DEFAULT 'en',
                last_notified_event_id INTEGER DEFAULT 0,
                updated_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS geocode_cache (
                location_text TEXT PRIMARY KEY,
                lat REAL,
                lon REAL,
                cached_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS safe_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token TEXT UNIQUE NOT NULL,
                alias TEXT,
                message TEXT,
                city TEXT,
                lat REAL,
                lon REAL,
                created_at TEXT DEFAULT (datetime('now')),
                expires_at TEXT
            );
        """)


# ---------------------------------------------------------------------------
# Events CRUD
# ---------------------------------------------------------------------------

def _title_hash(title: str) -> str:
    import hashlib
    return hashlib.sha1(title.lower().strip()[:300].encode()).hexdigest()


def insert_events_batch(events):
    """Insert a list of event dicts, skipping duplicates by title hash."""
    if not events:
        return 0
    inserted = 0
    with get_db() as db:
        # Migrate: add columns if they don't exist yet
        try:
            db.execute("ALTER TABLE events ADD COLUMN title_hash TEXT")
        except Exception:
            pass
        try:
            db.execute("ALTER TABLE events ADD COLUMN source_url TEXT")
        except Exception:
            pass
        try:
            db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_events_title_hash ON events(title_hash)")
        except Exception:
            pass

        for ev in events:
            title = ev.get("title", "")
            if not title.strip():
                continue
            sources_json = json.dumps(ev.get("sources", []))
            th = _title_hash(title)
            try:
                db.execute(
                    """INSERT OR IGNORE INTO events
                       (title, title_hash, description, location_name, sources, source_url,
                        reliability_score, severity, lat, lon, category,
                        event_type, goldstein_scale, mention_count, timestamp)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        title,
                        th,
                        ev.get("description", ""),
                        ev.get("location_name", ""),
                        sources_json,
                        ev.get("source_url", ""),
                        ev.get("reliability_score", 0.0),
                        ev.get("severity", 0.0),
                        ev.get("lat"),
                        ev.get("lon"),
                        ev.get("category", "rumored"),
                        ev.get("event_type", "unknown"),
                        ev.get("goldstein_scale"),
                        ev.get("mention_count", 1),
                        ev.get("timestamp", datetime.now(timezone.utc).isoformat()),
                    ),
                )
                if db.execute("SELECT changes()").fetchone()[0]:
                    inserted += 1
            except sqlite3.IntegrityError:
                continue
    return inserted


def get_events(category=None, event_type=None, min_severity=None,
               limit=200, offset=0, hours=None):
    clauses = []
    params = []
    if category:
        clauses.append("category = ?")
        params.append(category)
    if event_type:
        clauses.append("event_type = ?")
        params.append(event_type)
    if min_severity is not None:
        clauses.append("severity >= ?")
        params.append(min_severity)
    if hours:
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        clauses.append("timestamp >= ?")
        params.append(cutoff)

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    query = f"SELECT * FROM events {where} ORDER BY timestamp DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    with get_db() as db:
        rows = db.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def get_nearby_events(lat, lon, radius_km, hours=6, min_severity=0.5):
    """Approximate bounding-box filter then Haversine refine."""
    deg = radius_km / 111.0
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    with get_db() as db:
        rows = db.execute(
            """SELECT * FROM events
               WHERE lat BETWEEN ? AND ?
                 AND lon BETWEEN ? AND ?
                 AND severity >= ?
                 AND timestamp >= ?
               ORDER BY severity DESC""",
            (lat - deg, lat + deg, lon - deg, lon + deg, min_severity, cutoff),
        ).fetchall()
    return [dict(r) for r in rows]


def get_threat_level(lat=None, lon=None, radius_km=100):
    """Compute aggregate threat level: CRITICAL/HIGH/MODERATE/LOW/UNKNOWN."""
    if lat is None or lon is None:
        events = get_events(hours=6, min_severity=0.4, limit=500)
    else:
        events = get_nearby_events(lat, lon, radius_km, hours=6, min_severity=0.3)

    if not events:
        return "UNKNOWN"

    confirmed_high = sum(
        1 for e in events if e["category"] == "confirmed" and e["severity"] >= 0.7
    )
    developing = sum(1 for e in events if e["category"] == "developing")
    max_severity = max(e["severity"] for e in events)

    if confirmed_high >= 3 or max_severity >= 0.9:
        return "CRITICAL"
    if confirmed_high >= 1 or max_severity >= 0.7:
        return "HIGH"
    if developing >= 2 or max_severity >= 0.4:
        return "MODERATE"
    return "LOW"


def prune_old_events(hours=None):
    hours = hours or config.MAX_EVENTS_AGE_HOURS
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    with get_db() as db:
        db.execute("DELETE FROM events WHERE timestamp < ?", (cutoff,))


# ---------------------------------------------------------------------------
# User sessions
# ---------------------------------------------------------------------------

def upsert_session(session_id, **kwargs):
    with get_db() as db:
        existing = db.execute(
            "SELECT id FROM user_sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
        if existing:
            sets = ", ".join(f"{k} = ?" for k in kwargs)
            vals = list(kwargs.values()) + [session_id]
            db.execute(
                f"UPDATE user_sessions SET {sets}, updated_at = datetime('now') WHERE session_id = ?",
                vals,
            )
        else:
            cols = ["session_id"] + list(kwargs.keys())
            placeholders = ", ".join(["?"] * len(cols))
            vals = [session_id] + list(kwargs.values())
            db.execute(
                f"INSERT INTO user_sessions ({', '.join(cols)}) VALUES ({placeholders})",
                vals,
            )


def get_session(session_id):
    with get_db() as db:
        row = db.execute(
            "SELECT * FROM user_sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
    return dict(row) if row else None


def get_alert_subscribers():
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM user_sessions WHERE alerts_enabled = 1 AND lat IS NOT NULL"
        ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Geocode cache
# ---------------------------------------------------------------------------

def get_cached_geocode(text):
    with get_db() as db:
        row = db.execute(
            "SELECT lat, lon FROM geocode_cache WHERE location_text = ?", (text,)
        ).fetchone()
    return (row["lat"], row["lon"]) if row else None


def cache_geocode(text, lat, lon):
    with get_db() as db:
        db.execute(
            "INSERT OR REPLACE INTO geocode_cache (location_text, lat, lon) VALUES (?, ?, ?)",
            (text, lat, lon),
        )


# ---------------------------------------------------------------------------
# Safe zones
# ---------------------------------------------------------------------------

def upsert_safe_zones(zones):
    with get_db() as db:
        for z in zones:
            db.execute(
                """INSERT OR REPLACE INTO safe_zones (name, type, lat, lon, address, phone, country)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (z.get("name"), z.get("type"), z["lat"], z["lon"],
                 z.get("address"), z.get("phone"), z.get("country")),
            )


def get_safe_zones(lat=None, lon=None, radius_km=50):
    if lat is not None and lon is not None:
        deg = radius_km / 111.0
        with get_db() as db:
            rows = db.execute(
                """SELECT * FROM safe_zones
                   WHERE lat BETWEEN ? AND ? AND lon BETWEEN ? AND ?""",
                (lat - deg, lat + deg, lon - deg, lon + deg),
            ).fetchall()
    else:
        with get_db() as db:
            rows = db.execute("SELECT * FROM safe_zones LIMIT 200").fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# "I'm Safe" reports
# ---------------------------------------------------------------------------

def create_safe_report(token, alias, message, city, lat, lon):
    expires = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
    with get_db() as db:
        db.execute(
            """INSERT INTO safe_reports (token, alias, message, city, lat, lon, expires_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (token, alias, message, city, lat, lon, expires),
        )


def get_safe_report(token):
    with get_db() as db:
        row = db.execute(
            "SELECT * FROM safe_reports WHERE token = ? AND expires_at > datetime('now')",
            (token,),
        ).fetchone()
    return dict(row) if row else None


def prune_expired_reports():
    with get_db() as db:
        db.execute("DELETE FROM safe_reports WHERE expires_at < datetime('now')")
