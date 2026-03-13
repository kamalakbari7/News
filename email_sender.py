import logging
import os
import smtplib
from email.mime.audio import MIMEAudio
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from jinja2 import Environment, FileSystemLoader

from config import GMAIL_ADDRESS, GMAIL_APP_PASSWORD, EMAIL_RECIPIENT

logger = logging.getLogger(__name__)

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")

PERSPECTIVE_COLORS = {
    "Neutral": "#718096",
    "Left-Leaning": "#3182ce",
    "Right-Leaning": "#e53e3e",
    "Other Sources": "#805ad5",
    "International": "#2b6cb0",
    "Tech": "#38a169",
    "GIS & Earth Science": "#d69e2e",
}


def build_email_html(topic_name: str, perspectives: dict[str, list[dict]],
                     generated_at: str, has_audio: bool = False) -> str:
    """Render the HTML email template for a single topic."""
    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR), autoescape=True)
    template = env.get_template("email_template.html")

    has_articles = any(articles for articles in perspectives.values())

    return template.render(
        topic_name=topic_name,
        perspectives=perspectives,
        perspective_colors=PERSPECTIVE_COLORS,
        generated_at=generated_at,
        has_articles=has_articles,
        has_audio=has_audio,
    )


def send_email(subject: str, html_body: str, recipients=None,
               audio_attachments: list[tuple[str, bytes]] | None = None) -> None:
    """Send an HTML email via Gmail SMTP.

    audio_attachments: list of (filename, mp3_bytes) tuples to attach.
    """
    to_list = recipients or EMAIL_RECIPIENT
    msg = MIMEMultipart("mixed")
    msg["From"] = GMAIL_ADDRESS
    msg["To"] = ", ".join(to_list)
    msg["Subject"] = subject

    msg.attach(MIMEText(html_body, "html"))

    for filename, mp3_bytes in (audio_attachments or []):
        audio_part = MIMEAudio(mp3_bytes, _subtype="mpeg")
        audio_part.add_header("Content-Disposition", "attachment", filename=filename)
        msg.attach(audio_part)

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_ADDRESS, to_list, msg.as_string())

    logger.info("Email sent: %s (attachments: %d)", subject,
                len(audio_attachments or []))
