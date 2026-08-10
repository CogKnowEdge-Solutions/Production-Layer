"""
Synthetic test data only -- Phase 0 decision #7. No real patient data, ever,
at this stage. All patients and records below are entirely made up.
"""

from protocol import Protocol, Rule

# One protocol, manually converted into a checklist (Option A).
# In a real setting, a human does this conversion from the actual trial
# document. Here, we're doing it ourselves for testing purposes.
DIABETES_TRIAL = Protocol(
    trial_id="T-004",
    trial_name="Type 2 Diabetes Management Study",
    rules=[
        Rule(rule_id="INC-01", rule_text="Patient must be 50 years of age or older", category="inclusion"),
        Rule(rule_id="INC-02", rule_text="Patient must have a diagnosis of Type 2 Diabetes", category="inclusion"),
        Rule(rule_id="EXC-01", rule_text="Patient is currently taking Warfarin", category="exclusion"),
    ],
)

# Three fake patients, covering three different expected outcomes.

PATIENT_CLEARLY_ELIGIBLE = {
    "patient_id": "P-1001",
    "record": """
Patient: Jane Doe (synthetic test record)
Date of Birth: 1968-03-11 (age 57)
Diagnoses: Type 2 Diabetes Mellitus, diagnosed 2019
Current Medications: Metformin 500mg twice daily
Allergies: None known
""".strip(),
    "expected_status": "likely_eligible",
}

PATIENT_CLEARLY_EXCLUDED = {
    "patient_id": "P-1002",
    "record": """
Patient: John Smith (synthetic test record)
Date of Birth: 1975-06-20 (age 51)
Diagnoses: Type 2 Diabetes Mellitus, diagnosed 2021
Current Medications: Warfarin 5mg daily, Metformin 500mg twice daily
Allergies: Penicillin
""".strip(),
    "expected_status": "likely_excluded",
}

PATIENT_MISSING_INFO = {
    "patient_id": "P-1003",
    "record": """
Patient: Alex Rivera (synthetic test record)
Date of Birth: 1970-01-15 (age 55)
Diagnoses: Hypertension
Current Medications: Lisinopril 10mg daily
Allergies: None known
Note: No diabetes screening on file.
""".strip(),
    "expected_status": "needs_more_info",
}

ALL_TEST_PATIENTS = [PATIENT_CLEARLY_ELIGIBLE, PATIENT_CLEARLY_EXCLUDED, PATIENT_MISSING_INFO]