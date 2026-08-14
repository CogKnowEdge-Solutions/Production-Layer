import { test, expect } from '@playwright/test';

// Local dev only: dashboard (8080) + API (8000) via docker compose.
const DASH = 'http://localhost:8080';
const API = 'http://localhost:8000';

test.setTimeout(180_000);

test('needs_more_review: clean confirmation right after submit, buttons on genuine return visit', async ({ page }) => {
  const trialId = `T-NMR-${Date.now()}`;
  const patientId = 'PT-NMR-01';

  // Seed a trial and run a real assessment so we have an undecided record.
  const trialResp = await page.request.post(`${API}/trials`, {
    data: {
      trial_id: trialId,
      trial_name: 'Needs More Review Test Trial',
      rules: [
        { rule_id: 'INC-01', rule_text: 'Adult patients aged 18 years or older.', category: 'inclusion' },
        { rule_id: 'EXC-01', rule_text: 'Patient is currently taking Warfarin.', category: 'exclusion' },
      ],
    },
  });
  expect(trialResp.ok()).toBeTruthy();

  const assessResp = await page.request.post(`${API}/assess`, {
    data: {
      trial_id: trialId,
      patient_id: patientId,
      patient_record:
        'Patient is a 60-year-old female with a history of lung cancer treated surgically. Current medications: Metformin only. No anticoagulants.',
    },
  });
  expect(assessResp.ok()).toBeTruthy();
  const assessmentId = (await assessResp.json()).assessment_id;

  // --- Scenario a: just-submitted shows confirmation, NO Accept/Deny ---
  await page.goto(`${DASH}/review?id=${assessmentId}`);
  await expect(page.getByText(`${patientId} · ${trialId}`, { exact: true })).toBeVisible();

  await page.getByRole('button', { name: 'Needs More Review' }).click();
  await page.getByRole('button', { name: 'Flag for further review' }).click();

  await expect(
    page.getByRole('heading', { name: 'Flagged for further review', exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText('You can return to this assessment anytime once you have what you need.'),
  ).toBeVisible();
  await expect(page.getByRole('button', { name: 'Accept' })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Deny' })).toHaveCount(0);

  // --- Scenario b: leave entirely, return via History -> buttons DO appear ---
  await page.goto(`${DASH}/history`);
  await expect(page.getByRole('heading', { name: 'Assessment History' })).toBeVisible();
  await page.getByText(patientId).first().click();

  await expect(page.getByText(`${patientId} · ${trialId}`, { exact: true })).toBeVisible();
  await expect(page.getByText('Finalize this decision')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Accept' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Deny' })).toBeVisible();

  // --- Accept still final from the return-visit view (regression check) ---
  await page.getByRole('button', { name: 'Accept' }).click();
  await expect(page.getByText(/Final decision/)).toBeVisible();
});
