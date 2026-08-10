"""
SQLite persistence layer (replaces the in-memory dicts from Phase 2).

Why now: the API worked but forgot everything on restart. A coordination
tool that loses its decisions is worse than useless -- it erodes trust.
SQLite is the smallest thing that actually persists: one file, no server,
stdlib-only, and it survives a hard kill of the process (that's tested
explicitly, not assumed).

Layout: five tables matching the API's object model --
  trials -> rules            (1:N)
  assessments -> rule_results (1:N)
  assessments -> decisions    (1:1, nullable; a decision never exists
                               until a coordinator records one)

Every store function opens a fresh connection for the duration of the
call and commits/rolls back/ closes it -- safe under uvicorn's thread
pool, and WAL mode lets a reader proceed while a writer commits.
"""

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(
    os.environ.get("CAREMATCH_DB_PATH", str(Path(__file__).resolve().parent / "data" / "carematch.db"))
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS trials (
    trial_id   TEXT PRIMARY KEY,
    trial_name TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS rules (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    trial_id  TEXT NOT NULL REFERENCES trials(trial_id) ON DELETE CASCADE,
    rule_id   TEXT NOT NULL,
    rule_text TEXT NOT NULL,
    category  TEXT NOT NULL,
    UNIQUE (trial_id, rule_id)
);

CREATE TABLE IF NOT EXISTS assessments (
    assessment_id    TEXT PRIMARY KEY,
    trial_id         TEXT NOT NULL REFERENCES trials(trial_id),
    patient_id       TEXT NOT NULL,
    patient_record   TEXT NOT NULL,
    suggested_status TEXT NOT NULL,
    provider_used    TEXT NOT NULL,
    model_used       TEXT NOT NULL,
    created_at       TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS rule_results (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    assessment_id TEXT NOT NULL REFERENCES assessments(assessment_id) ON DELETE CASCADE,
    rule_id       TEXT NOT NULL,
    rule_text     TEXT NOT NULL,
    status        TEXT NOT NULL,
    evidence      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS decisions (
    assessment_id   TEXT PRIMARY KEY REFERENCES assessments(assessment_id) ON DELETE CASCADE,
    decision        TEXT NOT NULL,
    decision_reason TEXT,
    decided_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


@contextmanager
def _connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with _connect() as conn:
        conn.executescript(SCHEMA)


def create_trial(trial_id: str, trial_name: str, rules: list[dict]):
    """Register (or re-register) a trial and its rules. Re-registering the
    same trial_id replaces its rules, so re-running the eval batch or a test
    suite doesn't error on duplicate keys."""
    with _connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO trials (trial_id, trial_name) VALUES (?, ?)",
            (trial_id, trial_name),
        )
        conn.execute("DELETE FROM rules WHERE trial_id = ?", (trial_id,))
        conn.executemany(
            "INSERT INTO rules (trial_id, rule_id, rule_text, category) VALUES (?, ?, ?, ?)",
            [(trial_id, r["rule_id"], r["rule_text"], r["category"]) for r in rules],
        )


def get_trial(trial_id: str) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT trial_id, trial_name FROM trials WHERE trial_id = ?", (trial_id,)
        ).fetchone()
        if row is None:
            return None
        rules = conn.execute(
            "SELECT rule_id, rule_text, category FROM rules WHERE trial_id = ? ORDER BY id",
            (trial_id,),
        ).fetchall()
        return {
            "trial_id": row["trial_id"],
            "trial_name": row["trial_name"],
            "rules": [dict(r) for r in rules],
        }


def list_trials() -> list[dict]:
    with _connect() as conn:
        rows = conn.execute("SELECT trial_id, trial_name FROM trials ORDER BY created_at").fetchall()
        result = []
        for row in rows:
            rules = conn.execute(
                "SELECT rule_id, rule_text, category FROM rules WHERE trial_id = ? ORDER BY id",
                (row["trial_id"],),
            ).fetchall()
            result.append(
                {
                    "trial_id": row["trial_id"],
                    "trial_name": row["trial_name"],
                    "rules": [dict(r) for r in rules],
                }
            )
        return result


def save_assessment(
    assessment_id: str,
    trial_id: str,
    patient_id: str,
    patient_record: str,
    suggested_status: str,
    provider_used: str,
    model_used: str,
    rule_results: list[dict],
):
    """Persist an assessment plus all of its per-rule results in one
    transaction -- the two must never be observable out of sync."""
    with _connect() as conn:
        conn.execute(
            "INSERT INTO assessments "
            "(assessment_id, trial_id, patient_id, patient_record, suggested_status, provider_used, model_used) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                assessment_id,
                trial_id,
                patient_id,
                patient_record,
                suggested_status,
                provider_used,
                model_used,
            ),
        )
        conn.executemany(
            "INSERT INTO rule_results (assessment_id, rule_id, rule_text, status, evidence) "
            "VALUES (?, ?, ?, ?, ?)",
            [
                (
                    assessment_id,
                    rr["rule_id"],
                    rr["rule_text"],
                    rr["status"],
                    rr["evidence"],
                )
                for rr in rule_results
            ],
        )


def get_assessment(assessment_id: str) -> dict | None:
    """Rehydrate an assessment by joining across all three tables:
    assessments + rule_results + decisions. A decision row only exists if
    one was recorded, so decision/decision_reason are None for undecided
    assessments -- same shape the API returned before SQLite existed."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT assessment_id, trial_id, patient_id, suggested_status, provider_used, model_used "
            "FROM assessments WHERE assessment_id = ?",
            (assessment_id,),
        ).fetchone()
        if row is None:
            return None
        rule_results = conn.execute(
            "SELECT rule_id, rule_text, status, evidence FROM rule_results "
            "WHERE assessment_id = ? ORDER BY id",
            (assessment_id,),
        ).fetchall()
        decision = conn.execute(
            "SELECT decision, decision_reason FROM decisions WHERE assessment_id = ?",
            (assessment_id,),
        ).fetchone()
        return {
            "assessment_id": row["assessment_id"],
            "trial_id": row["trial_id"],
            "patient_id": row["patient_id"],
            "suggested_status": row["suggested_status"],
            "provider_used": row["provider_used"],
            "model_used": row["model_used"],
            "rule_results": [dict(r) for r in rule_results],
            "decision": decision["decision"] if decision else None,
            "decision_reason": decision["decision_reason"] if decision else None,
        }


def set_decision(assessment_id: str, decision: str, reason: str | None) -> bool:
    """Record the coordinator's decision. Returns False (and records
    nothing) if the assessment doesn't exist -- the caller turns that into
    a 404, so an unknown id can never silently invent a decision row."""
    with _connect() as conn:
        exists = conn.execute(
            "SELECT 1 FROM assessments WHERE assessment_id = ?", (assessment_id,)
        ).fetchone()
        if exists is None:
            return False
        conn.execute(
            "INSERT INTO decisions (assessment_id, decision, decision_reason) VALUES (?, ?, ?) "
            "ON CONFLICT(assessment_id) DO UPDATE SET "
            "decision = excluded.decision, decision_reason = excluded.decision_reason",
            (assessment_id, decision, reason),
        )
        return True
