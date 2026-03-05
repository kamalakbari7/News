import logging
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse, quote

import feedparser
import requests

from config import NEWSAPI_KEY, OTHER_PERSPECTIVE, SOURCE_PERSPECTIVES, TIMEZONE

logger = logging.getLogger(__name__)

NEWSAPI_URL = "https://newsapi.org/v2/everything"
GOOGLE_NEWS_RSS_URL = "https://news.google.com/rss/search?q={query}&hl=en&gl=US&ceid=US:en"


def _is_safe_url(url: str) -> bool:
    """Only allow http and https URLs."""
    try:
        parsed = urlparse(url)
        return parsed.scheme in ("http", "https")
    except Exception:
        return False


def _classify_perspective(url: str) -> str:
    """Classify an article's perspective based on its domain.

    Returns the matching perspective name or OTHER_PERSPECTIVE.
    """
    try:
        domain = urlparse(url).netloc.lower()
        # Strip 'www.' prefix for matching
        if domain.startswith("www."):
            domain = domain[4:]
    except Exception:
        return OTHER_PERSPECTIVE

    for perspective, domains in SOURCE_PERSPECTIVES.items():
        for known_domain in domains:
            if domain == known_domain or domain.endswith("." + known_domain):
                return perspective
    return OTHER_PERSPECTIVE


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


def _fetch_from_google_news_rss(query: str, page_size: int) -> list[dict]:
    """Fetch articles from Google News RSS feed.

    Returns a list of article dicts in the same format as NewsAPI articles.
    """
    url = GOOGLE_NEWS_RSS_URL.format(query=quote(query))
    try:
        feed = feedparser.parse(url)
        if feed.bozo and not feed.entries:
            logger.warning("Google News RSS parse error for query='%s': %s",
                           query, feed.bozo_exception)
            return []
    except Exception as e:
        logger.warning("Google News RSS fetch failed for query='%s': %s", query, e)
        return []

    articles = []
    for entry in feed.entries[:page_size]:
        # Google News RSS provides: title, link, published, source
        source_name = entry.get("source", {}).get("title", "Unknown") if hasattr(entry.get("source", {}), "get") else "Unknown"
        articles.append({
            "title": entry.get("title", "No Title"),
            "source": {"name": source_name},
            "url": entry.get("link", ""),
            "description": entry.get("summary", ""),
            "content": entry.get("summary", ""),
            "publishedAt": entry.get("published", ""),
        })

    logger.info("Fetched %d articles from Google News RSS for query='%s'",
                len(articles), query)
    return articles


def fetch_articles(topic: dict) -> dict[str, list[dict]]:
    """Fetch articles for a topic from NewsAPI and Google News RSS.

    Returns a dict mapping perspective name to list of article dicts.
    Each article dict has keys: title, source, url, description, content, published_at, perspective.
    """
    try:
        from zoneinfo import ZoneInfo
    except ImportError:
        from backports.zoneinfo import ZoneInfo

    tz = ZoneInfo(TIMEZONE)
    from_dt = (datetime.now(tz) - timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%S")

    results = {}
    seen_urls = set()

    # Fetch from NewsAPI (per perspective)
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
            if url in seen_urls:
                continue
            seen_urls.add(url)
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
        logger.info("Fetched %d articles for topic='%s', perspective='%s' (NewsAPI)",
                     len(articles), topic["name"], perspective)

    # Fetch from Google News RSS
    rss_articles = _fetch_from_google_news_rss(topic["query"], topic["page_size"] * 3)
    for a in rss_articles:
        url = a.get("url", "")
        if not url or not _is_safe_url(url):
            continue
        if url in seen_urls:
            continue
        seen_urls.add(url)

        perspective = _classify_perspective(url)
        if perspective not in results:
            results[perspective] = []

        results[perspective].append({
            "title": a.get("title", "No Title"),
            "source": a.get("source", {}).get("name", "Unknown"),
            "url": url,
            "description": a.get("description", ""),
            "content": a.get("content", a.get("description", "")),
            "published_at": a.get("publishedAt", ""),
            "perspective": perspective,
        })

    rss_count = sum(1 for a in rss_articles if a.get("url", "") in seen_urls)
    logger.info("Added %d unique articles from Google News RSS for topic='%s'",
                rss_count, topic["name"])

    # Fetch from web sources (RSS feeds + Hacker News API)
    from web_scraper import fetch_from_web_sources

    web_articles = fetch_from_web_sources(topic["query"], max_per_site=topic["page_size"])
    web_count = 0
    for a in web_articles:
        url = a.get("url", "")
        if not url or not _is_safe_url(url):
            continue
        if url in seen_urls:
            continue
        seen_urls.add(url)

        perspective = _classify_perspective(url)
        if perspective not in results:
            results[perspective] = []

        results[perspective].append({
            "title": a.get("title", "No Title"),
            "source": a.get("source", {}).get("name", "Unknown"),
            "url": url,
            "description": a.get("description", ""),
            "content": a.get("content", a.get("description", "")),
            "published_at": a.get("publishedAt", ""),
            "perspective": perspective,
        })
        web_count += 1

    logger.info("Added %d unique articles from web sources for topic='%s'",
                web_count, topic["name"])

    return results
