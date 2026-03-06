import logging
import re
import time
from urllib.parse import quote

import feedparser
import requests

logger = logging.getLogger(__name__)

SITE_RSS_FEEDS = {
    "aljazeera.com": [
        "https://www.aljazeera.com/xml/rss/all.xml",
    ],
    "bloomberg.com": [
        "https://feeds.bloomberg.com/markets/news.rss",
        "https://feeds.bloomberg.com/technology/news.rss",
    ],
    "techcrunch.com": [
        "https://techcrunch.com/feed/",
    ],
    "wired.com": [
        "https://www.wired.com/feed/rss",
    ],
    "arstechnica.com": [
        "https://feeds.arstechnica.com/arstechnica/index",
    ],
}

HN_ALGOLIA_URL = "https://hn.algolia.com/api/v1/search_by_date"

# Topic-specific RSS feeds — only fetched when query keywords match
TOPIC_RSS_FEEDS = {
    "geospatial|remote sensing|earth science|gis": [
        ("OSGeo", "https://www.osgeo.org/community-news/feed/"),
        ("Esri Canada", "https://resources.esri.ca/news-and-updates.rss"),
        ("Esri Canada", "https://resources.esri.ca/getting-technical.rss"),
    ],
}

# Topic-specific Google News site searches (for sites that block direct scraping)
TOPIC_GOOGLE_NEWS_SITES = {
    "geospatial|remote sensing|earth science|gis": [
        ("Esri ArcNews", "site:esri.com/about/newsroom/arcnews"),
    ],
}


def _strip_html(text: str) -> str:
    """Remove HTML tags from text."""
    return re.sub(r"<[^>]+>", "", text).strip()


def _matches_topic(text: str, query: str) -> bool:
    """Check if text matches any keyword from the query.

    Query can contain OR-separated terms, e.g. "Data Science OR Machine Learning".
    Each term is matched as a whole (case-insensitive).
    """
    if not text:
        return False
    text_lower = text.lower()
    terms = [t.strip().lower() for t in query.split(" OR ")]
    return any(term in text_lower for term in terms if term)


def _fetch_rss_for_site(domain: str, query: str, max_articles: int) -> list[dict]:
    """Fetch and filter RSS feed entries for a site."""
    feeds = SITE_RSS_FEEDS.get(domain, [])
    articles = []

    for feed_url in feeds:
        try:
            feed = feedparser.parse(feed_url)
            if feed.bozo and not feed.entries:
                logger.warning("RSS parse error for %s: %s", feed_url, feed.bozo_exception)
                continue
        except Exception as e:
            logger.warning("RSS fetch failed for %s: %s", feed_url, e)
            continue

        for entry in feed.entries:
            title = entry.get("title", "")
            summary = _strip_html(entry.get("summary", ""))

            if not _matches_topic(f"{title} {summary}", query):
                continue

            articles.append({
                "title": title or "No Title",
                "source": {"name": domain.split(".")[0].capitalize()},
                "url": entry.get("link", ""),
                "description": summary,
                "content": summary,
                "publishedAt": entry.get("published", ""),
            })

            if len(articles) >= max_articles:
                return articles

    return articles


def _fetch_from_hacker_news(query: str, max_articles: int) -> list[dict]:
    """Fetch articles from Hacker News via Algolia search API."""
    try:
        resp = requests.get(
            HN_ALGOLIA_URL,
            params={
                "query": query,
                "tags": "story",
                "hitsPerPage": max_articles,
                "numericFilters": f"created_at_i>{int(time.time()) - 2 * 86400}",
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        logger.warning("Hacker News API error: %s", e)
        return []
    except ValueError as e:
        logger.warning("Hacker News JSON decode error: %s", e)
        return []

    articles = []
    for hit in data.get("hits", [])[:max_articles]:
        url = hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID', '')}"
        articles.append({
            "title": hit.get("title", "No Title"),
            "source": {"name": "Hacker News"},
            "url": url,
            "description": "",
            "content": "",
            "publishedAt": hit.get("created_at", ""),
        })

    return articles


def _query_matches_topic_feeds(query: str) -> list[tuple]:
    """Return topic-specific feed entries if query keywords match."""
    query_lower = query.lower()
    matched_feeds = []
    for keywords, feeds in TOPIC_RSS_FEEDS.items():
        if any(kw in query_lower for kw in keywords.split("|")):
            matched_feeds.extend(feeds)
    return matched_feeds


def _query_matches_google_news_sites(query: str) -> list[tuple]:
    """Return topic-specific Google News site searches if query keywords match."""
    query_lower = query.lower()
    matched = []
    for keywords, sites in TOPIC_GOOGLE_NEWS_SITES.items():
        if any(kw in query_lower for kw in keywords.split("|")):
            matched.extend(sites)
    return matched


def _fetch_google_news_site(source_name: str, site_query: str, max_articles: int) -> list[dict]:
    """Fetch articles from a specific site via Google News RSS search."""
    encoded = quote(site_query)
    url = f"https://news.google.com/rss/search?q={encoded}&hl=en&gl=US&ceid=US:en"

    # Extract actual domain from site query (e.g. "site:esri.com/about/..." -> "esri.com")
    domain_hint = ""
    if "site:" in site_query:
        domain_part = site_query.split("site:", 1)[1].split()[0]
        domain_hint = domain_part.split("/")[0]

    try:
        feed = feedparser.parse(url)
        if feed.bozo and not feed.entries:
            logger.warning("Google News RSS error for %s: %s", source_name, feed.bozo_exception)
            return []
    except Exception as e:
        logger.warning("Google News RSS fetch failed for %s: %s", source_name, e)
        return []

    articles = []
    for entry in feed.entries[:max_articles]:
        title = entry.get("title", "")
        # Google News titles often end with " - Source Name", clean it
        if " - " in title:
            title = title.rsplit(" - ", 1)[0]
        articles.append({
            "title": title or "No Title",
            "source": {"name": source_name},
            "url": entry.get("link", ""),
            "domain_hint": domain_hint,
            "description": _strip_html(entry.get("summary", "")),
            "content": _strip_html(entry.get("summary", "")),
            "publishedAt": entry.get("published", ""),
        })

    return articles


def _fetch_topic_rss(source_name: str, feed_url: str, query: str, max_articles: int) -> list[dict]:
    """Fetch and filter a single RSS feed for topic-specific sources."""
    try:
        feed = feedparser.parse(feed_url)
        if feed.bozo and not feed.entries:
            logger.warning("RSS parse error for %s: %s", feed_url, feed.bozo_exception)
            return []
    except Exception as e:
        logger.warning("RSS fetch failed for %s: %s", feed_url, e)
        return []

    articles = []
    for entry in feed.entries:
        title = entry.get("title", "")
        summary = _strip_html(entry.get("summary", ""))
        articles.append({
            "title": title or "No Title",
            "source": {"name": source_name},
            "url": entry.get("link", ""),
            "description": summary,
            "content": summary,
            "publishedAt": entry.get("published", ""),
        })
        if len(articles) >= max_articles:
            break

    return articles


def fetch_from_web_sources(query: str, max_per_site: int = 5) -> list[dict]:
    """Fetch articles from RSS feeds and Hacker News API.

    Returns a flat list of article dicts in the same format as NewsAPI/Google RSS.
    """
    all_articles = []

    for domain in SITE_RSS_FEEDS:
        try:
            articles = _fetch_rss_for_site(domain, query, max_per_site)
            all_articles.extend(articles)
            logger.info("Fetched %d articles from %s RSS", len(articles), domain)
        except Exception as e:
            logger.warning("Failed to fetch from %s: %s", domain, e)

    # Topic-specific feeds (e.g. GIS sites for geospatial queries)
    for source_name, feed_url in _query_matches_topic_feeds(query):
        try:
            articles = _fetch_topic_rss(source_name, feed_url, query, max_per_site)
            all_articles.extend(articles)
            logger.info("Fetched %d articles from %s RSS", len(articles), source_name)
        except Exception as e:
            logger.warning("Failed to fetch from %s: %s", source_name, e)

    # Topic-specific Google News site searches (for sites that block scraping)
    for source_name, site_query in _query_matches_google_news_sites(query):
        try:
            articles = _fetch_google_news_site(source_name, site_query, max_per_site)
            all_articles.extend(articles)
            logger.info("Fetched %d articles from %s (Google News)", len(articles), source_name)
        except Exception as e:
            logger.warning("Failed to fetch from %s: %s", source_name, e)

    try:
        hn_articles = _fetch_from_hacker_news(query, max_per_site)
        all_articles.extend(hn_articles)
        logger.info("Fetched %d articles from Hacker News", len(hn_articles))
    except Exception as e:
        logger.warning("Failed to fetch from Hacker News: %s", e)

    return all_articles
