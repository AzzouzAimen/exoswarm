from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest
from harness_support import (
    critic_policy,
    fixture_result,
    make_controller,
    make_registry,
    policy_client,
    seed_baseline,
    skeptic_policy,
)

from exoswarm.agents.model_client import ScriptedInferenceClient
from exoswarm.domain.enums import (
    CriticVerdict,
    Disposition,
    HarnessFailureKind,
    InvestigationStatus,
    ToolExecutionStatus,
    ToolStatus,
)
from exoswarm.domain.errors import ModelProviderTimeoutError
from exoswarm.investigation.runtime_inputs import (
    CachedCandidateSource,
    MappingCandidateSourceResolver,
)
from exoswarm.investigation.tool_registry import (
    ScientificToolRegistry,
    scaffold_tool_registry,
)
from exoswarm.science.contracts import ScientificToolSpec
from exoswarm.science.pipeline import (
    CandidateSearchParameters,
    CandidateSearchRuntimeInputs,
)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("scenario", "expected_action", "expected_verdict", "expected_status", "disposition"),
    [
        (
            "clean",
            None,
            CriticVerdict.VETO,
            InvestigationStatus.READY_TO_LOCK,
            Disposition.PLANETARY_INTERPRETATION_SURVIVES_IMPLEMENTED_VETTING,
        ),
        (
            "eclipsing_binary",
            "harmonic_test",
            CriticVerdict.APPROVE,
            InvestigationStatus.READY_TO_LOCK,
            Disposition.PLANETARY_INTERPRETATION_REJECTED,
        ),
        (
            "contamination",
            "centroid_localization",
            CriticVerdict.REVISE,
            InvestigationStatus.READY_TO_LOCK,
            Disposition.PLANETARY_INTERPRETATION_REJECTED,
        ),
        (
            "weak",
            "alternate_detrend",
            CriticVerdict.APPROVE,
            InvestigationStatus.INSUFFICIENT_EVIDENCE,
            None,
        ),
    ],
)
async def test_curated_evidence_scenarios_take_valid_different_branches(
    tmp_path,
    scenario,
    expected_action,
    expected_verdict,
    expected_status,
    disposition,
) -> None:
    client = policy_client()
    controller = make_controller(tmp_path, client, make_registry(scenario))
    created = controller.create("TARGET-X17")
    seed_baseline(controller, created.run_id, scenario)

    final = await controller.advance(created.run_id)

    adaptive = [item for item in final.tool_executions if item.adaptive]
    expected_actions = [] if expected_action is None else [expected_action]
    assert [item.tool_name for item in adaptive] == expected_actions
    assert final.critic_decisions[-1].verdict == expected_verdict
    assert final.status == expected_status
    assert final.disposition == disposition
    assert final.terminal_reason
    assert final.model_call_count == 2
    assert all(call.model_identity == "mock:evidence-aware-fixture-v1" for call in client.calls)


@pytest.mark.asyncio
async def test_mandatory_baseline_is_controller_enforced_before_any_model_call(tmp_path) -> None:
    calls: Counter[str] = Counter()
    client = policy_client()
    controller = make_controller(tmp_path, client, make_registry("eclipsing_binary", calls=calls))
    state = controller.create("TARGET-X17")

    for expected_count in range(1, 5):
        state = await controller.advance(state.run_id)
        assert state.model_call_count == 0
        assert len(state.completed_tests) == expected_count

    assert set(state.completed_tests) == {
        "signal_quality",
        "odd_even",
        "secondary_eclipse",
        "contamination",
    }
    assert calls == Counter(
        {
            "search_bls": 1,
            "odd_even": 1,
            "secondary_eclipse": 1,
            "contamination_screening": 1,
        }
    )
    assert state.candidate_signals


@pytest.mark.asyncio
async def test_model_timeout_retries_once_then_recovers(tmp_path) -> None:
    client = ScriptedInferenceClient(
        {
            "skeptic": [ModelProviderTimeoutError("fixture timeout"), skeptic_policy],
            "critic": [critic_policy],
        }
    )
    controller = make_controller(
        tmp_path, client, make_registry("eclipsing_binary"), max_model_retries=1
    )
    state = controller.create("TARGET-X17")
    seed_baseline(controller, state.run_id, "eclipsing_binary")

    state = await controller.advance(state.run_id)

    assert state.status == InvestigationStatus.READY_TO_LOCK
    assert state.model_retry_count == 1
    assert state.model_call_count == 3
    assert any(item.kind == HarnessFailureKind.MODEL_TIMEOUT for item in state.failures)
    assert any(event.type == "model.retry" for event in controller.events(state.run_id))


@pytest.mark.asyncio
async def test_scientific_precondition_and_tool_infrastructure_failures_are_distinct(
    tmp_path,
) -> None:
    precondition = make_controller(
        tmp_path / "precondition",
        policy_client(),
        make_registry("eclipsing_binary", adaptive_status=ToolStatus.PRECONDITION_FAILED),
    )
    state = precondition.create("TARGET-X17")
    seed_baseline(precondition, state.run_id, "eclipsing_binary")
    state = await precondition.advance(state.run_id)
    assert state.status == InvestigationStatus.INSUFFICIENT_EVIDENCE
    assert state.failures[-1].kind == HarnessFailureKind.PRECONDITION_FAILED
    assert precondition.evidence(state.run_id)[-1].tool_status == ToolStatus.PRECONDITION_FAILED

    infrastructure = make_controller(
        tmp_path / "infrastructure",
        policy_client(),
        make_registry("eclipsing_binary", raise_tool="harmonic_test"),
    )
    failed = infrastructure.create("TARGET-X17")
    seed_baseline(infrastructure, failed.run_id, "eclipsing_binary")
    failed = await infrastructure.advance(failed.run_id)
    assert failed.status == InvestigationStatus.FAILED
    assert failed.failures[-1].kind == HarnessFailureKind.TOOL_INFRASTRUCTURE_FAILURE
    assert failed.tool_executions[-1].status == ToolExecutionStatus.FAILED
    assert (
        failed.tool_executions[-1].failure_kind
        == HarnessFailureKind.TOOL_INFRASTRUCTURE_FAILURE
    )
    assert "RuntimeError" in (failed.tool_executions[-1].failure_reason or "")


@pytest.mark.asyncio
async def test_mismatched_tool_result_identifiers_fail_the_execution_durably(tmp_path) -> None:
    controller = make_controller(
        tmp_path,
        policy_client(),
        make_registry("eclipsing_binary", mismatch_tool="harmonic_test"),
    )
    state = controller.create("TARGET-X17")
    seed_baseline(controller, state.run_id, "eclipsing_binary")

    failed = await controller.advance(state.run_id)

    execution = failed.tool_executions[-1]
    assert failed.status == InvestigationStatus.FAILED
    assert execution.status == ToolExecutionStatus.FAILED
    assert execution.failure_kind == HarnessFailureKind.TOOL_INFRASTRUCTURE_FAILURE
    assert "identifiers do not match" in (execution.failure_reason or "")
    assert execution.evidence_ref is None
    assert len(controller.evidence(state.run_id)) == 4


@pytest.mark.asyncio
async def test_invalid_tool_result_parameters_fail_the_execution_durably(tmp_path) -> None:
    controller = make_controller(
        tmp_path,
        policy_client(),
        make_registry("eclipsing_binary", malformed_result_tool="harmonic_test"),
    )
    state = controller.create("TARGET-X17")
    seed_baseline(controller, state.run_id, "eclipsing_binary")

    failed = await controller.advance(state.run_id)

    execution = failed.tool_executions[-1]
    assert failed.status == InvestigationStatus.FAILED
    assert execution.status == ToolExecutionStatus.FAILED
    assert execution.failure_kind == HarnessFailureKind.TOOL_INFRASTRUCTURE_FAILURE
    assert "result validation failed" in (execution.failure_reason or "")
    assert execution.evidence_ref is None
    assert len(controller.evidence(state.run_id)) == 4


@pytest.mark.asyncio
async def test_no_evidence_is_preserved_as_scientific_result(tmp_path) -> None:
    controller = make_controller(
        tmp_path,
        policy_client(),
        make_registry("weak", adaptive_status=ToolStatus.NO_EVIDENCE),
        max_adaptive_experiments=1,
    )
    state = controller.create("TARGET-X17")
    seed_baseline(controller, state.run_id, "weak")
    state = await controller.advance(state.run_id)
    assert state.status == InvestigationStatus.INSUFFICIENT_EVIDENCE
    assert controller.evidence(state.run_id)[-1].tool_status == ToolStatus.NO_EVIDENCE


@pytest.mark.asyncio
async def test_tool_result_fixture_provenance_remains_in_ledger(tmp_path) -> None:
    controller = make_controller(tmp_path, policy_client(), make_registry("clean"))
    state = controller.create("TARGET-X17")
    result = fixture_result(
        tool_name="search_bls",
        run_id=state.run_id,
        action_id="fixture_candidate",
        target_id=state.opaque_target_id,
        scenario="clean",
    )
    controller.record_tool_result(state.run_id, result)
    record = controller.evidence(state.run_id)[0]
    assert record.result.provenance.code_version == "test-fixture-v1"
    assert record.result.provenance.source_data_ref.startswith("fixture:")


@pytest.mark.asyncio
async def test_candidate_runtime_inputs_are_typed_backend_owned_and_not_persisted(
    tmp_path,
) -> None:
    captured: dict[str, object] = {}

    def candidate_handler(run_id, action_id, target_id, parameters):
        captured.update(parameters)
        safe_parameters = {
            "preprocessing": parameters["preprocessing"],
            "search": parameters["search"],
        }
        return fixture_result(
            tool_name="search_bls",
            run_id=run_id,
            action_id=action_id,
            target_id=target_id,
            scenario="clean",
            parameters=safe_parameters,
        )

    registry = ScientificToolRegistry(
        [
            ScientificToolSpec(
                name="search_bls",
                handler=candidate_handler,
                parameter_schema=CandidateSearchParameters,
                runtime_input_schema=CandidateSearchRuntimeInputs,
                mandatory_test="signal_quality",
                order=10,
            )
        ]
    )
    cached_path = tmp_path / "private" / "recognizable-target.fits"
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

    updated = await controller.advance(state.run_id)

    assert captured["cached_path"] == cached_path
    assert captured["write_evidence"] is False
    run_dir = controller.artifacts.run_dir(state.opaque_target_id, state.run_id)
    staged_artifact_dir = Path(captured["artifact_dir"])
    assert staged_artifact_dir.name == "artifacts"
    assert staged_artifact_dir.parent.parent == run_dir / ".tool-staging"
    assert not (run_dir / ".tool-staging").exists()
    assert captured["ledger_path"] == controller.artifacts.evidence_path(updated)
    execution = updated.tool_executions[-1]
    assert execution.status == ToolExecutionStatus.COMPLETED
    assert set(execution.parameters) == {"preprocessing", "search"}
    persisted = json.dumps(updated.model_dump(mode="json")) + "\n" + "\n".join(
        event.model_dump_json() for event in controller.events(state.run_id)
    )
    assert str(cached_path) not in persisted
    assert "recognizable-target" not in persisted


@pytest.mark.asyncio
async def test_default_candidate_path_fails_explicitly_without_backend_source(tmp_path) -> None:
    controller = make_controller(
        tmp_path,
        ScriptedInferenceClient({}),
        scaffold_tool_registry(),
    )
    state = controller.create("TARGET-X17")

    failed = await controller.advance(state.run_id)

    assert failed.status == InvestigationStatus.INSUFFICIENT_EVIDENCE
    assert failed.failures[-1].kind == HarnessFailureKind.PRECONDITION_FAILED
    assert "backend-owned cached candidate source" in failed.failures[-1].concise_reason
    assert failed.tool_executions == []
    assert controller.evidence(state.run_id) == ()


@pytest.mark.asyncio
async def test_cached_real_candidate_can_cross_the_controller_runtime_boundary(
    tmp_path,
) -> None:
    repository_root = Path(__file__).parents[3]
    case_path = repository_root / "evals/fixtures/cached_real_tess_case.json"
    case = json.loads(case_path.read_text(encoding="utf-8"))
    cached_path = repository_root / case["cached_path"]
    if not cached_path.is_file():
        pytest.skip("cached-real TESS acceptance artifact is unavailable")
    resolver = MappingCandidateSourceResolver(
        {
            case["opaque_target_id"]: CachedCandidateSource(
                cached_path=cached_path
            )
        }
    )
    controller = make_controller(
        tmp_path,
        ScriptedInferenceClient({}),
        scaffold_tool_registry(),
        candidate_sources=resolver,
    )
    state = controller.create(case["opaque_target_id"])

    updated = await controller.advance(state.run_id)

    assert updated.candidate_signals
    assert updated.completed_tests == ["signal_quality"]
    assert updated.tool_executions[-1].status == ToolExecutionStatus.COMPLETED
    assert len(controller.evidence(state.run_id)) == 1
    assert str(cached_path) not in json.dumps(updated.model_dump(mode="json"))


@pytest.mark.asyncio
async def test_cached_real_candidate_completes_the_production_mandatory_vetting_path(
    tmp_path,
) -> None:
    repository_root = Path(__file__).parents[3]
    case_path = repository_root / "evals/fixtures/cached_real_tess_case.json"
    case = json.loads(case_path.read_text(encoding="utf-8"))
    cached_path = repository_root / case["cached_path"]
    if not cached_path.is_file():
        pytest.skip("cached-real TESS acceptance artifact is unavailable")
    resolver = MappingCandidateSourceResolver(
        {
            case["opaque_target_id"]: CachedCandidateSource(
                cached_path=cached_path
            )
        }
    )
    controller = make_controller(
        tmp_path,
        ScriptedInferenceClient({}),
        scaffold_tool_registry(),
        candidate_sources=resolver,
    )
    state = controller.create(case["opaque_target_id"])

    for _ in range(state.max_steps + 1):
        state = await controller.advance(state.run_id)
        if state.status in {
            InvestigationStatus.READY_TO_LOCK,
            InvestigationStatus.INSUFFICIENT_EVIDENCE,
            InvestigationStatus.FAILED,
            InvestigationStatus.BUDGET_EXHAUSTED,
        }:
            break

    assert state.status == InvestigationStatus.READY_TO_LOCK
    assert state.completed_tests == [
        "signal_quality",
        "odd_even",
        "secondary_eclipse",
        "contamination",
    ]
    assert [record.tool_name for record in controller.evidence(state.run_id)] == [
        "search_bls",
        "odd_even",
        "secondary_eclipse",
        "contamination_screening",
    ]
    assert state.disposition == Disposition.PLANETARY_INTERPRETATION_REJECTED
    persisted = json.dumps(state.model_dump(mode="json")) + "\n" + "\n".join(
        event.model_dump_json() for event in controller.events(state.run_id)
    )
    assert str(cached_path) not in persisted
