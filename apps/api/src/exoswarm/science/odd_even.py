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
    phase_distance,
)

_METHOD = (
    "per-transit inverse-variance weighted odd/even box-depth comparison; "
    "uncertainty=max(propagated error, event-depth standard error); threshold=3 sigma"
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
        tool_name="odd_even",
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
        suggested_alternatives=["secondary_eclipse", "harmonic_test"],
    )


def compare_odd_even(
    run_id: str, action_id: str, target_id: str, parameters: dict[str, Any]
) -> ScientificToolResult:
    """Compare aggregate depths of alternating transit events from a cached candidate."""

    try:
        request = CandidateArtifactRuntimeInputs.model_validate(parameters)
        candidate = load_candidate_artifact(request.candidate_artifact_path)
    except ValidationError:
        return _failure(
            run_id,
            action_id,
            target_id,
            "odd_even requires a strict backend-owned candidate artifact input",
        )
    except CandidateArtifactError as exc:
        return _failure(run_id, action_id, target_id, str(exc))

    centered = phase_distance(
        candidate.time_btjd, candidate.epoch_btjd, candidate.period_days
    )
    in_transit = np.abs(centered) <= 0.5 * candidate.duration_days
    transit_numbers = np.rint(
        (candidate.time_btjd[in_transit] - candidate.epoch_btjd) / candidate.period_days
    ).astype(np.int64)
    unique_events = np.unique(transit_numbers)
    odd_events = unique_events[unique_events % 2 != 0]
    even_events = unique_events[unique_events % 2 == 0]
    if len(unique_events) < 4 or len(odd_events) < 2 or len(even_events) < 2:
        return _failure(
            run_id,
            action_id,
            target_id,
            (
                "odd_even requires at least 4 usable transits with 2 per parity; "
                f"found {len(unique_events)} total, {len(odd_events)} odd, "
                f"and {len(even_events)} even"
            ),
            provenance=candidate.provenance,
        )

    flux = candidate.relative_flux[in_transit]
    errors = candidate.relative_flux_error[in_transit]

    def depth_for(parity: int) -> tuple[float, float, float, float, int]:
        event_depths: list[float] = []
        event_uncertainties: list[float] = []
        sample_count = 0
        for transit_number in unique_events[unique_events % 2 == parity]:
            selected = transit_numbers == transit_number
            sample_count += int(selected.sum())
            sample_weights = 1.0 / np.square(errors[selected])
            event_flux = float(np.average(flux[selected], weights=sample_weights))
            event_depths.append(1.0 - event_flux)
            event_uncertainties.append(float(np.sqrt(1.0 / sample_weights.sum())))

        depths = np.asarray(event_depths, dtype=np.float64)
        uncertainties = np.asarray(event_uncertainties, dtype=np.float64)
        event_weights = 1.0 / np.square(uncertainties)
        depth = float(np.average(depths, weights=event_weights))
        formal_uncertainty = float(np.sqrt(1.0 / event_weights.sum()))
        empirical_standard_error = float(np.std(depths, ddof=1) / np.sqrt(len(depths)))
        uncertainty = max(formal_uncertainty, empirical_standard_error)
        return (
            depth,
            uncertainty,
            formal_uncertainty,
            empirical_standard_error,
            sample_count,
        )

    (
        odd_depth,
        odd_uncertainty,
        odd_formal_uncertainty,
        odd_empirical_standard_error,
        odd_samples,
    ) = depth_for(1)
    (
        even_depth,
        even_uncertainty,
        even_formal_uncertainty,
        even_empirical_standard_error,
        even_samples,
    ) = depth_for(0)
    difference = odd_depth - even_depth
    difference_uncertainty = float(np.hypot(odd_uncertainty, even_uncertainty))
    significance = abs(difference) / difference_uncertainty
    threshold_sigma = 3.0
    mismatch_detected = bool(significance >= threshold_sigma)
    status = ToolStatus.SUCCESS if mismatch_detected else ToolStatus.NO_EVIDENCE
    reason = None if mismatch_detected else "no odd/even depth mismatch reached 3 sigma"
    warnings: list[str] = []
    if odd_depth <= 0 or even_depth <= 0:
        warnings.append("one parity has a non-positive fitted box depth")

    evidence_ref = candidate.artifact_ref
    return ScientificToolResult(
        tool_name="odd_even",
        status=status,
        run_id=run_id,
        action_id=action_id,
        target_id=target_id,
        measurements={
            "odd_depth": Measurement(
                value=odd_depth,
                unit="relative_flux_fraction",
                uncertainty=odd_uncertainty,
                evidence_ref=evidence_ref,
            ),
            "even_depth": Measurement(
                value=even_depth,
                unit="relative_flux_fraction",
                uncertainty=even_uncertainty,
                evidence_ref=evidence_ref,
            ),
            "odd_minus_even_depth": Measurement(
                value=difference,
                unit="relative_flux_fraction",
                uncertainty=difference_uncertainty,
                evidence_ref=evidence_ref,
            ),
            "absolute_difference_significance": Measurement(
                value=significance,
                unit="sigma",
                evidence_ref=evidence_ref,
            ),
            "odd_depth_formal_uncertainty": Measurement(
                value=odd_formal_uncertainty,
                unit="relative_flux_fraction",
                evidence_ref=evidence_ref,
            ),
            "odd_depth_empirical_standard_error": Measurement(
                value=odd_empirical_standard_error,
                unit="relative_flux_fraction",
                evidence_ref=evidence_ref,
            ),
            "even_depth_formal_uncertainty": Measurement(
                value=even_formal_uncertainty,
                unit="relative_flux_fraction",
                evidence_ref=evidence_ref,
            ),
            "even_depth_empirical_standard_error": Measurement(
                value=even_empirical_standard_error,
                unit="relative_flux_fraction",
                evidence_ref=evidence_ref,
            ),
            "usable_transits": Measurement(
                value=int(len(unique_events)), unit="count", evidence_ref=evidence_ref
            ),
        },
        diagnostics={
            "interpretation_code": (
                "ODD_EVEN_MISMATCH" if mismatch_detected else "ODD_EVEN_CONSISTENT"
            ),
            "candidate_period_days": candidate.period_days,
            "candidate_epoch_btjd": candidate.epoch_btjd,
            "candidate_duration_hours": candidate.duration_days * 24.0,
            "odd_transit_count": int(len(odd_events)),
            "even_transit_count": int(len(even_events)),
            "odd_in_transit_sample_count": odd_samples,
            "even_in_transit_sample_count": even_samples,
            "uncertainty_model": (
                "maximum of propagated reported-flux error and empirical per-event "
                "depth standard error for each parity"
            ),
            "parity_convention": (
                "transit number is round((time_btjd - recovered_epoch_btjd) / period_days); "
                "zero is even"
            ),
            "mismatch_threshold_sigma": threshold_sigma,
            "candidate_artifact_sha256": candidate.artifact_sha256,
        },
        warnings=warnings,
        method=_METHOD,
        parameters={},
        provenance=candidate.provenance,
        reason=reason,
    )
