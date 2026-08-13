import { test, expect } from '@playwright/test';

const headerLine = (pid: string, tid: string) => `${pid} · ${tid}`;

test('decision blocker prevents leaving undecided assessment', async ({ page }) => {
  // Create a trial and assessment
  const trialResp = await page.request.post('http://localhost:8000/trials', {
    data: {
      trial_id: 'T-BLOCKER-TEST',
      trial_name: 'Blocker Test Trial',
      rules: [
        { rule_id: 'INC-01', rule_text: 'Patient is 50 or older', category: 'inclusion' },
        { rule_id: 'EXC-01', rule_text: 'Patient is taking Warfarin', category: 'exclusion' },
      ],
    },
  });
  expect(trialResp.ok()).toBeTruthy();

  const assessResp = await page.request.post('http://localhost:8000/assess', {
    data: {
      trial_id: 'T-BLOCKER-TEST',
      patient_id: 'PT-BLOCKER-01',
      patient_record: 'Patient is a 55-year-old male with hypertension. Current medications: Metformin.',
    },
  });
  expect(assessResp.ok()).toBeTruthy();
  const assessData = await assessResp.json();
  const assessmentId = assessData.assessment_id;

  // Navigate to the review page with this undecided assessment
  await page.goto(`http://localhost:8080/review?id=${assessmentId}`);
  await page.waitForLoadState('networkidle');

  await expect(
    page.getByText(headerLine('PT-BLOCKER-01', 'T-BLOCKER-TEST'), { exact: true }),
  ).toBeVisible({ timeout: 10000 });

  // Click "Trials" nav tab - the undecided guard must pop a confirmation.
  // Register the dialog handler BEFORE the click: a registered dialog
  // listener disables Playwright's auto-dismiss, so the handler both
  // records the message and dismisses (Cancel), which unblocks the click.
  let capturedMessage = '';
  page.once('dialog', (dialog) => {
    capturedMessage = dialog.message();
    void dialog.dismiss();
  });
  await page.click('nav a:has-text("Trials")', { noWaitAfter: true });

  // Assert the confirmation dialog actually appeared with the right text
  expect(capturedMessage).toContain(
    "You haven't recorded a decision on this assessment yet. Leave without deciding?",
  );

  // Dialog dismissed (Cancel) => navigation must NOT have happened: still
  // on Review with the same assessment.
  await expect(
    page.getByText(headerLine('PT-BLOCKER-01', 'T-BLOCKER-TEST'), { exact: true }),
  ).toBeVisible();
  expect(page.url()).toContain(`/review?id=${assessmentId}`);

  // Now record a real decision (Accept)
  await page.click('button:has-text("Accept")');
  await page.waitForLoadState('networkidle');
  await expect(page.locator('h2:text("Accepted")')).toBeVisible();

  // Navigating away now must work with ZERO dialogs. Register a dialog
  // listener that fails the test if one fires.
  page.once('dialog', () => {
    throw new Error('Unexpected dialog after decision was recorded');
  });
  await page.click('nav a:has-text("Trials")');
  await page.waitForLoadState('networkidle');
  await expect(page.locator('h1:text("Trials")')).toBeVisible();

  // Navigate back to review - should still show the assessment
  await page.click('nav a:has-text("Assessment Review")');
  await page.waitForLoadState('networkidle');
  await expect(
    page.getByText(headerLine('PT-BLOCKER-01', 'T-BLOCKER-TEST'), { exact: true }),
  ).toBeVisible();
});
