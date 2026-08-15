from __future__ import annotations

import json

import pytest
from harness_support import fixture_result, make_controller, make_registry, seed_baseline

from exoswarm.agents.context import (
    FORBIDDEN_CONTEXT_KEYS,
    AgentContextPacket,
    ContextSizeError,
    assemble_context,
    assert_agent_safe_context,
    serialized_context_bytes,
)
from exoswarm.agents.model_client import ScriptedInferenceClient
from exoswarm.domain.enums import InformationValue, Priority
from exoswarm.domain.models import (
    EvidenceRecord,
    InvestigationState,
    Provenance,
    ScientificToolResult,
    SkepticDecision,
)


def test_context_is_compact_ledger_derived_and_ground_truth_isolated(tmp_path) -> None:
    controller = make_controller(
        tmp_path, ScriptedInferenceClient({}), make_registry("contamination")
    )
    state = controller.create("TARGET-X17")
    result = fixture_result(
        tool_name="search_bls",
        run_id=state.run_id,
        action_id="fixture_path_boundary",
        target_id=state.opaque_target_id,
        scenario="contamination",
    )
    result = ScientificToolResult.model_validate(
        {
            **result.model_dump(mode="python"),
            "provenance": Provenance(
                code_version="test-fixture-v1",
                source_data_ref=r"C:\private\cached\recognizable-target.fits",
                output_artifact_refs=["artifacts/raw-lightcurve-array.json"],
            ),
        }
    )
    state = controller.record_tool_result(state.run_id, result)

    packet = assemble_context(
        state,
        controller.evidence(state.run_id),
        available_experiments=("centroid_localization",),
    )
    payload = packet.model_dump(mode="json")
    serialized = json.dumps(payload).lower()

    assert packet.opaque_target_id == "TARGET-X17"
    assert packet.candidate is not None
    assert packet.candidate.measurements["period"].unit == "day"
    assert packet.candidate.measurements["period"].evidence_ref in packet.evidence_refs
    assert tuple(item.action_name for item in packet.available_experiments) == (
        "centroid_localization",
    )
    assert packet.available_experiments[0].deterministic_cost == 2
    assert not FORBIDDEN_CONTEXT_KEYS.intersection(payload)
    assert "recognizable-target" not in serialized
    assert ".fits" not in serialized
    assert "c:\\private" not in serialized
    assert "raw-lightcurve-array" not in serialized
    assert "catalog" not in serialized
    assert "ground_truth" not in serialized


def test_context_contains_only_recent_compact_evidence(tmp_path) -> None:
    controller = make_controller(tmp_path, ScriptedInferenceClient({}), make_registry("clean"))
    state = controller.create("TARGET-X17")
    seed_baseline(controller, state.run_id, "clean")
    state = controller.get(state.run_id)
    packet = assemble_context(state, controller.evidence(state.run_id), recent_limit=2)
    assert len(packet.recent_evidence) == 2
    assert len(packet.evidence_refs) == 2
    assert set(packet.evidence_refs).issubset(state.evidence_refs)
    assert all(item.code_version == "test-fixture-v1" for item in packet.recent_evidence)


def test_candidate_numbers_are_exactly_traceable_to_deterministic_evidence(tmp_path) -> None:
    controller = make_controller(tmp_path, ScriptedInferenceClient({}), make_registry("clean"))
    state = controller.create("TARGET-X17")
    seed_baseline(controller, state.run_id, "clean")
    state = controller.get(state.run_id)
    candidate = state.candidate_signals[0]
    ledger = {record.evidence_id: record for record in controller.evidence(state.run_id)}

    for name, measurement in candidate.measurements.items():
        assert measurement.evidence_ref in ledger
        source = ledger[measurement.evidence_ref].result.measurements[name]
        assert (measurement.value, measurement.unit) == (source.value, source.unit)


@pytest.mark.parametrize(
    "forbidden_value",
    [
        "/private/cache/recognizable-target.csv",
        "file:///private/cache/target.fits",
        r"C:\private\cache\target.fits",
        "TIC 123456789",
        "TOI-700 d",
        "ground-truth catalog reveal",
        "[0.9998, 1.0001, 0.9987, 1.0002]",
    ],
)
def test_context_rejects_paths_identity_truth_and_raw_array_strings(
    forbidden_value,
) -> None:
    state = InvestigationState(
        run_id="run_context_boundary",
        opaque_target_id="TARGET-X17",
        active_hypotheses=[forbidden_value],
    )

    with pytest.raises(RuntimeError, match="agent context"):
        assemble_context(state)


def test_context_reviews_every_proposed_decision_string() -> None:
    state = InvestigationState(
        run_id="run_proposal_boundary",
        opaque_target_id="TARGET-X17",
        step_count=1,
    )
    decision = SkepticDecision(
        decision_id="decision_1",
        run_id=state.run_id,
        step_id="step_0001",
        context_version=state.context_version,
        hypothesis_under_test="eclipsing_binary",
        requested_experiment="harmonic_test",
        reason_code="LOCAL_SOURCE_LEAK",
        expected_discriminating_result="Read /private/cache/recognizable-target.csv",
        expected_information_value=InformationValue.MEDIUM,
        priority=Priority.MEDIUM,
        budget_units_remaining=state.adaptive_cost_units_remaining,
        cost_of_selected_experiment=1,
        why_cost_is_justified="The action is bounded and directly discriminating.",
        concise_reason="A compact proposed action.",
    )

    with pytest.raises(RuntimeError, match="agent context"):
        assemble_context(state, role="critic", proposed_decision=decision)


def test_context_allows_scientific_notation_units_and_ordinary_prose() -> None:
    state = InvestigationState(
        run_id="run_legitimate_context",
        opaque_target_id="TARGET-X17",
        active_hypotheses=["instrumental_or_variable_noise"],
        strongest_unresolved_alternative="eclipsing_binary",
    )
    packet = assemble_context(state)
    payload = packet.model_dump(mode="python")
    payload["proposed_decision"] = SkepticDecision(
        decision_id="decision_legitimate",
        run_id=state.run_id,
        step_id="step_0000",
        context_version=state.context_version,
        hypothesis_under_test="eclipsing_binary",
        requested_experiment="harmonic_test",
        reason_code="COMPARE_ODD_EVEN",
        expected_discriminating_result="Compare a 1e-5 fractional signal in m/s units.",
        expected_information_value=InformationValue.MEDIUM,
        priority=Priority.MEDIUM,
        budget_units_remaining=state.adaptive_cost_units_remaining,
        cost_of_selected_experiment=1,
        why_cost_is_justified="The action is bounded and directly discriminating.",
        concise_reason="Ordinary scientific prose remains valid.",
    )

    assert_agent_safe_context(AgentContextPacket.model_validate(payload))


def _evidence_record(
    state: InvestigationState,
    *,
    index: int,
    interpretation_code: str | None = None,
) -> EvidenceRecord:
    result = fixture_result(
        tool_name="harmonic_test",
        run_id=state.run_id,
        action_id=f"pressure_action_{index}",
        target_id=state.opaque_target_id,
        scenario="clean",
        interpretation_code=interpretation_code,
    )
    return EvidenceRecord(
        evidence_id=f"evidence_pressure_{index}",
        run_id=state.run_id,
        step_id=f"step_{index:04d}",
        action_id=result.action_id,
        opaque_target_id=state.opaque_target_id,
        tool_name=result.tool_name,
        tool_status=result.status,
        result=result,
        interpretation_code=interpretation_code,
    )


def test_available_experiments_include_decision_metadata_and_authoritative_costs(
    tmp_path,
) -> None:
    controller = make_controller(tmp_path, ScriptedInferenceClient({}), make_registry("clean"))
    state = controller.create("TARGET-X17")
    seed_baseline(controller, state.run_id, "clean")
    state = controller.get(state.run_id)

    packet = assemble_context(
        state,
        controller.evidence(state.run_id),
        available_experiments=("harmonic_test", "centroid_localization"),
        adaptive_experiment_costs={"harmonic_test": 1, "centroid_localization": 2},
        experiment_specs=controller.registry.specs,
    )
    options = {item.action_name: item for item in packet.available_experiments}

    assert options["centroid_localization"].deterministic_cost == 2
    assert options["harmonic_test"].required_completed_tests == tuple(
        sorted(state.completed_tests)
    )
    assert options["harmonic_test"].parameter_contract["properties"]["trial_factor"] == {
        "type": "integer",
        "default": 1,
        "minimum": 1,
        "maximum": 2,
    }
    assert options["harmonic_test"].already_executed is False
    assert options["harmonic_test"].availability_reason is None


def test_context_omits_previously_executed_and_unavailable_actions(tmp_path) -> None:
    controller = make_controller(tmp_path, ScriptedInferenceClient({}), make_registry("clean"))
    state = controller.create("TARGET-X17")
    seed_baseline(controller, state.run_id, "clean")
    controller.record_tool_result(
        state.run_id,
        fixture_result(
            tool_name="harmonic_test",
            run_id=state.run_id,
            action_id="executed_harmonic",
            target_id=state.opaque_target_id,
            scenario="clean",
            parameters={"trial_factor": 1},
        ),
    )
    state = controller.get(state.run_id)

    packet = assemble_context(
        state,
        controller.evidence(state.run_id),
        available_experiments=("centroid_localization",),
        adaptive_experiment_costs={"centroid_localization": 2},
        experiment_specs=controller.registry.specs,
    )
    assert tuple(item.action_name for item in packet.available_experiments) == (
        "centroid_localization",
    )


def test_relevant_adverse_evidence_survives_context_pressure() -> None:
    state = InvestigationState(
        run_id="run_pressure",
        opaque_target_id="TARGET-X17",
        strongest_unresolved_alternative="background_contamination",
    )
    records = [
        _evidence_record(
            state,
            index=index,
            interpretation_code=(
                "CONTAMINATION_LIKELY"
                if index == 0
                else (
                    "ODD_EVEN_CONSISTENT",
                    "NO_SECONDARY_ECLIPSE",
                    "NO_CONTAMINATION_CAPACITY",
                    "CANDIDATE_PERIOD_PREFERRED",
                )[(index - 1) % 4]
            ),
        )
        for index in range(8)
    ]
    state = state.model_copy(update={"evidence_refs": [item.evidence_id for item in records]})

    packet = assemble_context(
        state,
        records,
        recent_limit=8,
        max_serialized_bytes=2_000,
    )

    assert "evidence_pressure_0" in packet.evidence_refs
    assert len(packet.recent_evidence) < len(records)
    assert len(serialized_context_bytes(packet)) <= 2_000
    assert packet.serialized_size_bytes == len(serialized_context_bytes(packet))


def test_context_fails_when_required_evidence_cannot_fit() -> None:
    state = InvestigationState(run_id="run_required_pressure", opaque_target_id="TARGET-X17")
    records = [
        _evidence_record(state, index=index, interpretation_code="ODD_EVEN_MISMATCH")
        for index in range(8)
    ]
    state = state.model_copy(update={"evidence_refs": [item.evidence_id for item in records]})

    with pytest.raises(ContextSizeError, match="required agent evidence"):
        assemble_context(state, records, max_serialized_bytes=2_000)


def test_context_reconstruction_is_deterministic_after_restart() -> None:
    state = InvestigationState(
        run_id="run_restart_context",
        opaque_target_id="TARGET-X17",
        active_hypotheses=["eclipsing_binary"],
        strongest_unresolved_alternative="eclipsing_binary",
    )
    record = _evidence_record(state, index=1, interpretation_code="ODD_EVEN_MISMATCH")
    state = state.model_copy(update={"evidence_refs": [record.evidence_id]})
    first = assemble_context(state, [record])

    restarted_state = InvestigationState.model_validate_json(state.model_dump_json())
    restarted_record = EvidenceRecord.model_validate_json(record.model_dump_json())
    rebuilt = assemble_context(restarted_state, [restarted_record])

    assert rebuilt == first
    assert serialized_context_bytes(rebuilt) == serialized_context_bytes(first)


def test_context_fingerprint_changes_when_durable_evidence_changes() -> None:
    state = InvestigationState(run_id="run_context_hash", opaque_target_id="TARGET-X17")
    first_record = _evidence_record(state, index=1)
    second_record = _evidence_record(state, index=2)

    before = assemble_context(state, [first_record], recent_limit=0)
    after = assemble_context(state, [first_record, second_record], recent_limit=0)

    assert before.context_fingerprint != after.context_fingerprint


def test_context_rejects_raw_numeric_arrays_in_proposed_parameters() -> None:
    state = InvestigationState(
        run_id="run_raw_parameter_boundary",
        opaque_target_id="TARGET-X17",
        step_count=1,
    )
    decision = SkepticDecision(
        decision_id="decision_raw_parameters",
        run_id=state.run_id,
        step_id="step_0001",
        context_version=state.context_version,
        hypothesis_under_test="eclipsing_binary",
        requested_experiment="harmonic_test",
        parameters={"samples": [0.9, 1.0, 1.1]},
        reason_code="RAW_PARAMETER_TEST",
        expected_discriminating_result="Use a deterministic bounded diagnostic.",
        expected_information_value=InformationValue.MEDIUM,
        priority=Priority.MEDIUM,
        budget_units_remaining=state.adaptive_cost_units_remaining,
        cost_of_selected_experiment=1,
        why_cost_is_justified="The bounded action costs one unit.",
        concise_reason="The array must be rejected before inference.",
    )

    with pytest.raises(RuntimeError, match="agent context"):
        assemble_context(state, role="critic", proposed_decision=decision)
