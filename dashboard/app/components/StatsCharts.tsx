import type { HealEvent, Outcome } from "../types";

const OUTCOME_ORDER: Outcome[] = ["healed", "failed_loud", "loop_suppressed", "budget_exhausted"];

const OUTCOME_BAR_COLOR: Record<Outcome, string> = {
  healed: "bg-amber-500",
  failed_loud: "bg-rose-500",
  loop_suppressed: "bg-violet-500",
  budget_exhausted: "bg-red-600",
};

const OUTCOME_LABEL: Record<Outcome, string> = {
  healed: "Healed",
  failed_loud: "Failed loud",
  loop_suppressed: "Loop suppressed",
  budget_exhausted: "Budget exhausted",
};

function StatTile({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-lg border border-neutral-800 bg-neutral-900/50 px-4 py-3">
      <div className="text-[11px] uppercase tracking-wide text-neutral-500">{label}</div>
      <div className="text-xl font-semibold text-neutral-100 mt-0.5">{value}</div>
      {sub && <div className="text-[11px] text-neutral-600 mt-0.5">{sub}</div>}
    </div>
  );
}

export function StatsCharts({ events }: { events: HealEvent[] }) {
  const total = events.length;
  const counts: Record<Outcome, number> = {
    healed: 0,
    failed_loud: 0,
    loop_suppressed: 0,
    budget_exhausted: 0,
  };
  for (const e of events) counts[e.outcome] += 1;

  const healedEvents = events.filter((e) => e.outcome === "healed");
  const avgConfidence =
    healedEvents.length > 0
      ? healedEvents.reduce((sum, e) => sum + (e.diagnosis?.confidence ?? 0), 0) / healedEvents.length
      : null;
  const transportFailures = events.filter((e) => e.is_transport_failure).length;

  const maxCount = Math.max(1, ...OUTCOME_ORDER.map((o) => counts[o]));

  if (total === 0) {
    return (
      <div className="rounded-lg border border-neutral-800 bg-neutral-900/50 px-5 py-6 text-sm text-neutral-500">
        No events yet -- stats fill in as the gateway handles requests.
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <StatTile label="Total requests" value={String(total)} />
        <StatTile
          label="Heal rate"
          value={`${Math.round((counts.healed / total) * 100)}%`}
          sub={`${counts.healed} of ${total}`}
        />
        <StatTile
          label="Avg. heal confidence"
          value={avgConfidence !== null ? avgConfidence.toFixed(2) : "—"}
        />
        <StatTile
          label="Transport vs. schema"
          value={`${transportFailures} / ${total - transportFailures}`}
          sub="upstream errors vs. drift"
        />
      </div>

      <div className="rounded-lg border border-neutral-800 bg-neutral-900/50 px-4 py-3">
        <div className="text-[11px] uppercase tracking-wide text-neutral-500 mb-2">
          Outcome breakdown
        </div>
        <div className="flex flex-col gap-1.5">
          {OUTCOME_ORDER.map((outcome) => (
            <div key={outcome} className="flex items-center gap-2">
              <span className="text-xs text-neutral-400 w-32 shrink-0">{OUTCOME_LABEL[outcome]}</span>
              <div className="flex-1 h-2 rounded-full bg-neutral-800 overflow-hidden">
                <div
                  className={`h-full rounded-full ${OUTCOME_BAR_COLOR[outcome]}`}
                  style={{ width: `${(counts[outcome] / maxCount) * 100}%` }}
                />
              </div>
              <span className="text-xs font-mono text-neutral-500 w-6 text-right">{counts[outcome]}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
