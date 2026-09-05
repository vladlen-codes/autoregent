import { CircuitBadge } from "./Badge";
import type { BudgetConfig, RouteCircuitSnapshot } from "../types";

export function CircuitGrid({
  circuits,
  budgetConfig,
}: {
  circuits: Record<string, RouteCircuitSnapshot>;
  budgetConfig?: BudgetConfig;
}) {
  const routes = Object.keys(circuits).sort();
  const maxHeals = budgetConfig?.rolling_window_max_heals ?? 5;
  const windowSeconds = budgetConfig?.rolling_window_seconds ?? 60;

  if (routes.length === 0) {
    return (
      <div className="rounded-lg border border-neutral-800 bg-neutral-900/50 px-5 py-6 text-sm text-neutral-500">
        No routes seen yet. Circuit state appears here as soon as a request
        hits the gateway.
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
      {routes.map((route) => {
        const c = circuits[route];
        const burnPct = Math.min(100, Math.round((c.heals_in_window / maxHeals) * 100));
        return (
          <div
            key={route}
            className="rounded-lg border border-neutral-800 bg-neutral-900/50 px-4 py-3 flex flex-col gap-2"
          >
            <div className="flex items-center justify-between gap-2">
              <span className="font-mono text-sm text-neutral-200 truncate" title={route}>
                {route}
              </span>
              <CircuitBadge state={c.state} />
            </div>
            <div>
              <div className="flex justify-between text-[11px] text-neutral-500 mb-1">
                <span>heal budget ({windowSeconds}s window)</span>
                <span className="font-mono">
                  {c.heals_in_window}/{maxHeals}
                </span>
              </div>
              <div className="h-1.5 rounded-full bg-neutral-800 overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all ${
                    burnPct >= 100
                      ? "bg-rose-500"
                      : burnPct >= 60
                        ? "bg-amber-500"
                        : "bg-emerald-500"
                  }`}
                  style={{ width: `${burnPct}%` }}
                />
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
