import os
import sys
from dotenv import load_dotenv

load_dotenv()

_REQUIRED_VARS = [
    "NEWSAPI_KEY",
    "OPENAI_API_KEY",
    "GMAIL_ADDRESS",
    "GMAIL_APP_PASSWORD",
]


def validate_config():
    missing = [v for v in _REQUIRED_VARS if not os.environ.get(v)]
    if missing:
        print(
            f"ERROR: Missing required environment variables: {', '.join(missing)}\n"
            f"Copy .env.example to .env and fill in all values.",
            file=sys.stderr,
        )
        sys.exit(1)


# API Keys — accessed via os.environ.get() so the web UI can import
# this module without all env vars being set. validate_config() is
# called at the start of main.run() before these are actually needed.
NEWSAPI_KEY = os.environ.get("NEWSAPI_KEY", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

# Email
GMAIL_ADDRESS = os.environ.get("GMAIL_ADDRESS", "")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")
EMAIL_RECIPIENT = [
    addr.strip()
    for addr in os.environ.get("EMAIL_RECIPIENT", GMAIL_ADDRESS).split(",")
]

# Topics
TOPICS = [
    {
        "name": "Iran",
        "query": "Iran",
        "sort_by": "popularity",
        "language": "en",
        "page_size": 20,
    },
    {
        "name": "Geospatial Information Systems, Remote Sensing & Earth Science",
        "query": "Geospatial Information Systems OR Remote Sensing OR Earth Observation OR GIS OR ArcGIS OR QGIS OR PostGIS OR GeoServer OR Satellite Imagery",
        "sort_by": "popularity",
        "language": "en",
        "page_size": 20,
    },
    {
        "name": "AI, Data Science & Machine Learning",
        "query": "Artificial Intelligence OR ChatGPT OR Large Language Model OR Generative AI OR OpenAI OR Data Science OR Machine Learning OR Deep Learning OR Neural Network OR PyTorch OR TensorFlow OR MLOps OR NLP",
        "sort_by": "popularity",
        "language": "en",
        "page_size": 20,
    },
    {
        "name": "Football",
        "query": "Football OR Soccer OR Premier League OR Champions League",
        "sort_by": "popularity",
        "language": "en",
        "page_size": 20,
    },
]

# News source perspectives
SOURCE_PERSPECTIVES = {
    "Neutral": [
        "reuters.com",
        "apnews.com",
        "bbc.co.uk",
        "bbc.com",
        "npr.org",
        "pbs.org",
        "cbsnews.com",
        "abcnews.go.com",
        "nbcnews.com",
    ],
    "Left-Leaning": [
        "cnn.com",
        "theguardian.com",
        "msnbc.com",
        "nytimes.com",
        "washingtonpost.com",
        "politico.com",
    ],
    "Right-Leaning": [
        "foxnews.com",
        "nypost.com",
        "dailywire.com",
        "washingtontimes.com",
        "nationalreview.com",
        "wsj.com",
    ],
    "International": [
        "aljazeera.com",
        "bloomberg.com",
        "cnbc.com",
    ],
    "Tech": [
        "techcrunch.com",
        "wired.com",
        "arstechnica.com",
        "news.ycombinator.com",
    ],
    "GIS & Earth Science": [
        "osgeo.org",
        "esri.com",
        "resources.esri.ca",
        "gisgeography.com",
        "geospatialworld.net",
        "xyht.com",
        "earthobservatory.nasa.gov",
        "qgis.org",
    ],
}

OTHER_PERSPECTIVE = "Other Sources"

# OpenAI
OPENAI_MODEL = "gpt-4o-mini"
MAX_SUMMARY_TOKENS = 200

# TTS / Podcast
TTS_MODEL = "tts-1"
TTS_VOICE_A = "alloy"
TTS_VOICE_B = "onyx"
PODCAST_DIR = os.environ.get("PODCAST_DIR", "/var/www/podcasts")
PODCAST_BASE_URL = os.environ.get("PODCAST_BASE_URL", "http://65.109.218.149/podcasts")
PODCAST_KEEP_DAYS = 7

# Scheduling
TIMEZONE = "America/Toronto"

# Logging
LOG_FILE = "logs/news_agent.log"
