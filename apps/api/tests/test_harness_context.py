from __future__ import annotations

import json

import pytest
from harness_support import fixture_result, make_controller, make_registry, seed_baseline

from exoswarm.agents.context import (
    FORBIDDEN_CONTEXT_KEYS,
    AgentContextPacket,
    assemble_context,
    assert_agent_safe_context,
)
from exoswarm.agents.model_client import ScriptedInferenceClient
from exoswarm.domain.enums import InformationValue, Priority
from exoswarm.domain.models import (
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
    assert packet.available_experiments == ("centroid_localization",)
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
    assert len(packet.evidence_refs) == 4
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
        hypothesis_under_test="eclipsing_binary",
        requested_experiment="harmonic_test",
        reason_code="LOCAL_SOURCE_LEAK",
        expected_discriminating_result="Read /private/cache/recognizable-target.csv",
        expected_information_value=InformationValue.MEDIUM,
        priority=Priority.MEDIUM,
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
        hypothesis_under_test="eclipsing_binary",
        requested_experiment="harmonic_test",
        reason_code="COMPARE_ODD_EVEN",
        expected_discriminating_result="Compare a 1e-5 fractional signal in m/s units.",
        expected_information_value=InformationValue.MEDIUM,
        priority=Priority.MEDIUM,
        concise_reason="Ordinary scientific prose remains valid.",
    )

    assert_agent_safe_context(AgentContextPacket.model_validate(payload))
