from __future__ import annotations

from typing import Any

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from exoswarm.domain.enums import ToolStatus
from exoswarm.domain.models import Measurement, Provenance, ScientificToolResult
from exoswarm.science.candidate_artifact import (
    CandidateArtifactError,
    CandidateArtifactRuntimeInputs,
    load_candidate_artifact,
)

_NEIGHBOR_METHOD = (
    "cached neighbor aperture-flux screening using flux_ratio=10^(-0.4*delta_magnitude)"
)
_CROWDSAP_METHOD = "cached SPOC CROWDSAP aggregate aperture-contamination screening"


class _StrictRuntimeModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class CachedNeighbor(_StrictRuntimeModel):
    neighbor_id: str = Field(min_length=1, max_length=128)
    separation_arcsec: float = Field(ge=0)
    delta_magnitude: float


class CachedNeighborContext(_StrictRuntimeModel):
    source_data_ref: str = Field(min_length=1)
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    magnitude_band: str = Field(min_length=1)
    search_radius_arcsec: float = Field(gt=0)
    aperture_radius_arcsec: float = Field(gt=0)
    neighbors: list[CachedNeighbor] = Field(default_factory=list, max_length=10_000)

    @model_validator(mode="after")
    def search_covers_aperture(self) -> CachedNeighborContext:
        if self.search_radius_arcsec < self.aperture_radius_arcsec:
            raise ValueError("neighbor search radius must cover the declared aperture")
        if any(
            neighbor.separation_arcsec > self.search_radius_arcsec
            for neighbor in self.neighbors
        ):
            raise ValueError("neighbor separation exceeds the cached search radius")
        if len({neighbor.neighbor_id for neighbor in self.neighbors}) != len(self.neighbors):
            raise ValueError("neighbor IDs must be unique")
        return self


class ContaminationRuntimeInputs(CandidateArtifactRuntimeInputs):
    neighbor_context: CachedNeighborContext | None = None


def _failure(
    run_id: str,
    action_id: str,
    target_id: str,
    reason: str,
    *,
    provenance: Provenance | None = None,
) -> ScientificToolResult:
    return ScientificToolResult(
        tool_name="contamination_screening",
        status=ToolStatus.PRECONDITION_FAILED,
        run_id=run_id,
        action_id=action_id,
        target_id=target_id,
        method=f"{_NEIGHBOR_METHOD}; {_CROWDSAP_METHOD}",
        parameters={},
        provenance=provenance
        or Provenance(
            code_version="exoswarm-api/0.1.0",
            source_data_ref="unavailable:invalid-contamination-input",
        ),
        reason=reason,
        suggested_alternatives=["centroid_localization"],
    )


def screen_contamination(
    run_id: str, action_id: str, target_id: str, parameters: dict[str, Any]
) -> ScientificToolResult:
    """Measure cached neighbor flux and whether a neighbor could reproduce the observed depth."""

    try:
        request = ContaminationRuntimeInputs.model_validate(parameters)
        candidate = load_candidate_artifact(request.candidate_artifact_path)
    except ValidationError:
        return _failure(
            run_id,
            action_id,
            target_id,
            "contamination_screening requires strict backend-owned candidate inputs",
        )
    except CandidateArtifactError as exc:
        return _failure(run_id, action_id, target_id, str(exc))

    if candidate.depth_fraction <= 0:
        return _failure(
            run_id,
            action_id,
            target_id,
            "contamination_screening requires a positive candidate depth",
            provenance=candidate.provenance,
        )

    context = request.neighbor_context
    if context is None:
        crowdsap = candidate.artifact.source.crowdsap
        if crowdsap is None:
            return _failure(
                run_id,
                action_id,
                target_id,
                "contamination_screening requires cached neighbor context or SPOC CROWDSAP",
                provenance=candidate.provenance,
            )
        contamination_fraction = 1.0 - crowdsap
        status = (
            ToolStatus.SUCCESS
            if contamination_fraction >= candidate.depth_fraction
            else ToolStatus.NO_EVIDENCE
        )
        code = (
            "CONTAMINATION_POSSIBLE"
            if status is ToolStatus.SUCCESS
            else "NO_CONTAMINATION_CAPACITY"
        )
        reason = (
            None
            if status is ToolStatus.SUCCESS
            else "SPOC aggregate aperture contamination is smaller than the candidate depth"
        )
        return ScientificToolResult(
            tool_name="contamination_screening",
            status=status,
            run_id=run_id,
            action_id=action_id,
            target_id=target_id,
            measurements={
                "spoc_crowdsap": Measurement(
                    value=crowdsap,
                    unit="target_flux_fraction_in_aperture",
                    evidence_ref=candidate.artifact_ref,
                ),
                "aperture_contamination_fraction": Measurement(
                    value=contamination_fraction,
                    unit="relative_flux_fraction",
                    evidence_ref=candidate.artifact_ref,
                ),
                "maximum_aggregate_contaminant_eclipse_depth": Measurement(
                    value=contamination_fraction,
                    unit="relative_flux_fraction",
                    evidence_ref=candidate.artifact_ref,
                ),
                "candidate_depth": Measurement(
                    value=candidate.depth_fraction,
                    unit="relative_flux_fraction",
                    uncertainty=candidate.depth_uncertainty_fraction,
                    evidence_ref=candidate.artifact_ref,
                ),
            },
            diagnostics={
                "interpretation_code": code,
                "contamination_mode": "SPOC_CROWDSAP",
                "candidate_artifact_sha256": candidate.artifact_sha256,
                "capacity_definition": (
                    "maximum aggregate contaminant eclipse assumes all non-target aperture flux "
                    "can disappear"
                ),
            },
            warnings=[
                "CROWDSAP is an aggregate aperture-crowding estimate; no source localization "
                "or centroid claim is made"
            ],
            method=_CROWDSAP_METHOD,
            parameters={},
            provenance=candidate.provenance,
            reason=reason,
        )

    in_aperture = [
        neighbor
        for neighbor in context.neighbors
        if neighbor.separation_arcsec <= context.aperture_radius_arcsec
    ]
    flux_ratios = np.asarray(
        [10.0 ** (-0.4 * neighbor.delta_magnitude) for neighbor in in_aperture],
        dtype=np.float64,
    )
    total_neighbor_flux_ratio = float(flux_ratios.sum()) if len(flux_ratios) else 0.0
    dilution_fraction = total_neighbor_flux_ratio / (1.0 + total_neighbor_flux_ratio)

    required_depths: list[tuple[CachedNeighbor, float, float]] = []
    for neighbor, flux_ratio in zip(in_aperture, flux_ratios, strict=True):
        required_eclipse_depth = candidate.depth_fraction * (
            1.0 + total_neighbor_flux_ratio
        ) / float(flux_ratio)
        required_depths.append((neighbor, float(flux_ratio), required_eclipse_depth))
    capable = [item for item in required_depths if item[2] <= 1.0]
    status = ToolStatus.SUCCESS if capable else ToolStatus.NO_EVIDENCE
    reason = (
        None
        if capable
        else "no cached in-aperture neighbor can reproduce the candidate depth at 100% eclipse"
    )

    evidence_ref = candidate.artifact_ref
    measurements: dict[str, Measurement] = {
        "cached_neighbor_count": Measurement(
            value=len(context.neighbors), unit="count", evidence_ref=evidence_ref
        ),
        "in_aperture_neighbor_count": Measurement(
            value=len(in_aperture), unit="count", evidence_ref=evidence_ref
        ),
        "depth_capable_neighbor_count": Measurement(
            value=len(capable), unit="count", evidence_ref=evidence_ref
        ),
        "total_neighbor_to_target_flux_ratio": Measurement(
            value=total_neighbor_flux_ratio,
            unit="flux_ratio",
            evidence_ref=evidence_ref,
        ),
        "neighbor_dilution_fraction": Measurement(
            value=dilution_fraction,
            unit="relative_flux_fraction",
            evidence_ref=evidence_ref,
        ),
        "candidate_depth": Measurement(
            value=candidate.depth_fraction,
            unit="relative_flux_fraction",
            uncertainty=candidate.depth_uncertainty_fraction,
            evidence_ref=evidence_ref,
        ),
    }
    if required_depths:
        best_neighbor, best_flux_ratio, minimum_required_depth = min(
            required_depths, key=lambda item: item[2]
        )
        measurements.update(
            {
                "brightest_in_aperture_neighbor_delta_magnitude": Measurement(
                    value=best_neighbor.delta_magnitude,
                    unit=f"mag_{context.magnitude_band}",
                    evidence_ref=evidence_ref,
                ),
                "brightest_in_aperture_neighbor_separation": Measurement(
                    value=best_neighbor.separation_arcsec,
                    unit="arcsec",
                    evidence_ref=evidence_ref,
                ),
                "brightest_in_aperture_neighbor_flux_ratio": Measurement(
                    value=best_flux_ratio, unit="flux_ratio", evidence_ref=evidence_ref
                ),
                "minimum_required_neighbor_eclipse_depth": Measurement(
                    value=minimum_required_depth,
                    unit="relative_flux_fraction",
                    evidence_ref=evidence_ref,
                ),
            }
        )

    provenance = candidate.provenance.model_copy(
        update={
            "input_artifact_refs": [
                *candidate.provenance.input_artifact_refs,
                context.source_data_ref,
            ]
        }
    )
    warnings = [
        "screen uses cached magnitudes and a circular aperture approximation; "
        "no centroid claim is made"
    ]
    if capable:
        warnings.append(
            "a depth-capable neighbor is evidence for follow-up, not source localization"
        )

    return ScientificToolResult(
        tool_name="contamination_screening",
        status=status,
        run_id=run_id,
        action_id=action_id,
        target_id=target_id,
        measurements=measurements,
        diagnostics={
            "interpretation_code": (
                "CONTAMINATION_POSSIBLE" if capable else "NO_CONTAMINATION_CAPACITY"
            ),
            "contamination_mode": "cached_neighbors",
            "magnitude_band": context.magnitude_band,
            "search_radius_arcsec": context.search_radius_arcsec,
            "aperture_radius_arcsec": context.aperture_radius_arcsec,
            "neighbor_source_sha256": context.source_sha256,
            "candidate_artifact_sha256": candidate.artifact_sha256,
            "depth_capable_definition": (
                "required intrinsic neighbor eclipse depth is <= 1.0 after aperture dilution"
            ),
        },
        warnings=warnings,
        method=_NEIGHBOR_METHOD,
        parameters={},
        provenance=provenance,
        reason=reason,
    )


__all__ = [
    "CachedNeighbor",
    "CachedNeighborContext",
    "ContaminationRuntimeInputs",
    "screen_contamination",
]
