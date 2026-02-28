import json
import pytest
import responses
import map_utils


class TestEventsToGeojson:
    def test_valid_geojson_structure(self, sample_events):
        db_events = []
        for e in sample_events:
            db_events.append({
                "id": 1,
                "title": e["title"],
                "description": e["description"],
                "severity": 0.8,
                "category": "confirmed",
                "event_type": "strike",
                "reliability_score": 0.9,
                "sources": json.dumps(["GDELT", "ReliefWeb"]),
                "timestamp": e["timestamp"],
                "mention_count": e["mention_count"],
                "lat": e["lat"],
                "lon": e["lon"],
            })
        result = map_utils.events_to_geojson(db_events)
        assert result["type"] == "FeatureCollection"
        assert len(result["features"]) > 0
        feat = result["features"][0]
        assert feat["type"] == "Feature"
        assert feat["geometry"]["type"] == "Point"
        assert len(feat["geometry"]["coordinates"]) == 2
        assert "severity" in feat["properties"]
        assert "title" in feat["properties"]

    def test_skips_events_without_coords(self):
        events = [{"title": "No coords", "lat": None, "lon": None, "severity": 0.5}]
        result = map_utils.events_to_geojson(events)
        assert len(result["features"]) == 0

    def test_empty_events(self):
        result = map_utils.events_to_geojson([])
        assert result["type"] == "FeatureCollection"
        assert result["features"] == []


class TestBuildDangerZones:
    def test_creates_polygons_for_high_severity(self):
        events = [
            {"lat": 35.0, "lon": 51.0, "severity": 0.9},
            {"lat": 35.1, "lon": 51.1, "severity": 0.8},
        ]
        result = map_utils.build_danger_zones(events, buffer_km=20)
        assert result["type"] == "FeatureCollection"
        assert len(result["features"]) >= 1
        geom_type = result["features"][0]["geometry"]["type"]
        assert geom_type in ("Polygon", "MultiPolygon")

    def test_empty_for_low_severity(self):
        events = [
            {"lat": 35.0, "lon": 51.0, "severity": 0.2},
        ]
        result = map_utils.build_danger_zones(events)
        assert len(result["features"]) == 0

    def test_empty_events(self):
        result = map_utils.build_danger_zones([])
        assert len(result["features"]) == 0

    def test_merges_overlapping_zones(self):
        events = [
            {"lat": 35.0, "lon": 51.0, "severity": 0.9},
            {"lat": 35.01, "lon": 51.01, "severity": 0.9},
        ]
        result = map_utils.build_danger_zones(events, buffer_km=50)
        assert len(result["features"]) == 1  # Should merge into single polygon


class TestCalculateEvacuationRoute:
    def test_straight_line_fallback_no_api_key(self):
        import config
        original = config.HAS_GEOAPIFY
        config.HAS_GEOAPIFY = False
        result = map_utils.calculate_evacuation_route(35.0, 51.0, 36.0, 52.0)
        assert result["success"] is True
        assert result["warning"] is not None
        assert result["distance_km"] > 0
        assert result["geojson"]["type"] == "FeatureCollection"
        config.HAS_GEOAPIFY = original

    @responses.activate
    def test_geoapify_route_parsing(self):
        import config
        original_key = config.GEOAPIFY_API_KEY
        original_flag = config.HAS_GEOAPIFY
        config.GEOAPIFY_API_KEY = "test-key"
        config.HAS_GEOAPIFY = True

        mock_response = {
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "geometry": {"type": "LineString", "coordinates": [[51.0, 35.0], [52.0, 36.0]]},
                "properties": {
                    "distance": 150000,
                    "time": 7200,
                    "legs": [{
                        "steps": [{
                            "instruction": {"text": "Head north"},
                            "distance": 150000,
                            "time": 7200,
                        }]
                    }],
                },
            }],
        }
        responses.add(
            responses.GET,
            "https://api.geoapify.com/v1/routing",
            json=mock_response,
            status=200,
        )
        result = map_utils.calculate_evacuation_route(35.0, 51.0, 36.0, 52.0)
        assert result["success"] is True
        assert result["distance_km"] == 150.0
        assert result["duration_min"] == 120
        assert len(result["steps"]) == 1
        assert result["steps"][0]["instruction"] == "Head north"

        config.GEOAPIFY_API_KEY = original_key
        config.HAS_GEOAPIFY = original_flag


class TestSafeZonesToGeojson:
    def test_valid_structure(self):
        zones = [
            {"name": "Hospital A", "type": "hospital", "lat": 35.0, "lon": 51.0, "address": "123 St", "phone": "+123"},
            {"name": "Embassy B", "type": "embassy", "lat": 35.1, "lon": 51.1, "address": "", "phone": ""},
        ]
        result = map_utils.safe_zones_to_geojson(zones)
        assert result["type"] == "FeatureCollection"
        assert len(result["features"]) == 2
        assert result["features"][0]["properties"]["name"] == "Hospital A"
