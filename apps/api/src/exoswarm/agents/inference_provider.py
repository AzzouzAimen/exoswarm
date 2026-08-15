from __future__ import annotations

from secrets import token_hex
from time import perf_counter
from typing import Any

from pydantic import BaseModel, ValidationError

from exoswarm.agents.context import AgentContextPacket, assert_agent_safe_context
from exoswarm.agents.model_client import AttemptKind, InferenceAttemptOutcome
from exoswarm.agents.prompt_registry import effective_output_token_limit, render_role_prompt
from exoswarm.agents.role_context import SafeRoleEnvelope
from exoswarm.agents.skeptic import safe_repair_feedback
from exoswarm.domain.enums import AgentRole, ThinkingMode
from exoswarm.domain.errors import (
    InvalidModelOutputError,
    ModelOutputTruncatedError,
    ModelProviderError,
    ModelProviderTimeoutError,
)
from exoswarm.domain.models import (
    CriticDecision,
    DirectorDecision,
    InferenceTraceRecord,
    ObserverAssessment,
    SignalAssessment,
    SkepticDecision,
    TransitHunterBrief,
)

FEATHERLESS_BASE_URL = "https://api.featherless.ai/v1"
FEATHERLESS_PROVIDER = "featherless"
ALLOWED_ROLES = frozenset(role.value for role in AgentRole)
ROLE_OUTPUT_SCHEMAS: dict[str, type[BaseModel]] = {
    "director": DirectorDecision,
    "observer": ObserverAssessment,
    "signal": SignalAssessment,
    "transit_hunter": TransitHunterBrief,
    "skeptic": SkepticDecision,
    "critic": CriticDecision,
}


def _attribute(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


class FeatherlessInferenceClient:
    """OpenAI-compatible Featherless adapter with a strict, raw-output-free boundary."""

    provider = FEATHERLESS_PROVIDER

    def __init__(
        self,
        *,
        api_key: str,
        model_identity: str = "deepseek-ai/DeepSeek-V4-Flash-0731",
        base_url: str = FEATHERLESS_BASE_URL,
        timeout_seconds: float = 30.0,
        max_output_tokens: int = 900,
        role_thinking_modes: dict[AgentRole, ThinkingMode] | None = None,
        thinking_confirmed_roles: set[AgentRole] | frozenset[AgentRole] = frozenset(),
        sdk: Any | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("FEATHERLESS_API_KEY is required")
        self.model_identity = model_identity
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.max_output_tokens = max_output_tokens
        self.role_thinking_modes = dict(role_thinking_modes or {})
        self.thinking_confirmed_roles = frozenset(thinking_confirmed_roles)
        self.supported_roles = frozenset(AgentRole)
        if sdk is None:
            from openai import AsyncOpenAI

            sdk = AsyncOpenAI(
                api_key=api_key,
                base_url=self.base_url,
                timeout=timeout_seconds,
                max_retries=0,
                default_headers={
                    "HTTP-Referer": "https://github.com/ExoSwarm/ExoSwarm",
                    "X-Title": "ExoSwarm",
                },
            )
        self._sdk = sdk

    @classmethod
    def from_settings(cls, settings: Any, *, sdk: Any | None = None) -> FeatherlessInferenceClient:
        secret = settings.featherless_api_key
        if secret is None:
            raise ValueError("FEATHERLESS_API_KEY is required")
        return cls(
            api_key=secret.get_secret_value(),
            model_identity=settings.model,
            base_url=settings.featherless_base_url,
            timeout_seconds=settings.inference_timeout_seconds,
            max_output_tokens=settings.inference_max_output_tokens,
            role_thinking_modes=settings.role_thinking_modes,
            thinking_confirmed_roles=settings.thinking_confirmed_roles,
            sdk=sdk,
        )

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
        if role not in ALLOWED_ROLES:
            raise ValueError(f"Featherless inference role is not allowed: {role}")
        packet: BaseModel
        if role in {"skeptic", "critic"}:
            packet = AgentContextPacket.model_validate(context, strict=True)
        else:
            if not isinstance(context, SafeRoleEnvelope):
                raise ValueError("specialist inference requires a sanitized role context")
            packet = context
        if str(packet.role) != role:
            raise ValueError("inference role does not match the sanitized context role")
        if output_schema is not ROLE_OUTPUT_SCHEMAS[role]:
            raise ValueError("requested output schema is not allowed for the inference role")
        assert_agent_safe_context(packet)
        call_id = f"call_{token_hex(12)}"
        feedback = safe_repair_feedback(validation_error_code) if attempt_kind == "repair" else None
        rendered = render_role_prompt(
            role=role,
            context=packet,
            output_schema=output_schema,
            repair_feedback=feedback,
        )
        agent_role = AgentRole(role)
        thinking_mode = self.role_thinking_modes.get(agent_role, ThinkingMode.OFF)
        output_token_limit = effective_output_token_limit(
            agent_role,
            configured_max_output_tokens=self.max_output_tokens,
            thinking_mode=thinking_mode,
        )
        common = {
            "call_id": call_id,
            "run_id": packet.run_id,
            "step_id": packet.step_id,
            "role": role,
            "provider": self.provider,
            "model_identity": self.model_identity,
            "attempt_kind": attempt_kind,
            "context_version": packet.context_version,
            "context_fingerprint": packet.context_fingerprint,
            "prompt_version": rendered.prompt_version,
            "prompt_template_sha256": rendered.prompt_template_sha256,
            "rendered_request_sha256": rendered.rendered_request_sha256,
            "example_set_version": rendered.example_set_version,
            "thinking_mode": thinking_mode,
            "thinking_requested": thinking_mode == ThinkingMode.ON,
            "thinking_confirmed": (
                thinking_mode == ThinkingMode.ON
                and agent_role in self.thinking_confirmed_roles
            ),
            "output_schema": output_schema.__name__,
            "fallback_used": fallback_used,
        }
        messages = rendered.messages
        template_kwargs: dict[str, bool] = {}
        if thinking_mode != ThinkingMode.AUTO:
            template_kwargs["thinking"] = thinking_mode == ThinkingMode.ON
        started = perf_counter()
        try:
            response = await self._sdk.chat.completions.create(
                model=self.model_identity,
                messages=messages,
                temperature=0,
                max_tokens=output_token_limit,
                response_format={"type": "json_object"},
                extra_body=(
                    {"chat_template_kwargs": template_kwargs} if template_kwargs else None
                ),
            )
        except Exception as exc:  # SDK types vary across injected and installed transports.
            latency_ms = max(0, round((perf_counter() - started) * 1000))
            error_type = type(exc).__name__
            if isinstance(exc, TimeoutError) or "timeout" in error_type.lower():
                error = ModelProviderTimeoutError("Featherless inference timed out")
                call = InferenceTraceRecord(
                    **common,
                    latency_ms=latency_ms,
                    status="TIMEOUT",
                    schema_valid=False,
                    timeout=True,
                )
            else:
                error = ModelProviderError("Featherless inference provider failed")
                call = InferenceTraceRecord(
                    **common,
                    latency_ms=latency_ms,
                    status="PROVIDER_ERROR",
                    schema_valid=False,
                    provider_error_type=error_type[:100],
                )
            return InferenceAttemptOutcome(call=call, error=error)

        latency_ms = max(0, round((perf_counter() - started) * 1000))
        response_model = _attribute(response, "model")
        if isinstance(response_model, str) and response_model:
            common["model_identity"] = response_model
        usage = _attribute(response, "usage")
        input_tokens = _attribute(usage, "prompt_tokens") if usage is not None else None
        output_tokens = _attribute(usage, "completion_tokens") if usage is not None else None
        choices = _attribute(response, "choices", [])
        finish_reason = None
        if choices:
            candidate_finish_reason = _attribute(choices[0], "finish_reason")
            if candidate_finish_reason is not None:
                finish_reason = str(candidate_finish_reason)[:100]
        if finish_reason == "length":
            error = ModelOutputTruncatedError(
                f"Featherless {role} response reached the configured output-token limit"
            )
            call = InferenceTraceRecord(
                **common,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency_ms=latency_ms,
                status="OUTPUT_TRUNCATED",
                schema_valid=False,
                validation_error_code=error.code,
                finish_reason=finish_reason,
            )
            return InferenceAttemptOutcome(call=call, error=error)
        try:
            message = _attribute(choices[0], "message")
            content = _attribute(message, "content")
            if not isinstance(content, str) or not content.strip():
                raise ValueError("empty completion content")
            decision = output_schema.model_validate_json(content, strict=True)
        except ValidationError as validation_error:
            first_error = validation_error.errors(
                include_url=False, include_context=False, include_input=False
            )[0]
            location = ".".join(str(part) for part in first_error.get("loc", ()))
            error_type = str(first_error.get("type", "validation_error"))
            if location:
                error_type = f"{error_type}@{location}"
            error = InvalidModelOutputError(
                f"Featherless {role} response failed {output_schema.__name__} validation"
            )
            call = InferenceTraceRecord(
                **common,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency_ms=latency_ms,
                status="INVALID",
                schema_valid=False,
                validation_error_code=error.code,
                finish_reason=finish_reason,
                error_type=error_type[:100],
            )
            return InferenceAttemptOutcome(call=call, error=error)
        except (IndexError, TypeError, ValueError) as parse_error:
            error = InvalidModelOutputError(
                f"Featherless {role} response failed {output_schema.__name__} validation"
            )
            call = InferenceTraceRecord(
                **common,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency_ms=latency_ms,
                status="INVALID",
                schema_valid=False,
                validation_error_code=error.code,
                finish_reason=finish_reason,
                error_type=type(parse_error).__name__,
            )
            return InferenceAttemptOutcome(call=call, error=error)
        call = InferenceTraceRecord(
            **common,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            status="SUCCESS",
            schema_valid=True,
            finish_reason=finish_reason,
        )
        return InferenceAttemptOutcome(call=call, decision=decision)

    @staticmethod
    def _messages(
        *,
        role: str,
        context: BaseModel,
        output_schema: type[BaseModel],
        attempt_kind: AttemptKind,
        validation_error_code: str | None,
    ) -> list[dict[str, str]]:
        """Compatibility adapter for tests and diagnostics that inspect safe requests."""

        return render_role_prompt(
            role=role,
            context=context,
            output_schema=output_schema,
            repair_feedback=(
                safe_repair_feedback(validation_error_code)
                if attempt_kind == "repair"
                else None
            ),
        ).messages
