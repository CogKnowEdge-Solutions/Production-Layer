import { test, expect } from '@playwright/test';

test('loading spinner with message shows while the LLM builds the assessment', async ({
  page,
}) => {
  // Make sure a trial exists to run an assessment against
  await page.goto('http://localhost:8000/docs');
  await page.waitForLoadState('networkidle');
  const trialResp = await page.request.post('http://localhost:8000/trials', {
    data: {
      trial_id: 'T-SPINNER-TEST',
      trial_name: 'Spinner Test Trial',
      rules: [
        { rule_id: 'INC-01', rule_text: 'Patient is 50 or older', category: 'inclusion' },
        { rule_id: 'EXC-01', rule_text: 'Patient is taking Warfarin', category: 'exclusion' },
      ],
    },
  });
  expect(trialResp.ok()).toBeTruthy();

  // Delay the /assess response so the pending state is observable
  await page.route('**/assess', async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 4000));
    await route.continue();
  });

  await page.goto('http://localhost:8080/');
  await page.waitForLoadState('networkidle');

  await page.selectOption('#trial', 'T-SPINNER-TEST');
  await page.fill('#pid', 'PT-SPINNER-01');
  await page.click('button:has-text("Run eligibility review")');

  // The YouTube-style spinning wheel + message must be visible while pending
  const spinner = page.locator('[role="status"] .animate-spin');
  await expect(spinner).toBeVisible({ timeout: 5000 });
  await expect(page.getByText('Getting the assessment…', { exact: true })).toBeVisible();
  await expect(page.getByText(/Consulting the LLM/)).toBeVisible();

  // Once the LLM call resolves, it lands on the review page for that patient
  await expect(
    page.getByText('PT-SPINNER-01 · T-SPINNER-TEST', { exact: true }),
  ).toBeVisible({ timeout: 30000 });
});
