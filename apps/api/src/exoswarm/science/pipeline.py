from __future__ import annotations

import hashlib
import json
import re
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from exoswarm.domain.enums import ToolStatus
from exoswarm.domain.models import (
    EvidenceRecord,
    Measurement,
    Provenance,
    ScientificToolResult,
)
from exoswarm.investigation.evidence import JsonlEvidenceLedger
from exoswarm.science.bls import BlsSearchConfig, BlsSearchError, search_lightcurve_bls
from exoswarm.science.io import (
    CachedLightCurveError,
    CachedLightCurvePreconditionError,
    CachedTessLightCurve,
    load_cached_tess_fits,
)
from exoswarm.science.preprocessing import (
    PreprocessedLightCurve,
    PreprocessingConfig,
    PreprocessingError,
    preprocess_lightcurve,
)
from exoswarm.science.transit import phase_fold

CODE_VERSION = "exoswarm-api/0.1.0"
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


class _StrictRequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PreprocessingParameters(_StrictRequestModel):
    quality_bitmask: int = Field(default=175, ge=0)
    outlier_sigma: float = Field(default=8.0, gt=0)
    detrend_window_days: float = Field(default=1.0, gt=0)
    gap_threshold_cadences: float = Field(default=5.0, gt=0)
    minimum_samples: int = Field(default=200, ge=20)


class BlsParameters(_StrictRequestModel):
    minimum_period_days: float = Field(default=0.5, gt=0)
    maximum_period_days: float | None = Field(default=None, gt=0)
    durations_hours: tuple[float, ...] = (1.5, 2.0, 3.0, 4.5, 6.0)
    frequency_factor: float = Field(default=1.0, gt=0)
    minimum_snr: float = Field(default=6.0, gt=0)
    minimum_transits: int = Field(default=3, ge=2)


class CandidateAnalysisRequest(_StrictRequestModel):
    cached_path: Path
    artifact_dir: Path
    ledger_path: Path
    step_id: str = Field(min_length=1)
    preprocessing: PreprocessingParameters = Field(default_factory=PreprocessingParameters)
    search: BlsParameters = Field(default_factory=BlsParameters)


def _library_versions() -> dict[str, str]:
    versions: dict[str, str] = {}
    for package in ("astropy", "lightkurve", "numpy", "scipy"):
        try:
            versions[package] = version(package)
        except PackageNotFoundError:
            versions[package] = "not-installed"
    return versions


def _safe_parameters(request: CandidateAnalysisRequest | None) -> dict[str, Any]:
    if request is None:
        return {}
    return {
        "preprocessing": request.preprocessing.model_dump(mode="json"),
        "search": request.search.model_dump(mode="json"),
    }


def _provenance(
    observation: CachedTessLightCurve | None,
    *,
    output_artifact_refs: list[str] | None = None,
) -> Provenance:
    if observation is None:
        return Provenance(
            code_version=CODE_VERSION,
            source_data_ref="unavailable:invalid-cached-input",
            library_versions=_library_versions(),
        )
    return Provenance(
        input_artifact_refs=[observation.source_data_ref],
        output_artifact_refs=output_artifact_refs or [],
        code_version=CODE_VERSION,
        source_data_ref=observation.source_data_ref,
        source_sha256=observation.source_sha256,
        library_versions=_library_versions(),
    )


def _source_diagnostics(observation: CachedTessLightCurve) -> dict[str, Any]:
    return {
        "sector": observation.sector,
        "cadence_seconds": observation.cadence_seconds,
        "time_system": observation.time_system,
        "time_unit": observation.time_unit,
        "epoch_convention": f"BTJD = BJD(TDB) - {observation.bjd_reference:.1f}",
        "bjd_reference": observation.bjd_reference,
        "input_flux_unit": observation.flux_unit,
        "source_size_bytes": observation.source_size_bytes,
        "fits_checksum": observation.fits_checksum,
        "fits_datasum": observation.fits_datasum,
    }


def _failure_result(
    *,
    status: ToolStatus,
    run_id: str,
    action_id: str,
    target_id: str,
    reason: str,
    request: CandidateAnalysisRequest | None,
    observation: CachedTessLightCurve | None = None,
    diagnostics: dict[str, Any] | None = None,
) -> ScientificToolResult:
    return ScientificToolResult(
        tool_name="search_bls",
        status=status,
        run_id=run_id,
        action_id=action_id,
        target_id=target_id,
        diagnostics=diagnostics or {},
        method="Astropy BoxLeastSquares with deterministic ExoSwarm preprocessing",
        parameters=_safe_parameters(request),
        provenance=_provenance(observation),
        reason=reason,
    )


def _artifact_payload(
    observation: CachedTessLightCurve,
    prepared: PreprocessedLightCurve,
    request: CandidateAnalysisRequest,
    *,
    period_grid_days: np.ndarray,
    periodogram_snr: np.ndarray,
    folded: dict[str, list[float]] | None,
) -> dict[str, Any]:
    return {
        "schema_version": "1",
        "source": {
            "source_data_ref": observation.source_data_ref,
            "source_sha256": observation.source_sha256,
            **_source_diagnostics(observation),
        },
        "processing": {
            **request.preprocessing.model_dump(mode="json"),
            "normalization_flux": prepared.normalization_flux,
            "normalization_flux_unit": observation.flux_unit,
            "detrend_window_samples": prepared.detrend_window_samples,
            "quality_removed_indices": np.flatnonzero(prepared.quality_removed).tolist(),
            "invalid_removed_indices": np.flatnonzero(prepared.invalid_removed).tolist(),
            "outlier_removed_indices": np.flatnonzero(prepared.outlier_removed).tolist(),
            "retained_source_indices": prepared.source_indices.tolist(),
        },
        "cleaned_lightcurve": {
            "time_btjd": prepared.time_btjd.tolist(),
            "relative_flux": prepared.relative_flux.tolist(),
            "relative_flux_error": prepared.relative_flux_error.tolist(),
            "trend": prepared.trend.tolist(),
            "units": {
                "time": "BTJD",
                "relative_flux": "fraction",
                "relative_flux_error": "fraction",
                "trend": "dimensionless",
            },
        },
        "bls": {
            "parameters": request.search.model_dump(mode="json"),
            "period_grid_days": period_grid_days.tolist(),
            "periodogram_depth_snr": periodogram_snr.tolist(),
        },
        "phase_folded": folded,
        "library_versions": _library_versions(),
        "code_version": CODE_VERSION,
    }


def _write_artifact(
    artifact_dir: Path,
    action_id: str,
    payload: dict[str, Any],
) -> tuple[str, Path]:
    if not _SAFE_ID.fullmatch(action_id):
        raise ValueError("action_id is not safe for an artifact filename")
    artifact_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{action_id}.candidate-search.json"
    artifact_path = artifact_dir / filename
    content = (
        json.dumps(payload, allow_nan=False, separators=(",", ":"), sort_keys=True) + "\n"
    ).encode()
    if artifact_path.exists():
        if artifact_path.read_bytes() != content:
            raise ValueError("existing candidate artifact differs from deterministic output")
    else:
        artifact_path.write_bytes(content)
    return f"artifacts/{filename}", artifact_path


def _append_evidence(
    result: ScientificToolResult,
    *,
    ledger_path: Path,
    step_id: str,
) -> None:
    canonical = json.dumps(
        result.model_dump(mode="json"), separators=(",", ":"), sort_keys=True
    ).encode()
    evidence_id = f"evidence_{hashlib.sha256(canonical).hexdigest()[:20]}"
    JsonlEvidenceLedger(ledger_path).append(
        EvidenceRecord(
            evidence_id=evidence_id,
            run_id=result.run_id,
            step_id=step_id,
            action_id=result.action_id,
            opaque_target_id=result.target_id,
            tool_name=result.tool_name,
            tool_status=result.status,
            result=result,
        )
    )


def analyze_cached_candidate(
    *,
    run_id: str,
    action_id: str,
    target_id: str,
    parameters: dict[str, Any],
) -> ScientificToolResult:
    """Run the cached FITS-to-candidate slice and append its typed result to evidence JSONL."""

    request: CandidateAnalysisRequest | None = None
    observation: CachedTessLightCurve | None = None
    try:
        request = CandidateAnalysisRequest.model_validate(parameters)
    except ValidationError:
        return _failure_result(
            status=ToolStatus.PRECONDITION_FAILED,
            run_id=run_id,
            action_id=action_id,
            target_id=target_id,
            reason="candidate analysis parameters do not satisfy the typed request contract",
            request=None,
        )

    try:
        observation = load_cached_tess_fits(request.cached_path)
        if not request.search.durations_hours:
            raise BlsSearchError("at least one transit duration is required")
        longest_duration_days = max(request.search.durations_hours) / 24.0
        if request.preprocessing.detrend_window_days < 3.0 * longest_duration_days:
            raise PreprocessingError(
                "detrend window must span at least three times the longest tested duration"
            )
        preprocessing_config = PreprocessingConfig(**request.preprocessing.model_dump())
        prepared = preprocess_lightcurve(observation, preprocessing_config)
        search_config = BlsSearchConfig(**request.search.model_dump())
        outcome = search_lightcurve_bls(
            prepared,
            cadence_seconds=observation.cadence_seconds,
            config=search_config,
        )
    except CachedLightCurvePreconditionError as exc:
        result = _failure_result(
            status=ToolStatus.PRECONDITION_FAILED,
            run_id=run_id,
            action_id=action_id,
            target_id=target_id,
            reason=str(exc),
            request=request,
            observation=observation,
            diagnostics={"failure_stage": "ingestion_contract"},
        )
        _append_evidence(result, ledger_path=request.ledger_path, step_id=request.step_id)
        return result
    except (FileNotFoundError, CachedLightCurveError) as exc:
        result = _failure_result(
            status=ToolStatus.FAILED,
            run_id=run_id,
            action_id=action_id,
            target_id=target_id,
            reason=(
                str(exc)
                if isinstance(exc, CachedLightCurveError)
                else "cached input was not found"
            ),
            request=request,
            observation=observation,
            diagnostics={"failure_stage": "ingestion"},
        )
        _append_evidence(result, ledger_path=request.ledger_path, step_id=request.step_id)
        return result
    except (PreprocessingError, BlsSearchError) as exc:
        result = _failure_result(
            status=ToolStatus.PRECONDITION_FAILED,
            run_id=run_id,
            action_id=action_id,
            target_id=target_id,
            reason=str(exc),
            request=request,
            observation=observation,
            diagnostics={
                "failure_stage": "preprocessing"
                if isinstance(exc, PreprocessingError)
                else "bls_search",
                **(_source_diagnostics(observation) if observation else {}),
            },
        )
        _append_evidence(result, ledger_path=request.ledger_path, step_id=request.step_id)
        return result

    folded_payload: dict[str, list[float]] | None = None
    if outcome.candidate is not None:
        folded = phase_fold(
            prepared.time_btjd,
            prepared.relative_flux,
            prepared.relative_flux_error,
            period_days=outcome.candidate.period_days,
            epoch_btjd=outcome.candidate.epoch_btjd,
        )
        folded_payload = {
            "phase": folded.phase.tolist(),
            "relative_flux": folded.relative_flux.tolist(),
            "relative_flux_error": folded.relative_flux_error.tolist(),
        }

    artifact_payload = _artifact_payload(
        observation,
        prepared,
        request,
        period_grid_days=outcome.period_grid_days,
        periodogram_snr=outcome.periodogram_snr,
        folded=folded_payload,
    )
    artifact_ref, _ = _write_artifact(request.artifact_dir, action_id, artifact_payload)
    provenance = _provenance(observation, output_artifact_refs=[artifact_ref])
    common_diagnostics = {
        **_source_diagnostics(observation),
        "input_sample_count": len(observation.time_btjd),
        "retained_sample_count": len(prepared.time_btjd),
        "quality_removed_count": int(prepared.quality_removed.sum()),
        "invalid_removed_count": int(prepared.invalid_removed.sum()),
        "outlier_removed_count": int(prepared.outlier_removed.sum()),
        "masks_artifact_ref": artifact_ref,
        "searched_minimum_period_days": outcome.searched_minimum_period_days,
        "searched_maximum_period_days": outcome.searched_maximum_period_days,
        "best_bls_snr": outcome.best_snr,
    }

    if outcome.candidate is None:
        result = ScientificToolResult(
            tool_name="search_bls",
            status=ToolStatus.NO_EVIDENCE,
            run_id=run_id,
            action_id=action_id,
            target_id=target_id,
            diagnostics=common_diagnostics,
            method="Astropy BoxLeastSquares objective=snr; Lightkurve TESS default bitmask=175",
            parameters=_safe_parameters(request),
            provenance=provenance,
            reason=outcome.reason,
        )
    else:
        candidate = outcome.candidate
        measurements = {
            "period": Measurement(
                value=candidate.period_days,
                unit="d",
                tolerance=candidate.period_grid_tolerance_days,
                evidence_ref=artifact_ref,
            ),
            "epoch": Measurement(
                value=candidate.epoch_btjd,
                unit="BTJD",
                tolerance=candidate.epoch_cadence_tolerance_days,
                evidence_ref=artifact_ref,
            ),
            "duration": Measurement(
                value=candidate.duration_hours,
                unit="h",
                tolerance=candidate.duration_grid_tolerance_hours,
                evidence_ref=artifact_ref,
            ),
            "depth": Measurement(
                value=candidate.depth_fraction,
                unit="relative_flux_fraction",
                uncertainty=candidate.depth_uncertainty_fraction,
                evidence_ref=artifact_ref,
            ),
            "snr": Measurement(
                value=candidate.snr,
                unit="dimensionless",
                evidence_ref=artifact_ref,
            ),
            "usable_transits": Measurement(
                value=candidate.usable_transits,
                unit="count",
                evidence_ref=artifact_ref,
            ),
            "in_transit_samples": Measurement(
                value=candidate.in_transit_samples,
                unit="count",
                evidence_ref=artifact_ref,
            ),
        }
        result = ScientificToolResult(
            tool_name="search_bls",
            status=ToolStatus.SUCCESS,
            run_id=run_id,
            action_id=action_id,
            target_id=target_id,
            measurements=measurements,
            diagnostics={
                **common_diagnostics,
                "phase_convention": "phase zero is mid-transit; phase range is [-0.5, 0.5)",
                "harmonic_trials": candidate.harmonic_diagnostics,
                "period_tolerance_kind": "maximum adjacent Astropy BLS grid spacing",
                "epoch_tolerance_kind": "one input cadence",
                "duration_tolerance_kind": "nearest tested duration-grid spacing",
                "depth_uncertainty_kind": "Astropy BLS 1-sigma depth_err",
            },
            method="Astropy BoxLeastSquares objective=snr; Lightkurve TESS default bitmask=175",
            parameters=_safe_parameters(request),
            provenance=provenance,
        )

    _append_evidence(result, ledger_path=request.ledger_path, step_id=request.step_id)
    return result
