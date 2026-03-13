import json
import logging

from openai import APIConnectionError, APIError, OpenAI, RateLimitError

from config import (
    OPENAI_API_KEY,
    OPENAI_MODEL,
    PODCAST_MAX_ARTICLES,
    TTS_MODEL,
    TTS_VOICE_A,
    TTS_VOICE_B,
)

logger = logging.getLogger(__name__)

client = OpenAI(api_key=OPENAI_API_KEY)

SCRIPT_SYSTEM_PROMPT = (
    "You are a podcast script writer. Write a natural, engaging conversation "
    "between two hosts (Host A and Host B) discussing today's top news stories. "
    "Host A introduces topics and provides context. Host B adds analysis, asks "
    "questions, and offers different angles. Keep it conversational and concise. "
    "Cover the most important stories, grouping related ones together. "
    "Return ONLY a JSON array of objects with 'speaker' and 'text' fields. "
    'Example: [{"speaker": "Host A", "text": "Welcome to today\'s news digest..."}, '
    '{"speaker": "Host B", "text": "Thanks! Let\'s dive right in."}]'
)

VOICE_MAP = {
    "Host A": TTS_VOICE_A,
    "Host B": TTS_VOICE_B,
}


def generate_discussion_script(topic_name: str, articles: list[dict]) -> list[dict]:
    """Generate a two-host discussion script from article summaries."""
    limited = articles[:PODCAST_MAX_ARTICLES]

    article_text = "\n\n".join(
        f"- {a.get('title', 'No Title')} ({a.get('source', 'Unknown')}): "
        f"{a.get('summary', a.get('description', ''))}"
        for a in limited
    )

    user_message = (
        f"Topic: {topic_name}\n\n"
        f"Here are today's top stories:\n\n{article_text}\n\n"
        "Write a podcast discussion covering these stories. "
        "Keep the total script under 800 words."
    )

    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": SCRIPT_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            max_tokens=2000,
            temperature=0.7,
        )
        content = response.choices[0].message.content.strip()
        # Strip markdown code fences if present
        if content.startswith("```"):
            content = content.split("\n", 1)[1] if "\n" in content else content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
        segments = json.loads(content)
        if not isinstance(segments, list):
            logger.warning("Script is not a list, wrapping")
            segments = [segments]
        return segments
    except (json.JSONDecodeError, KeyError) as e:
        logger.error("Failed to parse discussion script: %s", e)
        return []
    except (RateLimitError, APIConnectionError, APIError) as e:
        logger.error("OpenAI error generating script: %s", e)
        return []


def generate_audio(script_segments: list[dict]) -> bytes:
    """Convert discussion script segments to MP3 audio with alternating voices."""
    if not script_segments:
        return b""

    mp3_parts = []
    for segment in script_segments:
        speaker = segment.get("speaker", "Host A")
        text = segment.get("text", "")
        if not text:
            continue

        voice = VOICE_MAP.get(speaker, TTS_VOICE_A)
        try:
            response = client.audio.speech.create(
                model=TTS_MODEL,
                voice=voice,
                input=text,
                response_format="mp3",
            )
            mp3_parts.append(response.content)
        except (RateLimitError, APIConnectionError, APIError) as e:
            logger.warning("TTS error for segment '%s...': %s", text[:30], e)
            continue

    return b"".join(mp3_parts)


def generate_podcast(topic_name: str, articles: list[dict]) -> bytes:
    """Generate a full podcast MP3 for a topic.

    Returns MP3 bytes, or empty bytes on failure.
    """
    if not articles:
        logger.info("No articles for topic '%s', skipping podcast", topic_name)
        return b""

    logger.info("Generating discussion script for '%s' (%d articles)",
                topic_name, min(len(articles), PODCAST_MAX_ARTICLES))
    script = generate_discussion_script(topic_name, articles)
    if not script:
        logger.warning("Empty script for topic '%s'", topic_name)
        return b""

    logger.info("Generating audio for '%s' (%d segments)", topic_name, len(script))
    audio = generate_audio(script)
    if audio:
        logger.info("Generated %d bytes of audio for '%s'", len(audio), topic_name)
    else:
        logger.warning("No audio generated for '%s'", topic_name)

    return audio
