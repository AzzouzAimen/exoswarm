from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Callable, Mapping, Sequence
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, ValidationError

from exoswarm.domain.errors import InvalidModelOutputError, ModelNotConfiguredError


class InferenceCall(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    call_id: str
    model_identity: str
    role: str
    output_schema: str
    run_id: str
    step_id: str
    context_version: str
    status: str
    error_type: str | None = None


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


class UnconfiguredInferenceClient:
    model_identity = "unconfigured"

    async def decide(
        self, *, role: str, context: BaseModel, output_schema: type[BaseModel]
    ) -> BaseModel:
        del role, context, output_schema
        raise ModelNotConfiguredError("live model inference is not configured in the scaffold")


class ScriptedInferenceClient:
    """Deterministic queued inference for local harness tests and evaluations."""

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
        queue = self._responses.get(role)
        self._role_counts[role] += 1
        call_id = f"mock_call_{role}_{self._role_counts[role]:04d}"
        common = {
            "call_id": call_id,
            "model_identity": self.model_identity,
            "role": role,
            "output_schema": output_schema.__name__,
            "run_id": str(getattr(context, "run_id", "unknown")),
            "step_id": str(getattr(context, "step_id", "unknown")),
            "context_version": str(getattr(context, "context_version", "unknown")),
        }
        if not queue:
            error = InvalidModelOutputError(f"no scripted response remains for role {role}")
            self.calls.append(
                InferenceCall(**common, status="ERROR", error_type=type(error).__name__)
            )
            raise error

        response = queue.popleft()
        if callable(response):
            response = response(context, output_schema)
        if isinstance(response, Exception):
            self.calls.append(
                InferenceCall(**common, status="ERROR", error_type=type(response).__name__)
            )
            raise response
        try:
            validated = output_schema.model_validate(response)
        except (ValidationError, TypeError) as exc:
            error = InvalidModelOutputError(
                f"scripted {role} response failed {output_schema.__name__} validation"
            )
            self.calls.append(
                InferenceCall(**common, status="INVALID", error_type=type(exc).__name__)
            )
            raise error from exc
        self.calls.append(InferenceCall(**common, status="SUCCESS"))
        return validated
