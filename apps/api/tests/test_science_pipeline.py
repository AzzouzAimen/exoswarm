from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from astropy.io import fits

from exoswarm.domain.enums import ToolStatus
from exoswarm.domain.models import EvidenceRecord
from exoswarm.investigation.tool_registry import scaffold_tool_registry
from exoswarm.science.harmonic import classify_harmonic_relation
from exoswarm.science.pipeline import analyze_cached_candidate

INJECTED_PERIOD_DAYS = 3.2
INJECTED_EPOCH_BTJD = 1001.2
INJECTED_DURATION_HOURS = 3.0
INJECTED_DEPTH_FRACTION = 0.008


def _write_tess_fits(
    path: Path,
    *,
    time: np.ndarray,
    flux: np.ndarray,
    flux_error: np.ndarray,
    quality: np.ndarray | None = None,
    time_unit: str = "d",
    time_system: str = "TDB",
) -> None:
    if quality is None:
        quality = np.zeros(len(time), dtype=np.int32)
    columns = [
        fits.Column(name="TIME", format="D", unit=time_unit, array=time),
        fits.Column(name="PDCSAP_FLUX", format="D", unit="electron/s", array=flux),
        fits.Column(
            name="PDCSAP_FLUX_ERR", format="D", unit="electron/s", array=flux_error
        ),
        fits.Column(name="QUALITY", format="J", array=quality),
    ]
    table = fits.BinTableHDU.from_columns(columns)
    table.header["TIMESYS"] = time_system
    table.header["BJDREFI"] = 2_457_000
    table.header["BJDREFF"] = 0.0
    table.header["SECTOR"] = 42
    table.header["TIMEDEL"] = 20.0 / 60.0 / 24.0
    table.header["OBJECT"] = "TIC 123456789"
    fits.HDUList([fits.PrimaryHDU(), table]).writeto(path, checksum=True)


def _injected_observation(
    path: Path,
    *,
    period_days: float = INJECTED_PERIOD_DAYS,
    epoch_btjd: float = INJECTED_EPOCH_BTJD,
) -> None:
    cadence_days = 20.0 / 60.0 / 24.0
    time = np.arange(1000.0, 1027.0, cadence_days)
    phase_days = (
        (time - epoch_btjd + 0.5 * period_days) % period_days - 0.5 * period_days
    )
    in_transit = np.abs(phase_days) < INJECTED_DURATION_HOURS / 48.0
    rng = np.random.default_rng(20260815)
    relative_flux = (
        1.0
        + 0.0015 * np.sin(2.0 * np.pi * (time - time[0]) / 8.0)
        + rng.normal(0.0, 0.0007, len(time))
        - INJECTED_DEPTH_FRACTION * in_transit
    )
    quality = np.zeros(len(time), dtype=np.int32)
    quality[[50, 700]] = 1
    relative_flux[300] = np.nan
    _write_tess_fits(
        path,
        time=time,
        flux=100_000.0 * relative_flux,
        flux_error=np.full(len(time), 70.0),
        quality=quality,
    )


def _parameters(tmp_path: Path, cached_path: Path, *, minimum_snr: float = 6.0) -> dict:
    return {
        "cached_path": str(cached_path),
        "artifact_dir": str(tmp_path / "runs" / "TARGET-X17" / "run_1" / "artifacts"),
        "ledger_path": str(tmp_path / "runs" / "TARGET-X17" / "run_1" / "evidence.jsonl"),
        "step_id": "step_1",
        "preprocessing": {
            "quality_bitmask": 175,
            "outlier_sigma": 8.0,
            "detrend_window_days": 1.0,
            "gap_threshold_cadences": 5.0,
            "minimum_samples": 200,
        },
        "search": {
            "minimum_period_days": 0.75,
            "maximum_period_days": 6.0,
            "durations_hours": [2.0, 3.0, 4.0],
            "frequency_factor": 1.0,
            "minimum_snr": minimum_snr,
            "minimum_transits": 3,
        },
    }


def _phase_distance(first: float, second: float, period: float) -> float:
    return abs((first - second + 0.5 * period) % period - 0.5 * period)


def test_injected_transit_produces_typed_provenance_backed_candidate(tmp_path: Path) -> None:
    cached_path = tmp_path / "opaque-observation.fits"
    _injected_observation(cached_path)

    result = analyze_cached_candidate(
        run_id="run_1",
        action_id="action_bls_1",
        target_id="TARGET-X17",
        parameters=_parameters(tmp_path, cached_path),
    )

    assert result.status == ToolStatus.SUCCESS
    assert result.measurements["period"].unit == "d"
    assert result.measurements["period"].value == pytest.approx(
        INJECTED_PERIOD_DAYS, abs=0.02
    )
    assert result.measurements["epoch"].unit == "BTJD"
    assert _phase_distance(
        float(result.measurements["epoch"].value),
        INJECTED_EPOCH_BTJD,
        INJECTED_PERIOD_DAYS,
    ) < 0.04
    assert result.measurements["duration"].unit == "h"
    assert result.measurements["duration"].value == pytest.approx(
        INJECTED_DURATION_HOURS, abs=1.0
    )
    assert result.measurements["depth"].unit == "relative_flux_fraction"
    assert result.measurements["depth"].value == pytest.approx(
        INJECTED_DEPTH_FRACTION, rel=0.25
    )
    assert result.measurements["depth"].uncertainty is not None
    assert result.measurements["depth"].uncertainty > 0
    assert result.measurements["snr"].unit == "dimensionless"
    assert result.measurements["snr"].value >= 6.0
    assert result.measurements["usable_transits"].value >= 3

    assert result.diagnostics["time_system"] == "TDB"
    assert result.diagnostics["epoch_convention"] == "BTJD = BJD(TDB) - 2457000.0"
    assert result.diagnostics["input_flux_unit"] == "electron/s"
    assert result.diagnostics["quality_removed_count"] == 2
    assert result.diagnostics["invalid_removed_count"] == 1
    assert result.provenance.source_sha256
    assert result.provenance.source_data_ref.startswith("cached-tess:sha256:")
    assert result.provenance.output_artifact_refs == [
        "artifacts/action_bls_1.candidate-search.json"
    ]
    assert result.provenance.library_versions["astropy"]
    assert result.diagnostics["fits_checksum"]
    assert result.diagnostics["fits_datasum"]

    serialized = result.model_dump_json()
    assert "123456789" not in serialized
    assert str(cached_path) not in serialized

    artifact_path = tmp_path / "runs/TARGET-X17/run_1/artifacts/action_bls_1.candidate-search.json"
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert artifact["processing"]["quality_removed_indices"] == [50, 700]
    assert artifact["processing"]["invalid_removed_indices"] == [300]
    assert len(artifact["bls"]["period_grid_days"]) > 100
    assert min(artifact["phase_folded"]["phase"]) >= -0.5
    assert max(artifact["phase_folded"]["phase"]) < 0.5

    ledger_lines = (tmp_path / "runs/TARGET-X17/run_1/evidence.jsonl").read_text().splitlines()
    assert len(ledger_lines) == 1
    record = EvidenceRecord.model_validate_json(ledger_lines[0])
    assert record.result == result
    assert record.opaque_target_id == "TARGET-X17"


def test_flat_lightcurve_returns_no_evidence_without_candidate_placeholders(tmp_path: Path) -> None:
    cached_path = tmp_path / "flat.fits"
    time = np.arange(1000.0, 1020.0, 20.0 / 60.0 / 24.0)
    _write_tess_fits(
        cached_path,
        time=time,
        flux=np.full(len(time), 100_000.0),
        flux_error=np.full(len(time), 100.0),
    )

    result = analyze_cached_candidate(
        run_id="run_1",
        action_id="action_flat",
        target_id="TARGET-X17",
        parameters=_parameters(tmp_path, cached_path),
    )

    assert result.status == ToolStatus.NO_EVIDENCE
    assert result.measurements == {}
    assert result.reason is not None
    assert result.provenance.output_artifact_refs
    assert result.diagnostics["best_bls_snr"] < 6.0


@pytest.mark.parametrize(
    ("candidate", "expected"),
    [(1.6, "HALF_PERIOD"), (3.2, "SAME_PERIOD"), (6.4, "DOUBLE_PERIOD")],
)
def test_harmonic_period_relations_are_explicit(candidate: float, expected: str) -> None:
    relation = classify_harmonic_relation(candidate, INJECTED_PERIOD_DAYS)
    assert relation.relation == expected
    assert relation.relative_error == pytest.approx(0.0)


def test_recovered_half_period_case_is_classified_against_reference(tmp_path: Path) -> None:
    cached_path = tmp_path / "half-period.fits"
    half_period = INJECTED_PERIOD_DAYS / 2.0
    _injected_observation(cached_path, period_days=half_period, epoch_btjd=1000.8)
    parameters = _parameters(tmp_path, cached_path)
    parameters["search"]["maximum_period_days"] = 4.0

    result = analyze_cached_candidate(
        run_id="run_half",
        action_id="action_half",
        target_id="TARGET-X17",
        parameters=parameters,
    )

    assert result.status == ToolStatus.SUCCESS
    recovered = float(result.measurements["period"].value)
    assert recovered == pytest.approx(half_period, abs=0.02)
    assert classify_harmonic_relation(recovered, INJECTED_PERIOD_DAYS).relation == "HALF_PERIOD"


def test_candidate_is_stable_under_reasonable_detrend_window_change(tmp_path: Path) -> None:
    cached_path = tmp_path / "detrend-sensitivity.fits"
    _injected_observation(cached_path)
    baseline_parameters = _parameters(tmp_path / "baseline", cached_path)
    alternate_parameters = _parameters(tmp_path / "alternate", cached_path)
    alternate_parameters["preprocessing"]["detrend_window_days"] = 1.5

    baseline = analyze_cached_candidate(
        run_id="run_sensitivity",
        action_id="action_baseline",
        target_id="TARGET-X17",
        parameters=baseline_parameters,
    )
    alternate = analyze_cached_candidate(
        run_id="run_sensitivity",
        action_id="action_alternate",
        target_id="TARGET-X17",
        parameters=alternate_parameters,
    )

    assert baseline.status == alternate.status == ToolStatus.SUCCESS
    assert alternate.measurements["period"].value == pytest.approx(
        baseline.measurements["period"].value, abs=0.02
    )
    assert alternate.measurements["depth"].value == pytest.approx(
        baseline.measurements["depth"].value, rel=0.2
    )


def test_identical_input_and_configuration_produce_equivalent_results(tmp_path: Path) -> None:
    cached_path = tmp_path / "deterministic.fits"
    _injected_observation(cached_path)
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"

    first = analyze_cached_candidate(
        run_id="run_determinism",
        action_id="action_same",
        target_id="TARGET-X17",
        parameters=_parameters(first_root, cached_path),
    )
    second = analyze_cached_candidate(
        run_id="run_determinism",
        action_id="action_same",
        target_id="TARGET-X17",
        parameters=_parameters(second_root, cached_path),
    )

    assert first == second
    relative_artifact = "runs/TARGET-X17/run_1/artifacts/action_same.candidate-search.json"
    first_artifact = first_root / relative_artifact
    second_artifact = second_root / relative_artifact
    assert first_artifact.read_bytes() == second_artifact.read_bytes()


def test_evidence_ledger_is_append_only(tmp_path: Path) -> None:
    cached_path = tmp_path / "append-only.fits"
    _injected_observation(cached_path)
    parameters = _parameters(tmp_path, cached_path)

    first = analyze_cached_candidate(
        run_id="run_1",
        action_id="action_first",
        target_id="TARGET-X17",
        parameters=parameters,
    )
    ledger_path = tmp_path / "runs/TARGET-X17/run_1/evidence.jsonl"
    first_line = ledger_path.read_text(encoding="utf-8").splitlines()[0]
    second = analyze_cached_candidate(
        run_id="run_1",
        action_id="action_second",
        target_id="TARGET-X17",
        parameters=parameters,
    )

    lines = ledger_path.read_text(encoding="utf-8").splitlines()
    assert first.status == second.status == ToolStatus.SUCCESS
    assert len(lines) == 2
    assert lines[0] == first_line
    assert EvidenceRecord.model_validate_json(lines[0]).action_id == "action_first"
    assert EvidenceRecord.model_validate_json(lines[1]).action_id == "action_second"


def test_malformed_empty_and_insufficient_inputs_fail_explicitly(tmp_path: Path) -> None:
    malformed = tmp_path / "malformed.fits"
    malformed.write_bytes(b"not a FITS product")
    malformed_result = analyze_cached_candidate(
        run_id="run_1",
        action_id="action_malformed",
        target_id="TARGET-X17",
        parameters=_parameters(tmp_path / "malformed", malformed),
    )
    assert malformed_result.status == ToolStatus.FAILED
    assert malformed_result.measurements == {}

    empty = tmp_path / "empty.fits"
    _write_tess_fits(
        empty,
        time=np.asarray([], dtype=float),
        flux=np.asarray([], dtype=float),
        flux_error=np.asarray([], dtype=float),
    )
    empty_result = analyze_cached_candidate(
        run_id="run_1",
        action_id="action_empty",
        target_id="TARGET-X17",
        parameters=_parameters(tmp_path / "empty", empty),
    )
    assert empty_result.status == ToolStatus.PRECONDITION_FAILED
    assert empty_result.measurements == {}

    insufficient = tmp_path / "insufficient.fits"
    time = np.arange(1000.0, 1001.0, 20.0 / 60.0 / 24.0)
    _write_tess_fits(
        insufficient,
        time=time,
        flux=np.full(len(time), 100_000.0),
        flux_error=np.full(len(time), 100.0),
    )
    insufficient_result = analyze_cached_candidate(
        run_id="run_1",
        action_id="action_insufficient",
        target_id="TARGET-X17",
        parameters=_parameters(tmp_path / "insufficient", insufficient),
    )
    assert insufficient_result.status == ToolStatus.PRECONDITION_FAILED
    assert insufficient_result.measurements == {}


@pytest.mark.parametrize(
    ("time_unit", "time_system"),
    [("s", "TDB"), ("d", "UTC")],
)
def test_ambiguous_time_units_or_system_are_rejected(
    tmp_path: Path, time_unit: str, time_system: str
) -> None:
    cached_path = tmp_path / f"bad-time-{time_unit}-{time_system}.fits"
    time = np.arange(1000.0, 1005.0, 20.0 / 60.0 / 24.0)
    _write_tess_fits(
        cached_path,
        time=time,
        flux=np.full(len(time), 100_000.0),
        flux_error=np.full(len(time), 100.0),
        time_unit=time_unit,
        time_system=time_system,
    )
    result = analyze_cached_candidate(
        run_id="run_units",
        action_id=f"action_{time_unit}_{time_system}",
        target_id="TARGET-X17",
        parameters=_parameters(tmp_path, cached_path),
    )
    assert result.status == ToolStatus.PRECONDITION_FAILED
    assert result.measurements == {}


def test_registry_executes_the_vertical_slice(tmp_path: Path) -> None:
    cached_path = tmp_path / "registry.fits"
    _injected_observation(cached_path)
    result = scaffold_tool_registry().execute(
        "search_bls",
        run_id="run_1",
        action_id="action_registry",
        target_id="TARGET-X17",
        parameters=_parameters(tmp_path, cached_path),
        granted_scopes={"science:execute"},
    )
    assert result.status == ToolStatus.SUCCESS


def test_cached_real_tess_acceptance_case_if_present(tmp_path: Path) -> None:
    case_path = Path(__file__).parents[3] / "evals/fixtures/cached_real_tess_case.json"
    if not case_path.exists():
        pytest.skip(
            "requires evals/fixtures/cached_real_tess_case.json and its referenced cached SPOC FITS"
        )
    case = json.loads(case_path.read_text(encoding="utf-8"))
    cached_path = Path(__file__).parents[3] / case["cached_path"]
    parameters = _parameters(tmp_path, cached_path)
    parameters["search"].update(case.get("search", {}))
    result = analyze_cached_candidate(
        run_id="run_real",
        action_id="action_real",
        target_id=case["opaque_target_id"],
        parameters=parameters,
    )
    assert result.status == ToolStatus.SUCCESS
    expected = case["expected"]
    assert expected["period_days_min"] <= result.measurements["period"].value
    assert result.measurements["period"].value <= expected["period_days_max"]
