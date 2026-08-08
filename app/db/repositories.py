import uuid

from sqlalchemy.orm import Session

from app.db.models import (
    Assessment,
    AssessmentOverride,
    AuditLog,
    Caregiver,
    Patient,
    RuleEvaluation,
    Trial,
    User,
)


def create_user(db: Session, **kwargs) -> User:
    user = User(**kwargs)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_user_by_username(db: Session, username: str) -> User | None:
    return db.query(User).filter(User.username == username).first()


def get_user(db: Session, user_id: uuid.UUID) -> User | None:
    return db.get(User, user_id)


def list_users(db: Session, offset: int = 0, limit: int = 50):
    return db.query(User).order_by(User.created_at).offset(offset).limit(limit).all()


def count_users(db: Session) -> int:
    return db.query(User).count()


# --- Patients ---


def get_patient(db: Session, patient_id: uuid.UUID) -> Patient | None:
    return db.get(Patient, patient_id)


def find_patient_by_mrn(db: Session, hospital_id: str | None, mrn: str | None) -> Patient | None:
    if not mrn:
        return None
    q = db.query(Patient).filter(Patient.mrn == mrn)
    if hospital_id:
        q = q.filter(Patient.hospital_id == hospital_id)
    return q.first()


def create_patient(db: Session, **kwargs) -> Patient:
    patient = Patient(**kwargs)
    db.add(patient)
    db.commit()
    db.refresh(patient)
    return patient


def update_patient(db: Session, patient: Patient, **kwargs) -> Patient:
    for key, value in kwargs.items():
        setattr(patient, key, value)
    db.commit()
    db.refresh(patient)
    return patient


# --- Trials ---


def get_trial(db: Session, trial_id: uuid.UUID) -> Trial | None:
    return db.get(Trial, trial_id)


def create_trial(db: Session, **kwargs) -> Trial:
    trial = Trial(**kwargs)
    db.add(trial)
    db.commit()
    db.refresh(trial)
    return trial


def list_trials(db: Session, offset: int = 0, limit: int = 50):
    return db.query(Trial).order_by(Trial.created_at.desc()).offset(offset).limit(limit).all()


def count_trials(db: Session) -> int:
    return db.query(Trial).count()


# --- Assessments ---


def get_assessment(db: Session, assessment_id: uuid.UUID) -> Assessment | None:
    return db.get(Assessment, assessment_id)


def create_assessment(db: Session, **kwargs) -> Assessment:
    assessment = Assessment(**kwargs)
    db.add(assessment)
    db.commit()
    db.refresh(assessment)
    return assessment


def update_assessment(db: Session, assessment: Assessment, **kwargs) -> Assessment:
    for key, value in kwargs.items():
        setattr(assessment, key, value)
    db.commit()
    db.refresh(assessment)
    return assessment


def list_assessments(db: Session, offset: int = 0, limit: int = 50):
    return (
        db.query(Assessment)
        .order_by(Assessment.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


def count_assessments(db: Session) -> int:
    return db.query(Assessment).count()


# --- Rule evaluations ---


def create_rule_evaluation(db: Session, **kwargs) -> RuleEvaluation:
    evaluation = RuleEvaluation(**kwargs)
    db.add(evaluation)
    db.flush()
    return evaluation


def get_rule_evaluation(db: Session, rule_eval_id: uuid.UUID) -> RuleEvaluation | None:
    return db.get(RuleEvaluation, rule_eval_id)


def update_rule_evaluation(db: Session, evaluation: RuleEvaluation, **kwargs) -> RuleEvaluation:
    for key, value in kwargs.items():
        setattr(evaluation, key, value)
    db.commit()
    db.refresh(evaluation)
    return evaluation


# --- Caregivers ---


def create_caregiver(db: Session, **kwargs) -> Caregiver:
    caregiver = Caregiver(**kwargs)
    db.add(caregiver)
    db.commit()
    db.refresh(caregiver)
    return caregiver


def list_caregivers_for_patient(db: Session, patient_id: uuid.UUID):
    return (
        db.query(Caregiver)
        .filter(Caregiver.patient_id == patient_id)
        .order_by(Caregiver.created_at)
        .all()
    )


# --- Overrides ---


def create_override(db: Session, **kwargs) -> AssessmentOverride:
    override = AssessmentOverride(**kwargs)
    db.add(override)
    db.flush()
    return override


def list_overrides_for_assessment(db: Session, assessment_id: uuid.UUID):
    return (
        db.query(AssessmentOverride)
        .filter(AssessmentOverride.assessment_id == assessment_id)
        .order_by(AssessmentOverride.timestamp)
        .all()
    )


def list_all_overrides(db: Session, offset: int = 0, limit: int = 50):
    return (
        db.query(AssessmentOverride)
        .order_by(AssessmentOverride.timestamp.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


# --- Audit logs ---


def list_audit_logs(db: Session, offset: int = 0, limit: int = 50):
    return db.query(AuditLog).order_by(AuditLog.timestamp.desc()).offset(offset).limit(limit).all()


def count_audit_logs(db: Session) -> int:
    return db.query(AuditLog).count()
