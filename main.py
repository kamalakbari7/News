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


def run(dry_run: bool = False):
    configure_logging()
    logger = logging.getLogger(__name__)
    logger.info("News agent starting...")

    try:
        from zoneinfo import ZoneInfo
    except ImportError:
        from backports.zoneinfo import ZoneInfo

    tz = ZoneInfo(TIMEZONE)
    now = datetime.now(tz)
    generated_at = now.strftime("%B %d, %Y %H:%M %Z")

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

        html = build_email_html(topic["name"], perspectives, generated_at)
        subject = f"{topic['name']} News Digest - {now.strftime('%B %d, %Y %H:%M %Z')}"

        if dry_run:
            output_file = f"{topic['name'].replace(' ', '_').lower()}_digest.html"
            with open(output_file, "w") as f:
                f.write(html)
            logger.info("Dry run: HTML saved to %s", output_file)
        else:
            try:
                send_email(subject, html)
            except Exception as e:
                logger.error("Failed to send email for topic '%s': %s",
                             topic["name"], e, exc_info=True)

    logger.info("News agent finished.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="News Agent - Fetch, Summarize, Email")
    parser.add_argument("--dry-run", action="store_true",
                        help="Save HTML files instead of sending emails")
    args = parser.parse_args()
    run(dry_run=args.dry_run)
