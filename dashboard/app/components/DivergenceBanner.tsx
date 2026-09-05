import type { HealEvent } from "../types";

function formatTime(ts: string) {
  return new Date(ts).toLocaleTimeString();
}

export function DivergenceBanner({
  event,
  isNew,
}: {
  event: HealEvent | null;
  isNew: boolean;
}) {
  if (!event) {
    return (
      <div className="rounded-lg border border-neutral-800 bg-neutral-900/50 px-5 py-4 text-sm text-neutral-500">
        No divergence alerts yet. A heal shows up here the instant it happens
        -- the caller sees <span className="font-mono text-neutral-400">200</span>, this is what ops sees.
      </div>
    );
  }

  return (
    <div
      key={event.trace_id}
      className={`rounded-lg border border-amber-500/40 bg-amber-500/5 px-5 py-4 ${
        isNew ? "flash-once" : ""
      }`}
    >
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div className="flex items-center gap-2">
          <span className="relative flex h-2.5 w-2.5">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75" />
            <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-amber-400" />
          </span>
          <span className="text-sm font-semibold text-amber-300 tracking-wide">
            DIVERGENCE ALERT -- caller received 200, this was healed
          </span>
        </div>
        <span className="text-xs text-neutral-500 font-mono">{formatTime(event.timestamp)}</span>
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-x-6 gap-y-1 text-sm">
        <span className="text-neutral-300">
          route <span className="font-mono text-neutral-100">{event.route}</span>
        </span>
        {event.diagnosis && (
          <>
            <span className="text-neutral-300">
              drift <span className="font-mono text-neutral-100">{event.diagnosis.drift_type}</span>
            </span>
            <span className="text-neutral-300">
              confidence{" "}
              <span className="font-mono text-neutral-100">
                {event.diagnosis.confidence.toFixed(2)}
              </span>
            </span>
          </>
        )}
        <span className="text-neutral-500 font-mono text-xs">{event.trace_id}</span>
      </div>
    </div>
  );
}
