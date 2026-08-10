"""Eligibility orchestration: evaluates a patient against all trial rules,
aggregates per-rule results into an overall status, and persists the
assessment with full evidence chains.

Aggregation rules (from plan.md):
  - If ANY rule is UNCLEAR                       -> overall UNCLEAR (needs more information)
  - If ANY inclusion rule DOES_NOT_MATCH         -> LIKELY_INELIGIBLE
  - If ANY exclusion rule MATCHES                -> LIKELY_INELIGIBLE
  - Otherwise                                    -> LIKELY_ELIGIBLE

The AI NEVER makes the final decision: coordinators review and approve or
override the recommendation (see assessments API).
"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.db import repositories as repo
from app.db.models import Assessment, Trial
from app.middleware.metrics import ai_confidence_distribution, assessments_created_total
from app.services.audit_logger import get_audit_logger
from app.services.fhir_processor import PatientData, data_completeness
from app.services.rules_engine import (
    DOES_NOT_MATCH,
    MATCHES,
    UNCLEAR,
    evaluate_rule,
    validate_rule,
)

LIKELY_ELIGIBLE = "LIKELY_ELIGIBLE"
LIKELY_INELIGIBLE = "LIKELY_INELIGIBLE"
UNCLEAR_OVERALL = "UNCLEAR"


class EligibilityError(ValueError):
    pass


class EligibilityService:
    def __init__(self):
        self.audit = get_audit_logger()

    def _rules_from_trial(self, trial: Trial) -> list[dict]:
        rules = list(trial.rules or [])
        if trial.inclusion_rules:
            rules.extend({**r, "category": "inclusion"} for r in (trial.inclusion_rules or []))
        if trial.exclusion_rules:
            rules.extend({**r, "category": "exclusion"} for r in (trial.exclusion_rules or []))
        if not rules:
            raise EligibilityError(f"Trial {trial.trial_id} has no rules defined")
        return rules

    def evaluate(
        self,
        db: Session,
        *,
        trial: Trial,
        patient_data: PatientData,
        patient_id: uuid.UUID,
        hospital_id: str | None = None,
        coordinator_id: uuid.UUID | None = None,
        ip_address: str | None = None,
    ) -> Assessment:
        rules = self._rules_from_trial(trial)

        invalid = [r.get("rule_id") for r in rules if validate_rule(r)]
        if invalid:
            raise EligibilityError(f"Trial contains invalid rules: {invalid}")

        evaluations = [evaluate_rule(patient_data, rule) for rule in rules]

        # --- Aggregate ---
        unclear = [e for e in evaluations if e["status"] == UNCLEAR]
        inclusion_fails = [
            e for e in evaluations if e["category"] == "inclusion" and e["status"] == DOES_NOT_MATCH
        ]
        exclusion_matches = [
            e for e in evaluations if e["category"] == "exclusion" and e["status"] == MATCHES
        ]

        if unclear:
            overall = UNCLEAR_OVERALL
        elif inclusion_fails or exclusion_matches:
            overall = LIKELY_INELIGIBLE
        else:
            overall = LIKELY_ELIGIBLE

        # --- Confidence & data quality ---
        scored = [e for e in evaluations if e["status"] != UNCLEAR]
        avg_confidence = (
            round(sum(e["confidence"] for e in scored) / len(scored), 2) if scored else 0.0
        )
        completeness = data_completeness(patient_data)
        overall_confidence = round(avg_confidence * completeness, 2)

        assessments_created_total.inc()
        ai_confidence_distribution.observe(overall_confidence)

        assessment = repo.create_assessment(
            db,
            patient_id=patient_id,
            trial_id=trial.trial_id,
            hospital_id=hospital_id,
            overall_status=overall,
            ai_confidence=overall_confidence,
            data_quality_score=completeness,
            coordinator_id=coordinator_id,
            assessment_data={
                "trial_name": trial.trial_name,
                "nct_number": trial.nct_number,
                "protocol_version": trial.protocol_version,
                "data_quality_score": completeness,
                "rule_count": len(evaluations),
            },
        )

        for evaluation in evaluations:
            repo.create_rule_evaluation(
                db,
                assessment_id=assessment.assessment_id,
                rule_id=evaluation.get("rule_id"),
                rule_description=evaluation.get("description"),
                rule_type=evaluation.get("type"),
                category=evaluation.get("category"),
                status=evaluation["status"],
                confidence=evaluation["confidence"],
                evidence=evaluation["evidence"] or None,
                missing_data=evaluation.get("missing_data"),
            )
        db.commit()
        db.refresh(assessment)

        self.audit.log(
            db,
            action="assessment_created",
            user_id=coordinator_id,
            hospital_id=hospital_id,
            resource_type="Assessment",
            resource_id=assessment.assessment_id,
            data_accessed={"trial": str(trial.trial_id), "overall_status": overall},
            ip_address=ip_address,
        )
        return assessment


_eligibility_service: EligibilityService | None = None


def get_eligibility_service() -> EligibilityService:
    global _eligibility_service
    if _eligibility_service is None:
        _eligibility_service = EligibilityService()
    return _eligibility_service
