from unittest.mock import MagicMock, patch

import pytest
import requests

from news_fetcher import _is_safe_url, fetch_articles, _fetch_from_domains


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


class TestFetchArticles:
    @patch("news_fetcher._fetch_from_domains")
    def test_returns_perspectives(self, mock_fetch):
        mock_fetch.return_value = SAMPLE_NEWSAPI_RESPONSE["articles"]

        result = fetch_articles(SAMPLE_TOPIC)
        assert "Neutral" in result
        assert "Left-Leaning" in result
        assert "Right-Leaning" in result

    @patch("news_fetcher._fetch_from_domains")
    def test_filters_removed_articles(self, mock_fetch):
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

    @patch("news_fetcher._fetch_from_domains")
    def test_filters_unsafe_urls(self, mock_fetch):
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

    @patch("news_fetcher._fetch_from_domains")
    def test_article_structure(self, mock_fetch):
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
