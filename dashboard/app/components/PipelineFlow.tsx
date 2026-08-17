import { getPipelineSteps, type StepStatus } from "../lib/pipeline";
import type { HealEvent } from "../types";

const nodeStyles: Record<StepStatus, string> = {
  pass: "border-emerald-500/50 bg-emerald-500/10 text-emerald-300",
  fail: "border-rose-500/60 bg-rose-500/15 text-rose-300",
  skip: "border-neutral-800 bg-neutral-900/40 text-neutral-600",
};

const dotStyles: Record<StepStatus, string> = {
  pass: "bg-emerald-400",
  fail: "bg-rose-400",
  skip: "bg-neutral-700",
};

export function PipelineFlow({ event }: { event: HealEvent }) {
  const steps = getPipelineSteps(event);

  return (
    <div>
      <div className="text-[11px] uppercase tracking-wide text-neutral-500 mb-2">
        Request pipeline
      </div>
      <div className="flex flex-wrap items-stretch gap-1.5">
        {steps.map((step, i) => (
          <div key={step.id} className="flex items-center gap-1.5">
            <div
              className={`rounded-md border px-2.5 py-1.5 min-w-32 ${nodeStyles[step.status]}`}
              title={step.detail}
            >
              <div className="flex items-center gap-1.5">
                <span className={`inline-block h-1.5 w-1.5 rounded-full shrink-0 ${dotStyles[step.status]}`} />
                <span className="text-[11px] font-medium leading-tight">{step.label}</span>
              </div>
              <div className="text-[10px] leading-tight mt-0.5 opacity-80 max-w-40">{step.detail}</div>
            </div>
            {i < steps.length - 1 && <span className="text-neutral-700 text-xs shrink-0">→</span>}
          </div>
        ))}
      </div>
    </div>
  );
}
