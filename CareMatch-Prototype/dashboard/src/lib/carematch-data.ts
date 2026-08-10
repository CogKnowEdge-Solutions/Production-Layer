export type RuleStatus = "matches" | "nomatch" | "unclear";

export type RuleResult = {
  id: string;
  text: string;
  status: RuleStatus;
  evidence: string;
};

export type Trial = {
  id: string;
  name: string;
};

export const TRIALS: Trial[] = [
  { id: "NCT04821375", name: "ATLAS-2 — Adjuvant Therapy in Stage II NSCLC" },
  { id: "NCT05119842", name: "MERIDIAN — Type 2 Diabetes Renal Outcomes" },
];

export const STATUS_LABEL: Record<RuleStatus, string> = {
  matches: "Matches",
  nomatch: "Does Not Match",
  unclear: "Unclear",
};

export function deriveSuggestion(rules: RuleResult[]): string {
  // Any single Unclear criterion forces "Needs More Information" — this
  // overrides Likely Eligible / Likely Excluded entirely.
  if (rules.some((r) => r.status === "unclear")) return "Needs More Information";
  if (rules.some((r) => r.id.startsWith("EXC") && r.status === "matches")) return "Likely Excluded";
  if (rules.some((r) => r.id.startsWith("INC") && r.status === "nomatch")) return "Likely Excluded";
  return "Likely Eligible";
}

const ASSESSMENT = {
  trial: TRIALS[0]!,
  patientId: "PT-84213",
  inclusion: [
    {
      id: "INC-01",
      text: "Patient is 18 years of age or older at time of screening.",
      status: "matches",
      evidence:
        "\"62 y.o. female presenting for post-operative oncology follow-up.\"",
    },
    {
      id: "INC-02",
      text: "Histologically confirmed stage II non-small cell lung carcinoma.",
      status: "matches",
      evidence:
        "\"Pathology: invasive adenocarcinoma of the right upper lobe, pT2aN1M0 — Stage IIB.\"",
    },
    {
      id: "INC-03",
      text: "ECOG performance status of 0 or 1 documented within 28 days.",
      status: "unclear",
      evidence:
        "\"Patient ambulatory, tolerating light housework, reports fatigue in the afternoons.\" No ECOG score recorded in the chart.",
    },
  ] as RuleResult[],
  exclusion: [
    {
      id: "EXC-01",
      text: "Prior systemic chemotherapy for the current malignancy.",
      status: "nomatch",
      evidence:
        "\"No prior systemic therapy. Surgery only; adjuvant options under discussion.\"",
    },
    {
      id: "EXC-02",
      text: "Active autoimmune disease requiring systemic immunosuppression.",
      status: "unclear",
      evidence:
        "\"History of psoriasis, previously managed topically. Current medication list incomplete.\"",
    },
    {
      id: "EXC-03",
      text: "eGFR below 45 mL/min/1.73m² within 14 days of enrollment.",
      status: "nomatch",
      evidence: "\"eGFR 78 mL/min/1.73m² (2026-06-10). Creatinine 0.9 mg/dL.\"",
    },
  ] as RuleResult[],
};

export const SAMPLE_ASSESSMENT = {
  ...ASSESSMENT,
};

export const SAMPLE_RECORD = `62 y.o. female, post right upper lobectomy 2026-05-25.
Pathology: invasive adenocarcinoma, pT2aN1M0 (Stage IIB).
No prior systemic therapy. eGFR 78 mL/min/1.73m2 (2026-06-10).
History of psoriasis, topical management. Ambulatory, mild afternoon fatigue.`;
