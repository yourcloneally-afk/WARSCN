"""Processing pipeline: geocoding, severity scoring, cross-verification,
deduplication, and threat level computation."""

import difflib
import logging
import math
import re
import time
from datetime import datetime, timezone

from geopy.distance import geodesic

import config
import models

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pre-built geocoding lookup — instant, no API calls needed
# Covers all major cities/regions mentioned in Iran/Israel conflict coverage
# ---------------------------------------------------------------------------

LOCATION_LOOKUP = {
    # Iran
    "iran":          (32.4279, 53.6880),
    "tehran":        (35.6892, 51.3890),
    "isfahan":       (32.6546, 51.6680),
    "shiraz":        (29.5918, 52.5836),
    "tabriz":        (38.0962, 46.2738),
    "mashhad":       (36.2972, 59.6067),
    "ahvaz":         (31.3183, 48.6706),
    "bushehr":       (28.9684, 50.8385),
    "natanz":        (33.5223, 51.8962),
    "fordo":         (34.8847, 50.9992),
    "arak":          (34.0954, 49.7013),
    "bandar abbas":  (27.1832, 56.2666),
    "qom":           (34.6416, 50.8746),
    "kermanshah":    (34.3142, 47.0650),
    "zahedan":       (29.4963, 60.8629),
    "rasht":         (37.2808, 49.5832),
    "irgc":          (35.6892, 51.3890),
    "khuzestan":     (31.3183, 48.6706),
    "hormuz":        (27.1000, 56.4667),
    "strait of hormuz": (26.5500, 56.2500),

    # Israel / Palestine
    "israel":        (31.0461, 34.8516),
    "tel aviv":      (32.0853, 34.7818),
    "jerusalem":     (31.7683, 35.2137),
    "haifa":         (32.7940, 34.9896),
    "beer sheva":    (31.2518, 34.7913),
    "eilat":         (29.5581, 34.9482),
    "netanya":       (32.3329, 34.8600),
    "ashdod":        (31.8044, 34.6553),
    "sderot":        (31.5247, 34.5964),
    "ashkelon":      (31.6688, 34.5743),
    "gaza":          (31.5017, 34.4668),
    "west bank":     (31.9522, 35.2332),
    "ramallah":      (31.9038, 35.2034),
    "idf":           (31.0461, 34.8516),
    "mossad":        (32.0853, 34.7818),

    # Lebanon
    "lebanon":       (33.8547, 35.8623),
    "beirut":        (33.8938, 35.5018),
    "southern lebanon": (33.2705, 35.2037),
    "hezbollah":     (33.8938, 35.5018),

    # Syria
    "syria":         (34.8021, 38.9968),
    "damascus":      (33.5138, 36.2765),
    "aleppo":        (36.2021, 37.1343),

    # Iraq
    "iraq":          (33.2232, 43.6793),
    "baghdad":       (33.3152, 44.3661),
    "erbil":         (36.1901, 44.0091),
    "mosul":         (36.3400, 43.1300),

    # Yemen / Houthis
    "yemen":         (15.5527, 48.5164),
    "sanaa":         (15.3694, 44.1910),
    "houthi":        (15.5527, 48.5164),
    "hodeidah":      (14.7975, 42.9540),
    "aden":          (12.7797, 45.0095),

    # Jordan
    "jordan":        (30.5852, 36.2384),
    "amman":         (31.9454, 35.9284),

    # Saudi Arabia
    "saudi arabia":  (23.8859, 45.0792),
    "riyadh":        (24.6877, 46.7219),
    "jeddah":        (21.3891, 39.8579),

    # Gulf states
    "uae":           (23.4241, 53.8478),
    "dubai":         (25.2048, 55.2708),
    "abu dhabi":     (24.4539, 54.3773),
    "qatar":         (25.3548, 51.1839),
    "doha":          (25.2854, 51.5310),
    "bahrain":       (26.0667, 50.5577),
    "kuwait":        (29.3759, 47.9774),
    "oman":          (21.4735, 55.9754),
    "muscat":        (23.5880, 58.3829),

    # Regional / key
    "middle east":   (29.2985, 42.5510),
    "persian gulf":  (26.5000, 53.0000),
    "red sea":       (20.0000, 38.0000),
    "mediterranean": (35.0000, 18.0000),

    # US (relevant context — specific sites only, no country centroid to avoid false pins)
    "washington dc":  (38.8951, -77.0369),
    "pentagon":       (38.8719, -77.0563),
    "mar-a-lago":     (26.6788, -80.0363),
    "white house":    (38.8977, -77.0365),
    "camp david":     (39.6476, -77.4661),

    # Pakistan / Afghanistan (separate conflict — only pin if very specific)
    "islamabad":      (33.7215, 73.0433),
    "kabul":          (34.5553, 69.2075),

    # Turkey (host of US bases, regional actor)
    "ankara":         (39.9334, 32.8597),
    "istanbul":       (41.0082, 28.9784),
    "incirlik":       (37.0013, 35.4257),

    # Cyprus (US carrier staging)
    "cyprus":         (35.1264, 33.4299),
    "nicosia":        (35.1856, 33.3823),

    # Egypt
    "egypt":          (26.8206, 30.8025),
    "cairo":          (30.0444, 31.2357),
    "suez canal":     (30.4538, 32.5498),
    "suez":           (29.9668, 32.5498),
}


def _extract_location(title, desc=""):
    """Fast lookup: scan title+description for known location keywords."""
    text = (title + " " + (desc or "")).lower()
    # Prioritise longer/more specific matches first
    for loc in sorted(LOCATION_LOOKUP.keys(), key=len, reverse=True):
        if loc in text:
            return loc, LOCATION_LOOKUP[loc]
    return None, (None, None)


def geocode(text):
    """Geocode using pre-built lookup table first, then SQLite cache, then Nominatim."""
    if not text or len(text.strip()) < 2:
        return None, None

    text_lower = text.strip().lower()

    # 1. Instant pre-built lookup
    if text_lower in LOCATION_LOOKUP:
        return LOCATION_LOOKUP[text_lower]

    # Partial match
    for loc in sorted(LOCATION_LOOKUP.keys(), key=len, reverse=True):
        if loc in text_lower:
            return LOCATION_LOOKUP[loc]

    # 2. SQLite cache
    cached = models.get_cached_geocode(text)
    if cached and cached[0] is not None:
        return cached

    # 3. Nominatim fallback — skip for very short/vague terms to avoid country centroids
    if len(text.strip()) < 5 or text.strip().lower() in {"us", "usa", "iran", "israel", "world"}:
        return None, None
    try:
        from geopy.geocoders import Nominatim
        geocoder = Nominatim(user_agent=config.GEOCODER_USER_AGENT, timeout=8)
        time.sleep(1.1)
        loc = geocoder.geocode(text)
        if loc:
            # Reject coordinates that map to USA geographic center or similar vague centroids
            if 38.5 < loc.latitude < 40.5 and -101 < loc.longitude < -93:
                return None, None  # USA geographic center — too vague
            models.cache_geocode(text, loc.latitude, loc.longitude)
            return loc.latitude, loc.longitude
    except Exception as e:
        logger.debug("Nominatim failed for '%s': %s", text, e)

    return None, None


# Vague country-level terms that should NOT produce a pin on the map
_VAGUE_LOCATIONS = {
    "united states", "usa", "u.s.", "america", "us",
    "iran", "israel", "world", "global", "international",
    "middle east", "region", "local", "online",
}


def enrich_with_coords(events):
    """
    Fill in lat/lon for events without coordinates.
    1. Scan title+description for known specific city/site locations (instant)
    2. Fall back to location_text geocoding (skip vague country terms)
    """
    for ev in events:
        if ev.get("lat") is not None and ev.get("lon") is not None:
            continue

        # Try extracting from title/description first (fast, city-level preferred)
        loc_name, (lat, lon) = _extract_location(
            ev.get("title", ""),
            ev.get("description", ""),
        )
        if lat is not None:
            ev["lat"] = lat
            ev["lon"] = lon
            if not ev.get("location_text"):
                ev["location_text"] = loc_name.title()
            continue

        # Fall back to location_text (but skip vague country names)
        loc_text = (ev.get("location_text", "") or "").strip().lower()
        if loc_text and loc_text not in _VAGUE_LOCATIONS and len(loc_text) > 3:
            lat, lon = geocode(loc_text)
            if lat is not None:
                ev["lat"] = lat
                ev["lon"] = lon

    return events


# ---------------------------------------------------------------------------
# Severity scoring
# ---------------------------------------------------------------------------

def compute_severity(event):
    """Multi-signal severity score [0, 1]."""
    score = 0.2  # baseline

    # Goldstein scale: ranges -10 (conflict) to +10 (cooperation)
    gs = event.get("goldstein_scale")
    if gs is not None:
        try:
            gs = float(gs)
            if gs < 0:
                score += min(abs(gs) / 10.0, 0.4) * 0.8
        except (ValueError, TypeError):
            pass

    # Keyword scan on title + description
    text = f"{event.get('title', '')} {event.get('description', '')}".lower()
    kw_boost = 0.0
    for keyword, weight in config.SEVERITY_KEYWORDS.items():
        if keyword in text:
            kw_boost += weight
    score += max(min(kw_boost, 0.5), -0.15)

    # TextBlob sentiment
    try:
        blob = TextBlob(text[:500])
        if blob.sentiment.polarity < -0.5:
            score += 0.15
        elif blob.sentiment.polarity < -0.2:
            score += 0.08
    except Exception:
        pass

    # Mention count boost
    mentions = event.get("mention_count", 1) or 1
    if mentions > 1:
        score += min(math.log2(mentions) * 0.04, 0.15)

    return max(0.0, min(1.0, score))


def classify_event_type(event):
    """Infer event_type from text content."""
    text = f"{event.get('title', '')} {event.get('description', '')}".lower()
    if any(w in text for w in ["nuclear", "uranium", "enrichment", "natanz", "fordo", "bushehr", "centrifuge"]):
        return "nuclear"
    if any(w in text for w in ["airstrike", "air strike", "bombing", "bomb", "explosion", "blast"]):
        return "strike"
    if any(w in text for w in ["missile", "rocket", "ballistic", "intercept", "iron dome", "arrow"]):
        return "missile"
    if any(w in text for w in ["drone", "uav", "unmanned"]):
        return "drone"
    if any(w in text for w in ["killed", "dead", "casualties", "fatalities", "wounded", "death toll"]):
        return "casualties"
    if any(w in text for w in ["troops", "invasion", "ground offensive", "deploy", "ground forces", "infantry"]):
        return "military"
    if any(w in text for w in ["diplomatic", "negotiat", "ceasefire", "peace", "summit", "deal", "agreement"]):
        return "diplomatic"
    if any(w in text for w in ["protest", "demonstrat", "rally", "uprising"]):
        return "protest"
    if any(w in text for w in ["humanitarian", "aid", "shelter", "refugee", "relief", "evacuat"]):
        return "humanitarian"
    if any(w in text for w in ["sanction", "embargo", "economy", "oil", "market"]):
        return "economic"
    # General conflict/war classification
    if any(w in text for w in ["war", "conflict", "attack", "offensive", "operation", "combat", "strike"]):
        return "conflict"
    return "unknown"


# ---------------------------------------------------------------------------
# Cross-verification and deduplication
# ---------------------------------------------------------------------------

def _events_are_proximate(e1, e2, km_threshold=50, hours_threshold=2):
    """Check if two events are close in space and time."""
    if e1.get("lat") and e2.get("lat") and e1.get("lon") and e2.get("lon"):
        dist = geodesic(
            (e1["lat"], e1["lon"]), (e2["lat"], e2["lon"])
        ).kilometers
        if dist > km_threshold:
            return False

    t1 = e1.get("timestamp", "")
    t2 = e2.get("timestamp", "")
    if t1 and t2:
        try:
            dt1 = datetime.fromisoformat(t1.replace("Z", "+00:00"))
            dt2 = datetime.fromisoformat(t2.replace("Z", "+00:00"))
            if abs((dt1 - dt2).total_seconds()) > hours_threshold * 3600:
                return False
        except Exception:
            pass
    return True


def cross_verify(events):
    """Group events into clusters by proximity, compute reliability and category."""
    n = len(events)
    visited = [False] * n
    clusters = []

    for i in range(n):
        if visited[i]:
            continue
        cluster = [i]
        visited[i] = True
        for j in range(i + 1, n):
            if visited[j]:
                continue
            if _events_are_proximate(events[i], events[j]):
                title_sim = difflib.SequenceMatcher(
                    None,
                    events[i].get("title", "").lower(),
                    events[j].get("title", "").lower(),
                ).ratio()
                if title_sim > 0.45:
                    cluster.append(j)
                    visited[j] = True
        clusters.append(cluster)

    for cluster_indices in clusters:
        cluster_events = [events[i] for i in cluster_indices]
        unique_sources = set(e.get("source_name", "") for e in cluster_events)
        source_count = len(unique_sources)

        if source_count >= 3:
            category = "confirmed"
            reliability = min(0.6 + source_count * 0.1, 1.0)
        elif source_count == 2:
            category = "developing"
            reliability = 0.5
        else:
            category = "rumored"
            reliability = 0.25

        for idx in cluster_indices:
            events[idx]["category"] = category
            events[idx]["reliability_score"] = reliability
            all_sources = []
            for ci in cluster_indices:
                src = events[ci].get("source_name", "")
                if src and src not in all_sources:
                    all_sources.append(src)
            events[idx]["sources"] = all_sources

    return events


def deduplicate(events):
    """Remove near-duplicate events, keeping the richest version."""
    if not events:
        return events

    kept = []
    skip = set()
    for i, ev in enumerate(events):
        if i in skip:
            continue
        best = ev
        for j in range(i + 1, len(events)):
            if j in skip:
                continue
            sim = difflib.SequenceMatcher(
                None,
                ev.get("title", "").lower(),
                events[j].get("title", "").lower(),
            ).ratio()
            if sim > 0.55 and _events_are_proximate(ev, events[j]):
                skip.add(j)
                if len(events[j].get("description", "")) > len(best.get("description", "")):
                    best = events[j]
                    best["sources"] = list(set(
                        best.get("sources", []) + ev.get("sources", [])
                    ))
        kept.append(best)
    return kept


# ---------------------------------------------------------------------------
# Full pipeline
# ---------------------------------------------------------------------------

def process_pipeline(raw_events):
    """Complete processing chain: enrich -> score -> verify -> dedup -> store."""
    if not raw_events:
        logger.info("No raw events to process")
        return 0

    logger.info("Processing %d raw events", len(raw_events))

    enrich_with_coords(raw_events)

    for ev in raw_events:
        ev["severity"] = compute_severity(ev)
        ev["event_type"] = classify_event_type(ev)

    cross_verify(raw_events)
    deduped = deduplicate(raw_events)

    # Map to DB schema
    db_events = []
    for ev in deduped:
        db_events.append({
            "title": ev.get("title", ""),
            "description": ev.get("description", ""),
            "location_name": ev.get("location_text", ""),
            "sources": ev.get("sources", [ev.get("source_name", "")]),
            "source_url": ev.get("source_url", ""),
            "reliability_score": ev.get("reliability_score", 0.25),
            "severity": ev.get("severity", 0.0),
            "lat": ev.get("lat"),
            "lon": ev.get("lon"),
            "category": ev.get("category", "rumored"),
            "event_type": ev.get("event_type", "unknown"),
            "goldstein_scale": ev.get("goldstein_scale"),
            "mention_count": ev.get("mention_count", 1),
            "timestamp": ev.get("timestamp", datetime.now(timezone.utc).isoformat()),
        })

    inserted = models.insert_events_batch(db_events)
    models.prune_old_events()
    logger.info("Inserted %d events after processing (from %d deduped)", inserted, len(deduped))
    return inserted
