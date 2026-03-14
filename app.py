import logging
import os
import threading
from functools import wraps

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from flask import Flask, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

import db

logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-me-in-production")

ADMIN_PASSWORD_HASH = generate_password_hash(
    os.environ.get("ADMIN_PASSWORD", "admin")
)

scheduler = BackgroundScheduler()


# --- Auth ---

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("authenticated"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        password = request.form.get("password", "")
        if check_password_hash(ADMIN_PASSWORD_HASH, password):
            session["authenticated"] = True
            return redirect(url_for("dashboard"))
        flash("Invalid password.", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# --- Dashboard ---

@app.route("/")
@login_required
def dashboard():
    topics = db.get_topics()
    schedules = db.get_schedules()
    recent_runs = db.get_recent_runs(5)
    return render_template(
        "dashboard.html",
        topics=topics,
        schedules=schedules,
        recent_runs=recent_runs,
    )


# --- Topics ---

@app.route("/topics")
@login_required
def topics_list():
    topics = db.get_topics()
    return render_template("topics.html", topics=topics)


@app.route("/topics/new", methods=["GET", "POST"])
@login_required
def topic_new():
    if request.method == "POST":
        data = _parse_topic_form(request.form)
        db.save_topic(data)
        flash("Topic created.", "success")
        return redirect(url_for("topics_list"))
    return render_template("topic_form.html", topic=None)


@app.route("/topics/<int:topic_id>/edit", methods=["GET", "POST"])
@login_required
def topic_edit(topic_id):
    topic = db.get_topic(topic_id)
    if not topic:
        flash("Topic not found.", "error")
        return redirect(url_for("topics_list"))

    if request.method == "POST":
        data = _parse_topic_form(request.form)
        db.save_topic(data, topic_id=topic_id)
        flash("Topic updated.", "success")
        return redirect(url_for("topics_list"))

    return render_template("topic_form.html", topic=topic)


@app.route("/topics/<int:topic_id>/delete", methods=["POST"])
@login_required
def topic_delete(topic_id):
    db.delete_topic(topic_id)
    flash("Topic deleted.", "success")
    return redirect(url_for("topics_list"))


def _parse_topic_form(form):
    recipients_raw = form.get("recipients", "")
    recipients = [e.strip() for e in recipients_raw.splitlines() if e.strip()]
    return {
        "name": form.get("name", "").strip(),
        "query": form.get("query", "").strip(),
        "sort_by": form.get("sort_by", "popularity"),
        "language": form.get("language", "en"),
        "page_size": int(form.get("page_size", 20)),
        "recipients": recipients,
    }


# --- Schedule ---

@app.route("/schedule", methods=["GET", "POST"])
@login_required
def schedule():
    if request.method == "POST":
        hour = int(request.form.get("hour", 6))
        minute = int(request.form.get("minute", 0))
        timezone = request.form.get("timezone", "America/Toronto")
        db.save_schedule(hour, minute, timezone)
        rebuild_scheduler()
        flash("Schedule added.", "success")
        return redirect(url_for("schedule"))

    schedules = db.get_schedules()
    return render_template("schedule.html", schedules=schedules)


@app.route("/schedule/<int:schedule_id>/delete", methods=["POST"])
@login_required
def schedule_delete(schedule_id):
    db.delete_schedule(schedule_id)
    rebuild_scheduler()
    flash("Schedule removed.", "success")
    return redirect(url_for("schedule"))


# --- Logs ---

@app.route("/logs")
@login_required
def logs():
    recent_runs = db.get_recent_runs(20)
    return render_template("logs.html", runs=recent_runs)


# --- Run Now ---

_run_lock = threading.Lock()


@app.route("/run-now", methods=["POST"])
@login_required
def run_now():
    if _run_lock.locked():
        flash("A run is already in progress.", "error")
        return redirect(url_for("dashboard"))

    def _background_run():
        with _run_lock:
            from main import run
            try:
                run()
            except Exception as e:
                logger.error("Manual run failed: %s", e, exc_info=True)

    thread = threading.Thread(target=_background_run, daemon=True)
    thread.start()
    flash("News agent run started in background.", "success")
    return redirect(url_for("dashboard"))


# --- Scheduler ---

def rebuild_scheduler():
    """Rebuild APScheduler jobs from database schedule entries."""
    scheduler.remove_all_jobs()
    for s in db.get_schedules():
        if s["is_active"]:
            scheduler.add_job(
                _scheduled_run,
                CronTrigger(
                    hour=s["hour"],
                    minute=s["minute"],
                    timezone=s["timezone"],
                ),
                id=f"schedule_{s['id']}",
                replace_existing=True,
                max_instances=1,
            )
    logger.info("Scheduler rebuilt with %d jobs", len(scheduler.get_jobs()))


def _scheduled_run():
    """Run the news agent from the scheduler."""
    with _run_lock:
        from main import run
        try:
            run()
        except Exception as e:
            logger.error("Scheduled run failed: %s", e, exc_info=True)


# --- Startup ---

def init_app():
    """Initialize database and scheduler on startup."""
    db.init_db()
    rebuild_scheduler()
    if not scheduler.running:
        scheduler.start()


# Initialize when module loads (gunicorn imports this)
init_app()

if __name__ == "__main__":
    app.run(debug=True, port=5000)
