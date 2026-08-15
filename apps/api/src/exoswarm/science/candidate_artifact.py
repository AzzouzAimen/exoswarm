from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np
from astropy import units as u
from astropy.timeseries import BoxLeastSquares
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from exoswarm.domain.models import Provenance

VETTING_CODE_VERSION = "exoswarm-api/0.1.0"


class CandidateArtifactError(ValueError):
    """A candidate-search artifact cannot support deterministic vetting."""


class CandidateArtifactRuntimeInputs(BaseModel):
    """Controller-owned input; local paths never enter model-selected parameters."""

    model_config = ConfigDict(extra="forbid", strict=True)

    candidate_artifact_path: Path


class _ArtifactModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class _Source(_ArtifactModel):
    source_data_ref: str = Field(min_length=1)
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    sector: int
    cadence_seconds: float = Field(gt=0)
    time_system: Literal["TDB"]
    time_unit: Literal["d"]
    epoch_convention: str = Field(min_length=1)
    bjd_reference: float
    input_flux_unit: str = Field(min_length=1)
    source_size_bytes: int = Field(ge=0)
    fits_checksum: str | None
    fits_datasum: str | None
    crowdsap: float | None = Field(default=None, ge=0.0, le=1.0)


class _Processing(_ArtifactModel):
    quality_bitmask: int = Field(ge=0)
    outlier_sigma: float = Field(gt=0)
    detrend_window_days: float = Field(gt=0)
    gap_threshold_cadences: float = Field(gt=0)
    minimum_samples: int = Field(ge=20)
    normalization_flux: float = Field(gt=0)
    normalization_flux_unit: str = Field(min_length=1)
    detrend_window_samples: int = Field(ge=1)
    quality_removed_indices: list[int]
    invalid_removed_indices: list[int]
    outlier_removed_indices: list[int]
    retained_source_indices: list[int]


class _LightCurveUnits(_ArtifactModel):
    time: Literal["BTJD"]
    relative_flux: Literal["fraction"]
    relative_flux_error: Literal["fraction"]
    trend: Literal["dimensionless"]


class _CleanedLightCurve(_ArtifactModel):
    time_btjd: list[float]
    relative_flux: list[float]
    relative_flux_error: list[float]
    trend: list[float]
    units: _LightCurveUnits

    @model_validator(mode="after")
    def arrays_have_equal_lengths(self) -> _CleanedLightCurve:
        lengths = {
            len(self.time_btjd),
            len(self.relative_flux),
            len(self.relative_flux_error),
            len(self.trend),
        }
        if len(lengths) != 1:
            raise ValueError("cleaned light-curve arrays must have equal lengths")
        return self


class _BlsParameters(_ArtifactModel):
    minimum_period_days: float = Field(gt=0)
    maximum_period_days: float | None = Field(default=None, gt=0)
    durations_hours: list[float] = Field(min_length=1)
    frequency_factor: float = Field(gt=0)
    minimum_snr: float = Field(gt=0)
    minimum_transits: int = Field(ge=2)


class _BlsArtifact(_ArtifactModel):
    parameters: _BlsParameters
    period_grid_days: list[float] = Field(min_length=1)
    periodogram_depth_snr: list[float] = Field(min_length=1)

    @model_validator(mode="after")
    def grid_and_statistic_have_equal_lengths(self) -> _BlsArtifact:
        if len(self.period_grid_days) != len(self.periodogram_depth_snr):
            raise ValueError("BLS period grid and statistic must have equal lengths")
        return self


class _FoldedLightCurve(_ArtifactModel):
    phase: list[float]
    relative_flux: list[float]
    relative_flux_error: list[float]

    @model_validator(mode="after")
    def arrays_have_equal_lengths(self) -> _FoldedLightCurve:
        lengths = {len(self.phase), len(self.relative_flux), len(self.relative_flux_error)}
        if len(lengths) != 1:
            raise ValueError("phase-folded arrays must have equal lengths")
        return self


class CandidateArtifact(_ArtifactModel):
    schema_version: Literal["1"]
    source: _Source
    processing: _Processing
    cleaned_lightcurve: _CleanedLightCurve
    bls: _BlsArtifact
    phase_folded: _FoldedLightCurve | None
    library_versions: dict[str, str]
    code_version: str = Field(min_length=1)


@dataclass(frozen=True, slots=True)
class LoadedCandidateArtifact:
    artifact: CandidateArtifact
    artifact_sha256: str
    artifact_ref: str
    time_btjd: np.ndarray
    relative_flux: np.ndarray
    relative_flux_error: np.ndarray
    period_days: float
    epoch_btjd: float
    duration_days: float
    depth_fraction: float
    depth_uncertainty_fraction: float
    depth_snr: float

    @property
    def provenance(self) -> Provenance:
        return Provenance(
            input_artifact_refs=[self.artifact_ref, self.artifact.source.source_data_ref],
            code_version=VETTING_CODE_VERSION,
            source_data_ref=self.artifact.source.source_data_ref,
            source_sha256=self.artifact.source.source_sha256,
            library_versions=self.artifact.library_versions,
        )


def _finite_array(values: list[float], *, name: str) -> np.ndarray:
    array = np.asarray(values, dtype=np.float64)
    if np.any(~np.isfinite(array)):
        raise CandidateArtifactError(f"candidate artifact {name} contains non-finite values")
    return array


def load_candidate_artifact(path: Path) -> LoadedCandidateArtifact:
    """Load and validate an agent-safe candidate artifact without exposing its local path."""

    try:
        resolved = path.resolve(strict=True)
    except FileNotFoundError as exc:
        raise CandidateArtifactError("candidate artifact was not found") from exc
    if not resolved.is_file() or resolved.suffix.lower() != ".json":
        raise CandidateArtifactError("candidate artifact must be a JSON file")

    content = resolved.read_bytes()
    try:
        artifact = CandidateArtifact.model_validate_json(content)
    except ValidationError as exc:
        raise CandidateArtifactError(
            "candidate artifact does not satisfy schema version 1"
        ) from exc
    if artifact.phase_folded is None:
        raise CandidateArtifactError("candidate artifact contains no accepted BLS candidate")

    lightcurve = artifact.cleaned_lightcurve
    time_btjd = _finite_array(lightcurve.time_btjd, name="time_btjd")
    relative_flux = _finite_array(lightcurve.relative_flux, name="relative_flux")
    relative_flux_error = _finite_array(
        lightcurve.relative_flux_error, name="relative_flux_error"
    )
    if len(time_btjd) < 20:
        raise CandidateArtifactError("candidate artifact has fewer than 20 cleaned samples")
    if np.any(np.diff(time_btjd) <= 0):
        raise CandidateArtifactError("candidate artifact times must be strictly increasing")
    if np.any(relative_flux_error <= 0):
        raise CandidateArtifactError("candidate artifact flux errors must be positive")

    periods = _finite_array(artifact.bls.period_grid_days, name="period_grid_days")
    statistic = _finite_array(
        artifact.bls.periodogram_depth_snr, name="periodogram_depth_snr"
    )
    best_period_days = float(periods[int(np.argmax(statistic))])
    durations_days = (
        _finite_array(artifact.bls.parameters.durations_hours, name="durations_hours")
        / 24.0
    )
    durations_days = durations_days[durations_days < best_period_days]
    if len(durations_days) == 0:
        raise CandidateArtifactError("candidate duration grid is invalid for the best period")

    model = BoxLeastSquares(
        time_btjd * u.day,
        relative_flux * u.dimensionless_unscaled,
        dy=relative_flux_error * u.dimensionless_unscaled,
    )
    try:
        trial = model.power(
            np.asarray([best_period_days]) * u.day,
            durations_days * u.day,
            objective="snr",
        )
        epoch_btjd = float(np.asarray(trial.transit_time.to_value(u.day))[0])
        duration_days = float(np.asarray(trial.duration.to_value(u.day))[0])
        depth_fraction = float(np.asarray(trial.depth.value)[0])
        depth_uncertainty = float(np.asarray(trial.depth_err.value)[0])
        depth_snr = float(np.asarray(trial.depth_snr.value)[0])
    except (TypeError, ValueError, ZeroDivisionError, IndexError) as exc:
        raise CandidateArtifactError("candidate ephemeris reconstruction failed") from exc
    if not all(
        np.isfinite(value)
        for value in (
            best_period_days,
            epoch_btjd,
            duration_days,
            depth_fraction,
            depth_uncertainty,
            depth_snr,
        )
    ):
        raise CandidateArtifactError("candidate ephemeris contains non-finite values")
    if best_period_days <= 0 or duration_days <= 0 or depth_uncertainty <= 0:
        raise CandidateArtifactError("candidate ephemeris has non-positive scales")

    artifact_sha256 = hashlib.sha256(content).hexdigest()
    return LoadedCandidateArtifact(
        artifact=artifact,
        artifact_sha256=artifact_sha256,
        artifact_ref=f"candidate-artifact:sha256:{artifact_sha256}",
        time_btjd=time_btjd,
        relative_flux=relative_flux,
        relative_flux_error=relative_flux_error,
        period_days=best_period_days,
        epoch_btjd=epoch_btjd,
        duration_days=duration_days,
        depth_fraction=depth_fraction,
        depth_uncertainty_fraction=depth_uncertainty,
        depth_snr=depth_snr,
    )


def phase_distance(time_btjd: np.ndarray, epoch_btjd: float, period_days: float) -> np.ndarray:
    """Signed distance from phase zero in days, in [-P/2, P/2)."""

    return (time_btjd - epoch_btjd + 0.5 * period_days) % period_days - 0.5 * period_days


__all__ = [
    "CandidateArtifactError",
    "CandidateArtifactRuntimeInputs",
    "LoadedCandidateArtifact",
    "load_candidate_artifact",
    "phase_distance",
]
