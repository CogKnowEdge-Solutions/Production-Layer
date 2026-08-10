import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { listTrials, runAssessment, ApiError } from "@/lib/api";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "New Assessment — CareMatch Trial Eligibility Review" },
      {
        name: "description",
        content:
          "Start an evidence-backed clinical trial eligibility assessment: select a trial, enter a patient ID, and paste the patient record.",
      },
      { property: "og:title", content: "New Assessment — CareMatch" },
      {
        property: "og:description",
        content:
          "Evidence-backed clinical trial eligibility review for hospital research coordinators.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: NewAssessment,
});

const SAMPLE_RECORD = `62 y.o. female, post right upper lobectomy 2026-05-25.
Pathology: invasive adenocarcinoma, pT2aN1M0 (Stage IIB).
No prior systemic therapy. eGFR 78 mL/min/1.73m2 (2026-06-10).
History of psoriasis, topical management. Ambulatory, mild afternoon fatigue.`;

function NewAssessment() {
  const navigate = useNavigate();

  const trialsQuery = useQuery({
    queryKey: ["trials"],
    queryFn: listTrials,
  });

  const [trialId, setTrialId] = useState("");
  const [patientId, setPatientId] = useState("PT-84213");
  const [record, setRecord] = useState(SAMPLE_RECORD);

  // Once trials load, default the dropdown to the first one -- but only
  // once, not on every re-render (that would fight the user's own selection).
  if (trialsQuery.data && trialsQuery.data.length > 0 && trialId === "") {
    setTrialId(trialsQuery.data[0]!.trial_id);
  }

  const assessMutation = useMutation({
    mutationFn: runAssessment,
    onSuccess: (record) => {
      navigate({ to: "/review", search: { id: record.assessment_id } });
    },
  });

  const noTrialsRegistered = trialsQuery.data && trialsQuery.data.length === 0;

  return (
    <div className="mx-auto max-w-3xl px-6 py-12">
      <h1 className="text-3xl">New Assessment</h1>
      <p className="mt-3 max-w-xl text-sm leading-relaxed text-muted-foreground">
        Every criterion result is returned with a direct quote from the record supplied here. Nothing is
        asserted without a traceable excerpt.
      </p>

      {trialsQuery.isLoading && (
        <p className="mt-8 text-sm text-muted-foreground">Loading trials…</p>
      )}

      {trialsQuery.isError && (
        <p className="mt-8 border border-nomatch/40 bg-nomatch/8 p-4 text-sm text-nomatch">
          Couldn't reach the API to load trials. Is the backend running at the expected address?
        </p>
      )}

      {noTrialsRegistered && (
        <p className="mt-8 border border-unclear/50 bg-unclear/8 p-4 text-sm">
          No trials are registered yet. Set one up on the{" "}
          <a href="/trial-setup" className="underline underline-offset-4">
            Trial Setup
          </a>{" "}
          page first.
        </p>
      )}

      {trialsQuery.data && trialsQuery.data.length > 0 && (
        <form
          className="mt-10 space-y-7 border border-border bg-card p-7"
          onSubmit={(e) => {
            e.preventDefault();
            assessMutation.mutate({ trial_id: trialId, patient_id: patientId, patient_record: record });
          }}
        >
          <div>
            <label htmlFor="trial" className="mb-2 block text-sm font-medium">
              Trial protocol
            </label>
            <select
              id="trial"
              value={trialId}
              onChange={(e) => setTrialId(e.target.value)}
              className="w-full border border-input bg-background px-3 py-2.5 text-sm outline-none focus:border-primary focus:ring-2 focus:ring-ring/30"
            >
              {trialsQuery.data.map((t) => (
                <option key={t.trial_id} value={t.trial_id}>
                  {t.trial_id} — {t.trial_name}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label htmlFor="pid" className="mb-2 block text-sm font-medium">
              Patient ID
            </label>
            <input
              id="pid"
              value={patientId}
              onChange={(e) => setPatientId(e.target.value)}
              className="w-full border border-input bg-background px-3 py-2.5 font-mono text-sm outline-none focus:border-primary focus:ring-2 focus:ring-ring/30"
            />
          </div>

          <div>
            <label htmlFor="record" className="mb-2 block text-sm font-medium">
              Patient record text
            </label>
            <textarea
              id="record"
              rows={12}
              value={record}
              onChange={(e) => setRecord(e.target.value)}
              className="w-full border border-input bg-background px-3 py-2.5 font-mono text-[0.8125rem] leading-relaxed outline-none focus:border-primary focus:ring-2 focus:ring-ring/30"
            />
          </div>

          {assessMutation.isError && (
            <p className="border border-nomatch/40 bg-nomatch/8 p-3 text-sm text-nomatch">
              {assessMutation.error instanceof ApiError
                ? assessMutation.error.message
                : "Something went wrong running this assessment."}
            </p>
          )}

          <div className="flex items-center justify-between border-t border-border pt-6">
            <p className="text-xs text-muted-foreground">
              {assessMutation.isPending ? "Running eligibility review…" : "Connected to the CareMatch API."}
            </p>
            <button
              type="submit"
              disabled={assessMutation.isPending}
              className="bg-primary px-5 py-2.5 text-sm font-medium text-primary-foreground transition-colors hover:bg-structure focus:outline-none focus:ring-2 focus:ring-ring/40 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {assessMutation.isPending ? "Running…" : "Run eligibility review"}
            </button>
          </div>
        </form>
      )}
    </div>
  );
}