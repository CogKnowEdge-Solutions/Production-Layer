# CareMatch — Seed Data 

Exact values to type into the app's screens, so you can see it working correctly with your own eyes. Every example below has a **known correct answer** — if the app gives you something different, that's worth investigating, not something to ignore.

These exact values have already been tested and confirmed correct earlier in this project's development.

The five patients below are a quick manual walkthrough for confirming the app works with your own eyes — separate from the larger 12-patient formal evaluation described in `project_summary.md`.

---

## Step 1 — Go to "Trial Setup"

Enter this trial:

| Field | Value |
|---|---|
| Trial name | `Type 2 Diabetes Medication Trial` |
| Trial ID | `DEMO-TRIAL-001` |

Add these 3 rules (click "Add criterion" for the 2nd and 3rd):

| Rule ID | Rule Text | Type |
|---|---|---|
| `INC-01` | `Patient must be 50 years of age or older` | Inclusion |
| `INC-02` | `Patient must have a diagnosis of Type 2 Diabetes` | Inclusion |
| `EXC-01` | `Patient is currently taking Warfarin` | Exclusion |

**Important note on rule wording:** notice `EXC-01` is written as a plain statement ("Patient **is** currently taking Warfarin"), not as a negative requirement ("Patient must **not** be taking Warfarin"). Testing during this project found that the second style confuses the AI's reasoning. Always write exclusion rules the first way.

Click **Save trial**.

---

## Step 2 — Go to "New Assessment" and Try Each Patient Below

For each one, select the trial you just created, enter the Patient ID and record text exactly as shown, and check whether the result matches what's expected.

### Patient 1 — Should Come Back "Likely Eligible"
| Field | Value |
|---|---|
| Patient ID | `PT-1001` |
| Patient record | `62-year-old patient. Diagnosed with Type 2 Diabetes in 2019. Current medications: Metformin 500mg twice daily.` |

**Why:** meets both age and diagnosis rules, and isn't on Warfarin.

---

### Patient 2 — Should Come Back "Likely Excluded" (Age)
| Field | Value |
|---|---|
| Patient ID | `PT-1002` |
| Patient record | `35-year-old patient. Type 2 Diabetes diagnosed 2022. No current medications reported.` |

**Why:** too young — fails the age rule, even though the diabetes diagnosis is fine.

---

### Patient 3 — Should Come Back "Likely Excluded" (Medication)
| Field | Value |
|---|---|
| Patient ID | `PT-1003` |
| Patient record | `55-year-old patient. Type 2 Diabetes diagnosed 2020. Current medications: Warfarin 5mg daily, Metformin 500mg twice daily.` |

**Why:** meets age and diagnosis, but is on Warfarin — the one thing that disqualifies a patient.

---

### Patient 4 — Should Come Back "Needs More Information"
| Field | Value |
|---|---|
| Patient ID | `PT-1004` |
| Patient record | `Patient presenting for diabetes management follow-up. Type 2 Diabetes diagnosed 2019. Current medications: Metformin. Date of birth not recorded in this note.` |

**Why:** the record never actually states the patient's age — the AI should say "unclear" rather than guess, since guessing wrong here could wrongly exclude someone.

*(Note: "Needs More Information" here is the AI's suggestion about what's missing from the record — it is not the "Needs More Review" coordinator decision option, which is a separate thing a human picks later.)*

---

### Patient 5 — Should Come Back "Likely Eligible" (Boundary Case)
| Field | Value |
|---|---|
| Patient ID | `PT-1005` |
| Patient record | `Patient is exactly 50 years old (DOB confirms). Type 2 Diabetes diagnosed 2021. Current medications: Metformin, Atorvastatin.` |

**Why:** the rule says "50 or older" — exactly 50 should count as eligible, not excluded. This checks the AI handles the boundary correctly, not just clearly-above or clearly-below cases.

---

## What To Do If a Result Looks Wrong

1. Click into the **Assessment Review** screen and read the **evidence quote** shown for each rule — this tells you exactly what the AI based its answer on
2. Check that quote against the patient record text you actually typed in
3. If the quote is accurate but the conclusion still seems wrong, that's worth flagging as a real issue
4. If you have LangSmith tracing turned on, you can also look up that exact assessment there to see the full reasoning for each rule