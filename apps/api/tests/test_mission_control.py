from __future__ import annotations

import asyncio
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from harness_support import (
    fixture_result,
    make_controller,
    make_registry,
    policy_client,
    seed_baseline,
)
from pydantic import ValidationError

from exoswarm.api.app import create_app
from exoswarm.api.mission_control_models import PlotView
from exoswarm.config import Settings
from exoswarm.domain.enums import InvestigationStatus, ToolStatus
from exoswarm.domain.models import Measurement, RevealResult
from exoswarm.science.plot_projection import MAX_TRACE_POINTS, PLOT_MODES
from exoswarm.security.catalog_gate import CatalogGate
from exoswarm.services.target_registry import TargetRegistry


class CountingRevealProvider:
    def __init__(self) -> None:
        self.calls = 0
        self._lock = threading.Lock()

    def reveal(self, locked_result, locked_sha256):
        with self._lock:
            self.calls += 1
        time.sleep(0.05)
        return RevealResult(
            run_id=locked_result.run_id,
            opaque_target_id=locked_result.opaque_target_id,
            locked_result_sha256=locked_sha256,
            catalog_source="backend test catalog",
            catalog_payload={
                "target_name": "Post-lock fixture identity",
                "tic_id": "123456789",
                "catalog_disposition": "TEST",
                "known_values": {"period_days": 3.2},
            },
        )


def _client(tmp_path, controller, *, cors_origins=None) -> TestClient:
    settings = Settings(
        runs_dir=tmp_path / "runs",
        data_dir=tmp_path / "data",
        cors_origins=cors_origins or ["http://localhost:3000"],
    )
    targets = TargetRegistry(
        settings.data_dir / "targets/source_manifest.json", data_dir=settings.data_dir
    )
    return TestClient(create_app(settings, controller=controller, target_registry=targets))


def _candidate_artifact(point_count: int = 2400) -> dict[str, object]:
    time = [1000.0 + index / 1000.0 for index in range(point_count)]
    flux = [1.0 - (0.01 if index == point_count // 2 else 0.0) for index in range(point_count)]
    periods = [0.5 + index / 1000.0 for index in range(point_count)]
    snr = [float(index % 100) for index in range(point_count)]
    phase = [-0.5 + index / point_count for index in range(point_count)]
    return {
        "schema_version": "1",
        "source": {
            "source_data_ref": "cached-tess:sha256:" + "a" * 64,
            "source_sha256": "a" * 64,
            "sector": 2,
            "cadence_seconds": 120.0,
            "time_system": "TDB",
            "time_unit": "d",
            "epoch_convention": "BTJD = BJD(TDB) - 2457000.0",
            "bjd_reference": 2457000.0,
            "input_flux_unit": "e-/s",
            "source_size_bytes": 100,
            "fits_checksum": None,
            "fits_datasum": None,
            "crowdsap": 0.99,
        },
        "processing": {
            "quality_bitmask": 175,
            "outlier_sigma": 8.0,
            "detrend_window_days": 1.0,
            "gap_threshold_cadences": 5.0,
            "minimum_samples": 20,
            "normalization_flux": 1.0,
            "normalization_flux_unit": "e-/s",
            "detrend_window_samples": 10,
            "quality_removed_indices": [],
            "invalid_removed_indices": [],
            "outlier_removed_indices": [],
            "retained_source_indices": list(range(point_count)),
        },
        "cleaned_lightcurve": {
            "time_btjd": time,
            "relative_flux": flux,
            "relative_flux_error": [0.001] * point_count,
            "trend": [1.0] * point_count,
            "units": {
                "time": "BTJD",
                "relative_flux": "fraction",
                "relative_flux_error": "fraction",
                "trend": "dimensionless",
            },
        },
        "bls": {
            "parameters": {
                "minimum_period_days": 0.5,
                "maximum_period_days": 4.0,
                "durations_hours": [2.0],
                "frequency_factor": 1.0,
                "minimum_snr": 6.0,
                "minimum_transits": 3,
            },
            "period_grid_days": periods,
            "periodogram_depth_snr": snr,
        },
        "phase_folded": {
            "phase": phase,
            "relative_flux": flux,
            "relative_flux_error": [0.001] * point_count,
        },
        "library_versions": {"astropy": "test"},
        "code_version": "test-v1",
    }


def test_snapshot_projects_safe_evidence_decisions_budgets_and_hypotheses(tmp_path) -> None:
    controller = make_controller(tmp_path, policy_client(), make_registry("eclipsing_binary"))
    state = controller.create("TARGET-X17")
    seed_baseline(controller, state.run_id, "eclipsing_binary")
    final = asyncio.run(controller.advance(state.run_id))

    with _client(tmp_path, controller) as client:
        response = client.get(f"/api/investigations/{state.run_id}/mission-control")

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "1"
    assert payload["status"] == InvestigationStatus.READY_TO_LOCK
    assert payload["last_sequence"] == len(controller.events(state.run_id))
    assert payload["budgets"]["model_call_count"] == final.model_call_count
    assert payload["accepted_decisions"][0]["requested_experiment"] == "harmonic_test"
    assert payload["critic_decisions"][0]["verdict"] == "APPROVE"
    assert payload["role_checkpoints"]
    assert payload["lock"]["sha256"] is None
    assert payload["reveal"] is None
    assert "catalog_payload" not in response.text
    assert "source_data_ref" not in response.text
    assert "provenance" not in response.text
    assert all(
        measurement["evidence_ref"].startswith(("evidence_", "artifact_"))
        for item in payload["evidence"]
        for measurement in item["measurements"].values()
    )
    hypothesis_events = [
        event for event in controller.events(state.run_id) if event.type == "hypothesis.updated"
    ]
    assert hypothesis_events
    assert hypothesis_events[-1].payload["active_hypotheses"] == final.active_hypotheses
    assert hypothesis_events[-1].payload["evidence_id"] in final.evidence_refs


def test_snapshot_waits_for_open_run_mutation_and_returns_matching_cursor(tmp_path) -> None:
    controller = make_controller(tmp_path, policy_client(), make_registry("clean"))
    state = controller.create("TARGET-X17")
    app = create_app(
        Settings(runs_dir=tmp_path / "runs", data_dir=tmp_path / "data"),
        controller=controller,
        target_registry=TargetRegistry(
            tmp_path / "data/targets/source_manifest.json",
            data_dir=tmp_path / "data",
        ),
    )
    mutation_open = threading.Event()
    release_mutation = threading.Event()

    def mutate() -> None:
        with controller.run_boundary(state.run_id):
            current = controller.get(state.run_id)
            controller._emit(
                current,
                "budget.updated",
                {**controller._budget_payload(current), "step_count": 1},
            )
            mutation_open.set()
            assert release_mutation.wait(timeout=5)
            controller._replace(current, step_count=1)

    with ThreadPoolExecutor(max_workers=2) as pool:
        mutation = pool.submit(mutate)
        assert mutation_open.wait(timeout=5)
        snapshot = pool.submit(app.state.mission_control.snapshot, state.run_id)
        time.sleep(0.05)
        assert not snapshot.done()
        release_mutation.set()
        mutation.result(timeout=5)
        projected = snapshot.result(timeout=5)

    assert projected.last_sequence == len(controller.events(state.run_id)) == 2
    assert projected.budgets.step_count == 1
    assert controller.events(state.run_id)[-1].payload["step_count"] == 1


def test_plot_routes_are_allowlisted_bounded_and_explicitly_unavailable(tmp_path) -> None:
    controller = make_controller(tmp_path, policy_client(), make_registry("clean"))
    state = controller.create("TARGET-X17")
    artifact_ref = "artifacts/action_plot.candidate-search.json"
    run_dir = controller.artifacts.run_dir(state.opaque_target_id, state.run_id)
    artifact_path = run_dir / artifact_ref
    artifact_path.write_text(json.dumps(_candidate_artifact()), encoding="utf-8")
    search = fixture_result(
        tool_name="search_bls",
        run_id=state.run_id,
        action_id="action_plot",
        target_id=state.opaque_target_id,
        scenario="clean",
    )
    search = search.model_copy(
        update={
            "diagnostics": {"masks_artifact_ref": artifact_ref},
            "measurements": {
                **search.measurements,
                "period": Measurement(value=3.2, unit="d", evidence_ref=artifact_ref),
            },
        }
    )
    controller.record_tool_result(state.run_id, search)
    for index, tool_name in enumerate(("odd_even", "secondary_eclipse"), 1):
        result = fixture_result(
            tool_name=tool_name,
            run_id=state.run_id,
            action_id=f"action_summary_{index}",
            target_id=state.opaque_target_id,
            scenario="clean",
        )
        measurements = (
            {
                "odd_depth": Measurement(value=0.01, unit="relative_flux_fraction"),
                "even_depth": Measurement(value=0.009, unit="relative_flux_fraction"),
            }
            if tool_name == "odd_even"
            else {
                "strongest_secondary_phase": Measurement(value=0.5, unit="orbital_phase"),
                "strongest_secondary_depth": Measurement(
                    value=0.001, unit="relative_flux_fraction"
                ),
            }
        )
        controller.record_tool_result(
            state.run_id, result.model_copy(update={"measurements": measurements})
        )

    with _client(tmp_path, controller) as client:
        for mode in ("raw", "bls", "phase-fold", "odd-even", "secondary"):
            response = client.get(
                f"/api/investigations/{state.run_id}/mission-control/plots/{mode}"
            )
            assert response.status_code == 200
            payload = response.json()
            assert payload["available"] is True
            assert payload["evidence_refs"]
            assert all(len(trace["x"]) <= MAX_TRACE_POINTS for trace in payload["traces"])
            assert all(len(trace["x"]) == len(trace["y"]) for trace in payload["traces"])

        harmonic = client.get(f"/api/investigations/{state.run_id}/mission-control/plots/harmonic")
        unknown = client.get(
            f"/api/investigations/{state.run_id}/mission-control/plots/private.json"
        )

    assert harmonic.status_code == 200
    assert harmonic.json()["available"] is False
    assert harmonic.json()["traces"] == []
    assert unknown.status_code == 422
    with _client(tmp_path, controller) as client:
        raw_values = client.get(
            f"/api/investigations/{state.run_id}/mission-control/plots/raw"
        ).json()["traces"][0]["y"]
    assert min(raw_values) == pytest.approx(0.99)

    harmonic_result = fixture_result(
        tool_name="harmonic_test",
        run_id=state.run_id,
        action_id="action_harmonic",
        target_id=state.opaque_target_id,
        scenario="clean",
        parameters={"trial_factor": 1},
    ).model_copy(
        update={
            "measurements": {
                "half_period_snr": Measurement(value=7.0, unit="dimensionless"),
                "same_period_snr": Measurement(value=11.0, unit="dimensionless"),
                "double_period_snr": Measurement(value=6.0, unit="dimensionless"),
            }
        }
    )
    controller.record_tool_result(state.run_id, harmonic_result)
    with _client(tmp_path, controller) as client:
        harmonic_available = client.get(
            f"/api/investigations/{state.run_id}/mission-control/plots/harmonic"
        )
    assert harmonic_available.status_code == 200
    assert harmonic_available.json()["available"] is True
    assert harmonic_available.json()["traces"] == []
    assert [item["label"] for item in harmonic_available.json()["readouts"]] == [
        "P/2 SNR",
        "P SNR",
        "2P SNR",
    ]
    with _client(tmp_path, controller) as client:
        snapshot = client.get(
            f"/api/investigations/{state.run_id}/mission-control"
        ).json()
        secondary = client.get(
            f"/api/investigations/{state.run_id}/mission-control/plots/secondary"
        ).json()
        odd_even = client.get(
            f"/api/investigations/{state.run_id}/mission-control/plots/odd-even"
        ).json()
    assert snapshot["available_plot_modes"] == list(PLOT_MODES)
    assert secondary["traces"] == []
    assert secondary["x_label"] == secondary["y_label"] == ""
    assert secondary["readouts"] == [
        {
            "label": "phase",
            "value": "0.5 orbital_phase",
            "evidence_ref": secondary["evidence_refs"][0],
        },
        {
            "label": "depth",
            "value": "0.001 relative_flux_fraction",
            "evidence_ref": secondary["evidence_refs"][0],
        },
    ]
    assert odd_even["traces"] == []
    assert odd_even["x_label"] == odd_even["y_label"] == ""
    assert [item["label"] for item in odd_even["readouts"]] == [
        "odd depth",
        "even depth",
    ]
    assert set(PLOT_MODES) == {
        "raw",
        "bls",
        "phase-fold",
        "odd-even",
        "secondary",
        "harmonic",
    }


@pytest.mark.parametrize(
    "status,measurements,expected",
    [
        (ToolStatus.NO_EVIDENCE, {}, False),
        (ToolStatus.PRECONDITION_FAILED, {}, False),
        (ToolStatus.NOT_IMPLEMENTED, {}, False),
        (
            ToolStatus.NO_EVIDENCE,
            {
                "odd_depth": Measurement(value=0.01, unit="relative_flux_fraction"),
                "even_depth": Measurement(value=0.01, unit="relative_flux_fraction"),
            },
            True,
        ),
    ],
)
def test_plot_availability_requires_complete_usable_summary(
    tmp_path, status, measurements, expected
) -> None:
    controller = make_controller(tmp_path, policy_client(), make_registry("clean"))
    state = controller.create("TARGET-X17")
    result = fixture_result(
        tool_name="odd_even",
        run_id=state.run_id,
        action_id="action_summary",
        target_id=state.opaque_target_id,
        scenario="clean",
        status=status,
    ).model_copy(update={"measurements": measurements})
    controller.record_tool_result(state.run_id, result)

    with _client(tmp_path, controller) as client:
        snapshot = client.get(
            f"/api/investigations/{state.run_id}/mission-control"
        ).json()
        plot = client.get(
            f"/api/investigations/{state.run_id}/mission-control/plots/odd-even"
        ).json()

    assert ("odd-even" in snapshot["available_plot_modes"]) is expected
    assert plot["available"] is expected
    assert bool(plot["readouts"]) is expected


def test_route_errors_include_run_id_and_cors_is_configurable(tmp_path) -> None:
    controller = make_controller(tmp_path, policy_client(), make_registry("clean"))
    state = controller.create("TARGET-X17")
    origin = "https://mission.example.test"

    with _client(tmp_path, controller, cors_origins=[origin]) as client:
        reveal = client.post(f"/api/investigations/{state.run_id}/reveal")
        preflight = client.options(
            f"/api/investigations/{state.run_id}/mission-control",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "GET",
            },
        )

    assert reveal.status_code == 403
    assert reveal.json() == {
        "code": "RESULT_NOT_LOCKED",
        "message": "ground-truth reveal is unavailable before result lock",
        "recoverable": True,
        "run_id": state.run_id,
    }
    assert preflight.status_code == 200
    assert preflight.headers["access-control-allow-origin"] == origin


def test_lock_reveal_are_idempotent_and_refresh_from_verified_persistence(tmp_path) -> None:
    provider = CountingRevealProvider()
    controller = make_controller(tmp_path, policy_client(), make_registry("clean"))
    controller.catalog_gate = CatalogGate(controller.artifacts, provider)
    state = controller.create("TARGET-X17")
    seed_baseline(controller, state.run_id, "clean")
    asyncio.run(controller.advance(state.run_id))

    with _client(tmp_path, controller) as client:
        first_lock = client.post(f"/api/investigations/{state.run_id}/lock")
        run_dir = controller.artifacts.run_dir(state.opaque_target_id, state.run_id)
        result_before = (run_dir / "result.json").read_bytes()
        hash_before = (run_dir / "result.json.sha256").read_bytes()
        second_lock = client.post(f"/api/investigations/{state.run_id}/lock")
        first_reveal = client.post(f"/api/investigations/{state.run_id}/reveal")
        reveal_before = (run_dir / "reveal.json").read_bytes()
        second_reveal = client.post(f"/api/investigations/{state.run_id}/reveal")

    assert first_lock.json() == second_lock.json()
    assert first_reveal.json() == second_reveal.json()
    assert provider.calls == 1
    assert (run_dir / "result.json").read_bytes() == result_before
    assert (run_dir / "result.json.sha256").read_bytes() == hash_before
    assert (run_dir / "reveal.json").read_bytes() == reveal_before
    lock_events = [
        event for event in controller.events(state.run_id) if event.type == "result.locked"
    ]
    reveal_events = [
        event for event in controller.events(state.run_id) if event.type == "catalog.revealed"
    ]
    assert len(lock_events) == len(reveal_events) == 1

    restarted = make_controller(tmp_path, policy_client(), make_registry("clean"))
    restarted.catalog_gate = CatalogGate(restarted.artifacts, provider)
    with _client(tmp_path, restarted) as client:
        refreshed = client.get(f"/api/investigations/{state.run_id}/mission-control")

    assert refreshed.status_code == 200
    payload = refreshed.json()
    assert payload["status"] == "REVEALED"
    assert payload["lock"]["sha256"] == first_lock.json()["sha256"]
    assert payload["reveal"]["locked_result_sha256"] == first_lock.json()["sha256"]
    assert payload["reveal"]["catalog_payload"]["tic_id"] == "123456789"
    assert provider.calls == 1


def test_concurrent_lock_and_reveal_are_single_write_across_controllers(tmp_path) -> None:
    provider = CountingRevealProvider()
    first = make_controller(tmp_path, policy_client(), make_registry("clean"))
    state = first.create("TARGET-X17")
    seed_baseline(first, state.run_id, "clean")
    asyncio.run(first.advance(state.run_id))
    second = make_controller(tmp_path, policy_client(), make_registry("clean"))
    first.catalog_gate = CatalogGate(first.artifacts, provider)
    second.catalog_gate = CatalogGate(second.artifacts, provider)
    run_dir = first.artifacts.run_dir(state.opaque_target_id, state.run_id)

    with ThreadPoolExecutor(max_workers=8) as pool:
        lock_futures = [
            pool.submit(controller.lock, state.run_id)
            for controller in (first, second, first, second, first, second, first, second)
        ]
        receipts = [future.result(timeout=10) for future in lock_futures]

    assert len({receipt.model_dump_json() for receipt in receipts}) == 1
    result_bytes = (run_dir / "result.json").read_bytes()
    hash_bytes = (run_dir / "result.json.sha256").read_bytes()

    with ThreadPoolExecutor(max_workers=8) as pool:
        reveal_futures = [
            pool.submit(controller.reveal, state.run_id)
            for controller in (first, second, first, second, first, second, first, second)
        ]
        reveals = [future.result(timeout=10) for future in reveal_futures]

    reveal_bytes = (run_dir / "reveal.json").read_bytes()
    assert len({reveal.model_dump_json() for reveal in reveals}) == 1
    assert provider.calls == 1
    assert (run_dir / "result.json").read_bytes() == result_bytes
    assert (run_dir / "result.json.sha256").read_bytes() == hash_bytes
    assert (run_dir / "reveal.json").read_bytes() == reveal_bytes

    refreshed = make_controller(tmp_path, policy_client(), make_registry("clean"))
    events = refreshed.events(state.run_id)
    assert sum(event.type == "result.locked" for event in events) == 1
    assert sum(event.type == "catalog.revealed" for event in events) == 1


def test_mission_control_response_models_forbid_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        PlotView.model_validate(
            {
                "mode": "raw",
                "available": False,
                "x_label": "",
                "y_label": "",
                "annotation": "unavailable",
                "unexpected": True,
            }
        )
