import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { listTrials, type TrialRule } from "@/lib/api";

export const Route = createFileRoute("/trials")({
  head: () => ({
    meta: [
      { title: "Trials — Registered Protocols | CareMatch" },
      {
        name: "description",
        content:
          "Browse the clinical trial protocols registered in CareMatch and their inclusion and exclusion criteria.",
      },
      { property: "og:title", content: "Trials — CareMatch" },
      {
        property: "og:description",
        content: "Browse registered trial protocols and their eligibility criteria.",
      },
    ],
  }),
  component: Trials,
});

const CATEGORY_LABEL: Record<TrialRule["category"], string> = {
  inclusion: "Inclusion",
  exclusion: "Exclusion",
};

function Trials() {
  const trialsQuery = useQuery({
    queryKey: ["trials"],
    queryFn: listTrials,
  });

  const [expanded, setExpanded] = useState<string | null>(null);

  return (
    <div className="mx-auto max-w-4xl px-6 py-12">
      <h1 className="text-3xl">Trials</h1>
      <p className="mt-3 max-w-xl text-sm leading-relaxed text-muted-foreground">
        Every registered protocol, with its inclusion and exclusion criteria. Start an eligibility
        review on the New Assessment page.
      </p>

      {trialsQuery.isLoading && (
        <p className="mt-8 text-sm text-muted-foreground">Loading trials…</p>
      )}

      {trialsQuery.isError && (
        <p className="mt-8 border border-nomatch/40 bg-nomatch/8 p-4 text-sm text-nomatch">
          Couldn't reach the API to load trials. Is the backend running at the expected address?
        </p>
      )}

      {trialsQuery.data && trialsQuery.data.length === 0 && (
        <div className="mt-8 border border-border bg-card p-7">
          <p className="text-sm text-muted-foreground">No trials are registered yet.</p>
          <Link
            to="/trial-setup"
            className="mt-4 inline-block bg-primary px-5 py-2.5 text-sm font-medium text-primary-foreground transition-colors hover:bg-structure"
          >
            Set up a trial
          </Link>
        </div>
      )}

      <div className="mt-8 space-y-6">
        {trialsQuery.data?.map((t) => {
          const isOpen = expanded === t.trial_id;
          const inclusionCount = t.rules.filter((r) => r.category === "inclusion").length;
          const exclusionCount = t.rules.filter((r) => r.category === "exclusion").length;
          return (
            <div key={t.trial_id} className="border border-border bg-card p-6">
              <button
                onClick={() => setExpanded(isOpen ? null : t.trial_id)}
                className="grid w-full grid-cols-[minmax(0,1fr)_auto] items-center gap-4 text-left"
              >
                <div>
                  <h2 className="text-xl text-structure">{t.trial_name}</h2>
                  <p className="mt-1 font-mono text-xs text-muted-foreground">{t.trial_id}</p>
                </div>
                <div className="text-right">
                  <p className="text-xs text-muted-foreground">
                    {inclusionCount} inclusion · {exclusionCount} exclusion
                  </p>
                  <p className="mt-1 font-mono text-xs text-structure">{isOpen ? "▲" : "▼"}</p>
                </div>
              </button>

              {isOpen && (
                <div className="mt-5 space-y-4 border-t border-border pt-5">
                  {t.rules.length === 0 && (
                    <p className="text-sm text-muted-foreground">
                      No criteria defined for this trial yet.
                    </p>
                  )}
                  <div>
                    <p className="mb-2 font-mono text-[0.68rem] uppercase tracking-widest text-muted-foreground">
                      Inclusion
                    </p>
                    <div className="space-y-2">
                      {t.rules
                        .filter((r) => r.category === "inclusion")
                        .map((r) => (
                          <RuleLine key={r.rule_id} rule={r} />
                        ))}
                    </div>
                  </div>
                  <div>
                    <p className="mb-2 font-mono text-[0.68rem] uppercase tracking-widest text-muted-foreground">
                      Exclusion
                    </p>
                    <div className="space-y-2">
                      {t.rules
                        .filter((r) => r.category === "exclusion")
                        .map((r) => (
                          <RuleLine key={r.rule_id} rule={r} />
                        ))}
                    </div>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function RuleLine({ rule }: { rule: TrialRule }) {
  return (
    <div className="grid grid-cols-[6rem_minmax(0,1fr)] items-baseline gap-3 border border-border/60 bg-background px-4 py-2.5">
      <span
        className={`font-mono text-[0.68rem] uppercase tracking-widest ${
          rule.category === "inclusion" ? "text-match" : "text-nomatch"
        }`}
      >
        {CATEGORY_LABEL[rule.category]}
      </span>
      <div>
        <p className="font-mono text-xs text-muted-foreground">{rule.rule_id}</p>
        <p className="mt-1 text-sm leading-relaxed text-structure">{rule.rule_text}</p>
      </div>
    </div>
  );
}
