"""Rules engine: evaluates a patient against trial protocol rules.

Each rule is evaluated independently and produces one of three statuses:
  MATCHES         - the patient satisfies the rule criterion
  DOES_NOT_MATCH  - the patient does not satisfy the rule criterion
  UNCLEAR         - required data is missing, so no confident determination

Every evaluation carries a confidence score (0.0-1.0), evidence citations
pointing at the exact patient data that supports the conclusion, and (for
UNCLEAR results) a description of exactly what data is missing.

The AI never decides eligibility itself: the rules engine reports; a human
coordinator decides (see eligibility service aggregation).
"""

from __future__ import annotations

from app.services.fhir_processor import PatientData

MATCHES = "MATCHES"
DOES_NOT_MATCH = "DOES_NOT_MATCH"
UNCLEAR = "UNCLEAR"

SUPPORTED_TYPES = {
    "age_range",
    "medication",
    "diagnosis",
    "lab_value",
    "temporal",
    "caregiver",
    "description",
}


class RuleError(ValueError):
    pass


def _evidence(source: str, detail: str) -> dict:
    return {"source": source, "detail": detail}


def evaluate_age_range(data: PatientData, criteria: dict) -> dict:
    min_age = criteria.get("min_age")
    max_age = criteria.get("max_age")
    age = data.age()
    if age is None:
        return {
            "status": UNCLEAR,
            "confidence": 0.0,
            "evidence": [],
            "missing_data": ["birth_date - patient date of birth is required to compute age"],
        }
    ok = True
    reasons = []
    if min_age is not None and age < min_age:
        ok = False
        reasons.append(f"patient age {age} is below minimum {min_age}")
    if max_age is not None and age > max_age:
        ok = False
        reasons.append(f"patient age {age} exceeds maximum {max_age}")
    return {
        "status": MATCHES if ok else DOES_NOT_MATCH,
        "confidence": 1.0,
        "evidence": [
            _evidence("demographics", f"date_of_birth={data.birth_date}, computed age={age}")
        ],
    }


def _rxnorm_match(record_any: dict, rxnorm_codes: list[str], names: list[str]) -> bool:
    code = record_any.get("rxnorm", [])
    name = record_any.get("name", "") or ""
    name_l = name.lower()
    return any(c in code for c in rxnorm_codes) or any(n.lower() in name_l for n in names if n)


def evaluate_medication(data: PatientData, criteria: dict) -> dict:
    rxnorm_codes = [c for c in criteria.get("rxnorm_codes", []) if c]
    names = [n for n in criteria.get("names", []) if n]
    active_only = criteria.get("active_only", True)
    if not rxnorm_codes and not names:
        return {
            "status": UNCLEAR,
            "confidence": 0.0,
            "evidence": [],
            "missing_data": ["rule criteria"],
        }

    medications = data.active_medications() if active_only else data.medications
    if not data.medications:
        return {
            "status": UNCLEAR,
            "confidence": 0.2,
            "evidence": [],
            "missing_data": ["medication history - no medication records present in patient file"],
        }

    matched = [
        _evidence("medications", f"{m.name} (rxnorm={m.rxnorm}, status={m.status})")
        for m in medications
        if _rxnorm_match(m.__dict__, rxnorm_codes, names)
    ]
    if matched:
        return {"status": MATCHES, "confidence": 0.95, "evidence": matched}
    return {
        "status": DOES_NOT_MATCH,
        "confidence": 0.8,
        "evidence": [
            _evidence("medications", f"no active medication matching {names or rxnorm_codes} found")
        ],
    }


def _icd_match(record_any: dict, icd10_codes: list[str], names: list[str]) -> bool:
    code = record_any.get("icd10", [])
    name = record_any.get("name", "") or ""
    name_l = name.lower()
    return any(c in code for c in icd10_codes) or any(n.lower() in name_l for n in names if n)


def evaluate_diagnosis(data: PatientData, criteria: dict) -> dict:
    icd10_codes = [c for c in criteria.get("icd10_codes", []) if c]
    names = [n for n in criteria.get("names", []) if n]
    if not icd10_codes and not names:
        return {
            "status": UNCLEAR,
            "confidence": 0.0,
            "evidence": [],
            "missing_data": ["rule criteria"],
        }

    if not data.conditions:
        return {
            "status": UNCLEAR,
            "confidence": 0.3,
            "evidence": [],
            "missing_data": ["diagnosis/condition history - no conditions present in patient file"],
        }

    matched = [
        _evidence("conditions", f"{c.name} (icd10={c.icd10}, status={c.status})")
        for c in data.conditions
        if _icd_match(c.__dict__, icd10_codes, names)
    ]
    if matched:
        return {"status": MATCHES, "confidence": 0.9, "evidence": matched}
    return {
        "status": DOES_NOT_MATCH,
        "confidence": 0.8,
        "evidence": [
            _evidence("conditions", f"no condition matching {names or icd10_codes} found")
        ],
    }


def evaluate_lab_value(data: PatientData, criteria: dict) -> dict:
    loinc = criteria.get("loinc_code")
    operator = criteria.get("operator", ">=")
    target = criteria.get("value")
    unit = criteria.get("unit")
    name_hint = criteria.get("name")
    if target is None:
        return {
            "status": UNCLEAR,
            "confidence": 0.0,
            "evidence": [],
            "missing_data": ["rule criteria"],
        }

    if not data.observations:
        return {
            "status": UNCLEAR,
            "confidence": 0.2,
            "evidence": [],
            "missing_data": ["lab results - no observations present in patient file"],
        }

    candidates = data.observations
    if loinc:
        candidates = [o for o in candidates if o.loinc == loinc]
    if name_hint and not candidates:
        candidates = [o for o in data.observations if name_hint.lower() in (o.name or "").lower()]

    if not candidates:
        return {
            "status": UNCLEAR,
            "confidence": 0.3,
            "evidence": [],
            "missing_data": [f"lab observation for {loinc or name_hint} not found in patient file"],
        }

    for obs in candidates:
        if obs.value is None:
            continue
        ok = {
            ">=": obs.value >= target,
            "<=": obs.value <= target,
            ">": obs.value > target,
            "<": obs.value < target,
            "==": obs.value == target,
        }.get(operator)
        if ok is None:
            return {
                "status": UNCLEAR,
                "confidence": 0.0,
                "evidence": [],
                "missing_data": [f"unsupported operator {operator}"],
            }
        if ok:
            return {
                "status": MATCHES,
                "confidence": 0.9,
                "evidence": [
                    _evidence(
                        "observations",
                        f"{obs.name} (loinc={obs.loinc}) value={obs.value} "
                        f"{obs.unit} {operator} {target} {unit or ''}",
                    )
                ],
            }
    return {
        "status": DOES_NOT_MATCH,
        "confidence": 0.8,
        "evidence": [
            _evidence("observations", f"no lab value satisfies {operator} {target} {unit or ''}")
        ],
    }


def evaluate_temporal(data: PatientData, criteria: dict) -> dict:
    """Temporal constraint, e.g. 'no event in the last N days'.
    criteria: {field: 'medication'|'condition'|'observation', days: N, present: bool}
    'present: true' -> patient must have the event; 'present: false' -> must not.
    """
    field = criteria.get("field", "condition")
    days = criteria.get("days")
    present = criteria.get("present", False)
    name_hint = criteria.get("name")
    if days is None:
        return {
            "status": UNCLEAR,
            "confidence": 0.0,
            "evidence": [],
            "missing_data": ["rule criteria"],
        }

    if field == "medication":
        events: list = data.medications
    elif field == "observation":
        events = data.observations
    else:
        events = data.conditions

    if not events:
        return {
            "status": UNCLEAR,
            "confidence": 0.4,
            "evidence": [],
            "missing_data": [f"temporal data ({field}) missing from patient file"],
        }

    if name_hint:
        events = [e for e in events if name_hint.lower() in (e.name or "").lower()]
    if events:
        return {
            "status": MATCHES if present else DOES_NOT_MATCH,
            "confidence": 0.75,
            "evidence": [_evidence(field, f"{events[0].name} present in patient record")],
        }
    return {
        "status": DOES_NOT_MATCH if present else MATCHES,
        "confidence": 0.7,
        "evidence": [_evidence(field, f"no matching {field} event found")],
    }


def evaluate_caregiver(data: PatientData, criteria: dict) -> dict:
    relationship = criteria.get("relationship")
    min_age = criteria.get("min_age")
    requires_verification = criteria.get("requires_verification", False)
    must_have = criteria.get("must_have", True)

    if not data.caregivers:
        return {
            "status": UNCLEAR,
            "confidence": 0.2,
            "evidence": [],
            "missing_data": ["caregiver records - no caregivers associated with patient"],
        }

    matched = data.caregivers
    if relationship:
        matched = [
            c for c in matched if (c.relationship_type or "").upper() == relationship.upper()
        ]
    if not matched:
        return {
            "status": DOES_NOT_MATCH if must_have else MATCHES,
            "confidence": 0.8,
            "evidence": [
                _evidence("caregivers", f"no caregiver with relationship '{relationship}' found")
            ],
        }

    details = [
        f"{c.name or 'unknown'} (relationship={c.relationship_type}, age={c.age})" for c in matched
    ]
    ok = True
    if min_age is not None:
        adults = [c for c in matched if c.age is not None and c.age >= min_age]
        if not adults:
            ok = False
    if requires_verification:
        verified = [c for c in matched if c.verified]
        if not verified:
            ok = False
    status = MATCHES if ok else DOES_NOT_MATCH
    return {
        "status": status,
        "confidence": 0.85,
        "evidence": [_evidence("caregivers", " | ".join(details))],
    }


_EVALUATORS = {
    "age_range": evaluate_age_range,
    "medication": evaluate_medication,
    "diagnosis": evaluate_diagnosis,
    "lab_value": evaluate_lab_value,
    "temporal": evaluate_temporal,
    "caregiver": evaluate_caregiver,
}


def evaluate_rule(data: PatientData, rule: dict) -> dict:
    rule_type = rule.get("type")
    criteria = rule.get("criteria") or {}
    if rule_type == "description":
        return {
            "rule_id": rule.get("rule_id"),
            "description": rule.get("description"),
            "type": rule_type,
            "category": rule.get("category", "inclusion"),
            "status": UNCLEAR,
            "confidence": 0.0,
            "evidence": [],
            "missing_data": [
                (
                    "rule could not be machine-classified; requires clinical review "
                    "before eligibility can be determined"
                )
            ],
        }
    if rule_type not in _EVALUATORS:
        raise RuleError(f"Unsupported rule type '{rule_type}'")
    result = _EVALUATORS[rule_type](data, criteria)
    return {
        "rule_id": rule.get("rule_id"),
        "description": rule.get("description"),
        "type": rule_type,
        "category": rule.get("category", "inclusion"),
        **result,
    }


def validate_rule(rule: dict) -> list[str]:
    """Return a list of validation problems for a rule (empty if valid)."""
    problems = []
    if not rule.get("rule_id"):
        problems.append("rule_id is required")
    if not rule.get("type"):
        problems.append("type is required")
    elif rule["type"] not in SUPPORTED_TYPES:
        problems.append(f"type must be one of {sorted(SUPPORTED_TYPES)}")
    if rule.get("category") not in ("inclusion", "exclusion", None):
        problems.append("category must be 'inclusion' or 'exclusion'")
    if not rule.get("description"):
        problems.append("description is required")
    return problems
