"""Multi-source conflict data fetchers — Iran/Israel/US focus.

Strategy:
  1. Multiple targeted Google News RSS queries (Iran/Israel/war specific)
  2. Direct RSS feeds from major Middle East news outlets
  3. GDELT with tight CAMEO filter
  4. Pikud HaOref real-time alerts
  5. Strict relevance filter — articles MUST mention conflict keywords
"""

import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from urllib.parse import quote_plus

import feedparser
import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

import config

logger = logging.getLogger(__name__)

_retry = retry(
    wait=wait_exponential(min=2, max=30),
    stop=stop_after_attempt(2),
    retry=retry_if_exception_type((requests.RequestException, requests.Timeout)),
    reraise=False,
)

# ---------------------------------------------------------------------------
# Two-condition relevance filter
# Article must mention at least one LOCATION keyword AND one ACTION keyword.
# This prevents "Pakistan bombs Kabul", "daylight saving", AIPAC domestic news, etc.
# ---------------------------------------------------------------------------

_LOC_KW = {
    # Iran & nuclear programme
    "iran", "iranian", "irgc", "tehran", "khamenei", "natanz", "fordo",
    "bushehr", "arak", "isfahan", "qom", "ahvaz", "bandar abbas",
    "revolutionary guard", "rouhani", "raisi", "pezeshkian",
    # Israel
    "israel", "israeli", "idf", "netanyahu", "tel aviv", "haifa",
    "jerusalem", "mossad", "iron dome", "arrow missile",
    # Gulf / UAE
    "dubai", "abu dhabi", "uae", "united arab emirates",
    "bahrain", "kuwait", "qatar", "doha", "saudi arabia", "riyadh",
    "oman", "muscat",
    # Strait / waterways
    "strait of hormuz", "persian gulf", "red sea", "gulf of oman",
    # Regional actors / conflicts
    "hezbollah", "hamas", "houthi", "islamic jihad", "pij",
    "lebanon", "beirut", "gaza", "west bank",
    "syria", "damascus", "iraq", "baghdad",
    "yemen", "sanaa",
    # Specific operations
    "operation epic fury", "operation iron wall",
    # Nuclear
    "uranium enrichment", "nuclear deal", "jcpoa", "iaea iran",
}

_ACT_KW = {
    # Kinetic events
    "airstrike", "air strike", "strike", "attack", "bomb", "bombing",
    "explosion", "blast", "missile", "rocket", "drone strike",
    "intercept", "shoot down", "downed",
    "killed", "dead", "casualties", "wounded", "death toll",
    "invaded", "offensive", "assault", "raid",
    # Escalation signals
    "war", "retaliat", "conflict", "combat", "military operation",
    "nuclear weapon", "nuclear threat", "enrichment",
    "close strait", "blockade", "shut down",
    "evacuat", "emergency alert", "red alert",
    # Intel / political
    "sanctions", "seized", "arrested", "cyber attack", "blackout",
}

# Non-Latin scripts: Cyrillic, Arabic/Persian, CJK, Hangul, Greek, Thai, Hebrew
_NON_LATIN_RE = re.compile(
    r'[\u0370-\u03FF'   # Greek
    r'\u0400-\u04FF'    # Cyrillic
    r'\u0500-\u052F'    # Cyrillic Supplement
    r'\u0590-\u05FF'    # Hebrew
    r'\u0600-\u06FF'    # Arabic/Persian
    r'\u0E00-\u0E7F'    # Thai
    r'\u4E00-\u9FFF'    # CJK Unified
    r'\u3040-\u30FF'    # Hiragana/Katakana
    r'\uAC00-\uD7AF]'   # Hangul
)

# Non-English domains (Google News redirects hide original domain, so we also
# check the title for tell-tale non-English TLDs in the URL when visible)
_NON_EN_DOMAIN_RE = re.compile(
    r'https?://[^/]*\.(pl|de|it|nl|pt|ru|tr|cz|sk|ro|hr|hu|bg|lt|lv|ee|'
    r'fi|sv|da|no|is|jp|kr|cn|tw|th|vn|id|gr|uk\.co|co\.za)/'
)

# Noise phrases — even if location+action match, skip these
_NOISE_RE = re.compile(
    r'daylight saving|stock market|nfl|nba|weather forecast|'
    r'recipe|horoscope|crypto price|bitcoin|sports|academy award|'
    r'immigration law|ice detention|election fraud|gun control',
    re.I
)


def _is_relevant(title, desc="", url=""):
    """Return True only if the item is clearly about the Iran/Israel conflict."""
    if not title:
        return False
    # 1. Reject non-English scripts in title
    if _NON_LATIN_RE.search(title):
        return False
    # 2. Reject known non-English domains (only works for direct URLs, not GNews redirects)
    if url and _NON_EN_DOMAIN_RE.search(url):
        return False
    # 3. Reject clear noise
    if _NOISE_RE.search(title):
        return False
    text = (title + " " + (desc or "")).lower()
    # 4. Must have at least one LOCATION and one ACTION keyword
    has_loc = any(kw in text for kw in _LOC_KW)
    has_act = any(kw in text for kw in _ACT_KW)
    return has_loc and has_act


# ---------------------------------------------------------------------------
# Normalised event dict
# ---------------------------------------------------------------------------

def _norm(title="", description="", source_name="", source_url="",
          timestamp=None, location_text="", lat=None, lon=None,
          goldstein_scale=None, mention_count=1, raw=None):
    return {
        "title": (title or "")[:500],
        "description": (description or "")[:2000],
        "source_name": source_name,
        "source_url": source_url,
        "timestamp": timestamp or datetime.now(timezone.utc).isoformat(),
        "location_text": location_text,
        "lat": lat,
        "lon": lon,
        "goldstein_scale": goldstein_scale,
        "mention_count": mention_count or 1,
        "raw": raw or {},
    }


def _parse_rfc_date(s):
    if not s:
        return datetime.now(timezone.utc).isoformat()
    try:
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(s).isoformat()
    except Exception:
        pass
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).isoformat()
    except Exception:
        return datetime.now(timezone.utc).isoformat()


def _safe_float(val):
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# 1. Google News RSS — multiple targeted queries
# ---------------------------------------------------------------------------

# Each query targets a specific facet of the Iran/Israel conflict
GNEWS_QUERIES = [
    # Core conflict
    "Iran Israel strike attack 2026",
    "Iran US military airstrike 2026",
    "Operation Epic Fury Iran strikes",
    "Israel Iran war news today",
    # Iran specific
    "Tehran bombed explosion Iran",
    "IRGC missile strike killed",
    "Natanz Fordo Bushehr nuclear Iran attack",
    "Iran retaliation missiles Israel",
    "Khamenei Iran war response",
    # UAE / Gulf
    "Dubai UAE missile strike attack",
    "Abu Dhabi Iran attack explosion",
    "UAE Iran conflict 2026",
    "Gulf states Iran war attack",
    "Saudi Arabia Iran strike missile",
    "Strait of Hormuz Iran blocked closed",
    "Iran Persian Gulf attack warship",
    # Regional actors
    "Hezbollah attack Israel Lebanon",
    "Houthi missile strike Red Sea 2026",
    "Hamas attack Israel Gaza 2026",
    # Nuclear/escalation
    "Iran nuclear weapon threat 2026",
    "Iran uranium enrichment IAEA 2026",
    # Cyber / OSINT
    "Iran internet shutdown blackout 2026",
    "Iran protest uprising revolution 2026",
]


def _fetch_gnews_query(query):
    """Fetch one targeted Google News RSS query."""
    url = f"https://news.google.com/rss/search?q={quote_plus(query)}&hl=en&gl=US&ceid=US:en"
    try:
        feed = feedparser.parse(url)
        results = []
        for entry in feed.entries[:30]:
            title = entry.get("title", "").strip()
            if not title:
                continue
            # GNews titles often have " - Source Name" appended; extract that
            source_name = "Google News"
            source_info = entry.get("source", {})
            if isinstance(source_info, dict) and source_info.get("title"):
                source_name = source_info["title"]
            elif " - " in title:
                parts = title.rsplit(" - ", 1)
                if len(parts) == 2:
                    title = parts[0].strip()
                    source_name = parts[1].strip()

            summary = entry.get("summary", "")
            article_url = entry.get("link", "")

            if not _is_relevant(title, summary, article_url):
                continue

            results.append(_norm(
                title=title,
                description=summary,
                source_name=source_name,
                source_url=article_url,
                timestamp=_parse_rfc_date(entry.get("published", "")),
                raw={"id": entry.get("id", ""), "url": article_url},
            ))
        return results
    except Exception as e:
        logger.warning("GNews query '%s' failed: %s", query[:40], e)
        return []


def fetch_google_news_targeted():
    """Run all targeted Google News RSS queries in parallel."""
    all_results = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(_fetch_gnews_query, q): q for q in GNEWS_QUERIES}
        for future in as_completed(futures, timeout=30):
            try:
                results = future.result()
                all_results.extend(results)
            except Exception as e:
                logger.warning("GNews future failed: %s", e)
    logger.info("Google News (targeted) returned %d relevant articles", len(all_results))
    return all_results


# ---------------------------------------------------------------------------
# 2. Direct RSS feeds from major Middle East / conflict news outlets
# ---------------------------------------------------------------------------

DIRECT_RSS_FEEDS = [
    # (source_name, url, location_hint)
    # ── Tier-1 major outlets ──────────────────────────────────────────────────
    ("Times of Israel",     "https://www.timesofisrael.com/feed/",                              "Israel"),
    ("Jerusalem Post",      "https://www.jpost.com/rss/rssfeedsfrontpage.aspx",                 "Israel"),
    ("Al Jazeera",          "https://www.aljazeera.com/xml/rss/all.xml",                        ""),
    ("BBC Middle East",     "http://feeds.bbci.co.uk/news/world/middle_east/rss.xml",           ""),
    ("Middle East Eye",     "https://www.middleeasteye.net/rss",                                ""),
    ("Reuters World",       "https://feeds.reuters.com/reuters/worldNews",                      ""),
    ("Iran International",  "https://www.iranintl.com/en/rss",                                 "Iran"),
    ("Haaretz",             "https://www.haaretz.com/cmlink/1.628751",                         "Israel"),
    ("France24 ME",         "https://www.france24.com/en/middle-east/rss",                      ""),
    ("i24 News",            "https://www.i24news.tv/en/rss",                                   "Israel"),
    ("Radio Free Europe",   "https://www.rferl.org/api/epiqxpbveipe",                           ""),
    ("The National UAE",    "https://www.thenationalnews.com/rss/world/middle-east.xml",        ""),
    ("DW Middle East",      "https://rss.dw.com/rdf/rss-mea-news",                             ""),
    ("Israel Hayom",        "https://www.israelhayom.com/feed/",                               "Israel"),
    ("Axios World",         "https://api.axios.com/feed/",                                      ""),
    ("Ynet News",           "https://www.ynet.co.il/Integration/StoryRss2.xml",                "Israel"),
    # ── OSINT / conflict analysis ──────────────────────────────────────────────
    ("ISW",                 "https://www.understandingwar.org/taxonomy/term/5/feed",             ""),
    ("Bellingcat",          "https://www.bellingcat.com/feed/",                                 ""),
    ("Breaking Defense",    "https://breakingdefense.com/feed/",                               ""),
    ("Netblocks",           "https://netblocks.org/feed.xml",                                   "Iran"),
    # ── Telegram channels via RSSHub ──────────────────────────────────────────
    # Multiple public instances tried in order
    ("@InfinityHedge",      "https://rsshub.app/telegram/channel/infinityhedge",               ""),
    ("@IntelSlava",         "https://rsshub.app/telegram/channel/intelslava",                  ""),
    ("@OSINTdefender",      "https://rsshub.app/telegram/channel/OSINTdefender",               ""),
    ("@WarMonitor",         "https://rsshub.app/telegram/channel/warmonitor3",                 ""),
    ("@DiscloseTv",         "https://rsshub.app/telegram/channel/disclosetv",                  ""),
    ("@IranIntl_En",        "https://rsshub.app/telegram/channel/IranIntl_En",                 "Iran"),
    # ── AP via RSSHub ─────────────────────────────────────────────────────────
    ("AP News Iran",        "https://rsshub.app/apnews/topics/iran",                            "Iran"),
    ("AP News Israel",      "https://rsshub.app/apnews/topics/israel",                         "Israel"),
]


def _fetch_direct_rss(source_name, url, location_hint):
    """Fetch and filter one direct RSS feed."""
    try:
        feed = feedparser.parse(url)
        if feed.bozo and not feed.entries:
            return []
        results = []
        for entry in feed.entries[:60]:
            title = entry.get("title", "").strip()
            if not title:
                continue
            # Get best summary
            summary = ""
            if entry.get("content"):
                summary = entry["content"][0].get("value", "")
            if not summary:
                summary = entry.get("summary", "")
            # Clean HTML from summary
            summary = re.sub(r"<[^>]+>", " ", summary).strip()

            article_url = entry.get("link", "")

            if not _is_relevant(title, summary, article_url):
                continue

            ts = _parse_rfc_date(entry.get("published", entry.get("updated", "")))
            results.append(_norm(
                title=title,
                description=summary[:2000],
                source_name=source_name,
                source_url=article_url,
                timestamp=ts,
                location_text=location_hint,
                raw={"id": entry.get("id", ""), "url": article_url},
            ))
        logger.debug("%s: %d relevant items", source_name, len(results))
        return results
    except Exception as e:
        logger.warning("RSS feed '%s' failed: %s", source_name, e)
        return []


def fetch_direct_rss_feeds():
    """Fetch all direct RSS feeds in parallel."""
    all_results = []
    with ThreadPoolExecutor(max_workers=len(DIRECT_RSS_FEEDS)) as pool:
        futures = {
            pool.submit(_fetch_direct_rss, name, url, loc): name
            for name, url, loc in DIRECT_RSS_FEEDS
        }
        for future in as_completed(futures, timeout=45):
            name = futures[future]
            try:
                results = future.result()
                all_results.extend(results)
                if results:
                    logger.info("RSS %s: %d relevant items", name, len(results))
            except Exception as e:
                logger.warning("RSS future %s failed: %s", name, e)
    logger.info("Direct RSS feeds total: %d relevant articles", len(all_results))
    return all_results


# ---------------------------------------------------------------------------
# 3. GDELT with tight conflict filter
# ---------------------------------------------------------------------------

@_retry
def fetch_gdelt():
    """GDELT with tightly-focused Iran/Israel query."""
    params = {
        "query": (
            "(Iran OR Israel OR Tehran OR IRGC OR Netanyahu OR Khamenei) "
            "AND (strike OR attack OR bomb OR missile OR nuclear OR war OR military)"
        ),
        "mode": "ArtList",
        "maxrecords": "75",
        "format": "json",
        "sort": "DateDesc",
        "timespan": "24h",
    }
    try:
        resp = requests.get(config.GDELT_API_URL, params=params, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        articles = data.get("articles", [])
        results = []
        for art in articles:
            title = art.get("title", "")
            if not _is_relevant(title):
                continue
            results.append(_norm(
                title=title,
                description=art.get("seendate", ""),
                source_name=art.get("domain", "GDELT"),
                source_url=art.get("url", ""),
                timestamp=_parse_gdelt_date(art.get("seendate", "")),
                location_text=art.get("sourcecountry", ""),
                lat=_safe_float(art.get("lat")),
                lon=_safe_float(art.get("lon")),
                goldstein_scale=_safe_float(art.get("goldstein")),
                mention_count=int(art.get("numarts", 1) or 1),
                raw=art,
            ))
        logger.info("GDELT: %d relevant articles (from %d total)", len(results), len(articles))
        return results
    except Exception as e:
        logger.warning("GDELT failed: %s", e)
        return []


def _parse_gdelt_date(s):
    if not s:
        return datetime.now(timezone.utc).isoformat()
    try:
        s = s.strip().replace("T", " ").replace("Z", "")
        if len(s) == 14:
            dt = datetime.strptime(s, "%Y%m%d%H%M%S")
        else:
            dt = datetime.fromisoformat(s)
        return dt.replace(tzinfo=timezone.utc).isoformat()
    except Exception:
        return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# 4. Pikud HaOref — Israel Home Front Command real-time rocket alerts
# ---------------------------------------------------------------------------

def fetch_pikud_haoref():
    """Fetch Israel Home Front Command real-time alerts."""
    try:
        url = "https://www.oref.org.il/WarningMessages/alert/alerts.json"
        headers = {
            "Referer": "https://www.oref.org.il/",
            "X-Requested-With": "XMLHttpRequest",
            "User-Agent": "Mozilla/5.0",
        }
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200 and resp.text.strip():
            data = resp.json()
            if isinstance(data, list) and data:
                results = []
                for alert in data:
                    area = alert.get("data", "Unknown area")
                    results.append(_norm(
                        title=f"🚨 Alert: {area}",
                        description=f"Home Front Command alert — category: {alert.get('cat', 'N/A')}",
                        source_name="Pikud HaOref",
                        source_url="https://www.oref.org.il/",
                        location_text=area,
                        raw=alert,
                    ))
                logger.info("Pikud HaOref: %d active alerts", len(results))
                return results
        return []
    except Exception as e:
        logger.debug("Pikud HaOref unavailable (expected outside Israel): %s", e)
        return []


# ---------------------------------------------------------------------------
# 5. Optional paid sources
# ---------------------------------------------------------------------------

def fetch_newsdata():
    if not config.HAS_NEWSDATA:
        return []
    try:
        from newsdataapi import NewsDataApiClient
        api = NewsDataApiClient(apikey=config.NEWSDATA_API_KEY)
        resp = api.news_api(
            q="Iran Israel war strike nuclear",
            country="ir,il,us",
            language="en",
            category="politics,world",
        )
        results = []
        for art in (resp or {}).get("results", []):
            title = art.get("title", "")
            desc = art.get("description", "")
            if not _is_relevant(title, desc):
                continue
            results.append(_norm(
                title=title,
                description=desc,
                source_name=art.get("source_id", "NewsData"),
                source_url=art.get("link", ""),
                timestamp=art.get("pubDate"),
                location_text=", ".join(art.get("country", []) or []),
                raw=art,
            ))
        logger.info("NewsData.io: %d relevant articles", len(results))
        return results
    except Exception as e:
        logger.warning("NewsData failed: %s", e)
        return []


def fetch_acled():
    if not config.HAS_ACLED:
        return []
    try:
        resp = requests.get(
            "https://api.acleddata.com/acled/read",
            params={
                "key": config.ACLED_API_KEY,
                "email": config.ACLED_EMAIL,
                "country": "Iran|Israel|Lebanon|Yemen|Iraq",
                "limit": 50,
                "sort": "event_date:desc",
            },
            timeout=20,
        )
        resp.raise_for_status()
        results = []
        for ev in resp.json().get("data", []):
            results.append(_norm(
                title=f"{ev.get('event_type', 'Event')}: {ev.get('location', '')}",
                description=ev.get("notes", ""),
                source_name=ev.get("source", "ACLED"),
                source_url="https://acleddata.com",
                timestamp=ev.get("event_date"),
                location_text=ev.get("location", ""),
                lat=_safe_float(ev.get("latitude")),
                lon=_safe_float(ev.get("longitude")),
                mention_count=int(ev.get("fatalities", 0) or 0) + 1,
                raw=ev,
            ))
        logger.info("ACLED: %d events", len(results))
        return results
    except Exception as e:
        logger.warning("ACLED failed: %s", e)
        return []


def fetch_mediastack():
    if not config.HAS_MEDIASTACK:
        return []
    try:
        resp = requests.get(
            "http://api.mediastack.com/v1/news",
            params={
                "access_key": config.MEDIASTACK_API_KEY,
                "keywords": "Iran Israel war strike nuclear missile",
                "languages": "en",
                "sort": "published_desc",
                "limit": 25,
            },
            timeout=15,
        )
        resp.raise_for_status()
        results = []
        for art in resp.json().get("data", []):
            title = art.get("title", "")
            desc = art.get("description", "")
            if not _is_relevant(title, desc):
                continue
            results.append(_norm(
                title=title,
                description=desc,
                source_name=art.get("source", "Mediastack"),
                source_url=art.get("url", ""),
                timestamp=art.get("published_at"),
                location_text=art.get("country", ""),
                raw=art,
            ))
        logger.info("Mediastack: %d relevant articles", len(results))
        return results
    except Exception as e:
        logger.warning("Mediastack failed: %s", e)
        return []


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def fetch_all():
    """Run all fetchers, return merged and relevance-filtered list."""
    fetchers = [
        fetch_google_news_targeted,
        fetch_direct_rss_feeds,
        fetch_gdelt,
        fetch_pikud_haoref,
    ]

    if config.HAS_NEWSDATA:
        fetchers.append(fetch_newsdata)
    if config.HAS_ACLED:
        fetchers.append(fetch_acled)
    if config.HAS_MEDIASTACK:
        fetchers.append(fetch_mediastack)

    all_events = []
    with ThreadPoolExecutor(max_workers=len(fetchers)) as pool:
        futures = {pool.submit(f): f.__name__ for f in fetchers}
        for future in as_completed(futures, timeout=90):
            name = futures[future]
            try:
                events = future.result() or []
                all_events.extend(events)
                logger.info("Fetcher %s: %d events", name, len(events))
            except Exception as e:
                logger.error("Fetcher %s failed: %s", name, e)

    # Final relevance pass (with URL-based language filtering)
    before = len(all_events)
    all_events = [
        e for e in all_events
        if _is_relevant(e.get("title", ""), e.get("description", ""), e.get("source_url", ""))
    ]
    logger.info("Relevance filter: %d → %d events", before, len(all_events))

    return all_events
