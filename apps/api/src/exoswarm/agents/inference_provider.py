from __future__ import annotations

import json
from secrets import token_hex
from time import perf_counter
from typing import Any

from pydantic import BaseModel, ValidationError

from exoswarm.agents.context import AgentContextPacket, assert_agent_safe_context
from exoswarm.agents.model_client import AttemptKind, InferenceAttemptOutcome
from exoswarm.domain.errors import (
    InvalidModelOutputError,
    ModelProviderError,
    ModelProviderTimeoutError,
)
from exoswarm.domain.models import InferenceTraceRecord

FEATHERLESS_BASE_URL = "https://api.featherless.ai/v1"
FEATHERLESS_PROVIDER = "featherless"
ALLOWED_ROLES = frozenset({"skeptic", "critic"})


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
        sdk: Any | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("FEATHERLESS_API_KEY is required")
        self.model_identity = model_identity
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.max_output_tokens = max_output_tokens
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
        packet = AgentContextPacket.model_validate(context, strict=True)
        assert_agent_safe_context(packet)
        call_id = f"call_{token_hex(12)}"
        common = {
            "call_id": call_id,
            "run_id": packet.run_id,
            "step_id": packet.step_id,
            "role": role,
            "provider": self.provider,
            "model_identity": self.model_identity,
            "attempt_kind": attempt_kind,
            "context_version": packet.context_version,
            "fallback_used": fallback_used,
        }
        messages = self._messages(
            role=role,
            context=packet,
            output_schema=output_schema,
            attempt_kind=attempt_kind,
            validation_error_code=validation_error_code,
        )
        started = perf_counter()
        try:
            response = await self._sdk.chat.completions.create(
                model=self.model_identity,
                messages=messages,
                temperature=0,
                max_tokens=self.max_output_tokens,
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
        try:
            choices = _attribute(response, "choices", [])
            message = _attribute(choices[0], "message")
            content = _attribute(message, "content")
            if not isinstance(content, str) or not content.strip():
                raise ValueError("empty completion content")
            decision = output_schema.model_validate_json(content, strict=True)
        except (IndexError, TypeError, ValueError, ValidationError):
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
            )
            return InferenceAttemptOutcome(call=call, error=error)
        call = InferenceTraceRecord(
            **common,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            status="SUCCESS",
            schema_valid=True,
        )
        return InferenceAttemptOutcome(call=call, decision=decision)

    @staticmethod
    def _messages(
        *,
        role: str,
        context: AgentContextPacket,
        output_schema: type[BaseModel],
        attempt_kind: AttemptKind,
        validation_error_code: str | None,
    ) -> list[dict[str, str]]:
        repair = ""
        if attempt_kind == "repair":
            repair = (
                " This is the single repair attempt. The previous response failed validation "
                f"with code {validation_error_code or 'INVALID_MODEL_OUTPUT'}."
            )
        system = (
            f"You are the ExoSwarm {role}. Select or review only bounded scientific actions. "
            "Deterministic Python is authoritative for every measurement and action. "
            "Return exactly one JSON object matching the supplied schema, with no markdown, "
            "commentary, hidden reasoning, or additional keys." + repair
        )
        user_payload = {
            "objective": (
                "Select the most discriminating allowed experiment."
                if role == "skeptic"
                else "Review the Skeptic proposal with APPROVE, REVISE, or VETO."
            ),
            "context": context.model_dump(mode="json"),
            "output_schema": output_schema.model_json_schema(),
        }
        return [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": json.dumps(user_payload, separators=(",", ":"), sort_keys=True),
            },
        ]
