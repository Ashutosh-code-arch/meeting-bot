# meetingbot/db.py
import sqlite3, json, logging
from datetime import datetime
from pathlib import Path
from .config import DB_PATH

log = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS meetings (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  title        TEXT    DEFAULT 'Untitled Meeting',
  started_at   TEXT,
  ended_at     TEXT,
  duration_min REAL,
  audio_dir    TEXT,
  status       TEXT    DEFAULT 'recording',
  error        TEXT
);

CREATE TABLE IF NOT EXISTS jobs (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  meeting_id   INTEGER NOT NULL,
  step         TEXT    NOT NULL,
  status       TEXT    DEFAULT 'queued',
  result       TEXT,
  created_at   TEXT    DEFAULT (datetime('now')),
  updated_at   TEXT    DEFAULT (datetime('now')),
  FOREIGN KEY(meeting_id) REFERENCES meetings(id)
);

CREATE INDEX IF NOT EXISTS idx_jobs_step_status ON jobs(step, status);
"""


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def create_meeting(conn, audio_dir: str) -> int:
    cur = conn.execute(
        "INSERT INTO meetings (started_at, audio_dir, status) VALUES (?,?,?)",
        (datetime.now().isoformat(), audio_dir, "recording"))
    conn.commit()
    return cur.lastrowid


def finish_meeting(conn, meeting_id: int, title: str = ""):
    conn.execute(
        "UPDATE meetings SET ended_at=?, status='pending', title=? WHERE id=?",
        (datetime.now().isoformat(), title or "Untitled Meeting", meeting_id))
    for step in ['transcribe', 'diarize', 'merge', 'summarize', 'export']:
        conn.execute(
            "INSERT INTO jobs (meeting_id, step) VALUES (?,?)",
            (meeting_id, step))
    conn.commit()


def claim_job(conn, step: str):
    """
    Atomically claim one queued job for the given step.

    Uses a SELECT then UPDATE pattern instead of RETURNING to avoid
    the sqlite3 cursor conflict that happens when RETURNING keeps a
    statement open during commit().

    Returns a dict with 'id' and 'meeting_id', or None if no job queued.
    """
    # Step 1: find the oldest queued job for this step
    row = conn.execute(
        """SELECT id, meeting_id FROM jobs
           WHERE step = ? AND status = 'queued'
           ORDER BY created_at ASC
           LIMIT 1""",
        (step,)
    ).fetchone()

    if row is None:
        return None

    job_id     = row["id"]
    meeting_id = row["meeting_id"]

    # Step 2: claim it — only succeeds if it is still 'queued'
    # (guards against two workers racing on the same job)
    affected = conn.execute(
        """UPDATE jobs
           SET status = 'running', updated_at = datetime('now')
           WHERE id = ? AND status = 'queued'""",
        (job_id,)
    ).rowcount

    conn.commit()

    if affected == 0:
        # Another worker claimed it between our SELECT and UPDATE
        return None

    return {"id": job_id, "meeting_id": meeting_id}


def complete_job(conn, job_id: int, result: dict):
    conn.execute(
        "UPDATE jobs SET status='done', result=?, updated_at=datetime('now') WHERE id=?",
        (json.dumps(result), job_id))
    conn.commit()


def fail_job(conn, job_id: int, error: str):
    conn.execute(
        "UPDATE jobs SET status='failed', result=?, updated_at=datetime('now') WHERE id=?",
        (json.dumps({"error": error}), job_id))
    conn.commit()


def get_meeting_result(conn, meeting_id: int, step: str):
    row = conn.execute(
        "SELECT result FROM jobs WHERE meeting_id=? AND step=? AND status='done'",
        (meeting_id, step)).fetchone()
    return json.loads(row["result"]) if row else None


def list_meetings(conn):
    return conn.execute("""
      SELECT m.*,
             COUNT(j.id) FILTER(WHERE j.status='done')  AS done_steps,
             COUNT(j.id)                                 AS total_steps
      FROM meetings m
      LEFT JOIN jobs j ON j.meeting_id = m.id
      GROUP BY m.id
      ORDER BY m.started_at DESC
      LIMIT 50""").fetchall()
