from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from exoswarm.domain.enums import (
    AgentCheckpointStatus,
    AgentPhase,
    AgentRole,
    CriticVerdict,
    InvestigationStatus,
    LockState,
    ToolExecutionStatus,
    ToolStatus,
)
from exoswarm.domain.models import InferenceSummary
from exoswarm.investigation.runner import RunExecutionSnapshot


class MissionControlModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MeasurementView(MissionControlModel):
    value: float | int | str | bool
    display_value: str
    unit: str | None = None
    uncertainty: float | None = None
    tolerance: float | None = None
    evidence_ref: str


class EvidenceView(MissionControlModel):
    evidence_id: str
    timestamp: datetime
    step_id: str
    action_id: str
    tool_name: str
    status: ToolStatus
    interpretation_code: str | None = None
    summary: str
    measurements: dict[str, MeasurementView] = Field(default_factory=dict)
    diagnostics: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
    method: str
    evidence_ref: str
    artifact_refs: list[str] = Field(default_factory=list)


class CandidateSignalView(MissionControlModel):
    candidate_id: str
    evidence_refs: list[str]
    measurements: dict[str, MeasurementView] = Field(default_factory=dict)


class AgentCheckpointView(MissionControlModel):
    role: AgentRole
    phase: AgentPhase
    status: AgentCheckpointStatus
    decision_id: str
    context_version: str
    evidence_refs: list[str] = Field(default_factory=list)
    summary: str | None = None
    action: str | None = None
    expected_discriminator: str | None = None
    model_identity: str | None = None
    provider: str | None = None
    latency_ms: int | None = None
    schema_valid: bool | None = None
    fallback_code: str | None = None


class SkepticDecisionView(MissionControlModel):
    decision_id: str
    step_id: str
    context_version: str
    hypothesis_under_test: str
    requested_experiment: str
    reason_code: str
    expected_discriminating_result: str
    expected_information_value: str
    priority: str
    cost_of_selected_experiment: int
    concise_reason: str
    supporting_evidence_refs: list[str] = Field(default_factory=list)
    contradicting_evidence_refs: list[str] = Field(default_factory=list)


class CriticDecisionView(MissionControlModel):
    decision_id: str
    step_id: str
    context_version: str
    skeptic_decision_id: str
    verdict: CriticVerdict
    reason_code: str
    concise_reason: str
    revised_experiment: str | None = None
    supporting_evidence_refs: list[str] = Field(default_factory=list)
    contradicting_evidence_refs: list[str] = Field(default_factory=list)


class ToolExecutionView(MissionControlModel):
    action_id: str
    step_id: str
    tool_name: str
    status: ToolExecutionStatus
    adaptive: bool
    adaptive_cost_units: int
    agent_decision_id: str | None = None
    critic_decision_id: str | None = None
    result_status: ToolStatus | None = None
    evidence_ref: str | None = None
    failure_kind: str | None = None
    failure_reason: str | None = None


class FailureView(MissionControlModel):
    step_id: str
    kind: str
    concise_reason: str
    recoverable: bool
    retry_count: int


class BudgetView(MissionControlModel):
    step_count: int
    adaptive_cost_units_used: int
    adaptive_cost_units_remaining: int
    max_adaptive_cost_units: int
    adaptive_experiments_used: int
    max_adaptive_experiments: int
    model_call_count: int
    max_model_calls: int
    tool_call_count: int
    max_tool_calls: int
    critic_revision_count: int
    max_critic_revisions: int
    model_retry_count: int
    max_model_retries: int


class LockProjection(MissionControlModel):
    state: LockState
    sha256: str | None = None
    locked_at: datetime | None = None
    reveal_available: bool


class RevealProjection(MissionControlModel):
    run_id: str
    opaque_target_id: str
    locked_result_sha256: str
    catalog_source: str
    catalog_payload: dict[str, object]
    revealed_at: datetime


class PlotReadout(MissionControlModel):
    label: str
    value: str
    evidence_ref: str | None = None


class PlotTraceView(MissionControlModel):
    name: str
    x: list[float]
    y: list[float]
    kind: Literal["line", "markers", "bar"]
    tone: Literal["science", "muted", "unresolved", "approved"]
    dash: Literal["solid", "dot", "dash"] | None = None


class PlotView(MissionControlModel):
    mode: Literal["raw", "bls", "phase-fold", "odd-even", "secondary", "harmonic"]
    available: bool
    unavailable_reason: str | None = None
    evidence_refs: list[str] = Field(default_factory=list)
    traces: list[PlotTraceView] = Field(default_factory=list)
    x_label: str
    y_label: str
    annotation: str
    readouts: list[PlotReadout] = Field(default_factory=list)


class MissionControlSnapshot(MissionControlModel):
    schema_version: Literal["1"] = "1"
    run_id: str
    opaque_target_id: str
    status: InvestigationStatus
    lock_state: LockState
    disposition: str | None = None
    terminal_reason: str | None = None
    completed_tests: list[str]
    available_tests: list[str]
    evidence_refs: list[str]
    active_hypotheses: list[str]
    strongest_unresolved_alternative: str | None = None
    unresolved_questions: list[str]
    candidate_signals: list[CandidateSignalView]
    evidence: list[EvidenceView]
    accepted_decisions: list[SkepticDecisionView]
    critic_decisions: list[CriticDecisionView]
    role_checkpoints: list[AgentCheckpointView]
    tool_executions: list[ToolExecutionView]
    failures: list[FailureView]
    inference_summary: InferenceSummary
    budgets: BudgetView
    execution: RunExecutionSnapshot
    lock: LockProjection
    reveal: RevealProjection | None = None
    available_plot_modes: list[str] = Field(default_factory=list)
    plot_evidence_refs: list[str] = Field(default_factory=list)
    last_sequence: int = Field(ge=1)
    updated_at: datetime


__all__ = [
    "AgentCheckpointView",
    "BudgetView",
    "CandidateSignalView",
    "CriticDecisionView",
    "EvidenceView",
    "FailureView",
    "LockProjection",
    "MeasurementView",
    "MissionControlSnapshot",
    "PlotReadout",
    "PlotTraceView",
    "PlotView",
    "RevealProjection",
    "SkepticDecisionView",
    "ToolExecutionView",
]
