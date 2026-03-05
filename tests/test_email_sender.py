from unittest.mock import MagicMock, patch

import pytest

from email_sender import build_email_html, send_email


SAMPLE_PERSPECTIVES = {
    "Neutral": [
        {
            "title": "Neutral Article",
            "source": "Reuters",
            "url": "https://reuters.com/article",
            "summary": "A neutral summary.",
            "published_at": "2026-03-04T10:00:00Z",
        }
    ],
    "Left-Leaning": [
        {
            "title": "Left Article",
            "source": "CNN",
            "url": "https://cnn.com/article",
            "summary": "A left-leaning summary.",
            "published_at": "2026-03-04T11:00:00Z",
        }
    ],
    "Right-Leaning": [],
}


class TestBuildEmailHtml:
    def test_contains_topic_name(self):
        html = build_email_html("Iran", SAMPLE_PERSPECTIVES, "March 4, 2026 12:00 EST")
        assert "Iran" in html

    def test_contains_article_titles(self):
        html = build_email_html("Iran", SAMPLE_PERSPECTIVES, "March 4, 2026 12:00 EST")
        assert "Neutral Article" in html
        assert "Left Article" in html

    def test_contains_perspective_headers(self):
        html = build_email_html("Iran", SAMPLE_PERSPECTIVES, "March 4, 2026 12:00 EST")
        assert "Neutral" in html
        assert "Left-Leaning" in html

    def test_contains_perspective_colors(self):
        html = build_email_html("Iran", SAMPLE_PERSPECTIVES, "March 4, 2026 12:00 EST")
        assert "#718096" in html  # Neutral gray
        assert "#3182ce" in html  # Left blue

    def test_contains_article_urls(self):
        html = build_email_html("Iran", SAMPLE_PERSPECTIVES, "March 4, 2026 12:00 EST")
        assert "https://reuters.com/article" in html
        assert "https://cnn.com/article" in html

    def test_contains_generated_at(self):
        html = build_email_html("Iran", SAMPLE_PERSPECTIVES, "March 4, 2026 12:00 EST")
        assert "March 4, 2026 12:00 EST" in html

    def test_empty_perspectives(self):
        empty = {"Neutral": [], "Left-Leaning": [], "Right-Leaning": []}
        html = build_email_html("Iran", empty, "March 4, 2026 12:00 EST")
        assert "Iran" in html  # Still contains topic name


class TestSendEmail:
    @patch("email_sender.smtplib.SMTP")
    def test_sends_email_via_smtp(self, mock_smtp_class):
        mock_server = MagicMock()
        mock_smtp_class.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp_class.return_value.__exit__ = MagicMock(return_value=False)

        send_email("Test Subject", "<h1>Test</h1>")

        mock_smtp_class.assert_called_once_with("smtp.gmail.com", 587)
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once()
        mock_server.sendmail.assert_called_once()

    @patch("email_sender.smtplib.SMTP")
    def test_email_subject_in_message(self, mock_smtp_class):
        mock_server = MagicMock()
        mock_smtp_class.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp_class.return_value.__exit__ = MagicMock(return_value=False)

        send_email("Iran News Digest", "<h1>Test</h1>")

        sendmail_args = mock_server.sendmail.call_args[0]
        message_str = sendmail_args[2]
        assert "Iran News Digest" in message_str
