from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from astropy import units as u
from astropy.timeseries import BoxLeastSquares

from exoswarm.science.preprocessing import PreprocessedLightCurve


class BlsSearchError(ValueError):
    """The configured BLS search cannot produce a scientifically usable result."""


@dataclass(frozen=True, slots=True)
class BlsSearchConfig:
    minimum_period_days: float = 0.5
    maximum_period_days: float | None = None
    durations_hours: tuple[float, ...] = (1.5, 2.0, 3.0, 4.5, 6.0)
    frequency_factor: float = 1.0
    minimum_snr: float = 6.0
    minimum_transits: int = 3


@dataclass(frozen=True, slots=True)
class BlsCandidate:
    period_days: float
    period_grid_tolerance_days: float | None
    epoch_btjd: float
    epoch_cadence_tolerance_days: float
    duration_hours: float
    duration_grid_tolerance_hours: float | None
    depth_fraction: float
    depth_uncertainty_fraction: float
    snr: float
    usable_transits: int
    in_transit_samples: int
    period_grid_days: np.ndarray
    periodogram_snr: np.ndarray
    harmonic_diagnostics: dict[str, dict[str, float]]


@dataclass(frozen=True, slots=True)
class BlsSearchOutcome:
    candidate: BlsCandidate | None
    best_snr: float | None
    reason: str | None
    searched_minimum_period_days: float
    searched_maximum_period_days: float
    period_grid_days: np.ndarray
    periodogram_snr: np.ndarray


def _grid_tolerance(values: np.ndarray, index: int) -> float | None:
    neighbors: list[float] = []
    if index > 0:
        neighbors.append(abs(float(values[index]) - float(values[index - 1])))
    if index + 1 < len(values):
        neighbors.append(abs(float(values[index + 1]) - float(values[index])))
    return max(neighbors) if neighbors else None


def _duration_tolerance(durations_hours: np.ndarray, selected: float) -> float | None:
    if len(durations_hours) < 2:
        return None
    selected_index = int(np.argmin(np.abs(durations_hours - selected)))
    return _grid_tolerance(durations_hours, selected_index)


def search_lightcurve_bls(
    lightcurve: PreprocessedLightCurve,
    *,
    cadence_seconds: float,
    config: BlsSearchConfig,
) -> BlsSearchOutcome:
    """Search a detrended light curve using Astropy's unit-aware BLS implementation."""

    baseline_days = float(lightcurve.time_btjd[-1] - lightcurve.time_btjd[0])
    if not np.isfinite(baseline_days) or baseline_days <= 0:
        raise BlsSearchError("observation baseline must be finite and positive")
    if config.minimum_period_days <= 0 or config.minimum_transits < 2:
        raise BlsSearchError("period and transit-count bounds must be positive")
    if config.frequency_factor <= 0 or config.minimum_snr <= 0:
        raise BlsSearchError("frequency factor and minimum SNR must be positive")

    maximum_period_days = config.maximum_period_days
    if maximum_period_days is None:
        maximum_period_days = baseline_days / config.minimum_transits
    if maximum_period_days <= config.minimum_period_days:
        raise BlsSearchError("baseline is insufficient for the requested period range")

    duration_hours = np.asarray(sorted(set(config.durations_hours)), dtype=np.float64)
    if len(duration_hours) == 0 or np.any(~np.isfinite(duration_hours)) or np.any(
        duration_hours <= 0
    ):
        raise BlsSearchError("durations must be finite and positive")
    if float(duration_hours[-1] / 24.0) >= config.minimum_period_days:
        raise BlsSearchError("every tested duration must be shorter than the minimum period")

    model = BoxLeastSquares(
        lightcurve.time_btjd * u.day,
        lightcurve.relative_flux * u.dimensionless_unscaled,
        dy=lightcurve.relative_flux_error * u.dimensionless_unscaled,
    )
    try:
        result = model.autopower(
            duration_hours / 24.0 * u.day,
            objective="snr",
            minimum_period=config.minimum_period_days * u.day,
            maximum_period=maximum_period_days * u.day,
            frequency_factor=config.frequency_factor,
        )
    except (TypeError, ValueError, ZeroDivisionError) as exc:
        raise BlsSearchError("Astropy BLS rejected the configured search") from exc

    period_grid = np.asarray(result.period.to_value(u.day), dtype=np.float64)
    power = np.asarray(result.power.value, dtype=np.float64)
    finite_power = np.isfinite(power)
    if len(power) == 0 or not finite_power.any():
        return BlsSearchOutcome(
            candidate=None,
            best_snr=None,
            reason="BLS produced no finite trial statistic",
            searched_minimum_period_days=config.minimum_period_days,
            searched_maximum_period_days=float(maximum_period_days),
            period_grid_days=period_grid,
            periodogram_snr=power,
        )
    best_index = int(np.nanargmax(power))
    best_snr = float(np.asarray(result.depth_snr.value)[best_index])
    depth = float(np.asarray(result.depth.value)[best_index])
    depth_error = float(np.asarray(result.depth_err.value)[best_index])
    if not all(np.isfinite(value) for value in (best_snr, depth, depth_error)):
        return BlsSearchOutcome(
            candidate=None,
            best_snr=None,
            reason="best BLS trial has non-finite measurements",
            searched_minimum_period_days=config.minimum_period_days,
            searched_maximum_period_days=float(maximum_period_days),
            period_grid_days=period_grid,
            periodogram_snr=power,
        )

    period_days = float(result.period[best_index].to_value(u.day))
    duration_days = float(result.duration[best_index].to_value(u.day))
    epoch_btjd = float(result.transit_time[best_index].to_value(u.day))
    transit_mask = np.asarray(
        model.transit_mask(
            lightcurve.time_btjd * u.day,
            period_days * u.day,
            duration_days * u.day,
            epoch_btjd * u.day,
        ),
        dtype=bool,
    )
    transit_numbers = np.rint(
        (lightcurve.time_btjd[transit_mask] - epoch_btjd) / period_days
    ).astype(np.int64)
    usable_transits = int(len(np.unique(transit_numbers)))

    if best_snr < config.minimum_snr or depth <= 0 or usable_transits < config.minimum_transits:
        return BlsSearchOutcome(
            candidate=None,
            best_snr=best_snr,
            reason=(
                "best BLS trial did not satisfy the declared SNR, positive-depth, and "
                "usable-transit thresholds"
            ),
            searched_minimum_period_days=config.minimum_period_days,
            searched_maximum_period_days=float(maximum_period_days),
            period_grid_days=period_grid,
            periodogram_snr=power,
        )

    harmonic_diagnostics: dict[str, dict[str, float]] = {}
    for label, factor in (("half_period", 0.5), ("same_period", 1.0), ("double_period", 2.0)):
        trial_period = period_days * factor
        if not config.minimum_period_days <= trial_period <= maximum_period_days:
            continue
        trial = model.power(
            np.asarray([trial_period]) * u.day,
            duration_hours / 24.0 * u.day,
            objective="snr",
        )
        harmonic_diagnostics[label] = {
            "period_days": trial_period,
            "depth_snr": float(np.asarray(trial.depth_snr.value)[0]),
            "depth_fraction": float(np.asarray(trial.depth.value)[0]),
        }

    selected_duration_hours = duration_days * 24.0
    candidate = BlsCandidate(
        period_days=period_days,
        period_grid_tolerance_days=_grid_tolerance(period_grid, best_index),
        epoch_btjd=epoch_btjd,
        epoch_cadence_tolerance_days=cadence_seconds / 86_400.0,
        duration_hours=selected_duration_hours,
        duration_grid_tolerance_hours=_duration_tolerance(
            duration_hours, selected_duration_hours
        ),
        depth_fraction=depth,
        depth_uncertainty_fraction=depth_error,
        snr=best_snr,
        usable_transits=usable_transits,
        in_transit_samples=int(transit_mask.sum()),
        period_grid_days=period_grid,
        periodogram_snr=power,
        harmonic_diagnostics=harmonic_diagnostics,
    )
    return BlsSearchOutcome(
        candidate=candidate,
        best_snr=best_snr,
        reason=None,
        searched_minimum_period_days=config.minimum_period_days,
        searched_maximum_period_days=float(maximum_period_days),
        period_grid_days=period_grid,
        periodogram_snr=power,
    )


def search_bls(run_id, action_id, target_id, parameters):
    from exoswarm.science.pipeline import analyze_cached_candidate

    return analyze_cached_candidate(
        run_id=run_id,
        action_id=action_id,
        target_id=target_id,
        parameters=parameters,
    )
