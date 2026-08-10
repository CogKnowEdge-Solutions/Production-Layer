"""
Trial protocol representation.

Phase 0 decision #6: protocols are manually converted into a clean rule
checklist by a human BEFORE the AI ever sees them (Option A). This module
is that checklist's shape -- not a PDF parser. Raw-document parsing (Option B)
was explicitly deferred to Phase 7.

RULE PHRASING CONVENTION (revised after real-model testing in Phase 1):
Write every rule_text the way it would naturally appear in an actual trial
protocol:
  - Inclusion rules: phrase as a requirement the patient must meet.
    e.g. "Patient must have a diagnosis of Type 2 Diabetes"
  - Exclusion rules: phrase as the disqualifying condition itself, stated
    plainly -- NOT as a negated requirement.
    e.g. "Patient is currently taking Warfarin"  (correct)
    NOT  "Patient must not currently be taking Warfarin"  (avoid -- see below)

Why: real testing against a live model showed that negated ("must not...")
exclusion rules caused the model to answer "does_not_match" almost every
time regardless of the actual facts -- it seems to struggle with the
double-negative of affirming an absence. Phrasing exclusion criteria as a
plain, positively-stated condition removes that ambiguity entirely: the
model just checks whether the record shows that condition or not.

Because of this, `category` is no longer just for display -- the prompt
sent to the model explains what a "match" means differently depending on
whether a rule is inclusion or exclusion, and the aggregation logic in
engine.py is category-aware accordingly.
"""

from typing import Literal

from pydantic import BaseModel, field_validator

from schema import RULE_ID_PATTERN


class Rule(BaseModel):
    rule_id: str  # e.g. "INC-01", "EXC-02"
    rule_text: str
    category: Literal["inclusion", "exclusion"]

    @field_validator("rule_id")
    @classmethod
    def rule_id_must_match_format(cls, v: str) -> str:
        if not RULE_ID_PATTERN.match(v):
            raise ValueError(
                f"rule_id '{v}' does not match required format INC-## or EXC-## "
                "(Phase 0 decision #6). This is caught here, at trial registration "
                "time, so the error is immediate and clear -- not deferred to a "
                "confusing failure later during assessment."
            )
        return v


class Protocol(BaseModel):
    trial_id: str
    trial_name: str
    rules: list[Rule]