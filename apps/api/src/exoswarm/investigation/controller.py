from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import multiprocessing
import shutil
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from secrets import token_hex
from threading import Event
from time import perf_counter
from typing import Any

from pydantic import BaseModel, ValidationError

from exoswarm.agents.context import assemble_context
from exoswarm.agents.critic import CRITIC_PROMPT_VERSION
from exoswarm.agents.director import (
    DirectorRoute,
    DirectorStateView,
    FreshCycleRoute,
    determine_director_route,
)
from exoswarm.agents.graph import InvestigationGraphUpdate, build_investigation_graph
from exoswarm.agents.inference_telemetry import (
    concise_inference_summary,
    derive_inference_summary,
)
from exoswarm.agents.model_client import (
    AttemptKind,
    InferenceAttemptOutcome,
    InferenceClient,
    UnconfiguredInferenceClient,
)
from exoswarm.agents.skeptic import SKEPTIC_PROMPT_VERSION
from exoswarm.config import Settings
from exoswarm.domain.enums import (
    CriticVerdict,
    Disposition,
    HarnessFailureKind,
    InvestigationStatus,
    LockState,
    ToolExecutionStatus,
    ToolStatus,
)
from exoswarm.domain.errors import (
    ActionValidationError,
    InvalidModelOutputError,
    ModelNotConfiguredError,
    ModelOutputTruncatedError,
    ModelProviderError,
    ModelProviderTimeoutError,
    RunNotFoundError,
    ToolPermissionError,
    UnknownToolError,
)
from exoswarm.domain.events import InvestigationEvent
from exoswarm.domain.models import (
    CandidateSignal,
    CriticDecision,
    EvidenceRecord,
    HarnessFailureRecord,
    InferenceTraceRecord,
    InvestigationState,
    LockReceipt,
    Measurement,
    RevealResult,
    ScientificToolResult,
    SkepticDecision,
    ToolExecutionRecord,
)
from exoswarm.investigation.hypotheses import (
    decisive_interpretation,
    has_weak_planetary_interpretation,
    updated_hypotheses,
)
from exoswarm.investigation.mandatory import missing_mandatory_tests
from exoswarm.investigation.runtime_inputs import CandidateSourceResolver
from exoswarm.investigation.state import validate_status_transition
from exoswarm.investigation.stopping import (
    adaptive_budget_terminal_reason,
    availability_terminal_reason,
)
from exoswarm.investigation.tool_registry import (
    STOP_ACTION,
    ScientificToolRegistry,
    scaffold_tool_registry,
)
from exoswarm.science.contracts import ExecutionIsolation, ScientificToolSpec
from exoswarm.security.catalog_gate import CatalogGate
from exoswarm.security.result_lock import ResultLockService
from exoswarm.services.artifacts import FileSystemRunArtifactStore

_SUCCESSFUL_TEST_STATUSES = frozenset(
    {ToolStatus.SUCCESS, ToolStatus.NO_EVIDENCE, ToolStatus.INDETERMINATE}
)
_LOGGER = logging.getLogger(__name__)


def _subprocess_tool_entry(
    sender: Any,
    handler: Any,
    run_id: str,
    action_id: str,
    target_id: str,
    parameters: dict[str, Any],
) -> None:
    """Execute one importable scientific handler without exposing raw exception text."""

    try:
        sender.send(("result", handler(run_id, action_id, target_id, parameters)))
    except BaseException as exc:
        sender.send(("error", type(exc).__name__[:100]))
    finally:
        sender.close()


class _SubprocessToolError(RuntimeError):
    pass


class _HarnessAbort(Exception):
    def __init__(
        self,
        kind: HarnessFailureKind,
        reason: str,
        *,
        status: InvestigationStatus = InvestigationStatus.FAILED,
        recoverable: bool = True,
        action_id: str | None = None,
    ) -> None:
        super().__init__(reason)
        self.kind = kind
        self.reason = reason
        self.status = status
        self.recoverable = recoverable
        self.action_id = action_id


class InvestigationController:
    """Explicit bounded policy loop around mockable inference and deterministic tools."""

    def __init__(
        self,
        settings: Settings,
        artifacts: FileSystemRunArtifactStore,
        result_lock: ResultLockService,
        catalog_gate: CatalogGate,
        *,
        inference: InferenceClient | None = None,
        fallback_inference: InferenceClient | None = None,
        registry: ScientificToolRegistry | None = None,
        candidate_sources: CandidateSourceResolver | None = None,
        granted_scopes: set[str] | frozenset[str] = frozenset({"science:execute"}),
    ) -> None:
        self.settings = settings
        self.artifacts = artifacts
        self.result_lock = result_lock
        self.catalog_gate = catalog_gate
        self.inference = inference or UnconfiguredInferenceClient()
        self.fallback_inference = fallback_inference
        self.registry = registry or scaffold_tool_registry()
        self.candidate_sources = candidate_sources
        self.granted_scopes = frozenset(granted_scopes)
        self._states: dict[str, InvestigationState] = {}
        self._events: dict[str, list[InvestigationEvent]] = {}
        self._advance_locks: dict[str, asyncio.Lock] = {}
        self._investigation_graph = build_investigation_graph(self)

    def create(self, opaque_target_id: str) -> InvestigationState:
        run_id = f"run_{token_hex(8)}"
        state = InvestigationState(
            run_id=run_id,
            opaque_target_id=opaque_target_id,
            available_tests=list(self.registry.names),
            max_steps=self.settings.max_steps,
            max_adaptive_experiments=self.settings.max_adaptive_experiments,
            max_adaptive_cost_units=self.settings.max_adaptive_cost_units,
            adaptive_cost_units_remaining=self.settings.max_adaptive_cost_units,
            max_model_calls=self.settings.max_model_calls,
            max_tool_calls=self.settings.max_tool_calls,
            max_model_retries=self.settings.max_model_retries,
            max_critic_revisions=self.settings.max_critic_revisions,
        )
        event = InvestigationEvent(
            event_id=f"evt_{token_hex(8)}",
            run_id=run_id,
            step_id="step_0000",
            action_id=f"action_{token_hex(8)}",
            sequence=1,
            type="investigation.created",
            payload={"status": state.status, "opaque_target_id": opaque_target_id},
        )
        self.artifacts.create(state)
        self.artifacts.append_trace(state, event)
        self._states[run_id] = state
        self._events[run_id] = [event]
        return state

    def get(self, run_id: str) -> InvestigationState:
        state = self._states.get(run_id)
        if state is None:
            state = self.artifacts.find_state(run_id)
            if state is None:
                raise RunNotFoundError(f"investigation not found: {run_id}")
            self._states[run_id] = state
            self._events[run_id] = self.artifacts.read_trace(state)
        return state

    def events(self, run_id: str) -> tuple[InvestigationEvent, ...]:
        self.get(run_id)
        return tuple(self._events[run_id])

    def evidence(self, run_id: str) -> tuple[EvidenceRecord, ...]:
        return tuple(self.artifacts.read_evidence(self.get(run_id)))

    def lock(self, run_id: str) -> LockReceipt:
        state = self.get(run_id)
        updated, receipt = self.result_lock.lock(state)
        event = self._event(updated, "result.locked", {"sha256": receipt.sha256})
        self._states[run_id] = updated
        self.artifacts.append_trace(updated, event)
        self._events[run_id].append(event)
        return receipt

    def reveal(self, run_id: str) -> RevealResult:
        state = self.get(run_id)
        reveal = self.catalog_gate.reveal(state)
        updated = self._replace(
            state,
            status=InvestigationStatus.REVEALED,
            lock_state=LockState.CATALOG_REVEALED,
        )
        self._emit(updated, "catalog.revealed", {"catalog_source": reveal.catalog_source})
        return reveal

    def fail_run(
        self,
        run_id: str,
        reason: str,
        *,
        kind: HarnessFailureKind = HarnessFailureKind.TOOL_INFRASTRUCTURE_FAILURE,
        recoverable: bool = True,
    ) -> InvestigationState:
        """Checkpoint a runner-boundary failure through the durable harness path."""

        state = self.get(run_id)
        if self._cannot_advance(state):
            return state
        prepared_action_id = next(
            (
                execution.action_id
                for execution in reversed(state.tool_executions)
                if execution.status == ToolExecutionStatus.PREPARED
            ),
            None,
        )
        return self._terminate(
            state,
            kind,
            reason,
            status=InvestigationStatus.FAILED,
            recoverable=recoverable,
            action_id=prepared_action_id,
        )

    def record_tool_result(self, run_id: str, result: ScientificToolResult) -> InvestigationState:
        """Admit an already deterministic result, including test/eval fixture results."""

        state = self.get(run_id)
        self._assert_science_admission_open(state)
        spec, validated_parameters = self.registry.validate_parameters(
            result.tool_name,
            parameters=result.parameters,
        )
        if result.run_id != run_id or result.target_id != state.opaque_target_id:
            raise ValueError("tool result identifiers do not match the durable investigation")
        if state.tool_call_count >= state.max_tool_calls:
            raise ValueError("tool-call budget is exhausted")
        if spec.adaptive:
            if state.adaptive_experiments_used >= state.max_adaptive_experiments:
                raise ValueError("adaptive-experiment count budget is exhausted")
            if spec.cost_units > state.adaptive_cost_units_remaining:
                raise ValueError("adaptive cost-unit budget is exhausted")
        signature = self._action_signature(result.tool_name, validated_parameters)
        if any(item.action_signature == signature for item in state.tool_executions):
            raise ValueError("identical action has already been recorded")
        execution = ToolExecutionRecord(
            action_id=result.action_id,
            step_id=f"step_{state.step_count:04d}",
            tool_name=result.tool_name,
            parameters=validated_parameters,
            action_signature=signature,
            status=ToolExecutionStatus.PREPARED,
            adaptive=spec.adaptive,
            adaptive_cost_units=spec.cost_units if spec.adaptive else 0,
        )
        state = self._replace(
            state,
            tool_call_count=state.tool_call_count + 1,
            adaptive_experiments_used=(
                state.adaptive_experiments_used + 1
                if spec.adaptive
                else state.adaptive_experiments_used
            ),
            adaptive_cost_units_used=(
                state.adaptive_cost_units_used + spec.cost_units
                if spec.adaptive
                else state.adaptive_cost_units_used
            ),
            adaptive_cost_units_remaining=(
                state.adaptive_cost_units_remaining - spec.cost_units
                if spec.adaptive
                else state.adaptive_cost_units_remaining
            ),
            tool_executions=[*state.tool_executions, execution],
        )
        self._commit_result(state, result)
        return self.get(run_id)

    async def advance(self, run_id: str) -> InvestigationState:
        """Invoke the sole LangGraph topology under the single-writer guard."""

        lock = self._advance_locks.setdefault(run_id, asyncio.Lock())
        async with lock:
            try:
                await self._investigation_graph.ainvoke(
                    {"run_id": run_id},
                    {"recursion_limit": 16},
                )
            except _HarnessAbort as exc:
                return self._terminate(
                    self.get(run_id),
                    exc.kind,
                    exc.reason,
                    status=exc.status,
                    recoverable=exc.recoverable,
                    action_id=exc.action_id,
                )
            return self.get(run_id)

    async def recover_prepared_execution(self, run_id: str) -> InvestigationGraphUpdate:
        """Recover controller-prepared work before any graph routing decision."""

        state = self.get(run_id)
        if self._cannot_advance(state):
            return {}
        await self._recover_prepared_execution(state)
        return {}

    def begin_cycle(self, run_id: str) -> InvestigationState:
        """Durably charge one step, idempotently across node-boundary restarts."""

        state = self.get(run_id)
        if self._cannot_advance(state) or not self._cycle_requires_begin(state):
            return state
        if state.step_count >= state.max_steps:
            raise _HarnessAbort(
                HarnessFailureKind.BUDGET_EXHAUSTED,
                "maximum total step budget reached",
                status=InvestigationStatus.BUDGET_EXHAUSTED,
                recoverable=False,
            )
        state = self._replace(state, step_count=state.step_count + 1)
        self._emit(state, "budget.updated", self._budget_payload(state))
        return state

    def determine_route(self, run_id: str) -> DirectorRoute:
        """Reload durable state and ask the deterministic Director for the next node."""

        state = self.get(run_id)
        prepared = any(
            item.status == ToolExecutionStatus.PREPARED for item in state.tool_executions
        )
        pending_evaluation = self._has_pending_evaluation(state)
        if (
            not self._cannot_advance(state)
            and not prepared
            and not pending_evaluation
            and self._cycle_requires_begin(state)
        ):
            state = self.begin_cycle(run_id)
        skeptic = self._current_skeptic(state)
        critic = self._current_critic(state, skeptic)
        selected_action = None
        if skeptic is not None and critic is not None and critic.verdict != CriticVerdict.VETO:
            selected_action = (
                critic.revised_experiment
                if critic.verdict == CriticVerdict.REVISE
                else skeptic.requested_experiment
            )
        persisted_revisions = sum(
            item.verdict == CriticVerdict.REVISE for item in state.critic_decisions
        )
        if self._cannot_advance(state) or prepared or pending_evaluation or skeptic is not None:
            return determine_director_route(
                DirectorStateView(
                    status=state.status,
                    terminal=self._cannot_advance(state),
                    has_prepared_execution=prepared,
                    has_uncommitted_result=pending_evaluation,
                    skeptic_decision_id=skeptic.decision_id if skeptic else None,
                    critic_decision_id=critic.decision_id if critic else None,
                    critic_verdict=critic.verdict if critic else None,
                    approved_action_is_stop=selected_action == STOP_ACTION,
                    critic_requires_resolution=(
                        critic is not None
                        and critic.verdict == CriticVerdict.REVISE
                        and state.critic_revision_count != persisted_revisions
                    ),
                )
            )
        if state.status in {
            InvestigationStatus.WAITING_FOR_CRITIC,
            InvestigationStatus.RUNNING_TOOL,
        }:
            raise _HarnessAbort(
                HarnessFailureKind.TOOL_INFRASTRUCTURE_FAILURE,
                f"durable lifecycle state is incomplete: {state.status}",
                recoverable=False,
            )
        state = self.begin_cycle(run_id)
        fresh_route = self._fresh_cycle_route(state)
        return determine_director_route(
            DirectorStateView(
                status=state.status,
                terminal=False,
                has_prepared_execution=False,
                has_uncommitted_result=False,
                skeptic_decision_id=None,
                critic_decision_id=None,
                critic_verdict=None,
                critic_requires_resolution=False,
                fresh_cycle_route=fresh_route,
            )
        )

    def record_director_route(
        self, run_id: str, route: DirectorRoute, *, source: str
    ) -> None:
        """Persist a concise audit record for each effective graph branch."""

        if route == DirectorRoute.NOOP_TERMINAL:
            return
        state = self.get(run_id)
        self._emit(
            state,
            "director.route",
            {
                "route": route.value,
                "source": source,
                "status": state.status.value,
            },
        )

    async def run_mandatory_cycle(self, run_id: str) -> InvestigationGraphUpdate:
        """Execute the next controller-authorized mandatory action."""

        state = self.get(run_id)
        missing = missing_mandatory_tests(set(state.completed_tests))
        candidates = [
            spec
            for spec in self.registry.specs
            if spec.mandatory_test in missing
            and spec.required_completed_tests.issubset(state.completed_tests)
        ]
        if not candidates:
            self._terminate(
                state,
                HarnessFailureKind.INSUFFICIENT_EVIDENCE,
                f"no registered action can complete mandatory tests: {sorted(missing)}",
                status=InvestigationStatus.INSUFFICIENT_EVIDENCE,
                recoverable=False,
            )
            return {}
        state = self._replace(state, status=InvestigationStatus.VETTING_MANDATORY)
        spec = candidates[0]
        await self._execute_action(state, spec.name, {}, adaptive=False)
        return {}

    async def run_skeptic_node(self, run_id: str) -> InvestigationGraphUpdate:
        """Persist exactly one validated Skeptic decision for the current step."""

        state = self.get(run_id)
        existing = self._current_skeptic(state)
        if existing is not None:
            if state.status == InvestigationStatus.SELECTING_ADAPTIVE_EXPERIMENT:
                self._replace(state, status=InvestigationStatus.WAITING_FOR_CRITIC)
            return {}
        available = self._available_adaptive_actions(state)
        state = self._replace(
            state,
            status=InvestigationStatus.SELECTING_ADAPTIVE_EXPERIMENT,
            available_tests=list(available),
        )
        skeptic, skeptic_call = await self._infer(
            state, role="skeptic", schema=SkepticDecision, available=available
        )
        state = self.get(run_id)
        assert isinstance(skeptic, SkepticDecision)
        self._validate_skeptic_identity(state, skeptic)
        state = self._replace(state, accepted_decisions=[*state.accepted_decisions, skeptic])
        self._emit(
            state,
            "agent.decision",
            {
                "role": "skeptic",
                "provider": skeptic_call.provider,
                "model_identity": skeptic_call.model_identity,
                "fallback_used": skeptic_call.fallback_used,
                "inference_call_id": skeptic_call.call_id,
                "decision": skeptic.model_dump(mode="json"),
                "context_version": state.context_version,
            },
        )
        self._replace(state, status=InvestigationStatus.WAITING_FOR_CRITIC)
        return {}

    async def run_critic_node(self, run_id: str) -> InvestigationGraphUpdate:
        """Persist exactly one validated Critic review for the current proposal."""

        state = self.get(run_id)
        skeptic = self._current_skeptic(state)
        if skeptic is None:
            raise _HarnessAbort(
                HarnessFailureKind.TOOL_INFRASTRUCTURE_FAILURE,
                "Critic routing requires a durable current-step Skeptic decision",
                recoverable=False,
            )
        existing = self._current_critic(state, skeptic)
        if existing is not None:
            return {}
        available = tuple(state.available_tests)
        critic, critic_call = await self._infer(
            state,
            role="critic",
            schema=CriticDecision,
            available=available,
            proposed_decision=skeptic,
        )
        state = self.get(run_id)
        assert isinstance(critic, CriticDecision)
        self._validate_critic_identity(state, skeptic, critic)
        state = self._replace(state, critic_decisions=[*state.critic_decisions, critic])
        self._emit(
            state,
            "critic.review",
            {
                "provider": critic_call.provider,
                "model_identity": critic_call.model_identity,
                "fallback_used": critic_call.fallback_used,
                "inference_call_id": critic_call.call_id,
                "decision": critic.model_dump(mode="json"),
                "context_version": state.context_version,
            },
        )
        return {}

    def resolve_critic_verdict(self, run_id: str) -> DirectorRoute:
        """Validate the durable Critic verdict and authorize its graph branch."""

        state = self.get(run_id)
        skeptic = self._current_skeptic(state)
        critic = self._current_critic(state, skeptic)
        if skeptic is None or critic is None:
            raise _HarnessAbort(
                HarnessFailureKind.TOOL_INFRASTRUCTURE_FAILURE,
                "Critic route requires matching durable decisions",
                recoverable=False,
            )
        if critic.verdict == CriticVerdict.VETO:
            return DirectorRoute.FINALIZE
        if critic.verdict == CriticVerdict.REVISE:
            revision_count = sum(
                item.verdict == CriticVerdict.REVISE for item in state.critic_decisions
            )
            prior_revisions = revision_count - 1
            if prior_revisions >= state.max_critic_revisions:
                raise _HarnessAbort(
                    HarnessFailureKind.BUDGET_EXHAUSTED,
                    "Critic revision budget reached",
                    status=InvestigationStatus.BUDGET_EXHAUSTED,
                    recoverable=False,
                )
            if state.critic_revision_count < revision_count:
                self._replace(state, critic_revision_count=revision_count)
            elif state.critic_revision_count > revision_count:
                raise _HarnessAbort(
                    HarnessFailureKind.TOOL_INFRASTRUCTURE_FAILURE,
                    "durable Critic revision counter exceeds persisted reviews",
                    recoverable=False,
                )
        selected_action = (
            critic.revised_experiment
            if critic.verdict == CriticVerdict.REVISE
            else skeptic.requested_experiment
        )
        if selected_action == STOP_ACTION:
            return DirectorRoute.FINALIZE
        return DirectorRoute.EXECUTE_APPROVED_ACTION

    async def run_adaptive_cycle(self, run_id: str) -> InvestigationGraphUpdate:
        """Execute the current Critic-authorized adaptive action once."""

        state = self.get(run_id)
        skeptic = self._current_skeptic(state)
        critic = self._current_critic(state, skeptic)
        if skeptic is None or critic is None or critic.verdict == CriticVerdict.VETO:
            raise _HarnessAbort(
                HarnessFailureKind.TOOL_INFRASTRUCTURE_FAILURE,
                "adaptive execution requires an approved durable proposal",
                recoverable=False,
            )
        tool_name = skeptic.requested_experiment
        parameters = skeptic.parameters
        if critic.verdict == CriticVerdict.REVISE:
            tool_name = critic.revised_experiment or ""
            parameters = critic.revised_parameters or {}
        if tool_name == STOP_ACTION:
            raise _HarnessAbort(
                HarnessFailureKind.TOOL_INFRASTRUCTURE_FAILURE,
                "stop decisions must route directly to finalization",
                recoverable=False,
            )
        await self._execute_action(
            state,
            tool_name,
            parameters,
            adaptive=True,
            agent_decision_id=skeptic.decision_id,
            critic_decision_id=critic.decision_id,
        )
        return {}

    def evaluate_cycle_result(self, run_id: str) -> InvestigationGraphUpdate:
        """Apply deterministic post-result policy to the latest durable evidence."""

        state = self.get(run_id)
        if self._cannot_advance(state):
            return {}
        if state.status != InvestigationStatus.UPDATING_EVIDENCE:
            raise _HarnessAbort(
                HarnessFailureKind.TOOL_INFRASTRUCTURE_FAILURE,
                f"result evaluation requires UPDATING_EVIDENCE, got {state.status}",
                recoverable=False,
            )
        result = self._latest_cycle_result(state)
        self._after_result(state, result)
        return {}

    def finalize_cycle(self, run_id: str) -> InvestigationGraphUpdate:
        """Finalize from durable evidence using the existing deterministic rules."""

        state = self.get(run_id)
        skeptic = self._current_skeptic(state)
        critic = self._current_critic(state, skeptic)
        if critic is not None and critic.verdict == CriticVerdict.VETO:
            reason = f"CRITIC_VETO:{critic.reason_code}"
        elif skeptic is not None and critic is not None and (
            skeptic.requested_experiment == STOP_ACTION
            or critic.revised_experiment == STOP_ACTION
        ):
            reason = f"AGENT_STOP:{skeptic.reason_code}"
        else:
            reason = adaptive_budget_terminal_reason(state) or availability_terminal_reason(
                has_available=bool(self._available_adaptive_actions(state)),
                has_unaffordable=self._has_unaffordable_adaptive_action(state),
            )
            if reason is None:
                raise _HarnessAbort(
                    HarnessFailureKind.TOOL_INFRASTRUCTURE_FAILURE,
                    "finalize route has no durable stopping reason",
                    recoverable=False,
                )
        self._finalize(state, reason)
        return {}

    def terminate_cycle(self, run_id: str) -> InvestigationGraphUpdate:
        """Terminate the controller-classified non-candidate path."""

        state = self.get(run_id)
        self._terminate(
            state,
            HarnessFailureKind.INSUFFICIENT_EVIDENCE,
            "mandatory baseline completed without candidate evidence",
            status=InvestigationStatus.INSUFFICIENT_EVIDENCE,
            recoverable=False,
        )
        return {}

    def _fresh_cycle_route(self, state: InvestigationState) -> FreshCycleRoute:
        missing = missing_mandatory_tests(set(state.completed_tests))
        if missing:
            return FreshCycleRoute.RUN_MANDATORY
        if not state.candidate_signals:
            return FreshCycleRoute.TERMINATE
        if state.adaptive_experiments_used >= state.max_adaptive_experiments:
            return FreshCycleRoute.FINALIZE
        if state.adaptive_cost_units_remaining == 0:
            return FreshCycleRoute.FINALIZE
        available = self._available_adaptive_actions(state)
        if not available:
            return FreshCycleRoute.FINALIZE
        self._replace(
            state,
            status=InvestigationStatus.SELECTING_ADAPTIVE_EXPERIMENT,
            available_tests=list(available),
        )
        return FreshCycleRoute.CALL_SKEPTIC

    def _cycle_requires_begin(self, state: InvestigationState) -> bool:
        if state.status in {
            InvestigationStatus.WAITING_FOR_CRITIC,
            InvestigationStatus.RUNNING_TOOL,
        }:
            return False
        if self._has_pending_evaluation(state):
            return False
        step_id = f"step_{state.step_count:04d}"
        current_events = [event for event in self._events[state.run_id] if event.step_id == step_id]
        latest_budget = max(
            (event.sequence for event in current_events if event.type == "budget.updated"),
            default=0,
        )
        latest_boundary = max(
            (
                event.sequence
                for event in current_events
                if event.type in {"evidence.appended", "recovery.completed"}
            ),
            default=0,
        )
        return latest_budget == 0 or latest_boundary > latest_budget

    def _has_pending_evaluation(self, state: InvestigationState) -> bool:
        if state.status != InvestigationStatus.UPDATING_EVIDENCE:
            return False
        step_id = f"step_{state.step_count:04d}"
        return any(
            event.step_id == step_id and event.type in {"budget.updated", "recovery.completed"}
            for event in self._events[state.run_id]
        )

    @staticmethod
    def _current_skeptic(state: InvestigationState) -> SkepticDecision | None:
        step_id = f"step_{state.step_count:04d}"
        return next(
            (item for item in reversed(state.accepted_decisions) if item.step_id == step_id),
            None,
        )

    @staticmethod
    def _current_critic(
        state: InvestigationState, skeptic: SkepticDecision | None
    ) -> CriticDecision | None:
        if skeptic is None:
            return None
        return next(
            (
                item
                for item in reversed(state.critic_decisions)
                if item.step_id == skeptic.step_id
                and item.skeptic_decision_id == skeptic.decision_id
            ),
            None,
        )

    def _latest_cycle_result(self, state: InvestigationState) -> ScientificToolResult:
        step_id = f"step_{state.step_count:04d}"
        execution = next(
            (
                item
                for item in reversed(state.tool_executions)
                if item.step_id == step_id and item.evidence_ref is not None
            ),
            None,
        )
        if execution is None:
            raise _HarnessAbort(
                HarnessFailureKind.TOOL_INFRASTRUCTURE_FAILURE,
                "UPDATING_EVIDENCE has no completed current-step execution",
                recoverable=False,
            )
        record = next(
            (
                item
                for item in reversed(self.artifacts.read_evidence(state))
                if item.evidence_id == execution.evidence_ref
            ),
            None,
        )
        if record is None:
            raise _HarnessAbort(
                HarnessFailureKind.TOOL_INFRASTRUCTURE_FAILURE,
                "completed execution has no matching durable evidence",
                recoverable=False,
                action_id=execution.action_id,
            )
        return record.result

    @property
    def _model_identity(self) -> str:
        return str(getattr(self.inference, "model_identity", type(self.inference).__name__))

    async def _infer(
        self,
        state: InvestigationState,
        *,
        role: str,
        schema: type[BaseModel],
        available: tuple[str, ...],
        proposed_decision: SkepticDecision | None = None,
    ) -> tuple[BaseModel, InferenceTraceRecord]:
        context = assemble_context(
            state,
            self.artifacts.read_evidence(state),
            role=role,  # type: ignore[arg-type]
            available_experiments=available,
            adaptive_experiment_costs={
                name: self._adaptive_action_cost(name) for name in available
            },
            experiment_specs=self.registry.specs,
            proposed_decision=proposed_decision,
        )
        attempt_kind: AttemptKind = "primary"
        first_validation_failure: _HarnessAbort | None = None

        while True:
            outcome = await self._run_inference_attempt(
                state.run_id,
                client=self.inference,
                role=role,
                context=context,
                schema=schema,
                attempt_kind=attempt_kind,
                validation_error_code=(
                    first_validation_failure.kind if first_validation_failure else None
                ),
            )
            state = self.get(state.run_id)

            if outcome.error is None and outcome.decision is not None:
                try:
                    current = self.get(state.run_id)
                    if current.context_version != context.context_version:
                        raise _HarnessAbort(
                            HarnessFailureKind.INVALID_MODEL_OUTPUT,
                            f"{role} response was produced from an obsolete context version",
                        )
                    decision = schema.model_validate(outcome.decision, strict=True)
                    self._validate_inference_decision(
                        current,
                        role=role,
                        decision=decision,
                        available=available,
                        proposed_decision=proposed_decision,
                    )
                except _HarnessAbort as exc:
                    invalid_call = outcome.call.model_copy(
                        update={
                            "status": "INVALID",
                            "schema_valid": False,
                            "validation_error_code": str(exc.kind),
                        }
                    )
                    self._record_inference_attempt(state, invalid_call)
                    if exc.kind == HarnessFailureKind.BUDGET_EXHAUSTED:
                        raise
                    if first_validation_failure is None:
                        first_validation_failure = exc
                    if attempt_kind == "primary":
                        attempt_kind = "repair"
                        continue
                    return await self._fallback_or_abort(
                        state,
                        role=role,
                        context=context,
                        schema=schema,
                        available=available,
                        proposed_decision=proposed_decision,
                        failure=first_validation_failure,
                    )
                except (ValidationError, TypeError) as exc:
                    invalid = _HarnessAbort(
                        HarnessFailureKind.INVALID_MODEL_OUTPUT,
                        f"{role} returned invalid structured output: {type(exc).__name__}",
                    )
                    invalid_call = outcome.call.model_copy(
                        update={
                            "status": "INVALID",
                            "schema_valid": False,
                            "validation_error_code": str(invalid.kind),
                        }
                    )
                    self._record_inference_attempt(state, invalid_call)
                    if first_validation_failure is None:
                        first_validation_failure = invalid
                    if attempt_kind == "primary":
                        attempt_kind = "repair"
                        continue
                    return await self._fallback_or_abort(
                        state,
                        role=role,
                        context=context,
                        schema=schema,
                        available=available,
                        proposed_decision=proposed_decision,
                        failure=first_validation_failure,
                    )
                self._record_inference_attempt(state, outcome.call)
                return decision, outcome.call

            self._record_inference_attempt(state, outcome.call)
            error = outcome.error
            if isinstance(error, ModelOutputTruncatedError):
                truncated = _HarnessAbort(
                    HarnessFailureKind.OUTPUT_TRUNCATED,
                    f"{role} inference reached the configured output-token limit",
                )
                if first_validation_failure is None:
                    first_validation_failure = truncated
                if attempt_kind == "primary":
                    attempt_kind = "repair"
                    continue
                return await self._fallback_or_abort(
                    state,
                    role=role,
                    context=context,
                    schema=schema,
                    available=available,
                    proposed_decision=proposed_decision,
                    failure=first_validation_failure,
                )
            if isinstance(error, (ModelProviderTimeoutError, TimeoutError)):
                kind = HarnessFailureKind.MODEL_TIMEOUT
                reason = f"{role} inference timed out"
            elif isinstance(
                error,
                (ModelProviderError, ModelNotConfiguredError, ConnectionError),
            ):
                kind = HarnessFailureKind.MODEL_PROVIDER_FAILURE
                reason = f"{role} inference provider failed"
            else:
                invalid = _HarnessAbort(
                    HarnessFailureKind.INVALID_MODEL_OUTPUT,
                    f"{role} returned invalid structured output",
                )
                if first_validation_failure is None:
                    first_validation_failure = invalid
                if attempt_kind == "primary":
                    attempt_kind = "repair"
                    continue
                return await self._fallback_or_abort(
                    state,
                    role=role,
                    context=context,
                    schema=schema,
                    available=available,
                    proposed_decision=proposed_decision,
                    failure=first_validation_failure,
                )

            state = self.get(state.run_id)
            if state.model_retry_count >= state.max_model_retries:
                return await self._fallback_or_abort(
                    state,
                    role=role,
                    context=context,
                    schema=schema,
                    available=available,
                    proposed_decision=proposed_decision,
                    failure=_HarnessAbort(kind, reason),
                )
            failure = HarnessFailureRecord(
                step_id=f"step_{state.step_count:04d}",
                kind=kind,
                concise_reason=reason,
                recoverable=True,
                retry_count=state.model_retry_count + 1,
            )
            state = self._replace(
                state,
                model_retry_count=state.model_retry_count + 1,
                failures=[*state.failures, failure],
            )
            self._emit(
                state,
                "model.retry",
                {
                    "role": role,
                    "kind": kind,
                    "attempt_kind": attempt_kind,
                    "retry_count": state.model_retry_count,
                },
            )

    async def _run_inference_attempt(
        self,
        run_id: str,
        *,
        client: InferenceClient,
        role: str,
        context: BaseModel,
        schema: type[BaseModel],
        attempt_kind: AttemptKind,
        validation_error_code: object | None = None,
        fallback_used: bool = False,
    ) -> InferenceAttemptOutcome:
        state = self.get(run_id)
        if state.model_call_count >= state.max_model_calls:
            raise _HarnessAbort(
                HarnessFailureKind.BUDGET_EXHAUSTED,
                "model-call budget reached before inference",
                status=InvestigationStatus.BUDGET_EXHAUSTED,
                recoverable=False,
            )
        state = self._replace(state, model_call_count=state.model_call_count + 1)
        self._emit(
            state,
            "agent.started",
            {
                "role": role,
                "provider": str(getattr(client, "provider", "unknown")),
                "model_identity": str(getattr(client, "model_identity", type(client).__name__)),
                "attempt_kind": attempt_kind,
                "context_version": str(getattr(context, "context_version", "unknown")),
                "fallback": fallback_used,
            },
        )
        started = perf_counter()
        common = {
            "call_id": f"call_{token_hex(12)}",
            "run_id": run_id,
            "step_id": str(getattr(context, "step_id", "unknown")),
            "role": role,
            "provider": str(getattr(client, "provider", "legacy")),
            "model_identity": str(getattr(client, "model_identity", type(client).__name__)),
            "output_schema": schema.__name__,
            "attempt_kind": attempt_kind,
            "context_version": str(getattr(context, "context_version", "unknown")),
            "context_fingerprint": str(
                getattr(context, "context_fingerprint", "0" * 64)
            ),
            "prompt_version": (
                SKEPTIC_PROMPT_VERSION if role == "skeptic" else CRITIC_PROMPT_VERSION
            ),
            "fallback_used": fallback_used,
        }
        decide_attempt = getattr(client, "decide_attempt", None)
        if callable(decide_attempt):
            try:
                return await asyncio.wait_for(
                    decide_attempt(
                        role=role,
                        context=context,
                        output_schema=schema,
                        attempt_kind=attempt_kind,
                        validation_error_code=(
                            str(validation_error_code)
                            if validation_error_code is not None
                            else None
                        ),
                        fallback_used=fallback_used,
                    ),
                    timeout=self.settings.inference_timeout_seconds,
                )
            except TimeoutError as exc:
                call = InferenceTraceRecord(
                    **common,
                    latency_ms=max(0, round((perf_counter() - started) * 1000)),
                    status="TIMEOUT",
                    schema_valid=False,
                    timeout=True,
                )
                return InferenceAttemptOutcome(call=call, error=exc)
        try:
            decision = await asyncio.wait_for(
                client.decide(role=role, context=context, output_schema=schema),
                timeout=self.settings.inference_timeout_seconds,
            )
        except (ModelProviderTimeoutError, TimeoutError) as exc:
            call = InferenceTraceRecord(
                **common,
                latency_ms=max(0, round((perf_counter() - started) * 1000)),
                status="TIMEOUT",
                schema_valid=False,
                timeout=True,
            )
            return InferenceAttemptOutcome(call=call, error=exc)
        except (ModelProviderError, ModelNotConfiguredError, ConnectionError) as exc:
            call = InferenceTraceRecord(
                **common,
                latency_ms=max(0, round((perf_counter() - started) * 1000)),
                status="PROVIDER_ERROR",
                schema_valid=False,
                provider_error_type=type(exc).__name__,
            )
            return InferenceAttemptOutcome(call=call, error=exc)
        except (InvalidModelOutputError, ValidationError, TypeError) as exc:
            call = InferenceTraceRecord(
                **common,
                latency_ms=max(0, round((perf_counter() - started) * 1000)),
                status="INVALID",
                schema_valid=False,
                validation_error_code=HarnessFailureKind.INVALID_MODEL_OUTPUT,
            )
            return InferenceAttemptOutcome(call=call, error=exc)
        call = InferenceTraceRecord(
            **common,
            latency_ms=max(0, round((perf_counter() - started) * 1000)),
            status="SUCCESS",
            schema_valid=True,
        )
        return InferenceAttemptOutcome(call=call, decision=decision)

    async def _fallback_or_abort(
        self,
        state: InvestigationState,
        *,
        role: str,
        context: BaseModel,
        schema: type[BaseModel],
        available: tuple[str, ...],
        proposed_decision: SkepticDecision | None,
        failure: _HarnessAbort,
    ) -> tuple[BaseModel, InferenceTraceRecord]:
        if not self.settings.agent_fallback_enabled or self.fallback_inference is None:
            raise failure from None
        self._emit(
            state,
            "inference.fallback",
            {
                "label": "AGENT_FALLBACK",
                "role": role,
                "reason_code": failure.kind,
                "provider": str(getattr(self.fallback_inference, "provider", "scripted")),
                "model_identity": str(
                    getattr(
                        self.fallback_inference,
                        "model_identity",
                        type(self.fallback_inference).__name__,
                    )
                ),
            },
        )
        outcome = await self._run_inference_attempt(
            state.run_id,
            client=self.fallback_inference,
            role=role,
            context=context,
            schema=schema,
            attempt_kind="primary",
            validation_error_code=failure.kind,
            fallback_used=True,
        )
        state = self.get(state.run_id)
        if outcome.error is not None or outcome.decision is None:
            self._record_inference_attempt(state, outcome.call)
            raise failure
        try:
            current = self.get(state.run_id)
            if current.context_version != context.context_version:
                raise _HarnessAbort(
                    HarnessFailureKind.INVALID_MODEL_OUTPUT,
                    f"{role} fallback response was produced from an obsolete context version",
                )
            decision = schema.model_validate(outcome.decision, strict=True)
            self._validate_inference_decision(
                current,
                role=role,
                decision=decision,
                available=available,
                proposed_decision=proposed_decision,
            )
        except (_HarnessAbort, ValidationError, TypeError):
            invalid_call = outcome.call.model_copy(
                update={
                    "status": "INVALID",
                    "schema_valid": False,
                    "validation_error_code": "AGENT_FALLBACK_INVALID",
                }
            )
            self._record_inference_attempt(state, invalid_call)
            raise failure from None
        self._record_inference_attempt(state, outcome.call)
        return decision, outcome.call

    def _validate_inference_decision(
        self,
        state: InvestigationState,
        *,
        role: str,
        decision: BaseModel,
        available: tuple[str, ...],
        proposed_decision: SkepticDecision | None,
    ) -> None:
        if role == "skeptic":
            skeptic = SkepticDecision.model_validate(decision, strict=True)
            self._validate_skeptic_identity(state, skeptic)
            self._validate_skeptic_budget_declaration(state, skeptic)
            self._validate_inferred_action(
                state, skeptic.requested_experiment, skeptic.parameters, available
            )
            return
        critic = CriticDecision.model_validate(decision, strict=True)
        if proposed_decision is None:
            raise _HarnessAbort(
                HarnessFailureKind.INVALID_MODEL_OUTPUT,
                "Critic inference is missing its bounded proposal",
            )
        self._validate_critic_identity(state, proposed_decision, critic)
        if critic.verdict == CriticVerdict.REVISE:
            if state.critic_revision_count >= state.max_critic_revisions:
                raise _HarnessAbort(
                    HarnessFailureKind.BUDGET_EXHAUSTED,
                    "Critic revision budget reached",
                    status=InvestigationStatus.BUDGET_EXHAUSTED,
                    recoverable=False,
                )
            self._validate_inferred_action(
                state,
                critic.revised_experiment or "",
                critic.revised_parameters or {},
                available,
            )

    def _validate_inferred_action(
        self,
        state: InvestigationState,
        tool_name: str,
        parameters: dict[str, Any],
        available: tuple[str, ...],
    ) -> None:
        if tool_name == STOP_ACTION:
            if tool_name not in available or parameters:
                raise _HarnessAbort(
                    HarnessFailureKind.UNAVAILABLE_ACTION,
                    "stop is not currently available or has invalid parameters",
                )
            return
        if state.tool_call_count >= state.max_tool_calls:
            raise _HarnessAbort(
                HarnessFailureKind.BUDGET_EXHAUSTED,
                "tool-call budget reached before inferred action",
                status=InvestigationStatus.BUDGET_EXHAUSTED,
                recoverable=False,
            )
        try:
            spec, validated_parameters = self.registry.validate_request(
                tool_name,
                parameters=parameters,
                granted_scopes=self.granted_scopes,
            )
        except UnknownToolError as exc:
            raise _HarnessAbort(
                HarnessFailureKind.UNKNOWN_ACTION,
                "model requested an unknown scientific action",
            ) from exc
        except ToolPermissionError as exc:
            raise _HarnessAbort(
                HarnessFailureKind.UNAUTHORIZED_ACTION,
                "model requested an action without the required scope",
            ) from exc
        except ActionValidationError as exc:
            raise _HarnessAbort(
                HarnessFailureKind.MALFORMED_PARAMETERS,
                "model requested malformed action parameters",
            ) from exc
        signature = self._action_signature(tool_name, validated_parameters)
        if any(
            item.action_signature == signature
            and item.status in {ToolExecutionStatus.PREPARED, ToolExecutionStatus.COMPLETED}
            for item in state.tool_executions
        ):
            raise _HarnessAbort(
                HarnessFailureKind.REPEATED_ACTION,
                f"identical action has already been accepted: {tool_name}",
            )
        if not spec.adaptive or tool_name not in available:
            raise _HarnessAbort(
                HarnessFailureKind.UNAVAILABLE_ACTION,
                f"adaptive action is not currently available: {tool_name}",
            )
        if spec.cost_units > state.adaptive_cost_units_remaining:
            raise _HarnessAbort(
                HarnessFailureKind.BUDGET_EXHAUSTED,
                f"adaptive action is unaffordable: {tool_name}",
                status=InvestigationStatus.BUDGET_EXHAUSTED,
                recoverable=False,
            )
        if missing_mandatory_tests(set(state.completed_tests)):
            raise _HarnessAbort(
                HarnessFailureKind.PRECONDITION_FAILED,
                "adaptive action cannot run before mandatory diagnostics complete",
            )
        if not spec.required_completed_tests.issubset(state.completed_tests):
            raise _HarnessAbort(
                HarnessFailureKind.PRECONDITION_FAILED,
                f"preconditions are incomplete for action {tool_name}",
            )

    def _record_inference_attempt(
        self, state: InvestigationState, call: InferenceTraceRecord
    ) -> InvestigationState:
        self._emit(state, "inference.attempt", call.model_dump(mode="json"))
        records = [
            InferenceTraceRecord.model_validate(event.payload)
            for event in self._events[state.run_id]
            if event.type == "inference.attempt"
        ]
        summary = derive_inference_summary(records)
        state = self._replace(self.get(state.run_id), inference_summary=summary)
        self.artifacts.write_inference_summary(state, summary)
        return state

    def _available_adaptive_actions(self, state: InvestigationState) -> tuple[str, ...]:
        completed = set(state.completed_tests)
        executed = {
            item.action_signature
            for item in state.tool_executions
            if item.status in {ToolExecutionStatus.PREPARED, ToolExecutionStatus.COMPLETED}
        }
        actions = tuple(
            spec.name
            for spec in self.registry.specs
            if spec.adaptive
            and self._spec_supported_for_target(state, spec)
            and spec.cost_units <= state.adaptive_cost_units_remaining
            and spec.required_completed_tests.issubset(completed)
            and self._action_signature(spec.name, {}) not in executed
        )
        return (*actions, STOP_ACTION) if actions else ()

    def _has_unaffordable_adaptive_action(self, state: InvestigationState) -> bool:
        completed = set(state.completed_tests)
        executed = {
            item.action_signature
            for item in state.tool_executions
            if item.status in {ToolExecutionStatus.PREPARED, ToolExecutionStatus.COMPLETED}
        }
        return any(
            spec.adaptive
            and self._spec_supported_for_target(state, spec)
            and spec.cost_units > state.adaptive_cost_units_remaining
            and spec.required_completed_tests.issubset(completed)
            and self._action_signature(spec.name, {}) not in executed
            for spec in self.registry.specs
        )

    def _validate_skeptic_identity(
        self, state: InvestigationState, decision: SkepticDecision
    ) -> None:
        expected_step = f"step_{state.step_count:04d}"
        if decision.role != "skeptic" or decision.run_id != state.run_id:
            raise _HarnessAbort(
                HarnessFailureKind.INVALID_MODEL_OUTPUT,
                "Skeptic role or run identifier does not match current state",
            )
        if decision.step_id != expected_step:
            raise _HarnessAbort(
                HarnessFailureKind.INVALID_MODEL_OUTPUT,
                "Skeptic step identifier is stale or mismatched",
            )
        if decision.context_version != state.context_version:
            raise _HarnessAbort(
                HarnessFailureKind.INVALID_MODEL_OUTPUT,
                "Skeptic context version is stale or mismatched",
            )

    def _validate_skeptic_budget_declaration(
        self, state: InvestigationState, decision: SkepticDecision
    ) -> None:
        if decision.budget_units_remaining != state.adaptive_cost_units_remaining:
            raise _HarnessAbort(
                HarnessFailureKind.INVALID_MODEL_OUTPUT,
                "Skeptic adaptive budget declaration is stale or mismatched",
            )
        if decision.requested_experiment == STOP_ACTION:
            if decision.cost_of_selected_experiment != 0:
                raise _HarnessAbort(
                    HarnessFailureKind.INVALID_MODEL_OUTPUT,
                    "Skeptic declared a nonzero cost for stop",
                )
            return
        try:
            spec = self.registry.resolve(decision.requested_experiment)
        except UnknownToolError:
            return
        if not spec.adaptive:
            return
        cost_units = spec.cost_units
        if decision.cost_of_selected_experiment != cost_units:
            raise _HarnessAbort(
                HarnessFailureKind.INVALID_MODEL_OUTPUT,
                "Skeptic declared cost does not match the authoritative tool registry",
            )

    def _adaptive_action_cost(self, action_name: str) -> int:
        return 0 if action_name == STOP_ACTION else self.registry.resolve(action_name).cost_units

    def _spec_supported_for_target(
        self, state: InvestigationState, spec: ScientificToolSpec
    ) -> bool:
        if not spec.implemented:
            return False
        if not spec.required_target_capabilities:
            return True
        supports = getattr(self.candidate_sources, "supports_capability", None)
        if not callable(supports):
            return False
        return all(
            bool(supports(state.opaque_target_id, capability))
            for capability in spec.required_target_capabilities
        )

    def _validate_critic_identity(
        self,
        state: InvestigationState,
        skeptic: SkepticDecision,
        critic: CriticDecision,
    ) -> None:
        if (
            critic.role != "critic"
            or critic.run_id != state.run_id
            or critic.step_id != skeptic.step_id
            or critic.context_version != state.context_version
            or critic.skeptic_decision_id != skeptic.decision_id
        ):
            raise _HarnessAbort(
                HarnessFailureKind.INVALID_MODEL_OUTPUT,
                "Critic role, run, step, context, or proposal identifier does not match",
            )

    async def _execute_action(
        self,
        state: InvestigationState,
        tool_name: str,
        parameters: dict[str, Any],
        *,
        adaptive: bool,
        agent_decision_id: str | None = None,
        critic_decision_id: str | None = None,
    ) -> ScientificToolResult:
        try:
            self._assert_science_admission_open(state)
        except ActionValidationError as exc:
            raise _HarnessAbort(
                HarnessFailureKind.UNAVAILABLE_ACTION,
                str(exc),
            ) from exc
        if state.tool_call_count >= state.max_tool_calls:
            raise _HarnessAbort(
                HarnessFailureKind.BUDGET_EXHAUSTED,
                "tool-call budget reached before execution",
                status=InvestigationStatus.BUDGET_EXHAUSTED,
                recoverable=False,
            )
        if adaptive and state.adaptive_experiments_used >= state.max_adaptive_experiments:
            raise _HarnessAbort(
                HarnessFailureKind.BUDGET_EXHAUSTED,
                "adaptive-experiment budget reached before execution",
                status=InvestigationStatus.BUDGET_EXHAUSTED,
                recoverable=False,
            )
        try:
            spec, validated_parameters = self.registry.validate_request(
                tool_name, parameters=parameters, granted_scopes=self.granted_scopes
            )
        except UnknownToolError as exc:
            raise _HarnessAbort(HarnessFailureKind.UNKNOWN_ACTION, str(exc)) from exc
        except ToolPermissionError as exc:
            raise _HarnessAbort(HarnessFailureKind.UNAUTHORIZED_ACTION, str(exc)) from exc
        except ActionValidationError as exc:
            raise _HarnessAbort(HarnessFailureKind.MALFORMED_PARAMETERS, str(exc)) from exc
        if adaptive and spec.cost_units > state.adaptive_cost_units_remaining:
            raise _HarnessAbort(
                HarnessFailureKind.BUDGET_EXHAUSTED,
                f"adaptive action cost exceeds remaining budget: {tool_name}",
                status=InvestigationStatus.BUDGET_EXHAUSTED,
                recoverable=False,
            )

        signature = self._action_signature(tool_name, validated_parameters)
        if any(
            item.action_signature == signature
            and item.status in {ToolExecutionStatus.PREPARED, ToolExecutionStatus.COMPLETED}
            for item in state.tool_executions
        ):
            raise _HarnessAbort(
                HarnessFailureKind.REPEATED_ACTION,
                f"identical action has already been accepted: {tool_name}",
            )

        if adaptive:
            available = self._available_adaptive_actions(state)
            if not spec.adaptive or tool_name not in available:
                raise _HarnessAbort(
                    HarnessFailureKind.UNAVAILABLE_ACTION,
                    f"adaptive action is not currently available: {tool_name}",
                )
            if missing_mandatory_tests(set(state.completed_tests)):
                raise _HarnessAbort(
                    HarnessFailureKind.PRECONDITION_FAILED,
                    "adaptive action cannot run before mandatory diagnostics complete",
                )
        elif spec.mandatory_test is None:
            raise _HarnessAbort(
                HarnessFailureKind.UNAVAILABLE_ACTION,
                f"controller cannot run non-mandatory action as baseline: {tool_name}",
            )
        if not spec.required_completed_tests.issubset(state.completed_tests):
            raise _HarnessAbort(
                HarnessFailureKind.PRECONDITION_FAILED,
                f"preconditions are incomplete for action {tool_name}",
            )

        action_id = f"action_{token_hex(8)}"
        runtime_inputs = self._runtime_inputs_for_action(state, spec, action_id)
        try:
            validated_runtime_inputs = self.registry.validate_runtime_inputs(
                spec, runtime_inputs
            )
            invocation_parameters = self.registry.invocation_parameters(
                tool_name,
                validated_parameters=validated_parameters,
                validated_runtime_inputs=validated_runtime_inputs,
            )
        except ActionValidationError as exc:
            raise _HarnessAbort(
                HarnessFailureKind.PRECONDITION_FAILED,
                str(exc),
                status=InvestigationStatus.INSUFFICIENT_EVIDENCE,
                recoverable=True,
            ) from exc
        execution = ToolExecutionRecord(
            action_id=action_id,
            step_id=f"step_{state.step_count:04d}",
            tool_name=tool_name,
            parameters=validated_parameters,
            action_signature=signature,
            status=ToolExecutionStatus.PREPARED,
            adaptive=adaptive,
            adaptive_cost_units=spec.cost_units if adaptive else 0,
            agent_decision_id=agent_decision_id,
            critic_decision_id=critic_decision_id,
        )
        state = self._replace(
            state,
            status=InvestigationStatus.RUNNING_TOOL,
            tool_call_count=state.tool_call_count + 1,
            adaptive_experiments_used=(
                state.adaptive_experiments_used + 1
                if adaptive
                else state.adaptive_experiments_used
            ),
            adaptive_cost_units_used=(
                state.adaptive_cost_units_used + spec.cost_units
                if adaptive
                else state.adaptive_cost_units_used
            ),
            adaptive_cost_units_remaining=(
                state.adaptive_cost_units_remaining - spec.cost_units
                if adaptive
                else state.adaptive_cost_units_remaining
            ),
            tool_executions=[*state.tool_executions, execution],
        )
        self._emit(
            state,
            "tool.started",
            {
                "tool_name": tool_name,
                "action_id": action_id,
                "parameters": validated_parameters,
                "adaptive": adaptive,
                "cost_units": spec.cost_units if adaptive else 0,
                "adaptive_cost_units_remaining": state.adaptive_cost_units_remaining,
            },
            action_id=action_id,
        )
        try:
            result = await self._invoke_tool_handler(
                state,
                spec,
                action_id,
                invocation_parameters,
            )
        except TimeoutError as exc:
            raise _HarnessAbort(
                HarnessFailureKind.TOOL_TIMEOUT,
                f"tool execution timed out for {tool_name}",
                recoverable=False,
                action_id=action_id,
            ) from exc
        except Exception as exc:
            raise _HarnessAbort(
                HarnessFailureKind.TOOL_INFRASTRUCTURE_FAILURE,
                f"tool infrastructure failure for {tool_name}: {type(exc).__name__}",
                recoverable=False,
                action_id=action_id,
            ) from exc
        if (
            result.tool_name != tool_name
            or result.run_id != state.run_id
            or result.action_id != action_id
            or result.target_id != state.opaque_target_id
        ):
            self._discard_staged_artifacts(state, spec, action_id)
            raise _HarnessAbort(
                HarnessFailureKind.TOOL_INFRASTRUCTURE_FAILURE,
                f"tool result identifiers do not match invocation for {tool_name}",
                recoverable=False,
                action_id=action_id,
            )
        try:
            _, result_parameters = self.registry.validate_parameters(
                result.tool_name,
                parameters=result.parameters,
            )
        except (ActionValidationError, ToolPermissionError, UnknownToolError) as exc:
            self._discard_staged_artifacts(state, spec, action_id)
            raise _HarnessAbort(
                HarnessFailureKind.TOOL_INFRASTRUCTURE_FAILURE,
                f"tool result validation failed for {tool_name}",
                recoverable=False,
                action_id=action_id,
            ) from exc
        if result_parameters != validated_parameters:
            self._discard_staged_artifacts(state, spec, action_id)
            raise _HarnessAbort(
                HarnessFailureKind.TOOL_INFRASTRUCTURE_FAILURE,
                f"tool result parameters do not match invocation for {tool_name}",
                recoverable=False,
                action_id=action_id,
            )
        try:
            self._promote_staged_artifacts(state, spec, action_id)
        except Exception as exc:
            self._discard_staged_artifacts(state, spec, action_id)
            raise _HarnessAbort(
                HarnessFailureKind.TOOL_INFRASTRUCTURE_FAILURE,
                f"tool artifact publication failed for {tool_name}: {type(exc).__name__}",
                recoverable=False,
                action_id=action_id,
            ) from exc
        return self._commit_result(state, result)

    async def _invoke_tool_handler(
        self,
        state: InvestigationState,
        spec: ScientificToolSpec,
        action_id: str,
        invocation_parameters: dict[str, Any],
    ) -> ScientificToolResult:
        """Run a synchronous tool behind a deadline and isolate late artifact writes."""

        if spec.execution_isolation == ExecutionIsolation.SUBPROCESS:
            return await self._invoke_subprocess_tool_handler(
                state, spec, action_id, invocation_parameters
            )

        abandoned = Event()
        stage_root = self._tool_stage_root(state, spec, action_id)

        def invoke() -> ScientificToolResult:
            try:
                return spec.handler(
                    state.run_id,
                    action_id,
                    state.opaque_target_id,
                    invocation_parameters,
                )
            finally:
                if abandoned.is_set():
                    self._discard_staged_artifacts(state, spec, action_id)

        future = asyncio.get_running_loop().run_in_executor(None, invoke)

        def consume_abandoned_result(done: asyncio.Future[ScientificToolResult]) -> None:
            if not abandoned.is_set():
                return
            if not done.cancelled():
                done.exception()
            if stage_root is not None:
                self._discard_staged_artifacts(state, spec, action_id)

        future.add_done_callback(consume_abandoned_result)
        try:
            return await asyncio.wait_for(
                asyncio.shield(future), timeout=spec.timeout_seconds
            )
        except asyncio.CancelledError:
            abandoned.set()
            if future.done() and stage_root is not None:
                self._discard_staged_artifacts(state, spec, action_id)
            raise
        except Exception:
            abandoned.set()
            if future.done() and stage_root is not None:
                self._discard_staged_artifacts(state, spec, action_id)
            raise

    async def _invoke_subprocess_tool_handler(
        self,
        state: InvestigationState,
        spec: ScientificToolSpec,
        action_id: str,
        invocation_parameters: dict[str, Any],
    ) -> ScientificToolResult:
        context = multiprocessing.get_context("spawn")
        receiver, sender = context.Pipe(duplex=False)
        process = context.Process(
            target=_subprocess_tool_entry,
            args=(
                sender,
                spec.handler,
                state.run_id,
                action_id,
                state.opaque_target_id,
                invocation_parameters,
            ),
            name=f"exoswarm-tool:{spec.name}:{action_id}",
            daemon=True,
        )
        message: tuple[str, Any] | None = None
        loop = asyncio.get_running_loop()
        deadline = loop.time() + spec.timeout_seconds
        try:
            process.start()
            sender.close()
            while loop.time() < deadline:
                if receiver.poll():
                    message = receiver.recv()
                    break
                if not process.is_alive():
                    break
                await asyncio.sleep(0.005)
            if message is None and receiver.poll():
                message = receiver.recv()
            if message is None:
                if process.is_alive():
                    self._terminate_tool_process(process)
                    raise TimeoutError(f"subprocess tool deadline reached: {spec.name}")
                raise _SubprocessToolError(
                    f"subprocess tool exited without a result: {spec.name}"
                )
            while process.is_alive() and loop.time() < deadline:
                await asyncio.sleep(0.005)
            if process.is_alive():
                self._terminate_tool_process(process)
                raise TimeoutError(f"subprocess tool did not exit by deadline: {spec.name}")
            process.join()
            kind, payload = message
            if kind == "error":
                raise _SubprocessToolError(
                    f"subprocess tool failed with {str(payload)[:100]}"
                )
            if kind != "result" or not isinstance(payload, ScientificToolResult):
                raise _SubprocessToolError("subprocess tool returned an invalid envelope")
            return payload
        except asyncio.CancelledError:
            if process.is_alive():
                self._terminate_tool_process(process)
            raise
        finally:
            receiver.close()
            sender.close()
            if process.is_alive():
                self._terminate_tool_process(process)
            process.close()

    @staticmethod
    def _terminate_tool_process(process: multiprocessing.Process) -> None:
        process.terminate()
        process.join(timeout=1)
        if process.is_alive():
            process.kill()
            process.join(timeout=1)

    def _tool_stage_root(
        self, state: InvestigationState, spec: ScientificToolSpec, action_id: str
    ) -> Path | None:
        if spec.name != "search_bls":
            return None
        run_dir = self.artifacts.run_dir(state.opaque_target_id, state.run_id).resolve()
        return run_dir / ".tool-staging" / action_id

    def _promote_staged_artifacts(
        self, state: InvestigationState, spec: ScientificToolSpec, action_id: str
    ) -> None:
        stage_root = self._tool_stage_root(state, spec, action_id)
        if stage_root is None:
            return
        staged_artifacts = stage_root / "artifacts"
        if not staged_artifacts.exists():
            return
        entries = list(staged_artifacts.iterdir())
        expected_name = f"{action_id}.candidate-search.json"
        if any(not item.is_file() or item.name != expected_name for item in entries):
            raise RuntimeError("candidate tool produced an unexpected staged artifact")
        destination_dir = (
            self.artifacts.run_dir(state.opaque_target_id, state.run_id) / "artifacts"
        )
        destination_dir.mkdir(parents=True, exist_ok=True)
        for staged in entries:
            destination = destination_dir / staged.name
            if destination.exists():
                if destination.read_bytes() != staged.read_bytes():
                    raise RuntimeError("candidate artifact conflicts with durable output")
                staged.unlink()
            else:
                staged.replace(destination)
        self._discard_staged_artifacts(state, spec, action_id)

    def _discard_staged_artifacts(
        self, state: InvestigationState, spec: ScientificToolSpec, action_id: str
    ) -> None:
        stage_root = self._tool_stage_root(state, spec, action_id)
        if stage_root is None:
            return
        run_dir = self.artifacts.run_dir(state.opaque_target_id, state.run_id).resolve()
        stage_parent = (run_dir / ".tool-staging").resolve()
        resolved = stage_root.resolve()
        if resolved.parent != stage_parent:
            raise RuntimeError("tool staging path escaped the run boundary")
        if resolved.exists():
            shutil.rmtree(resolved, ignore_errors=True)
        with suppress(OSError):
            stage_parent.rmdir()

    def _runtime_inputs_for_action(
        self,
        state: InvestigationState,
        spec: ScientificToolSpec,
        action_id: str,
    ) -> dict[str, Any]:
        if spec.runtime_input_schema is None:
            return {}
        if spec.name in {
            "odd_even",
            "secondary_eclipse",
            "harmonic_test",
            "contamination_screening",
        }:
            return {"candidate_artifact_path": self._candidate_artifact_path(state)}
        if spec.name != "search_bls":
            raise _HarnessAbort(
                HarnessFailureKind.PRECONDITION_FAILED,
                f"no controller-owned runtime input boundary exists for {spec.name}",
                status=InvestigationStatus.INSUFFICIENT_EVIDENCE,
                recoverable=True,
            )
        if self.candidate_sources is None:
            raise _HarnessAbort(
                HarnessFailureKind.PRECONDITION_FAILED,
                "search_bls requires a configured backend-owned cached candidate source",
                status=InvestigationStatus.INSUFFICIENT_EVIDENCE,
                recoverable=True,
            )
        try:
            source = self.candidate_sources.resolve(state.opaque_target_id)
        except LookupError as exc:
            raise _HarnessAbort(
                HarnessFailureKind.PRECONDITION_FAILED,
                "search_bls has no backend-owned cached candidate source for this opaque target",
                status=InvestigationStatus.INSUFFICIENT_EVIDENCE,
                recoverable=True,
            ) from exc
        stage_root = self._tool_stage_root(state, spec, action_id)
        assert stage_root is not None
        return {
            "cached_path": source.cached_path,
            "artifact_dir": stage_root / "artifacts",
            "ledger_path": self.artifacts.evidence_path(state),
            "step_id": f"step_{state.step_count:04d}",
            "write_evidence": False,
        }

    def _candidate_artifact_path(self, state: InvestigationState) -> Path:
        artifact_ref: str | None = None
        for record in reversed(self.artifacts.read_evidence(state)):
            if record.tool_name != "search_bls" or record.tool_status != ToolStatus.SUCCESS:
                continue
            candidate_ref = record.result.diagnostics.get("masks_artifact_ref")
            if isinstance(candidate_ref, str):
                artifact_ref = candidate_ref
                break
        if artifact_ref is None:
            raise _HarnessAbort(
                HarnessFailureKind.PRECONDITION_FAILED,
                "candidate-dependent vetting requires committed search_bls candidate evidence",
                status=InvestigationStatus.INSUFFICIENT_EVIDENCE,
                recoverable=True,
            )

        relative = PurePosixPath(artifact_ref)
        if (
            relative.is_absolute()
            or len(relative.parts) != 2
            or relative.parts[0] != "artifacts"
            or relative.suffix != ".json"
            or any(part in {"", ".", ".."} for part in relative.parts)
        ):
            raise _HarnessAbort(
                HarnessFailureKind.PRECONDITION_FAILED,
                "search_bls candidate artifact reference is outside the run artifact boundary",
                status=InvestigationStatus.INSUFFICIENT_EVIDENCE,
                recoverable=False,
            )
        run_dir = self.artifacts.run_dir(state.opaque_target_id, state.run_id).resolve()
        artifact_root = (run_dir / "artifacts").resolve()
        artifact_path = (run_dir / Path(*relative.parts)).resolve()
        if not artifact_path.is_relative_to(artifact_root) or not artifact_path.is_file():
            raise _HarnessAbort(
                HarnessFailureKind.PRECONDITION_FAILED,
                "committed search_bls candidate artifact is unavailable",
                status=InvestigationStatus.INSUFFICIENT_EVIDENCE,
                recoverable=True,
            )
        return artifact_path

    def _commit_result(
        self, state: InvestigationState, result: ScientificToolResult
    ) -> ScientificToolResult:
        self._assert_science_admission_open(state)
        execution = next(
            (item for item in state.tool_executions if item.action_id == result.action_id), None
        )
        if execution is None:
            raise ValueError("tool result has no matching prepared execution")
        if (
            execution.status != ToolExecutionStatus.PREPARED
            or result.tool_name != execution.tool_name
            or result.run_id != state.run_id
            or result.target_id != state.opaque_target_id
        ):
            raise ValueError("tool result does not match its prepared execution")
        _, result_parameters = self.registry.validate_parameters(
            result.tool_name,
            parameters=result.parameters,
        )
        if result_parameters != execution.parameters:
            raise ValueError("tool result parameters do not match its prepared execution")
        interpretation = result.diagnostics.get("interpretation_code")
        interpretation_code = interpretation if isinstance(interpretation, str) else None
        evidence_id = self._evidence_id(result)
        record = EvidenceRecord(
            evidence_id=evidence_id,
            run_id=state.run_id,
            step_id=execution.step_id,
            action_id=result.action_id,
            opaque_target_id=state.opaque_target_id,
            tool_name=result.tool_name,
            tool_status=result.status,
            result=result,
            interpretation_code=interpretation_code,
            agent_decision_id=execution.agent_decision_id,
            critic_decision_id=execution.critic_decision_id,
        )
        self.artifacts.append_evidence(state, record)

        spec = self.registry.resolve(result.tool_name)
        completed = list(state.completed_tests)
        if (
            spec.mandatory_test
            and result.status in _SUCCESSFUL_TEST_STATUSES
            and spec.mandatory_test not in completed
        ):
            completed.append(spec.mandatory_test)
        candidates = self._updated_candidates(state, result, evidence_id)
        hypotheses, strongest = updated_hypotheses(state, interpretation_code)
        executions = [
            item.model_copy(
                update={
                    "status": (
                        ToolExecutionStatus.FAILED
                        if result.status == ToolStatus.FAILED
                        else ToolExecutionStatus.COMPLETED
                    ),
                    "result_status": result.status,
                    "evidence_ref": evidence_id,
                    "failure_kind": (
                        HarnessFailureKind.TOOL_INFRASTRUCTURE_FAILURE
                        if result.status == ToolStatus.FAILED
                        else None
                    ),
                    "failure_reason": (
                        result.reason or f"tool returned FAILED: {result.tool_name}"
                        if result.status == ToolStatus.FAILED
                        else None
                    ),
                }
            )
            if item.action_id == result.action_id
            else item
            for item in state.tool_executions
        ]
        state = self._replace(
            state,
            status=InvestigationStatus.UPDATING_EVIDENCE,
            evidence_refs=[*state.evidence_refs, evidence_id],
            completed_tests=completed,
            candidate_signals=candidates,
            active_hypotheses=hypotheses,
            strongest_unresolved_alternative=strongest,
            tool_executions=executions,
            context_version=str(int(state.context_version) + 1),
        )
        self._assert_numerical_provenance(state)
        self._emit(
            state,
            "tool.completed",
            {
                "tool_name": result.tool_name,
                "action_id": result.action_id,
                "status": result.status,
                "evidence_ref": evidence_id,
            },
            action_id=result.action_id,
        )
        self._emit(
            state,
            "evidence.appended",
            {
                "evidence_id": evidence_id,
                "tool_name": result.tool_name,
                "status": result.status,
                "interpretation_code": interpretation_code,
            },
            action_id=result.action_id,
        )
        return result

    def _after_result(
        self, state: InvestigationState, result: ScientificToolResult
    ) -> InvestigationState:
        execution = next(
            (item for item in state.tool_executions if item.action_id == result.action_id), None
        )
        if result.status == ToolStatus.FAILED:
            return self._terminate(
                state,
                HarnessFailureKind.TOOL_INFRASTRUCTURE_FAILURE,
                f"tool returned FAILED: {result.tool_name}",
                recoverable=False,
                action_id=result.action_id,
            )
        if result.status == ToolStatus.PRECONDITION_FAILED:
            if execution is not None and execution.adaptive:
                alternatives = tuple(
                    dict.fromkeys(
                        name
                        for name in result.suggested_alternatives
                        if name in self._available_adaptive_actions(state)
                    )
                )
                failure = HarnessFailureRecord(
                    step_id=f"step_{state.step_count:04d}",
                    kind=HarnessFailureKind.PRECONDITION_FAILED,
                    concise_reason=f"scientific precondition failed: {result.tool_name}",
                    recoverable=True,
                    retry_count=state.model_retry_count,
                )
                if self._available_adaptive_actions(state):
                    state = self._replace(
                        state,
                        status=InvestigationStatus.SELECTING_ADAPTIVE_EXPERIMENT,
                        failures=[*state.failures, failure],
                    )
                    self._emit(
                        state,
                        "status.changed",
                        {
                            "status": state.status,
                            "reason_code": HarnessFailureKind.PRECONDITION_FAILED,
                            "failed_tool": result.tool_name,
                            "suggested_alternatives": list(alternatives),
                            "recoverable": True,
                        },
                    )
                    return state
                return self._finalize(
                    self._replace(state, failures=[*state.failures, failure]),
                    f"PRECONDITION_REPLAN_EXHAUSTED:{result.tool_name}",
                )
            return self._terminate(
                state,
                HarnessFailureKind.PRECONDITION_FAILED,
                f"scientific PRECONDITION_FAILED: {result.tool_name}",
                status=InvestigationStatus.INSUFFICIENT_EVIDENCE,
                recoverable=True,
            )
        if result.status == ToolStatus.NOT_IMPLEMENTED:
            return self._terminate(
                state,
                HarnessFailureKind.INSUFFICIENT_EVIDENCE,
                f"required scientific action is not implemented: {result.tool_name}",
                status=InvestigationStatus.INSUFFICIENT_EVIDENCE,
                recoverable=True,
            )
        if missing_mandatory_tests(set(state.completed_tests)):
            return self._replace(state, status=InvestigationStatus.VETTING_MANDATORY)
        codes = {
            record.interpretation_code
            for record in self.artifacts.read_evidence(state)
            if record.interpretation_code
        }
        decisive = decisive_interpretation(codes)
        if decisive is not None:
            return self._finalize(state, f"DETERMINISTIC_EVIDENCE:{decisive}")
        if execution is not None and execution.adaptive:
            budget_reason = adaptive_budget_terminal_reason(state)
            if budget_reason is not None:
                return self._finalize(state, budget_reason)
            if not self._available_adaptive_actions(state):
                return self._finalize(state, "NO_AVAILABLE_ADAPTIVE_ACTION")
            return self._replace(
                state, status=InvestigationStatus.SELECTING_ADAPTIVE_EXPERIMENT
            )
        if (
            result.status in {ToolStatus.NO_EVIDENCE, ToolStatus.INDETERMINATE}
            and state.adaptive_experiments_used >= state.max_adaptive_experiments
        ):
            return self._finalize(state, f"SCIENTIFIC_{result.status}")
        return self._replace(state, status=InvestigationStatus.SELECTING_ADAPTIVE_EXPERIMENT)

    def _finalize(self, state: InvestigationState, reason: str) -> InvestigationState:
        if missing_mandatory_tests(set(state.completed_tests)):
            return self._terminate(
                state,
                HarnessFailureKind.INSUFFICIENT_EVIDENCE,
                "mandatory diagnostics are incomplete",
                status=InvestigationStatus.INSUFFICIENT_EVIDENCE,
                recoverable=False,
            )
        codes = {
            record.interpretation_code
            for record in self.artifacts.read_evidence(state)
            if record.interpretation_code
        }
        if "ODD_EVEN_MISMATCH" in codes or "CONTAMINATION_LIKELY" in codes:
            disposition = Disposition.PLANETARY_INTERPRETATION_REJECTED
        elif "WEAK_NOISY" in codes:
            return self._terminate(
                state,
                HarnessFailureKind.INSUFFICIENT_EVIDENCE,
                f"{reason}: evidence remains weak or inconclusive",
                status=InvestigationStatus.INSUFFICIENT_EVIDENCE,
                recoverable=False,
            )
        elif has_weak_planetary_interpretation(codes):
            disposition = Disposition.PLANETARY_INTERPRETATION_WEAK
        elif "CLEAN_PLANET_LIKE" in codes or state.candidate_signals:
            disposition = Disposition.PLANETARY_INTERPRETATION_SURVIVES_IMPLEMENTED_VETTING
        else:
            return self._terminate(
                state,
                HarnessFailureKind.INSUFFICIENT_EVIDENCE,
                f"{reason}: no deterministic disposition rule is satisfied",
                status=InvestigationStatus.INSUFFICIENT_EVIDENCE,
                recoverable=False,
            )
        state = self._replace(
            state,
            status=InvestigationStatus.READY_TO_LOCK,
            disposition=disposition,
            terminal_reason=reason,
        )
        state = self._persist_terminal_inference_summary(state)
        self._emit(
            state,
            "status.changed",
            {"status": state.status, "terminal_reason": reason, "disposition": disposition},
        )
        return state

    def _terminate(
        self,
        state: InvestigationState,
        kind: HarnessFailureKind,
        reason: str,
        *,
        status: InvestigationStatus = InvestigationStatus.FAILED,
        recoverable: bool = True,
        action_id: str | None = None,
    ) -> InvestigationState:
        failure = HarnessFailureRecord(
            step_id=f"step_{state.step_count:04d}",
            kind=kind,
            concise_reason=reason,
            recoverable=recoverable,
            retry_count=state.model_retry_count,
        )
        executions = [
            item.model_copy(
                update={
                    "status": ToolExecutionStatus.FAILED,
                    "failure_kind": kind,
                    "failure_reason": reason,
                }
            )
            if item.action_id == action_id
            else item
            for item in state.tool_executions
        ]
        state = self._replace(
            state,
            status=status,
            terminal_reason=f"{kind}:{reason}",
            failures=[*state.failures, failure],
            tool_executions=executions,
        )
        state = self._persist_terminal_inference_summary(state)
        if action_id is not None:
            self._emit(
                state,
                "tool.failed",
                {
                    "action_id": action_id,
                    "failure_kind": kind,
                    "concise_reason": reason,
                    "recoverable": recoverable,
                },
                action_id=action_id,
            )
        self._emit(
            state,
            "run.failed" if status == InvestigationStatus.FAILED else "status.changed",
            {
                "status": status,
                "failure_kind": kind,
                "terminal_reason": state.terminal_reason,
                "recoverable": recoverable,
            },
        )
        return state

    def _persist_terminal_inference_summary(self, state: InvestigationState) -> InvestigationState:
        records = [
            InferenceTraceRecord.model_validate(event.payload)
            for event in self._events[state.run_id]
            if event.type == "inference.attempt"
        ]
        summary = derive_inference_summary(records)
        if summary != state.inference_summary:
            state = self._replace(state, inference_summary=summary)
        self.artifacts.write_inference_summary(state, summary)
        self._emit(
            state,
            "inference.summary",
            summary.model_dump(mode="json"),
        )
        _LOGGER.info(concise_inference_summary(summary))
        return state

    async def _recover_prepared_execution(
        self, state: InvestigationState
    ) -> InvestigationState:
        prepared = [
            item for item in state.tool_executions if item.status == ToolExecutionStatus.PREPARED
        ]
        if not prepared:
            return state
        existing = {record.action_id: record for record in self.artifacts.read_evidence(state)}
        for execution in prepared:
            if execution.action_id in existing:
                try:
                    state = self._commit_recovered_record(
                        state, existing[execution.action_id]
                    )
                except ActionValidationError as exc:
                    raise _HarnessAbort(
                        HarnessFailureKind.TOOL_INFRASTRUCTURE_FAILURE,
                        f"persisted evidence validation failed for {execution.tool_name}",
                        recoverable=False,
                        action_id=execution.action_id,
                    ) from exc
                result = existing[execution.action_id].result
            else:
                try:
                    spec, recovered_parameters = self.registry.validate_request(
                        execution.tool_name,
                        parameters=execution.parameters,
                        granted_scopes=self.granted_scopes,
                    )
                except ToolPermissionError as exc:
                    raise _HarnessAbort(
                        HarnessFailureKind.UNAUTHORIZED_ACTION,
                        f"prepared action is no longer authorized: {execution.tool_name}",
                        recoverable=False,
                        action_id=execution.action_id,
                    ) from exc
                except (ActionValidationError, UnknownToolError) as exc:
                    raise _HarnessAbort(
                        HarnessFailureKind.TOOL_INFRASTRUCTURE_FAILURE,
                        f"prepared action is invalid after restart: {execution.tool_name}",
                        recoverable=False,
                        action_id=execution.action_id,
                    ) from exc
                if not spec.idempotent:
                    raise _HarnessAbort(
                        HarnessFailureKind.TOOL_INFRASTRUCTURE_FAILURE,
                        f"cannot safely resume non-idempotent action {execution.tool_name}",
                        recoverable=False,
                        action_id=execution.action_id,
                    )
                try:
                    runtime_inputs = self._runtime_inputs_for_action(
                        state, spec, execution.action_id
                    )
                    validated_runtime_inputs = self.registry.validate_runtime_inputs(
                        spec, runtime_inputs
                    )
                    invocation_parameters = self.registry.invocation_parameters(
                        execution.tool_name,
                        validated_parameters=recovered_parameters,
                        validated_runtime_inputs=validated_runtime_inputs,
                    )
                    result = await self._invoke_tool_handler(
                        state,
                        spec,
                        execution.action_id,
                        invocation_parameters,
                    )
                except TimeoutError as exc:
                    raise _HarnessAbort(
                        HarnessFailureKind.TOOL_TIMEOUT,
                        f"tool execution timed out while recovering {execution.tool_name}",
                        recoverable=False,
                        action_id=execution.action_id,
                    ) from exc
                except _HarnessAbort as exc:
                    raise _HarnessAbort(
                        exc.kind,
                        exc.reason,
                        status=exc.status,
                        recoverable=exc.recoverable,
                        action_id=execution.action_id,
                    ) from exc
                except Exception as exc:
                    raise _HarnessAbort(
                        HarnessFailureKind.TOOL_INFRASTRUCTURE_FAILURE,
                        "tool infrastructure failure while recovering "
                        f"{execution.tool_name}: {type(exc).__name__}",
                        recoverable=False,
                        action_id=execution.action_id,
                    ) from exc
                if (
                    result.tool_name != execution.tool_name
                    or result.run_id != state.run_id
                    or result.action_id != execution.action_id
                    or result.target_id != state.opaque_target_id
                ):
                    self._discard_staged_artifacts(
                        state, spec, execution.action_id
                    )
                    raise _HarnessAbort(
                        HarnessFailureKind.TOOL_INFRASTRUCTURE_FAILURE,
                        "tool result identifiers do not match recovered invocation for "
                        f"{execution.tool_name}",
                        recoverable=False,
                        action_id=execution.action_id,
                    )
                try:
                    _, result_parameters = self.registry.validate_parameters(
                        result.tool_name,
                        parameters=result.parameters,
                    )
                    if result_parameters != recovered_parameters:
                        raise ActionValidationError(
                            "recovered tool result parameters do not match invocation"
                        )
                    self._promote_staged_artifacts(
                        state, spec, execution.action_id
                    )
                    self._commit_result(state, result)
                except (ActionValidationError, RuntimeError, ValueError) as exc:
                    self._discard_staged_artifacts(
                        state, spec, execution.action_id
                    )
                    raise _HarnessAbort(
                        HarnessFailureKind.TOOL_INFRASTRUCTURE_FAILURE,
                        f"tool result validation failed while recovering {execution.tool_name}",
                        recoverable=False,
                        action_id=execution.action_id,
                    ) from exc
                state = self.get(state.run_id)
                self._emit(
                    state,
                    "recovery.completed",
                    {
                        "action_id": execution.action_id,
                        "evidence_ref": next(
                            item.evidence_ref
                            for item in state.tool_executions
                            if item.action_id == execution.action_id
                        ),
                        "result_status": result.status,
                        "reexecuted": True,
                    },
                    action_id=execution.action_id,
                )
        return state

    def _commit_recovered_record(
        self, state: InvestigationState, record: EvidenceRecord
    ) -> InvestigationState:
        self._assert_science_admission_open(state)
        execution = next(
            (item for item in state.tool_executions if item.action_id == record.action_id), None
        )
        if (
            execution is None
            or execution.status != ToolExecutionStatus.PREPARED
            or execution.tool_name != record.tool_name
            or record.run_id != state.run_id
            or record.opaque_target_id != state.opaque_target_id
        ):
            raise _HarnessAbort(
                HarnessFailureKind.TOOL_INFRASTRUCTURE_FAILURE,
                "persisted evidence does not match its prepared execution",
                recoverable=False,
                action_id=record.action_id,
            )
        _, result_parameters = self.registry.validate_parameters(
            record.tool_name,
            parameters=record.result.parameters,
        )
        if result_parameters != execution.parameters:
            raise _HarnessAbort(
                HarnessFailureKind.TOOL_INFRASTRUCTURE_FAILURE,
                "persisted evidence parameters do not match prepared execution",
                recoverable=False,
                action_id=record.action_id,
            )
        spec = self.registry.resolve(record.tool_name)
        completed = list(state.completed_tests)
        if (
            spec.mandatory_test
            and record.tool_status in _SUCCESSFUL_TEST_STATUSES
            and spec.mandatory_test not in completed
        ):
            completed.append(spec.mandatory_test)
        executions = [
            item.model_copy(
                update={
                    "status": (
                        ToolExecutionStatus.FAILED
                        if record.tool_status == ToolStatus.FAILED
                        else ToolExecutionStatus.COMPLETED
                    ),
                    "result_status": record.tool_status,
                    "evidence_ref": record.evidence_id,
                    "failure_kind": (
                        HarnessFailureKind.TOOL_INFRASTRUCTURE_FAILURE
                        if record.tool_status == ToolStatus.FAILED
                        else None
                    ),
                    "failure_reason": (
                        record.result.reason
                        or f"tool returned FAILED: {record.tool_name}"
                        if record.tool_status == ToolStatus.FAILED
                        else None
                    ),
                }
            )
            if item.action_id == record.action_id
            else item
            for item in state.tool_executions
        ]
        evidence_refs = list(state.evidence_refs)
        if record.evidence_id not in evidence_refs:
            evidence_refs.append(record.evidence_id)
        hypotheses, strongest = updated_hypotheses(state, record.interpretation_code)
        state = self._replace(
            state,
            status=InvestigationStatus.UPDATING_EVIDENCE,
            evidence_refs=evidence_refs,
            completed_tests=completed,
            candidate_signals=self._updated_candidates(
                state, record.result, record.evidence_id
            ),
            active_hypotheses=hypotheses,
            strongest_unresolved_alternative=strongest,
            tool_executions=executions,
            context_version=str(int(state.context_version) + 1),
        )
        self._assert_numerical_provenance(state)
        self._emit(
            state,
            "recovery.completed",
            {
                "action_id": record.action_id,
                "evidence_ref": record.evidence_id,
                "result_status": record.tool_status,
                "reexecuted": False,
            },
            action_id=record.action_id,
        )
        return state

    def _updated_candidates(
        self, state: InvestigationState, result: ScientificToolResult, evidence_id: str
    ) -> list[CandidateSignal]:
        if result.tool_name != "search_bls" or result.status != ToolStatus.SUCCESS:
            return state.candidate_signals
        measurements = {
            name: Measurement.model_validate(
                {**measurement.model_dump(mode="python"), "evidence_ref": evidence_id}
            )
            for name, measurement in result.measurements.items()
        }
        return [
            CandidateSignal(
                candidate_id=str(result.diagnostics.get("candidate_id", "candidate_1")),
                evidence_refs=[evidence_id],
                measurements=measurements,
            )
        ]

    def _assert_numerical_provenance(self, state: InvestigationState) -> None:
        records = {record.evidence_id: record for record in self.artifacts.read_evidence(state)}
        for candidate in state.candidate_signals:
            for name, measurement in candidate.measurements.items():
                if not measurement.evidence_ref or measurement.evidence_ref not in records:
                    raise RuntimeError(f"candidate measurement lacks evidence: {name}")
                source = records[measurement.evidence_ref].result.measurements.get(name)
                if (
                    source is None
                    or source.value != measurement.value
                    or source.unit != measurement.unit
                ):
                    raise RuntimeError(f"candidate measurement differs from evidence: {name}")

    @staticmethod
    def _evidence_id(result: ScientificToolResult) -> str:
        canonical = json.dumps(
            result.model_dump(mode="json"), separators=(",", ":"), sort_keys=True
        ).encode()
        return f"evidence_{hashlib.sha256(canonical).hexdigest()[:20]}"

    @staticmethod
    def _action_signature(tool_name: str, parameters: dict[str, Any]) -> str:
        canonical = json.dumps(
            {"tool_name": tool_name, "parameters": parameters},
            default=str,
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
        return hashlib.sha256(canonical).hexdigest()

    def _replace(self, state: InvestigationState, **changes: Any) -> InvestigationState:
        requested_status = changes.get("status", state.status)
        validate_status_transition(state.status, InvestigationStatus(requested_status))
        payload = state.model_dump(mode="python")
        payload.update(changes)
        payload["updated_at"] = datetime.now(UTC)
        updated = InvestigationState.model_validate(payload)
        self.artifacts.save_state(updated)
        self._states[state.run_id] = updated
        return updated

    def _emit(
        self,
        state: InvestigationState,
        event_type: str,
        payload: dict[str, object],
        *,
        action_id: str | None = None,
    ) -> None:
        event = self._event(state, event_type, payload, action_id=action_id)
        self.artifacts.append_trace(state, event)
        self._events[state.run_id].append(event)

    def _event(
        self,
        state: InvestigationState,
        event_type: str,
        payload: dict[str, object],
        *,
        action_id: str | None = None,
    ) -> InvestigationEvent:
        sequence = len(self._events[state.run_id]) + 1
        return InvestigationEvent(
            event_id=f"evt_{token_hex(8)}",
            run_id=state.run_id,
            step_id=f"step_{state.step_count:04d}",
            action_id=action_id or f"action_{token_hex(8)}",
            sequence=sequence,
            timestamp=datetime.now(UTC),
            type=event_type,
            payload=payload,
        )

    @staticmethod
    def _budget_payload(state: InvestigationState) -> dict[str, object]:
        return {
            "step_count": state.step_count,
            "model_call_count": state.model_call_count,
            "tool_call_count": state.tool_call_count,
            "adaptive_experiments_used": state.adaptive_experiments_used,
            "max_adaptive_cost_units": state.max_adaptive_cost_units,
            "adaptive_cost_units_used": state.adaptive_cost_units_used,
            "adaptive_cost_units_remaining": state.adaptive_cost_units_remaining,
            "critic_revision_count": state.critic_revision_count,
            "model_retry_count": state.model_retry_count,
        }

    @staticmethod
    def _assert_science_admission_open(state: InvestigationState) -> None:
        if (
            state.lock_state != LockState.GROUND_TRUTH_LOCKED
            or InvestigationController._cannot_advance(state)
        ):
            raise ActionValidationError(
                "scientific result admission is unavailable after lock eligibility "
                "or terminal state"
            )

    @staticmethod
    def _cannot_advance(state: InvestigationState) -> bool:
        return state.status in {
            InvestigationStatus.READY_TO_LOCK,
            InvestigationStatus.RESULT_LOCKED,
            InvestigationStatus.REVEALED,
            InvestigationStatus.INSUFFICIENT_EVIDENCE,
            InvestigationStatus.REJECTED,
            InvestigationStatus.FAILED,
            InvestigationStatus.BUDGET_EXHAUSTED,
        }
