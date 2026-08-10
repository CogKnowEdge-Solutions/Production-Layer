"""
The core reasoning engine.

assess_patient() is the one function this whole phase exists to prove works.
It takes a patient record + a protocol, walks the rules one at a time
(calling the LLM for each), and aggregates into our locked Phase 0 schema.

Aggregation logic (category-aware -- see protocol.py for why this changed
after real-model testing revealed negated exclusion rules confuse the model):
  - ANY rule "unclear"                          -> needs_more_info
  - ANY inclusion rule "does_not_match"
    OR ANY exclusion rule "matches"              -> likely_excluded
  - otherwise                                    -> likely_eligible

Note this is always a SUGGESTION. requires_coordinator_approval is hard-coded
True in the schema itself (see schema.py) -- there is no code path that can
produce an assessment that skips human review, even for a clean pass.

The `call_llm` parameter is dependency injection: production code passes
llm_client.call_real_llm, tests pass a fake that returns canned answers.
This lets us fully test the loop and aggregation logic without needing an
API key.
"""

import time
from typing import Callable

from pydantic import ValidationError

from protocol import Protocol
from schema import AssessmentResult, RuleResult

LLMCallable = Callable[[str, str, str], dict]


def evaluate_single_rule(rule, patient_record: str, call_llm: LLMCallable) -> RuleResult:
    print(f"    Evaluating {rule.rule_id}: {rule.rule_text[:60]}...", end=" ", flush=True)
    start = time.monotonic()
    raw = call_llm(rule.rule_text, patient_record, rule.category)
    elapsed = time.monotonic() - start

    try:
        result = RuleResult(
            rule_id=rule.rule_id,
            rule_text=rule.rule_text,
            status=raw["status"],
            evidence=raw["evidence"],
        )
        print(f"done in {elapsed:.1f}s -> {result.status}")
        return result
    except (KeyError, ValidationError, TypeError) as exc:
        # Harness safety net: the model returned something that doesn't fit
        # our schema -- a missing field, an invalid status value, wrong
        # type, whatever. One malformed rule result must NEVER crash the
        # whole assessment, and must NEVER be silently guessed into a
        # possibly-wrong verdict. Fall back to the cautious "unclear" state
        # and say plainly that the AI's own output was the problem, not
        # the patient's data.
        print(f"done in {elapsed:.1f}s -> MALFORMED OUTPUT, falling back to unclear ({exc})")
        return RuleResult(
            rule_id=rule.rule_id,
            rule_text=rule.rule_text,
            status="unclear",
            evidence=(
                f"The AI's response for this rule could not be validated "
                f"(malformed output: {exc}). Raw response: {raw!r}"
            ),
        )


def aggregate_status(protocol: Protocol, rule_results: list[RuleResult]) -> str:
    results_by_id = {r.rule_id: r for r in rule_results}

    if any(r.status == "unclear" for r in rule_results):
        return "needs_more_info"

    for rule in protocol.rules:
        result = results_by_id[rule.rule_id]
        if rule.category == "inclusion" and result.status == "does_not_match":
            return "likely_excluded"
        if rule.category == "exclusion" and result.status == "matches":
            return "likely_excluded"

    return "likely_eligible"


def assess_patient(
    patient_id: str,
    patient_record: str,
    protocol: Protocol,
    call_llm: LLMCallable,
) -> AssessmentResult:
    rule_results = [
        evaluate_single_rule(rule, patient_record, call_llm) for rule in protocol.rules
    ]
    suggested_status = aggregate_status(protocol, rule_results)

    return AssessmentResult(
        patient_id=patient_id,
        trial_id=protocol.trial_id,
        suggested_status=suggested_status,
        rule_results=rule_results,
    )