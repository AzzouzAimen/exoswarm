from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Sequence
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from exoswarm.domain.models import (
    EvidenceRecord,
    InvestigationState,
    Measurement,
    SkepticDecision,
)

CONTEXT_SCHEMA_VERSION = "agent-context-v2"
CONTEXT_PROVENANCE_VERSION = "evidence-ledger-v2"
MAX_SERIALIZED_CONTEXT_BYTES = 16_384

FORBIDDEN_CONTEXT_KEYS = frozenset(
    {
        "cached_path",
        "cache_path",
        "catalog_disposition",
        "catalog_payload",
        "fits_path",
        "flux",
        "flux_values",
        "ground_truth",
        "known_period",
        "local_path",
        "private_provenance_path",
        "raw_array",
        "raw_flux",
        "raw_lightcurve",
        "reveal",
        "samples",
        "source_data_ref",
        "source_path",
        "target_name",
        "tic_id",
        "time_samples",
        "time_values",
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
_DECISION_CRITICAL_INTERPRETATIONS = frozenset(
    {
        "CLEAN_PLANET_LIKE",
        "CONTAMINATION_LIKELY",
        "CONTAMINATION_POSSIBLE",
        "HARMONIC_ALIAS_PREFERRED",
        "ODD_EVEN_MISMATCH",
        "SECONDARY_ECLIPSE_DETECTED",
        "WEAK_NOISY",
    }
)
_PARAMETER_SCHEMA_KEYS = (
    "type",
    "enum",
    "const",
    "default",
    "minimum",
    "maximum",
    "exclusiveMinimum",
    "exclusiveMaximum",
    "minLength",
    "maxLength",
    "pattern",
)

_FALLBACK_ACTION_CONTRACTS: dict[str, tuple[str, int, dict[str, Any]]] = {
    "alternate_detrend": (
        "Test whether the signal survives an allowed alternate detrending choice.",
        1,
        {
            "type": "object",
            "properties": {
                "window_days": {"type": "number", "exclusiveMinimum": 0.5, "exclusiveMaximum": 3.0}
            },
            "additionalProperties": False,
        },
    ),
    "alternate_aperture": (
        "Test whether the signal is stable under an allowed alternate aperture.",
        1,
        {"type": "object", "properties": {}, "additionalProperties": False},
    ),
    "centroid_localization": (
        "Test whether transit-associated position changes localize away from the target.",
        2,
        {"type": "object", "properties": {}, "additionalProperties": False},
    ),
    "harmonic_test": (
        "Test whether a harmonic or doubled-period explanation better accounts for the signal.",
        1,
        {
            "type": "object",
            "properties": {
                "trial_factor": {"type": "integer", "minimum": 1, "maximum": 2, "default": 1}
            },
            "additionalProperties": False,
        },
    ),
    "secondary_deep_search": (
        "Search deterministically for a weak secondary event at the candidate period.",
        1,
        {"type": "object", "properties": {}, "additionalProperties": False},
    ),
    "stop": (
        "Stop adaptive testing when no affordable action can change the decision.",
        0,
        {"type": "object", "properties": {}, "additionalProperties": False},
    ),
}


class ContextSizeError(RuntimeError):
    """Required decision context cannot fit inside the enforced serialization ceiling."""


class _NamedExperimentSpec(Protocol):
    name: str


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


class ExperimentOption(_FrozenPacket):
    action_name: str = Field(min_length=1)
    purpose: str = Field(min_length=1, max_length=240)
    deterministic_cost: int = Field(ge=0)
    required_completed_tests: tuple[str, ...] = ()
    parameter_contract: dict[str, Any]
    already_executed: bool
    availability_reason: str | None = Field(default=None, max_length=120)


class RemainingBudgets(_FrozenPacket):
    steps: int
    model_calls: int
    tool_calls: int
    adaptive_experiments: int
    critic_revisions: int
    transient_model_retries: int
    adaptive_cost_units: int


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
    available_experiments: tuple[ExperimentOption, ...]
    adaptive_experiment_costs: dict[str, int]
    proposed_decision: SkepticDecision | None = None
    remaining_budgets: RemainingBudgets
    context_version: str
    context_schema_version: Literal["agent-context-v2"] = CONTEXT_SCHEMA_VERSION
    provenance_version: str
    context_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    serialized_size_bytes: int = Field(ge=0, le=MAX_SERIALIZED_CONTEXT_BYTES)


def _context_measurement(measurement: Measurement, evidence_id: str) -> ContextMeasurement:
    return ContextMeasurement(
        value=measurement.value,
        unit=measurement.unit,
        uncertainty=measurement.uncertainty,
        tolerance=measurement.tolerance,
        evidence_ref=measurement.evidence_ref or evidence_id,
    )


def _compact_parameter_contract(parameter_schema: type[BaseModel] | None) -> dict[str, Any]:
    if parameter_schema is None:
        return {"type": "object", "properties": {}, "additionalProperties": False}
    schema = parameter_schema.model_json_schema()
    compact_properties: dict[str, Any] = {}
    for name in sorted(schema.get("properties", {})):
        field = schema["properties"][name]
        compact_properties[name] = {
            key: field[key] for key in _PARAMETER_SCHEMA_KEYS if key in field
        }
    compact: dict[str, Any] = {
        "type": "object",
        "properties": compact_properties,
        "additionalProperties": bool(schema.get("additionalProperties", False)),
    }
    required = sorted(schema.get("required", ()))
    if required:
        compact["required"] = required
    return compact


def _spec_value(spec: object, *names: str, default: Any) -> Any:
    for name in names:
        value = getattr(spec, name, None)
        if value is not None:
            return value
    return default


def build_experiment_options(
    state: InvestigationState,
    *,
    available_names: Sequence[str],
    experiment_specs: Iterable[_NamedExperimentSpec] = (),
    authoritative_costs: dict[str, int] | None = None,
) -> tuple[ExperimentOption, ...]:
    """Build model-visible action choices from the deterministic registry contract."""

    available = frozenset(available_names)
    specs_by_name = {
        str(spec.name): spec
        for spec in experiment_specs
        if spec.name
    }
    names = sorted(
        available
        | {
            name
            for name, spec in specs_by_name.items()
            if bool(getattr(spec, "adaptive", True))
        }
    )
    executions = {item.tool_name for item in state.tool_executions}
    remaining_cost = _spec_value(
        state,
        "experiment_budget_units_remaining",
        "adaptive_budget_units_remaining",
        "adaptive_cost_units_remaining",
        default=None,
    )
    options: list[ExperimentOption] = []
    for name in names:
        spec = specs_by_name.get(name)
        fallback_purpose, fallback_cost, fallback_parameters = _FALLBACK_ACTION_CONTRACTS.get(
            name,
            (
                f"Run the registered deterministic {name} diagnostic.",
                1,
                {"type": "object", "properties": {}, "additionalProperties": False},
            ),
        )
        required = tuple(sorted(getattr(spec, "required_completed_tests", ())))
        cost = int(
            (authoritative_costs or {}).get(
                name,
                _spec_value(
                    spec,
                    "deterministic_cost",
                    "cost_units",
                    "experiment_cost",
                    default=fallback_cost,
                ),
            )
        )
        already_executed = name in executions
        missing = sorted(set(required).difference(state.completed_tests))
        if already_executed:
            availability_reason = "already_executed"
        elif missing:
            availability_reason = "required_tests_incomplete"
        elif isinstance(remaining_cost, int) and cost > remaining_cost:
            availability_reason = "insufficient_cost_budget"
        elif name not in available:
            availability_reason = "not_currently_available"
        else:
            availability_reason = None
        parameter_schema = getattr(spec, "parameter_schema", None)
        options.append(
            ExperimentOption(
                action_name=name,
                purpose=str(
                    _spec_value(spec, "purpose", "description", default=fallback_purpose)
                )[:240],
                deterministic_cost=cost,
                required_completed_tests=required,
                parameter_contract=(
                    _compact_parameter_contract(parameter_schema)
                    if parameter_schema is not None
                    else fallback_parameters
                ),
                already_executed=already_executed,
                availability_reason=availability_reason,
            )
        )
    return tuple(options)


def _compact_evidence(record: EvidenceRecord) -> CompactEvidence:
    return CompactEvidence(
        evidence_id=record.evidence_id,
        tool_name=record.tool_name,
        status=record.tool_status,
        measurements={
            name: _context_measurement(measurement, record.evidence_id)
            for name, measurement in sorted(record.result.measurements.items())
        },
        interpretation_code=record.interpretation_code,
        method=record.result.method,
        code_version=record.result.provenance.code_version,
    )


def _canonical_json_bytes(payload: object) -> bytes:
    return json.dumps(
        payload,
        default=lambda value: (
            value.model_dump(mode="json") if isinstance(value, BaseModel) else str(value)
        ),
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def serialized_context_bytes(packet: AgentContextPacket) -> bytes:
    return _canonical_json_bytes(packet.model_dump(mode="json"))


def _ordered_evidence(
    state: InvestigationState, evidence: Sequence[EvidenceRecord]
) -> tuple[EvidenceRecord, ...]:
    by_id = {record.evidence_id: record for record in evidence}
    ordered = [by_id[evidence_id] for evidence_id in state.evidence_refs if evidence_id in by_id]
    referenced = {record.evidence_id for record in ordered}
    ordered.extend(
        sorted(
            (item for item in evidence if item.evidence_id not in referenced),
            key=lambda item: item.evidence_id,
        )
    )
    return tuple(ordered)


def _required_evidence_ids(
    state: InvestigationState, evidence: Sequence[EvidenceRecord]
) -> frozenset[str]:
    candidate_refs = {
        measurement.evidence_ref or candidate.evidence_refs[-1]
        for candidate in state.candidate_signals
        for measurement in candidate.measurements.values()
    }
    adverse = {
        record.evidence_id
        for record in evidence
        if record.interpretation_code in _DECISION_CRITICAL_INTERPRETATIONS
    }
    return frozenset(candidate_refs | adverse)


def _source_digest(state: InvestigationState, evidence: Sequence[EvidenceRecord]) -> str:
    durable = {
        "state": {
            "context_version": state.context_version,
            "evidence_refs": list(state.evidence_refs),
            "completed_tests": list(state.completed_tests),
            "active_hypotheses": list(state.active_hypotheses),
            "strongest_unresolved_alternative": state.strongest_unresolved_alternative,
        },
        "evidence": [
            {
                "evidence_id": record.evidence_id,
                "tool_name": record.tool_name,
                "status": str(record.tool_status),
                "interpretation_code": record.interpretation_code,
                "measurements": {
                    name: measurement.model_dump(mode="json")
                    for name, measurement in sorted(record.result.measurements.items())
                },
                "method": record.result.method,
                "code_version": record.result.provenance.code_version,
            }
            for record in evidence
        ],
    }
    return hashlib.sha256(_canonical_json_bytes(durable)).hexdigest()


def _finalize_packet(payload: dict[str, Any], source_digest: str) -> AgentContextPacket:
    fingerprint_payload = {**payload, "durable_source_digest": source_digest}
    fingerprint = hashlib.sha256(_canonical_json_bytes(fingerprint_payload)).hexdigest()
    size = 0
    packet: AgentContextPacket | None = None
    for _ in range(4):
        packet = AgentContextPacket.model_validate(
            {**payload, "context_fingerprint": fingerprint, "serialized_size_bytes": size}
        )
        updated_size = len(serialized_context_bytes(packet))
        if updated_size == size:
            break
        size = updated_size
    assert packet is not None
    if packet.serialized_size_bytes != size:
        packet = packet.model_copy(update={"serialized_size_bytes": size})
    return packet


def assemble_context(
    state: InvestigationState,
    evidence: list[EvidenceRecord] | tuple[EvidenceRecord, ...] = (),
    *,
    role: Literal["skeptic", "critic"] = "skeptic",
    available_experiments: tuple[str, ...] | None = None,
    adaptive_experiment_costs: dict[str, int] | None = None,
    experiment_specs: Iterable[_NamedExperimentSpec] = (),
    recent_limit: int = 6,
    proposed_decision: SkepticDecision | None = None,
    max_serialized_bytes: int = MAX_SERIALIZED_CONTEXT_BYTES,
) -> AgentContextPacket:
    """Rebuild a bounded, role-specific packet only from durable state and ledger records."""

    if recent_limit < 0:
        raise ValueError("recent_limit must be non-negative")
    if max_serialized_bytes <= 0 or max_serialized_bytes > MAX_SERIALIZED_CONTEXT_BYTES:
        raise ValueError(
            f"max_serialized_bytes must be between 1 and {MAX_SERIALIZED_CONTEXT_BYTES}"
        )
    candidate = state.candidate_signals[0] if state.candidate_signals else None
    candidate_packet = None
    if candidate is not None:
        fallback_ref = candidate.evidence_refs[-1]
        measurement_refs = tuple(
            dict.fromkeys(
                measurement.evidence_ref or fallback_ref
                for measurement in candidate.measurements.values()
            )
        )
        candidate_packet = CandidateContext(
            candidate_id=candidate.candidate_id,
            measurements={
                name: _context_measurement(measurement, fallback_ref)
                for name, measurement in sorted(candidate.measurements.items())
            },
            evidence_refs=measurement_refs,
        )

    ordered = _ordered_evidence(state, evidence)
    required_ids = _required_evidence_ids(state, ordered)
    required = [record for record in ordered if record.evidence_id in required_ids]
    optional = [record for record in reversed(ordered) if record.evidence_id not in required_ids]
    available_names = (
        available_experiments
        if available_experiments is not None
        else tuple(state.available_tests)
    )
    options = build_experiment_options(
        state,
        available_names=available_names,
        experiment_specs=experiment_specs,
        authoritative_costs=adaptive_experiment_costs,
    )
    costs = {option.action_name: option.deterministic_cost for option in options}
    active_hypotheses = tuple(dict.fromkeys(state.active_hypotheses))
    source_digest = _source_digest(state, ordered)

    def payload_for(
        selected: Sequence[EvidenceRecord], hypotheses: Sequence[str]
    ) -> dict[str, Any]:
        compact = tuple(_compact_evidence(record) for record in selected)
        selected_refs = tuple(record.evidence_id for record in selected)
        return {
            "role": role,
            "run_id": state.run_id,
            "step_id": f"step_{state.step_count:04d}",
            "opaque_target_id": state.opaque_target_id,
            "status": state.status,
            "candidate": candidate_packet,
            "evidence_refs": selected_refs,
            "completed_tests": tuple(state.completed_tests),
            "recent_evidence": compact,
            "active_hypotheses": tuple(hypotheses),
            "strongest_unresolved_alternative": state.strongest_unresolved_alternative,
            "available_experiments": options,
            # Kept as a compact compatibility index for existing scripted policies. The
            # typed options above remain the complete model-visible action contract.
            "adaptive_experiment_costs": costs,
            "proposed_decision": proposed_decision,
            "remaining_budgets": RemainingBudgets(
                steps=max(0, state.max_steps - state.step_count),
                model_calls=max(0, state.max_model_calls - state.model_call_count),
                tool_calls=max(0, state.max_tool_calls - state.tool_call_count),
                adaptive_experiments=max(
                    0, state.max_adaptive_experiments - state.adaptive_experiments_used
                ),
                critic_revisions=max(
                    0, state.max_critic_revisions - state.critic_revision_count
                ),
                transient_model_retries=max(
                    0, state.max_model_retries - state.model_retry_count
                ),
                adaptive_cost_units=int(_spec_value(
                    state,
                    "experiment_budget_units_remaining",
                    "adaptive_budget_units_remaining",
                    "adaptive_cost_units_remaining",
                    default=0,
                )),
            ),
            "context_version": state.context_version,
            "context_schema_version": CONTEXT_SCHEMA_VERSION,
            "provenance_version": CONTEXT_PROVENANCE_VERSION,
        }

    # Hypotheses other than the strongest named alternative are optional under pressure.
    hypotheses = list(active_hypotheses)
    packet = _finalize_packet(payload_for(required, hypotheses), source_digest)
    while len(serialized_context_bytes(packet)) > max_serialized_bytes and hypotheses:
        hypotheses.pop()
        packet = _finalize_packet(payload_for(required, hypotheses), source_digest)
    if len(serialized_context_bytes(packet)) > max_serialized_bytes:
        raise ContextSizeError(
            "required agent evidence cannot fit within the serialized context ceiling"
        )

    selected = list(required)
    optional_slots = max(0, recent_limit - len(required))
    for record in optional[:optional_slots]:
        candidate_selected = [*selected, record]
        candidate_selected.sort(key=lambda item: ordered.index(item))
        candidate_packet_result = _finalize_packet(
            payload_for(candidate_selected, hypotheses), source_digest
        )
        if len(serialized_context_bytes(candidate_packet_result)) <= max_serialized_bytes:
            selected = candidate_selected
            packet = candidate_packet_result

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
            raise RuntimeError(f"forbidden agent context field: {key}")
        if isinstance(value, dict):
            for child_key, child_value in value.items():
                inspect(child_value, str(child_key))
        elif isinstance(value, (list, tuple)):
            if len(value) >= 3 and all(
                isinstance(child, (int, float)) and not isinstance(child, bool)
                for child in value
            ):
                raise RuntimeError("agent context contains a raw numerical array")
            for child in value:
                inspect(child)
        elif isinstance(value, str):
            reject_unsafe_string(value)

    inspect(packet.model_dump(mode="json"))
