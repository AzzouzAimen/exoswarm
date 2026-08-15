from __future__ import annotations

from typing import Any

import numpy as np
from pydantic import ValidationError

from exoswarm.domain.enums import ToolStatus
from exoswarm.domain.models import Measurement, Provenance, ScientificToolResult
from exoswarm.science.candidate_artifact import (
    CandidateArtifactError,
    CandidateArtifactRuntimeInputs,
    load_candidate_artifact,
)

_METHOD = (
    "deterministic circular-phase box scan outside primary transit; "
    "robust MAD-plus-reported-error significance; threshold=5 sigma"
)


def _failure(
    run_id: str,
    action_id: str,
    target_id: str,
    reason: str,
    *,
    provenance: Provenance | None = None,
) -> ScientificToolResult:
    return ScientificToolResult(
        tool_name="secondary_eclipse",
        status=ToolStatus.PRECONDITION_FAILED,
        run_id=run_id,
        action_id=action_id,
        target_id=target_id,
        method=_METHOD,
        parameters={},
        provenance=provenance
        or Provenance(
            code_version="exoswarm-api/0.1.0",
            source_data_ref="unavailable:invalid-candidate-artifact",
        ),
        reason=reason,
        suggested_alternatives=["harmonic_test"],
    )


def _circular_distance(phases: np.ndarray, center: float) -> np.ndarray:
    return np.abs((phases - center + 0.5) % 1.0 - 0.5)


def search_secondary(
    run_id: str, action_id: str, target_id: str, parameters: dict[str, Any]
) -> ScientificToolResult:
    """Search non-primary orbital phases for the strongest same-duration flux decrement."""

    try:
        request = CandidateArtifactRuntimeInputs.model_validate(parameters)
        candidate = load_candidate_artifact(request.candidate_artifact_path)
    except ValidationError:
        return _failure(
            run_id,
            action_id,
            target_id,
            "secondary_eclipse requires a strict backend-owned candidate artifact input",
        )
    except CandidateArtifactError as exc:
        return _failure(run_id, action_id, target_id, str(exc))

    baseline_days = float(candidate.time_btjd[-1] - candidate.time_btjd[0])
    if baseline_days < 2.0 * candidate.period_days:
        return _failure(
            run_id,
            action_id,
            target_id,
            "secondary_eclipse requires an observation baseline spanning at least 2 periods",
            provenance=candidate.provenance,
        )

    phases = ((candidate.time_btjd - candidate.epoch_btjd) / candidate.period_days) % 1.0
    duration_phase = candidate.duration_days / candidate.period_days
    primary = _circular_distance(phases, 0.0) <= 0.75 * duration_phase
    baseline_mask = ~primary
    if int(baseline_mask.sum()) < 20:
        return _failure(
            run_id,
            action_id,
            target_id,
            "secondary_eclipse has fewer than 20 out-of-primary samples",
            provenance=candidate.provenance,
        )

    baseline_flux = candidate.relative_flux[baseline_mask]
    baseline_errors = candidate.relative_flux_error[baseline_mask]
    baseline_level = float(np.median(baseline_flux))
    robust_scatter = float(
        1.4826 * np.median(np.abs(baseline_flux - baseline_level))
    )
    noise_fraction = max(robust_scatter, float(np.median(baseline_errors)))
    if not np.isfinite(noise_fraction) or noise_fraction <= 0:
        return _failure(
            run_id,
            action_id,
            target_id,
            "secondary_eclipse could not estimate a positive finite noise scale",
            provenance=candidate.provenance,
        )

    cadence_phase = (
        float(np.median(np.diff(candidate.time_btjd))) / candidate.period_days
    )
    grid_step = max(duration_phase / 4.0, cadence_phase, 1.0 / 4096.0)
    exclusion_phase = max(1.5 * duration_phase, 0.05)
    centers = np.arange(exclusion_phase, 1.0 - exclusion_phase + 0.5 * grid_step, grid_step)

    best: tuple[float, float, float, int] | None = None
    for center in centers:
        event = _circular_distance(phases, float(center)) <= 0.5 * duration_phase
        event &= ~primary
        count = int(event.sum())
        if count < 3:
            continue
        weights = 1.0 / np.square(candidate.relative_flux_error[event])
        event_level = float(np.average(candidate.relative_flux[event], weights=weights))
        depth = baseline_level - event_level
        uncertainty = noise_fraction * np.sqrt(1.0 / count + 1.0 / int(baseline_mask.sum()))
        significance = depth / uncertainty
        if best is None or significance > best[2]:
            best = (float(center % 1.0), depth, float(significance), count)

    if best is None:
        return _failure(
            run_id,
            action_id,
            target_id,
            "secondary_eclipse found no phase box with at least 3 samples",
            provenance=candidate.provenance,
        )

    secondary_phase, depth, significance, sample_count = best
    uncertainty = depth / significance if significance != 0 else noise_fraction * np.sqrt(
        1.0 / sample_count + 1.0 / int(baseline_mask.sum())
    )
    threshold_sigma = 5.0
    detected = bool(depth > 0 and significance >= threshold_sigma)
    status = ToolStatus.SUCCESS if detected else ToolStatus.NO_EVIDENCE
    reason = None if detected else "no secondary-like decrement reached 5 sigma"
    evidence_ref = candidate.artifact_ref

    return ScientificToolResult(
        tool_name="secondary_eclipse",
        status=status,
        run_id=run_id,
        action_id=action_id,
        target_id=target_id,
        measurements={
            "strongest_secondary_phase": Measurement(
                value=secondary_phase,
                unit="orbital_phase",
                tolerance=0.5 * grid_step,
                evidence_ref=evidence_ref,
            ),
            "strongest_secondary_time_offset": Measurement(
                value=secondary_phase * candidate.period_days,
                unit="d",
                tolerance=0.5 * grid_step * candidate.period_days,
                evidence_ref=evidence_ref,
            ),
            "strongest_secondary_depth": Measurement(
                value=depth,
                unit="relative_flux_fraction",
                uncertainty=abs(float(uncertainty)),
                evidence_ref=evidence_ref,
            ),
            "strongest_secondary_significance": Measurement(
                value=significance, unit="sigma", evidence_ref=evidence_ref
            ),
            "secondary_in_event_samples": Measurement(
                value=sample_count, unit="count", evidence_ref=evidence_ref
            ),
        },
        diagnostics={
            "interpretation_code": (
                "SECONDARY_ECLIPSE_DETECTED" if detected else "NO_SECONDARY_ECLIPSE"
            ),
            "candidate_period_days": candidate.period_days,
            "candidate_epoch_btjd": candidate.epoch_btjd,
            "box_duration_hours": candidate.duration_days * 24.0,
            "phase_convention": "primary mid-transit is phase 0; phase increases in [0, 1)",
            "primary_exclusion_half_width_phase": exclusion_phase,
            "phase_grid_step": grid_step,
            "tested_phase_count": int(len(centers)),
            "baseline_sample_count": int(baseline_mask.sum()),
            "robust_noise_fraction": noise_fraction,
            "detection_threshold_sigma": threshold_sigma,
            "candidate_artifact_sha256": candidate.artifact_sha256,
        },
        warnings=["reported significance is a diagnostic statistic, not a false-alarm probability"],
        method=_METHOD,
        parameters={},
        provenance=candidate.provenance,
        reason=reason,
    )
