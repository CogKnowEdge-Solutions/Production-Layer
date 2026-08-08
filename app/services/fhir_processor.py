"""FHIR R4 processing: validate incoming bundles and extract a normalized
internal patient model for the rules engine.

Only the resources required for eligibility screening are extracted:
demographics, medications, conditions/diagnoses, lab observations, allergies,
and caregiver references. Missing required fields are tracked for data-quality
scoring and "unclear" rule outcomes.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from typing import Any


class FHIRValidationError(ValueError):
    pass


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None


def _age_on(birth_date: date, reference: date | None = None) -> int:
    reference = reference or date.today()
    years = reference.year - birth_date.year
    if (reference.month, reference.day) < (birth_date.month, birth_date.day):
        years -= 1
    return years


@dataclass
class MedicationRecord:
    name: str
    rxnorm: list[str] = field(default_factory=list)
    status: str | None = None
    date: str | None = None
    active: bool = True


@dataclass
class ConditionRecord:
    name: str
    icd10: list[str] = field(default_factory=list)
    status: str | None = None
    onset_date: str | None = None
    recorded_date: str | None = None


@dataclass
class ObservationRecord:
    name: str
    loinc: str | None = None
    value: float | None = None
    unit: str | None = None
    status: str | None = None
    date: str | None = None


@dataclass
class AllergyRecord:
    name: str
    status: str | None = None
    onset_date: str | None = None


@dataclass
class ProcedureRecord:
    name: str
    code: str | None = None
    performed_date: str | None = None
    status: str | None = None


@dataclass
class CaregiverRecord:
    name: str | None = None
    relationship_type: str | None = None
    birth_date: str | None = None
    age: int | None = None
    verified: bool | None = None


@dataclass
class PatientData:
    resource_type: str = "Patient"
    patient_id: str | None = None
    mrn: str | None = None
    name: str | None = None
    birth_date: str | None = None
    gender: str | None = None
    medications: list[MedicationRecord] = field(default_factory=list)
    conditions: list[ConditionRecord] = field(default_factory=list)
    observations: list[ObservationRecord] = field(default_factory=list)
    allergies: list[AllergyRecord] = field(default_factory=list)
    procedures: list[ProcedureRecord] = field(default_factory=list)
    caregivers: list[CaregiverRecord] = field(default_factory=list)
    missing_required: list[str] = field(default_factory=list)

    def age(self) -> int | None:
        bd = _parse_date(self.birth_date)
        if not bd:
            return None
        return _age_on(bd)

    def active_medications(self) -> list[MedicationRecord]:
        return [m for m in self.medications if m.active]

    def to_dict(self) -> dict:
        return asdict(self)


def _extract_coding(coding: Any) -> tuple[str | None, str | None]:
    """Return (system, code) for the first coding entry with a known code."""
    if not isinstance(coding, dict):
        return None, None
    system = coding.get("system")
    code = coding.get("code")
    if system and code:
        return system, code
    return None, None


def _name_from_codings(codings: Any) -> str | None:
    if isinstance(codings, dict):
        return codings.get("text") or codings.get("display")
    if isinstance(codings, list):
        for coding in codings:
            text = coding.get("text") or coding.get("display")
            if text:
                return text
    return None


def _medication_from_request(resource: dict) -> MedicationRecord | None:
    status = resource.get("status")
    codeable = resource.get("medicationCodeableConcept") or {}
    rxnorm: list[str] = []
    for coding in codeable.get("coding", []) or []:
        system, code = _extract_coding(coding)
        if system and "rxnorm" in system.lower() and code:
            rxnorm.append(code)
    name = _name_from_codings(codeable.get("coding")) or codeable.get("text")
    if name is None and resource.get("medicationReference"):
        name = "medication:" + resource["medicationReference"].get("reference", "")
    active = status in ("active", None, "on-hold", "intended")
    return MedicationRecord(
        name=name or "unknown",
        rxnorm=rxnorm,
        status=status,
        date=resource.get("authoredOn") or resource.get("statusChanged"),
        active=active,
    )


def _condition_from_resource(resource: dict) -> ConditionRecord:
    code = resource.get("code") or {}
    icd10: list[str] = []
    for coding in code.get("coding", []) or []:
        system, c = _extract_coding(coding)
        if (
            system
            and ("icd10" in system.lower() or system == "http://hl7.org/fhir/sid/icd-10-cm")
            and c
        ):
            icd10.append(c)
    name = _name_from_codings(code.get("coding")) or code.get("text")
    return ConditionRecord(
        name=name or "unknown",
        icd10=icd10,
        status=resource.get("clinicalStatus", {}).get("coding", [{}])[0].get("code")
        if isinstance(resource.get("clinicalStatus"), dict)
        else resource.get("clinicalStatus"),
        onset_date=resource.get("onsetDateTime") or resource.get("onsetPeriod", {}).get("start"),
        recorded_date=resource.get("recordedDate"),
    )


def _observation_from_resource(resource: dict) -> ObservationRecord:
    code = resource.get("code") or {}
    loinc: str | None = None
    for coding in code.get("coding", []) or []:
        system, c = _extract_coding(coding)
        if system and "loinc" in system.lower() and c:
            loinc = c
    name = _name_from_codings(code.get("coding")) or code.get("text")
    value_quantity = resource.get("valueQuantity") or {}
    value = value_quantity.get("value")
    try:
        value = float(value) if value is not None else None
    except (TypeError, ValueError):
        value = None
    return ObservationRecord(
        name=name or "unknown",
        loinc=loinc,
        value=value,
        unit=value_quantity.get("unit"),
        status=resource.get("status"),
        date=resource.get("effectiveDateTime") or resource.get("effectivePeriod", {}).get("start"),
    )


def _allergy_from_resource(resource: dict) -> AllergyRecord:
    code = resource.get("code") or {}
    name = _name_from_codings(code.get("coding")) or code.get("text")
    return AllergyRecord(
        name=name or "unknown",
        status=resource.get("clinicalStatus", {}).get("coding", [{}])[0].get("code")
        if isinstance(resource.get("clinicalStatus"), dict)
        else resource.get("clinicalStatus"),
        onset_date=resource.get("onsetDateTime"),
    )


def _procedure_from_resource(resource: dict) -> ProcedureRecord:
    code = resource.get("code") or {}
    name = _name_from_codings(code.get("coding")) or code.get("text")
    icd_code = None
    for coding in code.get("coding", []) or []:
        _, c = _extract_coding(coding)
        if c:
            icd_code = c
            break
    return ProcedureRecord(
        name=name or "unknown",
        code=icd_code,
        status=resource.get("status"),
        performed_date=resource.get("performedDateTime")
        or resource.get("performedPeriod", {}).get("start"),
    )


def _caregiver_from_resource(resource: dict) -> CaregiverRecord:
    name = resource.get("name") or resource.get("text") or {}
    name_str = None
    if isinstance(name, dict):
        name_str = " ".join(filter(None, [" ".join(name.get("given", [])), name.get("family")]))
    elif isinstance(name, str):
        name_str = name
    birth_date = _parse_date(resource.get("birthDate"))
    return CaregiverRecord(
        name=name_str,
        relationship_type=resource.get("relationship", {}).get("coding", [{}])[0].get("code")
        if isinstance(resource.get("relationship"), dict)
        else resource.get("relationship"),
        birth_date=resource.get("birthDate"),
        age=_age_on(birth_date) if birth_date else None,
    )


class FHIRProcessor:
    """Validate a FHIR R4 Patient/Bundle and extract PatientData."""

    REQUIRED_FIELDS = ["name", "birth_date"]

    def process(self, payload: dict) -> PatientData:
        if not isinstance(payload, dict):
            raise FHIRValidationError("FHIR payload must be a JSON object")
        resource_type = payload.get("resourceType")
        if resource_type == "Bundle":
            data = self._process_bundle(payload)
        elif resource_type == "Patient":
            data = self._process_patient_resource(payload)
        else:
            raise FHIRValidationError(
                f"Unsupported resourceType '{resource_type}'; expected Bundle or Patient"
            )
        data.missing_required = [f for f in self.REQUIRED_FIELDS if getattr(data, f) is None]
        return data

    def _process_bundle(self, bundle: dict) -> PatientData:
        data = PatientData()
        entries = bundle.get("entry", []) or []
        patient_seen = False
        for entry in entries:
            resource = entry.get("resource") or entry
            rtype = resource.get("resourceType")
            if rtype == "Patient" and not patient_seen:
                self._merge_patient(data, resource)
                patient_seen = True
            elif rtype == "MedicationRequest":
                record = _medication_from_request(resource)
                if record:
                    data.medications.append(record)
            elif rtype == "Condition":
                data.conditions.append(_condition_from_resource(resource))
            elif rtype == "Observation":
                data.observations.append(_observation_from_resource(resource))
            elif rtype == "AllergyIntolerance":
                data.allergies.append(_allergy_from_resource(resource))
            elif rtype == "Procedure":
                data.procedures.append(_procedure_from_resource(resource))
            elif rtype == "RelatedPerson":
                data.caregivers.append(_caregiver_from_resource(resource))
        if not patient_seen:
            raise FHIRValidationError("Bundle does not contain a Patient resource")
        return data

    def _process_patient_resource(self, resource: dict) -> PatientData:
        data = PatientData()
        self._merge_patient(data, resource)
        return data

    def _merge_patient(self, data: PatientData, patient: dict) -> None:
        data.patient_id = patient.get("id")
        for identifier in patient.get("identifier", []) or []:
            system = (identifier.get("system") or "").lower()
            value = identifier.get("value")
            if not value:
                continue
            if "mrn" in system or "patient" in system:
                data.mrn = value
            if not data.mrn:
                data.mrn = value
        names = patient.get("name", []) or []
        if names:
            name_obj = names[0]
            data.name = " ".join(
                filter(None, [" ".join(name_obj.get("given", [])), name_obj.get("family")])
            )
        data.birth_date = patient.get("birthDate")
        data.gender = patient.get("gender")


def data_completeness(data: PatientData) -> float:
    """Score 0.0-1.0: presence of expected clinical sections."""
    scored = 0.0
    total = 6
    if data.birth_date:
        scored += 1
    if data.name:
        scored += 1
    if data.medications or data.conditions:
        scored += 1
    if data.observations:
        scored += 1
    if data.allergies:
        scored += 1
    if data.procedures:
        scored += 1
    return round(scored / total, 2)


AGE_PATTERN = re.compile(r"(\d+)")
