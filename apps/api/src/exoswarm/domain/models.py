from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from exoswarm.domain.enums import (
    TERMINAL_STATUSES,
    CriticVerdict,
    Disposition,
    InformationValue,
    InvestigationStatus,
    LockState,
    Priority,
    ToolStatus,
)


def utc_now() -> datetime:
    return datetime.now(UTC)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Provenance(StrictModel):
    input_artifact_refs: list[str] = Field(default_factory=list)
    output_artifact_refs: list[str] = Field(default_factory=list)
    code_version: str = Field(min_length=1)
    source_data_ref: str = Field(min_length=1)
    source_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    library_versions: dict[str, str] = Field(default_factory=dict)


class Measurement(StrictModel):
    value: float | int | str | bool
    unit: str | None = None
    uncertainty: float | None = None
    tolerance: float | None = None
    evidence_ref: str | None = None


class ScientificToolResult(StrictModel):
    tool_name: str = Field(min_length=1)
    status: ToolStatus
    run_id: str = Field(min_length=1)
    action_id: str = Field(min_length=1)
    target_id: str = Field(min_length=1)
    measurements: dict[str, Measurement] = Field(default_factory=dict)
    diagnostics: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    method: str = Field(min_length=1)
    parameters: dict[str, Any] = Field(default_factory=dict)
    provenance: Provenance
    suggested_alternatives: list[str] = Field(default_factory=list)
    reason: str | None = None


class EvidenceRecord(StrictModel):
    evidence_id: str = Field(min_length=1)
    timestamp: datetime = Field(default_factory=utc_now)
    run_id: str = Field(min_length=1)
    step_id: str = Field(min_length=1)
    action_id: str = Field(min_length=1)
    opaque_target_id: str = Field(min_length=1)
    tool_name: str = Field(min_length=1)
    tool_status: ToolStatus
    result: ScientificToolResult
    interpretation_code: str | None = None
    agent_decision_id: str | None = None
    critic_decision_id: str | None = None

    @model_validator(mode="after")
    def result_identifiers_match(self) -> EvidenceRecord:
        if (self.run_id, self.action_id, self.opaque_target_id) != (
            self.result.run_id,
            self.result.action_id,
            self.result.target_id,
        ):
            raise ValueError("evidence and tool-result identifiers must match")
        if self.tool_status != self.result.status or self.tool_name != self.result.tool_name:
            raise ValueError("evidence and tool-result status/name must match")
        return self


class CandidateSignal(StrictModel):
    candidate_id: str = Field(min_length=1)
    evidence_refs: list[str] = Field(min_length=1)
    measurements: dict[str, Measurement] = Field(default_factory=dict)


class SkepticDecision(StrictModel):
    decision_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    step_id: str = Field(min_length=1)
    hypothesis_under_test: str = Field(min_length=1)
    requested_experiment: str = Field(min_length=1)
    parameters: dict[str, Any] = Field(default_factory=dict)
    reason_code: str = Field(min_length=1)
    expected_discriminating_result: str = Field(min_length=1, max_length=500)
    predicted_outcomes: dict[str, str] = Field(default_factory=dict)
    expected_information_value: InformationValue
    stop_if: str | None = Field(default=None, max_length=300)
    priority: Priority
    concise_reason: str = Field(min_length=1, max_length=300)


class CriticDecision(StrictModel):
    decision_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    step_id: str = Field(min_length=1)
    skeptic_decision_id: str = Field(min_length=1)
    verdict: CriticVerdict
    reason_code: str = Field(min_length=1)
    concise_reason: str = Field(min_length=1, max_length=300)
    revised_experiment: str | None = None
    revised_parameters: dict[str, Any] | None = None

    @model_validator(mode="after")
    def revision_matches_verdict(self) -> CriticDecision:
        if self.verdict == CriticVerdict.REVISE and not self.revised_experiment:
            raise ValueError("REVISE requires revised_experiment")
        if self.verdict != CriticVerdict.REVISE and self.revised_experiment is not None:
            raise ValueError("only REVISE may provide revised_experiment")
        return self


class InvestigationState(StrictModel):
    run_id: str = Field(min_length=1)
    opaque_target_id: str = Field(min_length=1)
    status: InvestigationStatus = InvestigationStatus.INITIALIZED
    lock_state: LockState = LockState.GROUND_TRUTH_LOCKED
    disposition: Disposition | None = None
    candidate_signals: list[CandidateSignal] = Field(default_factory=list)
    active_hypotheses: list[str] = Field(default_factory=list)
    strongest_unresolved_alternative: str | None = None
    evidence_refs: list[str] = Field(default_factory=list)
    completed_tests: list[str] = Field(default_factory=list)
    available_tests: list[str] = Field(default_factory=list)
    unresolved_questions: list[str] = Field(default_factory=list)
    step_count: int = Field(default=0, ge=0)
    model_call_count: int = Field(default=0, ge=0)
    tool_call_count: int = Field(default=0, ge=0)
    adaptive_experiments_used: int = Field(default=0, ge=0)
    max_steps: int = Field(default=12, ge=1)
    max_adaptive_experiments: int = Field(default=4, ge=0)
    terminal_reason: str | None = None
    context_version: str = "1"
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def terminal_state_has_reason(self) -> InvestigationState:
        if self.status in TERMINAL_STATUSES and not self.terminal_reason:
            raise ValueError("terminal investigation status requires terminal_reason")
        return self


class LockedResult(StrictModel):
    run_id: str = Field(min_length=1)
    opaque_target_id: str = Field(min_length=1)
    disposition: Disposition
    evidence_refs: list[str]
    terminal_reason: str = Field(min_length=1)
    schema_version: str = "1"
    locked_at: datetime = Field(default_factory=utc_now)


class LockReceipt(StrictModel):
    run_id: str
    opaque_target_id: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    result_path: str
    locked_at: datetime


class RevealResult(StrictModel):
    run_id: str = Field(min_length=1)
    opaque_target_id: str = Field(min_length=1)
    locked_result_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    catalog_source: str = Field(min_length=1)
    catalog_payload: dict[str, Any]
    revealed_at: datetime = Field(default_factory=utc_now)
