from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
API_SRC = ROOT / "apps" / "api" / "src"
if str(API_SRC) not in sys.path:
    sys.path.insert(0, str(API_SRC))

from exoswarm.agents.context import assemble_context
from exoswarm.agents.inference_provider import FeatherlessInferenceClient
from exoswarm.config import Settings
from exoswarm.domain.enums import InformationValue, Priority
from exoswarm.domain.models import (
    CandidateSignal,
    CriticDecision,
    InvestigationState,
    Measurement,
    SkepticDecision,
)


def _proposal(
    state: InvestigationState, *, experiment: str, cost: int
) -> SkepticDecision:
    return SkepticDecision(
        decision_id="decision_canary",
        run_id=state.run_id,
        step_id="step_0001",
        context_version=state.context_version,
        hypothesis_under_test="bounded_canary_alternative",
        requested_experiment=experiment,
        parameters={},
        reason_code="CANARY_PROPOSAL",
        expected_discriminating_result="Exercise the strict live response schema.",
        expected_information_value=InformationValue.MEDIUM,
        priority=Priority.MEDIUM,
        budget_units_remaining=state.adaptive_cost_units_remaining,
        cost_of_selected_experiment=cost,
        why_cost_is_justified="The canary checks the bounded schema contract.",
        concise_reason="A safe fixed proposal for schema validation.",
    )


def _canary_cases() -> tuple[tuple[InvestigationState, tuple[str, ...], dict[str, int]], ...]:
    cases = (
        ("clean", "eclipsing_binary", ("harmonic_test", "stop"), 11.2),
        ("odd_even", "eclipsing_binary", ("harmonic_test", "alternate_detrend", "stop"), 9.4),
        (
            "contamination",
            "background_contamination",
            ("alternate_aperture", "harmonic_test", "stop"),
            8.1,
        ),
        (
            "weak",
            "instrumental_or_variable_noise",
            ("alternate_detrend", "secondary_deep_search", "stop"),
            6.3,
        ),
        ("resolved", "none_material", ("stop",), 14.0),
    )
    costs = {
        "alternate_aperture": 1,
        "alternate_detrend": 1,
        "harmonic_test": 1,
        "secondary_deep_search": 1,
        "stop": 0,
    }
    built = []
    for index, (name, alternative, actions, snr) in enumerate(cases, 1):
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
            candidate_signals=[
                CandidateSignal(
                    candidate_id=f"candidate_{index}",
                    evidence_refs=[f"evidence_canary_{index}"],
                    measurements={
                        "period": Measurement(value=3.2 + index / 10, unit="day"),
                        "snr": Measurement(value=snr, unit="dimensionless"),
                    },
                )
            ],
        )
        built.append((state, actions, {action: costs[action] for action in actions}))
    return tuple(built)


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
        if decision.budget_units_remaining != context.remaining_budgets.adaptive_cost_units:
            return "BUDGET_DECLARATION_MISMATCH"
        option = options.get(decision.requested_experiment)
        if option is None or decision.cost_of_selected_experiment != option.deterministic_cost:
            return "COST_DECLARATION_MISMATCH"
        return validate_action(decision.requested_experiment, decision.parameters)

    assert isinstance(decision, CriticDecision)
    proposal = context.proposed_decision
    if proposal is None or decision.skeptic_decision_id != proposal.decision_id:
        return "PROPOSAL_ID_MISMATCH"
    if decision.verdict == "REVISE":
        return validate_action(
            decision.revised_experiment or "", decision.revised_parameters or {}
        )
    return None


async def run_canary(repeats: int) -> dict[str, Any]:
    if not os.environ.get("FEATHERLESS_API_KEY", "").strip():
        return {
            "schema_version": "1",
            "status": "SKIPPED",
            "reason": "FEATHERLESS_API_KEY is absent",
            "requested_repeats": repeats,
        }
    settings = Settings(_env_file=None)
    client = FeatherlessInferenceClient.from_settings(settings)
    calls = []
    repairs = 0
    valid_decisions = 0
    primary_semantic_valid = 0
    validation_failures: Counter[str] = Counter()
    cases = _canary_cases()
    exercised_states: set[str] = set()
    for index in range(repeats):
        state, actions, costs = cases[index % len(cases)]
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
                    available_experiments=actions,
                    adaptive_experiment_costs=costs,
                ),
                SkepticDecision,
            ),
            (
                "critic",
                assemble_context(
                    state,
                    role="critic",
                    available_experiments=actions,
                    adaptive_experiment_costs=costs,
                    proposed_decision=proposal,
                ),
                CriticDecision,
            ),
        )
        for role, context, schema in role_cases:
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
                continue
            if outcome.call.status not in {"INVALID", "OUTPUT_TRUNCATED"} and not semantic_error:
                continue
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

    primary = [item for item in calls if item.attempt_kind == "primary"]
    first_valid = sum(item.schema_valid for item in primary)
    latencies = [item.latency_ms for item in calls if item.latency_ms is not None]
    input_tokens = [
        item.input_tokens for item in calls if item.input_tokens is not None
    ]
    output_tokens = [
        item.output_tokens for item in calls if item.output_tokens is not None
    ]
    return {
        "schema_version": "1",
        "status": "COMPLETED",
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
        "acceptance": {
            "passed": bool(
                primary
                and primary_semantic_valid / len(primary) >= 0.9
                and valid_decisions == len(primary)
                and not any(
                    item.status in {"PROVIDER_ERROR", "TIMEOUT"} for item in calls
                )
            ),
            "minimum_first_attempt_valid_rate": 0.9,
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
