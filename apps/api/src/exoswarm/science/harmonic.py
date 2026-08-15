from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from astropy import units as u
from astropy.timeseries import BoxLeastSquares
from pydantic import ValidationError

from exoswarm.domain.enums import ToolStatus
from exoswarm.domain.models import Measurement, Provenance, ScientificToolResult
from exoswarm.science.candidate_artifact import (
    CandidateArtifactError,
    CandidateArtifactRuntimeInputs,
    load_candidate_artifact,
)


@dataclass(frozen=True, slots=True)
class HarmonicRelation:
    relation: str
    ratio: float
    relative_error: float


def classify_harmonic_relation(
    candidate_period_days: float,
    reference_period_days: float,
    *,
    relative_tolerance: float = 0.02,
) -> HarmonicRelation:
    """Classify equality, half-period, or double-period agreement explicitly."""

    if candidate_period_days <= 0 or reference_period_days <= 0:
        raise ValueError("periods must be positive")
    if relative_tolerance <= 0:
        raise ValueError("relative tolerance must be positive")
    ratio = candidate_period_days / reference_period_days
    relations = {"HALF_PERIOD": 0.5, "SAME_PERIOD": 1.0, "DOUBLE_PERIOD": 2.0}
    relation, expected = min(relations.items(), key=lambda item: abs(ratio - item[1]))
    relative_error = abs(ratio - expected) / expected
    if relative_error > relative_tolerance:
        relation = "NONE"
    return HarmonicRelation(relation=relation, ratio=ratio, relative_error=relative_error)


_METHOD = "Astropy BoxLeastSquares fixed trials at P/2, P, and 2P; objective=snr"


def _failure(
    run_id: str,
    action_id: str,
    target_id: str,
    reason: str,
    *,
    provenance: Provenance | None = None,
) -> ScientificToolResult:
    return ScientificToolResult(
        tool_name="harmonic_test",
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
        suggested_alternatives=["odd_even", "secondary_eclipse"],
    )


def test_harmonics(
    run_id: str, action_id: str, target_id: str, parameters: dict[str, Any]
) -> ScientificToolResult:
    """Measure the same box-search statistic at the candidate's three principal aliases."""

    try:
        request = CandidateArtifactRuntimeInputs.model_validate(parameters)
        candidate = load_candidate_artifact(request.candidate_artifact_path)
    except ValidationError:
        return _failure(
            run_id,
            action_id,
            target_id,
            "harmonic_test requires a strict backend-owned candidate artifact input",
        )
    except CandidateArtifactError as exc:
        return _failure(run_id, action_id, target_id, str(exc))

    baseline_days = float(candidate.time_btjd[-1] - candidate.time_btjd[0])
    if baseline_days < 2.0 * candidate.period_days:
        return _failure(
            run_id,
            action_id,
            target_id,
            "harmonic_test requires a baseline spanning at least 2 candidate periods",
            provenance=candidate.provenance,
        )

    model = BoxLeastSquares(
        candidate.time_btjd * u.day,
        candidate.relative_flux * u.dimensionless_unscaled,
        dy=candidate.relative_flux_error * u.dimensionless_unscaled,
    )
    configured_durations = (
        np.asarray(candidate.artifact.bls.parameters.durations_hours, dtype=np.float64)
        / 24.0
    )
    trials: dict[str, dict[str, float]] = {}
    for label, factor in (("half_period", 0.5), ("same_period", 1.0), ("double_period", 2.0)):
        trial_period = candidate.period_days * factor
        durations = configured_durations[configured_durations < trial_period]
        if len(durations) == 0:
            return _failure(
                run_id,
                action_id,
                target_id,
                f"harmonic_test has no valid duration for {label}",
                provenance=candidate.provenance,
            )
        try:
            result = model.power(
                np.asarray([trial_period]) * u.day,
                durations * u.day,
                objective="snr",
            )
            values = {
                "period_days": trial_period,
                "depth_fraction": float(np.asarray(result.depth.value)[0]),
                "depth_uncertainty_fraction": float(np.asarray(result.depth_err.value)[0]),
                "depth_snr": float(np.asarray(result.depth_snr.value)[0]),
                "duration_hours": float(np.asarray(result.duration.to_value(u.hour))[0]),
                "epoch_btjd": float(np.asarray(result.transit_time.to_value(u.day))[0]),
            }
        except (TypeError, ValueError, ZeroDivisionError, IndexError):
            return _failure(
                run_id,
                action_id,
                target_id,
                f"Astropy BLS rejected the {label} trial",
                provenance=candidate.provenance,
            )
        if not all(np.isfinite(value) for value in values.values()):
            return _failure(
                run_id,
                action_id,
                target_id,
                f"{label} trial produced non-finite measurements",
                provenance=candidate.provenance,
            )
        trials[label] = values

    alternative_label = max(
        ("half_period", "double_period"), key=lambda label: trials[label]["depth_snr"]
    )
    alternative_advantage = (
        trials[alternative_label]["depth_snr"] - trials["same_period"]["depth_snr"]
    )
    threshold = 1.0
    alternative_stronger = bool(alternative_advantage >= threshold)
    status = ToolStatus.SUCCESS if alternative_stronger else ToolStatus.NO_EVIDENCE
    reason = (
        None
        if alternative_stronger
        else "neither P/2 nor 2P exceeded the P trial by the declared SNR margin"
    )
    evidence_ref = candidate.artifact_ref
    measurements: dict[str, Measurement] = {}
    for label, values in trials.items():
        measurements[f"{label}_period"] = Measurement(
            value=values["period_days"], unit="d", evidence_ref=evidence_ref
        )
        measurements[f"{label}_depth"] = Measurement(
            value=values["depth_fraction"],
            unit="relative_flux_fraction",
            uncertainty=values["depth_uncertainty_fraction"],
            evidence_ref=evidence_ref,
        )
        measurements[f"{label}_snr"] = Measurement(
            value=values["depth_snr"], unit="dimensionless", evidence_ref=evidence_ref
        )
        measurements[f"{label}_duration"] = Measurement(
            value=values["duration_hours"], unit="h", evidence_ref=evidence_ref
        )
    measurements["strongest_alternative_snr_advantage"] = Measurement(
        value=alternative_advantage, unit="dimensionless", evidence_ref=evidence_ref
    )

    return ScientificToolResult(
        tool_name="harmonic_test",
        status=status,
        run_id=run_id,
        action_id=action_id,
        target_id=target_id,
        measurements=measurements,
        diagnostics={
            "interpretation_code": (
                "HARMONIC_ALIAS_PREFERRED"
                if alternative_stronger
                else "CANDIDATE_PERIOD_PREFERRED"
            ),
            "candidate_period_days": candidate.period_days,
            "trial_factors": {"half_period": 0.5, "same_period": 1.0, "double_period": 2.0},
            "strongest_alternative": alternative_label,
            "alternative_snr_advantage_threshold": threshold,
            "trial_epochs_btjd": {
                label: values["epoch_btjd"] for label, values in trials.items()
            },
            "epoch_convention": "BTJD/TDB mid-event time returned by Astropy BoxLeastSquares",
            "candidate_artifact_sha256": candidate.artifact_sha256,
        },
        warnings=["fixed-trial BLS SNR differences are diagnostic, not calibrated odds"],
        method=_METHOD,
        parameters={},
        provenance=candidate.provenance,
        reason=reason,
    )
