import { test, expect } from '@playwright/test';

// The review page shows the patient+trial on the meta line and (once a
// decision exists) again inside the decision box, so use an exact match on
// the unique header line rather than a loose substring.
const headerLine = (pid: string, tid: string) =>
  `${pid} · ${tid}`;

test('review persists last assessment across tab switches', async ({ page }) => {
  // Create a trial and run an assessment to have something to view
  await page.goto('http://localhost:8000/docs');
  await page.waitForLoadState('networkidle');

  const trialResp = await page.request.post('http://localhost:8000/trials', {
    data: {
      trial_id: 'T-PERSIST-TEST',
      trial_name: 'Persistence Test Trial',
      rules: [
        { rule_id: 'INC-01', rule_text: 'Patient is 50 or older', category: 'inclusion' },
        { rule_id: 'EXC-01', rule_text: 'Patient is taking Warfarin', category: 'exclusion' },
      ],
    },
  });
  expect(trialResp.ok()).toBeTruthy();

  const assessResp = await page.request.post('http://localhost:8000/assess', {
    data: {
      trial_id: 'T-PERSIST-TEST',
      patient_id: 'PT-PERSIST-01',
      patient_record: 'Patient is a 55-year-old male with hypertension. Current medications: Metformin.',
    },
  });
  expect(assessResp.ok()).toBeTruthy();
  const assessData = await assessResp.json();
  const assessmentId = assessData.assessment_id;

  // Navigate to the review page with this assessment
  await page.goto(`http://localhost:8080/review?id=${assessmentId}`);
  await page.waitForLoadState('networkidle');

  // Verify the assessment loads - the exact header line is unique
  await expect(
    page.getByText(headerLine('PT-PERSIST-01', 'T-PERSIST-TEST'), { exact: true }),
  ).toBeVisible();

  // Record a decision so navigating away is not blocked by the undecided-
  // assessment guard (that guard is covered by decision-blocker.spec.ts).
  await page.click('button:has-text("Accept")');
  await expect(page.locator('h2:text("Accepted")')).toBeVisible();

  // Navigate to Trials page
  await page.click('nav a:has-text("Trials")');
  await page.waitForLoadState('networkidle');
  await expect(page.locator('h1:text("Trials")')).toBeVisible();

  // Navigate back to Assessment Review via nav (no ?id= in URL)
  await page.click('nav a:has-text("Assessment Review")');
  await page.waitForLoadState('networkidle');

  // Assert the same assessment reappears automatically (from localStorage)
  await expect(
    page.getByText(headerLine('PT-PERSIST-01', 'T-PERSIST-TEST'), { exact: true }),
  ).toBeVisible();

  // Verify URL now has the assessment ID
  expect(page.url()).toContain(assessmentId);
});
