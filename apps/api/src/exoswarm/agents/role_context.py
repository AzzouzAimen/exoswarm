from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from exoswarm.agents.context import (
    MAX_SERIALIZED_CONTEXT_BYTES,
    CandidateContext,
    CompactEvidence,
    ExperimentOption,
    RemainingBudgets,
    assemble_context,
    assert_agent_safe_context,
)
from exoswarm.domain.enums import AgentRole
from exoswarm.domain.models import AgentDecisionRecord, EvidenceRecord, InvestigationState

ROLE_CONTEXT_SCHEMA_VERSION = "role-context-v2"


class _FrozenPacket(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class SafeRoleEnvelope(_FrozenPacket):
    role: AgentRole
    run_id: str
    step_id: str
    opaque_target_id: str
    context_version: str
    evidence_refs: tuple[str, ...]
    context_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    context_schema_version: Literal["role-context-v2"] = ROLE_CONTEXT_SCHEMA_VERSION
    serialized_size_bytes: int = Field(ge=0, le=MAX_SERIALIZED_CONTEXT_BYTES)


class ObservationQualityEvidence(_FrozenPacket):
    evidence_id: str
    tool_name: str
    status: str
    input_sample_count: int | None = Field(default=None, ge=0)
    retained_sample_count: int | None = Field(default=None, ge=0)
    quality_removed_count: int | None = Field(default=None, ge=0)
    invalid_removed_count: int | None = Field(default=None, ge=0)
    outlier_removed_count: int | None = Field(default=None, ge=0)
    cadence_seconds: float | None = Field(default=None, gt=0)
    preprocessing_parameters: dict[str, float | int] = Field(default_factory=dict)
    warnings: tuple[str, ...] = ()
    method: str
    code_version: str


class ObserverContext(SafeRoleEnvelope):
    role: Literal[AgentRole.OBSERVER] = AgentRole.OBSERVER
    quality_evidence: tuple[ObservationQualityEvidence, ...]
    completed_tests: tuple[str, ...]


class SignalContext(SafeRoleEnvelope):
    role: Literal[AgentRole.SIGNAL] = AgentRole.SIGNAL
    candidate: CandidateContext
    signal_evidence: tuple[CompactEvidence, ...]
    active_hypotheses: tuple[str, ...]
    strongest_unresolved_alternative: str | None


class TransitHunterContext(SafeRoleEnvelope):
    role: Literal[AgentRole.TRANSIT_HUNTER] = AgentRole.TRANSIT_HUNTER
    candidate: CandidateContext
    mandatory_evidence: tuple[CompactEvidence, ...]
    available_experiments: tuple[ExperimentOption, ...]
    promoted_specialist_briefs: dict[str, dict[str, Any]] = Field(default_factory=dict)


class DirectorContext(SafeRoleEnvelope):
    role: Literal[AgentRole.DIRECTOR] = AgentRole.DIRECTOR
    phase: Literal["briefing", "final"]
    authorized_route: str
    deterministic_disposition: str | None
    active_hypotheses: tuple[str, ...]
    accepted_role_briefs: dict[str, dict[str, Any]] = Field(default_factory=dict)
    remaining_budgets: RemainingBudgets
    lock_state: str


RoleContext = ObserverContext | SignalContext | TransitHunterContext | DirectorContext


def _canonical_bytes(payload: object) -> bytes:
    return json.dumps(
        payload,
        default=lambda value: (
            value.model_dump(mode="json") if isinstance(value, BaseModel) else str(value)
        ),
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _finalize(model: type[RoleContext], payload: dict[str, Any]) -> RoleContext:
    fingerprint = hashlib.sha256(_canonical_bytes(payload)).hexdigest()
    size = 0
    packet: RoleContext | None = None
    for _ in range(4):
        packet = model.model_validate(
            {**payload, "context_fingerprint": fingerprint, "serialized_size_bytes": size}
        )
        updated_size = len(_canonical_bytes(packet.model_dump(mode="json")))
        if updated_size == size:
            break
        size = updated_size
    assert packet is not None
    if size > MAX_SERIALIZED_CONTEXT_BYTES:
        raise ValueError("role context exceeds the serialized context ceiling")
    if packet.serialized_size_bytes != size:
        packet = packet.model_copy(update={"serialized_size_bytes": size})
    assert_agent_safe_context(packet)
    return packet


def _briefs(
    records: Iterable[AgentDecisionRecord], *, roles: frozenset[AgentRole]
) -> dict[str, dict[str, Any]]:
    return {
        record.role.value: dict(record.decision)
        for record in records
        if record.role in roles and record.decision is not None
    }


def _optional_nonnegative_int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def _optional_positive_float(value: object) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0:
        return float(value)
    return None


def _observation_quality_evidence(record: EvidenceRecord) -> ObservationQualityEvidence:
    diagnostics = record.result.diagnostics
    preprocessing = record.result.parameters.get("preprocessing", {})
    safe_preprocessing = {
        str(key): value
        for key, value in preprocessing.items()
        if isinstance(value, (int, float)) and not isinstance(value, bool)
    } if isinstance(preprocessing, dict) else {}
    return ObservationQualityEvidence(
        evidence_id=record.evidence_id,
        tool_name=record.tool_name,
        status=record.tool_status.value,
        input_sample_count=_optional_nonnegative_int(diagnostics.get("input_sample_count")),
        retained_sample_count=_optional_nonnegative_int(
            diagnostics.get("retained_sample_count")
        ),
        quality_removed_count=_optional_nonnegative_int(
            diagnostics.get("quality_removed_count")
        ),
        invalid_removed_count=_optional_nonnegative_int(
            diagnostics.get("invalid_removed_count")
        ),
        outlier_removed_count=_optional_nonnegative_int(
            diagnostics.get("outlier_removed_count")
        ),
        cadence_seconds=_optional_positive_float(diagnostics.get("cadence_seconds")),
        preprocessing_parameters=safe_preprocessing,
        warnings=tuple(record.result.warnings),
        method=record.result.method,
        code_version=record.result.provenance.code_version,
    )


def assemble_role_context(
    state: InvestigationState,
    evidence: list[EvidenceRecord] | tuple[EvidenceRecord, ...],
    *,
    role: Literal["observer", "signal", "transit_hunter", "director"],
    available_experiments: tuple[str, ...] = (),
    adaptive_experiment_costs: dict[str, int] | None = None,
    experiment_specs: Iterable[object] = (),
    accepted_role_records: Iterable[AgentDecisionRecord] = (),
    promoted_specialist_briefs: bool = False,
    authorized_route: str | None = None,
    director_phase: Literal["briefing", "final"] = "briefing",
    deterministic_disposition: str | None = None,
) -> RoleContext:
    """Project the existing safe evidence packet into a smaller role-specific packet."""

    base = assemble_context(
        state,
        evidence,
        role="skeptic",
        available_experiments=available_experiments,
        adaptive_experiment_costs=adaptive_experiment_costs,
        experiment_specs=experiment_specs,
    )
    common: dict[str, Any] = {
        "run_id": base.run_id,
        "step_id": base.step_id,
        "opaque_target_id": base.opaque_target_id,
        "context_version": base.context_version,
        "context_schema_version": ROLE_CONTEXT_SCHEMA_VERSION,
    }
    if role == "observer":
        visible_records = [
            record for record in evidence if record.evidence_id in base.evidence_refs
        ]
        quality_records = [
            record for record in visible_records if record.tool_name == "search_bls"
        ] or visible_records[:1]
        quality = tuple(_observation_quality_evidence(record) for record in quality_records)
        return _finalize(
            ObserverContext,
            {
                **common,
                "role": AgentRole.OBSERVER,
                "evidence_refs": tuple(item.evidence_id for item in quality),
                "quality_evidence": quality,
                "completed_tests": base.completed_tests,
            },
        )
    if base.candidate is None and role in {"signal", "transit_hunter"}:
        raise ValueError(f"{role} context requires a deterministic candidate")
    if role == "signal":
        assert base.candidate is not None
        return _finalize(
            SignalContext,
            {
                **common,
                "role": AgentRole.SIGNAL,
                "evidence_refs": base.evidence_refs,
                "candidate": base.candidate,
                "signal_evidence": base.recent_evidence,
                "active_hypotheses": base.active_hypotheses,
                "strongest_unresolved_alternative": base.strongest_unresolved_alternative,
            },
        )
    if role == "transit_hunter":
        assert base.candidate is not None
        return _finalize(
            TransitHunterContext,
            {
                **common,
                "role": AgentRole.TRANSIT_HUNTER,
                "evidence_refs": base.evidence_refs,
                "candidate": base.candidate,
                "mandatory_evidence": base.recent_evidence,
                "available_experiments": base.available_experiments,
                "promoted_specialist_briefs": (
                    _briefs(
                        accepted_role_records,
                        roles=frozenset({AgentRole.OBSERVER, AgentRole.SIGNAL}),
                    )
                    if promoted_specialist_briefs
                    else {}
                ),
            },
        )
    if authorized_route is None:
        raise ValueError("Director context requires the deterministic authorized route")
    return _finalize(
        DirectorContext,
        {
            **common,
            "role": AgentRole.DIRECTOR,
            "phase": director_phase,
            "authorized_route": authorized_route,
            "deterministic_disposition": (
                deterministic_disposition
                if deterministic_disposition is not None
                else state.disposition.value if state.disposition is not None else None
            ),
            "active_hypotheses": base.active_hypotheses,
            "accepted_role_briefs": _briefs(
                accepted_role_records,
                roles=frozenset(
                    {AgentRole.OBSERVER, AgentRole.SIGNAL, AgentRole.TRANSIT_HUNTER}
                ),
            ),
            "remaining_budgets": base.remaining_budgets,
            "lock_state": state.lock_state.value,
            "evidence_refs": base.evidence_refs,
        },
    )


def visible_evidence_refs(context: BaseModel) -> frozenset[str]:
    refs = getattr(context, "evidence_refs", ())
    return frozenset(str(item) for item in refs)


__all__ = [
    "DirectorContext",
    "ObservationQualityEvidence",
    "ObserverContext",
    "ROLE_CONTEXT_SCHEMA_VERSION",
    "RoleContext",
    "SafeRoleEnvelope",
    "SignalContext",
    "TransitHunterContext",
    "assemble_role_context",
    "visible_evidence_refs",
]
