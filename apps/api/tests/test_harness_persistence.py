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

from exoswarm.domain.enums import InvestigationStatus, ToolExecutionStatus
from exoswarm.domain.models import EvidenceRecord, ToolExecutionRecord


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
    )
    state = first._replace(  # noqa: SLF001
        state,
        tool_call_count=state.tool_call_count + 1,
        adaptive_experiments_used=state.adaptive_experiments_used + 1,
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
    assert any(event.type == "recovery.completed" for event in restarted.events(state.run_id))


def test_persisted_snapshot_contains_decisions_reviews_invocations_and_budgets(tmp_path) -> None:
    controller = make_controller(tmp_path, policy_client(), make_registry("clean"))
    state = controller.create("TARGET-X17")
    path = controller.artifacts.run_dir(state.opaque_target_id, state.run_id) / "state.json"
    payload = path.read_text(encoding="utf-8")
    assert '"max_model_calls"' in payload
    assert '"max_tool_calls"' in payload
    assert '"accepted_decisions"' in payload
    assert '"critic_decisions"' in payload
    assert '"tool_executions"' in payload
    assert '"failures"' in payload
