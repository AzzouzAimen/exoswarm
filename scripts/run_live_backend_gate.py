"""Run one real cached target through FastAPI, Featherless, lock, and reveal."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from exoswarm.agents.context import CONTEXT_SCHEMA_VERSION
from exoswarm.agents.prompt_registry import (
    PROMPT_REGISTRY,
    effective_output_token_limit,
)
from exoswarm.api.app import create_app
from exoswarm.config import Settings
from fastapi.testclient import TestClient

from evals.provenance import evaluation_provenance


def _require_success(response, operation: str) -> dict[str, Any]:
    if not response.is_success:
        raise RuntimeError(
            f"{operation} failed with HTTP {response.status_code}: {response.text}"
        )
    return response.json()


def _event_payloads(stream_text: str) -> list[dict[str, Any]]:
    return [
        json.loads(line.removeprefix("data: "))
        for line in stream_text.splitlines()
        if line.startswith("data: ")
    ]


def run_gate(*, target_id: str, timeout_seconds: float) -> dict[str, Any]:
    configured = Settings()
    if configured.featherless_api_key is None:
        raise RuntimeError("FEATHERLESS_API_KEY is required for the live backend gate")

    gate_started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="exoswarm-live-backend-") as temporary:
        settings = configured.model_copy(
            update={
                "data_dir": ROOT / "data",
                "runs_dir": Path(temporary) / "runs",
                "run_timeout_seconds": timeout_seconds,
            }
        )
        with TestClient(create_app(settings)) as client:
            created = _require_success(
                client.post(
                    "/api/investigations",
                    json={"opaque_target_id": target_id},
                    headers={"Idempotency-Key": f"live-backend-gate-{target_id}"},
                ),
                "create investigation",
            )
            run_id = created["run_id"]
            deadline = time.monotonic() + timeout_seconds
            while True:
                state = _require_success(
                    client.get(f"/api/investigations/{run_id}"),
                    "read investigation",
                )
                if not state["execution"]["active"]:
                    break
                if time.monotonic() >= deadline:
                    raise TimeoutError(
                        f"live backend gate exceeded {timeout_seconds:.0f} seconds"
                    )
                time.sleep(0.1)

            stream = client.get(f"/api/investigations/{run_id}/events")
            stream.raise_for_status()
            events = _event_payloads(stream.text)
            if state["status"] != "READY_TO_LOCK":
                attempts = [
                    event["payload"]
                    for event in events
                    if event["type"] == "inference.attempt"
                ]
                raise RuntimeError(
                    "live target did not reach READY_TO_LOCK: "
                    f"{state['status']} / {state.get('terminal_reason')}; "
                    f"sanitized_inference_attempts={json.dumps(attempts, sort_keys=True)}"
                )
            if state["model_call_count"] < 1:
                raise RuntimeError("live target did not exercise an actual model call")

            locked = _require_success(
                client.post(f"/api/investigations/{run_id}/lock"),
                "lock investigation",
            )
            artifacts = _require_success(
                client.get(f"/api/investigations/{run_id}/artifacts"),
                "list artifacts",
            )["artifacts"]
            revealed = _require_success(
                client.post(f"/api/investigations/{run_id}/reveal"),
                "reveal catalog comparison",
            )
            if revealed["locked_result_sha256"] != locked["sha256"]:
                raise RuntimeError("reveal does not reference the locked result hash")

            inference = state["inference_summary"]
            attempts = [
                {
                    key: event["payload"].get(key)
                    for key in (
                        "role",
                        "attempt_kind",
                        "status",
                        "schema_valid",
                        "validation_error_code",
                        "error_type",
                        "finish_reason",
                        "latency_ms",
                        "input_tokens",
                        "output_tokens",
                        "prompt_version",
                        "prompt_template_sha256",
                        "context_version",
                        "context_fingerprint",
                        "thinking_mode",
                        "thinking_requested",
                        "thinking_confirmed",
                    )
                }
                for event in events
                if event["type"] == "inference.attempt"
            ]
            agent_decisions = []
            for event in events:
                if event["type"] != "agent.decision":
                    continue
                payload = event["payload"]
                decision = payload["decision"]
                role = decision["role"]
                phase = payload.get("phase") or {
                    "skeptic": "decision",
                    "critic": "review",
                }.get(role)
                agent_decisions.append(
                    {
                        "role": role,
                        "phase": phase,
                        "provider": payload["provider"],
                        "model_identity": payload["model_identity"],
                        "fallback_used": payload["fallback_used"],
                        "context_version": payload["context_version"],
                        "decision": decision,
                    }
                )
            agent_starts = [
                {
                    key: event["payload"].get(key)
                    for key in (
                        "role",
                        "attempt_kind",
                        "context_version",
                        "evidence_count",
                        "advisory_roles",
                        "thinking_mode",
                        "thinking_requested",
                        "thinking_confirmed",
                    )
                }
                for event in events
                if event["type"] == "agent.started"
            ]
            checkpoints = state.get("role_checkpoints", [])
            checkpoint_pairs = {
                (item["role"], item["phase"])
                for item in checkpoints
                if item["status"] == "COMPLETE"
            }
            adaptive_branch_entered = bool(
                state["accepted_decisions"]
                or state["critic_decisions"]
                or any(item["adaptive"] for item in state["tool_executions"])
            )
            required_checkpoint_pairs = {("director", "final")}
            if adaptive_branch_entered:
                required_checkpoint_pairs.update(
                    {
                        ("observer", "briefing"),
                        ("signal", "briefing"),
                        ("transit_hunter", "briefing"),
                        ("director", "briefing"),
                        ("skeptic", "decision"),
                        ("critic", "review"),
                    }
                )
            phase_by_role_context = {
                (item["role"], item["context_version"]): item["phase"]
                for item in checkpoints
            }
            first_attempt_by_phase: dict[tuple[str, str], dict[str, Any]] = {}
            for attempt in attempts:
                phase = phase_by_role_context.get(
                    (attempt["role"], attempt["context_version"])
                )
                if phase is None:
                    continue
                first_attempt_by_phase.setdefault((attempt["role"], phase), attempt)
            successful_first_attempt_pairs = {
                pair
                for pair, attempt in first_attempt_by_phase.items()
                if attempt["attempt_kind"] == "primary"
                and attempt["status"] == "SUCCESS"
                and attempt["schema_valid"] is True
            }
            decision_pairs = {
                (item["role"], item["phase"])
                for item in agent_decisions
                if item["phase"] is not None
            }
            required_fields_by_role = {
                "observer": {"quality_flags", "observation_limitations"},
                "signal": {"leading_hypothesis", "alternative_hypothesis"},
                "transit_hunter": {"viability_code", "strongest_vetting_question"},
                "director": {"authorized_route", "focus_hypothesis", "mission_brief"},
                "skeptic": {"requested_experiment", "reason_code"},
                "critic": {"verdict", "reason_code"},
            }

            def _has_evidence_citation(item: dict[str, Any]) -> bool:
                decision = item["decision"]
                return any(
                    decision.get(field)
                    for field in (
                        "cited_evidence_refs",
                        "supporting_evidence_refs",
                        "contradicting_evidence_refs",
                    )
                )

            required_decisions = [
                item
                for item in agent_decisions
                if (item["role"], item["phase"]) in required_checkpoint_pairs
            ]
            role_outputs_auditable = (
                required_checkpoint_pairs.issubset(decision_pairs)
                and all(_has_evidence_citation(item) for item in required_decisions)
                and all(
                    required_fields_by_role[item["role"]].issubset(item["decision"])
                    for item in required_decisions
                )
            )
            skeptic_starts = [
                item for item in agent_starts if item["role"] == "skeptic"
            ]
            critic_starts = [item for item in agent_starts if item["role"] == "critic"]
            advisory_handoff_visible = (
                not adaptive_branch_entered
                or not settings.specialist_advisory_enabled
                or (
                    bool(skeptic_starts)
                    and {"director", "transit_hunter"}.issubset(
                        skeptic_starts[0]["advisory_roles"] or []
                    )
                    and all(not (item["advisory_roles"] or []) for item in critic_starts)
                )
            )
            skipped = [
                event["payload"] for event in events if event["type"] == "agent.skipped"
            ]
            checks = {
                "required_role_phases_complete": required_checkpoint_pairs.issubset(
                    checkpoint_pairs
                ),
                "required_role_phases_first_attempt_valid": (
                    required_checkpoint_pairs.issubset(successful_first_attempt_pairs)
                ),
                "role_outputs_auditable_and_grounded": role_outputs_auditable,
                "promoted_advisory_handoff_visible": advisory_handoff_visible,
                "no_role_skipped": not skipped,
                "first_attempt_schema_valid_at_least_90_percent": (
                    inference["first_attempt_schema_valid"]["rate"] != "not_applicable"
                    and inference["first_attempt_schema_valid"]["rate"] >= 0.9
                ),
                "no_provider_errors_or_timeouts": (
                    inference["provider_errors_timeouts"] == 0
                ),
                "raw_samples_zero": inference["raw_light_curve_samples_sent"] == 0,
                "reveal_hash_verified": True,
            }
            return {
                "schema_version": "2",
                "status": "PASS" if all(checks.values()) else "FAIL",
                "checks": checks,
                "branch_mode": (
                    "adaptive_multi_agent" if adaptive_branch_entered else "decisive_baseline"
                ),
                "required_role_phases": sorted(
                    f"{role}:{phase}" for role, phase in required_checkpoint_pairs
                ),
                "provenance": evaluation_provenance(
                    evaluation_id="live-backend-gate-v2",
                    configuration={
                        "inference_model": settings.model,
                        "context_schema_version": CONTEXT_SCHEMA_VERSION,
                        "configured_max_input_tokens": (
                            settings.inference_max_input_tokens
                        ),
                        "configured_max_output_tokens": (
                            settings.inference_max_output_tokens
                        ),
                        "specialist_advisory_enabled": (
                            settings.specialist_advisory_enabled
                        ),
                        "effective_role_max_output_tokens": {
                            role.value: effective_output_token_limit(
                                role,
                                configured_max_output_tokens=(
                                    settings.inference_max_output_tokens
                                ),
                                thinking_mode=settings.thinking_mode_for(role),
                            )
                            for role in PROMPT_REGISTRY
                        },
                        "role_thinking_modes": {
                            role.value: settings.thinking_mode_for(role).value
                            for role in PROMPT_REGISTRY
                        },
                        "target_id": target_id,
                        "timeout_seconds": timeout_seconds,
                    },
                ),
                "opaque_target_id": target_id,
                "run_status_before_lock": state["status"],
                "disposition": state["disposition"],
                "terminal_reason": state["terminal_reason"],
                "completed_tests": state["completed_tests"],
                "proposed_adaptive_actions": [
                    decision["requested_experiment"]
                    for decision in state["accepted_decisions"]
                    if decision["requested_experiment"] != "stop"
                ],
                "critic_verdicts": [
                    decision["verdict"] for decision in state["critic_decisions"]
                ],
                "adaptive_actions": [
                    execution["tool_name"]
                    for execution in state["tool_executions"]
                    if execution["adaptive"]
                    and execution["status"] == "COMPLETED"
                ],
                "model_calls": state["model_call_count"],
                "tool_calls": state["tool_call_count"],
                "inference": inference,
                "inference_attempts": attempts,
                "agent_decisions": agent_decisions,
                "agent_starts": agent_starts,
                "attempt_counts_by_role": dict(
                    sorted(Counter(item["role"] for item in attempts).items())
                ),
                "role_checkpoints": checkpoints,
                "skipped_roles": skipped,
                "event_count": len(events),
                "event_types": sorted({event["type"] for event in events}),
                "artifact_count": len(artifacts),
                "artifact_paths": sorted(item["relative_path"] for item in artifacts),
                "locked_sha256": locked["sha256"],
                "reveal_hash_verified": True,
                "catalog_source": revealed["catalog_source"],
                "elapsed_seconds": round(time.perf_counter() - gate_started, 3),
            }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", default="TARGET-P21")
    parser.add_argument("--timeout", type=float, default=300.0)
    parser.add_argument(
        "--report",
        type=Path,
        default=ROOT / "evals/live_backend_gate.json",
    )
    args = parser.parse_args()
    report = run_gate(target_id=args.target, timeout_seconds=args.timeout)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    if report["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
