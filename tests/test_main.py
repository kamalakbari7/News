import os
from unittest.mock import MagicMock, patch, call

import pytest


SAMPLE_PERSPECTIVES = {
    "Neutral": [
        {
            "title": "Article 1",
            "source": "Reuters",
            "url": "https://reuters.com/1",
            "description": "Desc 1",
            "content": "Content 1",
            "published_at": "2026-03-04T10:00:00Z",
            "perspective": "Neutral",
        }
    ],
    "Left-Leaning": [],
    "Right-Leaning": [],
}

EMPTY_PERSPECTIVES = {
    "Neutral": [],
    "Left-Leaning": [],
    "Right-Leaning": [],
}


class TestRun:
    @patch("main.send_email")
    @patch("main.build_email_html", return_value="<html>test</html>")
    @patch("main.summarize_article", return_value="Summary text")
    @patch("main.fetch_articles")
    def test_sends_one_email_per_topic(self, mock_fetch, mock_summarize,
                                       mock_build, mock_send):
        mock_fetch.return_value = SAMPLE_PERSPECTIVES

        from main import run
        run(dry_run=False)

        # 4 topics = 5 emails
        assert mock_send.call_count == 4

    @patch("main.send_email")
    @patch("main.build_email_html", return_value="<html>test</html>")
    @patch("main.summarize_article", return_value="Summary text")
    @patch("main.fetch_articles")
    def test_skips_email_when_no_articles(self, mock_fetch, mock_summarize,
                                          mock_build, mock_send):
        mock_fetch.return_value = EMPTY_PERSPECTIVES

        from main import run
        run(dry_run=False)

        mock_send.assert_not_called()

    @patch("main.send_email")
    @patch("main.build_email_html", return_value="<html>test</html>")
    @patch("main.summarize_article", return_value="Summary text")
    @patch("main.fetch_articles")
    def test_dry_run_writes_files(self, mock_fetch, mock_summarize,
                                   mock_build, mock_send, tmp_path):
        mock_fetch.return_value = SAMPLE_PERSPECTIVES

        # Change to tmp_path so HTML files are written there
        original_dir = os.getcwd()
        os.chdir(tmp_path)
        try:
            from main import run
            run(dry_run=True)
        finally:
            os.chdir(original_dir)

        mock_send.assert_not_called()
        # Should have created HTML files
        html_files = list(tmp_path.glob("*.html"))
        assert len(html_files) == 4

    @patch("main.send_email")
    @patch("main.build_email_html", return_value="<html>test</html>")
    @patch("main.summarize_article", return_value="Summary text")
    @patch("main.fetch_articles")
    def test_summarize_called_for_each_article(self, mock_fetch, mock_summarize,
                                                mock_build, mock_send):
        mock_fetch.return_value = SAMPLE_PERSPECTIVES

        from main import run
        run(dry_run=False)

        # 1 article per perspective group per topic, 4 topics
        # Neutral has 1 article, others empty = 1 article per topic = 5 total
        assert mock_summarize.call_count == 4

    @patch("main.send_email")
    @patch("main.build_email_html", return_value="<html>test</html>")
    @patch("main.summarize_article", return_value="Summary text")
    @patch("main.fetch_articles")
    def test_email_failure_does_not_crash(self, mock_fetch, mock_summarize,
                                          mock_build, mock_send):
        mock_fetch.return_value = SAMPLE_PERSPECTIVES
        mock_send.side_effect = Exception("SMTP error")

        from main import run
        # Should not raise
        run(dry_run=False)
