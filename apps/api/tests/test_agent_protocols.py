from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from exoswarm.agents.context import assemble_context
from exoswarm.agents.critic import CRITIC_PROMPT_VERSION, build_critic_messages
from exoswarm.agents.inference_provider import FeatherlessInferenceClient
from exoswarm.agents.skeptic import SKEPTIC_PROMPT_VERSION, build_skeptic_messages
from exoswarm.domain.enums import CriticVerdict, InformationValue, Priority
from exoswarm.domain.models import CriticDecision, InvestigationState, SkepticDecision


def _state() -> InvestigationState:
    return InvestigationState(
        run_id="run_protocol",
        opaque_target_id="TARGET-X17",
        step_count=3,
        active_hypotheses=["planetary_transit", "eclipsing_binary"],
        strongest_unresolved_alternative="eclipsing_binary",
        available_tests=["harmonic_test"],
    )


def _proposal(state: InvestigationState) -> SkepticDecision:
    return SkepticDecision(
        decision_id="decision_protocol",
        run_id=state.run_id,
        step_id="step_0003",
        context_version=state.context_version,
        hypothesis_under_test="eclipsing_binary",
        requested_experiment="harmonic_test",
        parameters={"trial_factor": 1},
        reason_code="HARMONIC_DISCRIMINATION",
        expected_discriminating_result="Test the allowed doubled-period alternative.",
        predicted_outcomes={"HARMONIC_FOUND": "eclipsing-binary alternative strengthened"},
        expected_information_value=InformationValue.HIGH,
        priority=Priority.HIGH,
        budget_units_remaining=state.adaptive_cost_units_remaining,
        cost_of_selected_experiment=1,
        why_cost_is_justified="One unit directly tests the strongest unresolved alternative.",
        concise_reason="The harmonic test is the most discriminating affordable action.",
    )


def test_skeptic_and_critic_receive_distinct_operational_instructions() -> None:
    state = _state()
    skeptic_context = assemble_context(
        state,
        available_experiments=("harmonic_test",),
        adaptive_experiment_costs={"harmonic_test": 1},
    )
    critic_context = assemble_context(
        state,
        role="critic",
        available_experiments=("harmonic_test",),
        adaptive_experiment_costs={"harmonic_test": 1},
        proposed_decision=_proposal(state),
    )

    skeptic = build_skeptic_messages(
        context=skeptic_context, output_schema=SkepticDecision
    )
    critic = build_critic_messages(context=critic_context, output_schema=CriticDecision)

    assert skeptic[0]["content"] != critic[0]["content"]
    assert "strongest unresolved" in skeptic[0]["content"]
    assert "available, affordable, unexecuted" in skeptic[0]["content"]
    for required_check in (
        "relevance",
        "duplication",
        "preconditions",
        "cost justification",
        "discriminate",
    ):
        assert required_check in critic[0]["content"]
    skeptic_payload = json.loads(skeptic[1]["content"])
    critic_payload = json.loads(critic[1]["content"])
    assert skeptic_payload["prompt_version"] == SKEPTIC_PROMPT_VERSION
    assert critic_payload["prompt_version"] == CRITIC_PROMPT_VERSION
    assert skeptic_payload["exact_output_bindings"] == {
        "run_id": skeptic_context.run_id,
        "step_id": skeptic_context.step_id,
        "context_version": skeptic_context.context_version,
    }
    assert critic_payload["exact_output_bindings"] == {
        "run_id": critic_context.run_id,
        "step_id": critic_context.step_id,
        "context_version": critic_context.context_version,
        "skeptic_decision_id": critic_context.proposed_decision.decision_id,
    }
    assert "byte-for-byte" in skeptic[0]["content"]
    assert "byte-for-byte" in critic[0]["content"]
    assert "why_cost_is_justified and concise_reason" in skeptic[0]["content"]
    assert "concise_reason at or below 300 characters" in critic[0]["content"]


def test_repair_message_uses_only_bounded_safe_feedback() -> None:
    state = _state()
    context = assemble_context(
        state,
        available_experiments=("harmonic_test",),
        adaptive_experiment_costs={"harmonic_test": 1},
    )
    unsafe_error = r"provider leaked C:\private\secret.txt token=super-secret"

    messages = FeatherlessInferenceClient._messages(
        role="skeptic",
        context=context,
        output_schema=SkepticDecision,
        attempt_kind="repair",
        validation_error_code=unsafe_error,
    )
    serialized = json.dumps(messages)
    payload = json.loads(messages[1]["content"])

    assert unsafe_error not in serialized
    assert "super-secret" not in serialized
    assert payload["repair_feedback"] == {
        "category": "structure",
        "code": "INVALID_MODEL_OUTPUT",
    }
    assert "single repair attempt" in messages[0]["content"]


@pytest.mark.parametrize("verdict", [CriticVerdict.APPROVE, CriticVerdict.VETO])
def test_non_revision_critic_decision_rejects_revised_parameters(verdict) -> None:
    state = _state()

    with pytest.raises(ValidationError, match="only REVISE may provide revision fields"):
        CriticDecision(
            decision_id="critic_invalid_revision_fields",
            run_id=state.run_id,
            step_id="step_0003",
            context_version=state.context_version,
            skeptic_decision_id="decision_protocol",
            verdict=verdict,
            reason_code="NO_REVISION_ALLOWED",
            concise_reason="Non-revision verdicts cannot carry ignored parameters.",
            revised_parameters={"trial_factor": 2},
        )


def test_revision_critic_decision_requires_explicit_parameters() -> None:
    state = _state()

    with pytest.raises(ValidationError, match="REVISE requires revised_parameters"):
        CriticDecision(
            decision_id="critic_missing_revision_parameters",
            run_id=state.run_id,
            step_id="step_0003",
            context_version=state.context_version,
            skeptic_decision_id="decision_protocol",
            verdict=CriticVerdict.REVISE,
            reason_code="REVISION_INCOMPLETE",
            concise_reason="A revision must contain its complete bounded request.",
            revised_experiment="harmonic_test",
        )
