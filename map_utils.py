"""Mapping utilities: GeoJSON generation, danger zone buffering,
evacuation routing (Geoapify), safe zone queries (Overpass), traffic tiles."""

import json
import logging
import math

import requests
from shapely.geometry import Point, mapping
from shapely.ops import unary_union

import config
import models

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# GeoJSON generation
# ---------------------------------------------------------------------------

def events_to_geojson(events):
    """Convert a list of event dicts to a GeoJSON FeatureCollection."""
    features = []
    for ev in events:
        if ev.get("lat") is None or ev.get("lon") is None:
            continue
        sources = ev.get("sources", "[]")
        if isinstance(sources, str):
            try:
                sources = json.loads(sources)
            except (json.JSONDecodeError, TypeError):
                sources = [sources] if sources else []

        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [ev["lon"], ev["lat"]],
            },
            "properties": {
                "id": ev.get("id"),
                "title": ev.get("title", ""),
                "description": (ev.get("description", "") or "")[:300],
                "severity": ev.get("severity", 0),
                "category": ev.get("category", "rumored"),
                "event_type": ev.get("event_type", "unknown"),
                "reliability_score": ev.get("reliability_score", 0),
                "sources": sources,
                "source_count": len(sources) if isinstance(sources, list) else 1,
                "timestamp": ev.get("timestamp", ""),
                "mention_count": ev.get("mention_count", 1),
            },
        })
    return {"type": "FeatureCollection", "features": features}


# ---------------------------------------------------------------------------
# Danger zones
# ---------------------------------------------------------------------------

def build_danger_zones(events, buffer_km=None):
    """Build buffered polygons around high-severity events."""
    buffer_km = buffer_km or config.DANGER_BUFFER_KM
    buffer_deg = buffer_km / 111.0  # approximate degrees

    high_sev = [
        e for e in events
        if e.get("lat") is not None
        and e.get("lon") is not None
        and (e.get("severity", 0) or 0) >= 0.6
    ]

    if not high_sev:
        return {"type": "FeatureCollection", "features": []}

    polygons = []
    for ev in high_sev:
        pt = Point(ev["lon"], ev["lat"])
        severity = ev.get("severity", 0.6)
        scaled_buffer = buffer_deg * (0.5 + severity)
        polygons.append(pt.buffer(scaled_buffer))

    merged = unary_union(polygons)

    if merged.geom_type == "Polygon":
        features = [{"type": "Feature", "geometry": mapping(merged), "properties": {"zone": "danger"}}]
    elif merged.geom_type == "MultiPolygon":
        features = [
            {"type": "Feature", "geometry": mapping(poly), "properties": {"zone": "danger"}}
            for poly in merged.geoms
        ]
    else:
        features = []

    return {"type": "FeatureCollection", "features": features}


# ---------------------------------------------------------------------------
# Evacuation routing (Geoapify)
# ---------------------------------------------------------------------------

def calculate_evacuation_route(start_lat, start_lon, end_lat, end_lon, danger_zones=None):
    """Calculate route via Geoapify, avoiding danger zones if possible."""
    if not config.HAS_GEOAPIFY:
        return _straight_line_fallback(start_lat, start_lon, end_lat, end_lon)

    try:
        url = "https://api.geoapify.com/v1/routing"
        params = {
            "waypoints": f"{start_lat},{start_lon}|{end_lat},{end_lon}",
            "mode": "drive",
            "apiKey": config.GEOAPIFY_API_KEY,
        }

        if danger_zones and danger_zones.get("features"):
            avoid_areas = []
            for feat in danger_zones["features"][:5]:
                geom = feat.get("geometry", {})
                coords = geom.get("coordinates", [])
                if geom.get("type") == "Polygon" and coords:
                    ring = coords[0]
                    pts = "|".join(f"{c[1]},{c[0]}" for c in ring[:20])
                    avoid_areas.append(pts)
            if avoid_areas:
                params["avoid"] = ";".join(avoid_areas[:3])

        resp = requests.get(url, params=params, timeout=20)
        resp.raise_for_status()
        data = resp.json()

        if not data.get("features"):
            return _straight_line_fallback(start_lat, start_lon, end_lat, end_lon)

        route_feature = data["features"][0]
        props = route_feature.get("properties", {})
        legs = props.get("legs", [{}])
        steps = []
        for leg in legs:
            for step in leg.get("steps", []):
                steps.append({
                    "instruction": step.get("instruction", {}).get("text", ""),
                    "distance_m": step.get("distance", 0),
                    "duration_s": step.get("time", 0),
                })

        return {
            "success": True,
            "geojson": data,
            "distance_km": round(props.get("distance", 0) / 1000, 1),
            "duration_min": round(props.get("time", 0) / 60, 0),
            "steps": steps,
            "warning": None,
        }
    except Exception as e:
        logger.error("Geoapify routing failed: %s", e)
        return _straight_line_fallback(start_lat, start_lon, end_lat, end_lon)


def _straight_line_fallback(lat1, lon1, lat2, lon2):
    """Fallback when no routing API is available."""
    from geopy.distance import geodesic
    dist = geodesic((lat1, lon1), (lat2, lon2)).kilometers
    return {
        "success": True,
        "geojson": {
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[lon1, lat1], [lon2, lat2]],
                },
                "properties": {},
            }],
        },
        "distance_km": round(dist, 1),
        "duration_min": None,
        "steps": [{"instruction": "Straight-line distance (no routing API configured)", "distance_m": dist * 1000, "duration_s": 0}],
        "warning": "No routing API key configured. Showing straight-line distance. Set GEOAPIFY_API_KEY for turn-by-turn routing.",
    }


# ---------------------------------------------------------------------------
# Safe zones (Overpass API)
# ---------------------------------------------------------------------------

def find_safe_zones(lat, lon, radius_km=50):
    """Query Overpass API for hospitals, embassies, shelters, border crossings."""
    radius_m = radius_km * 1000
    query = f"""
    [out:json][timeout:15];
    (
      node["amenity"="hospital"](around:{radius_m},{lat},{lon});
      node["amenity"="embassy"](around:{radius_m},{lat},{lon});
      node["emergency"="shelter"](around:{radius_m},{lat},{lon});
      node["amenity"="shelter"](around:{radius_m},{lat},{lon});
      node["barrier"="border_control"](around:{radius_m},{lat},{lon});
      node["office"="diplomatic"](around:{radius_m},{lat},{lon});
    );
    out body;
    """
    try:
        resp = requests.post(
            "https://overpass-api.de/api/interpreter",
            data={"data": query},
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
        zones = []
        for el in data.get("elements", []):
            tags = el.get("tags", {})
            zone_type = _classify_safe_zone(tags)
            zones.append({
                "name": tags.get("name", zone_type.title()),
                "type": zone_type,
                "lat": el.get("lat"),
                "lon": el.get("lon"),
                "address": tags.get("addr:full", tags.get("addr:street", "")),
                "phone": tags.get("phone", tags.get("contact:phone", "")),
                "country": tags.get("addr:country", ""),
            })
        models.upsert_safe_zones(zones)
        logger.info("Overpass returned %d safe zones", len(zones))
        return safe_zones_to_geojson(zones)
    except Exception as e:
        logger.warning("Overpass query failed: %s. Falling back to cached data.", e)
        cached = models.get_safe_zones(lat, lon, radius_km)
        return safe_zones_to_geojson(cached)


def _classify_safe_zone(tags):
    if tags.get("amenity") == "hospital":
        return "hospital"
    if tags.get("amenity") == "embassy" or tags.get("office") == "diplomatic":
        return "embassy"
    if "shelter" in tags.get("amenity", "") or "shelter" in tags.get("emergency", ""):
        return "shelter"
    if tags.get("barrier") == "border_control":
        return "border"
    return "other"


def safe_zones_to_geojson(zones):
    features = []
    for z in zones:
        if z.get("lat") is None or z.get("lon") is None:
            continue
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [z["lon"], z["lat"]]},
            "properties": {
                "name": z.get("name", ""),
                "type": z.get("type", "other"),
                "address": z.get("address", ""),
                "phone": z.get("phone", ""),
            },
        })
    return {"type": "FeatureCollection", "features": features}


# ---------------------------------------------------------------------------
# Traffic tiles
# ---------------------------------------------------------------------------

def get_traffic_tile_url():
    """Return TomTom traffic raster tile URL template, or None."""
    if not config.HAS_TOMTOM:
        return None
    return (
        f"https://api.tomtom.com/traffic/map/4/tile/flow/relative0/"
        f"{{z}}/{{x}}/{{y}}.png?key={config.TOMTOM_API_KEY}&tileSize=256"
    )
