import type { CircuitState, Outcome, RouteClass } from "../types";

const base =
  "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium tracking-wide whitespace-nowrap";

// A heal is deliberately NOT colored green. Green reads as "all good, ignore
// me" -- the exact instinct this product exists to override. Healed gets the
// same attention-grabbing amber as an alert, because that's what it is.
const outcomeStyles: Record<Outcome, string> = {
  healed: "bg-amber-500/15 text-amber-300 ring-1 ring-amber-500/40",
  failed_loud: "bg-rose-500/15 text-rose-300 ring-1 ring-rose-500/40",
  loop_suppressed: "bg-violet-500/15 text-violet-300 ring-1 ring-violet-500/40",
  budget_exhausted: "bg-red-600/20 text-red-300 ring-1 ring-red-600/50",
};

const outcomeLabels: Record<Outcome, string> = {
  healed: "HEALED",
  failed_loud: "FAILED LOUD",
  loop_suppressed: "LOOP SUPPRESSED",
  budget_exhausted: "BUDGET EXHAUSTED",
};

export function OutcomeBadge({ outcome }: { outcome: Outcome }) {
  return <span className={`${base} ${outcomeStyles[outcome]}`}>{outcomeLabels[outcome]}</span>;
}

const routeClassStyles: Record<RouteClass, string> = {
  TRANSACTIONAL: "bg-neutral-100/10 text-neutral-100 ring-1 ring-neutral-100/30 font-semibold",
  INFORMATIONAL: "bg-neutral-500/10 text-neutral-400 ring-1 ring-neutral-500/30",
};

export function RouteClassBadge({ routeClass }: { routeClass: RouteClass }) {
  return <span className={`${base} ${routeClassStyles[routeClass]}`}>{routeClass}</span>;
}

const circuitStyles: Record<CircuitState, string> = {
  CLOSED: "bg-emerald-500/15 text-emerald-300 ring-1 ring-emerald-500/40",
  HALF_OPEN: "bg-amber-500/15 text-amber-300 ring-1 ring-amber-500/40",
  OPEN: "bg-rose-500/15 text-rose-300 ring-1 ring-rose-500/40",
};

export function CircuitBadge({ state }: { state: CircuitState }) {
  return <span className={`${base} ${circuitStyles[state]}`}>{state}</span>;
}
