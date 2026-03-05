import logging
import os
import smtplib
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
}


def build_email_html(topic_name: str, perspectives: dict[str, list[dict]],
                     generated_at: str) -> str:
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
    )


def send_email(subject: str, html_body: str) -> None:
    """Send an HTML email via Gmail SMTP."""
    msg = MIMEMultipart("alternative")
    msg["From"] = GMAIL_ADDRESS
    msg["To"] = EMAIL_RECIPIENT
    msg["Subject"] = subject

    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_ADDRESS, EMAIL_RECIPIENT, msg.as_string())

    logger.info("Email sent: %s", subject)
