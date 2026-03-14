from unittest.mock import MagicMock, patch

import pytest
import requests

from web_scraper import (
    _strip_html, _matches_topic, _fetch_rss_for_site,
    _fetch_from_hacker_news, fetch_from_web_sources,
)


class TestStripHtml:
    def test_strips_tags(self):
        assert _strip_html("<p>Hello <b>world</b></p>") == "Hello world"

    def test_plain_text_passthrough(self):
        assert _strip_html("no tags here") == "no tags here"

    def test_empty_string(self):
        assert _strip_html("") == ""

    def test_strips_links(self):
        assert _strip_html('<a href="url">click</a>') == "click"


class TestMatchesTopic:
    def test_simple_match(self):
        assert _matches_topic("Iran nuclear deal", "Iran") is True

    def test_or_query_first_term(self):
        assert _matches_topic("Data Science trends", "Data Science OR Machine Learning") is True

    def test_or_query_second_term(self):
        assert _matches_topic("Machine Learning model", "Data Science OR Machine Learning") is True

    def test_no_match(self):
        assert _matches_topic("Weather forecast today", "Iran") is False

    def test_case_insensitive(self):
        assert _matches_topic("IRAN sanctions", "iran") is True

    def test_empty_text(self):
        assert _matches_topic("", "Iran") is False


class TestFetchRssForSite:
    @patch("web_scraper.feedparser.parse")
    def test_successful_fetch_with_matching_entries(self, mock_parse):
        entry1 = MagicMock()
        entry1.get.side_effect = lambda k, d=None: {
            "title": "AI breakthrough in research",
            "link": "https://techcrunch.com/ai-article",
            "summary": "Summary about AI",
            "published": "2026-03-04T10:00:00Z",
        }.get(k, d)

        entry2 = MagicMock()
        entry2.get.side_effect = lambda k, d=None: {
            "title": "Unrelated cooking article",
            "link": "https://techcrunch.com/cooking",
            "summary": "About cooking",
            "published": "2026-03-04T11:00:00Z",
        }.get(k, d)

        mock_parse.return_value = MagicMock(bozo=False, entries=[entry1, entry2])

        result = _fetch_rss_for_site("techcrunch.com", "AI", 5)
        assert len(result) == 1
        assert result[0]["title"] == "AI breakthrough in research"
        assert result[0]["url"] == "https://techcrunch.com/ai-article"

    @patch("web_scraper.feedparser.parse")
    def test_respects_max_articles(self, mock_parse):
        entries = []
        for i in range(10):
            entry = MagicMock()
            entry.get.side_effect = lambda k, d=None, i=i: {
                "title": f"AI Article {i}",
                "link": f"https://techcrunch.com/{i}",
                "summary": "About AI",
                "published": "",
            }.get(k, d)
            entries.append(entry)

        mock_parse.return_value = MagicMock(bozo=False, entries=entries)

        result = _fetch_rss_for_site("techcrunch.com", "AI", 3)
        assert len(result) == 3

    @patch("web_scraper.feedparser.parse")
    def test_parse_error_returns_empty(self, mock_parse):
        mock_parse.return_value = MagicMock(bozo=True, entries=[], bozo_exception="XML error")

        result = _fetch_rss_for_site("techcrunch.com", "AI", 5)
        assert result == []

    @patch("web_scraper.feedparser.parse")
    def test_exception_returns_empty(self, mock_parse):
        mock_parse.side_effect = Exception("Network error")

        result = _fetch_rss_for_site("techcrunch.com", "AI", 5)
        assert result == []

    def test_unknown_domain_returns_empty(self):
        result = _fetch_rss_for_site("unknownsite.com", "AI", 5)
        assert result == []


class TestFetchFromHackerNews:
    @patch("web_scraper.requests.get")
    def test_successful_fetch(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "hits": [
                {
                    "title": "Show HN: AI Tool",
                    "url": "https://example.com/ai-tool",
                    "objectID": "12345",
                    "created_at": "2026-03-04T10:00:00.000Z",
                },
                {
                    "title": "Ask HN: Best ML course?",
                    "url": "",
                    "objectID": "67890",
                    "created_at": "2026-03-04T11:00:00.000Z",
                },
            ]
        }
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        result = _fetch_from_hacker_news("AI", 5)
        assert len(result) == 2
        assert result[0]["title"] == "Show HN: AI Tool"
        assert result[0]["url"] == "https://example.com/ai-tool"
        # Empty URL should construct HN link
        assert result[1]["url"] == "https://news.ycombinator.com/item?id=67890"

    @patch("web_scraper.requests.get")
    def test_network_error_returns_empty(self, mock_get):
        mock_get.side_effect = requests.ConnectionError("Connection failed")

        result = _fetch_from_hacker_news("AI", 5)
        assert result == []

    @patch("web_scraper.requests.get")
    def test_respects_max_articles(self, mock_get):
        hits = [
            {"title": f"Article {i}", "url": f"https://example.com/{i}",
             "objectID": str(i), "created_at": ""}
            for i in range(10)
        ]
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"hits": hits}
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        result = _fetch_from_hacker_news("AI", 3)
        assert len(result) == 3


class TestFetchFromWebSources:
    @patch("web_scraper._query_matches_google_news_sites", return_value=[])
    @patch("web_scraper._query_matches_topic_feeds", return_value=[])
    @patch("web_scraper._fetch_from_hacker_news", return_value=[])
    @patch("web_scraper._fetch_rss_for_site")
    def test_combines_results_from_sites(self, mock_rss, mock_hn, mock_topics, mock_gn):
        mock_rss.return_value = [
            {"title": "RSS Article", "url": "https://example.com/1",
             "source": {"name": "Test"}, "description": "D", "content": "C", "publishedAt": ""},
        ]

        from web_scraper import SITE_RSS_FEEDS
        num_sites = len(SITE_RSS_FEEDS)
        result = fetch_from_web_sources("AI", max_per_site=5)
        assert len(result) == num_sites
        assert mock_rss.call_count == num_sites

    @patch("web_scraper._query_matches_google_news_sites", return_value=[])
    @patch("web_scraper._query_matches_topic_feeds", return_value=[])
    @patch("web_scraper._fetch_from_hacker_news")
    @patch("web_scraper._fetch_rss_for_site")
    def test_one_site_failure_doesnt_affect_others(self, mock_rss, mock_hn,
                                                    mock_topics, mock_gn):
        from web_scraper import SITE_RSS_FEEDS
        num_sites = len(SITE_RSS_FEEDS)
        side_effects = [Exception("Site 1 down")]
        side_effects.append([{"title": "OK", "url": "https://example.com/ok",
              "source": {"name": "Test"}, "description": "D", "content": "C", "publishedAt": ""}])
        side_effects.extend([] for _ in range(num_sites - 2))
        mock_rss.side_effect = side_effects
        mock_hn.return_value = []

        result = fetch_from_web_sources("AI", max_per_site=5)
        assert len(result) == 1
        assert result[0]["title"] == "OK"

    @patch("web_scraper._query_matches_google_news_sites", return_value=[])
    @patch("web_scraper._query_matches_topic_feeds", return_value=[])
    @patch("web_scraper._fetch_from_hacker_news")
    @patch("web_scraper._fetch_rss_for_site", return_value=[])
    def test_includes_hacker_news(self, mock_rss, mock_hn, mock_topics, mock_gn):
        mock_hn.return_value = [
            {"title": "HN Article", "url": "https://example.com/hn",
             "source": {"name": "Hacker News"}, "description": "", "content": "", "publishedAt": ""},
        ]

        result = fetch_from_web_sources("AI", max_per_site=5)
        assert any(a["title"] == "HN Article" for a in result)
