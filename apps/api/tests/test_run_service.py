from __future__ import annotations

import asyncio
import json
import time
from collections import Counter
from dataclasses import replace

import pytest
from harness_support import make_controller, make_registry, policy_client

from exoswarm.agents.model_client import ScriptedInferenceClient
from exoswarm.domain.enums import InvestigationStatus, ToolExecutionStatus
from exoswarm.investigation.runner import InvestigationRunService, RunExecutionStatus
from exoswarm.investigation.tool_registry import ScientificToolRegistry
from exoswarm.services.target_registry import (
    TargetManifestError,
    TargetMappingNotFoundError,
    TargetRegistry,
)


def _target_registry(tmp_path, target_id: str = "TARGET-X17") -> TargetRegistry:
    data_dir = tmp_path / "data"
    source = data_dir / "cached" / "lightcurves" / "secret-cached-source.fits"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"fixture-source")
    manifest = data_dir / "targets" / "source_manifest.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        json.dumps(
            {
                "schema_version": "1",
                "targets": [
                    {
                        "opaque_target_id": target_id,
                        "cached_lightcurve_path": (
                            "cached/lightcurves/secret-cached-source.fits"
                        ),
                        "cached_tpf_path": None,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return TargetRegistry(manifest, data_dir=data_dir)


def _service(tmp_path, controller, registry: TargetRegistry) -> InvestigationRunService:
    return InvestigationRunService(
        controller,
        registry,
        runs_dir=tmp_path / "runs",
        timeout_seconds=2,
        sse_poll_interval_seconds=0.001,
    )


def test_versioned_target_registry_resolves_source_but_lists_only_safe_metadata(
    tmp_path,
) -> None:
    registry = _target_registry(tmp_path)

    source = registry.resolve("TARGET-X17")
    public = registry.list_agent_safe()

    assert source.cached_path.name == "secret-cached-source.fits"
    assert public == [
        {
            "opaque_target_id": "TARGET-X17",
            "cached_lightcurve_available": True,
            "cached_tpf_available": False,
        }
    ]
    assert "path" not in json.dumps(public)


def test_target_registry_rejects_unknown_manifest_version(tmp_path) -> None:
    manifest = tmp_path / "data/targets/source_manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text('{"schema_version":"2","targets":[]}', encoding="utf-8")

    with pytest.raises(TargetManifestError, match="source_manifest.json"):
        TargetRegistry(manifest, data_dir=tmp_path / "data")


@pytest.mark.asyncio
async def test_start_duplicate_start_and_terminal_stop_are_idempotent(tmp_path) -> None:
    calls: Counter[str] = Counter()
    controller = make_controller(
        tmp_path,
        policy_client(),
        make_registry("clean", calls=calls),
    )
    service = _service(tmp_path, controller, _target_registry(tmp_path))

    first_state, first_execution = await service.create_and_start("TARGET-X17", "request-1")
    duplicate_state, duplicate_execution = await service.create_and_start(
        "TARGET-X17", "request-1"
    )

    assert duplicate_state.run_id == first_state.run_id
    assert first_execution.status == RunExecutionStatus.RUNNING
    assert duplicate_execution.active

    execution = await service.wait(first_state.run_id)
    final = controller.get(first_state.run_id)
    assert execution.status == RunExecutionStatus.STOPPED
    assert final.status == InvestigationStatus.READY_TO_LOCK
    calls_after_completion = calls.copy()

    stopped = await service.start(first_state.run_id)
    assert stopped.status == RunExecutionStatus.STOPPED
    assert calls == calls_after_completion


@pytest.mark.asyncio
async def test_failed_controller_run_stops_without_spinning(tmp_path) -> None:
    controller = make_controller(
        tmp_path,
        ScriptedInferenceClient({}),
        make_registry("clean"),
    )
    service = _service(tmp_path, controller, _target_registry(tmp_path))

    state, _ = await service.create_and_start("TARGET-X17", "failed-request")
    execution = await service.wait(state.run_id)
    failed = controller.get(state.run_id)

    assert execution.status == RunExecutionStatus.FAILED
    assert failed.status == InvestigationStatus.FAILED
    assert execution.advances <= failed.max_steps + 1
    assert not execution.active


@pytest.mark.asyncio
async def test_restart_resumes_durable_state_and_preserves_event_order(tmp_path) -> None:
    registry = _target_registry(tmp_path)
    first = make_controller(tmp_path, policy_client(), make_registry("clean"))
    state = first.create("TARGET-X17")
    state = await first.advance(state.run_id)
    state = await first.advance(state.run_id)
    sequences_before = [event.sequence for event in first.events(state.run_id)]

    restarted = make_controller(tmp_path, policy_client(), make_registry("clean"))
    service = _service(tmp_path, restarted, registry)
    durable, execution = await service.resume(state.run_id)
    assert durable.step_count == 2
    assert execution.status == RunExecutionStatus.RUNNING

    await service.wait(state.run_id)
    final = restarted.get(state.run_id)
    sequences = [event.sequence for event in restarted.events(state.run_id)]
    assert final.status == InvestigationStatus.READY_TO_LOCK
    assert sequences[: len(sequences_before)] == sequences_before
    assert sequences == list(range(1, len(sequences) + 1))


@pytest.mark.asyncio
async def test_same_run_cannot_advance_in_two_tasks(tmp_path) -> None:
    registry = _target_registry(tmp_path)
    controller = make_controller(tmp_path, policy_client(), make_registry("clean"))
    state = controller.create("TARGET-X17")
    original_advance = controller.advance
    active = 0
    maximum_active = 0

    async def observed_advance(run_id: str):
        nonlocal active, maximum_active
        active += 1
        maximum_active = max(maximum_active, active)
        try:
            await asyncio.sleep(0.005)
            return await original_advance(run_id)
        finally:
            active -= 1

    controller.advance = observed_advance  # type: ignore[method-assign]
    service = _service(tmp_path, controller, registry)
    first, second = await asyncio.gather(service.start(state.run_id), service.start(state.run_id))

    assert first.run_id == second.run_id
    await service.wait(state.run_id)
    assert maximum_active == 1


@pytest.mark.asyncio
async def test_process_lease_prevents_a_second_service_from_driving_same_run(tmp_path) -> None:
    registry = _target_registry(tmp_path)
    controller = make_controller(tmp_path, policy_client(), make_registry("clean"))
    state = controller.create("TARGET-X17")
    original_advance = controller.advance
    gate = asyncio.Event()
    calls = 0

    async def gated_advance(run_id: str):
        nonlocal calls
        calls += 1
        await gate.wait()
        return await original_advance(run_id)

    controller.advance = gated_advance  # type: ignore[method-assign]
    first_service = _service(tmp_path, controller, registry)
    second_service = _service(tmp_path, controller, registry)

    await first_service.start(state.run_id)
    await asyncio.sleep(0)
    second = await second_service.start(state.run_id)
    assert second.stop_reason == "ACTIVE_IN_ANOTHER_PROCESS"
    await asyncio.sleep(0.01)
    assert calls == 1

    gate.set()
    await first_service.wait(state.run_id)
    assert calls <= controller.get(state.run_id).max_steps + 1


@pytest.mark.asyncio
async def test_missing_mapping_fails_before_run_creation(tmp_path) -> None:
    registry = _target_registry(tmp_path)
    controller = make_controller(tmp_path, policy_client(), make_registry("clean"))
    service = _service(tmp_path, controller, registry)

    with pytest.raises(TargetMappingNotFoundError, match="TARGET-MISSING"):
        await service.create_and_start("TARGET-MISSING", "missing-request")

    assert not list((tmp_path / "runs").glob("TARGET-MISSING/*/state.json"))


@pytest.mark.asyncio
async def test_runner_stops_after_one_cycle_without_durable_progress(tmp_path) -> None:
    registry = _target_registry(tmp_path)
    controller = make_controller(tmp_path, policy_client(), make_registry("clean"))
    state = controller.create("TARGET-X17")
    calls = 0

    async def stalled_advance(run_id: str):
        nonlocal calls
        calls += 1
        return controller.get(run_id)

    controller.advance = stalled_advance  # type: ignore[method-assign]
    service = _service(tmp_path, controller, registry)

    await service.start(state.run_id)
    execution = await service.wait(state.run_id)

    assert execution.status == RunExecutionStatus.FAILED
    assert execution.stop_reason == "NO_DURABLE_PROGRESS"
    assert execution.advances == 1
    assert calls == 1
    durable = controller.get(state.run_id)
    assert durable.status == InvestigationStatus.FAILED
    assert "RUNNER_NO_PROGRESS" in (durable.terminal_reason or "")

    restarted = _service(tmp_path, controller, registry)
    recovered = restarted.inspect(state.run_id)
    assert recovered.status == RunExecutionStatus.FAILED
    assert recovered.stop_reason == durable.terminal_reason


@pytest.mark.asyncio
async def test_unexpected_runner_failure_is_durable_across_service_restart(tmp_path) -> None:
    registry = _target_registry(tmp_path)
    controller = make_controller(tmp_path, policy_client(), make_registry("clean"))
    state = controller.create("TARGET-X17")

    async def explode(_run_id: str):
        raise RuntimeError("boom")

    controller.advance = explode  # type: ignore[method-assign]
    service = _service(tmp_path, controller, registry)

    await service.start(state.run_id)
    execution = await service.wait(state.run_id)

    assert execution.status == RunExecutionStatus.FAILED
    durable = controller.get(state.run_id)
    assert durable.status == InvestigationStatus.FAILED
    assert "RUNNER_FAILURE" in (durable.terminal_reason or "")
    restarted = _service(tmp_path, controller, registry)
    assert restarted.inspect(state.run_id).status == RunExecutionStatus.FAILED


@pytest.mark.asyncio
async def test_wall_clock_timeout_preempts_sync_tool_commit_and_is_durable(tmp_path) -> None:
    registry = _target_registry(tmp_path)
    base_registry = make_registry("clean")
    original = base_registry.resolve("search_bls").handler

    def slow_search(run_id, action_id, target_id, parameters):
        time.sleep(0.3)
        return original(run_id, action_id, target_id, parameters)

    science_registry = ScientificToolRegistry(
        replace(spec, handler=slow_search) if spec.name == "search_bls" else spec
        for spec in base_registry.specs
    )
    controller = make_controller(tmp_path, policy_client(), science_registry)
    state = controller.create("TARGET-X17")
    service = InvestigationRunService(
        controller,
        registry,
        runs_dir=tmp_path / "runs",
        timeout_seconds=0.1,
        sse_poll_interval_seconds=0.001,
    )

    await service.start(state.run_id)
    execution = await service.wait(state.run_id)

    assert execution.status == RunExecutionStatus.FAILED
    durable = controller.get(state.run_id)
    assert durable.status == InvestigationStatus.FAILED
    assert "RUNNER_TIMEOUT" in (durable.terminal_reason or "")
    assert durable.tool_executions[-1].status == ToolExecutionStatus.FAILED

    await asyncio.sleep(0.32)
    assert controller.get(state.run_id).status == InvestigationStatus.FAILED
    assert controller.evidence(state.run_id) == ()


@pytest.mark.asyncio
async def test_cached_source_path_never_enters_state_or_events(tmp_path) -> None:
    registry = _target_registry(tmp_path)
    controller = make_controller(tmp_path, policy_client(), make_registry("clean"))
    service = _service(tmp_path, controller, registry)

    state, _ = await service.create_and_start("TARGET-X17", "private-source-request")
    await service.wait(state.run_id)
    public_material = json.dumps(
        {
            "state": controller.get(state.run_id).model_dump(mode="json"),
            "events": [
                event.model_dump(mode="json") for event in controller.events(state.run_id)
            ],
        }
    )

    assert "secret-cached-source.fits" not in public_material
    assert "cached_path" not in public_material
