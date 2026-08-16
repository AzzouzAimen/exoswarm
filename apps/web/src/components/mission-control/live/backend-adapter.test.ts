import { describe, expect, it } from "vitest"

import type { MissionControlSnapshot } from "@/lib/contracts"

import { buildAgentTraceStages } from "../model/agent-trace"
import { instrumentFromPlot, presentationEventFromBackendEvent, presentationForStatus, presentationFromSnapshot, unavailableInstrument } from "./backend-adapter"

const snapshot = (status: MissionControlSnapshot["status"]): MissionControlSnapshot => ({
  schema_version: "1",
  run_id: "run_1",
  opaque_target_id: "TARGET-X17",
  status,
  lock_state: status === "REVEALED" ? "CATALOG_REVEALED" : status === "RESULT_LOCKED" ? "RESULT_LOCKED" : "GROUND_TRUTH_LOCKED",
  disposition: status === "READY_TO_LOCK" || status === "RESULT_LOCKED" || status === "REVEALED" ? "TRANSIT_LIKE_SIGNAL" : null,
  terminal_reason: status === "FINALIZING" ? null : "backend checkpoint",
  completed_tests: ["candidate_search"],
  available_tests: ["harmonic_test"],
  evidence_refs: ["evidence_1"],
  active_hypotheses: ["planetary_transit"],
  strongest_unresolved_alternative: "eclipsing_binary",
  unresolved_questions: [],
  candidate_signals: [],
  evidence: [{
    evidence_id: "evidence_1",
    timestamp: "2026-08-16T00:00:00Z",
    step_id: "step_1",
    action_id: "action_1",
    tool_name: "search_bls",
    status: "SUCCESS",
    interpretation_code: "TRANSIT_LIKE",
    summary: "Backend measured evidence",
    measurements: { period: { value: 2, display_value: "2 d", unit: "d", uncertainty: null, tolerance: null, evidence_ref: "evidence_1" } },
    diagnostics: {},
    method: "deterministic",
    evidence_ref: "evidence_1",
    artifact_refs: [],
  }],
  accepted_decisions: [],
  critic_decisions: [],
  role_checkpoints: [],
  tool_executions: [],
  failures: status === "FAILED" ? [{ step_id: "step_1", kind: "MODEL_TIMEOUT", concise_reason: "Backend timed out", recoverable: true, retry_count: 1 }] : [],
  inference_summary: {
    provider: "not_measured",
    model_identity: "not_measured",
    agent_calls: 0,
    input_tokens: "not_measured",
    output_tokens: "not_measured",
    median_input_tokens: "not_measured",
    max_input_tokens: "not_measured",
    median_latency_ms: "not_measured",
    first_attempt_schema_valid: { numerator: 0, denominator: 0, rate: "not_applicable" },
    repairs: { numerator: 0, denominator: 0, rate: "not_applicable" },
    fallbacks: { numerator: 0, denominator: 0, rate: "not_applicable" },
    provider_errors_timeouts: 0,
    raw_light_curve_samples_sent: 0,
  },
  budgets: {
    step_count: 1,
    adaptive_cost_units_used: 0,
    adaptive_cost_units_remaining: 4,
    max_adaptive_cost_units: 4,
    adaptive_experiments_used: 0,
    max_adaptive_experiments: 4,
    model_call_count: 0,
    max_model_calls: 24,
    tool_call_count: 1,
    max_tool_calls: 8,
    critic_revision_count: 0,
    max_critic_revisions: 1,
    model_retry_count: 0,
    max_model_retries: 1,
  },
  execution: { run_id: "run_1", status: "STOPPED", active: false, advances: 1, stop_reason: null, started_at: null, finished_at: null },
  lock: { state: status === "RESULT_LOCKED" || status === "REVEALED" ? "RESULT_LOCKED" : "GROUND_TRUTH_LOCKED", sha256: status === "RESULT_LOCKED" || status === "REVEALED" ? "a".repeat(64) : null, locked_at: status === "RESULT_LOCKED" || status === "REVEALED" ? "2026-08-16T00:01:00Z" : null, reveal_available: status === "RESULT_LOCKED" },
  reveal: status === "REVEALED" ? { run_id: "run_1", opaque_target_id: "TARGET-X17", locked_result_sha256: "a".repeat(64), catalog_source: "backend catalog", catalog_payload: { target_name: "TIC hidden until reveal" }, revealed_at: "2026-08-16T00:02:00Z" } : null,
  available_plot_modes: ["raw"],
  plot_evidence_refs: ["evidence_1"],
  last_sequence: 4,
  updated_at: "2026-08-16T00:00:00Z",
})

describe("backend presentation adapter", () => {
  it("maps FINALIZING and READY_TO_LOCK centrally", () => {
    expect(presentationForStatus("FINALIZING").phase).toBe("locking")
    expect(presentationForStatus("READY_TO_LOCK").stageLabel).toBe("Result ready")
    expect(presentationFromSnapshot(snapshot("READY_TO_LOCK")).run.mode).toBe("live")
  })

  it("keeps failure visible and does not fabricate plots or catalog identity", () => {
    const failed = presentationFromSnapshot(snapshot("FAILED"))
    expect(failed.timeline.some((item) => item.tone === "danger")).toBe(true)
    expect(failed.instrument.available).toBe(false)
    expect(failed.instrument.plot.traces).toEqual([])
    expect(failed.target.groundTruthState).toBe("sealed")
    expect(presentationFromSnapshot(snapshot("RESULT_LOCKED")).target.groundTruthState).toBe("sealed")
    expect(presentationFromSnapshot(snapshot("REVEALED")).target.groundTruthState).toBe("revealed")
  })

  it("deduplicates timeline records projected from durable snapshot data", () => {
    const duplicated = snapshot("SEARCHING")
    duplicated.evidence = [duplicated.evidence[0]!, duplicated.evidence[0]!]
    const ids = presentationFromSnapshot(duplicated).timeline.map((item) => item.id)
    expect(new Set(ids).size).toBe(ids.length)
  })

  it("keeps the deterministic Director visible and preserves distinct Director checkpoints", () => {
    const withDirector = snapshot("READY_TO_LOCK")
    withDirector.role_checkpoints = [
      {
        role: "director",
        phase: "briefing",
        status: "COMPLETE",
        decision_id: "director_step_5",
        context_version: "5",
        evidence_refs: ["evidence_1"],
        summary: "Route the unresolved alternative.",
        action: null,
        expected_discriminator: null,
        model_identity: "model",
        provider: "provider",
        latency_ms: 10,
        schema_valid: true,
        fallback_code: null,
      },
      {
        role: "director",
        phase: "final",
        status: "COMPLETE",
        decision_id: "director_step_5",
        context_version: "6",
        evidence_refs: ["evidence_1"],
        summary: "Finalize the bounded investigation.",
        action: null,
        expected_discriminator: null,
        model_identity: "model",
        provider: "provider",
        latency_ms: 10,
        schema_valid: true,
        fallback_code: null,
      },
    ]

    const presentation = presentationFromSnapshot(withDirector)
    const directorRecords = presentation.timeline.filter((item) => item.agentId === "director")
    const directorStages = buildAgentTraceStages(presentation).filter((stage) => stage.agent.id === "director")

    expect(directorRecords).toHaveLength(3)
    expect(new Set(directorRecords.map((item) => item.id)).size).toBe(3)
    expect(directorStages.length).toBeGreaterThan(0)
  })

  it("uses backend plot fields and preserves unavailable state", () => {
    const unavailable = unavailableInstrument("harmonic", "Not run")
    expect(unavailable.available).toBe(false)
    expect(unavailable.plot.traces).toEqual([])
    const plot = instrumentFromPlot({ mode: "raw", available: true, unavailable_reason: null, evidence_refs: ["evidence_1"], traces: [{ name: "flux", x: [1], y: [2], kind: "line", tone: "science", dash: null }], x_label: "BTJD", y_label: "fraction", annotation: "Measured", readouts: [{ label: "sample", value: "1", evidence_ref: "evidence_1" }] })
    expect(plot.plot.traces[0]?.y).toEqual([2])
    expect(plot.readouts[0]?.evidenceRef).toBe("evidence_1")
  })

  it("normalizes unknown backend event types to an audit-safe record", () => {
    const normalized = presentationEventFromBackendEvent({ event_id: "evt_1", run_id: "run_1", step_id: "step_1", action_id: "action_1", sequence: 5, timestamp: "2026-08-16T00:00:00Z", type: "future.event", payload: {}, schema_version: "1" }, snapshot("SEARCHING"))
    expect(normalized?.type).toBe("audit.event")
  })
})
