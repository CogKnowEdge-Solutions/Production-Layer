"""
Postgres persistence layer (replaces the SQLite layer from earlier phases).

Why Postgres: the API worked but the data lived in a single file on the
app server. A coordination tool that loses its decisions is worse than
useless -- it erodes trust. Postgres keeps the same five-table model with
the same foreign keys and ON DELETE CASCADE behaviour, but the data now
lives in a real, remotely-hosted database that survives a hard kill of
the app process (that's tested explicitly, not assumed).

Layout: five tables matching the API's object model --
  trials -> rules            (1:N)
  assessments -> rule_results (1:N)
  assessments -> decisions    (1:1, nullable; a decision never exists
                               until a coordinator records one)

Every store function runs inside its own transaction: the call checks out a
connection from a small shared pool, commits/rolls back, and returns the
connection -- safe under uvicorn's thread pool, and Postgres' MVCC lets a
reader proceed while a writer commits.

Connection: the full Postgres DSN is read from DATABASE_URL (the direct
connection string, e.g. postgresql://postgres:...@db.<project>.supabase.co:5432/postgres).
Optional CAREMATCH_DB_SCHEMA (default "public") scopes all tables to a
single schema -- the test suite points it at a throwaway schema in the
same database so tests never touch real data.
"""

import os
import re
import time
from contextlib import contextmanager

import psycopg2
from dotenv import load_dotenv
from psycopg2 import pool as pg_pool
from psycopg2 import sql
from psycopg2.extras import DictCursor

# db.py is imported before main.py's own load_dotenv() call, so it loads
# api/.env itself -- otherwise the manual (non-Docker) run would never see
# DATABASE_URL. Existing environment variables always win over the file.
load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL", "")
DB_SCHEMA = os.environ.get("CAREMATCH_DB_SCHEMA", "public")

if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", DB_SCHEMA):
    raise RuntimeError(
        f"CAREMATCH_DB_SCHEMA must be a plain SQL identifier, got {DB_SCHEMA!r}"
    )

# A small shared pool instead of a fresh connection per call. With SQLite a
# connection was an open of a local file (cheap), but a Postgres connection
# is a full TCP+TLS+auth round trip to a remote server (~2s), so opening one
# per store call made every request and the whole test suite impractically
# slow. ThreadedConnectionPool is thread-safe, and each _connect() call still
# commits/rolls back atomically within its own transaction. maxconn stays well
# under Supabase's direct-connection limit (60).
_POOL: pg_pool.ThreadedConnectionPool | None = None

# Last time each pooled connection was verified alive (keyed by id(conn)).
# A connection that has been idle in the pool for more than a couple of
# minutes may have been idle-timed-out by Supabase, so it gets re-verified on
# checkout; connections in steady use skip the check to save a round trip.
_LAST_PING_TS: dict[int, float] = {}
_IDLE_PING_SECONDS = 120.0


def _get_pool():
    global _POOL
    if _POOL is None:
        _POOL = pg_pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=10,
            dsn=_require_database_url(),
            cursor_factory=DictCursor,
            # Server-side search_path applied at connect time -- one less
            # round trip per call than a per-call SET search_path.
            options=f"-c search_path={DB_SCHEMA}",
        )
    return _POOL


def _checkout():
    """Check a healthy connection out of the pool. Re-verifies with SELECT 1
    only if the connection has been idle long enough that Supabase could have
    dropped it; discards dead connections (up to a few attempts)."""
    pool = _get_pool()
    for _ in range(3):
        conn = pool.getconn()
        try:
            if time.monotonic() - _LAST_PING_TS.get(id(conn), 0.0) > _IDLE_PING_SECONDS:
                cur = conn.cursor()
                cur.execute("SELECT 1")
                cur.fetchone()
                cur.close()
                _LAST_PING_TS[id(conn)] = time.monotonic()
            return conn
        except psycopg2.Error:
            _LAST_PING_TS.pop(id(conn), None)
            pool.putconn(conn, close=True)
    raise RuntimeError("Could not obtain a healthy Postgres connection from the pool")

# Postgres syntax equivalents of the old SQLite schema: SERIAL for the
# auto-increment id columns (SQLite's AUTOINCREMENT), now() for timestamps
# (SQLite's datetime('now')). The five tables, the foreign keys, and the
# ON DELETE CASCADE rules behave identically to before.
SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS trials (
        trial_id   TEXT PRIMARY KEY,
        trial_name TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS rules (
        id        SERIAL PRIMARY KEY,
        trial_id  TEXT NOT NULL REFERENCES trials(trial_id) ON DELETE CASCADE,
        rule_id   TEXT NOT NULL,
        rule_text TEXT NOT NULL,
        category  TEXT NOT NULL,
        UNIQUE (trial_id, rule_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS assessments (
        assessment_id    TEXT PRIMARY KEY,
        trial_id         TEXT NOT NULL REFERENCES trials(trial_id),
        patient_id       TEXT NOT NULL,
        patient_record   TEXT NOT NULL,
        suggested_status TEXT NOT NULL,
        provider_used    TEXT NOT NULL,
        model_used       TEXT NOT NULL,
        created_at       TEXT NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS rule_results (
        id            SERIAL PRIMARY KEY,
        assessment_id TEXT NOT NULL REFERENCES assessments(assessment_id) ON DELETE CASCADE,
        rule_id       TEXT NOT NULL,
        rule_text     TEXT NOT NULL,
        status        TEXT NOT NULL,
        evidence      TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS decisions (
        assessment_id   TEXT PRIMARY KEY REFERENCES assessments(assessment_id) ON DELETE CASCADE,
        decision        TEXT NOT NULL,
        decision_reason TEXT,
        decided_at      TEXT NOT NULL DEFAULT now()
    )
    """,
)


def _require_database_url() -> str:
    if not DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL is not set. Point it at a Postgres database, e.g. "
            "postgresql://postgres:...@db.<project>.supabase.co:5432/postgres "
            "(see api/.env.example for the placeholder)."
        )
    return DATABASE_URL


@contextmanager
def _connect():
    conn = _checkout()
    cur = None
    try:
        cur = conn.cursor()
        yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        if cur is not None:
            cur.close()
        _get_pool().putconn(conn)


def init_db():
    with _connect() as cur:
        cur.execute(
            sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(DB_SCHEMA))
        )
        for statement in SCHEMA:
            cur.execute(statement)


def create_trial(trial_id: str, trial_name: str, rules: list[dict]):
    """Register (or re-register) a trial and its rules. Re-registering the
    same trial_id replaces its rules, so re-running the eval batch or a test
    suite doesn't error on duplicate keys. Like the old SQLite INSERT OR
    REPLACE, a re-registered trial gets a fresh created_at."""
    with _connect() as cur:
        cur.execute(
            "INSERT INTO trials (trial_id, trial_name, created_at) VALUES (%s, %s, now()) "
            "ON CONFLICT (trial_id) DO UPDATE SET "
            "trial_name = EXCLUDED.trial_name, created_at = now()",
            (trial_id, trial_name),
        )
        cur.execute("DELETE FROM rules WHERE trial_id = %s", (trial_id,))
        cur.executemany(
            "INSERT INTO rules (trial_id, rule_id, rule_text, category) VALUES (%s, %s, %s, %s)",
            [(trial_id, r["rule_id"], r["rule_text"], r["category"]) for r in rules],
        )


def get_trial(trial_id: str) -> dict | None:
    with _connect() as cur:
        cur.execute(
            "SELECT trial_id, trial_name FROM trials WHERE trial_id = %s", (trial_id,)
        )
        row = cur.fetchone()
        if row is None:
            return None
        cur.execute(
            "SELECT rule_id, rule_text, category FROM rules WHERE trial_id = %s ORDER BY id",
            (trial_id,),
        )
        rules = cur.fetchall()
        return {
            "trial_id": row["trial_id"],
            "trial_name": row["trial_name"],
            "rules": [dict(r) for r in rules],
        }


def list_trials() -> list[dict]:
    with _connect() as cur:
        cur.execute("SELECT trial_id, trial_name FROM trials ORDER BY created_at")
        rows = cur.fetchall()
        result = []
        for row in rows:
            cur.execute(
                "SELECT rule_id, rule_text, category FROM rules WHERE trial_id = %s ORDER BY id",
                (row["trial_id"],),
            )
            rules = cur.fetchall()
            result.append(
                {
                    "trial_id": row["trial_id"],
                    "trial_name": row["trial_name"],
                    "rules": [dict(r) for r in rules],
                }
            )
        return result


def count_assessments_for_trial(trial_id: str) -> int:
    """How many assessments currently reference this trial -- the number a
    delete would orphan. The audit trail is the whole point of this
    project, so a trial that has historical assessments against it can
    never be deleted silently."""
    with _connect() as cur:
        cur.execute("SELECT COUNT(*) FROM assessments WHERE trial_id = %s", (trial_id,))
        return cur.fetchone()[0]


def delete_trial(trial_id: str) -> bool:
    """Delete a trial and its rules ONLY if no assessment references it.
    Returns False (and deletes nothing) when assessments exist -- the caller
    turns that into a 409, so deleting a trial can never silently orphan or
    destroy historical assessment evidence. When it does delete, the rules
    rows go via the schema's ON DELETE CASCADE."""
    with _connect() as cur:
        cur.execute("SELECT COUNT(*) FROM assessments WHERE trial_id = %s", (trial_id,))
        referencing = cur.fetchone()[0]
        if referencing > 0:
            return False
        cur.execute("DELETE FROM trials WHERE trial_id = %s", (trial_id,))
        return cur.rowcount > 0


def delete_assessment(assessment_id: str) -> bool:
    """Permanently remove an assessment. rule_results and the decision row
    are removed by the schema's ON DELETE CASCADE (see SCHEMA: both tables
    declare it on assessment_id) -- one transaction, nothing orphaned.
    Returns False if no such assessment exists (caller returns a 404)."""
    with _connect() as cur:
        cur.execute("DELETE FROM assessments WHERE assessment_id = %s", (assessment_id,))
        return cur.rowcount > 0


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
    with _connect() as cur:
        cur.execute(
            "INSERT INTO assessments "
            "(assessment_id, trial_id, patient_id, patient_record, suggested_status, provider_used, model_used) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
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
        cur.executemany(
            "INSERT INTO rule_results (assessment_id, rule_id, rule_text, status, evidence) "
            "VALUES (%s, %s, %s, %s, %s)",
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
    with _connect() as cur:
        cur.execute(
            "SELECT assessment_id, trial_id, patient_id, suggested_status, provider_used, model_used "
            "FROM assessments WHERE assessment_id = %s",
            (assessment_id,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        cur.execute(
            "SELECT rule_id, rule_text, status, evidence FROM rule_results "
            "WHERE assessment_id = %s ORDER BY id",
            (assessment_id,),
        )
        rule_results = cur.fetchall()
        cur.execute(
            "SELECT decision, decision_reason FROM decisions WHERE assessment_id = %s",
            (assessment_id,),
        )
        decision = cur.fetchone()
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


def list_assessments() -> list[dict]:
    """Lightweight summary of every assessment, newest first, for the
    History view. Deliberately NO rule_results -- the full nested detail
    stays on get_assessment()/GET /assessments/{id}. Left join keeps
    undecided assessments in the list with decision/decision_reason None."""
    with _connect() as cur:
        cur.execute(
            "SELECT a.assessment_id, a.trial_id, a.patient_id, "
            "a.suggested_status, a.created_at, "
            "d.decision, d.decision_reason "
            "FROM assessments a "
            "LEFT JOIN decisions d ON d.assessment_id = a.assessment_id "
            "ORDER BY a.created_at DESC, a.assessment_id DESC"
        )
        rows = cur.fetchall()
        return [dict(r) for r in rows]


def set_decision(assessment_id: str, decision: str, reason: str | None) -> bool:
    """Record the coordinator's decision. Returns False (and records
    nothing) if the assessment doesn't exist -- the caller turns that into
    a 404, so an unknown id can never silently invent a decision row."""
    with _connect() as cur:
        cur.execute("SELECT 1 FROM assessments WHERE assessment_id = %s", (assessment_id,))
        exists = cur.fetchone()
        if exists is None:
            return False
        cur.execute(
            "INSERT INTO decisions (assessment_id, decision, decision_reason) VALUES (%s, %s, %s) "
            "ON CONFLICT(assessment_id) DO UPDATE SET "
            "decision = excluded.decision, decision_reason = excluded.decision_reason",
            (assessment_id, decision, reason),
        )
        return True
