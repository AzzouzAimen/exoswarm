from __future__ import annotations

import asyncio

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
from pydantic import BaseModel

from exoswarm.agents.context import AgentContextPacket
from exoswarm.agents.model_client import ScriptedInferenceClient
from exoswarm.agents.prompt_registry import (
    PROMPT_HASH_LOCKS,
    PROMPT_REGISTRY,
    effective_output_token_limit,
    effective_per_role_call_limit,
    effective_timeout_seconds,
    prompt_template_sha256,
    validate_prompt_registry,
)
from exoswarm.agents.role_context import (
    DirectorContext,
    ObservationQualityEvidence,
    ObserverContext,
    SignalContext,
    TransitHunterContext,
    assemble_role_context,
)
from exoswarm.domain.enums import AgentCheckpointStatus, AgentPhase, AgentRole, ThinkingMode
from exoswarm.domain.errors import ModelProviderTimeoutError
from exoswarm.domain.models import (
    AgentRoleCheckpoint,
    DirectorDecision,
    EvidenceRecord,
    InvestigationState,
    ObserverAssessment,
    SignalAssessment,
    TransitHunterBrief,
)
from exoswarm.evaluation.outcomes import compare_scientific_outcomes
from exoswarm.investigation.controller import InvestigationController


def observer_policy(context: BaseModel, _schema: type[BaseModel]) -> ObserverAssessment:
    packet = ObserverContext.model_validate(context)
    return ObserverAssessment(
        decision_id=f"observer_{packet.step_id}",
        run_id=packet.run_id,
        step_id=packet.step_id,
        context_version=packet.context_version,
        quality_flags=["QUALITY_ACCEPTABLE"],
        preparation_concerns=["NONE"],
        cited_evidence_refs=[packet.evidence_refs[-1]],
        observation_limitations="The cited evidence supports no additional limitation.",
        questions_for_later_roles=["Does mandatory vetting leave an ambiguity?"],
    )


def signal_policy(context: BaseModel, _schema: type[BaseModel]) -> SignalAssessment:
    packet = SignalContext.model_validate(context)
    return SignalAssessment(
        decision_id=f"signal_{packet.step_id}",
        run_id=packet.run_id,
        step_id=packet.step_id,
        context_version=packet.context_version,
        leading_hypothesis="planetary_transit",
        alternative_hypothesis="eclipsing_binary",
        ambiguity_flags=["NONE"],
        cited_evidence_refs=[packet.evidence_refs[-1]],
        vetting_questions=["Does the bounded review find contrary evidence?"],
        concise_reason="The cited deterministic evidence remains transit-like.",
    )


def transit_policy(context: BaseModel, _schema: type[BaseModel]) -> TransitHunterBrief:
    packet = TransitHunterContext.model_validate(context)
    return TransitHunterBrief(
        decision_id=f"transit_{packet.step_id}",
        run_id=packet.run_id,
        step_id=packet.step_id,
        context_version=packet.context_version,
        focus_candidate_id=packet.candidate.candidate_id,
        viability_code="VIABLE_FOR_VETTING",
        ambiguity_codes=["NONE"],
        strongest_vetting_question="Can any allowed action change the interpretation?",
        cited_evidence_refs=[packet.evidence_refs[-1]],
        ranked_action_names=[item.action_name for item in packet.available_experiments],
    )


def director_policy(context: BaseModel, _schema: type[BaseModel]) -> DirectorDecision:
    packet = DirectorContext.model_validate(context)
    focus = packet.active_hypotheses[0] if packet.active_hypotheses else "unresolved"
    return DirectorDecision(
        decision_id=f"director_{packet.phase}_{packet.step_id}",
        run_id=packet.run_id,
        step_id=packet.step_id,
        context_version=packet.context_version,
        phase=packet.phase,
        authorized_route=packet.authorized_route,
        deterministic_disposition=packet.deterministic_disposition,
        focus_hypothesis=focus,
        requested_handoffs=["skeptic", "critic"],
        cited_evidence_refs=[packet.evidence_refs[-1]],
        conflict_codes=["NONE"],
        mission_brief="Follow the binding route and keep deterministic evidence authoritative.",
    )


def six_role_client() -> ScriptedInferenceClient:
    return ScriptedInferenceClient(
        {
            "observer": [observer_policy],
            "signal": [signal_policy],
            "transit_hunter": [transit_policy],
            "director": [director_policy, director_policy],
            "skeptic": [skeptic_policy],
            "critic": [critic_policy],
        },
        model_identity="mock:six-role-v1",
    )


class ConcurrentSpecialistClient(ScriptedInferenceClient):
    def __init__(self) -> None:
        super().__init__(
            {
                "observer": [observer_policy],
                "signal": [signal_policy],
                "transit_hunter": [transit_policy],
            }
        )
        self._parallel_gate = asyncio.Event()
        self._entered_parallel_roles: set[str] = set()
        self.observed_overlap = False

    async def decide_attempt(self, **kwargs):
        role = kwargs["role"]
        if role in {"observer", "signal"}:
            self._entered_parallel_roles.add(role)
            if len(self._entered_parallel_roles) == 2:
                self.observed_overlap = True
                self._parallel_gate.set()
            await asyncio.wait_for(self._parallel_gate.wait(), timeout=1)
        return await super().decide_attempt(**kwargs)


@pytest.mark.asyncio
async def test_six_role_path_is_seven_calls_and_scientifically_result_neutral(tmp_path) -> None:
    multi = make_controller(
        tmp_path / "multi",
        six_role_client(),
        make_registry("clean"),
        multi_agent_enabled=True,
        max_model_calls=24,
    )
    state = multi.create("TARGET-X17")
    seed_baseline(multi, state.run_id, "clean")
    multi_result = await multi.advance(state.run_id)

    baseline = make_controller(
        tmp_path / "baseline", policy_client(), make_registry("clean")
    )
    baseline_state = baseline.create("TARGET-X17")
    seed_baseline(baseline, baseline_state.run_id, "clean")
    baseline_result = await baseline.advance(baseline_state.run_id)

    comparison = compare_scientific_outcomes(
        baseline_result,
        baseline.artifacts.read_evidence(baseline_result),
        multi_result,
        multi.artifacts.read_evidence(multi_result),
    )
    assert comparison.equivalent, comparison.mismatch_paths
    assert multi_result.model_call_count == 7
    records = multi.artifacts.read_agent_decisions(multi_result)
    assert len(records) == 7
    assert {record.role for record in records} == set(AgentRole)
    assert all(record.status == AgentCheckpointStatus.COMPLETE for record in records)
    assert all(record.evidence_refs for record in records)
    final_director = next(
        record
        for record in records
        if record.role == AgentRole.DIRECTOR and record.phase == AgentPhase.FINAL
    )
    assert final_director.decision is not None
    assert final_director.decision["deterministic_disposition"] == (
        multi_result.disposition.value
    )


@pytest.mark.asyncio
async def test_decisive_adaptive_result_still_runs_final_director(tmp_path) -> None:
    controller = make_controller(
        tmp_path,
        six_role_client(),
        make_registry(
            "clean", adaptive_interpretations={"harmonic_test": "CLEAN_PLANET_LIKE"}
        ),
        multi_agent_enabled=True,
        max_model_calls=24,
    )
    state = controller.create("TARGET-X17")
    for index, tool_name in enumerate(
        ("search_bls", "odd_even", "secondary_eclipse", "contamination_screening"),
        1,
    ):
        controller.record_tool_result(
            state.run_id,
            fixture_result(
                tool_name=tool_name,
                run_id=state.run_id,
                action_id=f"fixture_neutral_{index}",
                target_id=state.opaque_target_id,
                scenario="clean",
                interpretation_code=None,
            ),
        )

    final = await controller.advance(state.run_id)

    assert final.disposition is not None
    assert any(item.adaptive for item in final.tool_executions)
    assert any(
        checkpoint.role == AgentRole.DIRECTOR
        and checkpoint.phase == AgentPhase.FINAL
        and checkpoint.status == AgentCheckpointStatus.COMPLETE
        for checkpoint in final.role_checkpoints
    )


@pytest.mark.asyncio
async def test_director_semantic_repair_receives_bounded_specific_code(tmp_path) -> None:
    def invalid_focus(context: BaseModel, schema: type[BaseModel]) -> DirectorDecision:
        return director_policy(context, schema).model_copy(
            update={"focus_hypothesis": "outside_the_bounded_state"}
        )

    client = ScriptedInferenceClient(
        {
            "observer": [observer_policy],
            "signal": [signal_policy],
            "transit_hunter": [transit_policy],
            "director": [invalid_focus, director_policy, director_policy],
            "skeptic": [skeptic_policy],
            "critic": [critic_policy],
        }
    )
    controller = make_controller(
        tmp_path, client, make_registry("clean"), multi_agent_enabled=True
    )
    state = controller.create("TARGET-X17")
    seed_baseline(controller, state.run_id, "clean")

    await controller.advance(state.run_id)

    director_attempts = [
        event.payload
        for event in controller.events(state.run_id)
        if event.type == "inference.attempt" and event.payload["role"] == "director"
    ]
    assert director_attempts[0]["validation_error_code"] == (
        "DIRECTOR_FOCUS_OUT_OF_SCOPE"
    )
    assert director_attempts[1]["attempt_kind"] == "repair"


@pytest.mark.asyncio
async def test_skeptic_numeric_narrative_is_repaired_before_acceptance(tmp_path) -> None:
    def numeric_narrative(
        context: BaseModel, schema: type[BaseModel]
    ) -> object:
        return skeptic_policy(context, schema).model_copy(
            update={"concise_reason": "The candidate period is 1.5 days."}
        )

    client = ScriptedInferenceClient(
        {
            "skeptic": [numeric_narrative, skeptic_policy],
            "critic": [critic_policy],
        }
    )
    controller = make_controller(tmp_path, client, make_registry("clean"))
    state = controller.create("TARGET-X17")
    seed_baseline(controller, state.run_id, "clean")

    await controller.advance(state.run_id)

    skeptic_attempts = [
        event.payload
        for event in controller.events(state.run_id)
        if event.type == "inference.attempt" and event.payload["role"] == "skeptic"
    ]
    assert skeptic_attempts[0]["validation_error_code"] == (
        "NUMERIC_NARRATIVE_UNSUPPORTED"
    )
    assert skeptic_attempts[1]["attempt_kind"] == "repair"


@pytest.mark.asyncio
async def test_specialist_checkpoint_is_idempotent_before_and_after_reload(tmp_path) -> None:
    client = six_role_client()
    first = make_controller(
        tmp_path, client, make_registry("clean"), multi_agent_enabled=True
    )
    state = first.create("TARGET-X17")
    seed_baseline(first, state.run_id, "clean")
    first.begin_cycle(state.run_id)

    await first.run_specialist_briefing(state.run_id)
    assert first.get(state.run_id).model_call_count == 3
    await first.run_specialist_briefing(state.run_id)
    assert first.get(state.run_id).model_call_count == 3

    reloaded = make_controller(
        tmp_path,
        ScriptedInferenceClient({}),
        make_registry("clean"),
        multi_agent_enabled=True,
    )
    await reloaded.run_specialist_briefing(state.run_id)
    recovered = reloaded.get(state.run_id)
    assert recovered.model_call_count == 3
    assert {
        (checkpoint.role, checkpoint.phase)
        for checkpoint in recovered.role_checkpoints
    }.issuperset(
        {
            (AgentRole.OBSERVER, AgentPhase.BRIEFING),
            (AgentRole.SIGNAL, AgentPhase.BRIEFING),
            (AgentRole.TRANSIT_HUNTER, AgentPhase.BRIEFING),
        }
    )


@pytest.mark.asyncio
async def test_observer_and_signal_calls_overlap_before_transit_handoff(tmp_path) -> None:
    client = ConcurrentSpecialistClient()
    controller = make_controller(
        tmp_path, client, make_registry("clean"), multi_agent_enabled=True
    )
    state = controller.create("TARGET-X17")
    seed_baseline(controller, state.run_id, "clean")
    controller.begin_cycle(state.run_id)

    await controller.run_specialist_briefing(state.run_id)

    assert client.observed_overlap is True
    records = controller.artifacts.read_agent_decisions(controller.get(state.run_id))
    assert [record.role for record in records] == [
        AgentRole.OBSERVER,
        AgentRole.SIGNAL,
        AgentRole.TRANSIT_HUNTER,
    ]


@pytest.mark.asyncio
async def test_promoted_briefs_reach_skeptic_but_not_independent_critic(tmp_path) -> None:
    observed: dict[str, dict[str, dict[str, object]]] = {}

    def inspect_skeptic(context: BaseModel, schema: type[BaseModel]):
        packet = AgentContextPacket.model_validate(context)
        observed["skeptic"] = packet.promoted_advisory_briefs
        return skeptic_policy(context, schema)

    def inspect_critic(context: BaseModel, schema: type[BaseModel]):
        packet = AgentContextPacket.model_validate(context)
        observed["critic"] = packet.promoted_advisory_briefs
        return critic_policy(context, schema)

    client = ScriptedInferenceClient(
        {
            "observer": [observer_policy],
            "signal": [signal_policy],
            "transit_hunter": [transit_policy],
            "director": [director_policy, director_policy],
            "skeptic": [inspect_skeptic],
            "critic": [inspect_critic],
        }
    )
    controller = make_controller(
        tmp_path,
        client,
        make_registry("clean"),
        multi_agent_enabled=True,
        specialist_advisory_enabled=True,
    )
    state = controller.create("TARGET-X17")
    seed_baseline(controller, state.run_id, "clean")

    final = await controller.advance(state.run_id)

    assert final.disposition is not None
    assert set(observed["skeptic"]) == {"transit_hunter", "director"}
    assert observed["skeptic"]["director"]["focus_hypothesis"]
    assert observed["skeptic"]["transit_hunter"]["ranked_action_names"]
    assert observed["critic"] == {}
    starts = [
        event.payload
        for event in controller.events(state.run_id)
        if event.type == "agent.started"
    ]
    skeptic_start = next(item for item in starts if item["role"] == "skeptic")
    critic_start = next(item for item in starts if item["role"] == "critic")
    assert set(skeptic_start["advisory_roles"]) == {"director", "transit_hunter"}
    assert critic_start["advisory_roles"] == []


@pytest.mark.asyncio
async def test_advisory_timeout_skips_to_safe_baseline(tmp_path) -> None:
    client = ScriptedInferenceClient(
        {
            "observer": [
                ModelProviderTimeoutError("fixture timeout"),
                ModelProviderTimeoutError("fixture timeout"),
            ],
            "skeptic": [skeptic_policy],
            "critic": [critic_policy],
        }
    )
    controller = make_controller(
        tmp_path,
        client,
        make_registry("clean"),
        multi_agent_enabled=True,
        max_model_retries=3,
    )
    state = controller.create("TARGET-X17")
    seed_baseline(controller, state.run_id, "clean")

    final = await controller.advance(state.run_id)

    baseline = make_controller(
        tmp_path / "baseline", policy_client(), make_registry("clean")
    )
    baseline_state = baseline.create("TARGET-X17")
    seed_baseline(baseline, baseline_state.run_id, "clean")
    baseline_final = await baseline.advance(baseline_state.run_id)

    assert final.disposition is not None
    skipped = [
        event for event in controller.events(state.run_id) if event.type == "agent.skipped"
    ]
    assert any(
        event.payload["role"] == "observer"
        and event.payload["label"] == "ROLE_SKIPPED_TO_SAFE_BASELINE"
        for event in skipped
    )
    assert final.model_call_count == 4
    assert not [failure for failure in final.failures if failure.kind.value == "MODEL_TIMEOUT"]
    observer_attempts = [
        event
        for event in controller.events(state.run_id)
        if event.type == "inference.attempt" and event.payload["role"] == "observer"
    ]
    assert len(observer_attempts) == 2
    comparison = compare_scientific_outcomes(
        baseline_final,
        baseline.artifacts.read_evidence(baseline_final),
        final,
        controller.artifacts.read_evidence(final),
    )
    assert comparison.equivalent, comparison.mismatch_paths


def test_role_context_models_enforce_isolation() -> None:
    assert "available_experiments" not in ObserverContext.model_fields
    assert "promoted_specialist_briefs" not in SignalContext.model_fields
    assert "critic_verdict" not in TransitHunterContext.model_fields
    assert "proposed_decision" not in DirectorContext.model_fields
    assert "measurements" not in ObservationQualityEvidence.model_fields


def test_observer_context_contains_quality_metadata_not_candidate_measurements(
    tmp_path,
) -> None:
    controller = make_controller(tmp_path, policy_client(), make_registry("clean"))
    state = controller.create("TARGET-X17")
    seed_baseline(controller, state.run_id, "clean")
    state = controller.get(state.run_id)

    context = assemble_role_context(
        state,
        controller.artifacts.read_evidence(state),
        role="observer",
    )
    packet = ObserverContext.model_validate(context)

    assert packet.quality_evidence
    assert {item.tool_name for item in packet.quality_evidence} == {"search_bls"}
    assert all("measurements" not in item.model_dump() for item in packet.quality_evidence)


def test_every_versioned_prompt_has_an_exact_hash_lock() -> None:
    validate_prompt_registry()
    assert set(PROMPT_HASH_LOCKS) == {
        registration.prompt_version for registration in PROMPT_REGISTRY.values()
    }
    assert {
        registration.prompt_version: prompt_template_sha256(role)
        for role, registration in PROMPT_REGISTRY.items()
    } == PROMPT_HASH_LOCKS


def test_thinking_uses_dedicated_bounded_token_and_timeout_headroom() -> None:
    assert effective_output_token_limit(
        AgentRole.SKEPTIC,
        configured_max_output_tokens=20_000,
        thinking_mode=ThinkingMode.ON,
    ) == 20_000
    assert effective_output_token_limit(
        AgentRole.SKEPTIC,
        configured_max_output_tokens=20_000,
        thinking_mode=ThinkingMode.OFF,
    ) == 1_200
    assert effective_timeout_seconds(
        AgentRole.SKEPTIC,
        configured_timeout_seconds=120,
        thinking_mode=ThinkingMode.ON,
    ) == 120
    assert effective_timeout_seconds(
        AgentRole.SKEPTIC,
        configured_timeout_seconds=120,
        thinking_mode=ThinkingMode.OFF,
    ) == 30
    assert effective_per_role_call_limit(
        AgentRole.SKEPTIC, thinking_mode=ThinkingMode.ON
    ) == 3
    assert effective_per_role_call_limit(
        AgentRole.SKEPTIC, thinking_mode=ThinkingMode.OFF
    ) == 2


def test_role_checkpoint_only_suppresses_the_same_context_version() -> None:
    checkpoint = AgentRoleCheckpoint(
        role=AgentRole.OBSERVER,
        phase=AgentPhase.BRIEFING,
        context_version="1",
        decision_id="observer_step_0001",
        status=AgentCheckpointStatus.COMPLETE,
    )
    original = InvestigationState(
        run_id="run_checkpoint",
        opaque_target_id="TARGET-X17",
        context_version="1",
        role_checkpoints=[checkpoint],
    )
    refreshed = original.model_copy(update={"context_version": "2"})

    assert InvestigationController._role_checkpoint_done(
        original, AgentRole.OBSERVER, AgentPhase.BRIEFING
    )
    assert not InvestigationController._role_checkpoint_done(
        refreshed, AgentRole.OBSERVER, AgentPhase.BRIEFING
    )


def test_semantic_outcome_comparator_reports_scientific_mismatch(tmp_path) -> None:
    controller = make_controller(tmp_path, policy_client(), make_registry("clean"))
    state = controller.create("TARGET-X17")
    seed_baseline(controller, state.run_id, "clean")
    state = controller.get(state.run_id)
    changed = state.model_copy(update={"adaptive_cost_units_remaining": 3})

    comparison = compare_scientific_outcomes(
        state,
        controller.artifacts.read_evidence(state),
        changed,
        controller.artifacts.read_evidence(state),
    )

    assert comparison.equivalent is False
    assert "$.budget.adaptive_cost_remaining" in comparison.mismatch_paths


def test_semantic_outcome_comparator_ignores_generated_action_artifact_names() -> None:
    def evidence(run_id: str, action_id: str) -> EvidenceRecord:
        result = fixture_result(
            tool_name="search_bls",
            run_id=run_id,
            action_id=action_id,
            target_id="TARGET-X17",
            scenario="clean",
        )
        artifact_ref = f"artifacts/{action_id}.candidate-search.json"
        result = result.model_copy(
            update={
                "diagnostics": {"masks_artifact_ref": artifact_ref},
                "provenance": result.provenance.model_copy(
                    update={"output_artifact_refs": [artifact_ref]}
                ),
            }
        )
        return EvidenceRecord(
            evidence_id=f"evidence_{action_id}",
            run_id=run_id,
            step_id="step_0001",
            action_id=action_id,
            opaque_target_id="TARGET-X17",
            tool_name=result.tool_name,
            tool_status=result.status,
            result=result,
        )

    baseline = InvestigationState(run_id="run_baseline", opaque_target_id="TARGET-X17")
    candidate = InvestigationState(run_id="run_candidate", opaque_target_id="TARGET-X17")
    comparison = compare_scientific_outcomes(
        baseline,
        [evidence(baseline.run_id, "action_baseline")],
        candidate,
        [evidence(candidate.run_id, "action_candidate")],
    )

    assert comparison.equivalent, comparison.mismatch_paths
