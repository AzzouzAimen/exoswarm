from __future__ import annotations

import argparse
import asyncio
import json
import re
import statistics
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
API_SRC = ROOT / "apps" / "api" / "src"
for import_root in (ROOT, API_SRC):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from exoswarm.agents.context import CONTEXT_SCHEMA_VERSION, assemble_context
from exoswarm.agents.inference_provider import FeatherlessInferenceClient
from exoswarm.agents.prompt_registry import effective_output_token_limit
from exoswarm.config import Settings
from exoswarm.domain.enums import InformationValue, Priority, ToolStatus
from exoswarm.domain.models import (
    CandidateSignal,
    CriticDecision,
    EvidenceRecord,
    InvestigationState,
    Measurement,
    Provenance,
    ScientificToolResult,
    SkepticDecision,
)

from evals.provenance import evaluation_provenance


@dataclass(frozen=True, slots=True)
class CanaryCase:
    name: str
    state: InvestigationState
    evidence: tuple[EvidenceRecord, ...]
    actions: tuple[str, ...]
    costs: dict[str, int]
    acceptable_actions: frozenset[str]


_NUMERIC_CLAIM = re.compile(r"(?<![A-Za-z_])[-+]?\d+(?:\.\d+)?")


def _runtime_configuration(settings: Settings, repeats: int) -> dict[str, Any]:
    return {
        "inference_model": settings.model,
        "context_schema_version": CONTEXT_SCHEMA_VERSION,
        "configured_max_input_tokens": settings.inference_max_input_tokens,
        "configured_max_output_tokens": settings.inference_max_output_tokens,
        "effective_role_max_output_tokens": {
            role: effective_output_token_limit(
                role,
                configured_max_output_tokens=settings.inference_max_output_tokens,
                thinking_mode=settings.thinking_mode_for(role),
            )
            for role in ("skeptic", "critic")
        },
        "role_thinking_modes": {
            role: settings.thinking_mode_for(role).value
            for role in ("skeptic", "critic")
        },
        "requested_repeats": repeats,
    }


def _proposal(
    state: InvestigationState, *, experiment: str, cost: int
) -> SkepticDecision:
    experiment_claims = {
        "alternate_aperture": (
            "Test whether the candidate depth is stable under a different aperture.",
            "A depth shift would discriminate contamination from an on-target signal.",
        ),
        "alternate_detrend": (
            "Test whether the candidate persists under an alternate detrending window.",
            "Signal instability would support an instrumental or variable-noise explanation.",
        ),
        "harmonic_test": (
            "Test the candidate at the half, candidate, and double-period aliases.",
            "A preferred harmonic would discriminate an eclipsing-binary interpretation.",
        ),
        "secondary_deep_search": (
            "Search more deeply for secondary-like structure at the candidate period.",
            "Secondary structure would weaken the planetary interpretation.",
        ),
        "stop": (
            "Stop because the supplied evidence has no material unresolved alternative.",
            "No additional bounded experiment is expected to change the disposition.",
        ),
    }
    objective, discriminating_result = experiment_claims[experiment]
    return SkepticDecision(
        decision_id="decision_canary",
        run_id=state.run_id,
        step_id="step_0001",
        context_version=state.context_version,
        hypothesis_under_test=(
            state.strongest_unresolved_alternative or "residual_false_positive"
        ),
        requested_experiment=experiment,
        parameters={},
        reason_code="CANARY_RELEVANT_PROPOSAL",
        expected_discriminating_result=discriminating_result,
        expected_information_value=InformationValue.MEDIUM,
        priority=Priority.MEDIUM,
        budget_units_remaining=state.adaptive_cost_units_remaining,
        cost_of_selected_experiment=cost,
        why_cost_is_justified=(
            "The action directly tests the strongest unresolved alternative at the declared cost."
            if cost
            else "Stopping consumes no experiment budget because no material alternative remains."
        ),
        concise_reason=objective,
        supporting_evidence_refs=list(state.candidate_signals[0].evidence_refs[-1:]),
        contradicting_evidence_refs=[],
    )


def _canary_cases() -> tuple[CanaryCase, ...]:
    cases = (
        (
            "clean",
            "eclipsing_binary",
            ("harmonic_test", "stop"),
            11.2,
            frozenset({"harmonic_test"}),
        ),
        (
            "odd_even",
            "eclipsing_binary",
            ("harmonic_test", "alternate_detrend", "stop"),
            9.4,
            frozenset({"harmonic_test"}),
        ),
        (
            "contamination",
            "background_contamination",
            ("alternate_aperture", "harmonic_test", "stop"),
            8.1,
            frozenset({"alternate_aperture"}),
        ),
        (
            "weak",
            "instrumental_or_variable_noise",
            ("alternate_detrend", "secondary_deep_search", "stop"),
            6.3,
            frozenset({"alternate_detrend"}),
        ),
        (
            "resolved",
            "none_material",
            ("stop",),
            14.0,
            frozenset({"stop"}),
        ),
    )
    costs = {
        "alternate_aperture": 1,
        "alternate_detrend": 1,
        "harmonic_test": 1,
        "secondary_deep_search": 1,
        "stop": 0,
    }
    built = []
    for index, (name, alternative, actions, snr, acceptable_actions) in enumerate(
        cases, 1
    ):
        evidence_id = f"evidence_canary_{index}"
        measurements = {
            "period": Measurement(
                value=3.2 + index / 10,
                unit="day",
                evidence_ref=evidence_id,
            ),
            "snr": Measurement(
                value=snr,
                unit="dimensionless",
                evidence_ref=evidence_id,
            ),
        }
        state = InvestigationState(
            run_id=f"run_canary_{name}",
            opaque_target_id=f"TARGET-CANARY-{index}",
            status="SELECTING_ADAPTIVE_EXPERIMENT",
            step_count=1,
            completed_tests=[
                "signal_quality",
                "odd_even",
                "secondary_eclipse",
                "contamination",
            ],
            active_hypotheses=["planetary", alternative],
            strongest_unresolved_alternative=alternative,
            evidence_refs=[evidence_id],
            candidate_signals=[
                CandidateSignal(
                    candidate_id=f"candidate_{index}",
                    evidence_refs=[evidence_id],
                    measurements=measurements,
                )
            ],
        )
        result = ScientificToolResult(
            tool_name="search_bls",
            status=ToolStatus.SUCCESS,
            run_id=state.run_id,
            action_id=f"action_canary_{index}",
            target_id=state.opaque_target_id,
            measurements=measurements,
            diagnostics={"canary_case": name},
            method="curated canary evidence fixture",
            provenance=Provenance(
                code_version="canary-fixture-v1",
                source_data_ref=f"fixture:canary:{name}",
            ),
        )
        evidence = EvidenceRecord(
            evidence_id=evidence_id,
            run_id=state.run_id,
            step_id="step_0001",
            action_id=result.action_id,
            opaque_target_id=state.opaque_target_id,
            tool_name=result.tool_name,
            tool_status=result.status,
            result=result,
        )
        built.append(
            CanaryCase(
                name=name,
                state=state,
                evidence=(evidence,),
                actions=actions,
                costs={action: costs[action] for action in actions},
                acceptable_actions=acceptable_actions,
            )
        )
    return tuple(built)


def _decision_quality_result(
    *,
    case: CanaryCase,
    role: str,
    decision: SkepticDecision | CriticDecision | None,
    proposal: SkepticDecision,
) -> dict[str, Any]:
    selected_action: str | None = None
    verdict: str | None = None
    if isinstance(decision, SkepticDecision):
        selected_action = decision.requested_experiment
    elif isinstance(decision, CriticDecision):
        verdict = str(decision.verdict)
        if decision.verdict == "APPROVE":
            selected_action = proposal.requested_experiment
        elif decision.verdict == "REVISE":
            selected_action = decision.revised_experiment
        else:
            selected_action = "stop"
    return {
        "case": case.name,
        "role": role,
        "selected_action": selected_action,
        "verdict": verdict,
        "acceptable_actions": sorted(case.acceptable_actions),
        "passed": selected_action in case.acceptable_actions,
    }


def _parameters_match_contract(parameters: dict[str, Any], contract: dict[str, Any]) -> bool:
    properties = contract.get("properties", {})
    if not isinstance(properties, dict):
        return False
    required = contract.get("required", [])
    if not isinstance(required, list) or any(name not in parameters for name in required):
        return False
    if contract.get("additionalProperties") is False and set(parameters) - set(properties):
        return False
    for name, value in parameters.items():
        field = properties.get(name)
        if not isinstance(field, dict):
            continue
        expected = field.get("type")
        if expected == "integer" and (isinstance(value, bool) or not isinstance(value, int)):
            return False
        if expected == "number" and (
            isinstance(value, bool) or not isinstance(value, (int, float))
        ):
            return False
        if expected == "string" and not isinstance(value, str):
            return False
        if "minimum" in field and value < field["minimum"]:
            return False
        if "maximum" in field and value > field["maximum"]:
            return False
        if "exclusiveMinimum" in field and value <= field["exclusiveMinimum"]:
            return False
        if "exclusiveMaximum" in field and value >= field["exclusiveMaximum"]:
            return False
        if "enum" in field and value not in field["enum"]:
            return False
    return True


def _semantic_error(
    role: str,
    decision: SkepticDecision | CriticDecision,
    context: Any,
) -> str | None:
    if decision.run_id != context.run_id:
        return "RUN_ID_MISMATCH"
    if decision.step_id != context.step_id:
        return "STEP_ID_MISMATCH"
    if decision.context_version != context.context_version:
        return "CONTEXT_VERSION_MISMATCH"
    cited = {
        str(item)
        for field in (
            "supporting_evidence_refs",
            "contradicting_evidence_refs",
        )
        for item in getattr(decision, field, ())
    }
    visible = set(context.evidence_refs)
    if visible and not cited:
        return "CITATION_REQUIRED"
    if not cited.issubset(visible):
        return "CITATION_OUT_OF_CONTEXT"
    options = {item.action_name: item for item in context.available_experiments}

    def validate_action(action: str, parameters: dict[str, Any]) -> str | None:
        option = options.get(action)
        if option is None or option.availability_reason is not None:
            return "UNAVAILABLE_ACTION"
        if not _parameters_match_contract(parameters, option.parameter_contract):
            return "MALFORMED_PARAMETERS"
        return None

    if role == "skeptic":
        assert isinstance(decision, SkepticDecision)
        narratives = (
            decision.hypothesis_under_test,
            decision.expected_discriminating_result,
            *decision.predicted_outcomes.values(),
            *(value for value in (decision.stop_if,) if value is not None),
            decision.why_cost_is_justified,
            decision.concise_reason,
        )
        if any(_NUMERIC_CLAIM.search(value) for value in narratives):
            return "NUMERIC_NARRATIVE_UNSUPPORTED"
        if decision.budget_units_remaining != context.remaining_budgets.adaptive_cost_units:
            return "BUDGET_DECLARATION_MISMATCH"
        option = options.get(decision.requested_experiment)
        if option is None or decision.cost_of_selected_experiment != option.deterministic_cost:
            return "COST_DECLARATION_MISMATCH"
        return validate_action(decision.requested_experiment, decision.parameters)

    assert isinstance(decision, CriticDecision)
    if _NUMERIC_CLAIM.search(decision.concise_reason):
        return "NUMERIC_NARRATIVE_UNSUPPORTED"
    proposal = context.proposed_decision
    if proposal is None or decision.skeptic_decision_id != proposal.decision_id:
        return "PROPOSAL_ID_MISMATCH"
    if decision.verdict == "REVISE":
        return validate_action(
            decision.revised_experiment or "", decision.revised_parameters or {}
        )
    return None


async def run_canary(
    repeats: int, *, settings: Settings | None = None
) -> dict[str, Any]:
    settings = settings or Settings()
    if settings.featherless_api_key is None:
        return {
            "schema_version": "2",
            "status": "SKIPPED",
            "reason": "FEATHERLESS_API_KEY is absent",
            "requested_repeats": repeats,
            "provenance": evaluation_provenance(
                evaluation_id="featherless-canary-v2",
                configuration=_runtime_configuration(settings, repeats),
            ),
        }
    client = FeatherlessInferenceClient.from_settings(settings)
    calls = []
    repairs = 0
    valid_decisions = 0
    primary_semantic_valid = 0
    validation_failures: Counter[str] = Counter()
    quality_results: list[dict[str, Any]] = []
    cases = _canary_cases()
    exercised_states: set[str] = set()
    for index in range(repeats):
        case = cases[index % len(cases)]
        state, actions, costs = case.state, case.actions, case.costs
        exercised_states.add(state.run_id)
        proposal_action = next((action for action in actions if action != "stop"), "stop")
        proposal = _proposal(
            state,
            experiment=proposal_action,
            cost=costs[proposal_action],
        )
        role_cases = (
            (
                "skeptic",
                assemble_context(
                    state,
                    case.evidence,
                    available_experiments=actions,
                    adaptive_experiment_costs=costs,
                ),
                SkepticDecision,
            ),
            (
                "critic",
                assemble_context(
                    state,
                    case.evidence,
                    role="critic",
                    available_experiments=actions,
                    adaptive_experiment_costs=costs,
                    proposed_decision=proposal,
                ),
                CriticDecision,
            ),
        )
        for role, context, schema in role_cases:
            final_decision: SkepticDecision | CriticDecision | None = None
            outcome = await client.decide_attempt(
                role=role,
                context=context,
                output_schema=schema,
                attempt_kind="primary",
            )
            calls.append(outcome.call)
            semantic_error = (
                _semantic_error(role, outcome.decision, context)
                if outcome.decision is not None
                else None
            )
            if semantic_error:
                validation_failures[f"primary:{role}:{semantic_error}"] += 1
            elif not outcome.call.schema_valid:
                validation_failures[
                    f"primary:{role}:"
                    f"{outcome.call.error_type or outcome.call.validation_error_code or outcome.call.status}"
                ] += 1
            if outcome.call.schema_valid and semantic_error is None:
                primary_semantic_valid += 1
                valid_decisions += 1
                final_decision = outcome.decision
            elif outcome.call.status in {"INVALID", "OUTPUT_TRUNCATED"} or semantic_error:
                repairs += 1
                repair = await client.decide_attempt(
                    role=role,
                    context=context,
                    output_schema=schema,
                    attempt_kind="repair",
                    validation_error_code=(
                        semantic_error or outcome.call.validation_error_code
                    ),
                )
                calls.append(repair.call)
                repair_semantic_error = (
                    _semantic_error(role, repair.decision, context)
                    if repair.decision is not None
                    else None
                )
                if repair_semantic_error:
                    validation_failures[f"repair:{role}:{repair_semantic_error}"] += 1
                elif not repair.call.schema_valid:
                    validation_failures[
                        f"repair:{role}:"
                        f"{repair.call.error_type or repair.call.validation_error_code or repair.call.status}"
                    ] += 1
                if repair.call.schema_valid and repair_semantic_error is None:
                    valid_decisions += 1
                    final_decision = repair.decision
            quality_results.append(
                _decision_quality_result(
                    case=case,
                    role=role,
                    decision=final_decision,
                    proposal=proposal,
                )
            )

    primary = [item for item in calls if item.attempt_kind == "primary"]
    first_valid = sum(item.schema_valid for item in primary)
    latencies = [item.latency_ms for item in calls if item.latency_ms is not None]
    input_tokens = [
        item.input_tokens for item in calls if item.input_tokens is not None
    ]
    output_tokens = [
        item.output_tokens for item in calls if item.output_tokens is not None
    ]
    quality_passes = sum(item["passed"] for item in quality_results)
    selected_branches = {
        item["selected_action"]
        for item in quality_results
        if item["selected_action"] is not None
    }
    return {
        "schema_version": "2",
        "status": "COMPLETED",
        "provenance": evaluation_provenance(
            evaluation_id="featherless-canary-v2",
            configuration=_runtime_configuration(settings, repeats),
        ),
        "model_identities": sorted({item.model_identity for item in calls}),
        "requested_repeats": repeats,
        "decisions": len(primary),
        "attempts": len(calls),
        "varied_evidence_states": len(exercised_states),
        "first_attempt_schema_valid": {
            "numerator": first_valid,
            "denominator": len(primary),
            "rate": first_valid / len(primary) if primary else "not_applicable",
        },
        "schema_valid_after_repair_policy": {
            "numerator": valid_decisions,
            "denominator": len(primary),
            "rate": valid_decisions / len(primary) if primary else "not_applicable",
        },
        "first_attempt_semantic_valid": {
            "numerator": primary_semantic_valid,
            "denominator": len(primary),
            "rate": primary_semantic_valid / len(primary) if primary else "not_applicable",
        },
        "repairs": repairs,
        "validation_failures": dict(sorted(validation_failures.items())),
        "finish_reasons": dict(
            sorted(Counter(item.finish_reason or "not_reported" for item in calls).items())
        ),
        "provider_errors_timeouts": sum(
            item.status in {"PROVIDER_ERROR", "TIMEOUT"} for item in calls
        ),
        "usage": {
            "input_tokens": sum(input_tokens)
            if len(input_tokens) == len(calls)
            else "not_measured",
            "output_tokens": (
                sum(output_tokens)
                if len(output_tokens) == len(calls)
                else "not_measured"
            ),
        },
        "latency_ms": {
            "median": statistics.median(latencies)
            if len(latencies) == len(calls)
            else "not_measured",
            "maximum": max(latencies)
            if len(latencies) == len(calls)
            else "not_measured",
        },
        "raw_light_curve_samples_sent": 0,
        "decision_quality": {
            "numerator": quality_passes,
            "denominator": len(quality_results),
            "rate": quality_passes / len(quality_results)
            if quality_results
            else "not_applicable",
            "branch_count": len(selected_branches),
            "results": quality_results,
        },
        "acceptance": {
            "passed": bool(
                primary
                and primary_semantic_valid / len(primary) >= 0.9
                and valid_decisions == len(primary)
                and quality_passes / len(quality_results) >= 0.8
                and len(selected_branches) >= 3
                and not any(
                    item.status in {"PROVIDER_ERROR", "TIMEOUT"} for item in calls
                )
            ),
            "minimum_first_attempt_valid_rate": 0.9,
            "minimum_decision_quality_rate": 0.8,
            "minimum_branch_count": 3,
            "semantic_identity_action_parameters_budget_validated": True,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the opt-in Featherless schema canary."
    )
    parser.add_argument("--repeats", type=int, default=10)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("--repeats must be at least 1")
    report = asyncio.run(run_canary(args.repeats))
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if report["status"] == "SKIPPED" or report["acceptance"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
