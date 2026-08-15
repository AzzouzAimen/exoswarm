from __future__ import annotations

from collections import Counter
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from exoswarm.agents.context import AgentContextPacket
from exoswarm.agents.model_client import ScriptedInferenceClient
from exoswarm.config import Settings
from exoswarm.domain.enums import CriticVerdict, InformationValue, Priority, ToolStatus
from exoswarm.domain.models import (
    CriticDecision,
    Measurement,
    Provenance,
    ScientificToolResult,
    SkepticDecision,
)
from exoswarm.investigation.controller import InvestigationController
from exoswarm.investigation.mandatory import MANDATORY_TESTS
from exoswarm.investigation.runtime_inputs import CandidateSourceResolver
from exoswarm.investigation.tool_registry import ScientificToolRegistry
from exoswarm.science.contracts import ScientificToolSpec
from exoswarm.security.catalog_gate import CatalogGate
from exoswarm.security.result_lock import ResultLockService
from exoswarm.services.artifacts import FileSystemRunArtifactStore
from exoswarm.services.nasa_reveal import UnconfiguredCatalogRevealProvider


class NoParameters(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HarmonicParameters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trial_factor: int = Field(default=1, ge=1, le=2)


class DetrendParameters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    window_days: float = Field(default=1.5, gt=0.5, lt=3.0)


def fixture_result(
    *,
    tool_name: str,
    run_id: str,
    action_id: str,
    target_id: str,
    scenario: str,
    status: ToolStatus = ToolStatus.SUCCESS,
    parameters: dict[str, Any] | None = None,
    interpretation_code: str | None = None,
    suggested_alternatives: list[str] | None = None,
) -> ScientificToolResult:
    """Clearly labeled deterministic scientific fixture result; never production data."""

    measurements = {}
    if tool_name == "search_bls" and status == ToolStatus.SUCCESS:
        measurements = {
            "period": Measurement(value=3.2, unit="day", tolerance=0.02),
            "depth": Measurement(value=0.0012, unit="fraction", uncertainty=0.0001),
            "duration": Measurement(value=2.4, unit="hour", tolerance=0.2),
            "snr": Measurement(value=11.0, unit="dimensionless"),
        }
    diagnostics: dict[str, Any] = {"fixture_scenario": scenario}
    if interpretation_code:
        diagnostics["interpretation_code"] = interpretation_code
    return ScientificToolResult(
        tool_name=tool_name,
        status=status,
        run_id=run_id,
        action_id=action_id,
        target_id=target_id,
        measurements=measurements,
        diagnostics=diagnostics,
        method=f"test-fixture:{scenario}:{tool_name}",
        parameters=parameters or {},
        provenance=Provenance(
            code_version="test-fixture-v1",
            source_data_ref=f"fixture:curated-harness:{scenario}",
        ),
        suggested_alternatives=suggested_alternatives or [],
        reason=(f"fixture status {status}" if status != ToolStatus.SUCCESS else None),
    )


def interpretation_for(scenario: str) -> str:
    return {
        "clean": "CLEAN_PLANET_LIKE",
        "eclipsing_binary": "ODD_EVEN_MISMATCH",
        "contamination": "CONTAMINATION_LIKELY",
        "weak": "WEAK_NOISY",
    }[scenario]


def make_registry(
    scenario: str,
    *,
    calls: Counter[str] | None = None,
    adaptive_status: ToolStatus = ToolStatus.SUCCESS,
    adaptive_statuses: dict[str, ToolStatus] | None = None,
    adaptive_interpretations: dict[str, str | None] | None = None,
    adaptive_alternatives: dict[str, list[str]] | None = None,
    raise_tool: str | None = None,
    mismatch_tool: str | None = None,
    malformed_result_tool: str | None = None,
    adaptive_scope: frozenset[str] = frozenset({"science:execute"}),
) -> ScientificToolRegistry:
    counts = calls if calls is not None else Counter()

    def handler(
        run_id: str, action_id: str, target_id: str, parameters: dict[str, Any]
    ) -> ScientificToolResult:
        tool_name = parameters.pop("__tool_name")
        counts[tool_name] += 1
        if tool_name == raise_tool:
            raise RuntimeError("simulated fixture infrastructure failure")
        result_parameters = dict(parameters)
        if tool_name == malformed_result_tool:
            result_parameters["unexpected_result_parameter"] = True
        selected_status = (
            (adaptive_statuses or {}).get(tool_name, adaptive_status)
            if tool_name in ADAPTIVE_TOOLS
            else ToolStatus.SUCCESS
        )
        selected_interpretation = (
            (adaptive_interpretations or {}).get(
                tool_name, interpretation_for(scenario)
            )
            if tool_name in ADAPTIVE_TOOLS
            else None
        )
        return fixture_result(
            tool_name=tool_name,
            run_id=run_id,
            action_id=(f"{action_id}_mismatch" if tool_name == mismatch_tool else action_id),
            target_id=target_id,
            scenario=scenario,
            status=selected_status,
            parameters=result_parameters,
            interpretation_code=selected_interpretation,
            suggested_alternatives=(adaptive_alternatives or {}).get(tool_name),
        )

    def bound(tool_name: str):
        def invoke(
            run_id: str, action_id: str, target_id: str, parameters: dict[str, Any]
        ) -> ScientificToolResult:
            return handler(
                run_id,
                action_id,
                target_id,
                {"__tool_name": tool_name, **parameters},
            )

        return invoke

    specs = [
        ScientificToolSpec(
            name="search_bls",
            handler=bound("search_bls"),
            parameter_schema=NoParameters,
            mandatory_test="signal_quality",
            order=10,
        ),
        ScientificToolSpec(
            name="odd_even",
            handler=bound("odd_even"),
            parameter_schema=NoParameters,
            mandatory_test="odd_even",
            order=20,
        ),
        ScientificToolSpec(
            name="secondary_eclipse",
            handler=bound("secondary_eclipse"),
            parameter_schema=NoParameters,
            mandatory_test="secondary_eclipse",
            order=30,
        ),
        ScientificToolSpec(
            name="contamination_screening",
            handler=bound("contamination_screening"),
            parameter_schema=NoParameters,
            mandatory_test="contamination",
            order=40,
        ),
        ScientificToolSpec(
            name="harmonic_test",
            handler=bound("harmonic_test"),
            parameter_schema=HarmonicParameters,
            adaptive=True,
            cost_units=1,
            required_completed_tests=MANDATORY_TESTS,
            required_scopes=adaptive_scope,
            order=50,
        ),
        ScientificToolSpec(
            name="centroid_localization",
            handler=bound("centroid_localization"),
            parameter_schema=NoParameters,
            adaptive=True,
            cost_units=2,
            required_completed_tests=MANDATORY_TESTS,
            required_scopes=adaptive_scope,
            order=60,
        ),
        ScientificToolSpec(
            name="alternate_detrend",
            handler=bound("alternate_detrend"),
            parameter_schema=DetrendParameters,
            adaptive=True,
            cost_units=1,
            required_completed_tests=MANDATORY_TESTS,
            required_scopes=adaptive_scope,
            order=70,
        ),
    ]
    return ScientificToolRegistry(specs)


ADAPTIVE_TOOLS = frozenset(
    {"harmonic_test", "centroid_localization", "alternate_detrend"}
)


def make_controller(
    tmp_path,
    inference: ScriptedInferenceClient,
    registry: ScientificToolRegistry,
    *,
    granted_scopes: frozenset[str] = frozenset({"science:execute"}),
    candidate_sources: CandidateSourceResolver | None = None,
    **settings_overrides: Any,
) -> InvestigationController:
    settings = Settings(
        runs_dir=tmp_path / "runs",
        data_dir=tmp_path / "data",
        **settings_overrides,
    )
    artifacts = FileSystemRunArtifactStore(settings.runs_dir)
    return InvestigationController(
        settings,
        artifacts,
        ResultLockService(artifacts),
        CatalogGate(artifacts, UnconfiguredCatalogRevealProvider()),
        inference=inference,
        registry=registry,
        candidate_sources=candidate_sources,
        granted_scopes=granted_scopes,
    )


def seed_baseline(
    controller: InvestigationController, run_id: str, scenario: str
) -> None:
    target_id = controller.get(run_id).opaque_target_id
    code_tool = {
        "clean": "contamination_screening",
        "eclipsing_binary": "odd_even",
        "contamination": "contamination_screening",
        "weak": "search_bls",
    }[scenario]
    for index, tool_name in enumerate(
        ("search_bls", "odd_even", "secondary_eclipse", "contamination_screening"), 1
    ):
        controller.record_tool_result(
            run_id,
            fixture_result(
                tool_name=tool_name,
                run_id=run_id,
                action_id=f"fixture_{scenario}_{index}",
                target_id=target_id,
                scenario=scenario,
                interpretation_code=(
                    interpretation_for(scenario) if tool_name == code_tool else None
                ),
            ),
        )


def skeptic_policy(context: BaseModel, _schema: type[BaseModel]) -> SkepticDecision:
    packet = AgentContextPacket.model_validate(context)
    codes = {item.interpretation_code for item in packet.recent_evidence}
    if "CONTAMINATION_LIKELY" in codes:
        experiment = "harmonic_test"
        parameters = {"trial_factor": 1}
        hypothesis = "background_contamination"
    elif "WEAK_NOISY" in codes:
        experiment = "alternate_detrend"
        parameters = {"window_days": 1.5}
        hypothesis = "instrumental_or_variable_noise"
    else:
        experiment = "harmonic_test"
        parameters = {"trial_factor": 1}
        hypothesis = "eclipsing_binary"
    return SkepticDecision(
        decision_id=f"decision_{packet.step_id}",
        run_id=packet.run_id,
        step_id=packet.step_id,
        context_version=packet.context_version,
        hypothesis_under_test=hypothesis,
        requested_experiment=experiment,
        parameters=parameters,
        reason_code="FIXTURE_EVIDENCE_BRANCH",
        expected_discriminating_result="Use the deterministic fixture result to discriminate.",
        predicted_outcomes={"RESOLVED": "update from deterministic evidence"},
        expected_information_value=InformationValue.HIGH,
        priority=Priority.HIGH,
        budget_units_remaining=packet.remaining_budgets.adaptive_cost_units,
        cost_of_selected_experiment=packet.adaptive_experiment_costs[experiment],
        why_cost_is_justified="The selected fixture action targets the strongest alternative.",
        concise_reason="The compact fixture evidence selects this bounded experiment.",
    )


def critic_policy(context: BaseModel, _schema: type[BaseModel]) -> CriticDecision:
    packet = AgentContextPacket.model_validate(context)
    proposal = packet.proposed_decision
    assert proposal is not None
    codes = {item.interpretation_code for item in packet.recent_evidence}
    if "CLEAN_PLANET_LIKE" in codes:
        verdict = CriticVerdict.VETO
        revised_experiment = None
        revised_parameters = None
    elif "CONTAMINATION_LIKELY" in codes:
        verdict = CriticVerdict.REVISE
        revised_experiment = "centroid_localization"
        revised_parameters = {}
    else:
        verdict = CriticVerdict.APPROVE
        revised_experiment = None
        revised_parameters = None
    return CriticDecision(
        decision_id=f"critic_{packet.step_id}",
        run_id=packet.run_id,
        step_id=packet.step_id,
        context_version=packet.context_version,
        skeptic_decision_id=proposal.decision_id,
        verdict=verdict,
        reason_code=f"FIXTURE_{verdict}",
        concise_reason="Deterministic fixture review of bounded information value.",
        revised_experiment=revised_experiment,
        revised_parameters=revised_parameters,
    )


def policy_client() -> ScriptedInferenceClient:
    return ScriptedInferenceClient(
        {"skeptic": [skeptic_policy], "critic": [critic_policy]},
        model_identity="mock:evidence-aware-fixture-v1",
    )
