"use client";

import { useState } from "react";
import { OutcomeBadge, RouteClassBadge } from "./Badge";
import type { HealEvent } from "../types";

function formatTime(ts: string) {
  return new Date(ts).toLocaleTimeString();
}

function JsonBlock({ label, value }: { label: string; value: unknown }) {
  if (value === null || value === undefined) {
    return (
      <div>
        <div className="text-[11px] uppercase tracking-wide text-neutral-500 mb-1">{label}</div>
        <div className="text-xs text-neutral-600 font-mono">none</div>
      </div>
    );
  }
  return (
    <div>
      <div className="text-[11px] uppercase tracking-wide text-neutral-500 mb-1">{label}</div>
      <pre className="text-xs font-mono text-neutral-300 bg-neutral-950 border border-neutral-800 rounded-md p-2 overflow-x-auto">
        {JSON.stringify(value, null, 2)}
      </pre>
    </div>
  );
}

function EventRow({ event }: { event: HealEvent }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="border-b border-neutral-800 last:border-b-0">
      <button
        onClick={() => setExpanded((e) => !e)}
        className="w-full flex flex-wrap items-center gap-3 px-4 py-2.5 text-left hover:bg-neutral-900/60 transition-colors"
      >
        <span className="text-xs text-neutral-500 font-mono w-20 shrink-0">
          {formatTime(event.timestamp)}
        </span>
        <OutcomeBadge outcome={event.outcome} />
        <RouteClassBadge routeClass={event.route_class} />
        <span className="font-mono text-sm text-neutral-200 truncate flex-1 min-w-32">
          {event.route}
        </span>
        {event.diagnosis && (
          <span className="text-xs text-neutral-500 font-mono hidden sm:inline">
            {event.diagnosis.drift_type} @ {event.diagnosis.confidence.toFixed(2)}
          </span>
        )}
        <span className="text-xs text-neutral-600 font-mono hidden md:inline">
          {event.trace_id.slice(0, 8)}
        </span>
        <span className="text-neutral-600 text-xs">{expanded ? "−" : "+"}</span>
      </button>

      {expanded && (
        <div className="px-4 pb-4 pt-1 space-y-3 bg-neutral-950/40">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <JsonBlock label="Original payload" value={event.original_payload} />
            <JsonBlock label="Healed payload" value={event.healed_payload} />
          </div>
          {event.diagnosis && (
            <JsonBlock label="Gemini diagnosis" value={event.diagnosis} />
          )}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
            <div>
              <div className="text-[11px] uppercase tracking-wide text-neutral-500 mb-1">
                Call stack
              </div>
              <div className="font-mono text-neutral-300">
                {event.call_stack.join(" → ") || "(empty)"}
              </div>
            </div>
            <div>
              <div className="text-[11px] uppercase tracking-wide text-neutral-500 mb-1">
                Signature (HMAC-SHA256)
              </div>
              <div className="font-mono text-neutral-500 break-all">
                {event.signature ?? "none"}
              </div>
            </div>
          </div>
          <div className="text-[11px] text-neutral-600 font-mono">
            trace_id: {event.trace_id} &middot; heal_count: {event.heal_count}
          </div>
        </div>
      )}
    </div>
  );
}

export function EventFeed({ events }: { events: HealEvent[] }) {
  if (events.length === 0) {
    return (
      <div className="rounded-lg border border-neutral-800 bg-neutral-900/50 px-5 py-6 text-sm text-neutral-500">
        No events yet. Send a request through <span className="font-mono">/proxy/...</span> to see
        one land here.
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-neutral-800 bg-neutral-900/50 overflow-hidden">
      {events.map((event, i) => (
        <EventRow key={`${event.trace_id}-${i}`} event={event} />
      ))}
    </div>
  );
}
