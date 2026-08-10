"""
Phase 5 (simulated) evaluation batch.

Registers one trial, then runs 12 synthetic patients through the REAL
API (real LLM calls -- this costs a small amount of real money). Each
patient has a known, human-decided "expected" answer, so we can compute
real agreement metrics instead of just eyeballing results.

Coverage, on purpose:
- 4 clearly eligible cases (including one edge-case age boundary)
- 5 clearly excluded cases (age, diagnosis, medication, one edge-case
  age boundary, one with multiple simultaneous failures)
- 3 genuinely unclear cases -- one per rule, deliberately re-testing the
  two real bugs found earlier in this project:
    - P-06 re-tests the "absence should mean unclear, not a confident
      no" calibration bug we fixed in the prompt
    - The trial's exclusion rule uses the CORRECT phrasing convention
      (positive disqualifying statement) we fixed after finding the
      negation-confusion bug -- this batch also confirms that fix holds
"""

import json
import sys
import urllib.request
import urllib.error

API_BASE = "http://localhost:8000"

TRIAL = {
    "trial_id": "TEST-BATCH-001",
    "trial_name": "Diabetes Study - Evaluation Batch",
    "rules": [
        {"rule_id": "INC-01", "rule_text": "Patient must be 50 years of age or older", "category": "inclusion"},
        {"rule_id": "INC-02", "rule_text": "Patient must have a diagnosis of Type 2 Diabetes", "category": "inclusion"},
        {"rule_id": "EXC-01", "rule_text": "Patient is currently taking Warfarin", "category": "exclusion"},
    ],
}

PATIENTS = [
    {
        "patient_id": "P-01", "expected": "likely_eligible",
        "record": "60-year-old patient. Diagnosed with Type 2 Diabetes in 2018. Current medications: Metformin 500mg twice daily.",
    },
    {
        "patient_id": "P-02", "expected": "likely_excluded",
        "record": "55-year-old patient. Type 2 Diabetes diagnosed 2020. Current medications: Warfarin 5mg daily, Metformin 500mg twice daily.",
    },
    {
        "patient_id": "P-03", "expected": "likely_excluded",
        "record": "35-year-old patient. Type 2 Diabetes diagnosed 2022. No current medications reported.",
    },
    {
        "patient_id": "P-04", "expected": "likely_excluded",
        "record": "60-year-old patient. Diagnoses: Hypertension only. No history of diabetes. Current medications: Lisinopril 10mg daily.",
    },
    {
        "patient_id": "P-05", "expected": "needs_more_info",
        "record": "Patient presenting for diabetes management follow-up. Type 2 Diabetes diagnosed 2019. Current medications: Metformin. Date of birth not recorded in this note.",
    },
    {
        "patient_id": "P-06", "expected": "needs_more_info",
        "record": "60-year-old patient. Diagnoses: Hypertension. Note: no diabetes screening on file. Current medications: Amlodipine 5mg daily.",
    },
    {
        "patient_id": "P-07", "expected": "needs_more_info",
        "record": "60-year-old patient. Type 2 Diabetes diagnosed 2017. Current medication list incomplete in this record -- patient reports 'a few pills' but names were not documented.",
    },
    {
        "patient_id": "P-08", "expected": "likely_eligible",
        "record": "72-year-old patient. Type 2 Diabetes diagnosed 2015, managed with insulin. No other current medications reported.",
    },
    {
        "patient_id": "P-09", "expected": "likely_excluded",
        "record": "40-year-old patient. No diagnosis of diabetes on file. Current medications: Warfarin 5mg daily for atrial fibrillation.",
    },
    {
        "patient_id": "P-10", "expected": "likely_eligible",
        "record": "Patient is exactly 50 years old (DOB confirms). Type 2 Diabetes diagnosed 2021. Current medications: Metformin, Atorvastatin.",
    },
    {
        "patient_id": "P-11", "expected": "likely_excluded",
        "record": "49-year-old patient. Type 2 Diabetes diagnosed 2020. No current medications reported.",
    },
    {
        "patient_id": "P-12", "expected": "likely_eligible",
        "record": "65-year-old patient. Type 2 Diabetes diagnosed 2016. Current medications: Aspirin 81mg daily, Lisinopril 10mg daily. Known allergy: penicillin.",
    },
]


def post(path: str, body: dict) -> tuple[int, dict]:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        f"{API_BASE}{path}", data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def main():
    print("=== Registering evaluation trial ===")
    status, body = post("/trials", TRIAL)
    print(f"POST /trials -> {status}")
    if status not in (200, 201):
        print("Trial registration failed (may already exist from a prior run) -- continuing anyway.")
        print(body)

    results = []
    print(f"\n=== Running {len(PATIENTS)} assessments (real LLM calls) ===")
    for i, patient in enumerate(PATIENTS, 1):
        print(f"[{i}/{len(PATIENTS)}] {patient['patient_id']}...", end=" ", flush=True)
        status, body = post(
            "/assess",
            {
                "trial_id": TRIAL["trial_id"],
                "patient_id": patient["patient_id"],
                "patient_record": patient["record"],
            },
        )
        if status != 201:
            print(f"FAILED (HTTP {status}): {body}")
            results.append({**patient, "actual": "ERROR", "match": False, "raw": body})
            continue

        actual = body["assessment"]["suggested_status"]
        match = actual == patient["expected"]
        print(f"expected={patient['expected']}, actual={actual} -> {'✅' if match else '❌'}")
        results.append({**patient, "actual": actual, "match": match, "raw": body})

    # Save full detail for later review
    with open("eval_results.json", "w") as f:
        json.dump(results, f, indent=2)

    total = len(results)
    matches = sum(1 for r in results if r["match"])
    false_exclusions = sum(
        1 for r in results if r["expected"] == "likely_eligible" and r["actual"] == "likely_excluded"
    )

    print(f"\n{'=' * 60}")
    print(f"RESULTS: {matches}/{total} matched expected outcome ({matches/total*100:.0f}%)")
    print(f"False exclusions (expected eligible, got excluded): {false_exclusions}")
    print(f"{'=' * 60}")
    print("\nMismatches:")
    for r in results:
        if not r["match"]:
            print(f"  {r['patient_id']}: expected={r['expected']}, got={r['actual']}")
    print("\nFull detail saved to eval_results.json")


if __name__ == "__main__":
    main()