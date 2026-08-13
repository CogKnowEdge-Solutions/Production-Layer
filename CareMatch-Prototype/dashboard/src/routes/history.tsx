import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import {
  ApiError,
  decisionDisplayLabel,
  deleteAssessment,
  listAssessments,
  SUGGESTED_STATUS_LABEL,
  type AssessmentSummary,
} from "@/lib/api";

export const Route = createFileRoute("/history")({
  head: () => ({
    meta: [
      { title: "Assessment History — Every Assessment | CareMatch" },
      {
        name: "description",
        content:
          "Every eligibility assessment CareMatch has ever run, newest first, with each AI suggestion and the coordinator's decision.",
      },
      { property: "og:title", content: "Assessment History — CareMatch" },
      {
        property: "og:description",
        content: "Browse every assessment run in CareMatch and its decision state.",
      },
    ],
  }),
  component: History,
});

function decisionTone(decision: string | null): string {
  if (decision === "accepted") return "text-match";
  if (decision === "denied") return "text-nomatch";
  if (decision === "needs_more_review") return "text-unclear";
  return "text-muted-foreground";
}

function History() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const assessmentsQuery = useQuery({
    queryKey: ["assessments"],
    queryFn: listAssessments,
  });

  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  async function handleDelete(row: AssessmentSummary) {
    // Honest by design: deleting an assessment permanently removes real
    // audit evidence. This confirmation is deliberately explicit -- it
    // should never be possible to trigger with a single accidental click.
    const confirmed = window.confirm(
      `Delete this assessment for ${row.patient_id} (${row.assessment_id})? ` +
        "This permanently removes the record, its evidence, and any recorded " +
        "decision. This cannot be undone.",
    );
    if (!confirmed) return;
    setDeletingId(row.assessment_id);
    setDeleteError(null);
    try {
      await deleteAssessment(row.assessment_id);
      queryClient.invalidateQueries({ queryKey: ["assessments"] });
    } catch (err) {
      const message =
        err instanceof ApiError
          ? err.message
          : "Couldn't delete this assessment. Please try again.";
      setDeleteError(message);
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <div className="mx-auto max-w-5xl px-6 py-12">
      <h1 className="text-3xl">Assessment History</h1>
      <p className="mt-3 max-w-2xl text-sm leading-relaxed text-muted-foreground">
        Every assessment CareMatch has ever run, newest first. Click any row to open that
        assessment's full evidence and decision in the Assessment Review page.
      </p>

      {assessmentsQuery.isLoading && (
        <p className="mt-8 text-sm text-muted-foreground">Loading assessment history…</p>
      )}

      {assessmentsQuery.isError && (
        <p className="mt-8 border border-nomatch/40 bg-nomatch/8 p-4 text-sm text-nomatch">
          Couldn't reach the API to load assessment history. Is the backend running at the expected
          address?
        </p>
      )}

      {assessmentsQuery.data && assessmentsQuery.data.length === 0 && (
        <div className="mt-8 border border-border bg-card p-7">
          <p className="text-sm text-muted-foreground">No assessments have been run yet.</p>
          <Link
            to="/"
            className="mt-4 inline-block bg-primary px-5 py-2.5 text-sm font-medium text-primary-foreground transition-colors hover:bg-structure"
          >
            Run the first assessment
          </Link>
        </div>
      )}

      {assessmentsQuery.data && assessmentsQuery.data.length > 0 && (
        <div className="mt-8 overflow-x-auto border border-border bg-card">
          {deleteError && (
            <p className="border-b border-border bg-nomatch/8 px-5 py-3 text-sm text-nomatch">
              {deleteError}
            </p>
          )}
          <table className="w-full border-collapse text-left">
            <thead>
              <tr className="border-b border-border bg-secondary/60 font-mono text-[0.68rem] uppercase tracking-widest text-muted-foreground">
                <th className="px-5 py-3 font-medium">Patient</th>
                <th className="px-5 py-3 font-medium">Trial</th>
                <th className="px-5 py-3 font-medium">AI suggestion</th>
                <th className="px-5 py-3 font-medium">Decision</th>
                <th className="px-5 py-3 font-medium">Recorded</th>
                <th className="px-5 py-3 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {assessmentsQuery.data.map((a) => (
                <tr
                  key={a.assessment_id}
                  onClick={() => navigate({ to: "/review", search: { id: a.assessment_id } })}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      navigate({ to: "/review", search: { id: a.assessment_id } });
                    }
                  }}
                  tabIndex={0}
                  className="cursor-pointer transition-colors hover:bg-secondary/40 focus-visible:bg-secondary/40 focus-visible:outline-none"
                >
                  <td className="border-t border-border/60 px-5 py-4 font-mono text-sm text-structure">
                    <Link
                      to="/review"
                      search={{ id: a.assessment_id }}
                      onClick={(e) => e.stopPropagation()}
                      className="block text-structure transition-colors hover:text-primary"
                    >
                      {a.patient_id}
                    </Link>
                  </td>
                  <td className="border-t border-border/60 px-5 py-4 font-mono text-sm text-muted-foreground">
                    {a.trial_id}
                  </td>
                  <td className="border-t border-border/60 px-5 py-4 text-sm text-structure">
                    {SUGGESTED_STATUS_LABEL[a.suggested_status]}
                  </td>
                  <td className="border-t border-border/60 px-5 py-4 text-sm">
                    <span className={decisionTone(a.decision)}>{decisionDisplayLabel(a.decision)}</span>
                  </td>
                  <td className="border-t border-border/60 px-5 py-4 font-mono text-xs text-muted-foreground">
                    {a.created_at}
                  </td>
                  <td className="border-t border-border/60 px-5 py-4 text-right">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDelete(a);
                      }}
                      onKeyDown={(e) => e.stopPropagation()}
                      disabled={deletingId === a.assessment_id}
                      className="text-sm text-nomatch underline underline-offset-4 hover:text-nomatch/80 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {deletingId === a.assessment_id ? "Deleting…" : "Delete"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
