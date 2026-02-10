"""One-time script: approve Princeton tweets and schedule 4h apart + video."""
import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path

FEEDBACK_DIR = Path("data/content_feedback")
FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)

conn = sqlite3.connect("data/approval_queue.db")
now = datetime.utcnow()

# Approve tweets 60-64 and schedule 4h apart
tweet_ids = [60, 61, 62, 63, 64]
for i, tid in enumerate(tweet_ids):
    scheduled_time = now + timedelta(hours=i * 4)
    conn.execute(
        "UPDATE approvals SET status='approved', reviewed_at=? WHERE id=?",
        (now.isoformat(), tid),
    )

    row = conn.execute(
        "SELECT action_data FROM approvals WHERE id=?", (tid,)
    ).fetchone()
    action_data = json.loads(row[0])

    schedule_data = {
        "approval_id": tid,
        "action_type": "tweet",
        "content_type": "tweet",
        "action_data": action_data,
        "scheduled_time": scheduled_time.isoformat(),
        "platforms": ["twitter"],
    }

    ts = now.strftime("%Y%m%d_%H%M%S")
    fname = FEEDBACK_DIR / f"schedule_{tid}_{ts}.json"
    with open(fname, "w") as f:
        json.dump(schedule_data, f)

    print(f"Tweet #{tid} -> scheduled {scheduled_time.strftime('%H:%M UTC')}")

conn.commit()

# Execute video #58 (15-Minute Cities)
video_row = conn.execute(
    "SELECT action_data FROM approvals WHERE id=58"
).fetchone()
if video_row:
    video_data = json.loads(video_row[0])
    exec_data = {
        "approval_id": 58,
        "action_type": "video_distribute",
        "action_data": video_data,
    }
    ts = now.strftime("%Y%m%d_%H%M%S")
    fname = FEEDBACK_DIR / f"execute_58_{ts}.json"
    with open(fname, "w") as f:
        json.dump(exec_data, f)
    print("Video #58 (15-Minute Cities) -> queued for immediate distribution")

conn.close()
print("Done! Oprah picks these up in the next 30-second poll.")
