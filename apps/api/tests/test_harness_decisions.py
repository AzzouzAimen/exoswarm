from __future__ import annotations

import pytest
from harness_support import (
    NoParameters,
    fixture_result,
    make_controller,
    make_registry,
    seed_baseline,
)

from exoswarm.agents.context import AgentContextPacket, assemble_context
from exoswarm.agents.model_client import ScriptedInferenceClient
from exoswarm.domain.enums import (
    CriticVerdict,
    HarnessFailureKind,
    InformationValue,
    InvestigationStatus,
    Priority,
)
from exoswarm.domain.errors import ModelProviderError, ModelProviderTimeoutError
from exoswarm.domain.models import CriticDecision, InvestigationState, SkepticDecision
from exoswarm.investigation.mandatory import MANDATORY_TESTS
from exoswarm.investigation.state import validate_status_transition
from exoswarm.investigation.tool_registry import scaffold_tool_registry


def request_policy(tool_name: str, parameters: dict | None = None):
    def decide(context, _schema):
        packet = AgentContextPacket.model_validate(context)
        return SkepticDecision(
            decision_id=f"decision_{packet.step_id}",
            run_id=packet.run_id,
            step_id=packet.step_id,
            context_version=packet.context_version,
            hypothesis_under_test="bounded_fixture_alternative",
            requested_experiment=tool_name,
            parameters=parameters or {},
            reason_code="FIXTURE_REQUEST",
            expected_discriminating_result="Exercise deterministic action validation.",
            expected_information_value=InformationValue.MEDIUM,
            priority=Priority.MEDIUM,
            budget_units_remaining=packet.remaining_budgets.adaptive_cost_units,
            cost_of_selected_experiment=packet.adaptive_experiment_costs.get(tool_name, 1),
            why_cost_is_justified="The fixture requests a bounded discriminating action.",
            concise_reason="A concise fixture reason.",
            supporting_evidence_refs=list(packet.evidence_refs[-1:]),
            contradicting_evidence_refs=[],
        )

    return decide


def test_production_availability_excludes_unimplemented_centroid(tmp_path) -> None:
    controller = make_controller(
        tmp_path,
        ScriptedInferenceClient({}),
        scaffold_tool_registry(),
    )
    state = controller.create("TARGET-X17")
    state = controller._replace(state, completed_tests=sorted(MANDATORY_TESTS))

    available = controller._available_adaptive_actions(state)

    assert "harmonic_test" in available
    assert "stop" in available
    assert "centroid_localization" not in available


def approve_policy(context, _schema):
    packet = AgentContextPacket.model_validate(context)
    assert packet.proposed_decision
    return CriticDecision(
        decision_id=f"critic_{packet.step_id}",
        run_id=packet.run_id,
        step_id=packet.step_id,
        context_version=packet.context_version,
        skeptic_decision_id=packet.proposed_decision.decision_id,
        verdict=CriticVerdict.APPROVE,
        reason_code="FIXTURE_APPROVE",
        concise_reason="The bounded request is informative in this fixture.",
        supporting_evidence_refs=list(packet.evidence_refs[-1:]),
        contradicting_evidence_refs=[],
    )


@pytest.mark.asyncio
async def test_scripted_client_accepts_schema_valid_mapping_and_records_call_metadata() -> None:
    state = InvestigationState(
        run_id="run_mapping",
        opaque_target_id="TARGET-X17",
        step_count=1,
    )
    context = assemble_context(
        state,
        available_experiments=("harmonic_test",),
        adaptive_experiment_costs={"harmonic_test": 1},
    )
    payload = {
        "decision_id": "decision_mapping",
        "run_id": state.run_id,
        "step_id": "step_0001",
        "context_version": state.context_version,
        "hypothesis_under_test": "eclipsing_binary",
        "requested_experiment": "harmonic_test",
        "reason_code": "MAPPING_FIXTURE",
        "expected_discriminating_result": "Test a schema-valid queued mapping.",
        "expected_information_value": "medium",
        "priority": "high",
        "budget_units_remaining": state.adaptive_cost_units_remaining,
        "cost_of_selected_experiment": 1,
        "why_cost_is_justified": "The bounded fixture action costs one unit.",
        "concise_reason": "The mapping follows the strict decision schema.",
    }
    client = ScriptedInferenceClient({"skeptic": [payload]}, model_identity="mock:mapping")
    decision = await client.decide(
        role="skeptic", context=context, output_schema=SkepticDecision
    )
    assert isinstance(decision, SkepticDecision)
    assert decision.requested_experiment == "harmonic_test"
    assert client.calls[0].model_identity == "mock:mapping"
    assert client.calls[0].context_version == state.context_version


async def run_invalid_case(tmp_path, skeptic_response, *, scopes=frozenset({"science:execute"})):
    client = ScriptedInferenceClient(
        {"skeptic": [skeptic_response], "critic": [approve_policy]}
    )
    controller = make_controller(
        tmp_path,
        client,
        make_registry("eclipsing_binary"),
        granted_scopes=scopes,
    )
    state = controller.create("TARGET-X17")
    seed_baseline(controller, state.run_id, "eclipsing_binary")
    return controller, await controller.advance(state.run_id)


@pytest.mark.asyncio
async def test_invalid_structured_output_is_explicit_and_never_executes(tmp_path) -> None:
    controller, state = await run_invalid_case(tmp_path, {"not": "a decision"})
    assert state.status == InvestigationStatus.FAILED
    assert state.failures[-1].kind == HarnessFailureKind.INVALID_MODEL_OUTPUT
    assert not [item for item in state.tool_executions if item.adaptive]
    assert len(controller.evidence(state.run_id)) == 4
    call = controller.inference.calls[0]
    assert call.status == "INVALID"
    assert call.model_identity == "mock:scripted-v1"
    assert call.run_id == state.run_id
    assert call.output_schema == "SkepticDecision"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("response", "expected"),
    [
        (request_policy("unknown_science_tool"), HarnessFailureKind.UNKNOWN_ACTION),
        (request_policy("odd_even"), HarnessFailureKind.REPEATED_ACTION),
        (
            request_policy("harmonic_test", {"trial_factor": 9}),
            HarnessFailureKind.MALFORMED_PARAMETERS,
        ),
    ],
)
async def test_unknown_repeated_and_malformed_actions_are_rejected(
    tmp_path, response, expected
) -> None:
    _, state = await run_invalid_case(tmp_path, response)
    assert state.status == InvestigationStatus.FAILED
    assert state.failures[-1].kind == expected
    assert not [item for item in state.tool_executions if item.adaptive]


@pytest.mark.asyncio
async def test_unavailable_nonadaptive_action_is_rejected(tmp_path) -> None:
    client = ScriptedInferenceClient(
        {"skeptic": [request_policy("load_cached_lightcurve")], "critic": [approve_policy]}
    )
    registry = make_registry("eclipsing_binary")
    # Registered and authorized, but deliberately unavailable in the adaptive phase.
    from exoswarm.science.contracts import ScientificToolSpec

    registry.register(
        ScientificToolSpec(
            name="load_cached_lightcurve",
            parameter_schema=NoParameters,
            handler=lambda *_args: fixture_result(
                tool_name="load_cached_lightcurve",
                run_id="unused",
                action_id="unused",
                target_id="unused",
                scenario="eclipsing_binary",
            ),
        )
    )
    controller = make_controller(tmp_path, client, registry)
    state = controller.create("TARGET-X17")
    seed_baseline(controller, state.run_id, "eclipsing_binary")
    state = await controller.advance(state.run_id)
    assert state.failures[-1].kind == HarnessFailureKind.UNAVAILABLE_ACTION


@pytest.mark.asyncio
async def test_missing_permission_scope_is_rejected_before_execution(tmp_path) -> None:
    _, state = await run_invalid_case(
        tmp_path, request_policy("harmonic_test", {"trial_factor": 1}), scopes=frozenset()
    )
    assert state.status == InvestigationStatus.FAILED
    assert state.failures[-1].kind == HarnessFailureKind.UNAUTHORIZED_ACTION


@pytest.mark.asyncio
async def test_identical_action_is_rejected_even_when_requested_again(tmp_path) -> None:
    client = ScriptedInferenceClient(
        {
            "skeptic": [request_policy("harmonic_test", {"trial_factor": 1})],
            "critic": [approve_policy],
        }
    )
    controller = make_controller(tmp_path, client, make_registry("eclipsing_binary"))
    state = controller.create("TARGET-X17")
    seed_baseline(controller, state.run_id, "eclipsing_binary")
    controller.record_tool_result(
        state.run_id,
        fixture_result(
            tool_name="harmonic_test",
            run_id=state.run_id,
            action_id="fixture_prior_harmonic",
            target_id=state.opaque_target_id,
            scenario="eclipsing_binary",
            parameters={"trial_factor": 1},
        ),
    )
    state = await controller.advance(state.run_id)
    assert state.failures[-1].kind == HarnessFailureKind.REPEATED_ACTION


@pytest.mark.asyncio
async def test_model_and_step_budgets_are_external_to_model(tmp_path) -> None:
    client = ScriptedInferenceClient({"skeptic": [request_policy("harmonic_test")]})
    controller = make_controller(
        tmp_path / "model", client, make_registry("clean"), max_model_calls=0
    )
    state = controller.create("TARGET-X17")
    seed_baseline(controller, state.run_id, "clean")
    state = await controller.advance(state.run_id)
    assert state.status == InvestigationStatus.BUDGET_EXHAUSTED
    assert state.failures[-1].kind == HarnessFailureKind.BUDGET_EXHAUSTED
    assert client.calls == []

    step_client = ScriptedInferenceClient({})
    step_controller = make_controller(
        tmp_path / "step", step_client, make_registry("clean"), max_steps=1
    )
    step = step_controller.create("TARGET-X17")
    step = await step_controller.advance(step.run_id)
    assert step.step_count == 1
    step = await step_controller.advance(step.run_id)
    assert step.status == InvestigationStatus.BUDGET_EXHAUSTED


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error",
    [ModelProviderTimeoutError("timeout"), ModelProviderError("provider down")],
)
async def test_transient_model_failures_stop_after_bounded_retry(tmp_path, error) -> None:
    client = ScriptedInferenceClient({"skeptic": [error, error]})
    controller = make_controller(
        tmp_path, client, make_registry("clean"), max_model_retries=1
    )
    state = controller.create("TARGET-X17")
    seed_baseline(controller, state.run_id, "clean")
    state = await controller.advance(state.run_id)
    assert state.status == InvestigationStatus.FAILED
    assert state.model_call_count == 2
    assert state.model_retry_count == 1
    assert state.failures[-1].kind in {
        HarnessFailureKind.MODEL_TIMEOUT,
        HarnessFailureKind.MODEL_PROVIDER_FAILURE,
    }


def test_invalid_status_transition_is_rejected_mechanically() -> None:
    with pytest.raises(ValueError, match="invalid investigation status transition"):
        validate_status_transition(
            InvestigationStatus.INITIALIZED, InvestigationStatus.RESULT_LOCKED
        )
