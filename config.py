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
EMAIL_RECIPIENT = os.environ.get("EMAIL_RECIPIENT", GMAIL_ADDRESS)

# Topics
TOPICS = [
    {
        "name": "Iran",
        "query": "Iran",
        "sort_by": "popularity",
        "language": "en",
        "page_size": 5,
    },
    {
        "name": "Data Science, GIS & Remote Sensing",
        "query": "Data Science OR GIS OR Remote Sensing",
        "sort_by": "popularity",
        "language": "en",
        "page_size": 5,
    },
]

# News source perspectives
SOURCE_PERSPECTIVES = {
    "Neutral": [
        "reuters.com",
        "apnews.com",
        "bbc.co.uk",
        "npr.org",
        "pbs.org",
    ],
    "Left-Leaning": [
        "cnn.com",
        "theguardian.com",
        "msnbc.com",
        "nytimes.com",
        "washingtonpost.com",
    ],
    "Right-Leaning": [
        "foxnews.com",
        "nypost.com",
        "dailywire.com",
        "washingtontimes.com",
        "nationalreview.com",
    ],
}

# OpenAI
OPENAI_MODEL = "gpt-4o-mini"
MAX_SUMMARY_TOKENS = 200

# Scheduling
TIMEZONE = "America/Toronto"

# Logging
LOG_FILE = "logs/news_agent.log"
