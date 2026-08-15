from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from exoswarm.domain.enums import ToolStatus
from exoswarm.domain.errors import ActionValidationError
from exoswarm.investigation.tool_registry import scaffold_tool_registry
from exoswarm.science.contamination import screen_contamination
from exoswarm.science.harmonic import test_harmonics as run_harmonic_test
from exoswarm.science.odd_even import compare_odd_even
from exoswarm.science.secondary import search_secondary

PERIOD_DAYS = 3.2
EPOCH_BTJD = 1001.2
DURATION_HOURS = 3.0
CADENCE_DAYS = 20.0 / 60.0 / 24.0


def _write_candidate_artifact(
    path: Path,
    *,
    baseline_days: float = 27.0,
    odd_depth: float = 0.008,
    even_depth: float = 0.008,
    secondary_depth: float = 0.0,
    noise: float = 0.0005,
    crowdsap: float | None = 0.99,
    units: dict[str, str] | None = None,
) -> Path:
    time = np.arange(1000.0, 1000.0 + baseline_days, CADENCE_DAYS)
    centered_days = (time - EPOCH_BTJD + 0.5 * PERIOD_DAYS) % PERIOD_DAYS - 0.5 * PERIOD_DAYS
    primary = np.abs(centered_days) <= DURATION_HOURS / 48.0
    transit_numbers = np.rint((time - EPOCH_BTJD) / PERIOD_DAYS).astype(np.int64)
    depths = np.where(transit_numbers % 2 == 0, even_depth, odd_depth)
    secondary_centered = (
        time - (EPOCH_BTJD + 0.5 * PERIOD_DAYS) + 0.5 * PERIOD_DAYS
    ) % PERIOD_DAYS - 0.5 * PERIOD_DAYS
    secondary = np.abs(secondary_centered) <= DURATION_HOURS / 48.0
    rng = np.random.default_rng(20260815)
    flux = (
        np.ones(len(time))
        + rng.normal(0.0, noise, len(time))
        - depths * primary
        - secondary_depth * secondary
    )
    errors = np.full(len(time), noise if noise > 0 else 0.0005)
    phases = ((time - EPOCH_BTJD + 0.5 * PERIOD_DAYS) % PERIOD_DAYS) / PERIOD_DAYS - 0.5
    order = np.argsort(phases, kind="stable")
    payload = {
        "schema_version": "1",
        "source": {
            "source_data_ref": "cached-tess:sha256:" + "a" * 64,
            "source_sha256": "a" * 64,
            "sector": 42,
            "cadence_seconds": 1200.0,
            "time_system": "TDB",
            "time_unit": "d",
            "epoch_convention": "BTJD = BJD(TDB) - 2457000.0",
            "bjd_reference": 2457000.0,
            "input_flux_unit": "electron/s",
            "source_size_bytes": 1234,
            "fits_checksum": "fixture-checksum",
            "fits_datasum": "fixture-datasum",
            "crowdsap": crowdsap,
        },
        "processing": {
            "quality_bitmask": 175,
            "outlier_sigma": 8.0,
            "detrend_window_days": 1.0,
            "gap_threshold_cadences": 5.0,
            "minimum_samples": 200,
            "normalization_flux": 100000.0,
            "normalization_flux_unit": "electron/s",
            "detrend_window_samples": 73,
            "quality_removed_indices": [],
            "invalid_removed_indices": [],
            "outlier_removed_indices": [],
            "retained_source_indices": list(range(len(time))),
        },
        "cleaned_lightcurve": {
            "time_btjd": time.tolist(),
            "relative_flux": flux.tolist(),
            "relative_flux_error": errors.tolist(),
            "trend": np.ones(len(time)).tolist(),
            "units": units
            or {
                "time": "BTJD",
                "relative_flux": "fraction",
                "relative_flux_error": "fraction",
                "trend": "dimensionless",
            },
        },
        "bls": {
            "parameters": {
                "minimum_period_days": 0.75,
                "maximum_period_days": 6.5,
                "durations_hours": [2.0, 3.0, 4.0],
                "frequency_factor": 1.0,
                "minimum_snr": 6.0,
                "minimum_transits": 3,
            },
            "period_grid_days": [3.1, PERIOD_DAYS, 3.3],
            "periodogram_depth_snr": [2.0, 20.0, 3.0],
        },
        "phase_folded": {
            "phase": phases[order].tolist(),
            "relative_flux": flux[order].tolist(),
            "relative_flux_error": errors[order].tolist(),
        },
        "library_versions": {"astropy": "fixture", "numpy": "fixture"},
        "code_version": "fixture-v1",
    }
    path.write_text(
        json.dumps(payload, allow_nan=False, separators=(",", ":"), sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def _invoke(handler, artifact_path: Path):
    return handler(
        "run_1",
        "action_1",
        "TARGET-X17",
        {"candidate_artifact_path": artifact_path},
    )


def _neighbor_context(*, delta_magnitude: float | None) -> dict:
    neighbors = []
    if delta_magnitude is not None:
        neighbors.append(
            {
                "neighbor_id": "NEIGHBOR-1",
                "separation_arcsec": 8.0,
                "delta_magnitude": delta_magnitude,
            }
        )
    return {
        "source_data_ref": "cached-neighbors:sha256:" + "b" * 64,
        "source_sha256": "b" * 64,
        "magnitude_band": "TESS",
        "search_radius_arcsec": 60.0,
        "aperture_radius_arcsec": 20.0,
        "neighbors": neighbors,
    }


def test_odd_even_detects_controlled_depth_mismatch_with_explicit_units(tmp_path: Path) -> None:
    artifact = _write_candidate_artifact(tmp_path / "candidate.json", odd_depth=0.001)

    result = _invoke(compare_odd_even, artifact)

    assert result.status == ToolStatus.SUCCESS
    assert result.measurements["odd_depth"].unit == "relative_flux_fraction"
    assert result.measurements["even_depth"].value == pytest.approx(0.008, abs=0.001)
    assert result.measurements["odd_depth"].value == pytest.approx(0.001, abs=0.001)
    assert result.measurements["absolute_difference_significance"].unit == "sigma"
    assert result.measurements["absolute_difference_significance"].value >= 3.0
    assert result.diagnostics["parity_convention"].endswith("zero is even")
    assert result.diagnostics["interpretation_code"] == "ODD_EVEN_MISMATCH"


def test_odd_even_clean_control_preserves_no_evidence(tmp_path: Path) -> None:
    result = _invoke(compare_odd_even, _write_candidate_artifact(tmp_path / "candidate.json"))

    assert result.status == ToolStatus.NO_EVIDENCE
    assert result.reason == "no odd/even depth mismatch reached 3 sigma"
    assert result.measurements
    assert result.diagnostics["interpretation_code"] == "ODD_EVEN_CONSISTENT"


def test_odd_even_insufficient_transits_is_typed_precondition(tmp_path: Path) -> None:
    artifact = _write_candidate_artifact(tmp_path / "short.json", baseline_days=8.0)

    result = _invoke(compare_odd_even, artifact)

    assert result.status == ToolStatus.PRECONDITION_FAILED
    assert result.measurements == {}
    assert "at least 4 usable transits" in (result.reason or "")


def test_secondary_search_detects_injected_phase_half_event(tmp_path: Path) -> None:
    artifact = _write_candidate_artifact(
        tmp_path / "secondary.json", secondary_depth=0.004
    )

    result = _invoke(search_secondary, artifact)

    assert result.status == ToolStatus.SUCCESS
    assert result.measurements["strongest_secondary_phase"].value == pytest.approx(
        0.5, abs=0.03
    )
    assert result.measurements["strongest_secondary_phase"].unit == "orbital_phase"
    assert result.measurements["strongest_secondary_time_offset"].unit == "d"
    assert result.measurements["strongest_secondary_depth"].unit == (
        "relative_flux_fraction"
    )
    assert result.measurements["strongest_secondary_significance"].unit == "sigma"
    assert result.diagnostics["interpretation_code"] == "SECONDARY_ECLIPSE_DETECTED"


def test_secondary_clean_control_is_negative_not_failure(tmp_path: Path) -> None:
    result = _invoke(search_secondary, _write_candidate_artifact(tmp_path / "clean.json"))

    assert result.status == ToolStatus.NO_EVIDENCE
    assert result.measurements
    assert "false-alarm probability" in result.warnings[0]
    assert result.diagnostics["interpretation_code"] == "NO_SECONDARY_ECLIPSE"


def test_secondary_short_baseline_is_indeterminate_precondition(tmp_path: Path) -> None:
    artifact = _write_candidate_artifact(tmp_path / "short.json", baseline_days=5.0)

    result = _invoke(search_secondary, artifact)

    assert result.status == ToolStatus.PRECONDITION_FAILED
    assert "at least 2 periods" in (result.reason or "")


def test_harmonic_pack_measures_half_same_and_double_periods(tmp_path: Path) -> None:
    artifact = _write_candidate_artifact(
        tmp_path / "alias.json", odd_depth=0.001, even_depth=0.012
    )

    result = _invoke(run_harmonic_test, artifact)

    assert result.status == ToolStatus.SUCCESS
    assert result.measurements["half_period_period"].value == pytest.approx(1.6)
    assert result.measurements["same_period_period"].value == pytest.approx(3.2)
    assert result.measurements["double_period_period"].value == pytest.approx(6.4)
    assert result.measurements["half_period_period"].unit == "d"
    assert result.measurements["same_period_depth"].unit == "relative_flux_fraction"
    assert result.measurements["double_period_duration"].unit == "h"
    assert set(result.diagnostics["trial_factors"]) == {
        "half_period",
        "same_period",
        "double_period",
    }
    assert result.diagnostics["strongest_alternative"] == "double_period"
    assert result.measurements["strongest_alternative_snr_advantage"].value >= 1.0
    assert result.diagnostics["interpretation_code"] == "HARMONIC_ALIAS_PREFERRED"


def test_harmonic_short_baseline_is_typed_precondition(tmp_path: Path) -> None:
    artifact = _write_candidate_artifact(tmp_path / "short.json", baseline_days=5.0)

    result = _invoke(run_harmonic_test, artifact)

    assert result.status == ToolStatus.PRECONDITION_FAILED
    assert result.measurements == {}


@pytest.mark.parametrize(
    ("delta_magnitude", "expected_status", "expected_capable"),
    [
        (3.0, ToolStatus.SUCCESS, 1),
        (8.0, ToolStatus.NO_EVIDENCE, 0),
        (None, ToolStatus.NO_EVIDENCE, 0),
    ],
)
def test_contamination_screening_positive_and_negative_controls(
    tmp_path: Path,
    delta_magnitude: float | None,
    expected_status: ToolStatus,
    expected_capable: int,
) -> None:
    artifact = _write_candidate_artifact(tmp_path / "candidate.json")

    result = screen_contamination(
        "run_1",
        "action_1",
        "TARGET-X17",
        {
            "candidate_artifact_path": artifact,
            "neighbor_context": _neighbor_context(delta_magnitude=delta_magnitude),
        },
    )

    assert result.status == expected_status
    assert result.measurements["depth_capable_neighbor_count"].value == expected_capable
    assert result.measurements["neighbor_dilution_fraction"].unit == (
        "relative_flux_fraction"
    )
    assert result.diagnostics["neighbor_source_sha256"] == "b" * 64
    assert "centroid" in result.warnings[0]


def test_contamination_screening_uses_labeled_spoc_crowding_fallback(
    tmp_path: Path,
) -> None:
    artifact = _write_candidate_artifact(
        tmp_path / "candidate.json",
        crowdsap=0.98724049,
    )

    result = screen_contamination(
        "run_1",
        "action_1",
        "TARGET-X17",
        {"candidate_artifact_path": artifact},
    )

    assert result.status == ToolStatus.SUCCESS
    assert result.measurements["spoc_crowdsap"].value == pytest.approx(0.98724049)
    assert result.measurements["aperture_contamination_fraction"].value == pytest.approx(
        1.0 - 0.98724049
    )
    assert result.diagnostics["contamination_mode"] == "SPOC_CROWDSAP"
    assert result.diagnostics["interpretation_code"] == "CONTAMINATION_POSSIBLE"
    assert any("no source localization" in warning for warning in result.warnings)


def test_candidate_artifact_unit_ambiguity_fails_loudly(tmp_path: Path) -> None:
    artifact = _write_candidate_artifact(
        tmp_path / "bad-units.json",
        units={
            "time": "day",
            "relative_flux": "fraction",
            "relative_flux_error": "fraction",
            "trend": "dimensionless",
        },
    )

    result = _invoke(compare_odd_even, artifact)

    assert result.status == ToolStatus.PRECONDITION_FAILED
    assert result.measurements == {}
    assert "schema version 1" in (result.reason or "")


@pytest.mark.parametrize(
    "handler",
    [compare_odd_even, search_secondary, run_harmonic_test],
)
def test_vetting_results_are_deterministic_and_do_not_expose_paths(
    tmp_path: Path, handler
) -> None:
    artifact = _write_candidate_artifact(tmp_path / "recognizable-target.json")

    first = _invoke(handler, artifact)
    second = _invoke(handler, artifact)

    assert first == second
    serialized = first.model_dump_json()
    assert str(artifact) not in serialized
    assert "recognizable-target" not in serialized
    assert first.parameters == {}
    assert first.provenance.source_sha256 == "a" * 64
    assert first.provenance.input_artifact_refs[0].startswith(
        "candidate-artifact:sha256:"
    )


def test_registry_keeps_candidate_path_out_of_model_parameters(tmp_path: Path) -> None:
    artifact = _write_candidate_artifact(tmp_path / "candidate.json")
    registry = scaffold_tool_registry()

    with pytest.raises(ActionValidationError, match="parameters for odd_even"):
        registry.execute(
            "odd_even",
            run_id="run_1",
            action_id="action_1",
            target_id="TARGET-X17",
            parameters={"candidate_artifact_path": artifact},
            granted_scopes={"science:execute"},
        )
    with pytest.raises(ActionValidationError, match="backend runtime inputs"):
        registry.execute(
            "odd_even",
            run_id="run_1",
            action_id="action_1",
            target_id="TARGET-X17",
            runtime_inputs={"candidate_artifact_path": str(artifact)},
            granted_scopes={"science:execute"},
        )

    result = registry.execute(
        "odd_even",
        run_id="run_1",
        action_id="action_1",
        target_id="TARGET-X17",
        parameters={},
        runtime_inputs={"candidate_artifact_path": artifact},
        granted_scopes={"science:execute"},
    )
    assert result.parameters == {}
    assert result.status == ToolStatus.NO_EVIDENCE


def test_contamination_runtime_schema_rejects_incomplete_neighbor_coverage(
    tmp_path: Path,
) -> None:
    artifact = _write_candidate_artifact(tmp_path / "candidate.json")
    context = _neighbor_context(delta_magnitude=3.0)
    context["search_radius_arcsec"] = 10.0
    context["aperture_radius_arcsec"] = 20.0

    with pytest.raises(ActionValidationError, match="backend runtime inputs"):
        scaffold_tool_registry().execute(
            "contamination_screening",
            run_id="run_1",
            action_id="action_1",
            target_id="TARGET-X17",
            runtime_inputs={
                "candidate_artifact_path": artifact,
                "neighbor_context": context,
            },
            granted_scopes={"science:execute"},
        )


def test_contamination_screening_is_deterministic_and_path_safe(tmp_path: Path) -> None:
    artifact = _write_candidate_artifact(tmp_path / "recognizable-target.json")
    invocation = {
        "candidate_artifact_path": artifact,
        "neighbor_context": _neighbor_context(delta_magnitude=3.0),
    }

    first = screen_contamination(
        "run_1", "action_1", "TARGET-X17", invocation
    )
    second = screen_contamination(
        "run_1", "action_1", "TARGET-X17", invocation
    )

    assert first == second
    serialized = first.model_dump_json()
    assert str(artifact) not in serialized
    assert "recognizable-target" not in serialized
    assert first.parameters == {}
