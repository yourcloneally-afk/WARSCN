import json
import pytest
import responses
import api_utils
import config


class TestFetchGdelt:
    @responses.activate
    def test_returns_normalized_events(self, sample_gdelt_response):
        responses.add(
            responses.GET,
            config.GDELT_API_URL,
            json=sample_gdelt_response,
            status=200,
        )
        results = api_utils.fetch_gdelt()
        assert len(results) == 2
        assert results[0]["title"] == "Iran conflict escalation report"
        assert results[0]["source_name"] == "example.com"
        assert "timestamp" in results[0]

    @responses.activate
    def test_handles_empty_response(self):
        responses.add(
            responses.GET,
            config.GDELT_API_URL,
            json={"articles": []},
            status=200,
        )
        results = api_utils.fetch_gdelt()
        assert results == []

    @responses.activate
    def test_handles_malformed_json(self):
        responses.add(
            responses.GET,
            config.GDELT_API_URL,
            body="not json",
            status=200,
        )
        with pytest.raises(Exception):
            api_utils.fetch_gdelt()


class TestFetchReliefweb:
    @responses.activate
    def test_returns_normalized_events(self, sample_reliefweb_response):
        api_url = f"{config.RELIEFWEB_API_URL}?appname={config.RELIEFWEB_APPNAME}"
        for country in config.FOCUS_COUNTRIES:
            responses.add(
                responses.POST,
                api_url,
                json=sample_reliefweb_response,
                status=200,
            )
        results = api_utils.fetch_reliefweb()
        assert len(results) >= 1
        assert results[0]["title"] == "Humanitarian situation in Iran"

    @responses.activate
    def test_handles_api_failure(self):
        api_url = f"{config.RELIEFWEB_API_URL}?appname={config.RELIEFWEB_APPNAME}"
        for _ in config.FOCUS_COUNTRIES:
            responses.add(
                responses.POST,
                api_url,
                status=500,
            )
        # Should not raise, just return partial/empty
        results = api_utils.fetch_reliefweb()
        assert isinstance(results, list)


class TestFetchGoogleRss:
    @responses.activate
    def test_returns_events_from_rss(self):
        rss_xml = """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
            <channel>
                <item>
                    <title>Iran conflict update</title>
                    <link>https://example.com/news1</link>
                    <description>Details about the conflict.</description>
                    <pubDate>Sat, 28 Feb 2026 10:00:00 GMT</pubDate>
                </item>
            </channel>
        </rss>"""
        responses.add(
            responses.GET,
            config.GOOGLE_NEWS_RSS_URL,
            body=rss_xml,
            status=200,
            content_type="application/rss+xml",
        )
        results = api_utils.fetch_google_rss()
        assert len(results) >= 1
        assert "Iran" in results[0]["title"]


class TestFetchPikudHaoref:
    @responses.activate
    def test_handles_empty_response(self):
        responses.add(
            responses.GET,
            "https://www.oref.org.il/WarningMessages/alert/alerts.json",
            body="",
            status=200,
        )
        results = api_utils.fetch_pikud_haoref()
        assert results == []

    @responses.activate
    def test_handles_geo_restriction(self):
        responses.add(
            responses.GET,
            "https://www.oref.org.il/WarningMessages/alert/alerts.json",
            status=403,
        )
        results = api_utils.fetch_pikud_haoref()
        assert results == []


class TestFetchNewsdata:
    def test_skips_when_no_key(self):
        original = config.HAS_NEWSDATA
        config.HAS_NEWSDATA = False
        results = api_utils.fetch_newsdata()
        assert results == []
        config.HAS_NEWSDATA = original


class TestFetchAcled:
    def test_skips_when_no_key(self):
        original = config.HAS_ACLED
        config.HAS_ACLED = False
        results = api_utils.fetch_acled()
        assert results == []
        config.HAS_ACLED = original


class TestFetchMediastack:
    def test_skips_when_no_key(self):
        original = config.HAS_MEDIASTACK
        config.HAS_MEDIASTACK = False
        results = api_utils.fetch_mediastack()
        assert results == []
        config.HAS_MEDIASTACK = original


class TestFetchAll:
    @responses.activate
    def test_aggregates_multiple_sources(self, sample_gdelt_response, sample_reliefweb_response):
        responses.add(responses.GET, config.GDELT_API_URL, json=sample_gdelt_response, status=200)
        api_url = f"{config.RELIEFWEB_API_URL}?appname={config.RELIEFWEB_APPNAME}"
        for _ in config.FOCUS_COUNTRIES:
            responses.add(responses.POST, api_url, json=sample_reliefweb_response, status=200)
        responses.add(responses.GET, config.GOOGLE_NEWS_RSS_URL, body="<rss><channel></channel></rss>", status=200)
        responses.add(responses.GET, "https://www.oref.org.il/WarningMessages/alert/alerts.json", body="", status=200)

        results = api_utils.fetch_all()
        assert isinstance(results, list)
        assert len(results) >= 2  # At least GDELT + ReliefWeb
