import os
import sqlite3
from datetime import datetime

DB_PATH = os.environ.get("DB_PATH", os.path.join(os.path.dirname(__file__), "data", "news_agent.db"))


def _get_conn():
    """Get a short-lived SQLite connection."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Create tables if they don't exist and seed defaults on first run."""
    conn = _get_conn()
    try:
        schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
        with open(schema_path) as f:
            conn.executescript(f.read())

        # Seed default topics from config if table is empty
        count = conn.execute("SELECT COUNT(*) FROM topics").fetchone()[0]
        if count == 0:
            _seed_defaults(conn)

        conn.commit()
    finally:
        conn.close()


def _seed_defaults(conn):
    """Seed topics and schedule from hardcoded config on first run."""
    # Import here to avoid circular imports
    from config import TOPICS, GMAIL_ADDRESS

    for topic in TOPICS:
        cursor = conn.execute(
            "INSERT INTO topics (name, query, sort_by, language, page_size) "
            "VALUES (?, ?, ?, ?, ?)",
            (topic["name"], topic["query"], topic.get("sort_by", "popularity"),
             topic.get("language", "en"), topic.get("page_size", 20)),
        )
        topic_id = cursor.lastrowid

        # Add default recipient
        conn.execute(
            "INSERT INTO topic_recipients (topic_id, email) VALUES (?, ?)",
            (topic_id, GMAIL_ADDRESS),
        )

    # Seed default schedule: 6am and 6pm Toronto time
    conn.execute(
        "INSERT INTO schedule (hour, minute, timezone) VALUES (?, ?, ?)",
        (6, 0, "America/Toronto"),
    )
    conn.execute(
        "INSERT INTO schedule (hour, minute, timezone) VALUES (?, ?, ?)",
        (18, 0, "America/Toronto"),
    )


# --- Topics ---

def get_topics():
    """Return active topics as list of dicts (same format as config.TOPICS)."""
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM topics WHERE is_active = 1 ORDER BY id"
        ).fetchall()

        topics = []
        for row in rows:
            recipients = [
                r["email"] for r in conn.execute(
                    "SELECT email FROM topic_recipients WHERE topic_id = ?",
                    (row["id"],),
                ).fetchall()
            ]
            topics.append({
                "id": row["id"],
                "name": row["name"],
                "query": row["query"],
                "sort_by": row["sort_by"],
                "language": row["language"],
                "page_size": row["page_size"],
                "recipients": recipients if recipients else None,
            })
        return topics
    finally:
        conn.close()


def get_topic(topic_id):
    """Return a single topic dict or None."""
    conn = _get_conn()
    try:
        row = conn.execute("SELECT * FROM topics WHERE id = ?", (topic_id,)).fetchone()
        if not row:
            return None

        recipients = [
            r["email"] for r in conn.execute(
                "SELECT email FROM topic_recipients WHERE topic_id = ?",
                (topic_id,),
            ).fetchall()
        ]
        return {
            "id": row["id"],
            "name": row["name"],
            "query": row["query"],
            "sort_by": row["sort_by"],
            "language": row["language"],
            "page_size": row["page_size"],
            "is_active": row["is_active"],
            "recipients": recipients,
        }
    finally:
        conn.close()


def save_topic(data, topic_id=None):
    """Insert or update a topic. Returns the topic id."""
    conn = _get_conn()
    try:
        if topic_id:
            conn.execute(
                "UPDATE topics SET name=?, query=?, sort_by=?, language=?, "
                "page_size=?, updated_at=datetime('now') WHERE id=?",
                (data["name"], data["query"], data.get("sort_by", "popularity"),
                 data.get("language", "en"), data.get("page_size", 20), topic_id),
            )
        else:
            cursor = conn.execute(
                "INSERT INTO topics (name, query, sort_by, language, page_size) "
                "VALUES (?, ?, ?, ?, ?)",
                (data["name"], data["query"], data.get("sort_by", "popularity"),
                 data.get("language", "en"), data.get("page_size", 20)),
            )
            topic_id = cursor.lastrowid

        # Update recipients
        emails = data.get("recipients", [])
        set_recipients(topic_id, emails, conn=conn)

        conn.commit()
        return topic_id
    finally:
        conn.close()


def delete_topic(topic_id):
    """Delete a topic and its recipients."""
    conn = _get_conn()
    try:
        conn.execute("DELETE FROM topic_recipients WHERE topic_id = ?", (topic_id,))
        conn.execute("DELETE FROM topics WHERE id = ?", (topic_id,))
        conn.commit()
    finally:
        conn.close()


def set_recipients(topic_id, emails, conn=None):
    """Replace all recipients for a topic."""
    should_close = conn is None
    if conn is None:
        conn = _get_conn()
    try:
        conn.execute("DELETE FROM topic_recipients WHERE topic_id = ?", (topic_id,))
        for email in emails:
            email = email.strip()
            if email:
                conn.execute(
                    "INSERT OR IGNORE INTO topic_recipients (topic_id, email) "
                    "VALUES (?, ?)",
                    (topic_id, email),
                )
        if should_close:
            conn.commit()
    finally:
        if should_close:
            conn.close()


# --- Schedule ---

def get_schedules():
    """Return all schedule entries."""
    conn = _get_conn()
    try:
        rows = conn.execute("SELECT * FROM schedule ORDER BY hour, minute").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def save_schedule(hour, minute=0, timezone="America/Toronto"):
    """Add a schedule entry. Returns the id."""
    conn = _get_conn()
    try:
        cursor = conn.execute(
            "INSERT INTO schedule (hour, minute, timezone) VALUES (?, ?, ?)",
            (hour, minute, timezone),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def delete_schedule(schedule_id):
    """Delete a schedule entry."""
    conn = _get_conn()
    try:
        conn.execute("DELETE FROM schedule WHERE id = ?", (schedule_id,))
        conn.commit()
    finally:
        conn.close()


# --- Run Log ---

def log_run_start():
    """Log the start of a news agent run. Returns the run id."""
    conn = _get_conn()
    try:
        cursor = conn.execute(
            "INSERT INTO run_log (status) VALUES ('running')"
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def log_run_end(run_id, status, topics_processed=0, error_message=None):
    """Update a run log entry with completion info."""
    conn = _get_conn()
    try:
        conn.execute(
            "UPDATE run_log SET finished_at=datetime('now'), status=?, "
            "topics_processed=?, error_message=? WHERE id=?",
            (status, topics_processed, error_message, run_id),
        )
        conn.commit()
    finally:
        conn.close()


def get_recent_runs(limit=10):
    """Return recent run log entries."""
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM run_log ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
