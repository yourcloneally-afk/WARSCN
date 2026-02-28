import os
from dotenv import load_dotenv

load_dotenv()

# --- Flask ---
SECRET_KEY = os.getenv("SECRET_KEY", "evacscan-dev-key-change-in-production")
DEBUG = os.getenv("FLASK_DEBUG", "0") == "1"

# --- Database ---
DB_PATH = os.getenv("DB_PATH", "events.db")

# --- Scheduler / polling ---
POLL_INTERVAL_SEC = int(os.getenv("POLL_INTERVAL_SEC", "120"))  # Every 2 minutes
MAX_EVENTS_AGE_HOURS = int(os.getenv("MAX_EVENTS_AGE_HOURS", "24"))

# --- Alert thresholds ---
ALERT_RADIUS_KM = int(os.getenv("ALERT_RADIUS_KM", "100"))
DANGER_BUFFER_KM = int(os.getenv("DANGER_BUFFER_KM", "20"))

# --- Free-tier API sources (no key needed) ---
GDELT_API_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
RELIEFWEB_API_URL = "https://api.reliefweb.int/v1/reports"
RELIEFWEB_APPNAME = os.getenv("RELIEFWEB_APPNAME", "evacscan")  # Must be pre-approved at https://apidoc.reliefweb.int
GOOGLE_NEWS_RSS_URL = "https://news.google.com/rss/search"

# --- Optional paid sources (auto-detected) ---
NEWSDATA_API_KEY = os.getenv("NEWSDATA_API_KEY")
ACLED_API_KEY = os.getenv("ACLED_API_KEY")
ACLED_EMAIL = os.getenv("ACLED_EMAIL")
MEDIASTACK_API_KEY = os.getenv("MEDIASTACK_API_KEY")

HAS_NEWSDATA = bool(NEWSDATA_API_KEY)
HAS_ACLED = bool(ACLED_API_KEY and ACLED_EMAIL)
HAS_MEDIASTACK = bool(MEDIASTACK_API_KEY)

# --- Mapping services ---
GEOAPIFY_API_KEY = os.getenv("GEOAPIFY_API_KEY")
TOMTOM_API_KEY = os.getenv("TOMTOM_API_KEY")

HAS_GEOAPIFY = bool(GEOAPIFY_API_KEY)
HAS_TOMTOM = bool(TOMTOM_API_KEY)

# --- Notification services ---
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE = os.getenv("TWILIO_PHONE")
ALERT_EMAIL_USER = os.getenv("ALERT_EMAIL_USER")
ALERT_EMAIL_PASS = os.getenv("ALERT_EMAIL_PASS")
ALERT_EMAIL_SMTP = os.getenv("ALERT_EMAIL_SMTP", "smtp.gmail.com")

HAS_TWILIO = bool(TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_PHONE)
HAS_EMAIL = bool(ALERT_EMAIL_USER and ALERT_EMAIL_PASS)

# --- Severity keyword weights ---
SEVERITY_KEYWORDS = {
    "airstrike": 0.30, "air strike": 0.30, "missile": 0.30, "rocket": 0.25,
    "bombing": 0.30, "bomb": 0.25, "nuclear": 0.40, "chemical": 0.35,
    "casualties": 0.20, "killed": 0.20, "dead": 0.20, "wounded": 0.15,
    "invasion": 0.30, "ground offensive": 0.30, "troops": 0.15,
    "drone": 0.20, "intercept": 0.15, "explosion": 0.20,
    "ceasefire": -0.20, "peace": -0.15, "negotiations": -0.10,
    "humanitarian": -0.05, "aid": -0.05, "evacuation": 0.10,
    "shelter": 0.05, "warning": 0.15, "sirens": 0.25,
}

# --- Focus regions ---
FOCUS_COUNTRIES = ["Iran", "Israel", "United States"]
FOCUS_COUNTRY_CODES = ["IRN", "ISR", "USA"]
GDELT_CAMEO_CODES = ["18", "19", "20"]  # Military action root codes

# --- Geocoding ---
GEOCODER_USER_AGENT = "evacscan-conflict-monitor/1.0"
