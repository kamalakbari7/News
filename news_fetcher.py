import logging
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import requests

from config import NEWSAPI_KEY, SOURCE_PERSPECTIVES, TIMEZONE

logger = logging.getLogger(__name__)

NEWSAPI_URL = "https://newsapi.org/v2/everything"


def _is_safe_url(url: str) -> bool:
    """Only allow http and https URLs."""
    try:
        parsed = urlparse(url)
        return parsed.scheme in ("http", "https")
    except Exception:
        return False


def _fetch_from_domains(query: str, domains: str, sort_by: str, language: str,
                        page_size: int, from_dt: str) -> list[dict]:
    params = {
        "q": query,
        "domains": domains,
        "sortBy": sort_by,
        "language": language,
        "pageSize": page_size,
        "from": from_dt,
        "apiKey": NEWSAPI_KEY,
    }
    for attempt in range(2):
        try:
            resp = requests.get(NEWSAPI_URL, params=params, timeout=30)
            if resp.status_code >= 500:
                if attempt == 0:
                    time.sleep(5)
                    continue
                logger.warning("NewsAPI server error %s for domains=%s",
                               resp.status_code, domains)
                return []
            resp.raise_for_status()
            data = resp.json()
            if data.get("status") != "ok":
                logger.warning("NewsAPI returned status=%s for domains=%s",
                               data.get("status"), domains)
                return []
            articles = data.get("articles", [])
            if not isinstance(articles, list):
                logger.warning("NewsAPI articles is not a list for domains=%s", domains)
                return []
            return articles
        except requests.ConnectionError:
            if attempt == 0:
                time.sleep(5)
                continue
            logger.warning("Connection error fetching news for domains=%s", domains)
            return []
        except requests.RequestException as e:
            logger.warning("Request error fetching news: %s", e)
            return []
    return []


def fetch_articles(topic: dict) -> dict[str, list[dict]]:
    """Fetch articles for a topic from all perspective groups.

    Returns a dict mapping perspective name to list of article dicts.
    Each article dict has keys: title, source, url, description, content, published_at, perspective.
    """
    try:
        from zoneinfo import ZoneInfo
    except ImportError:
        from backports.zoneinfo import ZoneInfo

    tz = ZoneInfo(TIMEZONE)
    from_dt = (datetime.now(tz) - timedelta(hours=6)).strftime("%Y-%m-%dT%H:%M:%S")

    results = {}
    for perspective, domains_list in SOURCE_PERSPECTIVES.items():
        domains = ",".join(domains_list)
        raw_articles = _fetch_from_domains(
            query=topic["query"],
            domains=domains,
            sort_by=topic["sort_by"],
            language=topic["language"],
            page_size=topic["page_size"],
            from_dt=from_dt,
        )
        articles = []
        for a in raw_articles:
            if a.get("title") == "[Removed]":
                continue
            url = a.get("url", "")
            if url and not _is_safe_url(url):
                logger.warning("Skipping article with unsafe URL: %s", url)
                continue
            articles.append({
                "title": a.get("title", "No Title"),
                "source": a.get("source", {}).get("name", "Unknown"),
                "url": url,
                "description": a.get("description", ""),
                "content": a.get("content", a.get("description", "")),
                "published_at": a.get("publishedAt", ""),
                "perspective": perspective,
            })
        results[perspective] = articles
        logger.info("Fetched %d articles for topic='%s', perspective='%s'",
                     len(articles), topic["name"], perspective)

    return results
