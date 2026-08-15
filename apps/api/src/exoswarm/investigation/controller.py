from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from secrets import token_hex
from typing import Any

from pydantic import BaseModel, ValidationError

from exoswarm.agents.context import assemble_context
from exoswarm.agents.model_client import InferenceClient, UnconfiguredInferenceClient
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
    InvestigationState,
    LockReceipt,
    Measurement,
    RevealResult,
    ScientificToolResult,
    SkepticDecision,
    ToolExecutionRecord,
)
from exoswarm.investigation.mandatory import missing_mandatory_tests
from exoswarm.investigation.runtime_inputs import CandidateSourceResolver
from exoswarm.investigation.state import validate_status_transition
from exoswarm.investigation.tool_registry import ScientificToolRegistry, scaffold_tool_registry
from exoswarm.science.contracts import ScientificToolSpec
from exoswarm.security.catalog_gate import CatalogGate
from exoswarm.security.result_lock import ResultLockService
from exoswarm.services.artifacts import FileSystemRunArtifactStore

_SUCCESSFUL_TEST_STATUSES = frozenset(
    {ToolStatus.SUCCESS, ToolStatus.NO_EVIDENCE, ToolStatus.INDETERMINATE}
)
_DECISIVE_INTERPRETATIONS = frozenset(
    {"CLEAN_PLANET_LIKE", "ODD_EVEN_MISMATCH", "CONTAMINATION_LIKELY", "WEAK_NOISY"}
)


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
        registry: ScientificToolRegistry | None = None,
        candidate_sources: CandidateSourceResolver | None = None,
        granted_scopes: set[str] | frozenset[str] = frozenset({"science:execute"}),
    ) -> None:
        self.settings = settings
        self.artifacts = artifacts
        self.result_lock = result_lock
        self.catalog_gate = catalog_gate
        self.inference = inference or UnconfiguredInferenceClient()
        self.registry = registry or scaffold_tool_registry()
        self.candidate_sources = candidate_sources
        self.granted_scopes = frozenset(granted_scopes)
        self._states: dict[str, InvestigationState] = {}
        self._events: dict[str, list[InvestigationEvent]] = {}

    def create(self, opaque_target_id: str) -> InvestigationState:
        run_id = f"run_{token_hex(8)}"
        state = InvestigationState(
            run_id=run_id,
            opaque_target_id=opaque_target_id,
            available_tests=list(self.registry.names),
            max_steps=self.settings.max_steps,
            max_adaptive_experiments=self.settings.max_adaptive_experiments,
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
        self._events[run_id].append(event)
        self.artifacts.append_trace(updated, event)
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

    def record_tool_result(self, run_id: str, result: ScientificToolResult) -> InvestigationState:
        """Admit an already deterministic result, including test/eval fixture results."""

        state = self.get(run_id)
        self._assert_science_admission_open(state)
        _, validated_parameters = self.registry.validate_parameters(
            result.tool_name,
            parameters=result.parameters,
        )
        if result.run_id != run_id or result.target_id != state.opaque_target_id:
            raise ValueError("tool result identifiers do not match the durable investigation")
        if state.tool_call_count >= state.max_tool_calls:
            raise ValueError("tool-call budget is exhausted")
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
        )
        state = self._replace(
            state,
            tool_call_count=state.tool_call_count + 1,
            tool_executions=[*state.tool_executions, execution],
        )
        self._commit_result(state, result)
        return self.get(run_id)

    async def advance(self, run_id: str) -> InvestigationState:
        """Advance one durable, bounded controller cycle and return its checkpointed state."""

        state = self.get(run_id)
        if self._cannot_advance(state):
            return state
        try:
            state = self._recover_prepared_execution(state)
            if self._cannot_advance(state):
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

            missing = missing_mandatory_tests(set(state.completed_tests))
            if missing:
                return self._run_next_mandatory(state, missing)
            if not state.candidate_signals:
                return self._terminate(
                    state,
                    HarnessFailureKind.INSUFFICIENT_EVIDENCE,
                    "mandatory baseline completed without candidate evidence",
                    status=InvestigationStatus.INSUFFICIENT_EVIDENCE,
                    recoverable=False,
                )
            if state.adaptive_experiments_used >= state.max_adaptive_experiments:
                return self._finalize(state, "ADAPTIVE_EXPERIMENT_BUDGET_REACHED")

            available = self._available_adaptive_actions(state)
            if not available:
                return self._finalize(state, "NO_AVAILABLE_ADAPTIVE_ACTION")
            state = self._replace(
                state,
                status=InvestigationStatus.SELECTING_ADAPTIVE_EXPERIMENT,
                available_tests=list(available),
            )
            skeptic = await self._infer(
                state, role="skeptic", schema=SkepticDecision, available=available
            )
            state = self.get(run_id)
            assert isinstance(skeptic, SkepticDecision)
            self._validate_skeptic_identity(state, skeptic)
            state = self._replace(
                state, accepted_decisions=[*state.accepted_decisions, skeptic]
            )
            self._emit(
                state,
                "agent.decision",
                {
                    "role": "skeptic",
                    "model_identity": self._model_identity,
                    "decision": skeptic.model_dump(mode="json"),
                    "context_version": state.context_version,
                },
            )

            state = self._replace(state, status=InvestigationStatus.WAITING_FOR_CRITIC)
            critic = await self._infer(
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
                    "model_identity": self._model_identity,
                    "decision": critic.model_dump(mode="json"),
                    "context_version": state.context_version,
                },
            )

            if critic.verdict == CriticVerdict.VETO:
                return self._finalize(state, f"CRITIC_VETO:{critic.reason_code}")
            tool_name = skeptic.requested_experiment
            parameters = skeptic.parameters
            if critic.verdict == CriticVerdict.REVISE:
                if state.critic_revision_count >= state.max_critic_revisions:
                    raise _HarnessAbort(
                        HarnessFailureKind.BUDGET_EXHAUSTED,
                        "Critic revision budget reached",
                        status=InvestigationStatus.BUDGET_EXHAUSTED,
                        recoverable=False,
                    )
                tool_name = critic.revised_experiment or ""
                parameters = critic.revised_parameters or {}
                state = self._replace(
                    state, critic_revision_count=state.critic_revision_count + 1
                )

            result = self._execute_action(
                state,
                tool_name,
                parameters,
                adaptive=True,
                agent_decision_id=skeptic.decision_id,
                critic_decision_id=critic.decision_id,
            )
            state = self.get(run_id)
            return self._after_result(state, result)
        except _HarnessAbort as exc:
            return self._terminate(
                self.get(run_id),
                exc.kind,
                exc.reason,
                status=exc.status,
                recoverable=exc.recoverable,
                action_id=exc.action_id,
            )

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
    ) -> BaseModel:
        while True:
            state = self.get(state.run_id)
            if state.model_call_count >= state.max_model_calls:
                raise _HarnessAbort(
                    HarnessFailureKind.BUDGET_EXHAUSTED,
                    "model-call budget reached before inference",
                    status=InvestigationStatus.BUDGET_EXHAUSTED,
                    recoverable=False,
                )
            context = assemble_context(
                state,
                self.artifacts.read_evidence(state),
                role=role,  # type: ignore[arg-type]
                available_experiments=available,
                proposed_decision=proposed_decision,
            )
            state = self._replace(state, model_call_count=state.model_call_count + 1)
            self._emit(
                state,
                "agent.started",
                {
                    "role": role,
                    "model_identity": self._model_identity,
                    "context_version": context.context_version,
                },
            )
            try:
                output = await self.inference.decide(
                    role=role, context=context, output_schema=schema
                )
                return schema.model_validate(output, strict=True)
            except (ModelProviderTimeoutError, TimeoutError):
                kind = HarnessFailureKind.MODEL_TIMEOUT
                reason = f"{role} inference timed out"
            except (ModelProviderError, ConnectionError):
                kind = HarnessFailureKind.MODEL_PROVIDER_FAILURE
                reason = f"{role} inference provider failed"
            except (InvalidModelOutputError, ValidationError, TypeError) as exc:
                raise _HarnessAbort(
                    HarnessFailureKind.INVALID_MODEL_OUTPUT,
                    f"{role} returned invalid structured output: {exc}",
                ) from exc

            state = self.get(state.run_id)
            if state.model_retry_count >= state.max_model_retries:
                raise _HarnessAbort(kind, reason)
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
                {"role": role, "kind": kind, "retry_count": state.model_retry_count},
            )

    def _run_next_mandatory(
        self, state: InvestigationState, missing: frozenset[str]
    ) -> InvestigationState:
        candidates = [
            spec
            for spec in self.registry.specs
            if spec.mandatory_test in missing
            and spec.required_completed_tests.issubset(state.completed_tests)
        ]
        if not candidates:
            return self._terminate(
                state,
                HarnessFailureKind.INSUFFICIENT_EVIDENCE,
                f"no registered action can complete mandatory tests: {sorted(missing)}",
                status=InvestigationStatus.INSUFFICIENT_EVIDENCE,
                recoverable=False,
            )
        state = self._replace(state, status=InvestigationStatus.VETTING_MANDATORY)
        spec = candidates[0]
        try:
            result = self._execute_action(state, spec.name, {}, adaptive=False)
        except _HarnessAbort:
            raise
        return self._after_result(self.get(state.run_id), result)

    def _available_adaptive_actions(self, state: InvestigationState) -> tuple[str, ...]:
        completed = set(state.completed_tests)
        executed = {
            item.action_signature
            for item in state.tool_executions
            if item.status in {ToolExecutionStatus.PREPARED, ToolExecutionStatus.COMPLETED}
        }
        return tuple(
            spec.name
            for spec in self.registry.specs
            if spec.adaptive
            and spec.required_completed_tests.issubset(completed)
            and self._action_signature(spec.name, {}) not in executed
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
            or critic.skeptic_decision_id != skeptic.decision_id
        ):
            raise _HarnessAbort(
                HarnessFailureKind.INVALID_MODEL_OUTPUT,
                "Critic role, run, step, or proposal identifier does not match",
            )

    def _execute_action(
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
        runtime_inputs = self._runtime_inputs_for_action(state, spec)
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
            },
            action_id=action_id,
        )
        try:
            result = spec.handler(
                state.run_id, action_id, state.opaque_target_id, invocation_parameters
            )
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
            raise _HarnessAbort(
                HarnessFailureKind.TOOL_INFRASTRUCTURE_FAILURE,
                f"tool result validation failed for {tool_name}",
                recoverable=False,
                action_id=action_id,
            ) from exc
        if result_parameters != validated_parameters:
            raise _HarnessAbort(
                HarnessFailureKind.TOOL_INFRASTRUCTURE_FAILURE,
                f"tool result parameters do not match invocation for {tool_name}",
                recoverable=False,
                action_id=action_id,
            )
        return self._commit_result(state, result)

    def _runtime_inputs_for_action(
        self,
        state: InvestigationState,
        spec: ScientificToolSpec,
    ) -> dict[str, Any]:
        if spec.runtime_input_schema is None:
            return {}
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
        run_dir = self.artifacts.run_dir(state.opaque_target_id, state.run_id)
        return {
            "cached_path": source.cached_path,
            "artifact_dir": run_dir / "artifacts",
            "ledger_path": self.artifacts.evidence_path(state),
            "step_id": f"step_{state.step_count:04d}",
            "write_evidence": False,
        }

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
        hypotheses, strongest = self._updated_hypotheses(state, interpretation_code)
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
        if result.status == ToolStatus.FAILED:
            return self._terminate(
                state,
                HarnessFailureKind.TOOL_INFRASTRUCTURE_FAILURE,
                f"tool returned FAILED: {result.tool_name}",
                recoverable=False,
                action_id=result.action_id,
            )
        if result.status == ToolStatus.PRECONDITION_FAILED:
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
        interpretation = result.diagnostics.get("interpretation_code")
        if interpretation in _DECISIVE_INTERPRETATIONS:
            return self._finalize(state, f"DETERMINISTIC_EVIDENCE:{interpretation}")
        if missing_mandatory_tests(set(state.completed_tests)):
            return self._replace(state, status=InvestigationStatus.VETTING_MANDATORY)
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
        elif "CLEAN_PLANET_LIKE" in codes or any(
            item.adaptive and item.status == ToolExecutionStatus.COMPLETED
            for item in state.tool_executions
        ):
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

    def _recover_prepared_execution(self, state: InvestigationState) -> InvestigationState:
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
                    runtime_inputs = self._runtime_inputs_for_action(state, spec)
                    validated_runtime_inputs = self.registry.validate_runtime_inputs(
                        spec, runtime_inputs
                    )
                    invocation_parameters = self.registry.invocation_parameters(
                        execution.tool_name,
                        validated_parameters=recovered_parameters,
                        validated_runtime_inputs=validated_runtime_inputs,
                    )
                    result = spec.handler(
                        state.run_id,
                        execution.action_id,
                        state.opaque_target_id,
                        invocation_parameters,
                    )
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
                    raise _HarnessAbort(
                        HarnessFailureKind.TOOL_INFRASTRUCTURE_FAILURE,
                        "tool result identifiers do not match recovered invocation for "
                        f"{execution.tool_name}",
                        recoverable=False,
                        action_id=execution.action_id,
                    )
                try:
                    self._commit_result(state, result)
                except (ActionValidationError, ValueError) as exc:
                    raise _HarnessAbort(
                        HarnessFailureKind.TOOL_INFRASTRUCTURE_FAILURE,
                        f"tool result validation failed while recovering {execution.tool_name}",
                        recoverable=False,
                        action_id=execution.action_id,
                    ) from exc
                state = self.get(state.run_id)
            state = self._after_result(state, result)
            if self._cannot_advance(state):
                break
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
        hypotheses, strongest = self._updated_hypotheses(
            state, record.interpretation_code
        )
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

    @staticmethod
    def _updated_hypotheses(
        state: InvestigationState, interpretation_code: str | None
    ) -> tuple[list[str], str | None]:
        rules = {
            "CLEAN_PLANET_LIKE": (["planetary_transit"], "eclipsing_binary"),
            "ODD_EVEN_MISMATCH": (["eclipsing_binary"], "planetary_transit"),
            "CONTAMINATION_LIKELY": (["background_contamination"], "planetary_transit"),
            "WEAK_NOISY": (["instrumental_or_variable_noise"], "planetary_transit"),
        }
        return rules.get(
            interpretation_code,
            (state.active_hypotheses, state.strongest_unresolved_alternative),
        )

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
        self._states[state.run_id] = updated
        self.artifacts.save_state(updated)
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
        self._events[state.run_id].append(event)
        self.artifacts.append_trace(state, event)

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
