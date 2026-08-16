export type JsonValue = string | number | boolean | null | JsonValue[] | { [key: string]: JsonValue }

export type InvestigationStatus =
  | "INITIALIZED"
  | "PREPARING"
  | "SEARCHING"
  | "VETTING_MANDATORY"
  | "SELECTING_ADAPTIVE_EXPERIMENT"
  | "WAITING_FOR_CRITIC"
  | "RUNNING_TOOL"
  | "UPDATING_EVIDENCE"
  | "FINALIZING"
  | "READY_TO_LOCK"
  | "RESULT_LOCKED"
  | "REVEALED"
  | "INSUFFICIENT_EVIDENCE"
  | "REJECTED"
  | "FAILED"
  | "BUDGET_EXHAUSTED"

export type LockState = "GROUND_TRUTH_LOCKED" | "RESULT_LOCKED" | "CATALOG_REVEALED"
export type ToolStatus =
  | "SUCCESS"
  | "NO_EVIDENCE"
  | "INDETERMINATE"
  | "PRECONDITION_FAILED"
  | "NOT_IMPLEMENTED"
  | "FAILED"
export type ToolExecutionStatus = "PREPARED" | "COMPLETED" | "FAILED"
export type AgentRole = "director" | "observer" | "signal" | "transit_hunter" | "skeptic" | "critic"
export type AgentPhase = "briefing" | "decision" | "review" | "final"
export type AgentCheckpointStatus = "COMPLETE" | "SKIPPED"
export type CriticVerdict = "APPROVE" | "REVISE" | "VETO"
export type PlotMode = "raw" | "bls" | "phase-fold" | "odd-even" | "secondary" | "harmonic"

export interface TargetOption {
  opaque_target_id: string
  cached_lightcurve_available: boolean
  cached_tpf_available: boolean
  sector?: string
  display_label?: string
}

export interface ViewerTarget {
  opaque_target_id: string
  target_name: string
  tic_id: string
  catalog_disposition: string
  catalog_source: string
  catalog_source_url: string
  known_values: Record<string, number | string>
}

export interface RunExecutionView {
  run_id: string
  status: "PAUSED" | "RUNNING" | "STOPPED" | "FAILED"
  active: boolean
  advances: number
  stop_reason: string | null
  started_at: string | null
  finished_at: string | null
}

export interface CreateInvestigationResponse {
  run_id: string
  opaque_target_id: string
  status: InvestigationStatus
  lock_state: LockState
  event_stream_url: string
  execution: RunExecutionView
}

export interface MeasurementView {
  value: number | string | boolean
  display_value: string
  unit: string | null
  uncertainty: number | null
  tolerance: number | null
  evidence_ref: string
}

export interface EvidenceView {
  evidence_id: string
  timestamp: string
  step_id: string
  action_id: string
  tool_name: string
  status: ToolStatus
  interpretation_code: string | null
  summary: string
  measurements: Record<string, MeasurementView>
  diagnostics: Record<string, string | number | boolean | null>
  method: string
  evidence_ref: string
  artifact_refs: string[]
}

export interface CandidateSignalView {
  candidate_id: string
  evidence_refs: string[]
  measurements: Record<string, MeasurementView>
}

export interface AgentCheckpointView {
  role: AgentRole
  phase: AgentPhase
  status: AgentCheckpointStatus
  decision_id: string
  context_version: string
  evidence_refs: string[]
  summary: string | null
  action: string | null
  expected_discriminator: string | null
  model_identity: string | null
  provider: string | null
  latency_ms: number | null
  schema_valid: boolean | null
  fallback_code: string | null
}

export interface SkepticDecisionView {
  decision_id: string
  step_id: string
  context_version: string
  hypothesis_under_test: string
  requested_experiment: string
  reason_code: string
  expected_discriminating_result: string
  expected_information_value: string
  priority: string
  cost_of_selected_experiment: number
  concise_reason: string
  supporting_evidence_refs: string[]
  contradicting_evidence_refs: string[]
}

export interface CriticDecisionView {
  decision_id: string
  step_id: string
  context_version: string
  skeptic_decision_id: string
  verdict: CriticVerdict
  reason_code: string
  concise_reason: string
  revised_experiment: string | null
  supporting_evidence_refs: string[]
  contradicting_evidence_refs: string[]
}

export interface ToolExecutionView {
  action_id: string
  step_id: string
  tool_name: string
  status: ToolExecutionStatus
  adaptive: boolean
  adaptive_cost_units: number
  agent_decision_id: string | null
  critic_decision_id: string | null
  result_status: ToolStatus | null
  evidence_ref: string | null
  failure_kind: string | null
  failure_reason: string | null
}

export interface FailureView {
  step_id: string
  kind: string
  concise_reason: string
  recoverable: boolean
  retry_count: number
}

export interface BudgetView {
  step_count: number
  adaptive_cost_units_used: number
  adaptive_cost_units_remaining: number
  max_adaptive_cost_units: number
  adaptive_experiments_used: number
  max_adaptive_experiments: number
  model_call_count: number
  max_model_calls: number
  tool_call_count: number
  max_tool_calls: number
  critic_revision_count: number
  max_critic_revisions: number
  model_retry_count: number
  max_model_retries: number
}

export interface InferenceRateView {
  numerator: number
  denominator: number
  rate: number | "not_applicable"
}

export interface InferenceSummaryView {
  provider: string
  model_identity: string
  agent_calls: number
  input_tokens: number | "not_measured"
  output_tokens: number | "not_measured"
  median_input_tokens: number | "not_measured"
  max_input_tokens: number | "not_measured"
  median_latency_ms: number | "not_measured"
  first_attempt_schema_valid: InferenceRateView
  repairs: InferenceRateView
  fallbacks: InferenceRateView
  provider_errors_timeouts: number
  raw_light_curve_samples_sent: 0
}

export interface LockProjection {
  state: LockState
  sha256: string | null
  locked_at: string | null
  reveal_available: boolean
}

export interface LockReceipt {
  run_id: string
  opaque_target_id: string
  sha256: string
  result_path: string
  locked_at: string
}

export interface RevealProjection {
  run_id: string
  opaque_target_id: string
  locked_result_sha256: string
  catalog_source: string
  catalog_payload: Record<string, JsonValue>
  revealed_at: string
}

export type RevealResult = RevealProjection

export interface ArtifactMetadata {
  artifact_id: string
  relative_path: string
  kind: "audit" | "science" | "authority"
  media_type: string
  size_bytes: number
  sha256: string
}

export interface ArtifactListResponse {
  run_id: string
  opaque_target_id: string
  artifacts: ArtifactMetadata[]
}

export interface InvestigationView {
  run_id: string
  opaque_target_id: string
  status: InvestigationStatus
  lock_state: LockState
  disposition: string | null
  evidence_refs: string[]
  completed_tests: string[]
  available_tests: string[]
  terminal_reason: string | null
  execution: RunExecutionView
  [key: string]: unknown
}

export interface MissionControlSnapshot {
  schema_version: "1"
  run_id: string
  opaque_target_id: string
  status: InvestigationStatus
  lock_state: LockState
  disposition: string | null
  terminal_reason: string | null
  completed_tests: string[]
  available_tests: string[]
  evidence_refs: string[]
  active_hypotheses: string[]
  strongest_unresolved_alternative: string | null
  unresolved_questions: string[]
  candidate_signals: CandidateSignalView[]
  evidence: EvidenceView[]
  accepted_decisions: SkepticDecisionView[]
  critic_decisions: CriticDecisionView[]
  role_checkpoints: AgentCheckpointView[]
  tool_executions: ToolExecutionView[]
  failures: FailureView[]
  inference_summary: InferenceSummaryView
  budgets: BudgetView
  execution: RunExecutionView
  lock: LockProjection
  reveal: RevealProjection | null
  available_plot_modes: string[]
  plot_evidence_refs: string[]
  last_sequence: number
  updated_at: string
}

export interface PlotTraceView {
  name: string
  x: number[]
  y: number[]
  kind: "line" | "markers" | "bar"
  tone: "science" | "muted" | "unresolved" | "approved"
  dash: "solid" | "dot" | "dash" | null
}

export interface PlotView {
  mode: PlotMode
  available: boolean
  unavailable_reason: string | null
  evidence_refs: string[]
  traces: PlotTraceView[]
  x_label: string
  y_label: string
  annotation: string
  readouts: Array<{ label: string; value: string; evidence_ref: string | null }>
}

export const INVESTIGATION_EVENT_TYPES = [
  "investigation.created",
  "status.changed",
  "director.route",
  "agent.queued",
  "agent.started",
  "agent.completed",
  "agent.handoff",
  "agent.skipped",
  "agent.decision",
  "inference.attempt",
  "inference.fallback",
  "inference.summary",
  "critic.review",
  "tool.started",
  "tool.completed",
  "tool.failed",
  "evidence.appended",
  "hypothesis.updated",
  "budget.updated",
  "model.retry",
  "recovery.completed",
  "result.locked",
  "catalog.revealed",
  "run.failed",
] as const

export type InvestigationEventType = (typeof INVESTIGATION_EVENT_TYPES)[number]

export interface InvestigationEvent {
  event_id: string
  run_id: string
  step_id: string
  action_id: string
  sequence: number
  timestamp: string
  type: string
  payload: Record<string, unknown>
  schema_version: "1"
}

export interface ClientErrorShape {
  code: string
  message: string
  run_id: string | null
  recoverable: boolean
}
