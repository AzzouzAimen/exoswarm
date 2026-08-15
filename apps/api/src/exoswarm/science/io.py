from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from astropy.io import fits

from exoswarm.science.contracts import not_implemented_result


class CachedLightCurveError(ValueError):
    """A cached light curve cannot satisfy the deterministic ingestion contract."""


class CachedLightCurvePreconditionError(CachedLightCurveError):
    """A readable light curve lacks data or metadata required for analysis."""


@dataclass(frozen=True, slots=True)
class CachedTessLightCurve:
    time_btjd: np.ndarray
    flux: np.ndarray
    flux_error: np.ndarray
    quality: np.ndarray
    sector: int
    cadence_seconds: float
    time_system: str
    time_unit: str
    bjd_reference: float
    flux_unit: str
    source_sha256: str
    source_size_bytes: int
    fits_checksum: str | None
    fits_datasum: str | None
    crowdsap: float | None

    @property
    def source_data_ref(self) -> str:
        return f"cached-tess:sha256:{self.source_sha256}"


def _header_value(primary: fits.Header, table: fits.Header, key: str) -> Any:
    value = table.get(key)
    return primary.get(key) if value is None else value


def _required_column(table: fits.BinTableHDU, name: str) -> np.ndarray:
    names = {column.upper(): column for column in (table.columns.names or [])}
    try:
        actual_name = names[name]
    except KeyError as exc:
        raise CachedLightCurveError(f"missing required FITS column: {name}") from exc
    return np.asarray(table.data[actual_name])


def load_cached_tess_fits(path: Path) -> CachedTessLightCurve:
    """Load a local SPOC-like light-curve FITS file without network access.

    Recognizable target headers are intentionally neither copied nor returned. The content
    digest is the agent-safe source identity; backend-only code can retain the path mapping.
    """

    resolved = path.resolve(strict=True)
    if not resolved.is_file():
        raise CachedLightCurveError("cached observation path is not a file")
    if resolved.suffix.lower() not in {".fits", ".fit", ".fts"}:
        raise CachedLightCurveError("cached observation must be a FITS file")

    source_bytes = resolved.read_bytes()
    source_sha256 = hashlib.sha256(source_bytes).hexdigest()

    try:
        with fits.open(resolved, mode="readonly", memmap=False, checksum=True) as hdus:
            if len(hdus) < 2 or not isinstance(hdus[1], fits.BinTableHDU):
                raise CachedLightCurveError("FITS extension 1 must be a binary light-curve table")
            primary_header = hdus[0].header
            table = hdus[1]
            table_header = table.header

            time = _required_column(table, "TIME").astype(np.float64, copy=True)
            flux = _required_column(table, "PDCSAP_FLUX").astype(np.float64, copy=True)
            flux_error = _required_column(table, "PDCSAP_FLUX_ERR").astype(
                np.float64, copy=True
            )
            quality = _required_column(table, "QUALITY").astype(np.int64, copy=True)

            lengths = {len(time), len(flux), len(flux_error), len(quality)}
            if lengths == {0}:
                raise CachedLightCurvePreconditionError("cached light curve contains no cadences")
            if len(lengths) != 1:
                raise CachedLightCurveError("cached light-curve columns have unequal lengths")

            time_unit = str(table.columns["TIME"].unit or "").strip().lower()
            tess_btjd_column_units = {
                "bjd - 2457000, days",
                "jd - 2457000, days",
            }
            if time_unit not in {"d", "day", "days", *tess_btjd_column_units}:
                raise CachedLightCurvePreconditionError(
                    "TIME must declare days as its FITS column unit"
                )
            time_system = str(_header_value(primary_header, table_header, "TIMESYS") or "").upper()
            if time_system != "TDB":
                raise CachedLightCurvePreconditionError("TIMESYS must explicitly be TDB")

            bjdrefi = _header_value(primary_header, table_header, "BJDREFI")
            bjdreff = _header_value(primary_header, table_header, "BJDREFF")
            if bjdrefi is None:
                raise CachedLightCurvePreconditionError(
                    "BJDREFI is required for the BTJD epoch convention"
                )
            bjd_reference = float(bjdrefi) + float(bjdreff or 0.0)
            if not np.isclose(bjd_reference, 2_457_000.0, rtol=0.0, atol=1e-8):
                raise CachedLightCurvePreconditionError(
                    "BJD reference is not the TESS BTJD reference"
                )

            sector = _header_value(primary_header, table_header, "SECTOR")
            if sector is None or int(sector) < 1:
                raise CachedLightCurvePreconditionError(
                    "a positive TESS SECTOR header is required"
                )

            cadence_days = _header_value(primary_header, table_header, "TIMEDEL")
            if cadence_days is None or not np.isfinite(float(cadence_days)):
                finite_time = np.sort(time[np.isfinite(time)])
                differences = np.diff(finite_time)
                differences = differences[differences > 0]
                if len(differences) == 0:
                    raise CachedLightCurvePreconditionError(
                        "cadence cannot be inferred from TIME"
                    )
                cadence_days = float(np.median(differences))
            cadence_seconds = float(cadence_days) * 86_400.0
            if cadence_seconds <= 0:
                raise CachedLightCurvePreconditionError("cadence must be positive")

            flux_unit = str(table.columns["PDCSAP_FLUX"].unit or "").strip()
            if not flux_unit:
                raise CachedLightCurvePreconditionError(
                    "PDCSAP_FLUX must declare a FITS column unit"
                )

            checksum = table_header.get("CHECKSUM")
            datasum = table_header.get("DATASUM")
            crowdsap_header = _header_value(primary_header, table_header, "CROWDSAP")
            crowdsap = None if crowdsap_header is None else float(crowdsap_header)
            if crowdsap is not None and (
                not np.isfinite(crowdsap) or crowdsap < 0.0 or crowdsap > 1.0
            ):
                raise CachedLightCurvePreconditionError(
                    "CROWDSAP must be a finite fraction in [0, 1] when present"
                )
    except CachedLightCurveError:
        raise
    except (OSError, TypeError, ValueError, IndexError) as exc:
        raise CachedLightCurveError(
            "cached observation is not a readable TESS FITS product"
        ) from exc

    return CachedTessLightCurve(
        time_btjd=time,
        flux=flux,
        flux_error=flux_error,
        quality=quality,
        sector=int(sector),
        cadence_seconds=cadence_seconds,
        time_system=time_system,
        time_unit="d",
        bjd_reference=bjd_reference,
        flux_unit=flux_unit,
        source_sha256=source_sha256,
        source_size_bytes=len(source_bytes),
        fits_checksum=str(checksum) if checksum is not None else None,
        fits_datasum=str(datasum) if datasum is not None else None,
        crowdsap=crowdsap,
    )


def load_cached_lightcurve(run_id, action_id, target_id, parameters):
    # The public milestone entry point is search_bls, which owns the full typed result and ledger
    # transaction. Keep this standalone registry action explicit until a multi-step runtime exists.
    return not_implemented_result(
        tool_name="load_cached_lightcurve",
        run_id=run_id,
        action_id=action_id,
        target_id=target_id,
        parameters=parameters,
    )


def load_cached_tpf(run_id, action_id, target_id, parameters):
    return not_implemented_result(
        tool_name="load_cached_tpf",
        run_id=run_id,
        action_id=action_id,
        target_id=target_id,
        parameters=parameters,
    )
