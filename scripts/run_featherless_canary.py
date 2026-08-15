from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import sys
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
    CriticDecision,
    InvestigationState,
    SkepticDecision,
)


def _proposal(state: InvestigationState) -> SkepticDecision:
    return SkepticDecision(
        decision_id="decision_canary",
        run_id=state.run_id,
        step_id="step_0001",
        context_version=state.context_version,
        hypothesis_under_test="bounded_canary_alternative",
        requested_experiment="harmonic_test",
        parameters={},
        reason_code="CANARY_PROPOSAL",
        expected_discriminating_result="Exercise the strict live response schema.",
        expected_information_value=InformationValue.MEDIUM,
        priority=Priority.MEDIUM,
        budget_units_remaining=state.adaptive_cost_units_remaining,
        cost_of_selected_experiment=1,
        why_cost_is_justified="The canary checks the bounded schema contract.",
        concise_reason="A safe fixed proposal for schema validation.",
    )


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
    state = InvestigationState(
        run_id="run_canary_safe",
        opaque_target_id="TARGET-CANARY",
        step_count=1,
    )
    proposal = _proposal(state)
    role_cases = (
        (
            "skeptic",
            assemble_context(
                state,
                available_experiments=("harmonic_test",),
                adaptive_experiment_costs={"harmonic_test": 1},
            ),
            SkepticDecision,
        ),
        (
            "critic",
            assemble_context(
                state,
                role="critic",
                available_experiments=("harmonic_test",),
                adaptive_experiment_costs={"harmonic_test": 1},
                proposed_decision=proposal,
            ),
            CriticDecision,
        ),
    )
    calls = []
    repairs = 0
    valid_decisions = 0
    for _ in range(repeats):
        for role, context, schema in role_cases:
            outcome = await client.decide_attempt(
                role=role,
                context=context,
                output_schema=schema,
                attempt_kind="primary",
            )
            calls.append(outcome.call)
            if outcome.call.schema_valid:
                valid_decisions += 1
                continue
            if outcome.call.status != "INVALID":
                continue
            repairs += 1
            repair = await client.decide_attempt(
                role=role,
                context=context,
                output_schema=schema,
                attempt_kind="repair",
                validation_error_code=outcome.call.validation_error_code,
            )
            calls.append(repair.call)
            if repair.call.schema_valid:
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
        "repairs": repairs,
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
