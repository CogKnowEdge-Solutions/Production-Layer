"""Protocol parser: converts human-readable trial rulebooks into structured
rule objects the rules engine can evaluate.

The parser is deliberately conservative: lines it cannot confidently classify
are still emitted as rules (type 'description') so no eligibility criterion is
silently dropped, but they are marked as needing clinical review.

Structured rule input is also supported directly - when a protocol document is
already a machine-readable list of rule objects it is passed through after
validation.
"""

from __future__ import annotations

import re
from typing import Any

from app.services.rules_engine import validate_rule

_BULLET_RE = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s*(.*)$")
_AGE_RE = re.compile(r"(?:at\s+least|minimum|≥|>=\s*)\s*(\d+)\s*(?:years|yrs)", re.I)
_AGE_MAX_RE = re.compile(
    r"(?:at\s+most|maximum|under\s+the\s+age\s+of|≤)\s*(\d+)\s*(?:years|yrs)", re.I
)

_LAB_OPERATORS = {
    ">=": re.compile(r"(?:≥|>=|at least)\s*(\d+(?:\.\d+)?)"),
    "<=": re.compile(r"(?:≤|<=|at most)\s*(\d+(?:\.\d+)?)"),
    ">": re.compile(r"(?:>|greater than)\s*(\d+(?:\.\d+)?)"),
    "<": re.compile(r"(?:<|less than)\s*(\d+(?:\.\d+)?)"),
}


_KNOWN_MEDICATIONS = [
    "warfarin",
    "metformin",
    "insulin",
    "clopidogrel",
    "aspirin",
    "apixaban",
    "rivaroxaban",
    "heparin",
    "phenytoin",
    "methotrexate",
    "amiodarone",
]
_KNOWN_CONDITIONS = [
    "diabetes",
    "hypertension",
    "cancer",
    "heart failure",
    "chronic kidney disease",
    "copd",
    "asthma",
    "epilepsy",
    "hiv",
    "hepatitis",
    "stroke",
]


def _extract_quoted(line: str) -> list[str]:
    return re.findall(r"\"([^\"]+)\"|'([^']+)'", line)


def _classify(line: str, category: str, rule_id: str) -> dict:
    lowered = line.lower()
    criteria: dict[str, Any] = {}

    min_age = _AGE_RE.search(line)
    max_age = _AGE_MAX_RE.search(line)
    if min_age or max_age:
        criteria["min_age"] = int(min_age.group(1)) if min_age else None
        criteria["max_age"] = int(max_age.group(1)) if max_age else None
        return {
            "rule_id": rule_id,
            "description": line.strip(),
            "type": "age_range",
            "category": category,
            "criteria": criteria,
        }

    if any(k in lowered for k in ("taking", "medication", "prescribed", "drug", "receiving")):
        names = [n for pair in _extract_quoted(line) for n in pair if n]
        if not names:
            names = [med for med in _KNOWN_MEDICATIONS if med in lowered]
        if names:
            criteria["names"] = names
            return {
                "rule_id": rule_id,
                "description": line.strip(),
                "type": "medication",
                "category": category,
                "criteria": criteria,
            }

    if any(k in lowered for k in ("diagnos", "history of", "icd-10", "icd10", "has ")):
        names = [n for pair in _extract_quoted(line) for n in pair if n]
        if not names:
            names = [cond for cond in _KNOWN_CONDITIONS if cond in lowered]
        if names:
            criteria["names"] = names
            return {
                "rule_id": rule_id,
                "description": line.strip(),
                "type": "diagnosis",
                "category": category,
                "criteria": criteria,
            }

    lab_kw = any(
        k in lowered
        for k in (
            "hemoglobin",
            "hba1c",
            "glucose",
            "creatinine",
            "platelet",
            "lab value",
            "level",
            "mg/dl",
            "mmol/l",
        )
    )
    if lab_kw:
        for operator, pattern in _LAB_OPERATORS.items():
            match = pattern.search(line)
            if match:
                criteria["operator"] = operator
                criteria["value"] = float(match.group(1))
                criteria["name"] = line.split(operator)[0].strip() if operator in line else lowered
                return {
                    "rule_id": rule_id,
                    "description": line.strip(),
                    "type": "lab_value",
                    "category": category,
                    "criteria": criteria,
                }

    if "caregiver" in lowered or "proxy" in lowered or "legal guardian" in lowered:
        criteria["must_have"] = True
        return {
            "rule_id": rule_id,
            "description": line.strip(),
            "type": "caregiver",
            "category": category,
            "criteria": criteria,
        }

    return {
        "rule_id": rule_id,
        "description": line.strip(),
        "type": "description",
        "category": category,
        "criteria": {},
    }


def parse_protocol_document(text: str, prefix: str = "R") -> tuple[list[dict], list[str]]:
    """Parse human-readable protocol text into rule objects.

    Returns (rules, warnings). Lines that could not be classified confidently
    are kept as 'description' rules and flagged in warnings for clinical review.
    """
    rules: list[dict] = []
    warnings: list[str] = []
    category = "inclusion"
    counter = 0

    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue
        if re.search(r"\binclusion\b", stripped, re.I) and not re.search(
            r"\bexclusion\b", stripped, re.I
        ):
            category = "inclusion"
            continue
        if re.search(r"\bexclusion\b", stripped, re.I):
            category = "exclusion"
            continue
        match = _BULLET_RE.match(raw_line)
        if not match:
            continue
        line = match.group(1).strip()
        if not line:
            continue
        counter += 1
        rule = _classify(line, category, f"{prefix}-{counter:03d}")
        problems = validate_rule(rule)
        if problems:
            warnings.append(f"Rule {rule['rule_id']}: {'; '.join(problems)}")
        if rule["type"] == "description":
            warnings.append(
                f"Rule {rule['rule_id']} could not be auto-classified; "
                f"please review clinically: {line}"
            )
        rules.append(rule)

    return rules, warnings


def parse_structured_rules(raw: list[dict], prefix: str = "R") -> tuple[list[dict], list[str]]:
    """Pass through pre-structured rule objects after validation."""
    warnings: list[str] = []
    rules: list[dict] = []
    for index, item in enumerate(raw, start=1):
        if not isinstance(item, dict):
            warnings.append(f"Rule {index}: not an object; skipped")
            continue
        rule = dict(item)
        rule.setdefault("rule_id", f"{prefix}-{index:03d}")
        rule.setdefault("category", "inclusion")
        problems = validate_rule(rule)
        if problems:
            warnings.append(f"Rule {rule.get('rule_id')}: {'; '.join(problems)}")
        if rule.get("type") == "description":
            warnings.append(
                f"Rule {rule.get('rule_id')} is marked for clinical review (type 'description')"
            )
        rules.append(rule)
    return rules, warnings
