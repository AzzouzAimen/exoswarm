from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True, slots=True)
class FoldedLightCurve:
    phase: np.ndarray
    relative_flux: np.ndarray
    relative_flux_error: np.ndarray


def phase_fold(
    time_btjd: np.ndarray,
    relative_flux: np.ndarray,
    relative_flux_error: np.ndarray,
    *,
    period_days: float,
    epoch_btjd: float,
) -> FoldedLightCurve:
    """Fold onto mid-transit phase zero, returning phase in [-0.5, 0.5)."""

    if period_days <= 0 or not np.isfinite(period_days) or not np.isfinite(epoch_btjd):
        raise ValueError("period and epoch must be finite, with a positive period")
    phase = ((time_btjd - epoch_btjd + 0.5 * period_days) % period_days) / period_days - 0.5
    order = np.argsort(phase, kind="stable")
    return FoldedLightCurve(
        phase=phase[order],
        relative_flux=relative_flux[order],
        relative_flux_error=relative_flux_error[order],
    )
