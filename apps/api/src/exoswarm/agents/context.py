from __future__ import annotations

import json
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from exoswarm.domain.models import (
    EvidenceRecord,
    InvestigationState,
    Measurement,
    SkepticDecision,
)

FORBIDDEN_CONTEXT_KEYS = frozenset(
    {
        "cached_path",
        "cache_path",
        "local_path",
        "private_provenance_path",
        "catalog_disposition",
        "catalog_payload",
        "fits_path",
        "ground_truth",
        "known_period",
        "raw_flux",
        "raw_lightcurve",
        "reveal",
        "source_data_ref",
        "source_path",
        "target_name",
        "tic_id",
        "toi_id",
    }
)

_WINDOWS_PATH = re.compile(r"(?i)(?:\b[a-z]:[\\/]|\\\\[^\\\s]+\\[^\\\s]+)")
_POSIX_PATH = re.compile(
    r"(?:^|[\s\"'(])/(?!/)[A-Za-z0-9._~-]+(?:/[A-Za-z0-9._~-]+)*"
)
_LOCAL_FILE_SUFFIX = re.compile(
    r"(?i)\.(?:fits?|fts|csv|tsv|npy|npz|parquet)(?:\b|$)"
)
_HIDDEN_AUTHORITY = re.compile(
    r"(?i)\b(?:ground[-_\s]?truth|catalog(?:ue)?|reveal(?:ed)?)\b"
)
_RECOGNIZABLE_TARGET = re.compile(
    r"(?i)\b(?:tic|toi)\s*[-:#]?\s*\d+[a-z]?\b|"
    r"\b(?:kepler|k2|wasp|hat-p|tres|gj|hd)\s*[- ]?\s*\d+[a-z]?\b"
)


class _FrozenPacket(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ContextMeasurement(_FrozenPacket):
    value: float | int | str | bool
    unit: str | None = None
    uncertainty: float | None = None
    tolerance: float | None = None
    evidence_ref: str


class CandidateContext(_FrozenPacket):
    candidate_id: str
    measurements: dict[str, ContextMeasurement]
    evidence_refs: tuple[str, ...]


class CompactEvidence(_FrozenPacket):
    evidence_id: str
    tool_name: str
    status: str
    measurements: dict[str, ContextMeasurement]
    interpretation_code: str | None
    method: str
    code_version: str


class RemainingBudgets(_FrozenPacket):
    steps: int
    model_calls: int
    tool_calls: int
    adaptive_experiments: int
    critic_revisions: int
    transient_model_retries: int


class AgentContextPacket(_FrozenPacket):
    role: Literal["skeptic", "critic"]
    run_id: str
    step_id: str
    opaque_target_id: str
    status: str
    candidate: CandidateContext | None
    evidence_refs: tuple[str, ...]
    completed_tests: tuple[str, ...]
    recent_evidence: tuple[CompactEvidence, ...]
    active_hypotheses: tuple[str, ...]
    strongest_unresolved_alternative: str | None
    available_experiments: tuple[str, ...]
    proposed_decision: SkepticDecision | None = None
    remaining_budgets: RemainingBudgets
    context_version: str
    provenance_version: str


def _context_measurement(measurement: Measurement, evidence_id: str) -> ContextMeasurement:
    return ContextMeasurement(
        value=measurement.value,
        unit=measurement.unit,
        uncertainty=measurement.uncertainty,
        tolerance=measurement.tolerance,
        evidence_ref=measurement.evidence_ref or evidence_id,
    )


def assemble_context(
    state: InvestigationState,
    evidence: list[EvidenceRecord] | tuple[EvidenceRecord, ...] = (),
    *,
    role: Literal["skeptic", "critic"] = "skeptic",
    available_experiments: tuple[str, ...] | None = None,
    recent_limit: int = 6,
    proposed_decision: SkepticDecision | None = None,
) -> AgentContextPacket:
    """Rebuild the compact model packet only from durable state and ledger records."""

    candidate = state.candidate_signals[0] if state.candidate_signals else None
    candidate_packet = None
    if candidate is not None:
        fallback_ref = candidate.evidence_refs[-1]
        candidate_packet = CandidateContext(
            candidate_id=candidate.candidate_id,
            measurements={
                name: _context_measurement(measurement, fallback_ref)
                for name, measurement in candidate.measurements.items()
            },
            evidence_refs=tuple(candidate.evidence_refs),
        )

    recent = tuple(
        CompactEvidence(
            evidence_id=record.evidence_id,
            tool_name=record.tool_name,
            status=record.tool_status,
            measurements={
                name: _context_measurement(measurement, record.evidence_id)
                for name, measurement in record.result.measurements.items()
            },
            interpretation_code=record.interpretation_code,
            method=record.result.method,
            code_version=record.result.provenance.code_version,
        )
        for record in evidence[-recent_limit:]
    )
    packet = AgentContextPacket(
        role=role,
        run_id=state.run_id,
        step_id=f"step_{state.step_count:04d}",
        opaque_target_id=state.opaque_target_id,
        status=state.status,
        candidate=candidate_packet,
        evidence_refs=tuple(state.evidence_refs),
        completed_tests=tuple(state.completed_tests),
        recent_evidence=recent,
        active_hypotheses=tuple(state.active_hypotheses),
        strongest_unresolved_alternative=state.strongest_unresolved_alternative,
        available_experiments=(
            available_experiments
            if available_experiments is not None
            else tuple(state.available_tests)
        ),
        proposed_decision=proposed_decision,
        remaining_budgets=RemainingBudgets(
            steps=max(0, state.max_steps - state.step_count),
            model_calls=max(0, state.max_model_calls - state.model_call_count),
            tool_calls=max(0, state.max_tool_calls - state.tool_call_count),
            adaptive_experiments=max(
                0, state.max_adaptive_experiments - state.adaptive_experiments_used
            ),
            critic_revisions=max(0, state.max_critic_revisions - state.critic_revision_count),
            transient_model_retries=max(
                0, state.max_model_retries - state.model_retry_count
            ),
        ),
        context_version=state.context_version,
        provenance_version="evidence-ledger-v1",
    )
    assert_agent_safe_context(packet)
    return packet


def assert_agent_safe_context(packet: AgentContextPacket) -> None:
    """Fail closed when non-allowlisted authority data enters a compact packet."""

    def reject_unsafe_string(value: str) -> None:
        lowered = value.lower()
        if len(value) > 1_000:
            raise RuntimeError("agent context contains an oversized raw value")
        if lowered.startswith("file:") or "file://" in lowered:
            raise RuntimeError("agent context contains a local file URI")
        if _WINDOWS_PATH.search(value) or _POSIX_PATH.search(value):
            raise RuntimeError("agent context contains a local source path")
        if _LOCAL_FILE_SUFFIX.search(value):
            raise RuntimeError("agent context contains a cached source location")
        if _HIDDEN_AUTHORITY.search(value):
            raise RuntimeError("agent context contains catalog or reveal authority data")
        if _RECOGNIZABLE_TARGET.search(value):
            raise RuntimeError("agent context contains recognizable target identity")
        stripped = value.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            try:
                decoded = json.loads(stripped)
            except json.JSONDecodeError:
                decoded = None
            if isinstance(decoded, list) and len(decoded) >= 3:
                raise RuntimeError("agent context contains a raw observation array")

    def inspect(value: Any, key: str | None = None) -> None:
        normalized_key = key.lower() if key is not None else None
        if normalized_key in FORBIDDEN_CONTEXT_KEYS:
            raise RuntimeError(f"forbidden agent-context field: {key}")
        if isinstance(value, dict):
            for child_key, child_value in value.items():
                inspect(child_value, str(child_key))
        elif isinstance(value, (list, tuple)):
            for child in value:
                inspect(child)
        elif isinstance(value, str):
            reject_unsafe_string(value)

    inspect(packet.model_dump(mode="json"))
