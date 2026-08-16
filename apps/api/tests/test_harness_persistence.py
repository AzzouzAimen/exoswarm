from __future__ import annotations

from collections import Counter

import pytest
from harness_support import (
    fixture_result,
    make_controller,
    make_registry,
    policy_client,
    seed_baseline,
)

from exoswarm.agents.director import DirectorRoute
from exoswarm.domain.enums import (
    HarnessFailureKind,
    InvestigationStatus,
    ToolExecutionStatus,
)
from exoswarm.domain.errors import ActionValidationError
from exoswarm.domain.models import EvidenceRecord, ToolExecutionRecord


@pytest.mark.asyncio
async def test_restart_resumes_durable_finalizing_phase(tmp_path) -> None:
    registry = make_registry("clean")
    first = make_controller(tmp_path, policy_client(), registry)
    state = first.create("TARGET-X17")
    seed_baseline(first, state.run_id, "clean")

    update = first.evaluate_cycle_result(state.run_id)
    prepared = first.get(state.run_id)

    assert update == {"current_route": DirectorRoute.FINALIZE}
    assert prepared.status == InvestigationStatus.FINALIZING
    assert prepared.pending_final_reason

    restarted = make_controller(tmp_path, policy_client(), registry)
    assert restarted.determine_route(state.run_id) == DirectorRoute.FINALIZE

    await restarted.finalize_cycle(state.run_id)
    finalized = restarted.get(state.run_id)

    assert finalized.status == InvestigationStatus.READY_TO_LOCK
    assert finalized.pending_final_reason is None


@pytest.mark.asyncio
async def test_restart_resumes_partial_run_without_duplicate_tools_or_ledger_records(
    tmp_path,
) -> None:
    calls: Counter[str] = Counter()
    registry = make_registry("eclipsing_binary", calls=calls)
    first = make_controller(tmp_path, policy_client(), registry)
    state = first.create("TARGET-X17")

    state = await first.advance(state.run_id)
    state = await first.advance(state.run_id)
    assert state.completed_tests == ["signal_quality", "odd_even"]
    original_trace = first.events(state.run_id)
    original_evidence = first.evidence(state.run_id)

    restarted = make_controller(tmp_path, policy_client(), registry)
    recovered = restarted.get(state.run_id)
    assert recovered == state
    assert restarted.events(state.run_id) == original_trace
    assert restarted.evidence(state.run_id) == original_evidence

    recovered = await restarted.advance(state.run_id)
    recovered = await restarted.advance(state.run_id)
    recovered = await restarted.advance(state.run_id)

    assert recovered.status == InvestigationStatus.READY_TO_LOCK
    assert len(restarted.evidence(state.run_id)) == 5
    assert len({record.evidence_id for record in restarted.evidence(state.run_id)}) == 5
    assert len({record.action_id for record in restarted.evidence(state.run_id)}) == 5
    assert calls == Counter(
        {
            "search_bls": 1,
            "odd_even": 1,
            "secondary_eclipse": 1,
            "contamination_screening": 1,
            "harmonic_test": 1,
        }
    )

    before = restarted.get(state.run_id)
    final_restart = make_controller(tmp_path, policy_client(), registry)
    after = await final_restart.advance(state.run_id)
    assert after == before
    assert calls["harmonic_test"] == 1
    assert len(final_restart.evidence(state.run_id)) == 5


@pytest.mark.asyncio
async def test_trace_and_evidence_are_append_only_and_monotonically_ordered(tmp_path) -> None:
    controller = make_controller(tmp_path, policy_client(), make_registry("contamination"))
    state = controller.create("TARGET-X17")
    first_trace_line = (
        controller.artifacts.run_dir(state.opaque_target_id, state.run_id) / "trace.jsonl"
    ).read_text(encoding="utf-8").splitlines()[0]

    for _ in range(4):
        state = await controller.advance(state.run_id)
    evidence_path = controller.artifacts.evidence_path(state)
    first_evidence_line = evidence_path.read_text(encoding="utf-8").splitlines()[0]
    state = await controller.advance(state.run_id)

    trace_lines = (
        controller.artifacts.run_dir(state.opaque_target_id, state.run_id) / "trace.jsonl"
    ).read_text(encoding="utf-8").splitlines()
    evidence_lines = evidence_path.read_text(encoding="utf-8").splitlines()
    sequences = [event.sequence for event in controller.events(state.run_id)]
    assert trace_lines[0] == first_trace_line
    assert evidence_lines[0] == first_evidence_line
    assert sequences == list(range(1, len(sequences) + 1))
    assert len(evidence_lines) == 5


@pytest.mark.asyncio
async def test_restart_recovers_ledger_committed_prepared_action_without_reexecution(
    tmp_path,
) -> None:
    calls: Counter[str] = Counter()
    registry = make_registry("eclipsing_binary", calls=calls)
    first = make_controller(tmp_path, policy_client(), registry)
    state = first.create("TARGET-X17")
    seed_baseline(first, state.run_id, "eclipsing_binary")
    state = first.get(state.run_id)
    state = first._replace(  # noqa: SLF001 - intentional crash-checkpoint fixture
        state, status=InvestigationStatus.SELECTING_ADAPTIVE_EXPERIMENT
    )
    state = first._replace(  # noqa: SLF001
        state, status=InvestigationStatus.WAITING_FOR_CRITIC
    )
    state = first._replace(state, status=InvestigationStatus.RUNNING_TOOL)  # noqa: SLF001
    parameters = {"trial_factor": 1}
    action_id = "action_interrupted_commit"
    execution = ToolExecutionRecord(
        action_id=action_id,
        step_id="step_0000",
        tool_name="harmonic_test",
        parameters=parameters,
        action_signature=first._action_signature("harmonic_test", parameters),  # noqa: SLF001
        status=ToolExecutionStatus.PREPARED,
        adaptive=True,
        adaptive_cost_units=1,
    )
    state = first._replace(  # noqa: SLF001
        state,
        tool_call_count=state.tool_call_count + 1,
        adaptive_experiments_used=state.adaptive_experiments_used + 1,
        adaptive_cost_units_used=state.adaptive_cost_units_used + 1,
        adaptive_cost_units_remaining=state.adaptive_cost_units_remaining - 1,
        tool_executions=[*state.tool_executions, execution],
    )
    result = fixture_result(
        tool_name="harmonic_test",
        run_id=state.run_id,
        action_id=action_id,
        target_id=state.opaque_target_id,
        scenario="eclipsing_binary",
        parameters=parameters,
        interpretation_code="ODD_EVEN_MISMATCH",
    )
    record = EvidenceRecord(
        evidence_id=first._evidence_id(result),  # noqa: SLF001
        run_id=state.run_id,
        step_id="step_0000",
        action_id=action_id,
        opaque_target_id=state.opaque_target_id,
        tool_name=result.tool_name,
        tool_status=result.status,
        result=result,
        interpretation_code="ODD_EVEN_MISMATCH",
    )
    first.artifacts.append_evidence(state, record)

    restarted = make_controller(tmp_path, policy_client(), registry)
    recovered = await restarted.advance(state.run_id)

    assert recovered.status == InvestigationStatus.READY_TO_LOCK
    assert calls["harmonic_test"] == 0
    assert len(restarted.evidence(state.run_id)) == 5
    recovered_execution = next(
        item for item in recovered.tool_executions if item.action_id == action_id
    )
    assert recovered_execution.status == ToolExecutionStatus.COMPLETED
    assert recovered_execution.evidence_ref == record.evidence_id
    assert recovered.adaptive_cost_units_used == 1
    assert recovered.adaptive_cost_units_remaining == 3
    assert any(event.type == "recovery.completed" for event in restarted.events(state.run_id))
    hypothesis = [
        event for event in restarted.events(state.run_id) if event.type == "hypothesis.updated"
    ]
    assert hypothesis[-1].payload["evidence_id"] == record.evidence_id
    assert hypothesis[-1].payload["active_hypotheses"] == recovered.active_hypotheses


def test_persisted_snapshot_contains_decisions_reviews_invocations_and_budgets(tmp_path) -> None:
    controller = make_controller(tmp_path, policy_client(), make_registry("clean"))
    state = controller.create("TARGET-X17")
    path = controller.artifacts.run_dir(state.opaque_target_id, state.run_id) / "state.json"
    payload = path.read_text(encoding="utf-8")
    assert '"max_model_calls"' in payload
    assert '"max_tool_calls"' in payload
    assert '"max_adaptive_cost_units"' in payload
    assert '"adaptive_cost_units_used"' in payload
    assert '"adaptive_cost_units_remaining"' in payload
    assert '"accepted_decisions"' in payload
    assert '"critic_decisions"' in payload
    assert '"tool_executions"' in payload
    assert '"failures"' in payload


@pytest.mark.asyncio
async def test_terminal_failed_execution_is_not_reexecuted_after_restart(tmp_path) -> None:
    calls: Counter[str] = Counter()
    registry = make_registry(
        "eclipsing_binary", calls=calls, raise_tool="harmonic_test"
    )
    first = make_controller(tmp_path, policy_client(), registry)
    state = first.create("TARGET-X17")
    seed_baseline(first, state.run_id, "eclipsing_binary")
    failed = await first.advance(state.run_id)
    call_count = calls["harmonic_test"]

    restarted = make_controller(tmp_path, policy_client(), registry)
    recovered = await restarted.advance(state.run_id)

    assert recovered == failed
    assert calls["harmonic_test"] == call_count
    assert recovered.tool_executions[-1].status == ToolExecutionStatus.FAILED
    assert (
        recovered.tool_executions[-1].failure_kind
        == HarnessFailureKind.TOOL_INFRASTRUCTURE_FAILURE
    )


@pytest.mark.asyncio
async def test_interrupted_prepared_idempotent_action_is_reexecuted_once(tmp_path) -> None:
    calls: Counter[str] = Counter()
    registry = make_registry("eclipsing_binary", calls=calls)
    first = make_controller(tmp_path, policy_client(), registry)
    state = first.create("TARGET-X17")
    seed_baseline(first, state.run_id, "eclipsing_binary")
    state = first._replace(  # noqa: SLF001 - intentional interrupted checkpoint
        first.get(state.run_id), status=InvestigationStatus.SELECTING_ADAPTIVE_EXPERIMENT
    )
    state = first._replace(state, status=InvestigationStatus.WAITING_FOR_CRITIC)  # noqa: SLF001
    state = first._replace(state, status=InvestigationStatus.RUNNING_TOOL)  # noqa: SLF001
    parameters = {"trial_factor": 1}
    execution = ToolExecutionRecord(
        action_id="action_interrupted_before_execution",
        step_id="step_0000",
        tool_name="harmonic_test",
        parameters=parameters,
        action_signature=first._action_signature("harmonic_test", parameters),  # noqa: SLF001
        status=ToolExecutionStatus.PREPARED,
        adaptive=True,
        adaptive_cost_units=1,
    )
    first._replace(  # noqa: SLF001
        state,
        tool_call_count=state.tool_call_count + 1,
        adaptive_experiments_used=state.adaptive_experiments_used + 1,
        adaptive_cost_units_used=state.adaptive_cost_units_used + 1,
        adaptive_cost_units_remaining=state.adaptive_cost_units_remaining - 1,
        tool_executions=[*state.tool_executions, execution],
    )

    restarted = make_controller(tmp_path, policy_client(), registry)
    recovered = await restarted.advance(state.run_id)

    assert calls["harmonic_test"] == 1
    assert recovered.status == InvestigationStatus.READY_TO_LOCK
    restored_execution = next(
        item for item in recovered.tool_executions if item.action_id == execution.action_id
    )
    assert restored_execution.status == ToolExecutionStatus.COMPLETED
    assert recovered.adaptive_cost_units_used == 1
    assert recovered.adaptive_cost_units_remaining == 3
    assert len(restarted.evidence(state.run_id)) == 5


@pytest.mark.asyncio
@pytest.mark.parametrize("locked", [False, True])
async def test_tool_result_admission_cannot_mutate_lock_eligible_or_locked_run(
    tmp_path, locked
) -> None:
    controller = make_controller(tmp_path, policy_client(), make_registry("clean"))
    state = controller.create("TARGET-X17")
    seed_baseline(controller, state.run_id, "clean")
    state = await controller.advance(state.run_id)
    assert state.status == InvestigationStatus.READY_TO_LOCK
    if locked:
        controller.lock(state.run_id)
        state = controller.get(state.run_id)

    run_dir = controller.artifacts.run_dir(state.opaque_target_id, state.run_id)
    ledger_path = controller.artifacts.evidence_path(state)
    state_before = state
    evidence_before = controller.evidence(state.run_id)
    ledger_before = ledger_path.read_bytes()
    trace_before = (run_dir / "trace.jsonl").read_bytes()
    state_bytes_before = (run_dir / "state.json").read_bytes()
    result_before = (run_dir / "result.json").read_bytes() if locked else None
    hash_before = (run_dir / "result.json.sha256").read_bytes() if locked else None

    with pytest.raises(ActionValidationError, match="lock eligibility"):
        controller.record_tool_result(
            state.run_id,
            fixture_result(
                tool_name="harmonic_test",
                run_id=state.run_id,
                action_id=f"fixture_post_lock_{locked}",
                target_id=state.opaque_target_id,
                scenario="clean",
                parameters={"trial_factor": 1},
            ),
        )

    assert controller.get(state.run_id) == state_before
    assert controller.evidence(state.run_id) == evidence_before
    assert ledger_path.read_bytes() == ledger_before
    assert (run_dir / "trace.jsonl").read_bytes() == trace_before
    assert (run_dir / "state.json").read_bytes() == state_bytes_before
    assert ((run_dir / "result.json").read_bytes() if locked else None) == result_before
    assert (
        (run_dir / "result.json.sha256").read_bytes() if locked else None
    ) == hash_before
