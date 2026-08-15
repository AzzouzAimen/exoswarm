from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.ndimage import median_filter

from exoswarm.science.contracts import not_implemented_result
from exoswarm.science.io import CachedTessLightCurve


class PreprocessingError(ValueError):
    """The observation cannot be safely prepared for transit search."""


@dataclass(frozen=True, slots=True)
class PreprocessingConfig:
    quality_bitmask: int = 175
    outlier_sigma: float = 8.0
    detrend_window_days: float = 1.0
    gap_threshold_cadences: float = 5.0
    minimum_samples: int = 200


@dataclass(frozen=True, slots=True)
class PreprocessedLightCurve:
    time_btjd: np.ndarray
    relative_flux: np.ndarray
    relative_flux_error: np.ndarray
    trend: np.ndarray
    source_indices: np.ndarray
    quality_removed: np.ndarray
    invalid_removed: np.ndarray
    outlier_removed: np.ndarray
    normalization_flux: float
    detrend_window_samples: int


def _odd_window(sample_count: int, requested: int) -> int:
    window = min(sample_count if sample_count % 2 else sample_count - 1, requested)
    return max(1, window if window % 2 else window - 1)


def _detrend_by_segments(
    time_btjd: np.ndarray,
    normalized_flux: np.ndarray,
    *,
    cadence_days: float,
    requested_window: int,
    gap_threshold_cadences: float,
) -> np.ndarray:
    split_after = np.flatnonzero(
        np.diff(time_btjd) > gap_threshold_cadences * cadence_days
    ) + 1
    segments = np.split(np.arange(len(time_btjd)), split_after)
    trend = np.empty_like(normalized_flux)
    for segment in segments:
        window = _odd_window(len(segment), requested_window)
        if window < 5:
            trend[segment] = np.median(normalized_flux[segment])
        else:
            trend[segment] = median_filter(normalized_flux[segment], size=window, mode="reflect")
    return trend


def preprocess_lightcurve(
    observation: CachedTessLightCurve,
    config: PreprocessingConfig,
) -> PreprocessedLightCurve:
    """Apply explicit TESS quality, finite-value, outlier, normalization, and trend masks."""

    if config.quality_bitmask < 0:
        raise PreprocessingError("quality bitmask must be non-negative")
    if config.outlier_sigma <= 0:
        raise PreprocessingError("outlier sigma must be positive")
    if config.detrend_window_days <= 0 or config.gap_threshold_cadences <= 0:
        raise PreprocessingError("detrending window and gap threshold must be positive")
    if config.minimum_samples < 20:
        raise PreprocessingError("minimum sample count must be at least 20")

    quality_keep = (observation.quality & config.quality_bitmask) == 0
    finite_keep = (
        np.isfinite(observation.time_btjd)
        & np.isfinite(observation.flux)
        & np.isfinite(observation.flux_error)
        & (observation.flux > 0)
        & (observation.flux_error > 0)
    )
    preliminary_keep = quality_keep & finite_keep
    if int(preliminary_keep.sum()) < config.minimum_samples:
        raise PreprocessingError("insufficient valid cadences after quality and finite filtering")

    preliminary_flux = observation.flux[preliminary_keep]
    normalization_flux = float(np.median(preliminary_flux))
    if not np.isfinite(normalization_flux) or normalization_flux <= 0:
        raise PreprocessingError("flux normalization is not finite and positive")

    deviations = preliminary_flux - normalization_flux
    mad = float(np.median(np.abs(deviations)))
    robust_sigma = 1.4826 * mad
    high_outlier_preliminary = np.zeros(len(preliminary_flux), dtype=bool)
    if robust_sigma > 0:
        # Only positive impulsive outliers are clipped here. Negative events are retained so a
        # transit is never removed merely because it is significant.
        high_outlier_preliminary = deviations > config.outlier_sigma * robust_sigma

    outlier_removed = np.zeros(len(observation.time_btjd), dtype=bool)
    outlier_removed[np.flatnonzero(preliminary_keep)] = high_outlier_preliminary
    keep = preliminary_keep & ~outlier_removed
    if int(keep.sum()) < config.minimum_samples:
        raise PreprocessingError("insufficient cadences after outlier filtering")

    source_indices = np.flatnonzero(keep)
    time_btjd = observation.time_btjd[keep]
    if np.any(np.diff(time_btjd) <= 0):
        raise PreprocessingError("usable TIME values must be strictly increasing")

    normalized_flux = observation.flux[keep] / normalization_flux
    normalized_error = observation.flux_error[keep] / normalization_flux
    cadence_days = observation.cadence_seconds / 86_400.0
    requested_window = max(5, int(round(config.detrend_window_days / cadence_days)))
    if requested_window % 2 == 0:
        requested_window += 1
    trend = _detrend_by_segments(
        time_btjd,
        normalized_flux,
        cadence_days=cadence_days,
        requested_window=requested_window,
        gap_threshold_cadences=config.gap_threshold_cadences,
    )
    if np.any(~np.isfinite(trend)) or np.any(trend <= 0):
        raise PreprocessingError("detrending produced a non-finite or non-positive trend")

    relative_flux = normalized_flux / trend
    relative_flux_error = normalized_error / trend
    if np.any(~np.isfinite(relative_flux)) or np.any(~np.isfinite(relative_flux_error)):
        raise PreprocessingError("preprocessed flux contains non-finite values")

    return PreprocessedLightCurve(
        time_btjd=time_btjd,
        relative_flux=relative_flux,
        relative_flux_error=relative_flux_error,
        trend=trend,
        source_indices=source_indices,
        quality_removed=~quality_keep,
        invalid_removed=~finite_keep,
        outlier_removed=outlier_removed,
        normalization_flux=normalization_flux,
        detrend_window_samples=requested_window,
    )


def preprocess(run_id, action_id, target_id, parameters):
    return not_implemented_result(
        tool_name="preprocess",
        run_id=run_id,
        action_id=action_id,
        target_id=target_id,
        parameters=parameters,
    )
