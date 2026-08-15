from __future__ import annotations

import asyncio
import time
from collections import Counter
from dataclasses import replace

import pytest
from harness_support import (
    fixture_result,
    make_controller,
    make_registry,
    policy_client,
    seed_baseline,
)

from exoswarm.agents.context import AgentContextPacket
from exoswarm.agents.model_client import ScriptedInferenceClient
from exoswarm.domain.enums import (
    CriticVerdict,
    HarnessFailureKind,
    InformationValue,
    InvestigationStatus,
    Priority,
    ToolExecutionStatus,
)
from exoswarm.domain.models import CriticDecision, SkepticDecision
from exoswarm.investigation.runtime_inputs import (
    CachedCandidateSource,
    MappingCandidateSourceResolver,
)
from exoswarm.investigation.tool_registry import ScientificToolRegistry
from exoswarm.science.contracts import ExecutionIsolation, ScientificToolSpec
from exoswarm.science.pipeline import (
    CandidateSearchParameters,
    CandidateSearchRuntimeInputs,
)


def _subprocess_late_writer(run_id, action_id, target_id, parameters):
    time.sleep(0.1)
    cached_path = parameters["cached_path"]
    completion_marker = cached_path.with_suffix(".completed")
    completion_marker.parent.mkdir(parents=True, exist_ok=True)
    completion_marker.write_text("late computation completed\n", encoding="utf-8")
    artifact_dir = parameters["artifact_dir"]
    artifact_dir.mkdir(parents=True, exist_ok=True)
    (artifact_dir / f"{action_id}.candidate-search.json").write_text(
        "{}\n", encoding="utf-8"
    )
    return fixture_result(
        tool_name="search_bls",
        run_id=run_id,
        action_id=action_id,
        target_id=target_id,
        scenario="clean",
        parameters={
            "preprocessing": parameters["preprocessing"],
            "search": parameters["search"],
        },
    )


def _skeptic_request(
    context,
    _schema,
    *,
    tool_name: str = "harmonic_test",
    declared_cost: int | None = None,
    declared_remaining: int | None = None,
    context_version: str | None = None,
) -> SkepticDecision:
    packet = AgentContextPacket.model_validate(context)
    cost = packet.adaptive_experiment_costs[tool_name]
    return SkepticDecision(
        decision_id=f"decision_{packet.step_id}",
        run_id=packet.run_id,
        step_id=packet.step_id,
        context_version=context_version or packet.context_version,
        hypothesis_under_test="eclipsing_binary",
        requested_experiment=tool_name,
        parameters={"trial_factor": 1} if tool_name == "harmonic_test" else {},
        reason_code="HARDENING_FIXTURE",
        expected_discriminating_result="Exercise the authoritative loop boundary.",
        expected_information_value=InformationValue.HIGH,
        priority=Priority.HIGH,
        budget_units_remaining=(
            packet.remaining_budgets.adaptive_cost_units
            if declared_remaining is None
            else declared_remaining
        ),
        cost_of_selected_experiment=cost if declared_cost is None else declared_cost,
        why_cost_is_justified="The action directly tests the strongest unresolved alternative.",
        concise_reason="Use the bounded deterministic hardening fixture.",
    )


def _approve(context, _schema) -> CriticDecision:
    packet = AgentContextPacket.model_validate(context)
    assert packet.proposed_decision is not None
    return CriticDecision(
        decision_id=f"critic_{packet.step_id}",
        run_id=packet.run_id,
        step_id=packet.step_id,
        context_version=packet.context_version,
        skeptic_decision_id=packet.proposed_decision.decision_id,
        verdict=CriticVerdict.APPROVE,
        reason_code="HARDENING_APPROVE",
        concise_reason="The bounded action is valid and discriminating.",
    )


@pytest.mark.asyncio
async def test_critic_revision_charges_authoritative_revised_price(tmp_path) -> None:
    controller = make_controller(tmp_path, policy_client(), make_registry("contamination"))
    state = controller.create("TARGET-X17")
    seed_baseline(controller, state.run_id, "contamination")

    state = await controller.advance(state.run_id)

    execution = next(item for item in state.tool_executions if item.adaptive)
    assert state.accepted_decisions[-1].cost_of_selected_experiment == 1
    assert state.critic_decisions[-1].verdict == CriticVerdict.REVISE
    assert execution.tool_name == "centroid_localization"
    assert execution.adaptive_cost_units == 2
    assert state.adaptive_cost_units_used == 2
    assert state.adaptive_cost_units_remaining == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("mismatch", ["cost", "remaining", "context"])
async def test_stale_or_false_skeptic_declarations_never_prepare_a_tool(
    tmp_path, mismatch
) -> None:
    def invalid(context, schema):
        packet = AgentContextPacket.model_validate(context)
        kwargs = {}
        if mismatch == "cost":
            kwargs["declared_cost"] = 2
        elif mismatch == "remaining":
            kwargs["declared_remaining"] = packet.remaining_budgets.adaptive_cost_units - 1
        else:
            kwargs["context_version"] = "obsolete-context"
        return _skeptic_request(context, schema, **kwargs)

    client = ScriptedInferenceClient({"skeptic": [invalid, invalid], "critic": [_approve]})
    controller = make_controller(tmp_path, client, make_registry("eclipsing_binary"))
    state = controller.create("TARGET-X17")
    seed_baseline(controller, state.run_id, "eclipsing_binary")

    state = await controller.advance(state.run_id)

    assert state.status == InvestigationStatus.FAILED
    assert state.failures[-1].kind == HarnessFailureKind.INVALID_MODEL_OUTPUT
    assert not [item for item in state.tool_executions if item.adaptive]


@pytest.mark.asyncio
async def test_no_affordable_valid_experiment_finishes_without_model_call(tmp_path) -> None:
    registry = make_registry("clean")
    expensive = ScientificToolRegistry(
        replace(spec, cost_units=2) if spec.adaptive else spec for spec in registry.specs
    )
    client = ScriptedInferenceClient({})
    controller = make_controller(
        tmp_path,
        client,
        expensive,
        max_adaptive_cost_units=1,
    )
    state = controller.create("TARGET-X17")
    seed_baseline(controller, state.run_id, "clean")

    state = await controller.advance(state.run_id)

    assert state.status == InvestigationStatus.READY_TO_LOCK
    assert state.terminal_reason == "NO_AFFORDABLE_VALID_ADAPTIVE_EXPERIMENT"
    assert state.adaptive_cost_units_remaining == 1
    assert client.calls == []


@pytest.mark.asyncio
async def test_concurrent_advances_are_serialized_before_inference(tmp_path) -> None:
    client = policy_client()
    controller = make_controller(tmp_path, client, make_registry("eclipsing_binary"))
    state = controller.create("TARGET-X17")
    seed_baseline(controller, state.run_id, "eclipsing_binary")

    first, second = await asyncio.gather(
        controller.advance(state.run_id),
        controller.advance(state.run_id),
    )

    durable = controller.get(state.run_id)
    assert first.status == second.status == InvestigationStatus.READY_TO_LOCK
    assert len([call for call in client.calls if call.role == "skeptic"]) == 1
    assert len([call for call in client.calls if call.role == "critic"]) == 1
    assert len([item for item in durable.tool_executions if item.adaptive]) == 1


class _HangingInferenceClient:
    provider = "fixture"
    model_identity = "fixture:hanging"

    async def decide(self, *, role, context, output_schema):
        del role, context, output_schema
        await asyncio.sleep(1)
        raise AssertionError("controller timeout did not preempt inference")


@pytest.mark.asyncio
async def test_controller_enforces_model_timeout_and_retry_limit(tmp_path) -> None:
    controller = make_controller(
        tmp_path,
        _HangingInferenceClient(),
        make_registry("eclipsing_binary"),
        inference_timeout_seconds=0.01,
        max_model_retries=0,
    )
    state = controller.create("TARGET-X17")
    seed_baseline(controller, state.run_id, "eclipsing_binary")

    state = await controller.advance(state.run_id)

    assert state.status == InvestigationStatus.FAILED
    assert state.failures[-1].kind == HarnessFailureKind.MODEL_TIMEOUT
    attempts = [
        event
        for event in controller.events(state.run_id)
        if event.type == "inference.attempt"
    ]
    assert len(attempts) == 1
    assert attempts[0].payload["status"] == "TIMEOUT"
    assert attempts[0].payload["output_schema"] == "SkepticDecision"


@pytest.mark.asyncio
async def test_tool_timeout_keeps_single_durable_charge_and_is_not_replayed(tmp_path) -> None:
    calls: Counter[str] = Counter()
    registry = make_registry("eclipsing_binary", calls=calls)
    harmonic = registry.resolve("harmonic_test")
    original = harmonic.handler

    def slow_handler(run_id, action_id, target_id, parameters):
        time.sleep(0.05)
        return original(run_id, action_id, target_id, parameters)

    timed = ScientificToolRegistry(
        replace(spec, handler=slow_handler, timeout_seconds=0.01)
        if spec.name == "harmonic_test"
        else spec
        for spec in registry.specs
    )
    controller = make_controller(tmp_path, policy_client(), timed)
    state = controller.create("TARGET-X17")
    seed_baseline(controller, state.run_id, "eclipsing_binary")

    failed = await controller.advance(state.run_id)

    assert failed.status == InvestigationStatus.FAILED
    assert failed.failures[-1].kind == HarnessFailureKind.TOOL_TIMEOUT
    assert failed.adaptive_cost_units_used == 1
    assert failed.adaptive_cost_units_remaining == 3
    assert failed.tool_executions[-1].status == ToolExecutionStatus.FAILED

    restarted = make_controller(tmp_path, policy_client(), timed)
    recovered = await restarted.advance(state.run_id)
    assert recovered == failed
    assert recovered.adaptive_cost_units_used == 1


@pytest.mark.asyncio
async def test_timed_out_candidate_tool_cannot_publish_late_artifacts(tmp_path) -> None:
    registry = ScientificToolRegistry(
        [
            ScientificToolSpec(
                name="search_bls",
                handler=_subprocess_late_writer,
                parameter_schema=CandidateSearchParameters,
                runtime_input_schema=CandidateSearchRuntimeInputs,
                mandatory_test="signal_quality",
                timeout_seconds=0.01,
                execution_isolation=ExecutionIsolation.SUBPROCESS,
            )
        ]
    )
    cached_path = tmp_path / "private" / "source.fits"
    resolver = MappingCandidateSourceResolver(
        {"TARGET-X17": CachedCandidateSource(cached_path=cached_path)}
    )
    controller = make_controller(
        tmp_path,
        ScriptedInferenceClient({}),
        registry,
        candidate_sources=resolver,
    )
    state = controller.create("TARGET-X17")

    failed = await controller.advance(state.run_id)
    await asyncio.sleep(0.15)

    run_dir = controller.artifacts.run_dir(state.opaque_target_id, state.run_id)
    assert failed.status == InvestigationStatus.FAILED
    assert failed.failures[-1].kind == HarnessFailureKind.TOOL_TIMEOUT
    assert controller.evidence(state.run_id) == ()
    assert list((run_dir / "artifacts").iterdir()) == []
    assert not cached_path.with_suffix(".completed").exists()
    assert not (run_dir / ".tool-staging").exists()
