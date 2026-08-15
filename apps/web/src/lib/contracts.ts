export type InvestigationStatus =
  | "INITIALIZED"
  | "PREPARING"
  | "SEARCHING"
  | "VETTING_MANDATORY"
  | "SELECTING_ADAPTIVE_EXPERIMENT"
  | "WAITING_FOR_CRITIC"
  | "RUNNING_TOOL"
  | "UPDATING_EVIDENCE"
  | "READY_TO_LOCK"
  | "RESULT_LOCKED"
  | "REVEALED"
  | "INSUFFICIENT_EVIDENCE"
  | "REJECTED"
  | "FAILED"
  | "BUDGET_EXHAUSTED";

export type LockState = "GROUND_TRUTH_LOCKED" | "RESULT_LOCKED" | "CATALOG_REVEALED";

export interface InvestigationView {
  run_id: string;
  opaque_target_id: string;
  status: InvestigationStatus;
  lock_state: LockState;
  disposition: string | null;
  evidence_refs: string[];
  completed_tests: string[];
  available_tests: string[];
  terminal_reason: string | null;
}

export interface InvestigationEvent {
  event_id: string;
  run_id: string;
  step_id: string;
  action_id: string;
  sequence: number;
  timestamp: string;
  type: string;
  payload: Record<string, unknown>;
  schema_version: "1";
}
