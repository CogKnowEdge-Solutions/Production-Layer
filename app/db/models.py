import uuid
from datetime import UTC, date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db.database import Base


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


def _now() -> datetime:
    return datetime.now(UTC)


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(
        String(50), index=True
    )  # ADMINISTRATOR/PROVIDER/COORDINATOR/AUDITOR
    hospital_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Patient(Base):
    __tablename__ = "patients"

    patient_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    hospital_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    mrn: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    first_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    gender: Mapped[str | None] = mapped_column(String(50), nullable=True)
    fhir_data: Mapped[dict] = mapped_column(JSON, default=dict)
    data_quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )

    caregivers: Mapped[list["Caregiver"]] = relationship(
        back_populates="patient", cascade="all, delete-orphan"
    )


class Caregiver(Base):
    __tablename__ = "caregivers"

    caregiver_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    patient_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("patients.patient_id"), index=True
    )
    relationship_type: Mapped[str] = mapped_column(
        String(50)
    )  # PRIMARY/EMERGENCY_CONTACT/LEGAL_PROXY/POWER_OF_ATTORNEY
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    qualifications: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    authorization_status: Mapped[str] = mapped_column(
        String(50), default="PENDING"
    )  # VERIFIED/PENDING/REVOKED
    consent_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    patient: Mapped[Patient] = relationship(back_populates="caregivers")


class Trial(Base):
    __tablename__ = "trials"

    trial_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    nct_number: Mapped[str | None] = mapped_column(
        String(20), nullable=True, unique=True, index=True
    )
    trial_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    protocol_version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(
        String(50), default="ACTIVE", index=True
    )  # ACTIVE/RECRUITING/COMPLETED
    rules: Mapped[dict] = mapped_column(JSON, default=dict)
    inclusion_rules: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    exclusion_rules: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Assessment(Base):
    __tablename__ = "assessments"

    assessment_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    patient_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("patients.patient_id"), index=True
    )
    trial_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("trials.trial_id"), index=True)
    hospital_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    overall_status: Mapped[str] = mapped_column(
        String(50)
    )  # LIKELY_ELIGIBLE/LIKELY_INELIGIBLE/UNCLEAR
    ai_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    data_quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    assessment_data: Mapped[dict] = mapped_column(JSON, default=dict)
    coordinator_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    review_status: Mapped[str] = mapped_column(
        String(50), default="PENDING"
    )  # PENDING/APPROVED/OVERRIDDEN
    final_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    override_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    rule_evaluations: Mapped[list["RuleEvaluation"]] = relationship(
        back_populates="assessment", cascade="all, delete-orphan"
    )
    overrides: Mapped[list["AssessmentOverride"]] = relationship(
        back_populates="assessment", cascade="all, delete-orphan"
    )


class RuleEvaluation(Base):
    __tablename__ = "rule_evaluations"

    rule_eval_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    assessment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("assessments.assessment_id"), index=True
    )
    rule_id: Mapped[str] = mapped_column(String(255))
    rule_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    rule_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    category: Mapped[str | None] = mapped_column(String(20), nullable=True)  # inclusion/exclusion
    status: Mapped[str] = mapped_column(String(50))  # MATCHES/DOES_NOT_MATCH/UNCLEAR
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    evidence: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    missing_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    is_overridden: Mapped[bool] = mapped_column(Boolean, default=False)
    override_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    original_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    overridden_by_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    overridden_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    assessment: Mapped[Assessment] = relationship(back_populates="rule_evaluations")


class AssessmentOverride(Base):
    __tablename__ = "assessment_overrides"

    override_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    assessment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("assessments.assessment_id"), index=True
    )
    rule_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    original_status: Mapped[str] = mapped_column(String(50))
    new_status: Mapped[str] = mapped_column(String(50))
    reasoning: Mapped[str] = mapped_column(Text)
    coordinator_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    impact_on_eligibility: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    assessment: Mapped[Assessment] = relationship(back_populates="overrides")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    audit_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    hospital_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(100), index=True)
    resource_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    data_accessed: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    result: Mapped[str] = mapped_column(String(20), default="success")  # success/denied/error
    ip_address: Mapped[str | None] = mapped_column(String(50), nullable=True)
    reason_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
