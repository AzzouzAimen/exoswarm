from __future__ import annotations

import asyncio
import hashlib
import json
import re
import tempfile
import time
from collections import Counter
from dataclasses import replace
from pathlib import Path
from typing import Any

from exoswarm.agents.context import AgentContextPacket
from exoswarm.agents.model_client import ScriptedInferenceClient
from exoswarm.config import Settings
from exoswarm.domain.enums import (
    CriticVerdict,
    InformationValue,
    InvestigationStatus,
    LockState,
    Priority,
    ToolExecutionStatus,
    ToolStatus,
)
from exoswarm.domain.errors import ModelProviderTimeoutError
from exoswarm.domain.models import (
    CriticDecision,
    EvidenceRecord,
    Measurement,
    Provenance,
    ScientificToolResult,
    SkepticDecision,
    ToolExecutionRecord,
)
from exoswarm.investigation.controller import InvestigationController
from exoswarm.investigation.mandatory import MANDATORY_TESTS
from exoswarm.investigation.runner import InvestigationRunService
from exoswarm.investigation.tool_registry import ScientificToolRegistry
from exoswarm.science.contracts import ScientificToolSpec
from exoswarm.security.catalog_gate import CatalogGate
from exoswarm.security.result_lock import ResultLockService
from exoswarm.services.artifacts import FileSystemRunArtifactStore
from exoswarm.services.nasa_reveal import UnconfiguredCatalogRevealProvider
from exoswarm.services.target_registry import TargetRegistry
from pydantic import BaseModel, ConfigDict, Field

SUITE_ROOT = Path(__file__).resolve().parent / "harness" / "v1"
_DYNAMIC_REFERENCE = re.compile(
    r"(?:run|action|evidence|evt)_[0-9a-f]{8,}|mock_call_(?:skeptic|critic)_\d+"
)


class _NoParameters(BaseModel):
    model_config = ConfigDict(extra="forbid")


class _HarmonicParameters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trial_factor: int = Field(default=1, ge=1, le=2)


class _DetrendParameters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    window_days: float = Field(default=1.5, gt=0.5, lt=3.0)


class RecordingScriptedClient(ScriptedInferenceClient):
    """The production scripted boundary plus safe, normalized context measurements."""

    def __init__(self, responses: dict[str, list[Any]], *, model_identity: str) -> None:
        super().__init__(responses, model_identity=model_identity)
        self.contexts: list[dict[str, Any]] = []

    async def decide_attempt(self, **kwargs: Any):
        packet = AgentContextPacket.model_validate(kwargs["context"])
        payload = packet.model_dump(mode="json")
        payload["context_fingerprint"] = "<production-fingerprint>"
        canonical = json.dumps(payload, separators=(",", ":"), sort_keys=True)
        normalized = _DYNAMIC_REFERENCE.sub("<dynamic-ref>", canonical)
        self.contexts.append(
            {
                "role": kwargs["role"],
                "attempt_kind": kwargs["attempt_kind"],
                "bytes": packet.serialized_size_bytes,
                "fingerprint": hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
                "production_fingerprint_valid": bool(
                    re.fullmatch(r"[0-9a-f]{64}", packet.context_fingerprint)
                ),
                "recent_evidence": len(packet.recent_evidence),
            }
        )
        return await super().decide_attempt(**kwargs)


def _load_locked() -> tuple[dict[str, Any], dict[str, Any]]:
    lock = json.loads((SUITE_ROOT / "lock.json").read_text(encoding="utf-8"))
    for name, expected_digest in lock["files"].items():
        actual_digest = hashlib.sha256((SUITE_ROOT / name).read_bytes()).hexdigest()
        if actual_digest != expected_digest:
            raise ValueError(f"locked evaluation file digest differs: {name}")
    scenarios = json.loads((SUITE_ROOT / "scenarios.json").read_text(encoding="utf-8"))
    acceptance = json.loads(
        (SUITE_ROOT / "acceptance.json").read_text(encoding="utf-8")
    )
    if scenarios["schema_version"] != "1" or acceptance["schema_version"] != "1":
        raise ValueError("unsupported harness evaluation schema version")
    if scenarios["suite_id"] != acceptance["suite_id"]:
        raise ValueError("scenario and acceptance suite identifiers do not match")
    if scenarios["suite_id"] != lock["suite_id"]:
        raise ValueError("locked manifest suite identifier does not match")
    scenario_ids = [item["id"] for item in scenarios["cases"]]
    if len(scenario_ids) != len(set(scenario_ids)):
        raise ValueError("locked scenario identifiers must be unique")
    if set(scenario_ids) != set(acceptance["cases"]):
        raise ValueError(
            "every locked scenario must have separate acceptance assertions"
        )
    return scenarios, acceptance


def _fixture_result(
    tool_name: str,
    run_id: str,
    action_id: str,
    target_id: str,
    profile: str,
    *,
    parameters: dict[str, Any] | None = None,
    interpretation_code: str | None = None,
) -> ScientificToolResult:
    measurements: dict[str, Measurement] = {}
    if tool_name == "search_bls":
        measurements = {
            "period": Measurement(value=3.2, unit="day", tolerance=0.02),
            "depth": Measurement(value=0.0012, unit="fraction", uncertainty=0.0001),
            "duration": Measurement(value=2.4, unit="hour", tolerance=0.2),
            "snr": Measurement(value=11.0, unit="dimensionless"),
        }
    diagnostics: dict[str, Any] = {"fixture_profile": profile}
    if interpretation_code:
        diagnostics["interpretation_code"] = interpretation_code
    return ScientificToolResult(
        tool_name=tool_name,
        status=ToolStatus.SUCCESS,
        run_id=run_id,
        action_id=action_id,
        target_id=target_id,
        measurements=measurements,
        diagnostics=diagnostics,
        method=f"eval-fixture-v1:{profile}:{tool_name}",
        parameters=parameters or {},
        provenance=Provenance(
            code_version="eval-fixture-v1",
            source_data_ref=f"fixture:harness-v1:{profile}",
        ),
    )


def _profile_code(profile: str) -> str:
    return {
        "clean": "CLEAN_PLANET_LIKE",
        "eclipsing_binary": "ODD_EVEN_MISMATCH",
        "contamination": "CONTAMINATION_LIKELY",
        "weak": "WEAK_NOISY",
    }[profile]


def _registry(
    profile: str,
    calls: Counter[str],
    *,
    failure_tool: str | None = None,
    timeout_tool: str | None = None,
) -> ScientificToolRegistry:
    adaptive = {"harmonic_test", "centroid_localization", "alternate_detrend"}
    code_tool = {
        "clean": "contamination_screening",
        "eclipsing_binary": "odd_even",
        "contamination": "contamination_screening",
        "weak": "search_bls",
    }[profile]

    def bound(tool_name: str):
        def invoke(
            run_id: str, action_id: str, target_id: str, parameters: dict[str, Any]
        ) -> ScientificToolResult:
            calls[tool_name] += 1
            if tool_name == failure_tool:
                raise RuntimeError("injected deterministic tool failure")
            if tool_name == timeout_tool:
                time.sleep(0.1)
            return _fixture_result(
                tool_name,
                run_id,
                action_id,
                target_id,
                profile,
                parameters=dict(parameters),
                interpretation_code=(
                    _profile_code(profile)
                    if tool_name == code_tool or tool_name in adaptive
                    else None
                ),
            )

        return invoke

    specs = [
        ScientificToolSpec(
            name="search_bls",
            handler=bound("search_bls"),
            parameter_schema=_NoParameters,
            mandatory_test="signal_quality",
            order=10,
        ),
        ScientificToolSpec(
            name="odd_even",
            handler=bound("odd_even"),
            parameter_schema=_NoParameters,
            mandatory_test="odd_even",
            order=20,
        ),
        ScientificToolSpec(
            name="secondary_eclipse",
            handler=bound("secondary_eclipse"),
            parameter_schema=_NoParameters,
            mandatory_test="secondary_eclipse",
            order=30,
        ),
        ScientificToolSpec(
            name="contamination_screening",
            handler=bound("contamination_screening"),
            parameter_schema=_NoParameters,
            mandatory_test="contamination",
            order=40,
        ),
        ScientificToolSpec(
            name="harmonic_test",
            handler=bound("harmonic_test"),
            parameter_schema=_HarmonicParameters,
            adaptive=True,
            cost_units=1,
            required_completed_tests=MANDATORY_TESTS,
            required_scopes=frozenset({"science:execute"}),
            order=50,
        ),
        ScientificToolSpec(
            name="centroid_localization",
            handler=bound("centroid_localization"),
            parameter_schema=_NoParameters,
            adaptive=True,
            cost_units=2,
            required_completed_tests=MANDATORY_TESTS,
            required_scopes=frozenset({"science:execute"}),
            order=60,
        ),
        ScientificToolSpec(
            name="alternate_detrend",
            handler=bound("alternate_detrend"),
            parameter_schema=_DetrendParameters,
            adaptive=True,
            cost_units=1,
            required_completed_tests=MANDATORY_TESTS,
            required_scopes=frozenset({"science:execute"}),
            order=70,
        ),
    ]
    return ScientificToolRegistry(specs)


def _skeptic(action: str, *, stale: bool = False):
    def decide(context: BaseModel, _schema: type[BaseModel]) -> SkepticDecision:
        packet = AgentContextPacket.model_validate(context)
        parameters: dict[str, Any] = {}
        if action == "harmonic_test":
            parameters = {"trial_factor": 1}
        elif action == "alternate_detrend":
            parameters = {"window_days": 1.5}
        return SkepticDecision(
            decision_id=f"decision_{packet.step_id}",
            run_id=packet.run_id,
            step_id="step_0000" if stale else packet.step_id,
            context_version=packet.context_version,
            hypothesis_under_test="bounded_eval_alternative",
            requested_experiment=action,
            parameters=parameters,
            reason_code="LOCKED_EVAL_SELECTION",
            expected_discriminating_result="Use deterministic evidence to test the alternative.",
            predicted_outcomes={"RESOLVED": "update only from tool evidence"},
            expected_information_value=InformationValue.HIGH,
            priority=Priority.HIGH,
            budget_units_remaining=packet.remaining_budgets.adaptive_cost_units,
            cost_of_selected_experiment=packet.adaptive_experiment_costs[action],
            why_cost_is_justified="The action targets the unresolved alternative.",
            concise_reason="The locked scenario selects one bounded experiment.",
        )

    return decide


def _critic(verdict: str, revised_action: str | None = None):
    def decide(context: BaseModel, _schema: type[BaseModel]) -> CriticDecision:
        packet = AgentContextPacket.model_validate(context)
        proposal = packet.proposed_decision
        assert proposal is not None
        revised_parameters: dict[str, Any] | None = None
        if revised_action == "harmonic_test":
            revised_parameters = {"trial_factor": 1}
        elif revised_action == "alternate_detrend":
            revised_parameters = {"window_days": 1.5}
        elif revised_action:
            revised_parameters = {}
        return CriticDecision(
            decision_id=f"critic_{packet.step_id}",
            run_id=packet.run_id,
            step_id=packet.step_id,
            context_version=packet.context_version,
            skeptic_decision_id=proposal.decision_id,
            verdict=CriticVerdict(verdict),
            reason_code=f"LOCKED_EVAL_{verdict}",
            concise_reason="The locked Critic fixture checks the bounded proposal.",
            revised_experiment=revised_action,
            revised_parameters=revised_parameters,
        )

    return decide


def _responses(
    case: dict[str, Any],
) -> tuple[RecordingScriptedClient, RecordingScriptedClient]:
    action = case.get("skeptic_action", "harmonic_test")
    sequence = case.get("skeptic_sequence", ["valid"])
    skeptic_responses: list[Any] = []
    for item in sequence:
        if item == "valid":
            skeptic_responses.append(_skeptic(action))
        elif item == "malformed":
            skeptic_responses.append({"valid_json": "scientifically unusable"})
        elif item == "stale":
            skeptic_responses.append(_skeptic(action, stale=True))
        elif item == "timeout":
            skeptic_responses.append(
                ModelProviderTimeoutError("injected provider timeout")
            )
        else:
            raise ValueError(f"unknown scripted response kind: {item}")
    primary = RecordingScriptedClient(
        {
            "skeptic": skeptic_responses,
            "critic": [
                _critic(case.get("critic", "APPROVE"), case.get("revised_action"))
            ],
        },
        model_identity="mock:locked-harness-v1",
    )
    fallback = RecordingScriptedClient(
        {
            "skeptic": [_skeptic(action)],
            "critic": [
                _critic(case.get("critic", "APPROVE"), case.get("revised_action"))
            ],
        },
        model_identity="mock:explicit-fallback-v1",
    )
    return primary, fallback


def _target_registry(base: Path) -> TargetRegistry:
    data_dir = base / "data"
    source = data_dir / "cached" / "eval-source.bin"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"locked-eval-source")
    manifest = data_dir / "targets" / "source_manifest.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        json.dumps(
            {
                "schema_version": "1",
                "targets": [
                    {
                        "opaque_target_id": "TARGET-EVAL",
                        "cached_lightcurve_path": "cached/eval-source.bin",
                        "cached_tpf_path": None,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return TargetRegistry(manifest, data_dir=data_dir)


def _controller(
    base: Path,
    case: dict[str, Any],
    registry: ScientificToolRegistry,
    primary: RecordingScriptedClient,
    fallback: RecordingScriptedClient,
) -> InvestigationController:
    settings_keys = {
        "max_steps",
        "max_adaptive_experiments",
        "max_adaptive_cost_units",
        "max_model_calls",
        "max_tool_calls",
        "max_model_retries",
        "max_critic_revisions",
    }
    overrides = {key: case[key] for key in settings_keys if key in case}
    settings = Settings(
        _env_file=None,
        runs_dir=base / "runs",
        data_dir=base / "data",
        agent_fallback_enabled=bool(case.get("fallback")),
        **overrides,
    )
    artifacts = FileSystemRunArtifactStore(settings.runs_dir)
    return InvestigationController(
        settings,
        artifacts,
        ResultLockService(artifacts),
        CatalogGate(artifacts, UnconfiguredCatalogRevealProvider()),
        inference=primary,
        fallback_inference=fallback if case.get("fallback") else None,
        registry=registry,
    )


def _seed_baseline(
    controller: InvestigationController, run_id: str, profile: str
) -> None:
    state = controller.get(run_id)
    code_tool = {
        "clean": "contamination_screening",
        "eclipsing_binary": "odd_even",
        "contamination": "contamination_screening",
        "weak": "search_bls",
    }[profile]
    for index, tool_name in enumerate(
        ("search_bls", "odd_even", "secondary_eclipse", "contamination_screening"), 1
    ):
        controller.record_tool_result(
            run_id,
            _fixture_result(
                tool_name,
                run_id,
                f"fixture_{profile}_{index}",
                state.opaque_target_id,
                profile,
                interpretation_code=(
                    _profile_code(profile) if tool_name == code_tool else None
                ),
            ),
        )


def _prepare_restart(
    controller: InvestigationController, run_id: str, profile: str
) -> None:
    state = controller.get(run_id)
    state = controller._replace(
        state, status=InvestigationStatus.SELECTING_ADAPTIVE_EXPERIMENT
    )
    state = controller._replace(state, status=InvestigationStatus.WAITING_FOR_CRITIC)
    state = controller._replace(state, status=InvestigationStatus.RUNNING_TOOL)
    parameters = {"trial_factor": 1}
    execution = ToolExecutionRecord(
        action_id="action_prepared_eval",
        step_id="step_0000",
        tool_name="harmonic_test",
        parameters=parameters,
        action_signature=controller._action_signature("harmonic_test", parameters),
        status=ToolExecutionStatus.PREPARED,
        adaptive=True,
        adaptive_cost_units=1,
    )
    state = controller._replace(
        state,
        tool_call_count=state.tool_call_count + 1,
        adaptive_experiments_used=state.adaptive_experiments_used + 1,
        adaptive_cost_units_used=state.adaptive_cost_units_used + 1,
        adaptive_cost_units_remaining=state.adaptive_cost_units_remaining - 1,
        tool_executions=[*state.tool_executions, execution],
    )
    result = _fixture_result(
        "harmonic_test",
        state.run_id,
        execution.action_id,
        state.opaque_target_id,
        profile,
        parameters=parameters,
        interpretation_code=_profile_code(profile),
    )
    controller.artifacts.append_evidence(
        state,
        EvidenceRecord(
            evidence_id=controller._evidence_id(result),
            run_id=state.run_id,
            step_id=execution.step_id,
            action_id=execution.action_id,
            opaque_target_id=state.opaque_target_id,
            tool_name=result.tool_name,
            tool_status=result.status,
            result=result,
            interpretation_code=_profile_code(profile),
        ),
    )


def _add_context_pressure(controller: InvestigationController, run_id: str) -> None:
    state = controller.get(run_id)
    for index in range(8):
        parameters = {"window_days": 1.01 + index * 0.1}
        controller.record_tool_result(
            run_id,
            _fixture_result(
                "alternate_detrend",
                run_id,
                f"fixture_pressure_{index}",
                state.opaque_target_id,
                "weak",
                parameters=parameters,
                interpretation_code="NO_SECONDARY_ECLIPSE",
            ),
        )


async def _drive_case(
    base: Path, case: dict[str, Any]
) -> tuple[InvestigationController, Any, list[dict[str, Any]], Counter[str]]:
    calls: Counter[str] = Counter()
    registry = _registry(
        case["profile"],
        calls,
        failure_tool=case.get("tool_failure"),
        timeout_tool=case.get("tool_timeout"),
    )
    if "all_adaptive_cost_units" in case:
        registry = ScientificToolRegistry(
            replace(spec, cost_units=case["all_adaptive_cost_units"])
            if spec.adaptive
            else spec
            for spec in registry.specs
        )
    if case.get("tool_timeout"):
        registry = ScientificToolRegistry(
            replace(spec, timeout_seconds=0.01)
            if spec.name == case["tool_timeout"]
            else spec
            for spec in registry.specs
        )
    primary, fallback = _responses(case)
    controller = _controller(base, case, registry, primary, fallback)
    state = controller.create("TARGET-EVAL")
    setup = case.get("setup", "seeded")
    if setup != "raw":
        _seed_baseline(controller, state.run_id, case["profile"])
    if setup == "repeat":
        controller.record_tool_result(
            state.run_id,
            _fixture_result(
                "harmonic_test",
                state.run_id,
                "fixture_prior_harmonic",
                state.opaque_target_id,
                case["profile"],
                parameters={"trial_factor": 1},
            ),
        )
    elif setup == "context_pressure":
        _add_context_pressure(controller, state.run_id)
    elif setup == "prepared_restart":
        _prepare_restart(controller, state.run_id, case["profile"])
        controller = _controller(base, case, registry, primary, fallback)

    service = InvestigationRunService(
        controller,
        _target_registry(base),
        runs_dir=base / "runs",
        timeout_seconds=float(case.get("runner_timeout_seconds", 2.0)),
        sse_poll_interval_seconds=0.001,
    )
    if setup == "no_progress":

        async def stalled(run_id: str):
            return controller.get(run_id)

        controller.advance = stalled  # type: ignore[method-assign]
    elif setup == "advance_budget":

        async def artificial_progress(run_id: str):
            current = controller.get(run_id)
            return controller._replace(
                current, context_version=str(int(current.context_version) + 1)
            )

        controller.advance = artificial_progress  # type: ignore[method-assign]
    elif setup == "runner_timeout":

        async def delayed_advance(run_id: str):
            await asyncio.sleep(0.1)
            return controller.get(run_id)

        controller.advance = delayed_advance  # type: ignore[method-assign]

    await service.start(state.run_id)
    execution = await service.wait(state.run_id)
    if case.get("tool_timeout"):
        await asyncio.sleep(0.12)
    contexts = [*primary.contexts, *fallback.contexts]
    return controller, execution, contexts, calls


def _actual(
    controller: InvestigationController,
    execution: Any,
    contexts: list[dict[str, Any]],
    calls: Counter[str],
) -> dict[str, Any]:
    state = controller.get(execution.run_id)
    events = controller.events(state.run_id)
    attempts = [event.payload for event in events if event.type == "inference.attempt"]
    adaptive = [
        item.tool_name
        for item in state.tool_executions
        if item.adaptive and not item.action_id.startswith("fixture_")
    ]
    signatures = [item.action_signature for item in state.tool_executions]
    return {
        "status": str(state.status),
        "disposition": str(state.disposition) if state.disposition else None,
        "terminal_reason": state.terminal_reason,
        "runner_stop_reason": execution.stop_reason,
        "selected_tools": [
            item.requested_experiment for item in state.accepted_decisions
        ],
        "adaptive_tools": adaptive,
        "repeated_tool_calls": len(signatures) - len(set(signatures)),
        "all_tools": [item.tool_name for item in state.tool_executions],
        "critic_verdicts": [str(item.verdict) for item in state.critic_decisions],
        "failure_kinds": [str(item.kind) for item in state.failures],
        "attempt_statuses": [item["status"] for item in attempts],
        "attempt_kinds": [item["attempt_kind"] for item in attempts],
        "fallback_labels": [
            event.payload.get("label")
            for event in events
            if event.type == "inference.fallback"
        ],
        "recovery_events": sum(event.type == "recovery.completed" for event in events),
        "mandatory_tests": list(state.completed_tests),
        "mandatory_checks_completed": set(MANDATORY_TESTS).issubset(
            state.completed_tests
        ),
        "model_calls": state.model_call_count,
        "tool_calls": state.tool_call_count,
        "step_count": state.step_count,
        "adaptive_experiments": state.adaptive_experiments_used,
        "adaptive_cost_units_used": state.adaptive_cost_units_used,
        "adaptive_cost_units_remaining": state.adaptive_cost_units_remaining,
        "critic_revisions": state.critic_revision_count,
        "model_retries": state.model_retry_count,
        "tool_invocations": dict(sorted(calls.items())),
        "context_count": len(contexts),
        "context_bytes_max": max((item["bytes"] for item in contexts), default=0),
        "context_fingerprints": [item["fingerprint"] for item in contexts],
        "production_context_fingerprints_valid": all(
            item["production_fingerprint_valid"] for item in contexts
        ),
        "recent_evidence_max": max(
            (item["recent_evidence"] for item in contexts), default=0
        ),
        "trace_events": len(events),
        "evidence_records": len(controller.evidence(state.run_id)),
        "lock_state": str(state.lock_state),
    }


def _persisted_checks(
    controller: InvestigationController,
    actual: dict[str, Any],
    global_rules: dict[str, Any],
) -> list[str]:
    state = controller.get(next(iter(controller._states)))
    run_dir = controller.artifacts.run_dir(state.opaque_target_id, state.run_id)
    events = controller.events(state.run_id)
    evidence = controller.evidence(state.run_id)
    failures: list[str] = []
    sequences = [event.sequence for event in events]
    if global_rules["require_contiguous_trace"] and sequences != list(
        range(1, len(events) + 1)
    ):
        failures.append("trace sequence is not contiguous")
    event_evidence = [
        event.payload["evidence_id"]
        for event in events
        if event.type == "evidence.appended"
    ]
    event_evidence.extend(
        event.payload["evidence_ref"]
        for event in events
        if event.type == "recovery.completed"
        and event.payload["evidence_ref"] not in event_evidence
    )
    if event_evidence != list(state.evidence_refs):
        failures.append("evidence event order differs from durable state")
    if [item.evidence_id for item in evidence] != list(state.evidence_refs):
        failures.append("ledger order differs from durable state")
    attempt_count = sum(event.type == "inference.attempt" for event in events)
    if attempt_count != state.model_call_count:
        failures.append("model-call budget count differs from inference trace")
    if state.step_count > state.max_steps:
        failures.append("step budget exceeded")
    if state.model_call_count > state.max_model_calls:
        failures.append("model-call budget exceeded")
    if state.tool_call_count > state.max_tool_calls:
        failures.append("tool-call budget exceeded")
    if state.adaptive_experiments_used > state.max_adaptive_experiments:
        failures.append("adaptive-experiment budget exceeded")
    if state.adaptive_cost_units_used > state.max_adaptive_cost_units:
        failures.append("adaptive cost budget exceeded")
    if (
        sum(item.adaptive_cost_units for item in state.tool_executions)
        != state.adaptive_cost_units_used
    ):
        failures.append("adaptive cost charge differs from durable executions")
    if state.critic_revision_count > state.max_critic_revisions:
        failures.append("Critic revision budget exceeded")
    signatures = [item.action_signature for item in state.tool_executions]
    if len(signatures) != len(set(signatures)):
        failures.append("a repeated action was executed")
    if actual["unnecessary_tool_calls"]:
        failures.append("adaptive tool calls outside the locked trajectory were executed")
    if any(item not in controller.registry.names for item in actual["all_tools"]):
        failures.append("an unregistered action was executed")
    if (
        global_rules["require_ground_truth_locked"]
        and state.lock_state != LockState.GROUND_TRUTH_LOCKED
    ):
        failures.append("ground truth was unlocked during evaluation")
    persisted = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in sorted(run_dir.rglob("*"))
        if path.is_file()
    ).lower()
    for term in global_rules["forbidden_persisted_terms"]:
        if term.lower() in persisted:
            failures.append(f"forbidden persisted term: {term}")
    forbidden_keys = {
        "cached_path",
        "catalog_payload",
        "ground_truth",
        "local_path",
        "messages",
        "prompt",
        "provider_body",
        "raw_flux",
        "raw_lightcurve",
        "source_path",
        "system_prompt",
        "target_name",
        "tic_id",
        "toi_id",
        "user_prompt",
    }

    def inspect_persisted(value: Any, location: str) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if key.lower() in forbidden_keys:
                    failures.append(f"forbidden persisted field: {key} at {location}")
                inspect_persisted(child, f"{location}.{key}")
        elif isinstance(value, list):
            if len(value) >= 3 and all(
                isinstance(item, (int, float)) for item in value
            ):
                failures.append(f"raw numeric array persisted at {location}")
            for index, child in enumerate(value):
                inspect_persisted(child, f"{location}[{index}]")
        elif isinstance(value, str):
            if re.search(r"(?i)(?:\b[a-z]:[\\/]|file://|\\\\[^\\\s]+\\)", value):
                failures.append(f"local path persisted at {location}")
            if re.search(
                r"(?i)\b(?:tic|toi|kepler|k2|wasp|hat-p)\s*[-:#]?\s*\d+", value
            ):
                failures.append(f"recognizable target identity persisted at {location}")

    for path in sorted(run_dir.rglob("*")):
        if not path.is_file() or path.suffix not in {".json", ".jsonl"}:
            continue
        lines = (
            path.read_text(encoding="utf-8").splitlines()
            if path.suffix == ".jsonl"
            else [path.read_text(encoding="utf-8")]
        )
        for line_number, line in enumerate(lines, 1):
            if line.strip():
                inspect_persisted(json.loads(line), f"{path.name}:{line_number}")
    if actual["context_bytes_max"] > global_rules["max_context_bytes"]:
        failures.append("agent context exceeded locked byte limit")
    if actual["context_count"] and not all(actual["context_fingerprints"]):
        failures.append("agent context fingerprint is missing")
    if actual["context_count"] and not actual["production_context_fingerprints_valid"]:
        failures.append("production context fingerprint is invalid")

    reloaded = InvestigationController(
        controller.settings,
        controller.artifacts,
        controller.result_lock,
        controller.catalog_gate,
        inference=controller.inference,
        fallback_inference=controller.fallback_inference,
        registry=controller.registry,
    )
    reloaded_state = reloaded.get(state.run_id)
    if reloaded_state != state:
        failures.append("reloaded state differs from live durable state")
    if reloaded.events(state.run_id) != events:
        failures.append("reloaded trace differs from live trace")
    if reloaded.evidence(state.run_id) != evidence:
        failures.append("reloaded evidence differs from live ledger")
    return failures


def _unnecessary_tool_call_count(
    actual_tools: list[str], expected_tools: list[str]
) -> int:
    unexpected = Counter(actual_tools) - Counter(expected_tools)
    return sum(unexpected.values())


def _locked_checks(expected: dict[str, Any], actual: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    for key, value in expected.items():
        if key == "terminal_reason_contains":
            if value not in (actual["terminal_reason"] or ""):
                failures.append(f"terminal_reason does not contain {value!r}")
        elif actual.get(key) != value:
            failures.append(f"{key}: expected {value!r}, got {actual.get(key)!r}")
    return failures


async def _run_suite_in(base: Path) -> dict[str, Any]:
    scenarios, acceptance = _load_locked()
    results: list[dict[str, Any]] = []
    for case in scenarios["cases"]:
        case_root = base / case["id"]
        controller, execution, contexts, calls = await _drive_case(case_root, case)
        actual = _actual(controller, execution, contexts, calls)
        expected = acceptance["cases"][case["id"]]
        actual["unnecessary_tool_calls"] = _unnecessary_tool_call_count(
            actual["adaptive_tools"], expected.get("adaptive_tools", [])
        )
        failures = _locked_checks(expected, actual)
        failures.extend(_persisted_checks(controller, actual, acceptance["global"]))
        setup = case.get("setup", "seeded")
        if (
            setup not in {"raw", "no_progress", "advance_budget", "runner_timeout"}
            and not actual["mandatory_checks_completed"]
        ):
            failures.append("mandatory diagnostics were not completed")
        results.append(
            {
                "id": case["id"],
                "passed": not failures,
                "failures": failures,
                "actual": actual,
            }
        )

    branch_ids = {
        "clean_planet_like",
        "eclipsing_binary_adverse",
        "ambiguous_inconclusive",
        "evidence_branch_contamination",
    }
    branches = {
        tuple(item["actual"]["adaptive_tools"])
        for item in results
        if item["id"] in branch_ids
    }
    suite_failures: list[str] = []
    if len(branches) < 3:
        suite_failures.append(
            "locked evidence cases did not produce at least three branches"
        )
    if any(not item["passed"] for item in results):
        suite_failures.append("one or more locked scenarios failed")
    return {
        "schema_version": "1",
        "suite_id": scenarios["suite_id"],
        "passed": not suite_failures,
        "scenario_count": len(results),
        "passed_count": sum(item["passed"] for item in results),
        "failed_count": sum(not item["passed"] for item in results),
        "suite_failures": suite_failures,
        "metrics": {
            "branch_count": len(branches),
            "cost_budget_status": "graded",
            "repeated_tool_calls": sum(
                item["actual"]["repeated_tool_calls"] for item in results
            ),
            "artifact_reload_cases": len(results),
            "unnecessary_tool_calls": sum(
                item["actual"]["unnecessary_tool_calls"] for item in results
            ),
        },
        "known_gaps": [],
        "scenarios": results,
    }


def run_suite(work_dir: Path | None = None) -> dict[str, Any]:
    if work_dir is not None:
        work_dir.mkdir(parents=True, exist_ok=True)
        return asyncio.run(_run_suite_in(work_dir))
    with tempfile.TemporaryDirectory(prefix="exoswarm-harness-eval-") as temporary:
        return asyncio.run(_run_suite_in(Path(temporary)))


def markdown_summary(report: dict[str, Any]) -> str:
    status = "PASS" if report["passed"] else "FAIL"
    lines = [
        "# ExoSwarm harness evaluation",
        "",
        f"Suite: `{report['suite_id']}`",
        "",
        f"Result: **{status}** — {report['passed_count']}/{report['scenario_count']} scenarios passed.",
        "",
        "| Scenario | Result | Terminal status | Adaptive tools |",
        "|---|---:|---|---|",
    ]
    for item in report["scenarios"]:
        actual = item["actual"]
        tools = ", ".join(actual["adaptive_tools"]) or "—"
        lines.append(
            f"| `{item['id']}` | {'PASS' if item['passed'] else 'FAIL'} | "
            f"{actual['status']} | {tools} |"
        )
        for failure in item["failures"]:
            lines.append(f"| ↳ |  | {failure} |  |")
    lines.extend(
        [
            "",
            "## Coverage notes",
            "",
            f"- Deterministic branch count: {report['metrics']['branch_count']}.",
            (
                "- Durable state/trace/evidence artifact reload checks: "
                f"{report['metrics']['artifact_reload_cases']}."
            ),
            (
                "- Repeated / outside-trajectory tool calls: "
                f"{report['metrics']['repeated_tool_calls']} / "
                f"{report['metrics']['unnecessary_tool_calls']}."
            ),
            (
                "- Raw provider bodies, prompts, recognizable identity, local source paths, "
                "ground truth, and raw arrays are scanned out of persisted artifacts."
            ),
            "",
        ]
    )
    return "\n".join(lines)


__all__ = ["markdown_summary", "run_suite"]
