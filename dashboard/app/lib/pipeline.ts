import type { HealEvent } from "../types";

export type StepStatus = "pass" | "fail" | "skip";

export interface PipelineStep {
  id: string;
  label: string;
  status: StepStatus;
  detail: string;
}

const REASON_DETAIL: Record<string, string> = {
  circuit_open_precheck: "circuit already OPEN for this route -- fail fast, no dispatch attempted",
  transactional_short_circuit: "transactional routes get exactly one behaviour on failure",
  loop_detected: "fallback target already in the call stack -- would cycle forever",
  budget_exhausted_transaction: "per-transaction heal limit reached for this request",
  budget_exhausted_window: "rolling-window heal budget exhausted for this route",
  transport_failure_no_diagnosis: "no 200 payload to diagnose -- only a real error to show",
  gemini_unavailable: "timeout, API error, or a response that failed its own schema check",
  gemini_declined: "confidence too low, drift unrecoverable, or model recommended fail_loud",
  heal_executor_missing_source: "field_mapping pointed at a key that wasn't in the payload",
  validation_gate_blocked: "the remapped payload still didn't satisfy the expected schema",
  no_expected_schema: "no schema registered for this route -- can't diagnose or heal",
};

/**
 * Reconstructs which stages of the request pipeline a given event passed
 * through, and where (if anywhere) it stopped. Mirrors the actual branch
 * structure in app/heal_pipeline.py -- kept here rather than served by the
 * API since it's purely a presentation concern over data the event already
 * carries in full.
 */
export function getPipelineSteps(event: HealEvent): PipelineStep[] {
  const steps: PipelineStep[] = [];
  const isTransactional = event.route_class === "TRANSACTIONAL";
  const reason = event.failure_reason;

  steps.push({
    id: "classify",
    label: "Route Classifier",
    status: "pass",
    detail: `classified ${event.route_class}`,
  });

  if (reason === "circuit_open_precheck") {
    steps.push({
      id: "circuit",
      label: "Circuit Check",
      status: "fail",
      detail: REASON_DETAIL[reason],
    });
    steps.push({ id: "response", label: "Response", status: "fail", detail: "503, fail-fast" });
    return steps;
  }
  steps.push({ id: "circuit", label: "Circuit Check", status: "pass", detail: "circuit CLOSED or HALF_OPEN, request allowed" });

  steps.push({
    id: "dispatch",
    label: "Upstream Dispatch",
    status: event.is_transport_failure ? "fail" : "pass",
    detail: event.is_transport_failure
      ? "upstream returned an error (5xx / timeout / connection failure)"
      : "upstream responded 200 OK",
  });

  if (isTransactional) {
    steps.push({
      id: "shortcircuit",
      label: "Transactional Short-Circuit",
      status: event.outcome === "healed" ? "skip" : "fail",
      detail:
        event.outcome === "healed"
          ? "n/a -- clean pass, no failure to short-circuit"
          : REASON_DETAIL.transactional_short_circuit,
    });
    for (const id of ["loop", "budget", "gemini", "executor", "gate"]) {
      steps.push({ id, label: skipLabel(id), status: "skip", detail: "never entered -- write paths never heal" });
    }
    steps.push({
      id: "response",
      label: "Response",
      status: event.outcome === "healed" ? "pass" : "fail",
      detail: event.outcome === "healed" ? "200, clean" : "propagated the real upstream error",
    });
    return steps;
  }

  if (event.is_transport_failure) {
    steps.push({ id: "schema", label: "Schema Validation", status: "skip", detail: "n/a -- no 200 body to validate" });
  } else {
    steps.push({
      id: "schema",
      label: "Schema Validation",
      status: "fail",
      detail: "response diverged from the expected schema",
    });
  }

  steps.push({
    id: "loop",
    label: "Loop Detector",
    status: reason === "loop_detected" ? "fail" : "pass",
    detail: reason === "loop_detected" ? REASON_DETAIL.loop_detected : "fallback target not seen before in this transaction",
  });
  if (reason === "loop_detected") {
    steps.push({ id: "budget", label: skipLabel("budget"), status: "skip", detail: "never reached" });
    steps.push({ id: "gemini", label: skipLabel("gemini"), status: "skip", detail: "never reached" });
    steps.push({ id: "executor", label: skipLabel("executor"), status: "skip", detail: "never reached" });
    steps.push({ id: "gate", label: skipLabel("gate"), status: "skip", detail: "never reached" });
    steps.push({ id: "response", label: "Response", status: "fail", detail: "fails loud, retry suppressed" });
    return steps;
  }

  const budgetFailed = reason === "budget_exhausted_transaction" || reason === "budget_exhausted_window";
  steps.push({
    id: "budget",
    label: "Budget Check",
    status: budgetFailed ? "fail" : "pass",
    detail: budgetFailed ? REASON_DETAIL[reason as string] : "within per-transaction and rolling-window limits",
  });
  if (budgetFailed) {
    steps.push({ id: "gemini", label: skipLabel("gemini"), status: "skip", detail: "never reached" });
    steps.push({ id: "executor", label: skipLabel("executor"), status: "skip", detail: "never reached" });
    steps.push({ id: "gate", label: skipLabel("gate"), status: "skip", detail: "never reached" });
    steps.push({ id: "response", label: "Response", status: "fail", detail: "circuit tripped, fails loud" });
    return steps;
  }

  if (event.is_transport_failure) {
    // Real upstream error, no fallback target -- diagnosis never attempted.
    steps.push({ id: "gemini", label: skipLabel("gemini"), status: "skip", detail: "no payload shape to diagnose" });
    steps.push({ id: "executor", label: skipLabel("executor"), status: "skip", detail: "never reached" });
    steps.push({ id: "gate", label: skipLabel("gate"), status: "skip", detail: "never reached" });
    steps.push({ id: "response", label: "Response", status: "fail", detail: "propagated the real upstream error" });
    return steps;
  }

  const geminiFailed = reason === "gemini_unavailable" || reason === "gemini_declined" || reason === "no_expected_schema";
  steps.push({
    id: "gemini",
    label: "Gemini Diagnosis",
    status: reason === "no_expected_schema" ? "skip" : geminiFailed ? "fail" : "pass",
    detail:
      reason === "no_expected_schema"
        ? REASON_DETAIL.no_expected_schema
        : geminiFailed
          ? REASON_DETAIL[reason as string]
          : event.diagnosis
            ? `${event.diagnosis.drift_type}, confidence ${event.diagnosis.confidence.toFixed(2)}, recommended heal`
            : "diagnosis authorised a heal",
  });
  if (geminiFailed) {
    steps.push({ id: "executor", label: skipLabel("executor"), status: "skip", detail: "never reached" });
    steps.push({ id: "gate", label: skipLabel("gate"), status: "skip", detail: "never reached" });
    steps.push({ id: "response", label: "Response", status: "fail", detail: "fails loud -- never heal blind" });
    return steps;
  }

  const executorFailed = reason === "heal_executor_missing_source";
  steps.push({
    id: "executor",
    label: "Heal Executor",
    status: executorFailed ? "fail" : "pass",
    detail: executorFailed ? REASON_DETAIL.heal_executor_missing_source : "pure field remap applied, no values invented",
  });
  if (executorFailed) {
    steps.push({ id: "gate", label: skipLabel("gate"), status: "skip", detail: "never reached" });
    steps.push({ id: "response", label: "Response", status: "fail", detail: "fails loud -- couldn't remap" });
    return steps;
  }

  const gateFailed = reason === "validation_gate_blocked";
  steps.push({
    id: "gate",
    label: "Validation Gate",
    status: gateFailed ? "fail" : "pass",
    detail: gateFailed ? REASON_DETAIL.validation_gate_blocked : "healed payload satisfies the expected schema",
  });
  steps.push({
    id: "response",
    label: "Response",
    status: gateFailed ? "fail" : "pass",
    detail: gateFailed ? "dropped, fails loud regardless of what the model recommended" : "200, healed + disclosed",
  });

  return steps;
}

function skipLabel(id: string): string {
  const labels: Record<string, string> = {
    loop: "Loop Detector",
    budget: "Budget Check",
    gemini: "Gemini Diagnosis",
    executor: "Heal Executor",
    gate: "Validation Gate",
  };
  return labels[id] ?? id;
}
