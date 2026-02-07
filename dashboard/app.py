"""
David Flip Dashboard - Flask Web Application

Provides a web interface to:
- View system status
- Review pending approvals
- See research findings
- View activity timeline
- Check tweet history
"""

import json
import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from functools import wraps

from flask import Flask, render_template, jsonify, request, redirect, url_for, session
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("DASHBOARD_SECRET_KEY", "david-flip-dashboard-secret-2026")

# Paths
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
APPROVAL_DB = DATA_DIR / "approvals.db"
RESEARCH_DB = DATA_DIR / "research.db"
AUDIT_LOG = DATA_DIR / "audit.db"

# Simple auth (single operator)
DASHBOARD_PASSWORD = os.environ.get("DASHBOARD_PASSWORD", "flipt2026")


def get_db(db_path):
    """Get database connection."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def login_required(f):
    """Decorator to require login."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function


# ============== AUTH ==============

@app.route("/login", methods=["GET", "POST"])
def login():
    """Login page."""
    if request.method == "POST":
        if request.form.get("password") == DASHBOARD_PASSWORD:
            session["logged_in"] = True
            return redirect(url_for("index"))
        return render_template("login.html", error="Invalid password")
    return render_template("login.html")


@app.route("/logout")
def logout():
    """Logout."""
    session.pop("logged_in", None)
    return redirect(url_for("login"))


# ============== MAIN PAGES ==============

@app.route("/")
@login_required
def index():
    """Dashboard home - overview of everything."""
    stats = get_stats()
    recent_activity = get_recent_activity(limit=20)
    pending_count = get_pending_approval_count()

    return render_template(
        "index.html",
        stats=stats,
        recent_activity=recent_activity,
        pending_count=pending_count
    )


@app.route("/approvals")
@login_required
def approvals():
    """Pending approvals page."""
    pending = get_pending_approvals()
    return render_template("approvals.html", approvals=pending)


@app.route("/research")
@login_required
def research():
    """Research findings page."""
    findings = get_research_findings(limit=50)
    return render_template("research.html", findings=findings)


@app.route("/tweets")
@login_required
def tweets():
    """Tweet history page."""
    tweet_history = get_tweet_history(limit=50)
    return render_template("tweets.html", tweets=tweet_history)


@app.route("/activity")
@login_required
def activity():
    """Full activity timeline."""
    timeline = get_recent_activity(limit=100)
    return render_template("activity.html", timeline=timeline)


# ============== API ENDPOINTS ==============

@app.route("/api/approve/<int:approval_id>", methods=["POST"])
@login_required
def api_approve(approval_id):
    """Approve a pending item."""
    try:
        conn = get_db(APPROVAL_DB)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE approvals SET status = 'approved', decided_at = ? WHERE id = ?",
            (datetime.now().isoformat(), approval_id)
        )
        conn.commit()
        conn.close()

        # Log the action
        log_activity("approval", f"Approved item #{approval_id}")

        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/reject/<int:approval_id>", methods=["POST"])
@login_required
def api_reject(approval_id):
    """Reject a pending item."""
    reason = request.json.get("reason", "Rejected by operator")
    try:
        conn = get_db(APPROVAL_DB)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE approvals SET status = 'rejected', decided_at = ?, rejection_reason = ? WHERE id = ?",
            (datetime.now().isoformat(), reason, approval_id)
        )
        conn.commit()
        conn.close()

        log_activity("approval", f"Rejected item #{approval_id}: {reason}")

        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/edit/<int:approval_id>", methods=["POST"])
@login_required
def api_edit(approval_id):
    """Edit and approve a pending item."""
    new_text = request.json.get("text", "")
    if not new_text:
        return jsonify({"success": False, "error": "No text provided"})

    try:
        conn = get_db(APPROVAL_DB)
        cursor = conn.cursor()

        # Get current action_data
        cursor.execute("SELECT action_data FROM approvals WHERE id = ?", (approval_id,))
        row = cursor.fetchone()
        if row:
            action_data = json.loads(row["action_data"])
            action_data["text"] = new_text

            cursor.execute(
                "UPDATE approvals SET action_data = ?, status = 'approved', decided_at = ? WHERE id = ?",
                (json.dumps(action_data), datetime.now().isoformat(), approval_id)
            )
            conn.commit()

        conn.close()

        log_activity("approval", f"Edited and approved item #{approval_id}")

        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/stats")
@login_required
def api_stats():
    """Get current stats."""
    return jsonify(get_stats())


@app.route("/api/activity")
@login_required
def api_activity():
    """Get recent activity."""
    limit = request.args.get("limit", 20, type=int)
    return jsonify(get_recent_activity(limit=limit))


# ============== DATA FUNCTIONS ==============

def get_david_status():
    """Get David's current status from status file."""
    status_file = DATA_DIR / "david_status.json"
    try:
        if status_file.exists():
            with open(status_file) as f:
                return json.load(f)
    except:
        pass
    return {
        "online": False,
        "timestamp_dubai": "Unknown",
        "status": "unknown"
    }


def get_stats():
    """Get dashboard statistics."""
    david_status = get_david_status()
    stats = {
        "pending_approvals": 0,
        "tweets_today": 0,
        "tweets_week": 0,
        "research_items_today": 0,
        "high_score_findings": 0,
        "system_status": david_status["status"],
        "david_online": david_status["online"],
        "david_timestamp": david_status["timestamp_dubai"]
    }

    try:
        # Pending approvals
        if APPROVAL_DB.exists():
            conn = get_db(APPROVAL_DB)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM approvals WHERE status = 'pending'")
            stats["pending_approvals"] = cursor.fetchone()[0]

            # Tweets today
            today = datetime.now().date().isoformat()
            cursor.execute(
                "SELECT COUNT(*) FROM approvals WHERE status = 'approved' AND action_type = 'tweet' AND decided_at LIKE ?",
                (f"{today}%",)
            )
            stats["tweets_today"] = cursor.fetchone()[0]

            # Tweets this week
            week_ago = (datetime.now() - timedelta(days=7)).isoformat()
            cursor.execute(
                "SELECT COUNT(*) FROM approvals WHERE status = 'approved' AND action_type = 'tweet' AND decided_at > ?",
                (week_ago,)
            )
            stats["tweets_week"] = cursor.fetchone()[0]
            conn.close()

        # Research items
        if RESEARCH_DB.exists():
            conn = get_db(RESEARCH_DB)
            cursor = conn.cursor()
            today = datetime.now().date().isoformat()
            cursor.execute(
                "SELECT COUNT(*) FROM research_items WHERE scraped_at LIKE ?",
                (f"{today}%",)
            )
            stats["research_items_today"] = cursor.fetchone()[0]

            cursor.execute(
                "SELECT COUNT(*) FROM research_items WHERE relevance_score >= 8"
            )
            stats["high_score_findings"] = cursor.fetchone()[0]
            conn.close()

        # System status is already set from david_status.json above

    except Exception as e:
        stats["error"] = str(e)

    return stats


def get_pending_approval_count():
    """Get count of pending approvals."""
    try:
        if APPROVAL_DB.exists():
            conn = get_db(APPROVAL_DB)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM approvals WHERE status = 'pending'")
            count = cursor.fetchone()[0]
            conn.close()
            return count
    except:
        pass
    return 0


def get_pending_approvals():
    """Get all pending approvals."""
    approvals = []
    try:
        if APPROVAL_DB.exists():
            conn = get_db(APPROVAL_DB)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, project_id, agent_id, action_type, action_data,
                       context_summary, created_at
                FROM approvals
                WHERE status = 'pending'
                ORDER BY created_at DESC
            """)
            for row in cursor.fetchall():
                approval = dict(row)
                approval["action_data"] = json.loads(approval["action_data"])
                approvals.append(approval)
            conn.close()
    except Exception as e:
        print(f"Error getting approvals: {e}")
    return approvals


def get_research_findings(limit=50):
    """Get research findings sorted by score."""
    findings = []
    try:
        if RESEARCH_DB.exists():
            conn = get_db(RESEARCH_DB)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, source, title, url, summary, relevance_score,
                       priority, suggested_action, scraped_at
                FROM research_items
                WHERE relevance_score > 0
                ORDER BY relevance_score DESC, scraped_at DESC
                LIMIT ?
            """, (limit,))
            findings = [dict(row) for row in cursor.fetchall()]
            conn.close()
    except Exception as e:
        print(f"Error getting research: {e}")
    return findings


def get_tweet_history(limit=50):
    """Get approved tweets."""
    tweets = []
    try:
        if APPROVAL_DB.exists():
            conn = get_db(APPROVAL_DB)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, action_data, context_summary, decided_at
                FROM approvals
                WHERE status = 'approved' AND action_type = 'tweet'
                ORDER BY decided_at DESC
                LIMIT ?
            """, (limit,))
            for row in cursor.fetchall():
                tweet = dict(row)
                tweet["action_data"] = json.loads(tweet["action_data"])
                tweets.append(tweet)
            conn.close()
    except Exception as e:
        print(f"Error getting tweets: {e}")
    return tweets


def get_recent_activity(limit=20):
    """Get recent activity from audit log."""
    activity = []
    try:
        audit_db = DATA_DIR / "audit.db"
        if audit_db.exists():
            conn = get_db(audit_db)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT timestamp, project_id, event_type, category, message, details
                FROM audit_log
                ORDER BY timestamp DESC
                LIMIT ?
            """, (limit,))
            activity = [dict(row) for row in cursor.fetchall()]
            conn.close()
    except Exception as e:
        print(f"Error getting activity: {e}")

    return activity


def log_activity(category, message):
    """Log an activity to the audit log."""
    try:
        audit_db = DATA_DIR / "audit.db"
        if audit_db.exists():
            conn = get_db(audit_db)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO audit_log (timestamp, project_id, event_type, category, message)
                VALUES (?, ?, ?, ?, ?)
            """, (datetime.now().isoformat(), "dashboard", "info", category, message))
            conn.commit()
            conn.close()
    except Exception as e:
        print(f"Error logging activity: {e}")


# ============== MAIN ==============

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
