export type RouteClass = "TRANSACTIONAL" | "INFORMATIONAL";

export type Outcome = "healed" | "failed_loud" | "loop_suppressed" | "budget_exhausted";

export type FailureReason =
  | "circuit_open_precheck"
  | "transactional_short_circuit"
  | "loop_detected"
  | "budget_exhausted_transaction"
  | "budget_exhausted_window"
  | "transport_failure_no_diagnosis"
  | "gemini_unavailable"
  | "gemini_declined"
  | "heal_executor_missing_source"
  | "validation_gate_blocked"
  | "no_expected_schema";

export type DriftType =
  | "field_rename"
  | "type_change"
  | "nesting_change"
  | "missing_field"
  | "unrecoverable";

export interface DriftDiagnosis {
  drift_type: DriftType;
  recommendation: "heal" | "fail_loud";
  confidence: number;
  field_mapping: Record<string, string>;
  reasoning: string;
}

export interface HealEvent {
  trace_id: string;
  timestamp: string;
  route: string;
  route_class: RouteClass;
  outcome: Outcome;
  failure_reason: FailureReason | null;
  is_transport_failure: boolean;
  original_payload: Record<string, unknown> | unknown[] | null;
  healed_payload: Record<string, unknown> | null;
  diagnosis: DriftDiagnosis | null;
  call_stack: string[];
  heal_count: number;
  signature: string | null;
}

export type CircuitState = "CLOSED" | "OPEN" | "HALF_OPEN";

export interface RouteCircuitSnapshot {
  state: CircuitState;
  heals_in_window: number;
}

export interface BudgetConfig {
  max_heals_per_transaction: number;
  rolling_window_seconds: number;
  rolling_window_max_heals: number;
  circuit_cooldown_seconds: number;
}

export interface HealthResponse {
  status: string;
  service: string;
  circuits: Record<string, RouteCircuitSnapshot>;
  budget_config?: BudgetConfig;
}
