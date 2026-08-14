# CareMatch — Seed Data 

Exact values to type into the app's screens, so you can see it working correctly with your own eyes. Every example below has a **known correct answer** — if the app gives you something different, that's worth investigating, not something to ignore.

These exact values have already been tested and confirmed correct earlier in this project's development.

The five patients below are a quick manual walkthrough for confirming the app works with your own eyes — separate from the larger 12-patient formal evaluation described in `project_summary.md`.

---

## Step 1 — Go to "Trial Setup"

Enter this trial:

**Trial name:**

```
Type 2 Diabetes Medication Trial
```

**Trial ID:**

```
DEMO-TRIAL-001
```

Add these 3 rules (click "Add criterion" for the 2nd and 3rd). For each rule, type in the Rule ID and Rule Text, and pick the type from the dropdown — the type isn't typed or pasted, you just select it:

**Rule 1**

Rule ID:
```
INC-01
```

Rule Text:
```
Patient must be 50 years of age or older
```

Type: **Inclusion** — select it in the dropdown.

**Rule 2**

Rule ID:
```
INC-02
```

Rule Text:
```
Patient must have a diagnosis of Type 2 Diabetes
```

Type: **Inclusion** — select it in the dropdown.

**Rule 3**

Rule ID:
```
EXC-01
```

Rule Text:
```
Patient is currently taking Warfarin
```

Type: **Exclusion** — select it in the dropdown.

**Important note on rule wording:** notice `EXC-01` is written as a plain statement ("Patient **is** currently taking Warfarin"), not as a negative requirement ("Patient must **not** be taking Warfarin"). Testing during this project found that the second style confuses the AI's reasoning. Always write exclusion rules the first way.

Click **Save trial**.

---

## Step 2 — Go to "New Assessment" and Try Each Patient Below

For each one, select the trial you just created, enter the Patient ID and record text exactly as shown, and check whether the result matches what's expected.

### Patient 1 — Should Come Back "Likely Eligible"

Patient ID to type in:

```
PT-1001
```

Patient record text to paste in:

```
62-year-old patient. Diagnosed with Type 2 Diabetes in 2019. Current medications: Metformin 500mg twice daily.
```

**Why:** meets both age and diagnosis rules, and isn't on Warfarin.

---

### Patient 2 — Should Come Back "Likely Excluded" (Age)

Patient ID to type in:

```
PT-1002
```

Patient record text to paste in:

```
35-year-old patient. Type 2 Diabetes diagnosed 2022. No current medications reported.
```

**Why:** too young — fails the age rule, even though the diabetes diagnosis is fine.

---

### Patient 3 — Should Come Back "Likely Excluded" (Medication)

Patient ID to type in:

```
PT-1003
```

Patient record text to paste in:

```
55-year-old patient. Type 2 Diabetes diagnosed 2020. Current medications: Warfarin 5mg daily, Metformin 500mg twice daily.
```

**Why:** meets age and diagnosis, but is on Warfarin — the one thing that disqualifies a patient.

---

### Patient 4 — Should Come Back "Needs More Information"

Patient ID to type in:

```
PT-1004
```

Patient record text to paste in:

```
Patient presenting for diabetes management follow-up. Type 2 Diabetes diagnosed 2019. Current medications: Metformin. Date of birth not recorded in this note.
```

**Why:** the record never actually states the patient's age — the AI should say "unclear" rather than guess, since guessing wrong here could wrongly exclude someone.

*(Note: "Needs More Information" here is the AI's suggestion about what's missing from the record — it is not the "Needs More Review" coordinator decision option, which is a separate thing a human picks later.)*

---

### Patient 5 — Should Come Back "Likely Eligible" (Boundary Case)

Patient ID to type in:

```
PT-1005
```

Patient record text to paste in:

```
Patient is exactly 50 years old (DOB confirms). Type 2 Diabetes diagnosed 2021. Current medications: Metformin, Atorvastatin.
```

**Why:** the rule says "50 or older" — exactly 50 should count as eligible, not excluded. This checks the AI handles the boundary correctly, not just clearly-above or clearly-below cases.

---

## Step 3 — Check Your Work

Now that all 5 patients have been assessed, confirm the app has actually stored everything by looking at two pages:

**1. The Trials page** (in the top navigation, click **Trials**)
- Confirm **`Type 2 Diabetes Medication Trial`** appears, with its 3 rules: `INC-01` (50 or older), `INC-02` (Type 2 Diabetes diagnosis), and `EXC-01` (currently taking Warfarin).
- Click the trial name to expand it if the rules aren't visible.

**2. The Assessment History page** (in the top navigation, click **Assessment History**)
- Confirm all **5 assessments** appear — one per patient (`PT-1001` through `PT-1005`), listed newest first.
- Each row should show the **AI suggestion** you saw when you ran it: likely eligible for `PT-1001` and `PT-1005`, likely excluded for `PT-1002` and `PT-1003`, and needs more information for `PT-1004`.
- Every row's **Decision** column should read **Undecided** — none of these assessments were given a coordinator decision in this walkthrough, and that's expected. Clicking any row opens the full evidence in the Assessment Review page.

If anything on either page is missing or different from above, that's worth investigating — the app stores everything permanently, so what you ran should be right there.

**Optional — clean up when you're done:** now that you've confirmed everything works, you can delete this test data with the Delete buttons on the **Assessment History** and **Trials** pages if you'd like a clean slate — entirely optional. The app works fine with this test data left in place too.

---

## Step 4 — (Optional) Flag One for Needs More Review

This walks through the "Needs More Review" coordinator decision and its confirmation screen:

1. Go to **Assessment History** and click `PT-1001` to open it in Assessment Review.
2. Click **Needs More Review**, then click **Flag for further review** (the reason is optional).
3. You should see a **"Flagged for further review"** confirmation, with the note "You can return to this assessment anytime once you have what you need." — and, deliberately, **no Accept or Deny buttons**. This is the intended UX: right after flagging, the screen shows a clean confirmation instead of immediately offering the final decision buttons again.
4. Navigate away (e.g. to **Assessment History**), then click `PT-1001` again to reopen it. This time you *should* see "Finalize this decision" with **Accept** and **Deny** buttons — the finalize controls return on a genuine return visit, because the assessment is flagged but not final.
5. Click **Accept**. The screen shows "Final decision."

If step 3 still shows Accept/Deny immediately after flagging — or step 4 shows the confirmation again on a return visit — that's a regression worth reporting.

---

## What To Do If a Result Looks Wrong

1. Click into the **Assessment Review** screen and read the **evidence quote** shown for each rule — this tells you exactly what the AI based its answer on
2. Check that quote against the patient record text you actually typed in
3. If the quote is accurate but the conclusion still seems wrong, that's worth flagging as a real issue
4. If you have LangSmith tracing turned on, you can also look up that exact assessment there to see the full reasoning for each rule