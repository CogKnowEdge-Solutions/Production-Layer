"""
The doorway (Phase 2). Wraps Phase 1's assess_patient() in an HTTP API so
any system can call it -- no direct Python import needed.

Persistence: trials, assessments, and coordinator decisions live in a
SQLite database (api/db.py), not in memory -- a hard process kill no
longer loses anything (that's proven by a real kill-and-restart test).

LLM_MODE controls cost: "real" (default) makes actual LLM calls through
Phase 1's llm_client. "fake" always returns "unclear" with zero cost and
zero network calls -- use this to test the API's plumbing (does routing,
validation, and error handling work?) without spending anything.
"""

import logging
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import Counter, Histogram
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel, field_validator

import db

# Loads api/.env if one exists. This is the reliable way to set LLM_MODE
# (and real API keys, later) -- it works the same regardless of which
# shell/terminal you're using, unlike `set` or `$env:` which differ between
# Command Prompt and PowerShell and are easy to get wrong.
load_dotenv()

# reasoning_engine/ is a sibling directory, not an installed package.
# This makes its already-tested modules importable here without
# reorganizing or duplicating any Phase 1 code.
REASONING_ENGINE_PATH = Path(__file__).resolve().parent.parent / "reasoning_engine"
sys.path.insert(0, str(REASONING_ENGINE_PATH))

from engine import assess_patient  # noqa: E402
from protocol import Protocol, Rule  # noqa: E402
from schema import AssessmentResult, RuleResult, RULE_ID_PATTERN  # noqa: E402
import llm_client  # noqa: E402

app = FastAPI(title="CareMatch API", description="Phase 2 -- the doorway into the reasoning engine")

# Auto-tracks request count, latency, and status codes for every endpoint,
# and exposes it all at /metrics for Prometheus to scrape. This is Phase 4,
# built directly into the REAL api this time -- not a separate toy service
# on a conflicting port, which is literally what caused a real bug earlier
# in this project (the standalone observability container silently
# shadowing this API on port 8000).
Instrumentator().instrument(app).expose(app)

# CareMatch-specific metrics -- what actually matters for THIS system,
# beyond generic HTTP traffic: what did the AI conclude, how long did
# reasoning take, how often do coordinators override it.
assessments_total = Counter(
    "assessments_total",
    "Total eligibility assessments created, by suggested status",
    ["suggested_status"],
)
reasoning_duration_seconds = Histogram(
    "reasoning_duration_seconds",
    "Time taken for assess_patient() to complete one full assessment",
)
coordinator_decisions_total = Counter(
    "coordinator_decisions_total",
    "Coordinator decisions recorded, by decision type",
    ["decision"],
)
trials_registered_total = Counter(
    "trials_registered_total",
    "Total trials registered via POST /trials",
)

# Without this, the browser blocks every request the dashboard makes to
# this API by default (CORS) -- it's not optional for a browser-based
# frontend, even in local dev. Listing common local dev ports explicitly
# rather than using "*", since that's clearer about what's actually
# expected to talk to this API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Human-readable request logging (senior-review step C). One structured line
# per request, separate from the Instrumentator() Prometheus metrics above --
# this is for a coordinator/support person to trace "request abc123 failed"
# through the logs, not for dashboards. Bound directly to stdout (via its own
# StreamHandler) so the lines appear no matter how uvicorn configures logging.
_logger = logging.getLogger("carematch.api")
if not _logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(message)s"))
    _logger.addHandler(_handler)
_logger.setLevel(logging.INFO)
_logger.propagate = False


@app.middleware("http")
async def request_logging(request: Request, call_next):
    request_id = str(uuid.uuid4())
    start = time.monotonic()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        response.headers["X-Request-ID"] = request_id
    except Exception:
        # Re-raise so FastAPI's normal error handling still produces the
        # 500; the request_id is still logged here for traceability.
        raise
    finally:
        duration_ms = (time.monotonic() - start) * 1000
        client_ip = request.client.host if request.client else "unknown"
        _logger.info(
            f"method={request.method} path={request.url.path} "
            f"status={status} duration_ms={duration_ms:.1f} "
            f"client_ip={client_ip} request_id={request_id}"
        )
    return response


# In-memory stores are GONE. Everything lives in SQLite via api/db.py --
# one file, WAL mode, survives a hard kill of the process. Schema is
# created idempotently at startup (or first import, for tests).
db.init_db()


class RuleIn(BaseModel):
    rule_id: str
    rule_text: str
    category: Literal["inclusion", "exclusion"]

    @field_validator("rule_id")
    @classmethod
    def rule_id_must_match_format(cls, v: str) -> str:
        # Validated here too (not just on the internal Rule/RuleResult
        # models) so FastAPI's own request parsing catches a bad rule_id
        # and returns a clean 422 immediately -- instead of the error
        # surfacing later as an unhandled 500 when the internal Rule
        # object gets constructed inside the handler.
        if not RULE_ID_PATTERN.match(v):
            raise ValueError(
                f"rule_id '{v}' does not match required format INC-## or EXC-## "
                "(Phase 0 decision #6)"
            )
        return v


class TrialRegisterRequest(BaseModel):
    trial_id: str
    trial_name: str
    rules: list[RuleIn]


class AssessRequest(BaseModel):
    trial_id: str
    patient_id: str
    patient_record: str


class AssessmentRecord(BaseModel):
    """
    Wraps Phase 1's AssessmentResult with tracking info the API layer
    needs (an id to reference it by, and the coordinator's eventual
    decision) -- without touching Phase 1's already-tested schema at all.
    Phase 0's rule still holds: requires_coordinator_approval is always
    True on the inner `assessment`, and `decision` starts as None every
    single time. There is no code path that skips this.

    provider_used / model_used: harness traceability. If reasoning
    quality is ever questioned later, we need to know exactly which
    model produced a given assessment -- not just "the AI said so."
    """
    assessment_id: str
    assessment: AssessmentResult
    # str | None on purpose, NOT a 3-value Literal: decisions are stored as
    # plain TEXT in SQLite, and rows written before the 3-option redesign
    # still contain the legacy values "approved"/"overridden". Those must
    # load and display without crashing (senior-review requirement), so the
    # response side tolerates any string; the REQUEST side below stays a
    # strict Literal so new writes can only be the 3 current values.
    decision: str | None = None
    decision_reason: str | None = None
    provider_used: str
    model_used: str


class DecisionRequest(BaseModel):
    # Strict on purpose: coordinators can only write these 3 values. Old
    # "approved"/"overridden" data stays readable (see AssessmentRecord
    # above) but is never written again.
    decision: Literal["accepted", "denied", "needs_more_review"]
    reason: str | None = None


def _fake_llm(rule_text: str, patient_record: str, category: str) -> dict:
    """
    Zero-cost stand-in for LLM_MODE=fake. Always returns "unclear" -- this
    only proves the request reached the engine and came back in the right
    shape. It does NOT test reasoning quality (that's what Phase 1's
    run_real_assessment.py is for).
    """
    return {"status": "unclear", "evidence": "FAKE MODE -- no real LLM call was made"}


def _protocol_from_row(row: dict) -> Protocol:
    return Protocol(
        trial_id=row["trial_id"],
        trial_name=row["trial_name"],
        rules=[Rule(**r) for r in row["rules"]],
    )


def _record_from_row(row: dict) -> "AssessmentRecord":
    assessment = AssessmentResult(
        patient_id=row["patient_id"],
        trial_id=row["trial_id"],
        suggested_status=row["suggested_status"],
        rule_results=[RuleResult(**r) for r in row["rule_results"]],
    )
    return AssessmentRecord(
        assessment_id=row["assessment_id"],
        assessment=assessment,
        decision=row["decision"],
        decision_reason=row["decision_reason"],
        provider_used=row["provider_used"],
        model_used=row["model_used"],
    )


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/trials", response_model=list[Protocol])
def list_trials():
    return [_protocol_from_row(row) for row in db.list_trials()]


@app.post("/trials", response_model=Protocol, status_code=201)
def register_trial(body: TrialRegisterRequest):
    protocol = Protocol(
        trial_id=body.trial_id,
        trial_name=body.trial_name,
        rules=[Rule(**r.model_dump()) for r in body.rules],
    )
    db.create_trial(
        protocol.trial_id,
        protocol.trial_name,
        [r.model_dump() for r in protocol.rules],
    )
    trials_registered_total.inc()
    return protocol


@app.get("/trials/{trial_id}", response_model=Protocol)
def get_trial(trial_id: str):
    row = db.get_trial(trial_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"No trial registered with id '{trial_id}'")
    return _protocol_from_row(row)


@app.post("/assess", response_model=AssessmentRecord, status_code=201)
def assess(body: AssessRequest):
    trial_row = db.get_trial(body.trial_id)
    if trial_row is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No trial registered with id '{body.trial_id}'. "
                "Register it first via POST /trials."
            ),
        )
    protocol = _protocol_from_row(trial_row)

    llm_mode = os.environ.get("LLM_MODE", "real").lower()
    call_llm = _fake_llm if llm_mode == "fake" else llm_client.call_real_llm

    start = time.monotonic()
    try:
        result = assess_patient(
            patient_id=body.patient_id,
            patient_record=body.patient_record,
            protocol=protocol,
            call_llm=call_llm,
        )
    except llm_client.LLMError as exc:
        raise HTTPException(status_code=502, detail=f"LLM error: {exc}") from exc
    finally:
        # Recorded even on failure -- a slow failing call is itself
        # something worth seeing on a dashboard, not just successes.
        reasoning_duration_seconds.observe(time.monotonic() - start)

    assessments_total.labels(suggested_status=result.suggested_status).inc()

    # Traceability: record exactly which provider/model actually produced
    # this assessment, resolved the same way llm_client itself resolves it,
    # so this is never guessed or out of sync with what really ran.
    if llm_mode == "fake":
        provider_used, model_used = "fake", "fake-mode-no-llm-call"
    else:
        provider_used = os.environ.get("LLM_PROVIDER", "openrouter").lower()
        if provider_used == "anthropic":
            model_used = os.environ.get("ANTHROPIC_MODEL", llm_client.DEFAULT_ANTHROPIC_MODEL)
        else:
            model_used = os.environ.get("OPENROUTER_MODEL", llm_client.DEFAULT_OPENROUTER_MODEL)

    record = AssessmentRecord(
        assessment_id=str(uuid.uuid4()),
        assessment=result,
        provider_used=provider_used,
        model_used=model_used,
    )
    db.save_assessment(
        assessment_id=record.assessment_id,
        trial_id=result.trial_id,
        patient_id=result.patient_id,
        patient_record=body.patient_record,
        suggested_status=result.suggested_status,
        provider_used=provider_used,
        model_used=model_used,
        rule_results=[rr.model_dump() for rr in result.rule_results],
    )
    return record


@app.get("/assessments/{assessment_id}", response_model=AssessmentRecord)
def get_assessment(assessment_id: str):
    row = db.get_assessment(assessment_id)
    if row is None:
        raise HTTPException(
            status_code=404, detail=f"No assessment found with id '{assessment_id}'"
        )
    return _record_from_row(row)


@app.post("/assessments/{assessment_id}/decision", response_model=AssessmentRecord)
def record_decision(assessment_id: str, body: DecisionRequest):
    """
    The coordinator's decision. Every assessment requires one -- this is
    where that happens. Overriding without a reason is allowed by the
    schema, but the dashboard (Phase 3) should make the reason field feel
    expected, not optional, since an unexplained override defeats the
    whole point of the evidence trail.
    """
    if not db.set_decision(assessment_id, body.decision, body.reason):
        raise HTTPException(
            status_code=404, detail=f"No assessment found with id '{assessment_id}'"
        )
    coordinator_decisions_total.labels(decision=body.decision).inc()
    return _record_from_row(db.get_assessment(assessment_id))