from unittest.mock import MagicMock, patch

import pytest
import requests

from news_fetcher import (
    _is_safe_url, _classify_perspective, _fetch_from_domains,
    _fetch_from_google_news_rss, fetch_articles,
)


SAMPLE_NEWSAPI_RESPONSE = {
    "status": "ok",
    "totalResults": 2,
    "articles": [
        {
            "source": {"id": "reuters", "name": "Reuters"},
            "title": "Test Article 1",
            "description": "Description 1",
            "url": "https://reuters.com/article1",
            "content": "Full content of article 1",
            "publishedAt": "2026-03-04T10:00:00Z",
        },
        {
            "source": {"id": "bbc", "name": "BBC"},
            "title": "Test Article 2",
            "description": "Description 2",
            "url": "https://bbc.co.uk/article2",
            "content": "Full content of article 2",
            "publishedAt": "2026-03-04T11:00:00Z",
        },
    ],
}

SAMPLE_TOPIC = {
    "name": "TestTopic",
    "query": "test",
    "sort_by": "popularity",
    "language": "en",
    "page_size": 5,
}


class TestIsSafeUrl:
    def test_https_is_safe(self):
        assert _is_safe_url("https://example.com/article") is True

    def test_http_is_safe(self):
        assert _is_safe_url("http://example.com/article") is True

    def test_javascript_is_unsafe(self):
        assert _is_safe_url("javascript:alert('xss')") is False

    def test_data_is_unsafe(self):
        assert _is_safe_url("data:text/html,<script>alert(1)</script>") is False

    def test_empty_string(self):
        assert _is_safe_url("") is False

    def test_ftp_is_unsafe(self):
        assert _is_safe_url("ftp://example.com/file") is False


class TestClassifyPerspective:
    def test_neutral_domain(self):
        assert _classify_perspective("https://reuters.com/article/123") == "Neutral"

    def test_left_leaning_domain(self):
        assert _classify_perspective("https://cnn.com/news/story") == "Left-Leaning"

    def test_right_leaning_domain(self):
        assert _classify_perspective("https://foxnews.com/politics") == "Right-Leaning"

    def test_www_prefix_stripped(self):
        assert _classify_perspective("https://www.reuters.com/article") == "Neutral"

    def test_subdomain_matching(self):
        assert _classify_perspective("https://edition.cnn.com/story") == "Left-Leaning"

    def test_unknown_domain_returns_other(self):
        assert _classify_perspective("https://unknownnews.com/article") == "Other Sources"

    def test_empty_url_returns_other(self):
        assert _classify_perspective("") == "Other Sources"


class TestFetchFromDomains:
    @patch("news_fetcher.requests.get")
    def test_successful_fetch(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = SAMPLE_NEWSAPI_RESPONSE
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        result = _fetch_from_domains("test", "reuters.com", "popularity", "en", 5, "2026-03-04")
        assert len(result) == 2
        assert result[0]["title"] == "Test Article 1"

    @patch("news_fetcher.requests.get")
    def test_server_error_retry_then_success(self, mock_get):
        error_resp = MagicMock()
        error_resp.status_code = 500

        ok_resp = MagicMock()
        ok_resp.status_code = 200
        ok_resp.json.return_value = SAMPLE_NEWSAPI_RESPONSE
        ok_resp.raise_for_status = MagicMock()

        mock_get.side_effect = [error_resp, ok_resp]

        result = _fetch_from_domains("test", "reuters.com", "popularity", "en", 5, "2026-03-04")
        assert len(result) == 2
        assert mock_get.call_count == 2

    @patch("news_fetcher.requests.get")
    def test_connection_error_returns_empty(self, mock_get):
        mock_get.side_effect = requests.ConnectionError("Connection failed")

        result = _fetch_from_domains("test", "reuters.com", "popularity", "en", 5, "2026-03-04")
        assert result == []

    @patch("news_fetcher.requests.get")
    def test_bad_status_returns_empty(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"status": "error", "message": "rate limited"}
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        result = _fetch_from_domains("test", "reuters.com", "popularity", "en", 5, "2026-03-04")
        assert result == []


class TestFetchFromGoogleNewsRss:
    @patch("news_fetcher.feedparser.parse")
    def test_successful_rss_fetch(self, mock_parse):
        mock_parse.return_value = MagicMock(
            bozo=False,
            entries=[
                MagicMock(
                    title="RSS Article 1",
                    link="https://reuters.com/rss-article",
                    summary="RSS summary",
                    published="Mon, 04 Mar 2026 10:00:00 GMT",
                    source={"title": "Reuters"},
                    **{"get": lambda k, d=None: {"title": "RSS Article 1", "link": "https://reuters.com/rss-article", "summary": "RSS summary", "published": "Mon, 04 Mar 2026 10:00:00 GMT"}.get(k, d)},
                ),
            ],
        )
        # Simpler approach: use a dict-like entry
        mock_entry = MagicMock()
        mock_entry.get.side_effect = lambda k, d=None: {
            "title": "RSS Article 1",
            "link": "https://reuters.com/rss-article",
            "summary": "RSS summary",
            "published": "Mon, 04 Mar 2026 10:00:00 GMT",
            "source": {"title": "Reuters"},
        }.get(k, d)
        mock_parse.return_value = MagicMock(bozo=False, entries=[mock_entry])

        result = _fetch_from_google_news_rss("test", 5)
        assert len(result) == 1
        assert result[0]["title"] == "RSS Article 1"
        assert result[0]["url"] == "https://reuters.com/rss-article"

    @patch("news_fetcher.feedparser.parse")
    def test_rss_parse_error_returns_empty(self, mock_parse):
        mock_parse.return_value = MagicMock(bozo=True, entries=[], bozo_exception="XML error")

        result = _fetch_from_google_news_rss("test", 5)
        assert result == []

    @patch("news_fetcher.feedparser.parse")
    def test_rss_exception_returns_empty(self, mock_parse):
        mock_parse.side_effect = Exception("Network error")

        result = _fetch_from_google_news_rss("test", 5)
        assert result == []

    @patch("news_fetcher.feedparser.parse")
    def test_rss_respects_page_size(self, mock_parse):
        entries = []
        for i in range(10):
            entry = MagicMock()
            entry.get.side_effect = lambda k, d=None, i=i: {
                "title": f"Article {i}",
                "link": f"https://example.com/{i}",
                "summary": f"Summary {i}",
                "published": "",
                "source": {"title": "Source"},
            }.get(k, d)
            entries.append(entry)
        mock_parse.return_value = MagicMock(bozo=False, entries=entries)

        result = _fetch_from_google_news_rss("test", 3)
        assert len(result) == 3


class TestFetchArticles:
    @patch("web_scraper.fetch_from_web_sources", return_value=[])
    @patch("news_fetcher._fetch_from_google_news_rss", return_value=[])
    @patch("news_fetcher._fetch_from_domains")
    def test_returns_perspectives(self, mock_fetch, mock_rss, mock_web):
        mock_fetch.return_value = SAMPLE_NEWSAPI_RESPONSE["articles"]

        result = fetch_articles(SAMPLE_TOPIC)
        assert "Neutral" in result
        assert "Left-Leaning" in result
        assert "Right-Leaning" in result

    @patch("web_scraper.fetch_from_web_sources", return_value=[])
    @patch("news_fetcher._fetch_from_google_news_rss", return_value=[])
    @patch("news_fetcher._fetch_from_domains")
    def test_filters_removed_articles(self, mock_fetch, mock_rss, mock_web):
        articles = [
            {"title": "[Removed]", "url": "https://example.com", "source": {"name": "X"}},
            {"title": "Good Article", "url": "https://example.com/good", "source": {"name": "Y"},
             "description": "Desc", "content": "Content", "publishedAt": "2026-03-04"},
        ]
        mock_fetch.return_value = articles

        result = fetch_articles(SAMPLE_TOPIC)
        for perspective_articles in result.values():
            for a in perspective_articles:
                assert a["title"] != "[Removed]"

    @patch("web_scraper.fetch_from_web_sources", return_value=[])
    @patch("news_fetcher._fetch_from_google_news_rss", return_value=[])
    @patch("news_fetcher._fetch_from_domains")
    def test_filters_unsafe_urls(self, mock_fetch, mock_rss, mock_web):
        articles = [
            {"title": "Bad URL", "url": "javascript:alert(1)", "source": {"name": "X"},
             "description": "Desc", "content": "Content", "publishedAt": "2026-03-04"},
            {"title": "Good URL", "url": "https://example.com/good", "source": {"name": "Y"},
             "description": "Desc", "content": "Content", "publishedAt": "2026-03-04"},
        ]
        mock_fetch.return_value = articles

        result = fetch_articles(SAMPLE_TOPIC)
        for perspective_articles in result.values():
            for a in perspective_articles:
                assert a["title"] != "Bad URL"

    @patch("web_scraper.fetch_from_web_sources", return_value=[])
    @patch("news_fetcher._fetch_from_google_news_rss", return_value=[])
    @patch("news_fetcher._fetch_from_domains")
    def test_article_structure(self, mock_fetch, mock_rss, mock_web):
        mock_fetch.return_value = SAMPLE_NEWSAPI_RESPONSE["articles"]

        result = fetch_articles(SAMPLE_TOPIC)
        article = result["Neutral"][0]
        assert "title" in article
        assert "source" in article
        assert "url" in article
        assert "description" in article
        assert "content" in article
        assert "published_at" in article
        assert "perspective" in article
        assert article["perspective"] == "Neutral"

    @patch("web_scraper.fetch_from_web_sources", return_value=[])
    @patch("news_fetcher._fetch_from_google_news_rss")
    @patch("news_fetcher._fetch_from_domains", return_value=[])
    def test_rss_articles_classified_by_domain(self, mock_fetch, mock_rss, mock_web):
        mock_rss.return_value = [
            {"title": "Reuters RSS", "url": "https://reuters.com/rss1",
             "source": {"name": "Reuters"}, "description": "D", "content": "C", "publishedAt": ""},
            {"title": "Unknown RSS", "url": "https://unknownnews.org/rss2",
             "source": {"name": "Unknown"}, "description": "D", "content": "C", "publishedAt": ""},
        ]

        result = fetch_articles(SAMPLE_TOPIC)
        # Reuters should go to Neutral
        neutral_titles = [a["title"] for a in result.get("Neutral", [])]
        assert "Reuters RSS" in neutral_titles
        # Unknown should go to Other Sources
        other_titles = [a["title"] for a in result.get("Other Sources", [])]
        assert "Unknown RSS" in other_titles

    @patch("web_scraper.fetch_from_web_sources", return_value=[])
    @patch("news_fetcher._fetch_from_google_news_rss")
    @patch("news_fetcher._fetch_from_domains")
    def test_deduplication_by_url(self, mock_fetch, mock_rss, mock_web):
        # Same URL from both NewsAPI and RSS
        mock_fetch.return_value = [
            {"title": "NewsAPI Article", "url": "https://reuters.com/same-article",
             "source": {"name": "Reuters"}, "description": "D", "content": "C", "publishedAt": ""},
        ]
        mock_rss.return_value = [
            {"title": "RSS Article", "url": "https://reuters.com/same-article",
             "source": {"name": "Reuters"}, "description": "D", "content": "C", "publishedAt": ""},
        ]

        result = fetch_articles(SAMPLE_TOPIC)
        all_urls = []
        for articles in result.values():
            all_urls.extend(a["url"] for a in articles)
        assert all_urls.count("https://reuters.com/same-article") == 1
