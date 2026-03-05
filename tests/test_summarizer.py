from unittest.mock import MagicMock, patch

import pytest
from openai import APIConnectionError, APIError, RateLimitError


SAMPLE_ARTICLE = {
    "title": "Test Article",
    "description": "A test article description",
    "content": "Full content of the test article for summarization.",
}


class TestSummarizeArticle:
    @patch("summarizer.client")
    def test_successful_summarization(self, mock_client):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "This is a summary."
        mock_client.chat.completions.create.return_value = mock_response

        from summarizer import summarize_article
        result = summarize_article(SAMPLE_ARTICLE)
        assert result == "This is a summary."
        mock_client.chat.completions.create.assert_called_once()

    @patch("summarizer.client")
    def test_api_error_falls_back_to_description(self, mock_client):
        mock_client.chat.completions.create.side_effect = APIError(
            message="Server error", request=MagicMock(), body=None
        )

        from summarizer import summarize_article
        result = summarize_article(SAMPLE_ARTICLE)
        assert result == "A test article description"

    @patch("summarizer.client")
    def test_rate_limit_falls_back(self, mock_client):
        mock_client.chat.completions.create.side_effect = RateLimitError(
            message="Rate limited", response=MagicMock(), body=None
        )

        from summarizer import summarize_article
        result = summarize_article(SAMPLE_ARTICLE)
        assert result == "A test article description"

    @patch("summarizer.client")
    def test_connection_error_falls_back(self, mock_client):
        mock_client.chat.completions.create.side_effect = APIConnectionError(
            request=MagicMock()
        )

        from summarizer import summarize_article
        result = summarize_article(SAMPLE_ARTICLE)
        assert result == "A test article description"

    @patch("summarizer.client")
    def test_no_content_or_description_returns_fallback(self, mock_client):
        from summarizer import summarize_article
        article = {"title": "Test", "content": "", "description": ""}
        result = summarize_article(article)
        assert result == ""
        mock_client.chat.completions.create.assert_not_called()

    @patch("summarizer.client")
    def test_empty_content_uses_description_for_api(self, mock_client):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Summary from desc"
        mock_client.chat.completions.create.return_value = mock_response

        from summarizer import summarize_article
        article = {"title": "Test", "content": "", "description": "Fallback desc"}
        result = summarize_article(article)
        assert result == "Summary from desc"
        mock_client.chat.completions.create.assert_called_once()

    @patch("summarizer.client")
    def test_content_truncated_to_3000(self, mock_client):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Summary"
        mock_client.chat.completions.create.return_value = mock_response

        from summarizer import summarize_article
        long_article = {
            "title": "Test",
            "content": "x" * 5000,
            "description": "Desc",
        }
        summarize_article(long_article)

        call_args = mock_client.chat.completions.create.call_args
        user_msg = call_args.kwargs["messages"][1]["content"]
        # Title prefix + 3000 chars of content
        assert len(user_msg) < 3100
