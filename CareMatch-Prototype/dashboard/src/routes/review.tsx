import { createFileRoute, Link } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import {
  decisionDisplayLabel,
  getAssessment,
  recordDecision,
  SUGGESTED_STATUS_LABEL,
  type Decision,
  type RuleResult,
  type RuleStatus,
} from "@/lib/api";
import { RuleCard } from "@/components/RuleCard";

export const Route = createFileRoute("/review")({
  validateSearch: (search: Record<string, unknown>) => ({
    id: typeof search["id"] === "string" ? search["id"] : "",
  }),
  head: () => ({
    meta: [
      { title: "Assessment Review — CareMatch Eligibility Evidence" },
      {
        name: "description",
        content:
          "Review inclusion and exclusion criteria results with the exact record excerpt behind each one, then approve or override.",
      },
      { property: "og:title", content: "Assessment Review — CareMatch" },
      {
        property: "og:description",
        content: "Criterion-by-criterion eligibility evidence with coordinator approval or override.",
      },
    ],
  }),
  component: Review,
});

const DEFAULT_REASON = "";

function Review() {
  const { id } = Route.useSearch();
  const queryClient = useQueryClient();

  const assessmentQuery = useQuery({
    queryKey: ["assessment", id],
    queryFn: () => getAssessment(id),
    enabled: id !== "",
  });

  const [panel, setPanel] = useState<"deny" | "needs_more_review" | null>(null);
  const [reason, setReason] = useState(DEFAULT_REASON);

  const decisionMutation = useMutation({
    mutationFn: (input: { decision: Decision; reason?: string }) => recordDecision(id, input),
    onSuccess: (record) => {
      queryClient.setQueryData(["assessment", id], record);
      setPanel(null);
      setReason(DEFAULT_REASON);
    },
  });

  if (id === "") {
    return (
      <div className="mx-auto max-w-3xl px-6 py-12">
        <p className="text-sm text-muted-foreground">
          No assessment selected.{" "}
          <Link to="/" className="text-primary underline underline-offset-4">
            Start a new assessment
          </Link>
          .
        </p>
      </div>
    );
  }

  if (assessmentQuery.isLoading) {
    return (
      <div className="mx-auto max-w-3xl px-6 py-12">
        <p className="text-sm text-muted-foreground">Loading assessment…</p>
      </div>
    );
  }

  if (assessmentQuery.isError || !assessmentQuery.data) {
    return (
      <div className="mx-auto max-w-3xl px-6 py-12">
        <p className="border border-nomatch/40 bg-nomatch/8 p-4 text-sm text-nomatch">
          Couldn't load this assessment. It may not exist, or the API may be unreachable.
        </p>
      </div>
    );
  }

  const record = assessmentQuery.data;
  const a = record.assessment;
  const inclusion = a.rule_results.filter((r) => r.rule_id.startsWith("INC"));
  const exclusion = a.rule_results.filter((r) => r.rule_id.startsWith("EXC"));

  const tally = a.rule_results.reduce<Record<RuleStatus, number>>(
    (counts, rule) => ({ ...counts, [rule.status]: counts[rule.status] + 1 }),
    { matches: 0, unclear: 0, does_not_match: 0 },
  );

  const suggestionLabel = SUGGESTED_STATUS_LABEL[a.suggested_status];
  const bannerStyle =
    a.suggested_status === "needs_more_info"
      ? "border-l-unclear bg-unclear/8"
      : a.suggested_status === "likely_excluded"
        ? "border-l-nomatch bg-nomatch/6"
        : "border-l-primary bg-primary/6";

  return (
    <div className="mx-auto max-w-7xl px-5 py-10 sm:px-6 sm:py-12">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <div>
          <h1 className="text-3xl">Assessment Review</h1>
          <p className="mt-2 font-mono text-xs text-muted-foreground">
            {a.patient_id} · {a.trial_id}
          </p>
          <p className="mt-1 font-mono text-[0.68rem] text-muted-foreground/70">
            Assessed via {record.provider_used} / {record.model_used}
          </p>
        </div>
        <Link to="/" className="text-sm text-primary underline underline-offset-4">
          New assessment
        </Link>
      </div>

      <section
        className={`mt-8 grid min-h-44 gap-8 rounded-md border border-structure/20 border-l-4 p-7 shadow-card sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center sm:p-9 ${bannerStyle}`}
      >
        <div className="min-w-0">
          <p className="font-mono text-[0.68rem] uppercase tracking-widest text-muted-foreground">
            Automated pre-read
          </p>
          <h2 className="mt-3 text-2xl text-structure sm:text-3xl">AI Suggestion: {suggestionLabel}</h2>
          <p className="mt-3 max-w-2xl text-sm leading-relaxed text-muted-foreground">
            This is a recommendation. Review the evidence below before deciding.
          </p>
        </div>
        <div className="grid grid-cols-3 divide-x divide-structure/15 border-y border-structure/15 py-4 sm:border-y-0 sm:py-0">
          <TallyStat value={tally.matches} label="Matches" tone="text-match" />
          <TallyStat value={tally.unclear} label="Unclear" tone="text-unclear" />
          <TallyStat value={tally.does_not_match} label="Does not match" tone="text-nomatch" />
        </div>
      </section>

      <div className="mt-11 grid items-start gap-10 lg:grid-cols-2 lg:gap-7">
        <Section title="Inclusion Criteria" note="Must be satisfied for enrollment.">
          {inclusion.map((r) => (
            <RuleCard key={r.rule_id} rule={r} />
          ))}
        </Section>

        <Section title="Exclusion Criteria" note="Any match disqualifies the patient.">
          {exclusion.map((r) => (
            <RuleCard key={r.rule_id} rule={r} />
          ))}
        </Section>
      </div>

      <section className="mt-12 border-t border-border pt-8">
        {record.decision === null ? (
          <>
            <h2 className="text-lg">Coordinator decision</h2>
            <p className="mt-2 text-sm text-muted-foreground">
              An explicit decision is required, including for clean cases.
            </p>

            {decisionMutation.isError && (
              <p className="mt-4 border border-nomatch/40 bg-nomatch/8 p-3 text-sm text-nomatch">
                Couldn't record that decision. Please try again.
              </p>
            )}

            <div className="mt-5 flex flex-wrap gap-3">
              <button
                onClick={() => decisionMutation.mutate({ decision: "accepted" })}
                disabled={decisionMutation.isPending}
                className="bg-primary px-5 py-2.5 text-sm font-medium text-primary-foreground transition-colors hover:bg-structure disabled:cursor-not-allowed disabled:opacity-60"
              >
                Accept
              </button>
              <button
                onClick={() => setPanel(panel === "deny" ? null : "deny")}
                disabled={decisionMutation.isPending}
                className="border border-structure/50 px-5 py-2.5 text-sm font-medium text-structure transition-colors hover:bg-secondary disabled:cursor-not-allowed disabled:opacity-60"
              >
                Deny
              </button>
              <button
                onClick={() => setPanel(panel === "needs_more_review" ? null : "needs_more_review")}
                disabled={decisionMutation.isPending}
                className="border border-structure/50 px-5 py-2.5 text-sm font-medium text-structure transition-colors hover:bg-secondary disabled:cursor-not-allowed disabled:opacity-60"
              >
                Needs More Review
              </button>
            </div>

            {panel === "deny" && (
              <DecisionPanel
                title="Why are you denying this assessment?"
                required
                placeholder="Documented rationale, recorded with the assessment."
                reason={reason}
                onChange={setReason}
                pending={decisionMutation.isPending}
                submitLabel={decisionMutation.isPending ? "Saving…" : "Confirm deny"}
                onSubmit={() =>
                  decisionMutation.mutate({ decision: "denied", reason: reason.trim() })
                }
                onCancel={() => {
                  setPanel(null);
                  setReason(DEFAULT_REASON);
                }}
              />
            )}

            {panel === "needs_more_review" && (
              <DecisionPanel
                title="What additional information or review is needed?"
                required={false}
                placeholder="Optional note, e.g. awaiting a follow-up report."
                reason={reason}
                onChange={setReason}
                pending={decisionMutation.isPending}
                submitLabel={decisionMutation.isPending ? "Saving…" : "Flag for further review"}
                onSubmit={() => {
                  const trimmed = reason.trim();
                  decisionMutation.mutate(
                    trimmed
                      ? { decision: "needs_more_review", reason: trimmed }
                      : { decision: "needs_more_review" },
                  );
                }}
                onCancel={() => {
                  setPanel(null);
                  setReason(DEFAULT_REASON);
                }}
              />
            )}
          </>
        ) : record.decision === "needs_more_review" ? (
          <>
            <div className="border-l-4 border-l-unclear bg-unclear/8 p-6">
              <p className="font-mono text-[0.68rem] uppercase tracking-widest text-muted-foreground">
                Decision recorded — awaiting final decision
              </p>
              <h2 className="mt-2 text-xl text-structure">
                {decisionDisplayLabel(record.decision)}
              </h2>
              {record.decision_reason && (
                <div className="evidence mt-3 max-w-2xl">{record.decision_reason}</div>
              )}
              <p className="mt-3 text-xs text-muted-foreground">
                Not final. Return when the missing information is available.
              </p>
            </div>

            <div className="mt-6">
              <h3 className="text-base">Finalize this decision</h3>
              <p className="mt-1 text-sm text-muted-foreground">
                Recorded by coordinator · {a.patient_id} · {a.trial_id}
              </p>
              <div className="mt-3 flex flex-wrap gap-3">
                <button
                  onClick={() => decisionMutation.mutate({ decision: "accepted" })}
                  disabled={decisionMutation.isPending}
                  className="bg-primary px-5 py-2.5 text-sm font-medium text-primary-foreground transition-colors hover:bg-structure disabled:cursor-not-allowed disabled:opacity-60"
                >
                  Accept
                </button>
                <button
                  onClick={() => setPanel(panel === "deny" ? null : "deny")}
                  disabled={decisionMutation.isPending}
                  className="border border-structure/50 px-5 py-2.5 text-sm font-medium text-structure transition-colors hover:bg-secondary disabled:cursor-not-allowed disabled:opacity-60"
                >
                  Deny
                </button>
              </div>

              {panel === "deny" && (
                <DecisionPanel
                  title="Why are you denying this assessment?"
                  required
                  placeholder="Documented rationale, recorded with the assessment."
                  reason={reason}
                  onChange={setReason}
                  pending={decisionMutation.isPending}
                  submitLabel={decisionMutation.isPending ? "Saving…" : "Confirm deny"}
                  onSubmit={() =>
                    decisionMutation.mutate({ decision: "denied", reason: reason.trim() })
                  }
                  onCancel={() => {
                    setPanel(null);
                    setReason(DEFAULT_REASON);
                  }}
                />
              )}
            </div>
          </>
        ) : (
          <div className="border-l-4 border-l-structure bg-secondary p-6">
            <p className="font-mono text-[0.68rem] uppercase tracking-widest text-muted-foreground">
              Decision recorded
            </p>
            <h2 className="mt-2 text-xl text-structure">
              {decisionDisplayLabel(record.decision)}
            </h2>
            {record.decision_reason && (
              <div className="evidence mt-3 max-w-2xl">{record.decision_reason}</div>
            )}
            <p className="mt-3 text-xs text-muted-foreground">
              Final decision · {a.patient_id} · {a.trial_id}
            </p>
          </div>
        )}
      </section>
    </div>
  );
}

function Section({
  title,
  note,
  children,
}: {
  title: string;
  note: string;
  children: React.ReactNode;
}) {
  return (
    <section>
      <div className="grid grid-cols-[minmax(0,1fr)_auto] items-baseline gap-4 border-b border-border pb-3">
        <h2 className="text-xl">{title}</h2>
        <p className="text-right text-xs text-muted-foreground">{note}</p>
      </div>
      <div className="mt-5 space-y-5">{children}</div>
    </section>
  );
}

function TallyStat({ value, label, tone }: { value: number; label: string; tone: string }) {
  return (
    <div className="min-w-20 px-3 text-center sm:min-w-24 sm:px-5">
      <p className={`font-mono text-xl font-medium ${tone}`}>{value}</p>
      <p className="mt-1 text-[0.68rem] leading-tight text-muted-foreground">{label}</p>
    </div>
  );
}

function DecisionPanel({
  title,
  required,
  placeholder,
  reason,
  onChange,
  pending,
  submitLabel,
  onSubmit,
  onCancel,
}: {
  title: string;
  required: boolean;
  placeholder: string;
  reason: string;
  onChange: (value: string) => void;
  pending: boolean;
  submitLabel: string;
  onSubmit: () => void;
  onCancel: () => void;
}) {
  const canSubmit = !required || reason.trim().length > 0;
  return (
    <div className="mt-6 max-w-2xl border border-border bg-card p-5">
      <label htmlFor="reason" className="mb-2 block text-sm font-medium">
        {title} {required && <span className="text-nomatch">*</span>}
      </label>
      <textarea
        id="reason"
        rows={4}
        value={reason}
        onChange={(e) => onChange(e.target.value)}
        className="w-full border border-input bg-background px-3 py-2.5 text-sm outline-none focus:border-primary focus:ring-2 focus:ring-ring/30"
        placeholder={placeholder}
      />
      <div className="mt-4 flex gap-3">
        <button
          disabled={!canSubmit || pending}
          onClick={onSubmit}
          className="bg-primary px-5 py-2.5 text-sm font-medium text-primary-foreground transition-colors hover:bg-structure disabled:cursor-not-allowed disabled:bg-muted disabled:text-muted-foreground"
        >
          {submitLabel}
        </button>
        <button
          onClick={onCancel}
          className="px-3 py-2.5 text-sm text-muted-foreground hover:text-foreground"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}