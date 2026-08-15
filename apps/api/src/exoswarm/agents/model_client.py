from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from time import perf_counter
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ValidationError

from exoswarm.agents.critic import CRITIC_PROMPT_VERSION
from exoswarm.agents.skeptic import SKEPTIC_PROMPT_VERSION, safe_repair_feedback
from exoswarm.domain.errors import (
    InvalidModelOutputError,
    ModelNotConfiguredError,
    ModelProviderError,
    ModelProviderTimeoutError,
)
from exoswarm.domain.models import InferenceTraceRecord

InferenceCall = InferenceTraceRecord
AttemptKind = Literal["primary", "repair"]


@dataclass(frozen=True, slots=True)
class InferenceAttemptOutcome:
    """One attempt result; raw provider content never crosses this boundary."""

    call: InferenceTraceRecord
    decision: BaseModel | None = None
    error: Exception | None = None


ScriptedResponse = (
    BaseModel
    | Mapping[str, Any]
    | Exception
    | Callable[[BaseModel, type[BaseModel]], BaseModel | Mapping[str, Any] | Exception]
)


class InferenceClient(Protocol):
    async def decide(
        self, *, role: str, context: BaseModel, output_schema: type[BaseModel]
    ) -> BaseModel: ...


class AttemptInferenceClient(InferenceClient, Protocol):
    async def decide_attempt(
        self,
        *,
        role: str,
        context: BaseModel,
        output_schema: type[BaseModel],
        attempt_kind: AttemptKind,
        validation_error_code: str | None = None,
        fallback_used: bool = False,
    ) -> InferenceAttemptOutcome: ...


class UnconfiguredInferenceClient:
    provider = "unconfigured"
    model_identity = "unconfigured"

    async def decide(
        self, *, role: str, context: BaseModel, output_schema: type[BaseModel]
    ) -> BaseModel:
        del role, context, output_schema
        raise ModelNotConfiguredError("live model inference is not configured")


class ScriptedInferenceClient:
    """Deterministic queued inference for local harness tests and evaluations."""

    provider = "scripted"

    def __init__(
        self,
        responses: Mapping[str, Sequence[ScriptedResponse]],
        *,
        model_identity: str = "mock:scripted-v1",
    ) -> None:
        self.model_identity = model_identity
        self._responses = {
            role: deque(role_responses) for role, role_responses in responses.items()
        }
        self.calls: list[InferenceCall] = []
        self._role_counts: defaultdict[str, int] = defaultdict(int)

    async def decide(
        self, *, role: str, context: BaseModel, output_schema: type[BaseModel]
    ) -> BaseModel:
        outcome = await self.decide_attempt(
            role=role,
            context=context,
            output_schema=output_schema,
            attempt_kind="primary",
        )
        if outcome.error is not None:
            raise outcome.error
        assert outcome.decision is not None
        return outcome.decision

    async def decide_attempt(
        self,
        *,
        role: str,
        context: BaseModel,
        output_schema: type[BaseModel],
        attempt_kind: AttemptKind,
        validation_error_code: str | None = None,
        fallback_used: bool = False,
    ) -> InferenceAttemptOutcome:
        started = perf_counter()
        queue = self._responses.get(role)
        self._role_counts[role] += 1
        call_id = f"mock_call_{role}_{self._role_counts[role]:04d}"
        common = {
            "call_id": call_id,
            "provider": self.provider,
            "model_identity": self.model_identity,
            "output_schema": output_schema.__name__,
            "role": role,
            "attempt_kind": attempt_kind,
            "run_id": str(getattr(context, "run_id", "unknown")),
            "step_id": str(getattr(context, "step_id", "unknown")),
            "context_version": str(getattr(context, "context_version", "unknown")),
            "context_fingerprint": str(
                getattr(context, "context_fingerprint", "0" * 64)
            ),
            "prompt_version": (
                SKEPTIC_PROMPT_VERSION if role == "skeptic" else CRITIC_PROMPT_VERSION
            ),
            "validation_error_code": (
                safe_repair_feedback(validation_error_code).code
                if attempt_kind == "repair"
                else None
            ),
            "fallback_used": fallback_used,
        }
        if not queue:
            error = InvalidModelOutputError(f"no scripted response remains for role {role}")
            return self._record(
                common,
                started,
                status="INVALID",
                schema_valid=False,
                validation_error_code=error.code,
                error_type=type(error).__name__,
                error=error,
            )

        response = queue.popleft()
        if callable(response):
            response = response(context, output_schema)
        if isinstance(response, Exception):
            if isinstance(response, (ModelProviderTimeoutError, TimeoutError)):
                return self._record(
                    common,
                    started,
                    status="TIMEOUT",
                    schema_valid=False,
                    timeout=True,
                    error_type=type(response).__name__,
                    error=response,
                )
            if isinstance(response, (ModelProviderError, ConnectionError)):
                return self._record(
                    common,
                    started,
                    status="PROVIDER_ERROR",
                    schema_valid=False,
                    provider_error_type=type(response).__name__,
                    error_type=type(response).__name__,
                    error=response,
                )
            return self._record(
                common,
                started,
                status="PROVIDER_ERROR",
                schema_valid=False,
                provider_error_type=type(response).__name__,
                error_type=type(response).__name__,
                error=response,
            )
        try:
            # Preserve mapping-fixture compatibility; the controller still revalidates
            # the resulting typed decision strictly before any state mutation.
            validated = output_schema.model_validate(response)
        except (ValidationError, TypeError):
            error = InvalidModelOutputError(
                f"scripted {role} response failed {output_schema.__name__} validation"
            )
            return self._record(
                common,
                started,
                status="INVALID",
                schema_valid=False,
                validation_error_code=error.code,
                error_type="ValidationError",
                error=error,
            )
        return self._record(
            common,
            started,
            status="SUCCESS",
            schema_valid=True,
            decision=validated,
        )

    def _record(
        self,
        common: dict[str, Any],
        started: float,
        *,
        status: Literal["SUCCESS", "INVALID", "TIMEOUT", "PROVIDER_ERROR"],
        schema_valid: bool,
        validation_error_code: str | None = None,
        timeout: bool = False,
        provider_error_type: str | None = None,
        error_type: str | None = None,
        decision: BaseModel | None = None,
        error: Exception | None = None,
    ) -> InferenceAttemptOutcome:
        trace_payload = {
            **common,
            "validation_error_code": (
                validation_error_code
                if validation_error_code is not None
                else common.get("validation_error_code")
            ),
        }
        call = InferenceTraceRecord(
            **trace_payload,
            latency_ms=max(0, round((perf_counter() - started) * 1000)),
            status=status,
            schema_valid=schema_valid,
            timeout=timeout,
            provider_error_type=provider_error_type,
            error_type=error_type,
        )
        self.calls.append(call)
        return InferenceAttemptOutcome(call=call, decision=decision, error=error)
