from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import PurePosixPath
from typing import Any

from pydantic import Field

from exoswarm.domain.models import EvidenceRecord, InvestigationState, StrictModel


class ScientificOutcomeComparison(StrictModel):
    """Result-neutral comparison with generated identifiers and prose removed."""

    equivalent: bool
    mismatch_paths: list[str] = Field(default_factory=list)
    baseline: dict[str, Any]
    candidate: dict[str, Any]


_GENERATED_ACTION_ARTIFACT = re.compile(r"^action_[A-Za-z0-9_-]+(?P<suffix>\..+)$")


def _artifact_name(reference: str) -> str:
    name = PurePosixPath(reference.replace("\\", "/")).name
    match = _GENERATED_ACTION_ARTIFACT.fullmatch(name)
    if match is None:
        return name
    return f"<generated-action>{match.group('suffix')}"


def _diagnostic_projection(value: Any, *, key: str | None = None) -> Any:
    if isinstance(value, dict):
        return {
            item_key: _diagnostic_projection(item_value, key=item_key)
            for item_key, item_value in sorted(value.items())
        }
    if isinstance(value, list):
        return [_diagnostic_projection(item) for item in value]
    if isinstance(value, str) and key is not None and key.endswith("_artifact_ref"):
        return _artifact_name(value)
    return value


def _measurement_projection(measurement: Any) -> dict[str, Any]:
    return {
        "value": measurement.value,
        "unit": measurement.unit,
        "uncertainty": measurement.uncertainty,
        "tolerance": measurement.tolerance,
    }


def _evidence_projection(record: EvidenceRecord) -> dict[str, Any]:
    result = record.result
    provenance = result.provenance
    return {
        "tool_name": record.tool_name,
        "tool_status": record.tool_status.value,
        "interpretation_code": record.interpretation_code,
        "result": {
            "status": result.status.value,
            "measurements": {
                key: _measurement_projection(value)
                for key, value in sorted(result.measurements.items())
            },
            "diagnostics": _diagnostic_projection(result.diagnostics),
            "warnings": result.warnings,
            "method": result.method,
            "parameters": result.parameters,
            "suggested_alternatives": result.suggested_alternatives,
            "reason": result.reason,
            "provenance": {
                "input_artifacts": sorted(
                    _artifact_name(item) for item in provenance.input_artifact_refs
                ),
                "output_artifacts": sorted(
                    _artifact_name(item) for item in provenance.output_artifact_refs
                ),
                "code_version": provenance.code_version,
                "source_data_ref": provenance.source_data_ref,
                "source_sha256": provenance.source_sha256,
                "library_versions": dict(sorted(provenance.library_versions.items())),
            },
        },
    }


def scientific_outcome_projection(
    state: InvestigationState, evidence: Iterable[EvidenceRecord]
) -> dict[str, Any]:
    """Return only deterministic scientific and safety semantics for parity checks."""

    return {
        "terminal": {
            "status": state.status.value,
            "disposition": state.disposition.value if state.disposition else None,
            "lock_state": state.lock_state.value,
            "terminal_reason": state.terminal_reason,
        },
        "tests": sorted(state.completed_tests),
        "candidates": [
            {
                "measurements": {
                    key: _measurement_projection(value)
                    for key, value in sorted(candidate.measurements.items())
                }
            }
            for candidate in state.candidate_signals
        ],
        "budget": {
            "tool_calls": state.tool_call_count,
            "adaptive_experiments": state.adaptive_experiments_used,
            "adaptive_cost_used": state.adaptive_cost_units_used,
            "adaptive_cost_remaining": state.adaptive_cost_units_remaining,
            "max_adaptive_experiments": state.max_adaptive_experiments,
            "max_adaptive_cost": state.max_adaptive_cost_units,
            "max_tool_calls": state.max_tool_calls,
        },
        "tool_sequence": [
            {
                "tool_name": item.tool_name,
                "parameters": item.parameters,
                "status": item.status.value,
                "adaptive": item.adaptive,
                "adaptive_cost_units": item.adaptive_cost_units,
                "result_status": item.result_status.value if item.result_status else None,
                "failure_kind": item.failure_kind.value if item.failure_kind else None,
            }
            for item in state.tool_executions
        ],
        "evidence": [_evidence_projection(record) for record in evidence],
        "failures": [
            {
                "kind": item.kind.value,
                "recoverable": item.recoverable,
                "retry_count": item.retry_count,
            }
            for item in state.failures
        ],
        "raw_light_curve_samples_sent": (
            state.inference_summary.raw_light_curve_samples_sent
        ),
    }


def _mismatch_paths(left: Any, right: Any, path: str = "$") -> list[str]:
    if type(left) is not type(right):
        return [path]
    if isinstance(left, dict):
        keys = sorted(set(left) | set(right))
        return [
            mismatch
            for key in keys
            for mismatch in (
                [f"{path}.{key}"]
                if key not in left or key not in right
                else _mismatch_paths(left[key], right[key], f"{path}.{key}")
            )
        ]
    if isinstance(left, list):
        mismatches: list[str] = []
        if len(left) != len(right):
            mismatches.append(f"{path}.length")
        for index, (left_item, right_item) in enumerate(zip(left, right, strict=False)):
            mismatches.extend(
                _mismatch_paths(left_item, right_item, f"{path}[{index}]")
            )
        return mismatches
    return [] if left == right else [path]


def compare_scientific_outcomes(
    baseline_state: InvestigationState,
    baseline_evidence: Iterable[EvidenceRecord],
    candidate_state: InvestigationState,
    candidate_evidence: Iterable[EvidenceRecord],
) -> ScientificOutcomeComparison:
    baseline = scientific_outcome_projection(baseline_state, baseline_evidence)
    candidate = scientific_outcome_projection(candidate_state, candidate_evidence)
    mismatches = _mismatch_paths(baseline, candidate)
    return ScientificOutcomeComparison(
        equivalent=not mismatches,
        mismatch_paths=mismatches,
        baseline=baseline,
        candidate=candidate,
    )


__all__ = [
    "ScientificOutcomeComparison",
    "compare_scientific_outcomes",
    "scientific_outcome_projection",
]
