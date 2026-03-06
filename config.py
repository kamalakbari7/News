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


validate_config()

# API Keys
NEWSAPI_KEY = os.environ["NEWSAPI_KEY"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]

# Email
GMAIL_ADDRESS = os.environ["GMAIL_ADDRESS"]
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]
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
        "query": "Geospatial Information Systems OR Remote Sensing OR Earth Science OR GIS OR ArcGIS OR QGIS",
        "sort_by": "popularity",
        "language": "en",
        "page_size": 20,
    },
    {
        "name": "Data Science or Machine Learning",
        "query": "Data Science OR Machine Learning",
        "sort_by": "popularity",
        "language": "en",
        "page_size": 20,
    },
    {
        "name": "Artificial Intelligence",
        "query": "Artificial Intelligence OR ChatGPT OR Large Language Model OR Generative AI OR OpenAI OR Machine Intelligence",
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
    ],
}

OTHER_PERSPECTIVE = "Other Sources"

# OpenAI
OPENAI_MODEL = "gpt-4o-mini"
MAX_SUMMARY_TOKENS = 200

# Scheduling
TIMEZONE = "America/Toronto"

# Logging
LOG_FILE = "logs/news_agent.log"
