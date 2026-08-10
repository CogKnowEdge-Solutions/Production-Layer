// Real API client for CareMatch's Phase 2 backend. Replaces the mock
// data that used to live in carematch-data.ts.
//
// One important fix made here: the mock data used "nomatch" as a status
// value, but the real backend returns "does_not_match". This file is the
// single source of truth for these types now -- match the backend exactly,
// don't invent a separate frontend vocabulary that needs translating.

const API_BASE = import.meta.env["VITE_API_BASE_URL"] || "http://localhost:8000";

export type RuleStatus = "matches" | "does_not_match" | "unclear";

export type RuleCategory = "inclusion" | "exclusion";

export type RuleResult = {
  rule_id: string;
  rule_text: string;
  status: RuleStatus;
  evidence: string;
};

export type SuggestedStatus = "likely_eligible" | "likely_excluded" | "needs_more_info";

export type AssessmentResult = {
  patient_id: string;
  trial_id: string;
  suggested_status: SuggestedStatus;
  requires_coordinator_approval: true;
  rule_results: RuleResult[];
};

export type Decision = "accepted" | "denied" | "needs_more_review";

export const DECISION_LABEL: Record<Decision, string> = {
  accepted: "Accepted",
  denied: "Denied",
  needs_more_review: "Flagged for Further Review",
};

// Legacy rows written before the 3-option redesign stored "approved" /
// "overridden". The backend still returns them (no migration), so the UI
// must display them gracefully instead of crashing.
export function decisionDisplayLabel(value: string | null): string {
  if (value === null) return "Undecided";
  return DECISION_LABEL[value as Decision] ?? `Recorded (${value})`;
}

export type AssessmentRecord = {
  assessment_id: string;
  assessment: AssessmentResult;
  // string | null, not Decision | null: the backend keeps legacy
  // "approved"/"overridden" rows readable without migration, so responses
  // can contain values outside the current 3-option set.
  decision: string | null;
  decision_reason: string | null;
  provider_used: string;
  model_used: string;
};

export type TrialRule = {
  rule_id: string;
  rule_text: string;
  category: RuleCategory;
};

export type Trial = {
  trial_id: string;
  trial_name: string;
  rules: TrialRule[];
};

export const STATUS_LABEL: Record<RuleStatus, string> = {
  matches: "Matches",
  does_not_match: "Does Not Match",
  unclear: "Unclear",
};

export const SUGGESTED_STATUS_LABEL: Record<SuggestedStatus, string> = {
  likely_eligible: "Likely Eligible",
  likely_excluded: "Likely Excluded",
  needs_more_info: "Needs More Information",
};

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function handle<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const detail = typeof body.detail === "string" ? body.detail : `Request failed (${res.status})`;
    throw new ApiError(detail, res.status);
  }
  return res.json() as Promise<T>;
}

export async function listTrials(): Promise<Trial[]> {
  const res = await fetch(`${API_BASE}/trials`);
  return handle(res);
}

export async function getTrial(trialId: string): Promise<Trial> {
  const res = await fetch(`${API_BASE}/trials/${encodeURIComponent(trialId)}`);
  return handle(res);
}

export async function registerTrial(trial: Trial): Promise<Trial> {
  const res = await fetch(`${API_BASE}/trials`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(trial),
  });
  return handle(res);
}

export async function runAssessment(input: {
  trial_id: string;
  patient_id: string;
  patient_record: string;
}): Promise<AssessmentRecord> {
  const res = await fetch(`${API_BASE}/assess`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  return handle(res);
}

export async function getAssessment(assessmentId: string): Promise<AssessmentRecord> {
  const res = await fetch(`${API_BASE}/assessments/${encodeURIComponent(assessmentId)}`);
  return handle(res);
}

export async function recordDecision(
  assessmentId: string,
  input: { decision: Decision; reason?: string },
): Promise<AssessmentRecord> {
  const res = await fetch(`${API_BASE}/assessments/${encodeURIComponent(assessmentId)}/decision`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  return handle(res);
}