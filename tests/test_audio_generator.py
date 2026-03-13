import json
from unittest.mock import MagicMock, patch

import pytest
from openai import APIConnectionError, APIError, RateLimitError

SAMPLE_ARTICLES = [
    {
        "title": "Test Article 1",
        "source": "BBC",
        "summary": "Summary of article 1.",
        "description": "Description 1",
    },
    {
        "title": "Test Article 2",
        "source": "CNN",
        "summary": "Summary of article 2.",
        "description": "Description 2",
    },
]

SAMPLE_SCRIPT = [
    {"speaker": "Neg", "text": "Welcome to today's news."},
    {"speaker": "Kam", "text": "Let's discuss the top stories."},
    {"speaker": "Neg", "text": "First up, article one."},
]


class TestGenerateDiscussionScript:
    @patch("audio_generator.client")
    def test_successful_script_generation(self, mock_client):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps(SAMPLE_SCRIPT)
        mock_client.chat.completions.create.return_value = mock_response

        from audio_generator import generate_discussion_script
        result = generate_discussion_script("Test Topic", SAMPLE_ARTICLES)

        assert len(result) == 3
        assert result[0]["speaker"] == "Neg"
        assert result[1]["speaker"] == "Kam"
        mock_client.chat.completions.create.assert_called_once()

    @patch("audio_generator.client")
    def test_script_with_markdown_code_fences(self, mock_client):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = (
            "```json\n" + json.dumps(SAMPLE_SCRIPT) + "\n```"
        )
        mock_client.chat.completions.create.return_value = mock_response

        from audio_generator import generate_discussion_script
        result = generate_discussion_script("Test Topic", SAMPLE_ARTICLES)

        assert len(result) == 3

    @patch("audio_generator.client")
    def test_api_error_returns_empty(self, mock_client):
        mock_client.chat.completions.create.side_effect = APIError(
            message="Server error", request=MagicMock(), body=None
        )

        from audio_generator import generate_discussion_script
        result = generate_discussion_script("Test Topic", SAMPLE_ARTICLES)

        assert result == []

    @patch("audio_generator.client")
    def test_invalid_json_returns_empty(self, mock_client):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Not valid JSON"
        mock_client.chat.completions.create.return_value = mock_response

        from audio_generator import generate_discussion_script
        result = generate_discussion_script("Test Topic", SAMPLE_ARTICLES)

        assert result == []

    @patch("audio_generator.client")
    def test_limits_articles_to_max(self, mock_client):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps(SAMPLE_SCRIPT)
        mock_client.chat.completions.create.return_value = mock_response

        many_articles = [{"title": f"Art {i}", "source": "X", "summary": f"Sum {i}"}
                         for i in range(20)]

        from audio_generator import generate_discussion_script
        generate_discussion_script("Test Topic", many_articles)

        call_args = mock_client.chat.completions.create.call_args
        user_msg = call_args.kwargs["messages"][1]["content"]
        # Should only include PODCAST_MAX_ARTICLES (10) articles
        assert user_msg.count("- Art ") == 10


class TestGenerateAudio:
    @patch("audio_generator.client")
    def test_successful_audio_generation(self, mock_client):
        mock_response = MagicMock()
        mock_response.content = b"fake-mp3-data"
        mock_client.audio.speech.create.return_value = mock_response

        from audio_generator import generate_audio
        result = generate_audio(SAMPLE_SCRIPT)

        assert result == b"fake-mp3-data" * 3
        assert mock_client.audio.speech.create.call_count == 3

    @patch("audio_generator.client")
    def test_uses_correct_voices(self, mock_client):
        mock_response = MagicMock()
        mock_response.content = b"data"
        mock_client.audio.speech.create.return_value = mock_response

        from audio_generator import generate_audio
        generate_audio(SAMPLE_SCRIPT)

        calls = mock_client.audio.speech.create.call_args_list
        assert calls[0].kwargs["voice"] == "alloy"   # Neg
        assert calls[1].kwargs["voice"] == "onyx"     # Kam
        assert calls[2].kwargs["voice"] == "alloy"   # Neg

    @patch("audio_generator.client")
    def test_empty_segments_returns_empty(self, mock_client):
        from audio_generator import generate_audio
        result = generate_audio([])

        assert result == b""
        mock_client.audio.speech.create.assert_not_called()

    @patch("audio_generator.client")
    def test_tts_error_skips_segment(self, mock_client):
        mock_response = MagicMock()
        mock_response.content = b"good-data"

        mock_client.audio.speech.create.side_effect = [
            mock_response,
            APIError(message="TTS error", request=MagicMock(), body=None),
            mock_response,
        ]

        from audio_generator import generate_audio
        result = generate_audio(SAMPLE_SCRIPT)

        assert result == b"good-data" * 2  # 2 successful, 1 skipped


class TestGeneratePodcast:
    @patch("audio_generator.generate_audio")
    @patch("audio_generator.generate_discussion_script")
    def test_full_pipeline(self, mock_script, mock_audio):
        mock_script.return_value = SAMPLE_SCRIPT
        mock_audio.return_value = b"full-podcast-mp3"

        from audio_generator import generate_podcast
        result = generate_podcast("Iran", SAMPLE_ARTICLES)

        assert result == b"full-podcast-mp3"
        mock_script.assert_called_once_with("Iran", SAMPLE_ARTICLES)
        mock_audio.assert_called_once_with(SAMPLE_SCRIPT)

    @patch("audio_generator.generate_discussion_script")
    def test_empty_articles_returns_empty(self, mock_script):
        from audio_generator import generate_podcast
        result = generate_podcast("Iran", [])

        assert result == b""
        mock_script.assert_not_called()

    @patch("audio_generator.generate_discussion_script")
    def test_empty_script_returns_empty(self, mock_script):
        mock_script.return_value = []

        from audio_generator import generate_podcast
        result = generate_podcast("Iran", SAMPLE_ARTICLES)

        assert result == b""
