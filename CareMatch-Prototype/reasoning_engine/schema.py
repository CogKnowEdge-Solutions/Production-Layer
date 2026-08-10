"""
The exact output contract we locked in during Phase 0 planning.

Key decisions enforced here, in code, not just in a doc:
- suggested_status (never "overall_status" -- this is a recommendation, not a decision)
- NO confidence field, anywhere, on purpose
- requires_coordinator_approval is always True -- Literal[True] makes it
  impossible to construct an object where this is False, even by accident
- every rule result carries its own rule_id, tied back to the protocol section
"""

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator

RuleStatus = Literal["matches", "does_not_match", "unclear"]
SuggestedStatus = Literal["likely_eligible", "likely_excluded", "needs_more_info"]

RULE_ID_PATTERN = re.compile(r"^(INC|EXC)-\d{2,}$")


class RuleResult(BaseModel):
    rule_id: str
    rule_text: str
    status: RuleStatus
    evidence: str = Field(
        ...,
        description=(
            "A direct quote from the patient record, or the literal string "
            "'no relevant information found' if nothing relevant exists."
        ),
    )

    @field_validator("rule_id")
    @classmethod
    def rule_id_must_match_format(cls, v: str) -> str:
        if not RULE_ID_PATTERN.match(v):
            raise ValueError(
                f"rule_id '{v}' does not match required format INC-## or EXC-## "
                "(Phase 0 decision #6)"
            )
        return v


class AssessmentResult(BaseModel):
    patient_id: str
    trial_id: str
    suggested_status: SuggestedStatus
    requires_coordinator_approval: Literal[True] = True
    rule_results: list[RuleResult]
