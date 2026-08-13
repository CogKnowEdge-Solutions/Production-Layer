"""
Input and output guardrails around the AI pipeline.

Two kinds, on purpose:

INPUT guardrails (checked before anything is sent to the AI): length,
PII-pattern scanning, and injection-pattern scanning. They run at the
very start of assess_patient() -- NOT in the API layer -- so every entry
point (the HTTP API AND run_real_assessment.py directly) is protected.
The whole point of an input guardrail is stopping cost and PII exposure
BEFORE they happen, not cleaning up after.

Be honest about what these are (same honesty style as the prompt-injection
defense note in llm_client.py):
- PII scanning here is PATTERN-BASED MITIGATION, not comprehensive PII
  detection. Regexes reliably catch a small set of fixed formats: SSN-format
  numbers, email addresses, and phone numbers. They CANNOT catch names,
  addresses, medical identifiers, or anything free-form -- real detection of
  those needs NER/NLP, which is out of scope and would be dishonest to claim.
  Think of this as a cheap first line of defense, not a guarantee.
- Injection scanning is the same kind of honest mitigation: a focused list of
  suspicious instructional phrases. No regex list can be a complete defense
  against prompt injection. What this does is catch obvious attempts and fail
  loudly instead of silently handing untrusted text to the model. The list
  lives in ONE place (INJECTION_PATTERNS) so it's easy to extend.

OUTPUT guardrail (checked after the AI answers): verify that the evidence
the model quotes actually appears in the patient record. Models hallucinate
quotes; a quoted-but-fabricated "evidence" string is worse than honest
uncertainty, so a non-verifiable quote is overridden to status "unclear"
with a message saying exactly why. Honest limit: this checks SUBSTRING
presence after light normalization (lowercase + collapsed whitespace), not
semantic correctness. An accurate-but-paraphrased quote that isn't a
substring gets overridden to "unclear" -- which is the safe direction
(uncertainty, never a made-up claim).

Every input check raises GuardrailViolation carrying WHICH check failed and
a SAFE message that never echoes the matched content -- the error response
itself must never leak the sensitive text that triggered it.
"""

import re
from typing import Callable, Optional

# ---------------------------------------------------------------------------
# Length limit
# ---------------------------------------------------------------------------

# 10,000 characters is generous for a real clinical note: a typical
# outpatient note is roughly 1-4 KB and even a long discharge summary rarely
# exceeds ~10 KB. It gives legitimate records plenty of room while (a)
# stopping a runaway paste / absurd payload, and (b) bounding worst-case
# cost -- the patient record is sent to the model once per rule, so an
# unbounded record means unbounded spend that multiplies with the rule count.
MAX_PATIENT_RECORD_CHARS = 10_000

# ---------------------------------------------------------------------------
# The one exception type
# ---------------------------------------------------------------------------


class GuardrailViolation(Exception):
    """Raised by any input guardrail. `check` identifies which guardrail
    fired (one of CHECK_LENGTH / CHECK_PII / CHECK_INJECTION); `message` is
    always safe to show a caller -- it never contains the matched value."""

    def __init__(self, check: str, message: str) -> None:
        self.check = check
        self.message = message
        super().__init__(message)


CHECK_LENGTH = "length"
CHECK_PII = "pii"
CHECK_INJECTION = "injection"

# ---------------------------------------------------------------------------
# PII patterns
# ---------------------------------------------------------------------------

# Only reliably-regex-detectable formats go here. NOT names, NOT addresses,
# NOT medical identifiers -- see the module docstring. Each entry pairs the
# human-readable pattern type (used in the safe error message) with its regex.
_SSN_PATTERN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_PHONE_PATTERN = re.compile(r"\b(\+?1[\s.-]?)?(\(?\d{3}\)?[\s.-]?)\d{3}[\s.-]?\d{4}\b")

_PII_CHECKS = [
    ("SSN", _SSN_PATTERN),
    ("email address", _EMAIL_PATTERN),
    ("phone number", _PHONE_PATTERN),
]

# ---------------------------------------------------------------------------
# Injection patterns
# ---------------------------------------------------------------------------

# Case-insensitive instructional phrases that commonly show up in prompt
# injection attempts. Deliberately small and focused; extend this list in
# ONE place when new patterns appear. Heuristic mitigation, honestly -- see
# the module docstring.
#
# False-positive review (real clinical documentation, probed with tests in
# test_guardrails.py -- do not let this drift back):
#   - "system\s*:" is narrowed on purpose. Bare "system:" appears constantly
#     in genuine notes ("Review of systems: Cardiovascular system: regular
#     rate and rhythm"). It now only fires when an actual instruction-like
#     phrase follows the colon, which is what real injections ("System:
#     ignore all previous instructions") do. Deliberate tradeoff: an
#     injection that says "system:" followed by an UNUSUAL instruction we
#     haven't listed would evade this one pattern (the other patterns below
#     may still catch it) -- we accept that in exchange for never rejecting
#     a real patient note for using the word "system".
#   - "from now on" was REMOVED entirely. It is ordinary English in
#     treatment plans ("From now on, the patient should take medication
#     twice daily"), and as a STANDALONE marker its catch value is
#     near-zero -- actual injections still carry an imperative ("ignore
#     previous instructions", "override instructions"), which the other
#     patterns catch. Keeping it would reject legitimate clinical language
#     for no real gain.
INJECTION_PATTERNS = [
    r"ignore previous instructions",
    r"ignore all previous instructions",
    r"ignore your instructions",
    r"disregard previous instructions",
    r"forget your instructions",
    r"override instructions",
    r"you are now",
    r"system\s*:\s*(ignore|disregard|forget|override|you are now|you should)",
    r"new instructions\s*:",
]

_INJECTION_REGEXES = [re.compile(p, re.IGNORECASE) for p in INJECTION_PATTERNS]

# ---------------------------------------------------------------------------
# Input checks
# ---------------------------------------------------------------------------


def check_length(patient_record: str) -> None:
    if len(patient_record) > MAX_PATIENT_RECORD_CHARS:
        raise GuardrailViolation(
            CHECK_LENGTH,
            f"Patient record is too long (maximum {MAX_PATIENT_RECORD_CHARS} characters).",
        )


def check_pii(patient_record: str) -> None:
    for label, pattern in _PII_CHECKS:
        if pattern.search(patient_record):
            raise GuardrailViolation(
                CHECK_PII,
                f"Possible {label} detected in patient record.",
            )


def check_injection(patient_record: str) -> None:
    if any(regex.search(patient_record) for regex in _INJECTION_REGEXES):
        raise GuardrailViolation(
            CHECK_INJECTION,
            "Suspicious instructional content detected in patient record field.",
        )


def check_patient_record(patient_record: str) -> None:
    """All input guardrails, in one call. Raises GuardrailViolation on the
    first check that fires. Called at the very start of assess_patient(),
    before any LLM call, so cost is never incurred for a rejected record."""
    check_length(patient_record)
    check_pii(patient_record)
    check_injection(patient_record)


# ---------------------------------------------------------------------------
# Output check
# ---------------------------------------------------------------------------

UNVERIFIED_EVIDENCE_MESSAGE = (
    "Evidence could not be verified against the patient record -- treating as unclear."
)

# Optional hook for counting overrides (set by api/main.py so the engine
# itself never depends on Prometheus -- same optional-wiring pattern as the
# LangSmith tracing wrapper in llm_client.py). When no hook is set, the
# override still happens and is still logged; it just isn't counted.
_hallucinated_evidence_hook: Optional[Callable[[], None]] = None


def set_hallucinated_evidence_hook(hook: Optional[Callable[[], None]]) -> None:
    global _hallucinated_evidence_hook
    _hallucinated_evidence_hook = hook


def _notify_hallucination() -> None:
    if _hallucinated_evidence_hook is not None:
        _hallucinated_evidence_hook()


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def verify_evidence(
    patient_record: str, evidence: str, rule_id: str, rule_text: str
) -> tuple[str, bool]:
    """
    OUTPUT guardrail: after the AI answers a rule, verify the evidence it
    quotes actually appears in the patient record (normalized comparison:
    lowercase + collapsed whitespace; substring, not semantic). Returns
    (evidence, verified):
      - verified True  -> the evidence is accepted unchanged
      - verified False -> the evidence was replaced with
                          UNVERIFIED_EVIDENCE_MESSAGE, and the caller should
                          force status to "unclear" (the engine does).
    The caller decides whether to call: the engine skips entirely when the
    status is already "unclear" (nothing to check). rule_id/rule_text are
    only for clear logging when the override fires.
    """
    if not isinstance(evidence, str) or not isinstance(patient_record, str):
        # Nothing to check meaningfully. Report unverifiable WITHOUT counting
        # this as a hallucination -- a non-string evidence is the malformed-
        # output path, which the engine's existing fallback already handles.
        return UNVERIFIED_EVIDENCE_MESSAGE, False

    normalized_record = _normalize(patient_record)
    normalized_evidence = _normalize(evidence)

    if normalized_evidence and normalized_evidence in normalized_record:
        return evidence, True

    # Log clearly whenever this actually fires -- a silently-swallowed quote
    # would defeat the whole point. This is the one place the override's
    # visibility matters.
    print(
        f"    [guardrail] evidence for {rule_id} ('{rule_text[:60]}') could not be "
        f"verified against the patient record -- overriding to unclear"
    )
    _notify_hallucination()
    return UNVERIFIED_EVIDENCE_MESSAGE, False
