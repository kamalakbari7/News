import argparse
import logging
import os
import sys
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler

import glob as globmod

from config import LOG_FILE, PODCAST_BASE_URL, PODCAST_DIR, PODCAST_KEEP_DAYS, TIMEZONE, validate_config
from db import get_topics, init_db, log_run_end, log_run_start
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


def _cleanup_old_podcasts(logger):
    """Remove podcast files older than PODCAST_KEEP_DAYS."""
    cutoff = datetime.now() - timedelta(days=PODCAST_KEEP_DAYS)
    for filepath in globmod.glob(os.path.join(PODCAST_DIR, "daily_brief_*.mp3")):
        try:
            mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
            if mtime < cutoff:
                os.remove(filepath)
                logger.info("Removed old podcast: %s", filepath)
        except OSError as e:
            logger.warning("Failed to remove old podcast %s: %s", filepath, e)


def run(dry_run: bool = False):
    configure_logging()
    logger = logging.getLogger(__name__)
    logger.info("News agent starting...")

    validate_config()
    init_db()

    from audio_generator import generate_podcast

    try:
        from zoneinfo import ZoneInfo
    except ImportError:
        from backports.zoneinfo import ZoneInfo

    tz = ZoneInfo(TIMEZONE)
    now = datetime.now(tz)
    generated_at = now.strftime("%B %d, %Y %H:%M %Z")

    topics = get_topics()
    run_id = log_run_start()
    all_topic_audios = []
    topics_processed = 0

    try:
        for topic in topics:
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

            topics_processed += 1

        # Save combined audio to VPS and email download link
        if all_topic_audios:
            combined_audio = b"".join(all_topic_audios)
            date_str = now.strftime("%Y-%m-%d")
            filename = f"daily_brief_{date_str}.mp3"

            if dry_run:
                with open(filename, "wb") as f:
                    f.write(combined_audio)
                logger.info("Dry run: Combined audio saved to %s", filename)
            else:
                try:
                    os.makedirs(PODCAST_DIR, exist_ok=True)
                    filepath = os.path.join(PODCAST_DIR, filename)
                    with open(filepath, "wb") as f:
                        f.write(combined_audio)
                    logger.info("Combined audio saved to %s (%d bytes)",
                                filepath, len(combined_audio))

                    # Clean up old podcast files
                    _cleanup_old_podcasts(logger)

                    # Send email with download link
                    download_url = f"{PODCAST_BASE_URL}/{filename}"
                    combined_subject = f"Combined News Podcast - {now.strftime('%B %d, %Y %H:%M %Z')}"
                    combined_html = (
                        "<html><body>"
                        "<h2>Combined News Podcast</h2>"
                        "<p>Listen to today's AI-generated news discussion covering all topics.</p>"
                        f'<p><a href="{download_url}" style="display:inline-block;padding:12px 24px;'
                        "background-color:#1a1a2e;color:#ffffff;text-decoration:none;"
                        'border-radius:6px;font-weight:bold;">Download Podcast MP3</a></p>'
                        f"<p><em>Generated: {generated_at}</em></p>"
                        "</body></html>"
                    )
                    send_email(combined_subject, combined_html)
                except Exception as e:
                    logger.error("Failed to save/send combined podcast: %s",
                                 e, exc_info=True)

        log_run_end(run_id, "success", topics_processed)
    except Exception as e:
        log_run_end(run_id, "error", topics_processed, str(e))
        logger.error("News agent failed: %s", e, exc_info=True)
        raise

    logger.info("News agent finished.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="News Agent - Fetch, Summarize, Email")
    parser.add_argument("--dry-run", action="store_true",
                        help="Save HTML files instead of sending emails")
    args = parser.parse_args()
    run(dry_run=args.dry_run)
