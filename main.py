import argparse
import logging
import os
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler

from config import LOG_FILE, TIMEZONE, TOPICS
from email_sender import build_email_html, send_email
from news_fetcher import fetch_articles
from summarizer import summarize_article


def configure_logging():
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    file_handler = RotatingFileHandler(
        LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3
    )
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(stream_handler)


def _sanitize_filename(name: str) -> str:
    """Convert topic name to a safe filename."""
    return name.replace(" ", "_").replace(",", "").replace("&", "and").lower()


def run(dry_run: bool = False):
    configure_logging()
    logger = logging.getLogger(__name__)
    logger.info("News agent starting...")

    from audio_generator import generate_podcast

    try:
        from zoneinfo import ZoneInfo
    except ImportError:
        from backports.zoneinfo import ZoneInfo

    tz = ZoneInfo(TIMEZONE)
    now = datetime.now(tz)
    generated_at = now.strftime("%B %d, %Y %H:%M %Z")

    all_topic_audios = []

    for topic in TOPICS:
        logger.info("Processing topic: %s", topic["name"])

        perspectives = fetch_articles(topic)

        # Summarize articles in each perspective group
        for perspective, articles in perspectives.items():
            for article in articles:
                article["summary"] = summarize_article(article)

        has_articles = any(articles for articles in perspectives.values())
        if not has_articles:
            logger.warning("No articles found for topic '%s'. Skipping email.",
                           topic["name"])
            continue

        # Generate podcast audio
        all_articles = [a for arts in perspectives.values() for a in arts]
        topic_audio = b""
        try:
            topic_audio = generate_podcast(topic["name"], all_articles)
        except Exception as e:
            logger.error("Failed to generate podcast for '%s': %s",
                         topic["name"], e, exc_info=True)

        has_audio = len(topic_audio) > 0
        html = build_email_html(topic["name"], perspectives, generated_at,
                                has_audio=has_audio)
        subject = f"{topic['name']} News Digest - {now.strftime('%B %d, %Y %H:%M %Z')}"

        # Prepare audio attachments
        audio_attachments = []
        if topic_audio:
            safe_name = _sanitize_filename(topic["name"])
            audio_attachments.append((f"{safe_name}_podcast.mp3", topic_audio))
            all_topic_audios.append(topic_audio)

        if dry_run:
            output_file = f"{_sanitize_filename(topic['name'])}_digest.html"
            with open(output_file, "w") as f:
                f.write(html)
            logger.info("Dry run: HTML saved to %s", output_file)
            if topic_audio:
                audio_file = f"{_sanitize_filename(topic['name'])}_podcast.mp3"
                with open(audio_file, "wb") as f:
                    f.write(topic_audio)
                logger.info("Dry run: Audio saved to %s", audio_file)
        else:
            try:
                send_email(subject, html, recipients=topic.get("recipients"),
                           audio_attachments=audio_attachments)
            except Exception as e:
                logger.error("Failed to send email for topic '%s': %s",
                             topic["name"], e, exc_info=True)

    # Generate combined audio from all topics
    if all_topic_audios:
        combined_audio = b"".join(all_topic_audios)
        if dry_run:
            with open("combined_news_podcast.mp3", "wb") as f:
                f.write(combined_audio)
            logger.info("Dry run: Combined audio saved to combined_news_podcast.mp3")
        else:
            try:
                combined_subject = f"Combined News Podcast - {now.strftime('%B %d, %Y %H:%M %Z')}"
                combined_html = (
                    "<html><body>"
                    "<h2>Combined News Podcast</h2>"
                    "<p>Listen to today's AI-generated news discussion covering all topics.</p>"
                    f"<p><em>Generated: {generated_at}</em></p>"
                    "</body></html>"
                )
                send_email(
                    combined_subject,
                    combined_html,
                    audio_attachments=[("combined_news_podcast.mp3", combined_audio)],
                )
            except Exception as e:
                logger.error("Failed to send combined podcast email: %s",
                             e, exc_info=True)

    logger.info("News agent finished.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="News Agent - Fetch, Summarize, Email")
    parser.add_argument("--dry-run", action="store_true",
                        help="Save HTML files instead of sending emails")
    args = parser.parse_args()
    run(dry_run=args.dry_run)
