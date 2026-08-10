"""
Run this yourself, with your own OpenRouter key set, to see REAL LLM
reasoning end to end -- not the fake canned answers used in test_engine.py.

Setup:
    1. Copy .env.example to .env (same folder)
    2. Open .env and paste in your real OPENROUTER_API_KEY
    3. pip install -r requirements.txt
    4. python run_real_assessment.py

Tip: this runs 3 patients x 3 rules = 9 real API calls by default. To
save cost while iterating:
    python run_real_assessment.py --quick             (just P-1001, 3 calls)
    python run_real_assessment.py --patient P-1003     (just one specific patient, 3 calls)
"""

import json
import sys
import time

from engine import assess_patient
from llm_client import call_real_llm
from test_data.fixtures import ALL_TEST_PATIENTS, DIABETES_TRIAL

if __name__ == "__main__":
    if "--patient" in sys.argv:
        idx = sys.argv.index("--patient")
        target_id = sys.argv[idx + 1]
        patients_to_test = [p for p in ALL_TEST_PATIENTS if p["patient_id"] == target_id]
        if not patients_to_test:
            print(f"No test patient with id '{target_id}'. Valid ids: "
                  f"{[p['patient_id'] for p in ALL_TEST_PATIENTS]}")
            sys.exit(1)
    elif "--quick" in sys.argv:
        patients_to_test = ALL_TEST_PATIENTS[:1]
    else:
        patients_to_test = ALL_TEST_PATIENTS

    overall_start = time.monotonic()

    for patient in patients_to_test:
        print(f"\n{'=' * 70}")
        print(f"Patient: {patient['patient_id']}  (expected: {patient['expected_status']})")
        print("=" * 70)

        result = assess_patient(
            patient_id=patient["patient_id"],
            patient_record=patient["record"],
            protocol=DIABETES_TRIAL,
            call_llm=call_real_llm,
        )

        print(json.dumps(result.model_dump(), indent=2))

        match = "✅ MATCHES EXPECTED" if result.suggested_status == patient["expected_status"] else "❌ DID NOT MATCH EXPECTED"
        print(f"\n{match}")

    total_elapsed = time.monotonic() - overall_start
    print(f"\n{'=' * 70}")
    print(f"Total time: {total_elapsed:.1f}s across {len(patients_to_test)} patient(s)")
    print("=" * 70)


