import { createFileRoute, Link } from "@tanstack/react-router";
import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { registerTrial, ApiError, type RuleCategory } from "@/lib/api";

export const Route = createFileRoute("/trial-setup")({
  head: () => ({
    meta: [
      { title: "Trial Setup — Define Protocol Criteria | CareMatch" },
      {
        name: "description",
        content:
          "Define a clinical trial protocol: name, identifier, and the inclusion and exclusion criteria used during eligibility review.",
      },
      { property: "og:title", content: "Trial Setup — CareMatch" },
      {
        property: "og:description",
        content: "Define trial protocols and their inclusion and exclusion criteria.",
      },
    ],
  }),
  component: TrialSetup,
});

type Row = { key: number; code: string; text: string; kind: RuleCategory };

// Real finding from testing (see reasoning_engine/protocol.py): exclusion
// criteria phrased as a NEGATED requirement ("must not be taking X")
// confuse the model into answering backwards -- it should be phrased as
// the disqualifying condition itself, stated plainly ("is currently taking
// X"). This is a heuristic warning, not a hard block -- some legitimate
// phrasing might still trip it, and it can't catch every risky pattern.
const NEGATED_PHRASING_PATTERN = /\b(must\s+not|should\s+not|shall\s+not|may\s+not|cannot|can't|do\s+not|don't)\b/i;

function isRiskyExclusionPhrasing(row: Row): boolean {
  return row.kind === "exclusion" && NEGATED_PHRASING_PATTERN.test(row.text);
}

function TrialSetup() {
  const [name, setName] = useState("");
  const [id, setId] = useState("");
  const [rows, setRows] = useState<Row[]>([
    { key: 1, code: "INC-01", text: "", kind: "inclusion" },
  ]);

  const saveMutation = useMutation({
    mutationFn: registerTrial,
  });

  const update = (key: number, patch: Partial<Row>) =>
    setRows((r) => r.map((row) => (row.key === key ? { ...row, ...patch } : row)));

  const inputCls =
    "w-full border border-input bg-background px-3 py-2 text-sm outline-none focus:border-primary focus:ring-2 focus:ring-ring/30";

  return (
    <div className="mx-auto max-w-4xl px-6 py-12">
      <h1 className="text-3xl">Trial Setup</h1>
      <p className="mt-3 max-w-xl text-sm leading-relaxed text-muted-foreground">
        Criteria are written in plain language so that each result can be quoted against the record
        verbatim.
      </p>

      <form
        className="mt-10 space-y-7 border border-border bg-card p-7"
        onSubmit={(e) => {
          e.preventDefault();
          saveMutation.mutate({
            trial_id: id.trim(),
            trial_name: name.trim(),
            rules: rows.map((r) => ({
              rule_id: r.code.trim(),
              rule_text: r.text.trim(),
              category: r.kind,
            })),
          });
        }}
      >
        <div className="grid gap-6 sm:grid-cols-2">
          <div>
            <label htmlFor="tname" className="mb-2 block text-sm font-medium">
              Trial name
            </label>
            <input id="tname" value={name} onChange={(e) => setName(e.target.value)} className={inputCls} />
          </div>
          <div>
            <label htmlFor="tid" className="mb-2 block text-sm font-medium">
              Trial ID
            </label>
            <input
              id="tid"
              value={id}
              onChange={(e) => setId(e.target.value)}
              placeholder="NCT00000000"
              className={`${inputCls} font-mono`}
            />
          </div>
        </div>

        <div>
          <div className="mb-3 flex items-baseline justify-between border-b border-border pb-2">
            <h2 className="text-lg">Criteria</h2>
            <button
              type="button"
              onClick={() =>
                setRows((r) => [
                  ...r,
                  { key: Date.now(), code: "", text: "", kind: "inclusion" },
                ])
              }
              className="text-sm text-primary underline underline-offset-4"
            >
              Add criterion
            </button>
          </div>

          <p className="mb-3 text-xs text-muted-foreground">
            Rule IDs must follow the format <span className="font-mono">INC-01</span>,{" "}
            <span className="font-mono">EXC-01</span>, etc. — two digits, matching the criterion's category.
          </p>

          <div className="mb-4 border border-unclear/50 bg-unclear/8 p-4 text-sm">
            <p className="font-medium text-foreground">Phrasing exclusion criteria</p>
            <p className="mt-1 text-muted-foreground">
              Write exclusion criteria as the disqualifying condition itself, stated plainly — not as a
              "must not" requirement. Testing showed the AI misreads negated phrasing.
            </p>
            <p className="mt-2 font-mono text-xs">
              <span className="text-nomatch">✗ Avoid:</span> "Patient must not be taking Warfarin"
              <br />
              <span className="text-match">✓ Prefer:</span> "Patient is currently taking Warfarin"
            </p>
          </div>

          <div className="space-y-3">
            {rows.map((row) => (
              <div key={row.key}>
                <div className="grid items-center gap-3 sm:grid-cols-[8rem_1fr_9rem_2rem]">
                  <input
                    aria-label="Rule ID"
                    value={row.code}
                    onChange={(e) => update(row.key, { code: e.target.value })}
                    placeholder="INC-01"
                    className={`${inputCls} font-mono text-xs`}
                  />
                  <input
                    aria-label="Rule text"
                    value={row.text}
                    onChange={(e) => update(row.key, { text: e.target.value })}
                    placeholder="Plain-language criterion"
                    className={inputCls}
                  />
                  <select
                    aria-label="Criterion type"
                    value={row.kind}
                    onChange={(e) => update(row.key, { kind: e.target.value as Row["kind"] })}
                    className={inputCls}
                  >
                    <option value="inclusion">Inclusion</option>
                    <option value="exclusion">Exclusion</option>
                  </select>
                  <button
                    type="button"
                    aria-label="Remove criterion"
                    onClick={() => setRows((r) => r.filter((x) => x.key !== row.key))}
                    className="text-sm text-muted-foreground hover:text-nomatch"
                  >
                    ×
                  </button>
                </div>
                {isRiskyExclusionPhrasing(row) && (
                  <p className="mt-1.5 text-xs text-unclear">
                    ⚠ This reads as a negated requirement. Consider rephrasing as the disqualifying
                    condition itself (e.g. "Patient is currently taking..." instead of "must not...").
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>

        {saveMutation.isError && (
          <p className="border border-nomatch/40 bg-nomatch/8 p-3 text-sm text-nomatch">
            {saveMutation.error instanceof ApiError
              ? saveMutation.error.message
              : "Couldn't save this trial. Please check the fields and try again."}
          </p>
        )}

        <div className="flex items-center gap-4 border-t border-border pt-6">
          <button
            type="submit"
            disabled={saveMutation.isPending}
            className="bg-primary px-5 py-2.5 text-sm font-medium text-primary-foreground transition-colors hover:bg-structure disabled:cursor-not-allowed disabled:opacity-60"
          >
            {saveMutation.isPending ? "Saving…" : "Save trial"}
          </button>
          {saveMutation.isSuccess && (
            <p className="text-sm text-match">
              Trial saved —{" "}
              <Link to="/" className="underline underline-offset-4">
                run an assessment against it
              </Link>
              .
            </p>
          )}
        </div>
      </form>
    </div>
  );
}
