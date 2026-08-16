from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import ValidationError

from exoswarm.science.candidate_artifact import CandidateArtifact, CandidateArtifactError

PlotMode = Literal["raw", "bls", "phase-fold", "odd-even", "secondary", "harmonic"]
PLOT_MODES: tuple[PlotMode, ...] = (
    "raw",
    "bls",
    "phase-fold",
    "odd-even",
    "secondary",
    "harmonic",
)
MAX_TRACE_POINTS = 1200


@dataclass(frozen=True, slots=True)
class PlotSeries:
    name: str
    x: list[float]
    y: list[float]
    kind: Literal["line", "markers", "bar"]


def load_plot_artifact(path: Path) -> CandidateArtifact:
    """Validate the persisted candidate artifact without exposing its filesystem path."""

    try:
        artifact = CandidateArtifact.model_validate_json(path.read_bytes())
    except (OSError, ValidationError) as exc:
        raise CandidateArtifactError("candidate plot artifact is invalid") from exc
    if artifact.phase_folded is None:
        raise CandidateArtifactError("candidate plot artifact has no accepted phase fold")
    for name, values in (
        ("time_btjd", artifact.cleaned_lightcurve.time_btjd),
        ("relative_flux", artifact.cleaned_lightcurve.relative_flux),
        ("period_grid_days", artifact.bls.period_grid_days),
        ("periodogram_depth_snr", artifact.bls.periodogram_depth_snr),
        ("phase", artifact.phase_folded.phase),
        ("phase_relative_flux", artifact.phase_folded.relative_flux),
    ):
        if any(not math.isfinite(float(value)) for value in values):
            raise CandidateArtifactError(f"candidate plot artifact contains non-finite {name}")
    return artifact


def bounded_series(
    x: list[float], y: list[float], *, limit: int = MAX_TRACE_POINTS
) -> tuple[list[float], list[float]]:
    if len(x) != len(y):
        raise CandidateArtifactError("plot series arrays have different lengths")
    if len(x) <= limit:
        return x, y
    bucket_count = max(1, (limit - 2) // 2)
    selected: set[int] = {0, len(x) - 1}
    for bucket in range(bucket_count):
        start = int(bucket * len(x) / bucket_count)
        end = max(start + 1, int((bucket + 1) * len(x) / bucket_count))
        segment = y[start:end]
        if not segment:
            continue
        selected.add(start + min(range(len(segment)), key=segment.__getitem__))
        selected.add(start + max(range(len(segment)), key=segment.__getitem__))
    indices = sorted(selected)
    if len(indices) > limit:
        raise RuntimeError("bounded plot selection exceeded its configured point limit")
    return [x[index] for index in indices], [y[index] for index in indices]


def candidate_plot(
    mode: PlotMode,
    artifact: CandidateArtifact,
    *,
    evidence_ref: str,
    artifact_ref: str,
) -> PlotSeries:
    if mode == "raw":
        x, y = bounded_series(
            artifact.cleaned_lightcurve.time_btjd,
            artifact.cleaned_lightcurve.relative_flux,
        )
        return PlotSeries("cleaned light curve", x, y, "line")
    if mode == "bls":
        x, y = bounded_series(artifact.bls.period_grid_days, artifact.bls.periodogram_depth_snr)
        return PlotSeries("BLS periodogram", x, y, "line")
    folded = artifact.phase_folded
    assert folded is not None
    x, y = bounded_series(folded.phase, folded.relative_flux)
    return PlotSeries("phase-folded light curve", x, y, "markers")


__all__ = [
    "MAX_TRACE_POINTS",
    "PLOT_MODES",
    "PlotMode",
    "PlotSeries",
    "candidate_plot",
    "load_plot_artifact",
    "bounded_series",
]
