import type { RuleResult, RuleStatus } from "@/lib/api";
import { STATUS_LABEL } from "@/lib/api";

const statusStyles: Record<RuleStatus, { badge: string; evidence: string; card: string }> = {
  matches: {
    badge: "border-match/40 text-match bg-match/8",
    evidence: "evidence evidence-match",
    card: "border-match/35 hover:border-l-match",
  },
  does_not_match: {
    badge: "border-nomatch/40 text-nomatch bg-nomatch/8",
    evidence: "evidence evidence-nomatch",
    card: "border-nomatch/35 hover:border-l-nomatch",
  },
  unclear: {
    badge: "border-unclear/60 text-unclear bg-unclear/12",
    evidence: "evidence evidence-unclear",
    card: "border-unclear/60 border-l-unclear bg-unclear/5 hover:border-l-unclear",
  },
};

export function RuleCard({ rule }: { rule: RuleResult }) {
  const s = statusStyles[rule.status];
  return (
    <article className={`group rounded-lg border border-l-4 bg-card p-6 shadow-card transition-[box-shadow,border-color,transform] duration-200 hover:-translate-y-0.5 hover:shadow-card-hover ${s.card}`}>
      <div className="grid grid-cols-[minmax(0,1fr)_auto] items-start gap-3">
        <div className="min-w-0">
          <span className="font-mono text-xs tracking-wide text-muted-foreground">{rule.rule_id}</span>
          <p className="mt-1 text-[0.95rem] leading-relaxed text-foreground">{rule.rule_text}</p>
        </div>
        <span
          className={`shrink-0 border px-2.5 py-1 font-mono text-[0.7rem] uppercase tracking-widest ${s.badge}`}
        >
          {STATUS_LABEL[rule.status]}
        </span>
      </div>

      <div className="mt-4">
        <div className={s.evidence}>
          {rule.evidence}
        </div>
      </div>
    </article>
  );
}