from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from harness_support import (
    critic_policy,
    make_controller,
    make_registry,
    policy_client,
    seed_baseline,
    skeptic_policy,
)

from exoswarm.agents.context import assemble_context
from exoswarm.agents.inference_provider import (
    FEATHERLESS_BASE_URL,
    FeatherlessInferenceClient,
)
from exoswarm.agents.inference_telemetry import derive_inference_summary
from exoswarm.agents.model_client import ScriptedInferenceClient
from exoswarm.config import Settings
from exoswarm.domain.enums import HarnessFailureKind, InvestigationStatus
from exoswarm.domain.models import InferenceTraceRecord, InvestigationState, SkepticDecision


class FakeCompletions:
    def __init__(self, responses: list[Any]) -> None:
        self.responses = list(responses)
        self.requests: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> Any:
        self.requests.append(kwargs)
        if not self.responses:
            raise AssertionError("fake transport has no response")
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        if callable(response):
            response = response(kwargs)
        return response


def fake_sdk(responses: list[Any]) -> tuple[Any, FakeCompletions]:
    completions = FakeCompletions(responses)
    return SimpleNamespace(chat=SimpleNamespace(completions=completions)), completions


def test_partial_provider_usage_is_not_reported_as_a_complete_total() -> None:
    measured = InferenceTraceRecord(
        call_id="call_1",
        run_id="run_1",
        step_id="step_0001",
        role="skeptic",
        provider="featherless",
        model_identity="deepseek-ai/DeepSeek-V4-Flash-0731",
        attempt_kind="primary",
        context_version="1",
        input_tokens=100,
        output_tokens=25,
        latency_ms=10,
        status="SUCCESS",
        schema_valid=True,
    )
    unmeasured = measured.model_copy(
        update={
            "call_id": "call_2",
            "role": "critic",
            "input_tokens": None,
            "output_tokens": None,
            "latency_ms": None,
        }
    )

    summary = derive_inference_summary([measured, unmeasured])

    assert summary.input_tokens == "not_measured"
    assert summary.output_tokens == "not_measured"
    assert summary.median_input_tokens == "not_measured"
    assert summary.max_input_tokens == "not_measured"
    assert summary.median_latency_ms == "not_measured"


def completion(content: str, *, prompt_tokens: int = 100, completion_tokens: int = 25) -> Any:
    return SimpleNamespace(
        model="deepseek-ai/DeepSeek-V4-Flash-0731",
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=SimpleNamespace(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        ),
    )


def valid_decision_response(request: dict[str, Any]) -> Any:
    payload = json.loads(request["messages"][1]["content"])
    context = payload["context"]
    if context["role"] == "skeptic":
        decision = {
            "role": "skeptic",
            "decision_id": f"decision_{context['step_id']}",
            "run_id": context["run_id"],
            "step_id": context["step_id"],
            "hypothesis_under_test": "eclipsing_binary",
            "requested_experiment": "harmonic_test",
            "parameters": {"trial_factor": 1},
            "reason_code": "FEATHERLESS_BOUNDED_SELECTION",
            "expected_discriminating_result": "Compare deterministic harmonic evidence.",
            "predicted_outcomes": {"RESOLVED": "Update from deterministic evidence."},
            "expected_information_value": "high",
            "priority": "high",
            "concise_reason": "The bounded harmonic check discriminates the alternatives.",
        }
    else:
        proposal = context["proposed_decision"]
        decision = {
            "role": "critic",
            "decision_id": f"critic_{context['step_id']}",
            "run_id": context["run_id"],
            "step_id": context["step_id"],
            "skeptic_decision_id": proposal["decision_id"],
            "verdict": "APPROVE",
            "reason_code": "FEATHERLESS_APPROVE",
            "concise_reason": "The proposed bounded experiment is valid and informative.",
        }
    return completion(json.dumps(decision))


@pytest.mark.asyncio
async def test_featherless_adapter_uses_safe_openai_compatible_request_and_metadata() -> None:
    state = InvestigationState(
        run_id="run_provider",
        opaque_target_id="TARGET-X17",
        step_count=1,
    )
    context = assemble_context(state, available_experiments=("harmonic_test",))
    sdk, transport = fake_sdk([valid_decision_response])
    client = FeatherlessInferenceClient(api_key="secret-never-persist", sdk=sdk)

    outcome = await client.decide_attempt(
        role="skeptic",
        context=context,
        output_schema=SkepticDecision,
        attempt_kind="primary",
    )

    assert isinstance(outcome.decision, SkepticDecision)
    assert outcome.error is None
    assert outcome.call.provider == "featherless"
    assert outcome.call.model_identity == "deepseek-ai/DeepSeek-V4-Flash-0731"
    assert outcome.call.input_tokens == 100
    assert outcome.call.output_tokens == 25
    assert outcome.call.schema_valid is True
    request = transport.requests[0]
    assert request["model"] == "deepseek-ai/DeepSeek-V4-Flash-0731"
    assert "response_format" not in request
    serialized_request = json.dumps(request)
    assert "secret-never-persist" not in serialized_request
    assert "raw_flux" not in serialized_request
    assert "local_path" not in serialized_request


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "status", "error_type"),
    [
        (TimeoutError("slow"), "TIMEOUT", "ModelProviderTimeoutError"),
        (RuntimeError("upstream unavailable"), "PROVIDER_ERROR", "ModelProviderError"),
    ],
)
async def test_featherless_adapter_classifies_provider_failures_without_raw_errors(
    error: Exception, status: str, error_type: str
) -> None:
    state = InvestigationState(run_id="run_error", opaque_target_id="TARGET-X17", step_count=1)
    context = assemble_context(state, available_experiments=("harmonic_test",))
    sdk, _ = fake_sdk([error])
    client = FeatherlessInferenceClient(api_key="secret-never-persist", sdk=sdk)

    outcome = await client.decide_attempt(
        role="skeptic",
        context=context,
        output_schema=SkepticDecision,
        attempt_kind="primary",
    )

    assert outcome.call.status == status
    assert type(outcome.error).__name__ == error_type
    assert "upstream unavailable" not in outcome.call.model_dump_json()
    assert "secret-never-persist" not in outcome.call.model_dump_json()


@pytest.mark.asyncio
async def test_invalid_primary_gets_one_repair_and_summary_is_trace_derived(tmp_path: Path) -> None:
    sdk, transport = fake_sdk(
        [
            completion("not-json", prompt_tokens=80, completion_tokens=2),
            valid_decision_response,
            valid_decision_response,
        ]
    )
    client = FeatherlessInferenceClient(api_key="secret-never-persist", sdk=sdk)
    controller = make_controller(tmp_path, client, make_registry("eclipsing_binary"))
    state = controller.create("TARGET-X17")
    seed_baseline(controller, state.run_id, "eclipsing_binary")

    state = await controller.advance(state.run_id)

    assert state.status == InvestigationStatus.READY_TO_LOCK
    assert len(transport.requests) == 3
    assert "single repair attempt" in transport.requests[1]["messages"][0]["content"]
    assert state.inference_summary.agent_calls == 3
    assert state.inference_summary.input_tokens == 280
    assert state.inference_summary.output_tokens == 52
    assert state.inference_summary.repairs.numerator == 1
    assert state.inference_summary.repairs.denominator == 1
    assert state.inference_summary.first_attempt_schema_valid.numerator == 1
    assert state.inference_summary.first_attempt_schema_valid.denominator == 2
    summary_path = controller.artifacts.run_dir(state.opaque_target_id, state.run_id) / (
        "inference_summary.json"
    )
    assert json.loads(summary_path.read_text(encoding="utf-8")) == (
        state.inference_summary.model_dump(mode="json")
    )
    restarted = make_controller(tmp_path, policy_client(), make_registry("eclipsing_binary"))
    assert restarted.get(state.run_id).inference_summary == state.inference_summary
    persisted = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (
            controller.artifacts.run_dir(state.opaque_target_id, state.run_id) / "state.json",
            controller.artifacts.run_dir(state.opaque_target_id, state.run_id) / "trace.jsonl",
            summary_path,
        )
    )
    assert "secret-never-persist" not in persisted
    assert "not-json" not in persisted
    assert "AGENT_FALLBACK" not in persisted


@pytest.mark.asyncio
async def test_explicit_scripted_fallback_is_labeled_and_counted(tmp_path: Path) -> None:
    sdk, _ = fake_sdk([TimeoutError("skeptic timeout"), TimeoutError("critic timeout")])
    live = FeatherlessInferenceClient(api_key="secret-never-persist", sdk=sdk)
    fallback = ScriptedInferenceClient(
        {"skeptic": [skeptic_policy], "critic": [critic_policy]},
        model_identity="mock:offline-fallback-v1",
    )
    controller = make_controller(
        tmp_path,
        live,
        make_registry("eclipsing_binary"),
        max_model_retries=0,
        agent_fallback_enabled=True,
    )
    controller.fallback_inference = fallback
    state = controller.create("TARGET-X17")
    seed_baseline(controller, state.run_id, "eclipsing_binary")

    state = await controller.advance(state.run_id)

    assert state.status == InvestigationStatus.READY_TO_LOCK
    fallback_events = [
        event for event in controller.events(state.run_id) if event.type == "inference.fallback"
    ]
    assert len(fallback_events) == 2
    assert all(event.payload["label"] == "AGENT_FALLBACK" for event in fallback_events)
    assert state.inference_summary.fallbacks.numerator == 2
    assert state.inference_summary.fallbacks.denominator == 2
    assert state.inference_summary.provider_errors_timeouts == 2
    agent_decision = next(
        event for event in controller.events(state.run_id) if event.type == "agent.decision"
    )
    critic_review = next(
        event for event in controller.events(state.run_id) if event.type == "critic.review"
    )
    assert agent_decision.payload["model_identity"] == "mock:offline-fallback-v1"
    assert critic_review.payload["model_identity"] == "mock:offline-fallback-v1"
    assert agent_decision.payload["fallback_used"] is True
    assert critic_review.payload["fallback_used"] is True


@pytest.mark.asyncio
async def test_semantically_invalid_action_is_not_counted_schema_valid(tmp_path: Path) -> None:
    def unknown_action(context, schema):
        return skeptic_policy(context, schema).model_copy(
            update={"requested_experiment": "unknown_tool"}
        )

    client = ScriptedInferenceClient(
        {
            "skeptic": [unknown_action, skeptic_policy],
            "critic": [critic_policy],
        }
    )
    controller = make_controller(
        tmp_path,
        client,
        make_registry("eclipsing_binary"),
    )
    state = controller.create("TARGET-X17")
    seed_baseline(controller, state.run_id, "eclipsing_binary")

    state = await controller.advance(state.run_id)

    attempts = [
        event.payload
        for event in controller.events(state.run_id)
        if event.type == "inference.attempt"
    ]
    assert attempts[0]["status"] == "INVALID"
    assert attempts[0]["schema_valid"] is False
    assert state.inference_summary.first_attempt_schema_valid.numerator == 1
    assert state.inference_summary.first_attempt_schema_valid.denominator == 2


def test_blank_featherless_key_is_treated_as_unconfigured() -> None:
    settings = Settings(featherless_api_key="", _env_file=None)

    assert settings.featherless_api_key is None


@pytest.mark.asyncio
async def test_unconfigured_fallback_preserves_existing_typed_failure(tmp_path: Path) -> None:
    sdk, _ = fake_sdk([TimeoutError("provider timeout")])
    live = FeatherlessInferenceClient(api_key="secret-never-persist", sdk=sdk)
    controller = make_controller(
        tmp_path,
        live,
        make_registry("eclipsing_binary"),
        max_model_retries=0,
        agent_fallback_enabled=False,
    )
    state = controller.create("TARGET-X17")
    seed_baseline(controller, state.run_id, "eclipsing_binary")

    state = await controller.advance(state.run_id)

    assert state.status == InvestigationStatus.FAILED
    assert state.failures[-1].kind == HarnessFailureKind.MODEL_TIMEOUT
    assert not [
        event for event in controller.events(state.run_id) if event.type == "inference.fallback"
    ]


def test_settings_read_official_featherless_environment_variables(monkeypatch) -> None:
    monkeypatch.setenv("FEATHERLESS_API_KEY", "configured-secret")
    monkeypatch.setenv("FEATHERLESS_BASE_URL", FEATHERLESS_BASE_URL)

    settings = Settings(_env_file=None)

    assert settings.featherless_api_key is not None
    assert settings.featherless_api_key.get_secret_value() == "configured-secret"
    assert settings.featherless_base_url == FEATHERLESS_BASE_URL
    assert settings.model == "deepseek-ai/DeepSeek-V4-Flash-0731"


def test_existing_scripted_client_consumers_remain_compatible() -> None:
    client = policy_client()
    assert client.model_identity == "mock:evidence-aware-fixture-v1"
