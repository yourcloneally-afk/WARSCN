import pytest
import models
import utils
import config


class TestComputeSeverity:
    def test_high_severity_airstrike(self):
        event = {
            "title": "Airstrike hits military base",
            "description": "Massive casualties reported after bombing",
            "goldstein_scale": -9.0,
            "mention_count": 20,
        }
        sev = utils.compute_severity(event)
        assert sev >= 0.7, f"Airstrike with -9 goldstein should be high severity, got {sev}"

    def test_low_severity_diplomatic(self):
        event = {
            "title": "Peace negotiations resume in Geneva",
            "description": "Ceasefire talks continue between parties",
            "goldstein_scale": 4.0,
            "mention_count": 3,
        }
        sev = utils.compute_severity(event)
        assert sev < 0.4, f"Peace/ceasefire should be low severity, got {sev}"

    def test_severity_clamped_to_range(self):
        event = {
            "title": "nuclear airstrike missile bombing casualties killed",
            "description": "nuclear airstrike missile bombing casualties killed",
            "goldstein_scale": -10.0,
            "mention_count": 1000,
        }
        sev = utils.compute_severity(event)
        assert 0.0 <= sev <= 1.0

    def test_missing_goldstein(self):
        event = {
            "title": "Unknown event",
            "description": "Something happened",
            "goldstein_scale": None,
            "mention_count": 1,
        }
        sev = utils.compute_severity(event)
        assert 0.0 <= sev <= 1.0

    def test_keyword_boosting(self):
        event_with = {"title": "Missile strike reported", "description": "", "mention_count": 1}
        event_without = {"title": "Report filed today", "description": "", "mention_count": 1}
        sev_with = utils.compute_severity(event_with)
        sev_without = utils.compute_severity(event_without)
        assert sev_with > sev_without


class TestClassifyEventType:
    def test_strike(self):
        assert utils.classify_event_type({"title": "Airstrike on base", "description": ""}) == "strike"

    def test_missile(self):
        assert utils.classify_event_type({"title": "Rocket fired from south", "description": ""}) == "missile"

    def test_diplomatic(self):
        assert utils.classify_event_type({"title": "Peace negotiations begin", "description": ""}) == "diplomatic"

    def test_humanitarian(self):
        assert utils.classify_event_type({"title": "Humanitarian aid convoy arrives", "description": ""}) == "humanitarian"

    def test_unknown(self):
        assert utils.classify_event_type({"title": "Something happened", "description": ""}) == "unknown"


class TestCrossVerify:
    def test_three_sources_confirmed(self, sample_events):
        events = sample_events[:3]  # Three about Tehran airstrike
        result = utils.cross_verify(events)
        confirmed = [e for e in result if e["category"] == "confirmed"]
        assert len(confirmed) >= 1, "3 corroborating sources should produce at least 1 confirmed event"

    def test_single_source_rumored(self, sample_events):
        events = [sample_events[4]]  # Missile launch, single source
        result = utils.cross_verify(events)
        assert result[0]["category"] == "rumored"

    def test_reliability_increases_with_sources(self, sample_events):
        single = utils.cross_verify([sample_events[4]])
        multi = utils.cross_verify(sample_events[:3])
        max_single = max(e["reliability_score"] for e in single)
        max_multi = max(e["reliability_score"] for e in multi)
        assert max_multi > max_single


class TestDeduplicate:
    def test_removes_duplicates(self, sample_events):
        events = sample_events[:3]
        for e in events:
            e["sources"] = [e["source_name"]]
        deduped = utils.deduplicate(events)
        assert len(deduped) < len(events), "Should merge near-duplicate events"

    def test_keeps_distinct_events(self, sample_events):
        distinct = [sample_events[0], sample_events[3]]  # Tehran vs Geneva
        for e in distinct:
            e["sources"] = [e["source_name"]]
        deduped = utils.deduplicate(distinct)
        assert len(deduped) == 2, "Distinct events should not be merged"

    def test_empty_input(self):
        assert utils.deduplicate([]) == []


class TestGeocodeCache:
    def test_cache_roundtrip(self):
        models.cache_geocode("Tehran, Iran", 35.6892, 51.3890)
        result = models.get_cached_geocode("Tehran, Iran")
        assert result is not None
        assert abs(result[0] - 35.6892) < 0.001
        assert abs(result[1] - 51.3890) < 0.001

    def test_cache_miss(self):
        result = models.get_cached_geocode("Nonexistent Place XYZ")
        assert result is None
