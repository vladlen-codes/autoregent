"use client";

import { useEffect, useRef, useState } from "react";
import { CircuitGrid } from "./components/CircuitGrid";
import { DivergenceBanner } from "./components/DivergenceBanner";
import { EventFeed } from "./components/EventFeed";
import type { HealEvent, HealthResponse } from "./types";

const DEFAULT_API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "https://autoregent-production.up.railway.app";

const POLL_INTERVAL_MS = 4000;

function useApiBaseUrl() {
  const [url, setUrl] = useState(DEFAULT_API_BASE_URL);

  useEffect(() => {
    // localStorage doesn't exist during the static-export prerender, so this
    // must be a post-mount effect -- the brief flash to a stored override is
    // the intended behavior, not an avoidable extra render.
    const stored = window.localStorage.getItem("autoregent-api-base-url");
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (stored) setUrl(stored);
  }, []);

  const update = (next: string) => {
    const trimmed = next.trim().replace(/\/$/, "");
    setUrl(trimmed);
    window.localStorage.setItem("autoregent-api-base-url", trimmed);
  };

  return [url, update] as const;
}

export default function DashboardPage() {
  const [apiBaseUrl, setApiBaseUrl] = useApiBaseUrl();
  const [urlDraft, setUrlDraft] = useState(apiBaseUrl);
  // Keep the input in sync when apiBaseUrl loads from localStorage post-mount,
  // without an effect -- adjusting state during render per React's guidance.
  const [syncedApiBaseUrl, setSyncedApiBaseUrl] = useState(apiBaseUrl);
  if (apiBaseUrl !== syncedApiBaseUrl) {
    setSyncedApiBaseUrl(apiBaseUrl);
    setUrlDraft(apiBaseUrl);
  }

  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [events, setEvents] = useState<HealEvent[]>([]);
  const [status, setStatus] = useState<"connecting" | "ok" | "error">("connecting");
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const [latestHealed, setLatestHealed] = useState<HealEvent | null>(null);
  const [isNewHeal, setIsNewHeal] = useState(false);
  const previousHealedTraceId = useRef<string | null>(null);
  const hasLoadedOnce = useRef(false);

  useEffect(() => {
    let cancelled = false;

    async function poll() {
      try {
        const [healthRes, eventsRes] = await Promise.all([
          fetch(`${apiBaseUrl}/health`, { cache: "no-store" }),
          fetch(`${apiBaseUrl}/events`, { cache: "no-store" }),
        ]);
        if (!healthRes.ok || !eventsRes.ok) throw new Error("non-200 response");

        const healthData: HealthResponse = await healthRes.json();
        const eventsData: HealEvent[] = await eventsRes.json();
        if (cancelled) return;

        setHealth(healthData);
        setEvents(eventsData);
        setStatus("ok");
        setLastUpdated(new Date());

        const healedEvents = eventsData.filter((e) => e.outcome === "healed");
        const newest = healedEvents.length > 0 ? healedEvents[healedEvents.length - 1] : null;
        if (newest) {
          const changed =
            previousHealedTraceId.current !== null &&
            previousHealedTraceId.current !== newest.trace_id;
          setIsNewHeal(hasLoadedOnce.current && changed);
          previousHealedTraceId.current = newest.trace_id;
          setLatestHealed(newest);
        }
        hasLoadedOnce.current = true;
      } catch {
        if (!cancelled) setStatus("error");
      }
    }

    poll();
    const id = setInterval(poll, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [apiBaseUrl]);

  const reversedEvents = [...events].reverse();

  return (
    <div className="max-w-5xl mx-auto w-full px-4 sm:px-6 py-8 flex flex-col gap-6">
      <header className="flex flex-col gap-3">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div>
            <h1 className="text-xl font-semibold tracking-tight">Autoregent</h1>
            <p className="text-sm text-neutral-500">
              Every heal is a disclosure event, not a success.
            </p>
          </div>
          <div className="flex items-center gap-2 text-xs text-neutral-500">
            <span
              className={`inline-block h-2 w-2 rounded-full ${
                status === "ok"
                  ? "bg-emerald-500"
                  : status === "error"
                    ? "bg-rose-500"
                    : "bg-amber-500 animate-pulse"
              }`}
            />
            <span>
              {status === "ok" && lastUpdated
                ? `updated ${lastUpdated.toLocaleTimeString()}`
                : status === "error"
                  ? "connection failed"
                  : "connecting..."}
            </span>
          </div>
        </div>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            setApiBaseUrl(urlDraft);
          }}
          className="flex items-center gap-2"
        >
          <label className="text-xs text-neutral-500 shrink-0">Gateway URL</label>
          <input
            value={urlDraft}
            onChange={(e) => setUrlDraft(e.target.value)}
            className="flex-1 min-w-0 rounded-md border border-neutral-800 bg-neutral-900 px-2.5 py-1 text-xs font-mono text-neutral-300 focus:outline-none focus:border-neutral-600"
            spellCheck={false}
          />
          <button
            type="submit"
            className="rounded-md border border-neutral-800 bg-neutral-900 px-2.5 py-1 text-xs text-neutral-300 hover:bg-neutral-800 transition-colors shrink-0"
          >
            Set
          </button>
        </form>
      </header>

      <section className="flex flex-col gap-2">
        <h2 className="text-xs uppercase tracking-wide text-neutral-500">Divergence alert</h2>
        <DivergenceBanner event={latestHealed} isNew={isNewHeal} />
      </section>

      <section className="flex flex-col gap-2">
        <h2 className="text-xs uppercase tracking-wide text-neutral-500">Circuit state / budget burn</h2>
        <CircuitGrid circuits={health?.circuits ?? {}} budgetConfig={health?.budget_config} />
      </section>

      <section className="flex flex-col gap-2">
        <div className="flex items-center justify-between">
          <h2 className="text-xs uppercase tracking-wide text-neutral-500">
            Event log ({events.length})
          </h2>
        </div>
        <EventFeed events={reversedEvents} />
      </section>

      <footer className="text-xs text-neutral-600 text-center pt-4 pb-2">
        In-memory event store -- restart of the gateway clears history. v0.1.
      </footer>
    </div>
  );
}
